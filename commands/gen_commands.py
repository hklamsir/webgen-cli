import shlex
import sys
import argparse
from pathlib import Path
from typing import TYPE_CHECKING, Optional, List
import time
import threading
import webbrowser

# 確保 website_generator 目錄在 sys.path 中
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import llm_client
    from commands.command_parser import CommandParser
    from commands.command_settings import CommandSettings
    # [重構] 導入介面
    from commands.shell_interface import ShellInterface
except ImportError as e:
    print(f"錯誤 (gen_commands)：無法導入 llm_client: {e}", file=sys.stderr)
    sys.exit(1)

gen_parser = CommandParser(prog='gen', description='根據自然語言描述，透過互動式流程生成一個新網站。')
gen_parser.add_argument(
    '--description', '--desc', 
    help='網站的主要描述 (可以是 "純文字" 或 "檔案路徑.txt")', 
    required=True
)
gen_parser.add_argument(
    '--header', 
    help='(可選) 頁首描述 (可以是 "純文字" 或 "檔案路徑.txt")'
)
gen_parser.add_argument(
    '--footer', 
    help='(可選) 頁尾描述 (可以是 "純文字" 或 "檔案路徑.txt")'
)

addpage_parser = CommandParser(prog='addpage', description='新增一個頁面至目前專案。')
addpage_parser.add_argument('file', help='新頁面的檔名 (例如: contact.html 或 api.php)。')
addpage_parser.add_argument('description', help='關於此頁面內容的描述。')
addpage_parser.add_argument('references', nargs='*', help='(可選) 供 AI 參考的檔案 (例如: @index.html @css/main.css)。')

edit_parser = CommandParser(prog='edit', description='使用 AI 編輯一個現有檔案。')
edit_parser.add_argument('file', help='要編輯的檔案路徑 (例如: index.html 或 js/script.js)。')
edit_parser.add_argument('description', help='您的修改要求 (例如: "將標題改為紅色")。')
edit_parser.add_argument('references', nargs='*', help='(可選) 供 AI 參考的檔案 (例如: @index.html)。')

# --------------------------

