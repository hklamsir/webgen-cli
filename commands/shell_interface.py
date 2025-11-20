from typing import Protocol, List, Optional, Dict, Any
import logging
from pathlib import Path

# 為了避免循環引用，使用 TYPE_CHECKING 導入類型
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from project_manager import ProjectManager
    from file_generator import FileGenerator
    from project_session import ProjectSession

class ShellInterface(Protocol):
    """
    定義 Shell 的介面合約。
    所有 Command Mixin 都應針對此介面編寫，而不是針對具體的 WebsiteShell 類別。
    """
    
    # --- 核心屬性 ---
    config: Dict[str, Any]
    logger: logging.Logger
    project_manager: 'ProjectManager'
    file_generator: 'FileGenerator'
    current_session: Optional['ProjectSession']
    prompt: str

    # --- 來自 cmd.Cmd 的方法 (部分) ---
    def do_help(self, arg: str) -> Optional[bool]: ...

    # --- Shell 提供的輔助方法 (Helpers) ---
    def _confirm(self, question: str) -> bool: ...
    
    def _get_user_input(self, prompt: str, default: str = "") -> str: ...
    
    def _get_project_structure(self) -> List[str]: ...
    
    def _get_project_file_completions(self, text: str) -> List[str]: ...
    
    def _build_reference_context(self, reference_files: List[str]) -> str: ...
    
    def _assemble_project(self) -> bool: ...
    
    def _notify_sync_success(self, relative_path: Path) -> None: ...