import logging
import sys
from pathlib import Path
from typing import Callable, Optional

try:
    from file_watcher import FileWatcher
except ImportError as e:
    print(f"錯誤：project_session.py 無法導入 FileWatcher: {e}", file=sys.stderr)
    sys.exit(1)

class ProjectSession:
    """
    (新) 封裝一個活動專案的狀態，包括其名稱、路徑和檔案監控器。
    """
    def __init__(self, name: str, path: Path, logger: logging.Logger, sync_callback: Callable):
        self.name = name
        self.path = path
        self.logger = logger
        self.sync_callback = sync_callback
        self.file_watcher: Optional[FileWatcher] = None
        self.logger.info(f"專案會話 '{name}' 已建立。")

    def start_watching(self):
        """啟動此會話的檔案監控。"""
        if self.file_watcher:
            self.stop_watching()
        
        try:
            self.file_watcher = FileWatcher(
                self.path,
                self.logger,
                self.sync_callback
            )
            self.file_watcher.start()
        except Exception as e:
            self.logger.error(f"啟動監察器失敗: {e}")

    def stop_watching(self):
        """停止此會話的檔案監控。"""
        if self.file_watcher:
            self.file_watcher.stop()
            self.file_watcher = None
        self.logger.info(f"專案會話 '{self.name}' 已停止監控。")

    def pause_watching(self):
        """暫停監控 (例如在檔案操作期間)。"""
        if self.file_watcher:
            self.file_watcher.pause()

    def resume_watching(self):
        """恢復監控。"""
        if self.file_watcher:
            self.file_watcher.resume()
            