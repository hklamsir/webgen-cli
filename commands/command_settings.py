"""
集中存放所有命令模組共享的常數和設定。
"""
from typing import Dict, Any


class CommandSettings:
    """集中管理 commands 模組共用的常數與小型輔助邏輯。

    原則：常數應保持不可變（使用 tuple / frozenset），並盡可能提供
    小型 helper 以便從外部 config dict 合併覆寫。
    """

    # --- 檔案系統 ---
    WORKINGS_DIR = 'workings'

    # 在 dir 和 deploy 命令中使用的忽略目錄和檔案（不可變集合）
    IGNORE_LIST = frozenset({
        '.git',
        '.vscode',
        '__pycache__',
        '.DS_Store',
        WORKINGS_DIR,
    })

    # 支援的頁面/資源副檔名（以 tuple 儲存以利序列化/比較）
    ALLOWED_PAGE_EXTENSIONS = ('.html', '.php', '.css', '.js', '.md', '.txt')

    # --- 部署 (FTP) 預設設定 ---
    FTP_DEFAULTS: Dict[str, Any] = {
        'host': "ftpupload.net",
        'user': None,
        'password': None,
        'remote_path': "/htdocs/",
        'port': 21,
        'use_tls': True,
    }

    # --- Shell (Meta) ---
    # help 命令的顯示順序
    HELP_ORDER = [
        "gen",
        "generate",
        "addpage",
        "edit",
        "list",
        "open",
        "close",
        "dir",
        "rename",
        "delete",
        "merge",
        "updatehtml",
        "deploy",
        "exit",
        "EOF",
        "help",
    ]

    # --- Helper functions ---
    @staticmethod
    def merge_ftp_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """從外部 config dict 合併 ftp 設定，回傳完整的 ftp 設定 dict。

        範例：config 可以是讀自 `config.json` 的 dict，包含 `ftp_config`。
        未提供的欄位會使用 `FTP_DEFAULTS`。
        """
        defaults = CommandSettings.FTP_DEFAULTS.copy()
        if not isinstance(config, dict):
            return defaults
        ftp = config.get('ftp_config') or config.get('ftp') or {}
        if not isinstance(ftp, dict):
            return defaults
        # 只覆寫有值的欄位
        for k, v in ftp.items():
            if v is not None:
                defaults[k] = v
        # 確保 remote_path 以 / 結尾
        if 'remote_path' in defaults and isinstance(defaults['remote_path'], str):
            if not defaults['remote_path'].endswith('/'):
                defaults['remote_path'] = defaults['remote_path'] + '/'
        return defaults

    @staticmethod
    def is_ignored(path_name: str) -> bool:
        """檢查檔案或資料夾名稱是否在忽略清單中（只比對基礎名稱）。"""
        import os

        base = os.path.basename(path_name)
        return base in CommandSettings.IGNORE_LIST