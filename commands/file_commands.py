import shlex  # <--- 1. 修正：導入 shlex
import sys
import argparse
import time
from pathlib import Path
from typing import TYPE_CHECKING, List

# 確保 website_generator 目錄在 sys.path 中
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import file_manager
    # (新) 導入集中化的設定
    from commands.command_settings import CommandSettings
    from commands.command_parser import CommandParser # <-- (新) 導入共用解析器
except ImportError:
    try:
        from command_settings import CommandSettings
    except ImportError as e:
        print(f"致命錯誤 (file_commands)：無法導入模組: {e}", file=sys.stderr)
        sys.exit(1)

# --- 類型檢查 ---
if TYPE_CHECKING:
    from shell import WebsiteShell
# -----------------

# --- (新) Argparse 定義 ---
# (新) 移除本地定義
# class CommandParser(argparse.ArgumentParser):
#     """自訂 ArgumentParser，在 cmd 模組中優雅地處理錯誤。"""
#     def error(self, message):
#         print(f"參數錯誤: {message}\n", file=sys.stderr)
#         self.print_help(sys.stderr)
#         raise argparse.ArgumentError(None, message)

rename_parser = CommandParser(prog='rename', description='重新命名檔案或目錄。')
rename_parser.add_argument('old_name', help='舊檔案/目錄名稱。')
rename_parser.add_argument('new_name', help='新檔案/目錄名稱。')

delete_parser = CommandParser(prog='delete', description='刪除檔案。')
delete_parser.add_argument('file', help='要刪除的檔案路徑。')

merge_parser = CommandParser(prog='merge', description='合併多個檔案至一個檔案。')
merge_parser.add_argument('files', nargs='+', help='檔案列表。最後一個是輸出檔案。 (<in1> [in2...] <out>)')

# --------------------------

