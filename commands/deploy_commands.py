import sys
import shlex
import argparse
import getpass 
from typing import TYPE_CHECKING, List
from pathlib import Path

# 確保 website_generator 目錄在 sys.path 中
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import ftp_deployer
    # (新) 導入集中化的設定
    from commands.command_settings import CommandSettings
    from commands.command_parser import CommandParser 
except ImportError:
    try:
        from command_settings import CommandSettings
    except ImportError as e:
        print(f"致命錯誤 (deploy_commands)：無法導入模組: {e}", file=sys.stderr)
        sys.exit(1)

# --- 類型檢查 ---
if TYPE_CHECKING:
    from shell import WebsiteShell
# -----------------

# --- (!! 更新 Argparse !!) ---
deploy_parser = CommandParser(prog='deploy', description='部署專案至 FTP。')
deploy_parser.add_argument('files', nargs='*', help='(可選) 要上傳的特定檔案列表 (例如 index.html css/main.css)。如果留空，則上傳整個專案。')
deploy_parser.add_argument('--host', help='FTP 主機。')
deploy_parser.add_argument('--user', help='FTP 使用者名稱。')
default_remote = CommandSettings.FTP_DEFAULTS.get('remote_path', '/public_html')
deploy_parser.add_argument('--path', help=f"遠端基礎路徑 (例如: {default_remote})。")
deploy_parser.add_argument('--pass', dest='password', help='FTP 密碼 (不安全，建議留空以觸發提示)。')
# (!! 新增 !!)
deploy_parser.add_argument(
    '-s', '--silent',
    action='store_true',
    help='啟用無提示模式。直接使用 config.json 中的 FTP 設定，跳過所有互動式提示和確認。'
)
# --------------------------

