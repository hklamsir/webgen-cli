import os
import time
import logging
import threading
import re
from pathlib import Path
from watchdog.events import FileSystemEventHandler
from typing import Callable, Optional

class HtmlSynchronizer:
    """
    處理將 HTML 內容同步回 workings/ 的核心邏輯。
    """
    def __init__(self, project_path: Path, logger: logging.Logger):
        self.project_path = project_path.resolve()
        self.workings_path = self.project_path / 'workings'
        self.logger = logger
        # 用於防止對同一個 *目標* 檔案的並發寫入
        self.file_write_locks = {} 
        self.lock_gen_lock = threading.Lock()
        self.logger.info(f"HtmlSynchronizer 初始化，目標目錄: {self.workings_path}")

    def _get_file_lock(self, path: Path) -> threading.Lock:
        """獲取或創建一個特定於檔案路徑的鎖。"""
        with self.lock_gen_lock:
            if path not in self.file_write_locks:
                self.file_write_locks[path] = threading.Lock()
            return self.file_write_locks[path]

    def sync_to_workings(self, src_path: Path) -> bool:
        """
        讀取 src_path，提取 <main> 到 <footer> 之間的內容，
        並將其寫入 workings/ 目錄下的對應路徑。
        返回 True 表示成功。
        """
        try:
            # 確保傳入的是 Path 物件
            relative_path = src_path.relative_to(self.project_path)
            target_path = self.workings_path / relative_path

            # 嘗試讀取 (帶重試，應對短暫的檔案鎖定)
            content = ""
            for _ in range(3):
                try:
                    content = src_path.read_text(encoding='utf-8')
                    break
                except (IOError, PermissionError):
                    time.sleep(0.1)
            
            if not content:
                self.logger.warning(f"Sync: 無法讀取 {relative_path} (可能被鎖定或為空)。")
                return False

            # 提取 <main> 到 <footer>
            # 使用非貪婪匹配捕捉 main 區塊
            match = re.search(r'(<main\b.*?)<footer\b', content, re.DOTALL | re.IGNORECASE)
            if match:
                final_content = match.group(1).strip()
            else:
                # 如果找不到標準結構，嘗試提取 body 內容作為後備方案，或報錯
                body_match = re.search(r'<body\b.*?>(.*?)</body>', content, re.DOTALL | re.IGNORECASE)
                if body_match:
                     final_content = f"<!-- 自動同步: 未找到 main/footer，僅同步 body 內容 -->\n{body_match.group(1).strip()}"
                else:
                     final_content = f"<!-- 同步失敗: 找不到 main/footer 或 body -->"

            # 獲取目標檔案的鎖並安全寫入
            file_lock = self._get_file_lock(target_path)
            with file_lock:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(final_content, encoding='utf-8')
            
            return True

        except Exception as e:
            self.logger.error(f"同步 {src_path.name} 時發生未預期錯誤: {e}", exc_info=True)
            return False