class GenCommands:
    """
    包含所有與 AI 生成相關的命令（gen, addpage, edit）。
    """

    def _show_loading_animation(self: "ShellInterface") -> tuple:
        """
        顯示載入動畫。
        """
        stop_event = threading.Event()
        
        def animate():
            while not stop_event.is_set():
                print(".", end="", flush=True)
                time.sleep(2)
        
        thread = threading.Thread(target=animate, daemon=True)
        thread.start()
        return thread, stop_event

    def _load_content_from_arg(self: "ShellInterface", arg_value: Optional[str]) -> Optional[str]:
        """
        檢查參數是否為檔案路徑。如果是，則讀取內容；否則，作為純文字返回。
        """
        if arg_value is None:
            return None
        path = Path(arg_value)
        if path.is_file() and path.exists():
            try:
                content = path.read_text(encoding='utf-8')
                print(f"  [提示] 已從檔案 '{arg_value}' 載入內容 (共 {len(content)} 字元)。")
                return content
            except Exception as e:
                print(f"  [警告] 無法讀取檔案 '{arg_value}': {e}。將其作為純文字處理。")
                return arg_value
        else:
            return arg_value

    def do_gen(self: "ShellInterface", arg: str):
        """根據自然語言描述，透過互動式流程生成一個新網站。
        用法: gen --desc <描述或檔案> [--header <描述或檔案>] [--footer <描述或檔案>]
        """
        try:
            args = gen_parser.parse_args(shlex.split(arg))
        except (argparse.ArgumentError, SystemExit):
            return

        if not self.config.get("deepseek_api_key"): 
            return print("錯誤：未設定 API Key。")

        print("\n步驟 0/4: 載入描述內容...")
        original_description = self._load_content_from_arg(args.description)
        header_prompt = self._load_content_from_arg(args.header)
        footer_prompt = self._load_content_from_arg(args.footer)

        if not original_description:
            return print("錯誤：主要描述內容為空。")
        
        if header_prompt is None:
            print("\n--- 頁首設定 ---")
            header_prompt = self._get_user_input("? 請輸入頁首 (header) 描述 (留空則使用 AI 預設): ")
            if not header_prompt:
                header_prompt = "包含網站Logo及標題，nav中的項目前加入圖示。"
        
        if footer_prompt is None:
            print("\n--- 頁尾設定 ---")
            footer_prompt = self._get_user_input("? 請輸入頁尾 (footer) 描述 (留空則使用 AI 預設): ")
            if not footer_prompt:
                footer_prompt = "包含版權聲明「 2025 林SIR設計，版權所有。」，背景色彩為漸變色）。"
        
        print("\n--- 需求確認 ---")
        def trunc(s: str, l: int = 100) -> str:
            if not s: return "N/A"
            s = s.replace('\n', ' ').replace('\r', '')
            return (s[:l] + '...') if len(s) > l else s

        print(f"  主要描述: {trunc(original_description)}")
        if args.description and Path(args.description).is_file():
             print(f"           (來源: {args.description})")

        print(f"  頁首 (H): {trunc(header_prompt)}")
        if args.header and Path(args.header).is_file():
             print(f"           (來源: {args.header})")
             
        print(f"  頁尾 (F): {trunc(footer_prompt)}")
        if args.footer and Path(args.footer).is_file():
             print(f"           (來源: {args.footer})")
        print("--------------------")
        
        if not self._confirm("是否確認使用以上內容執行?"):
            print("操作已取消。")
            return
        
        reconstructed_cmd = f'gen --desc "{args.description}"'
        if args.header:
            reconstructed_cmd += f' --header "{args.header}"'
        if args.footer:
            reconstructed_cmd += f' --footer "{args.footer}"'
        self.logger.info(f"使用者確認的命令: {reconstructed_cmd}")

        print("\n步驟 1/4: 呼叫 AI 優化您的需求描述... (這可能需要 5-10 秒)")
        if self._confirm("是否開始 AI 優化您的需求描述?"):
            self.logger.info("使用者確認進行提示優化。")
            try:
                optimized_description = llm_client.optimize_prompt(
                    original_description, 
                    header_prompt, 
                    footer_prompt, 
                    self.config
                )
                if not optimized_description:
                    raise Exception("AI 未能返回優化後的提示。")
                description = optimized_description
            except Exception as e:
                print(f"提示優化失敗： {e}")
                print("將改用您的原始描述繼續執行...")
                description = original_description
            
            print("\n--- AI 優化後的主要描述 ---")
            print(f'"{description}"')
            print("---------------------------------")
            
            print(f"(將使用此優化描述，以及您提供的頁首/頁尾) '{args.header or '預設'}' / '{args.footer or '預設'}'")
            print("------------------------------")
            
            if not self._confirm("是否使用此優化後的描述來生成網站 (頁首/頁尾保留不變)?"):
                print("操作已取消。")
                return
            self.logger.info(f"已確認使用優化後的 {description}，保留原始 header/footer 提示。")
        else:
            description = original_description

        print("\n步驟 2/4: 生成檔案結構...")
        file_list = self.file_generator.generate_initial_structure(description)
        if not file_list: 
            print("錯誤：無法從 AI 獲取檔案結構。請檢查日誌 logs/agent.log。")
            return
        
        print("AI 建議的檔案列表：")
        for f in file_list:
            print(f"  - {f}")
        
        project_name = self._get_user_input("請輸入新專案的名稱 (例如: 'my_site'): ").strip()
        if not project_name:
            print("操作取消。")
            return
        
        project_path = self.project_manager.create_project(project_name)
        if not project_path:
            print(f"錯誤：建立專案資料夾 {project_name} 失敗。")
            return
        
        # 這裡我們需要確保 self 具有 do_open
        # ShellInterface 中已經包含了 do_help 等基本命令，但 do_open 是 ProjectCommands 的一部分
        # 在這裡我們依賴 ShellInterface 的動態性，或者在 Interface 中加入 do_open
        # 為簡單起見，我們直接呼叫，因為我們知道執行時它會存在
        # 更好的做法是在 ShellInterface 加入所有 mixin 的 public methods
        getattr(self, 'do_open')(project_name) 
        if not self.current_session:
            print(f"錯誤：建立專案後無法開啟 {project_name}。")
            return

        print(f"\n步驟 3/4: 並行生成 {len(file_list)} 個檔案...")
        self.current_session.stop_watching()
        
        errors = self.file_generator.generate_project_files(
            project_path, file_list, description, header_prompt, footer_prompt
        )

        print("\n步驟 4/4: 組裝 HTML...")
        self._assemble_project()
        
        print(f"\n步驟 4/4: 完成！專案位於 {project_path}")
        self.current_session.start_watching()
        if errors: 
            print(f"注意：有 {len(errors)} 個檔案生成失敗。")

        try:
            candidates = [
                project_path / "index.html",
                project_path / CommandSettings.WORKINGS_DIR / "index.html"
            ]
            for p in candidates:
                if p.exists():
                    url = p.resolve().as_uri()
                    print(f"打開預覽: {url}")
                    webbrowser.open_new_tab(url)
                    break
            else:
                print("未找到 index.html，無法打開預覽。")
        except Exception as e:
            print(f"嘗試開啟瀏覽器預覽時發生錯誤: {e}")

    def do_generate(self: "ShellInterface", arg: str):
        """'gen' 命令的別名。
        用法: generate --desc <描述或檔案> [--header <描述或檔案>] [--footer <描述或檔案>]
        """
        self.do_gen(arg)

    def do_addpage(self: "ShellInterface", arg: str):
        """
        新增頁面: addpage <file.html|file.php> "<描述>" [@ref ...]
        """
        if not self.current_session: 
            return print("請先開啟專案。")
        
        try:
            args = addpage_parser.parse_args(shlex.split(arg))
            refs = []
            for r in args.references:
                if not r.startswith('@'):
                    addpage_parser.error(f"參考檔案必須以 '@' 開頭: '{r}'")
                refs.append(r[1:])
            
        except (argparse.ArgumentError, SystemExit):
            return

        fpath = args.file
        desc = args.description

        ext = Path(fpath).suffix.lower()
        if ext not in CommandSettings.ALLOWED_PAGE_EXTENSIONS:
            return print(f"錯誤：不支援的檔案副檔名: {ext}。允許的副檔名：{', '.join(CommandSettings.ALLOWED_PAGE_EXTENSIONS)}")
        
        if fpath.endswith('.php'):
            target = self.current_session.path / fpath
        else:
            target = self.current_session.path / CommandSettings.WORKINGS_DIR / fpath

        if target.exists() and not self._confirm(f"{fpath} 已存在，覆蓋？"): 
            return

        if not self._confirm("確認新增頁面？"): 
            return
        
        ref_ctx = self._build_reference_context(refs)
        
        print("呼叫 AI 生成中...", flush=True)
        loading_thread, stop_event = self._show_loading_animation()
        
        try:
            success = self.file_generator.add_new_page(
                self.current_session.path, fpath, desc, ref_ctx
            )
        finally:
            stop_event.set()
            loading_thread.join(timeout=1)
            print()
        
        if success and fpath.endswith('.html'):
            print("正在重新組裝...")
            self._assemble_project()

    def do_edit(self: "ShellInterface", arg: str):
        """
        編輯檔案: edit <file> "<描述>" [@ref ...]
        """
        if not self.current_session: 
            return print("請先開啟專案。")
        
        try:
            args = edit_parser.parse_args(shlex.split(arg))
            refs = []
            for r in args.references:
                if not r.startswith('@'):
                    edit_parser.error(f"參考檔案必須以 '@' 開頭: '{r}'")
                refs.append(r[1:])
            
        except (argparse.ArgumentError, SystemExit):
            return
        
        f_arg = args.file
        desc = args.description

        f_path_str = f_arg.replace(f"{CommandSettings.WORKINGS_DIR}/", '')
        full_path = self.current_session.path / f_path_str
        workings_path = self.current_session.path / CommandSettings.WORKINGS_DIR / f_path_str
        
        target_path = None
        is_html_source = False
        
        if f_path_str.endswith(('.html', '.htm')) and workings_path.exists():
            target_path = workings_path
            is_html_source = True
        elif full_path.exists():
            target_path = full_path
        else:
            return print(f"找不到檔案: {f_arg}")

        rel_path = target_path.relative_to(self.current_session.path)
        print(f"編輯目標: {rel_path}\n描述: {desc}")
        if not self._confirm("確認編輯？"): 
            return

        original = target_path.read_text(encoding='utf-8')
        ref_ctx = self._build_reference_context(refs)
        
        struct: Optional[List[str]] = None
        if target_path.name in ['header.html', 'footer.html', '_header.html', '_footer.html']:
             struct = self._get_project_structure()

        print("呼叫 AI 修改中...", flush=True)
        loading_thread, stop_event = self._show_loading_animation()
        
        try:
            success = self.file_generator.edit_existing_file(
                target_path, f_path_str, original, desc, ref_ctx, struct, is_html_source
            )
        finally:
            stop_event.set()
            loading_thread.join(timeout=1)
            print()
        
        if success and is_html_source:
            print("偵測到來源變更，重新組裝...")
            self._assemble_project()

    # --- 自動完成 ---
    def complete_addpage(self: "ShellInterface", text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """自動完成 addpage 命令。"""
        is_ref = False
        if text.startswith('@'):
            is_ref = True
        elif begidx > 0 and line[begidx - 1] == '@' and (begidx == 1 or line[begidx - 2].isspace()):
            is_ref = True

        if is_ref:
            prefix = text.lstrip('@')
            completions = self._get_project_file_completions(prefix)
            
            if text.startswith('@'):
                return ['@' + c for c in completions]
            else:
                return completions
        
        return self._get_project_file_completions(text)

    def complete_edit(self: "ShellInterface", text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """自動完成 edit 命令。"""
        is_ref = False
        if text.startswith('@'):
            is_ref = True
        elif begidx > 0 and line[begidx - 1] == '@' and (begidx == 1 or line[begidx - 2].isspace()):
            is_ref = True

        if is_ref:
            prefix = text.lstrip('@')
            completions = self._get_project_file_completions(prefix)
            
            if text.startswith('@'):
                return ['@' + c for c in completions]
            else:
                return completions
        
        return self._get_project_file_completions(text)