class FileCommands:
    """
    包含在專案中操作檔案的命令（dir, rename, delete, merge）。
    """

    # --- (新) 安全性輔助函數 ---
    def _is_safe_path(self: "WebsiteShell", user_input: str, target_path: Path) -> bool:
        """(安全) 檢查目標路徑是否安全且在專案目錄內。"""
        if not self.current_session:
            return False
        
        try:
            project_path = self.current_session.path
            
            # 關鍵：先拼接再 resolve，確保所有相對/絕對/symlink/.. 都被標準化
            proj_abs = project_path.resolve()
            target_abs = (project_path / user_input).resolve()  # <-- 先拼接再 resolve
            # target_abs = target_path.resolve()  # <-- 舊寫法：直接 resolve 外部傳入的 Path，可能已污染
            
            # 檢查是否為子路徑
            target_abs.relative_to(proj_abs)
            
            # 額外保護：不允許操作專案根目錄本身
            if proj_abs == target_abs:
                print(f"安全錯誤：拒絕操作專案根目錄。")
                return False
                
            return True
        except ValueError:
            print(f"安全錯誤：操作路徑 '{user_input}' 已超出專案邊界。")
            return False
        except Exception as e:
            self.logger.warning(f"_is_safe_path 檢查時出錯: {e}")
            return False

    def do_dir(self: "WebsiteShell", arg: str):
        """
        列出專案目錄結構。
        """
        if not self.current_session: 
            return print("請先開啟專案。")
        
        print(f"專案 '{self.current_session.name}' 結構：")
        
        # (新) 使用 CommandSettings.IGNORE_LIST
        ignore = CommandSettings.IGNORE_LIST
        
        def print_tree(dir_path: Path, prefix: str = ""):
            try:
                items = list(dir_path.iterdir())
            except PermissionError: 
                print(f"{prefix}└── [權限不足]")
                return
            
            items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))
            items = [i for i in items if i.name not in ignore]
            
            for i, item in enumerate(items):
                is_last = i == len(items) - 1
                connector = "└── " if is_last else "├── "
                print(f"{prefix}{connector}{item.name}{'/' if item.is_dir() else ''}")
                if item.is_dir():
                    print_tree(item, prefix + ("    " if is_last else "│   "))

        print_tree(self.current_session.path)

    # --- 3. 修正：修復 do_rename 損壞的定義並添加安全檢查 ---
    def do_rename(self: "WebsiteShell", arg: str):
        """
        重新命名檔案: rename <old_name> <new_name>
        """
        if not self.current_session:
            print("錯誤：無開啟的專案。")
            return

        try:
            args = rename_parser.parse_args(shlex.split(arg))
        except argparse.ArgumentError:
            return

        old_name, new_name = args.old_name, args.new_name

        # --- (新) 安全性檢查 ---
        # 檢查兩個路徑是否都在邊界內
        if not self._is_safe_path(old_name, self.current_session.path / old_name) or \
           not self._is_safe_path(new_name, self.current_session.path / new_name):
            return
        # --- 結束安全檢查 ---

        # --- 檔名副檔名警示（如果 new_name 副檔名不在允許清單，提示使用者） ---
        new_ext = Path(new_name).suffix.lower()
        if new_ext and new_ext not in CommandSettings.ALLOWED_PAGE_EXTENSIONS:
            print(f"警告：新的檔名副檔名 {new_ext} 可能不受支援。允許的副檔名：{', '.join(CommandSettings.ALLOWED_PAGE_EXTENSIONS)}")
            if not self._confirm("是否確定要進行重新命名？"):
                return

        self.current_session.pause_watching()
        try:
            old_root = self.current_session.path / old_name
            old_workings = self.current_session.path / CommandSettings.WORKINGS_DIR / old_name
            
            new_root = self.current_session.path / new_name
            new_workings = self.current_session.path / CommandSettings.WORKINGS_DIR / new_name

            renamed = False
            
            if old_root.exists():
                # 安全性：在 rename 之前再次檢查
                if not self._is_safe_path(old_name, old_root): return
                old_root.rename(new_root)
                print(f"已重新命名: {old_name} -> {new_name}")
                renamed = True

            if old_workings.exists():
                # 安全性：在 rename 之前再次檢查
                if not self._is_safe_path(f"{CommandSettings.WORKINGS_DIR}/{old_name}", old_workings): return
                old_workings.rename(new_workings)
                print(f"已重新命名: {CommandSettings.WORKINGS_DIR}/{old_name} -> {CommandSettings.WORKINGS_DIR}/{new_name}")
                renamed = True

            if not renamed:
                print(f"錯誤：找不到檔案 '{old_name}'")
                return

            print("建議執行 'updatehtml'。")

        finally:
            self.current_session.resume_watching()
            time.sleep(0.5)  # 給 Watchdog 足夠時間更新狀態

    def do_delete(self: "WebsiteShell", arg: str):
        """
        刪除檔案: delete <file>
        """
        if not self.current_session: 
            return print("請先開啟專案。")
        
        try:
            # (新) 使用 argparse 解析
            args = delete_parser.parse_args(shlex.split(arg))
        except argparse.ArgumentError:
            return
        
        target = args.file.strip()

        # --- 2. 移除局部的 is_safe_to_delete 函數 ---
        
        p_root = self.current_session.path / target
        p_work = self.current_session.path / CommandSettings.WORKINGS_DIR / target
        
        found = []

        # --- 2. (續) 在添加前使用 self._is_safe_path 檢查路徑 ---
        if p_root.exists() and p_root.is_file():
            if self._is_safe_path(target, p_root):
                found.append(p_root)

        if p_work.exists() and p_work.is_file():
            if self._is_safe_path(f"{CommandSettings.WORKINGS_DIR}/{target}", p_work):
                found.append(p_work)
        
        if not found: 
            return print(f"找不到可安全刪除的檔案: {target}")
        
        print("即將刪除:", ", ".join([str(p.relative_to(self.current_session.path)) for p in found]))
        if not self._confirm("確認刪除？"): 
            return

        self.current_session.pause_watching()
        for p in found:
            p.unlink()
            print(f"已刪除: {p.name}")
        self.current_session.resume_watching()
            
        if target.endswith(('.html', '.htm')):
             print("建議執行 'updatehtml'。")

    def do_merge(self: "WebsiteShell", arg: str):
        """
        合併檔案: merge <in1> <in2> ... <out>
        """
        if not self.current_session: 
            return print("請先開啟專案。")
        
        try:
            # (新) 使用 argparse 解析
            args = merge_parser.parse_args(shlex.split(arg))
            
            if len(args.files) < 2:
                # 雖然 argparse 的 nargs='+' 已確保至少有 1 個，但我們需要至少 2 個
                merge_parser.error("至少需要兩個檔案 (一個輸入和一個輸出)。")
            
            inputs = [str(self.current_session.path / f) for f in args.files[:-1]]
            output = str(self.current_session.path / args.files[-1])

            # 檢查副檔名是否允許（警告用）
            disallowed = []
            from pathlib import Path as _P
            for p in inputs + [output]:
                ext = _P(p).suffix.lower()
                if ext and ext not in CommandSettings.ALLOWED_PAGE_EXTENSIONS:
                    disallowed.append((p, ext))

            if disallowed:
                print("警告：下列檔案副檔名可能不受支援：")
                for p, ext in disallowed:
                    print(f"  - {p} (副檔名: {ext})")
                if not self._confirm("是否仍要繼續合併這些檔案？"):
                    return

            if _P(output).exists():
                if not self._confirm(f"輸出檔案 '{args.files[-1]}' 已存在，是否覆蓋？"):
                    return
            else:
                if not self._confirm("確認合併檔案？"): 
                    return
            file_manager.merge_files(inputs, output)
            print(f"已合併 {len(inputs)} 個檔案至 {args.files[-1]}")
        
        except argparse.ArgumentError:
            return # 解析器已打印錯誤
        except Exception as e:
            print(f"合併失敗: {e}")

    def do_updatehtml(self: "WebsiteShell", arg: str):
        """手動重新組裝 HTML。"""
        if not self.current_session: 
            return print("請先開啟專案。")
        print("正在重新組裝...")
        self._assemble_project()

    # --- 自動完成 ---

    def complete_rename(self: "WebsiteShell", text: str, line: str, begidx: int, endidx: int) -> List[str]:
        return self._get_project_file_completions(text)

    def complete_delete(self: "WebsiteShell", text: str, line: str, begidx: int, endidx: int) -> List[str]:
        return self._get_project_file_completions(text)

    def complete_merge(self: "WebsiteShell", text: str, line: str, begidx: int, endidx: int) -> List[str]:
        return self._get_project_file_completions(text)