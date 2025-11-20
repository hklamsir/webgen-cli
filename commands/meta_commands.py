import sys
from typing import TYPE_CHECKING

try:
    from commands.command_settings import CommandSettings
    # [重構] 導入介面
    from commands.shell_interface import ShellInterface
except ImportError:
    try:
        from command_settings import CommandSettings
    except ImportError as e:
        print(f"致命錯誤：無法導入 CommandSettings: {e}", file=sys.stderr)
        sys.exit(1)

class MetaCommands:
    """
    包含 Shell 的元命令（如 help, exit）和預設行為。
    """

    def do_help(self: "ShellInterface", arg: str):
        """
        覆寫 help，若沒帶參數則依 HELP_ORDER 顯示命令；
        若帶參數則回退到父類別行為顯示單一命令說明。
        """
        if arg:
            # 這裡依賴 super() 在 MRO 中找到 cmd.Cmd
            # Protocol 本身不能被 super() 調用，但在 Runtime 時 self 是一個 WebsiteShell (繼承自 Cmd)
            # 所以這裡的 super() 是有效的
            return super().do_help(arg) 
        
        print("可用命令：\n")
        shown = set()
        
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

    def do_exit(self: "ShellInterface", arg: str):
        """退出 Shell。"""
        if self.current_session:
            self.current_session.stop_watching()
        print("再見！")
        return True

    def do_EOF(self: "ShellInterface", arg: str):
        """處理 EOF (Ctrl+D) 退出。"""
        print("")
        return self.do_exit(arg)

    def emptyline(self: "ShellInterface"):
        pass

    def default(self: "ShellInterface", line: str):
        print(f"未知命令： '{line}'。輸入 'help' 查看可用命令。")