class DeployCommands:
    """
    包含部署專案的命令。
    """

    def do_deploy(self: "WebsiteShell", arg: str):
        """
        部署專案至 FTP。
        用法: deploy [file1 file2...] [-s] [--host <h>] [--user <u>] [--path <p>] [--pass <pwd>]
        (如果提供了檔案列表，只上傳那些檔案；否則，上傳整個專案。)
        (-s 啟用無提示模式，完全依賴 config.json)
        """
        if not self.current_session: 
            return print("請先開啟專案。")
        
        try:
            # (新) 使用 argparse 解析
            args = deploy_parser.parse_args(shlex.split(arg))
        except argparse.ArgumentError:
            return

        # 使用 CommandSettings.merge_ftp_config() 以合併預設與 config.json 的覆寫
        conf = CommandSettings.merge_ftp_config(self.config)

        # --- (!! 邏輯更新: 檢查 -s 模式 !!) ---
        if args.silent:
            # --- 模式 1: 無提示模式 ---
            print("[!] 啟用無提示模式 (-s)，使用 config.json 中的 ftp設定...")
            conf_host = conf.get('host')
            conf_user = conf.get('user')
            conf_pass = conf.get('password')
            conf_path = conf.get('remote_path')

            # 驗證 config.json 是否完整
            if not all([conf_host, conf_user, conf_pass, conf_path]):
                print("錯誤：無提示模式 (-s) 失敗。")
                print("請確保 config.json 中 'ftp_config' 包含 'host', 'user', 'password' 和 'remote_path'。")
                return

            host = conf_host
            user = conf_user
            pwd = conf_pass
            base_path_input = conf_path

        else:
            # --- 模式 2: 互動模式 (原始邏輯) ---
            
            # 1. 主機
            conf_host = conf.get('host')
            host = args.host or self._get_user_input(
                f"FTP 主機 [{conf_host}]: ", conf_host
            )
            
            # 2. 使用者
            conf_user = conf.get('user', '')
            user = args.user or self._get_user_input(
                f"FTP 使用者 [{conf_user}]: ", conf_user
            )
            
            # 3. 密碼 (新: 使用 getpass)
            conf_pass = conf.get('password', '')
            pwd = args.password or getpass.getpass("FTP 密碼: ") or conf_pass
            
            # 4. 路徑
            conf_path = conf.get('remote_path')
            if not conf_path.endswith('/'):
                conf_path = conf_path + '/'
            base_path_input = args.path or self._get_user_input(
                f"遠端基礎路徑 [{conf_path}{self.current_session.name}]: ", conf_path
            )
        # --- 結束模式檢查 ---

        # 確保基礎路徑以 / 結尾
        base_path = (base_path_input.rstrip('/') + '/')
        
        # (新) 組合最終路徑
        remote_path = base_path + self.current_session.name

        if not all([host, user, pwd, remote_path]): 
            # (此檢查主要用於互動模式，但保留無妨)
            return print("資訊不完整，取消。")

        # --- (!! 邏輯更新 !!) ---
        files_to_upload = args.files
        validated_files: List[str] = []
        upload_mode: str = ""
        
        if files_to_upload:
            # 模式 1: 上傳指定檔案
            print("\n--- 指定檔案上傳 ---")
            for f in files_to_upload:
                target_path = self.current_session.path / f
                
                # 安全性檢查
                if target_path.exists() and target_path.is_file() and self._is_safe_path(f, target_path):
                     # 檢查是否在 IGNORE_LIST 中 (例如 workings)
                    is_ignored = False
                    for ignored_part in CommandSettings.IGNORE_LIST:
                        if ignored_part in target_path.parts:
                            is_ignored = True
                            break
                            
                    if not is_ignored:
                        # 檢查副檔名是否允許
                        from pathlib import Path as _P
                        ext = _P(f).suffix.lower()
                        if ext not in CommandSettings.ALLOWED_PAGE_EXTENSIONS:
                            print(f"  - [跳過] {f} (不支援的副檔名: {ext})")
                        else:
                            validated_files.append(str(target_path.resolve()))
                            print(f"  - [準備] {f}")
                    else:
                        print(f"  - [忽略] {f} (在 IGNORE_LIST 中)")
                else:
                    print(f"  - [警告] 找不到或不安全: {f}")

            if not validated_files:
                return print("沒有找到任何有效的檔案可上傳。")
            
            # (!! 更新 !!) 僅在非 silent 模式下確認
            if not args.silent:
                if not self._confirm(f"確認上傳 {len(validated_files)} 個檔案至 {host}:{remote_path}？"): 
                    return
            else:
                print(f"[!] 無提示上傳 {len(validated_files)} 個檔案至 {host}:{remote_path}")
            
            upload_mode = "files"

        else:
            # 模式 2: 上傳整個目錄
            print("\n--- 完整專案上傳 ---")
            
            # (!! 更新 !!) 僅在非 silent 模式下確認
            if not args.silent:
                if not self._confirm(f"確認上傳 *整個專案* '{self.current_session.name}' 至 {host}:{remote_path}？"): 
                    return
            else:
                print(f"[!] 無提示上傳 *整個專案* '{self.current_session.name}' 至 {host}:{remote_path}")

            upload_mode = "directory"
        # --- 結束邏輯更新 ---

        try:
            # 傳遞 port（如果有）
            port = conf.get('port', 21)
            use_tls = conf.get('use_tls', False)
            deployer = ftp_deployer.FTPDeployer(host, user, pwd, port=port, use_tls=use_tls)
            if deployer.connect():
                print("連接成功，開始上傳...")
                
                # (新) 根據模式呼叫不同方法
                if upload_mode == "files":
                    deployer.upload_files(
                        str(self.current_session.path.resolve()), 
                        validated_files,                          
                        remote_path                               
                    )
                else:
                    ignore_list = list(CommandSettings.IGNORE_LIST)
                    deployer.upload_directory(
                        str(self.current_session.path.resolve()), 
                        remote_path, 
                        ignore_list=ignore_list
                    )
                
                print("部署完成！")
                deployer.disconnect()
            else:
                print("連接失敗。")
        except Exception as e:
            print(f"部署錯誤: {e}")

    # --- (!! 新增自動完成 !!) ---
    def complete_deploy(self: "WebsiteShell", text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """自動完成 deploy 命令中的檔案名稱。"""
        
        if text.startswith('-'):
            opts = ['--host', '--user', '--path', '--pass', '--silent', '-s'] # <-- (新)
            return [o for o in opts if o.startswith(text)]

        try:
            parts = shlex.split(line[:begidx])
            if parts and parts[-1] in ('--host', '--user', '--path', '--pass'):
                return [] 
        except ValueError:
            pass 

        return self._get_project_file_completions(text)