class HtmlSyncHandler(FileSystemEventHandler):
    """
    監控 HTML 檔案變更，並觸發 HtmlSynchronizer。
    處理 mtime 去抖動和暫停/恢復邏輯。
    """
    def __init__(self, 
                 project_path: Path, 
                 synchronizer: HtmlSynchronizer,
                 sync_ui_callback: Callable[[Path], None]):
        
        self.project_path = project_path.resolve()
        self.workings_path = self.project_path / 'workings'
        self.logger = logging.getLogger(__name__)
        
        self.synchronizer = synchronizer
        self.sync_ui_callback = sync_ui_callback
        
        # 儲存檔案的最後修改時間，防止重複觸發
        self.last_mtimes = {} 
        # 線程鎖，確保 mtime 檢查的原子性
        self.sync_lock = threading.Lock()
        
        # 用於暫停/恢復的事件
        self._paused = threading.Event()
        self._paused.set() # 預設為 True (即 "resumed" 狀態)
        
        self.logger.info(f"HtmlSyncHandler 初始化。監控根目錄: {self.project_path}")

    def pause(self):
        """暫停事件處理。"""
        self._paused.clear()
        self.logger.info("Watchdog: 已暫停監控。")

    def resume(self):
        """
        恢復事件處理。
        關鍵修正：在恢復前，重新掃描所有檔案的 mtime。
        這確保了暫停期間發生的任何變更（如 updatehtml 造成的變更）
        都被視為「已知」狀態，不會在恢復後立即觸發同步。
        """
        self.logger.info("[Watchdog] 準備恢復，正在更新 mtime 基準...")
        
        update_count = 0
        error_count = 0

        with self.sync_lock:
            # 重新掃描專案根目錄下的所有 HTML 檔
            for p in self.project_path.rglob('*.html'):
                try:
                    if not p.is_file():
                        continue
                    if p.is_relative_to(self.workings_path):
                        continue
                    resolved_p = p.resolve()
                    mtime = p.stat().st_mtime
                    self.last_mtimes[resolved_p] = mtime
                    update_count += 1
                except FileNotFoundError:
                    self.logger.debug(f"[Watchdog/Resume] 檔案已刪除: {p.name}")
                    error_count += 1
                except PermissionError:
                    self.logger.warning(f"[Watchdog/Resume] 無權限: {p.name}")
                    error_count += 1
                except Exception as e:
                    self.logger.debug(f"[Watchdog/Resume] 異常: {e}")
                    error_count += 1

        self._paused.set()
        self.logger.info(f"[Watchdog] 已恢復監控 ({update_count} 個基準, {error_count} 個錯誤)。")

    def _handle_event(self, src_path_str: str):
        """
        處理檔案系統事件的核心邏輯。包括防禦性檢查。
        """
        # 如果處於暫停狀態，直接忽略事件
        if not self._paused.is_set():
            return

        try:
            src_path = Path(src_path_str).resolve()
        except Exception as e:
            self.logger.debug(f"[Watchdog/Event] 無效路徑 {src_path_str}: {e}")
            return

        # 基本過濾條件
        if src_path.suffix.lower() != '.html':
            return
        try:
            if src_path.is_relative_to(self.workings_path):
                return
        except ValueError:
            pass
            
        # 檢查 mtime 是否真的改變了
        try:
            if not src_path.exists():
                self.logger.debug(f"[Watchdog/Event] 檔案已刪除: {src_path.name}")
                self.last_mtimes.pop(src_path, None)
                return
            current_mtime = src_path.stat().st_mtime
        except FileNotFoundError:
            self.logger.debug(f"[Watchdog/Event] 檔案在讀取中被刪除: {src_path.name}")
            self.last_mtimes.pop(src_path, None)
            return
        except PermissionError:
            self.logger.warning(f"[Watchdog/Event] 無權限讀取: {src_path.name}")
            return
        except (IOError, OSError) as e:
            self.logger.warning(f"[Watchdog/Event] OS 錯誤: {e}")
            return

        # 判斷檔案位置用於日誌
        try:
            is_in_root = not src_path.is_relative_to(self.workings_path)
            location_hint = "[ROOT]" if is_in_root else "[WORKINGS]"
        except ValueError:
            location_hint = "[UNKNOWN]"

        with self.sync_lock:
            last_mtime = self.last_mtimes.get(src_path)
            if last_mtime is not None and last_mtime == current_mtime:
                self.logger.debug(f"[Watchdog/Event] {location_hint} mtime 未變化，跳過")
                return
            self.last_mtimes[src_path] = current_mtime
            
        # 觸發同步
        self.logger.info(f"[Watchdog/Event] {location_hint} 偵測到變更: {src_path.name}")
        try:
            if self.synchronizer.sync_to_workings(src_path):
                try:
                    rel_path = src_path.relative_to(self.project_path)
                    self.sync_ui_callback(rel_path)
                except ValueError:
                    pass
        except Exception as e:
            self.logger.error(f"[Watchdog/Event] 同步異常: {e}", exc_info=True)

    def on_modified(self, event):
        """檔案被修改時觸發。"""
        if not event.is_directory:
            self._handle_event(event.src_path)

    def on_created(self, event):
        """檔案被建立時觸發。"""
        if not event.is_directory:
            self._handle_event(event.src_path)

    def on_moved(self, event):
        """檔案被移動或重新命名時觸發。同步新位置的檔案。"""
        if event.is_directory:
            return
        
        try:
            dest_path = Path(event.dest_path).resolve()
            
            if dest_path.suffix.lower() != '.html':
                return
            
            try:
                if dest_path.is_relative_to(self.workings_path):
                    return
            except ValueError:
                pass
            
            self.logger.info(f"[Watchdog/Moved] 重新命名: {event.src_path} -> {event.dest_path}")
            
            old_path = Path(event.src_path).resolve()
            self.last_mtimes.pop(old_path, None)
            
            self._handle_event(event.dest_path)
            
        except Exception as e:
            self.logger.error(f"[Watchdog/Moved] 異常: {e}", exc_info=True)