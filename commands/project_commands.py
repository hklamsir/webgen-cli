import sys
import shlex
import argparse
from typing import TYPE_CHECKING, List

# 確保 website_generator 目錄在 sys.path 中
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from project_session import ProjectSession
    from commands.command_parser import CommandParser # <-- (新) 導入共用解析器
except ImportError as e:
    print(f"錯誤 (project_commands)：無法導入 ProjectSession: {e}", file=sys.stderr)
    sys.exit(1)

# --- 類型檢查 ---
if TYPE_CHECKING:
    from shell import WebsiteShell
# -----------------

# --- (新) Argparse 定義 ---

# 建立解析器時禁用 exit_on_error=True (Python 3.9+) 或
# 捕捉 SystemExit (適用於所有版本)
# (新) 移除本地定義
# class CommandParser(argparse.ArgumentParser):
#     """自訂 ArgumentParser，在 cmd 模組中優雅地處理錯誤。"""
#     def error(self, message):
#         # 覆寫 error 方法以打印錯誤，而不是退出
#         print(f"參數錯誤: {message}\n", file=sys.stderr)
#         # 顯示該命令的輔助說明
#         self.print_help(sys.stderr)
#         # 拋出一個可被捕捉的異常，以終止 do_ 方法的執行
#         raise argparse.ArgumentError(None, message)

open_parser = CommandParser(prog='open', description='開啟一個現有的專案。')
open_parser.add_argument('name', help='要開啟的專案名稱。')

# --------------------------

class ProjectCommands:
    """
    包含與專案生命週期相關的命令（list, open, close）。
    """

    def do_list(self: "WebsiteShell", arg: str):
        """
        列出 'projects/' 目錄下的所有專案。
        """
        projects = self.project_manager.list_projects()
        
        if not projects:
            print(f"找不到任何專案 (在 '{self.project_manager.projects_root}' 中)。")
            return
        
        print(f"可用的專案 ({len(projects)}):")
        for proj in projects:
            print(f"  - {proj}")

    def do_open(self: "WebsiteShell", arg: str):
        """
        開啟專案: open <name>
        """
        try:
            # (新) 使用 argparse 解析
            args = open_parser.parse_args(shlex.split(arg))
        except argparse.ArgumentError:
            return # 解析器已打印錯誤
        
        # 如果已開啟，先關閉
        if self.current_session: 
            self.do_close("")
        
        proj_path = self.project_manager.open_project(args.name)
        
        if proj_path:
            # 建立新的會話
            self.current_session = ProjectSession(
                name=args.name,
                path=proj_path,
                logger=self.logger,
                sync_callback=self._notify_sync_success # 傳遞 UI 回調
            )
            self.current_session.start_watching()
            
            self.prompt = f"\n({args.name}) $ "
            print(f"已開啟專案: {args.name}")
        else:
            print(f"找不到專案 '{args.name}'。")

    def do_close(self: "WebsiteShell", arg: str):
        """
        關閉目前開啟的專案。
        """
        if not self.current_session: 
            return print("目前沒有開啟任何專案。")
        
        print(f"正在關閉專案: {self.current_session.name}")
        self.current_session.stop_watching()
        self.current_session = None
        
        self.prompt = '\n(website-gen) $ '
        print("專案已關閉。")

    # --- 自動完成 ---

    def complete_open(self: "WebsiteShell", text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """自動完成 open 命令。"""
        return self.project_manager.get_project_completions(text)