import argparse
import sys

class CommandParser(argparse.ArgumentParser):
    """
    (新)
    自訂 ArgumentParser，在 cmd 模組中優雅地處理錯誤。
    它會打印錯誤和輔助說明，然後拋出異常，而不是退出程式。
    """
    def error(self, message):
        # 覆寫 error 方法以打印錯誤，而不是退出
        print(f"參數錯誤: {message}\n", file=sys.stderr)
        # 顯示該命令的輔助說明
        self.print_help(sys.stderr)
        # 拋出一個可被捕捉的異常，以終止 do_ 方法的執行
        raise argparse.ArgumentError(None, message)