import cmd
import logging
import os
import sys
import shlex
from pathlib import Path
from typing import List, Optional

import colorama
from colorama import Fore, Style

# 導入重構後的新模組
from config_log import core as system_core

# 確保 website_generator 目錄在 sys.path 中
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from commands.command_settings import CommandSettings

try:
    # 導入必要的輔助模組
    import file_manager
    
    # 導入核心服務
    from project_manager import ProjectManager
    from file_generator import FileGenerator
    from project_session import ProjectSession
    
    # (新) 導入所有命令 Mixins
    from commands.meta_commands import MetaCommands
    from commands.gen_commands import GenCommands
    from commands.project_commands import ProjectCommands
    from commands.file_commands import FileCommands
    from commands.deploy_commands import DeployCommands
    
except ImportError as e:
    print(f"錯誤：無法導入必要模組 ({e})。", file=sys.stderr)
    print("請確保所有 .py 檔案和 'commands' 資料夾位於同一目錄。")
    sys.exit(1)

# ----------------------------------------------------------------------------
# 主 Shell 類別 (Mixin 重構)
# ----------------------------------------------------------------------------

class WebsiteShell(MetaCommands, 
                   GenCommands, 
                   ProjectCommands, 
                   FileCommands, 
                   DeployCommands,
                   cmd.Cmd):
    """
    AI 網站生成器互動式 Shell。
    (此類別現在主要負責狀態初始化和輔助方法)
    """
    intro = f'{Fore.YELLOW}歡迎使用 AI 網站原型生成器。輸入 "help" 或 "?" 顯示命令。{Style.RESET_ALL}\n'
    prompt = '\n(website-gen) $ '

    def __init__(self, config):
        """
        Shell 初始化。
        """
        super().__init__()
        self.config = config
        self.logger = logging.getLogger(__name__)

        # 注入依賴
        self.project_manager = ProjectManager(config)
        self.file_generator = FileGenerator(config)
        
        # 狀態管理
        self.current_session: Optional[ProjectSession] = None

        self.logger.info("Shell 已初始化 (v4.0 - 命令模組化)。")

    # --- 輔助方法 (供 Mixin 命令使用) ---
    def _confirm(self, question: str) -> bool:
        """
        向使用者請求 y/n 確認。
        """
        prompt = f"{question} [y/n]: "
        while True:
            try:
                response = input(prompt).strip().lower()
                if response in ['y', 'yes']:
                    return True
                if response in ['n', 'no']:
                    return False
                print("請輸入 'y' (是) 或 'n' (否)。")
            except (KeyboardInterrupt, EOFError):
                print("\n操作取消。")
                return False

    def _get_user_input(self, prompt: str, default: str = "") -> str:
        """
        安全地獲取使用者輸入。
        """
        try:
            response = input(prompt).strip()
            return response if response else default
        except (KeyboardInterrupt, EOFError):
            print("\n操作取消。")
            return default

    def _get_project_structure(self) -> List[str]:
        """
        遞迴掃描專案目錄並返回檔案列表，供 AI 參考。
        """
        if not self.current_session: return []
        file_list = []
        ignore = {'.git', '.vscode', '__pycache__', '.DS_Store'}
        
        for path in self.current_session.path.rglob('*'):
            if path.is_file():
                if not any(part in ignore for part in path.parts):
                    rel_path = path.relative_to(self.current_session.path).as_posix()
                    if not rel_path.startswith('.'):
                         file_list.append(rel_path)
        return sorted(file_list)

    def _get_project_file_completions(self, text: str) -> List[str]:
        """
        (自動完成輔助) 獲取目前專案中的所有檔案路徑。
        """
        if not self.current_session: return []
        
        all_files = self._get_project_structure() # <-- (修正) 確保呼叫帶有底線的正確方法

        options = set(all_files)
        for f in all_files:
            parts = f.split('/')
            if len(parts) > 1: options.add(parts[0] + '/')
        return sorted([o for o in options if o.startswith(text)])

    def _parse_args_with_references(self, parts: List[str], command_name: str) -> tuple[str, str, List[str], str]:
        """
        解析 'edit' 和 'addpage' 的參數，分離出檔案、描述和 @ 參考。
        """
        if len(parts) < 2:
            return "", "", [], f"錯誤：參數不足。用法: {command_name} <file> \"<desc>\" [@ref ...]"
        if parts[1].startswith('@'):
             return "", "", [], f"錯誤：描述必須是第二個參數。"
        refs = []
        for ref in parts[2:]:
            if not ref.startswith('@'): return "", "", [], f"錯誤：參考必須以 @ 開頭: '{ref}'"
            refs.append(ref[1:])
        return parts[0], parts[1], refs, ""

    def _build_reference_context(self, reference_files: List[str]) -> str:
        """
        根據 @ 檔案列表，讀取檔案內容並組合成一個上下文 String。
        """
        if not self.current_session or not reference_files: return ""
        contexts = []
        print(f"  [!] 正在讀取 {len(reference_files)} 個參考檔案...")
        for ref in reference_files:
            # 移除前導 'workings/'（使用設定的 WORKINGS_DIR）如果存在
            ref_clean = ref.replace(f"{CommandSettings.WORKINGS_DIR}/", '', 1).lstrip('/')

            # 優先在 workings 目錄查找 (.html 檔案)
            target = self.current_session.path / CommandSettings.WORKINGS_DIR / ref_clean
            if not target.exists():
                # 降級查找：嘗試專案根目錄
                target = self.current_session.path / ref_clean
            
            if target.exists():
                try:
                    content = file_manager.read_file_safe(target)
                    rel_path = target.relative_to(self.current_session.path).as_posix()
                    contexts.append(f"--- 參考: {rel_path} ---\n{content}\n")
                    print(f"    - 已載入: {rel_path}")
                except Exception as e:
                    print(f"    - [錯誤] 無法讀取 {ref}: {e}")
                    contexts.append(f"--- 參考: {ref} (讀取失敗: {e}) ---\n")
            else:
                print(f"    - [警告] 找不到: {ref} (已檢查: {target})")
                contexts.append(f"--- 參考: {ref} (找不到) ---\n")
        return "\n".join(contexts)

    def _assemble_project(self):
        """
        (內部輔助) 重新組裝所有 HTML 檔案。
        """
        if not self.current_session: return False
        
        self.current_session.pause_watching()
        
        workings = self.current_session.path / CommandSettings.WORKINGS_DIR
        if not workings.exists():
            self.current_session.resume_watching()
            return False
        
        files = [f.name for f in workings.iterdir() if f.is_file()]
        header = next((f for f in files if f.endswith(('header.html'))), None)
        footer = next((f for f in files if f.endswith(('footer.html'))), None)
        pages = [f for f in files if f.endswith('.html') and f not in (header, footer)]

        success = False
        if header and footer and pages:
            file_manager.assemble_html_files(self.current_session.path, header, footer, pages)
            print(f"  [成功] 已組裝 {len(pages)} 個頁面。")
            success = True
        else:
            print("  [失敗] 缺少模板或頁面。")
            success = False

        self.current_session.resume_watching()
        return success

    # --- Watchdog 同步回調 (UI 層) ---
    def _notify_sync_success(self, relative_path: Path):
        """
        (回調函數) 由 ProjectSession -> FileWatcher -> HtmlSyncHandler 觸發，
        用於在 UI 顯示同步成功訊息。
        
        修正：避免破壞 Shell 提示符，使用非侵入式輸出。
        """
        # 保存當前行的狀態
        try:
            # 清除當前行
            sys.stdout.write('\r' + ' ' * 120 + '\r')
            sys.stdout.flush()
            
            # 輸出同步訊息
            print(f"{Fore.CYAN}[Watchdog] 已同步 {relative_path.as_posix()} -> {CommandSettings.WORKINGS_DIR}/{Style.RESET_ALL}")
            
            # 重新顯示提示符
            sys.stdout.write(self.prompt)
            sys.stdout.flush()
        except Exception as e:
            self.logger.debug(f"_notify_sync_success 輸出異常: {e}")

