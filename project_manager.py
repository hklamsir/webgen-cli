import logging
import sys
from pathlib import Path
from typing import List, Optional

# 假定 file_manager 存在且有 create_project
try:
    import file_manager
except ImportError:
    print("錯誤：project_manager.py 無法導入 file_manager。", file=sys.stderr)
    sys.exit(1)


class ProjectManager:
    """
    負責處理專案的生命週期，如建立、開啟、列出。
    """

    def __init__(self, config):
        self.config = config
        self.projects_root = Path(config.get("projects_root", "projects"))
        self.projects_root.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"ProjectManager 初始化，根目錄: {self.projects_root}")

    def list_projects(self) -> List[str]:
        """
        列出 'projects/' 目錄下的所有專案。
        """
        if not self.projects_root.exists():
            return []
        return sorted([d.name for d in self.projects_root.iterdir() if d.is_dir()])

    def create_project(self, project_name: str) -> Optional[Path]:
        """
        呼叫 file_manager 建立新專案目錄結構。
        返回新專案的路徑。
        """
        project_path_str = file_manager.create_project(project_name, self.config)
        if project_path_str:
            self.logger.info(f"專案 '{project_name}' 已建立於 {project_path_str}")
            return Path(project_path_str)
        self.logger.error(f"建立專案 '{project_name}' 失敗。")
        return None

    def open_project(self, project_name: str) -> Optional[Path]:
        """
        檢查專案是否存在並返回其路徑。
        """
        proj_path = self.projects_root / project_name
        if proj_path.is_dir():
            return proj_path
        self.logger.warning(f"嘗試開啟不存在的專案: {project_name}")
        return None

    def get_project_completions(self, text: str) -> List[str]:
        """
        (自動完成輔助) 獲取 'projects/' 目錄下的專案目錄名稱。
        """
        if not self.projects_root.exists():
            return []
        return [
            d.name
            for d in self.projects_root.iterdir()
            if d.is_dir() and d.name.startswith(text)
        ]
