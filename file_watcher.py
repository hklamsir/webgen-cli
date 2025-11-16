import logging
import sys
import threading
from pathlib import Path
from typing import List, Optional, Callable

import colorama
from watchdog.observers import Observer

try:
    # 導入新的 HtmlSynchronizer 和更新後的 HtmlSyncHandler
    from sync_handler import HtmlSyncHandler, HtmlSynchronizer
except ImportError as e:
    print(f"錯誤：file_watcher.py 無法導入 sync_handler: {e}", file=sys.stderr)
    sys.exit(1)

class FileWatcher:
    """
    封裝 Watchdog 監控、同步和事件處理邏輯。
    """
    # (無類別層級型別註解) 屬性在 __init__ 中以 None 初始化以保持兼容性
    def __init__(self, project_path: Path, logger: logging.Logger, sync_callback: Callable):
        self.project_path = project_path
        self.logger = logger
        self.sync_callback = sync_callback # 來自 Shell 的 UI 回調
        
        self.observer = None
        self.observer_thread = None
        self.event_handler = None
        self.synchronizer = None
        
        self.logger.info(f"FileWatcher 為 {project_path} 初始化。")

    def start(self):
        """
        啟動檔案系統監察器。預載所有 HTML 檔案的 mtime。
        """
        try:
            # 1. 建立同步邏輯處理器
            self.synchronizer = HtmlSynchronizer(self.project_path, self.logger)
            
            # 2. 建立事件處理器，傳入同步器和 UI 回調
            self.event_handler = HtmlSyncHandler(
                self.project_path, 
                self.synchronizer, 
                self.sync_callback # 傳遞回調
            )
            
            self.logger.info("[Watchdog] 正在預載 mtime 基準...")
            count = 0
            error_count = 0
            workings = self.project_path / 'workings'
            
            for p in self.project_path.rglob('*.html'):
                try:
                    if not p.is_file():
                        continue
                    if p.is_relative_to(workings):
                        continue
                    resolved_p = p.resolve()
                    mtime = p.stat().st_mtime
                    self.event_handler.last_mtimes[resolved_p] = mtime
                    count += 1
                except FileNotFoundError:
                    self.logger.debug(f"[Watchdog/Start] 檔案已刪除: {p.name}")
                    error_count += 1
                except PermissionError:
                    self.logger.warning(f"[Watchdog/Start] 無權限: {p.name}")
                    error_count += 1
                except Exception as e:
                    self.logger.warning(f"[Watchdog/Start] 異常: {e}")
                    error_count += 1

            self.observer = Observer()
            self.observer.schedule(self.event_handler, str(self.project_path), recursive=True)
            self.observer_thread = threading.Thread(target=self.observer.start, daemon=True)
            self.observer_thread.start()
            err_hint = f", {error_count} 個錯誤" if error_count > 0 else ""
            print(f"\r{colorama.Fore.CYAN}[!] 檔案監察器已啟動 (預載 {count} 個基準{err_hint})。{colorama.Style.RESET_ALL}")
            
        except Exception as e:
            self.logger.error(f"[Watchdog] 啟動監察器失敗: {e}", exc_info=True)
            print(f"\r{colorama.Fore.RED}錯誤：啟動監察器失敗。{colorama.Style.RESET_ALL}")

    def stop(self):
        """
        停止檔案系統監察器。
        """
        try:
            if self.observer:
                self.observer.stop()
                if self.observer_thread:
                    self.observer_thread.join(timeout=2)
            
            self.observer = None
            self.observer_thread = None
            self.event_handler = None
            self.synchronizer = None
            
            self.logger.info("[Watchdog] 監察器已停止。")
            print(f"\r{colorama.Fore.CYAN}[!] 檔案監察器已停止。{colorama.Style.RESET_ALL}")
        except Exception as e:
            self.logger.error(f"[Watchdog] 停止監察器時異常: {e}", exc_info=True)

    def pause(self):
        """暫停事件處理。"""
        if self.event_handler:
            self.event_handler.pause()

    def resume(self):
        """恢復事件處理。"""
        if self.event_handler:
            self.event_handler.resume()
            