# ----------------------------------------------------------------------------
# 程式進入點
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    colorama.init()
    
    WELCOME_ART = f"""
{Fore.CYAN}
 _    _      _     _____              _____  _     _____ 
| |  | |    | |   |  __ \            /  __ \| |   |_   _|
| |  | | ___| |__ | |  \/ ___ _ __   | /  \/| |     | |  
| |/\| |/ _ \ '_ \| | __ / _ \ '_ \  | |    | |     | |  
\  /\  /  __/ |_) | |_\ \  __/ | | | | \__/\| |_____| |_ 
 \/  \/ \___|_.__/ \____/\___|_| |_|  \____/\_____/\___/  v.1.0

- Designed by Lamsir -
{Style.RESET_ALL}
"""
    print(WELCOME_ART)

    # 使用新系統初始化
    system_core.setup_logging()
    config = system_core.load_config()
    
    if not config:
        logging.critical("無法載入設定，程式退出。")
        sys.exit(1)

    shell = WebsiteShell(config)
    try:
        # 將 cmdloop 包在一個迴圈中，攔截 SystemExit（argparse 在 -h 或錯誤時會呼叫 sys.exit()）
        # 這樣可以避免單一命令的 help 或解析錯誤終止整個程式。
        while True:
            try:
                shell.cmdloop()
                break  # 正常退出 cmdloop（例如使用 quit/exit）則離開迴圈
            except SystemExit as se:
                # argparse 會透過 sys.exit() 觸發這個例外；攔截後回到 shell
                # print(f"\n[警告] argparse 嘗試退出 (code={se.code})，已攔截並返回 Shell。")
                # 繼續迴圈以重新啟動 cmdloop
                pass
            except KeyboardInterrupt:
                print("\n程式已中斷。")
                break
    except Exception as e:
        logging.critical(f"發生未預期錯誤: {e}", exc_info=True)
        print("發生嚴重錯誤，請檢查日誌。")
    finally:
        if shell.current_session:
            shell.current_session.stop_watching()
        sys.exit(0)
