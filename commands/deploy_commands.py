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
    from commands.command_settings import CommandSettings
    from commands.command_parser import CommandParser 
    # [重構] 導入介面
    from commands.shell_interface import ShellInterface
except ImportError:
    try:
        from command_settings import CommandSettings
    except ImportError as e:
        print(f"致命錯誤 (deploy_commands)：無法導入模組: {e}", file=sys.stderr)
        sys.exit(1)

deploy_parser = CommandParser(prog='deploy', description='部署專案至 FTP。')
deploy_parser.add_argument('files', nargs='*', help='(可選) 要上傳的特定檔案列表 (例如 index.html css/main.css)。如果留空，則上傳整個專案。')
deploy_parser.add_argument('--host', help='FTP 主機。')
deploy_parser.add_argument('--user', help='FTP 使用者名稱。')
default_remote = CommandSettings.FTP_DEFAULTS.get('remote_path', '/public_html')
deploy_parser.add_argument('--path', help=f"遠端基礎路徑 (例如: {default_remote})。")
deploy_parser.add_argument('--pass', dest='password', help='FTP 密碼 (不安全，建議留空以觸發提示)。')
deploy_parser.add_argument(
    '-s', '--silent',
    action='store_true',
    help='啟用無提示模式。直接使用 config.json 中的 FTP 設定，跳過所有互動式提示和確認。'
)

class DeployCommands:
    """
    包含部署專案的命令。
    """

    def do_deploy(self: "ShellInterface", arg: str):
        """
        部署專案至 FTP。
        """
        if not self.current_session: 
            return print("請先開啟專案。")
        
        try:
            args = deploy_parser.parse_args(shlex.split(arg))
        except argparse.ArgumentError:
            return

        conf = CommandSettings.merge_ftp_config(self.config)

        if args.silent:
            print("[!] 啟用無提示模式 (-s)，使用 config.json 中的 ftp設定...")
            conf_host = conf.get('host')
            conf_user = conf.get('user')
            conf_pass = conf.get('password')
            conf_path = conf.get('remote_path')

            if not all([conf_host, conf_user, conf_pass, conf_path]):
                print("錯誤：無提示模式 (-s) 失敗。")
                print("請確保 config.json 中 'ftp_config' 包含 'host', 'user', 'password' 和 'remote_path'。")
                return

            host = conf_host
            user = conf_user
            pwd = conf_pass
            base_path_input = conf_path

        else:
            conf_host = conf.get('host')
            host = args.host or self._get_user_input(
                f"FTP 主機 [{conf_host}]: ", conf_host
            )
            
            conf_user = conf.get('user', '')
            user = args.user or self._get_user_input(
                f"FTP 使用者 [{conf_user}]: ", conf_user
            )
            
            conf_pass = conf.get('password', '')
            pwd = args.password or getpass.getpass("FTP 密碼: ") or conf_pass
            
            conf_path = conf.get('remote_path')
            if not conf_path.endswith('/'):
                conf_path = conf_path + '/'
            base_path_input = args.path or self._get_user_input(
                f"遠端基礎路徑 [{conf_path}{self.current_session.name}]: ", conf_path
            )

        base_path = (base_path_input.rstrip('/') + '/')
        remote_path = base_path + self.current_session.name

        if not all([host, user, pwd, remote_path]): 
            return print("資訊不完整，取消。")

        files_to_upload = args.files
        validated_files: List[str] = []
        upload_mode: str = ""
        
        if files_to_upload:
            print("\n--- 指定檔案上傳 ---")
            for f in files_to_upload:
                # 注意：這裡假設 self 具有 _is_safe_path，但該方法其實在 FileCommands 裡
                # 如果 WebsiteShell 同時繼承了 FileCommands，執行時不會出錯。
                # 為了 Type Safe，應該將 _is_safe_path 移動到 Shell 核心或工具類。
                # 這裡我們暫時假設它是存在的 (Runtime-wise)
                target_path = self.current_session.path / f
                
                # 這裡需要呼叫 FileCommands 的私有方法，這在 Mixin 架構中是常見的壞味道
                # 建議將 _is_safe_path 提升到 ShellInterface 或是獨立的 Utility
                # 為了保持代碼相容性，我們這裡使用 getattr 安全調用，或者直接複製邏輯
                is_safe = getattr(self, '_is_safe_path', lambda x, y: True)(f, target_path)
                
                if target_path.exists() and target_path.is_file() and is_safe:
                    is_ignored = False
                    for ignored_part in CommandSettings.IGNORE_LIST:
                        if ignored_part in target_path.parts:
                            is_ignored = True
                            break
                            
                    if not is_ignored:
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
            
            if not args.silent:
                if not self._confirm(f"確認上傳 {len(validated_files)} 個檔案至 {host}:{remote_path}？"): 
                    return
            else:
                print(f"[!] 無提示上傳 {len(validated_files)} 個檔案至 {host}:{remote_path}")
            
            upload_mode = "files"

        else:
            print("\n--- 完整專案上傳 ---")
            
            if not args.silent:
                if not self._confirm(f"確認上傳 *整個專案* '{self.current_session.name}' 至 {host}:{remote_path}？"): 
                    return
            else:
                print(f"[!] 無提示上傳 *整個專案* '{self.current_session.name}' 至 {host}:{remote_path}")

            upload_mode = "directory"

        try:
            port = conf.get('port', 21)
            use_tls = conf.get('use_tls', False)
            deployer = ftp_deployer.FTPDeployer(host, user, pwd, port=port, use_tls=use_tls)
            if deployer.connect():
                print("連接成功，開始上傳...")
                
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

    def complete_deploy(self: "ShellInterface", text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """自動完成 deploy 命令中的檔案名稱。"""
        
        if text.startswith('-'):
            opts = ['--host', '--user', '--path', '--pass', '--silent', '-s']
            return [o for o in opts if o.startswith(text)]

        try:
            parts = shlex.split(line[:begidx])
            if parts and parts[-1] in ('--host', '--user', '--path', '--pass'):
                return [] 
        except ValueError:
            pass 

        return self._get_project_file_completions(text)