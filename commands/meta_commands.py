import sys
from typing import TYPE_CHECKING

# (新) 導入集中化的設定
try:
    from commands.command_settings import CommandSettings
except ImportError:
    # 處理可能的路徑問題 (如果從 shell.py 運行)
    try:
        from command_settings import CommandSettings
    except ImportError as e:
        print(f"致命錯誤：無法導入 CommandSettings: {e}", file=sys.stderr)
        sys.exit(1)


# --- 類型檢查 ---
if TYPE_CHECKING:
    from shell import WebsiteShell
# -----------------

class MetaCommands:
    """
    包含 Shell 的元命令（如 help, exit）和預設行為。
    (argparse 在此處並非必要)
    """

    def do_help(self: "WebsiteShell", arg: str):
        """
        覆寫 help，若沒帶參數則依 HELP_ORDER 顯示命令；
        若帶參數則回退到父類別行為顯示單一命令說明。
        """
        if arg:
            # (修正) 使用現代的 super() 呼叫，
            # 它將在 MRO 中正確找到 cmd.Cmd.do_help
            return super().do_help(arg) 
        
        print("可用命令：\n")
        shown = set()
        
        # (新) 使用 CommandSettings.HELP_ORDER
        for name in CommandSettings.HELP_ORDER:
            method_name = "do_" + name
            method = getattr(self, method_name, None)
            if not method:
                continue
            
            doc = (method.__doc__ or "").strip().splitlines()
            brief = doc[0] if doc else ""
            print(f"  {name:<12} {brief}")
            shown.add(name)
        
        others = []
        for attr in dir(self):
            if attr.startswith("do_"):
                cmdname = attr[3:]
                if cmdname not in shown:
                    others.append(cmdname)
                    
        if others:
            print("\n其他命令：")
            for name in sorted(others):
                method = getattr(self, "do_" + name)
                doc = (method.__doc__ or "").strip().splitlines()
                brief = doc[0] if doc else ""
                print(f"  {name:<12} {brief}")

    def do_exit(self: "WebsiteShell", arg: str):
        """退出 Shell。"""
        if self.current_session:
            self.current_session.stop_watching()
        print("再見！")
        return True

    def do_EOF(self: "WebsiteShell", arg: str):
        """處理 EOF (Ctrl+D) 退出。"""
        print("") # 換行
        return self.do_exit(arg)

    def emptyline(self: "WebsiteShell"):
        """
        使用者輸入空行時不執行任何操作。
        """
        pass

    def default(self: "WebsiteShell", line: str):
        """
        處理未知命令。
        """
        print(f"未知命令： '{line}'。輸入 'help' 查看可用命令。")