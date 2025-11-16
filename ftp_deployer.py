import os
import time
import ftplib
import logging
import posixpath
import ssl
from typing import List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# 10 MB 檔案大小警告閾值 (bytes)
FILE_SIZE_WARNING_MB = 10 * 1024 * 1024

# FTP 超時與重試設定
FTP_TIMEOUT = 30
FTP_RETRIES = 3
FTP_RETRY_DELAY = 2  # 指數退避起始秒數


class FTPDeployer:
    """
    處理 FTP 連接、遞迴上傳和錯誤處理的類別。
    """
    def __init__(self, host: str, user: str, password: str, port: int = 21, timeout: int = FTP_TIMEOUT, use_tls: bool = False):
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.timeout = timeout
        self.use_tls = use_tls
        self.ftp: Optional[ftplib.FTP] = None
        logger.info(f"FTPDeployer 已為 {self.host} 初始化。 use_tls={self.use_tls}")

    def connect(self) -> bool:
        """
        連接到 FTP 伺服器並登入。
        """
        if self.ftp:
            self.disconnect()

        for attempt in range(FTP_RETRIES):
            try:
                # 支援 FTPS (FTP over TLS)
                if self.use_tls:
                    # 建立寬鬆的 SSL 上下文以相容舊伺服器
                    # 這允許較小的 DH 金鑰 (用於解決 "DH_KEY_TOO_SMALL" 錯誤)
                    context = ssl.create_default_context()
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                    # 允許較低的安全等級以與舊伺服器相容
                    context.set_ciphers('DEFAULT@SECLEVEL=1')
                    
                    self.ftp = ftplib.FTP_TLS(context=context)
                else:
                    self.ftp = ftplib.FTP()

                self.ftp.set_pasv(True)
                self.ftp.set_debuglevel(0)  # 正式環境關閉 debug
                logger.info(f"正在連接到 {self.host}:{self.port}... (嘗試 {attempt + 1})")
                self.ftp.connect(self.host, self.port, self.timeout)
                logger.info(f"正在使用使用者 {self.user} 登入...")
                self.ftp.login(self.user, self.password)

                # 若使用 FTPS，設定保護模式
                if self.use_tls and isinstance(self.ftp, ftplib.FTP_TLS):
                    try:
                        # 使用 prot_c() (僅保護控制連線，與舊伺服器更相容)
                        # 而非 prot_p() (保護資料連線，易引發協議衝突)
                        self.ftp.prot_c()
                        logger.info("已使用 FTPS (TLS) 進行安全控制連線。")
                    except Exception as e:
                        logger.warning(f"啟用 FTPS PROT 保護失敗: {e}")

                logger.info("FTP 連接成功。")
                self.ftp.encoding = "utf-8"
                return True
            except ftplib.error_perm as e:
                logger.error(f"FTP 權限錯誤：{e}")
                if attempt == FTP_RETRIES - 1:
                    raise Exception(f"FTP 登入失敗：{e}")
            except Exception as e:
                logger.error(f"FTP 連接失敗：{e}")
                if attempt < FTP_RETRIES - 1:
                    time.sleep(FTP_RETRY_DELAY * (2 ** attempt))
                else:
                    raise Exception(f"FTP 連接失敗：{e}")
        return False

    def disconnect(self):
        """關閉 FTP 連接。"""
        if self.ftp:
            try:
                self.ftp.quit()
                logger.info("FTP 連接已安全關閉。")
            except Exception as e:
                logger.warning(f"關閉 FTP 連接時出錯：{e}")
            finally:
                self.ftp = None

    def _ensure_remote_dir_exists(self, remote_dir: str):
        """
        確保遠端目錄存在，如果不存在則建立它。
        使用 posixpath 嚴格建構路徑，避免 // 或遺漏 /
        """
        if not self.ftp:
            raise Exception("FTP 未連接。")

        # 移除開頭的 '/' 並分割
        parts = [p for p in remote_dir.split('/') if p]
        if not parts:
            return  # 根目錄

        current_path = ""
        for i, part in enumerate(parts):
            # 嚴格建構：/dir1/dir2
            current_path = posixpath.join('/', *parts[:i+1])

            try:
                self.ftp.cwd(current_path)
            except ftplib.error_perm:
                # 目錄不存在，建立它
                try:
                    logger.debug(f"建立遠端目錄：{current_path}")
                    self.ftp.mkd(current_path)
                    self.ftp.cwd(current_path)
                except ftplib.error_perm as e:
                    raise Exception(f"無法建立目錄 {current_path}：{e}")

    def _upload_file(self, local_file: str, remote_file: str):
        """
        上傳單一檔案，包含大檔案警告與重試機制。
        """
        local_path = Path(local_file)
        if not local_path.exists():
            raise FileNotFoundError(f"本地檔案不存在：{local_file}")

        file_size = local_path.stat().st_size
        if file_size > FILE_SIZE_WARNING_MB:
            logger.warning(f"上傳大檔案：{local_file} ({file_size / (1024*1024):.1f} MB)")

        remote_dir = posixpath.dirname(remote_file)
        if remote_dir and remote_dir != '/':
            self._ensure_remote_dir_exists(remote_dir)

        # 重試機制
        for attempt in range(FTP_RETRIES):
            try:
                with open(local_file, 'rb') as f:
                    cmd = f"STOR {remote_file}"
                    self.ftp.storbinary(cmd, f)
                logger.info(f"上傳成功：{remote_file}")
                return
            except Exception as e:
                logger.warning(f"上傳失敗 {remote_file} (嘗試 {attempt + 1})：{e}")
                if attempt < FTP_RETRIES - 1:
                    time.sleep(FTP_RETRY_DELAY * (2 ** attempt))
                else:
                    raise Exception(f"上傳失敗 {remote_file}：{e}")

    def upload_directory(self, local_path: str, remote_path: str, ignore_list: List[str] = None):
        """
        遞迴上傳整個目錄，根據 basename 名稱忽略指定項目。
        ignore_list 可包含目錄/檔案名稱 (如 'workings', '.git')
        只要 basename 匹配就會忽略，無論層級深度。
        """
        if not self.ftp:
            self.connect()
        if not self.ftp:
            raise Exception("無法連接到 FTP。")

        local_root = Path(local_path).resolve()
        if not local_root.is_dir():
            raise NotADirectoryError(f"本地路徑不是目錄：{local_path}")

        # 將 ignore_list 轉換為 set，用於快速名稱查找
        ignore_names = set(ignore_list or [])
        total_files = 0

        print("正在掃描並上傳目錄...")
        for root, dirs, files in os.walk(local_root):
            root_path = Path(root)

            # 基於 basename 忽略目錄：只保留名稱不在 ignore_names 中的目錄
            dirs[:] = [d for d in dirs if d not in ignore_names]

            relative_dir_path = root_path.relative_to(local_root)
            
            # 跳過此目錄本身如果名稱在忽略清單中
            if relative_dir_path != Path(".") and relative_dir_path.name in ignore_names:
                continue

            # 計算遠端目錄
            if relative_dir_path == Path("."):
                current_remote_dir = remote_path
            else:
                current_remote_dir = posixpath.join(remote_path, relative_dir_path.as_posix())

            self._ensure_remote_dir_exists(current_remote_dir)

            for file in files:
                # 基於 basename 忽略檔案
                if file in ignore_names:
                    logger.debug(f"忽略檔案 (名稱比對)：{file}")
                    continue

                local_file = root_path / file
                remote_file = posixpath.join(current_remote_dir, file)
                self._upload_file(str(local_file), remote_file)
                total_files += 1

        logger.info(f"目錄上傳完成。總共上傳 {total_files} 個檔案。")
        print(f"\n[成功] 目錄上傳完成。總共上傳 {total_files} 個檔案。")

    def upload_files(self, local_base_path_str: str, local_files: List[str], remote_path: str):
        """
        上傳指定檔案列表，保持相對結構。
        """
        if not self.ftp:
            self.connect()
        if not self.ftp:
            raise Exception("無法連接到 FTP。")

        logger.info(f"開始上傳 {len(local_files)} 個指定檔案至 {remote_path}")
        total_files = 0
        local_base_path = Path(local_base_path_str).resolve()

        for local_file_abs_path in local_files:
            local_file = Path(local_file_abs_path).resolve()

            if not local_file.exists():
                logger.warning(f"檔案不存在，跳過：{local_file}")
                continue

            try:
                relative_path = local_file.relative_to(local_base_path).as_posix()
            except ValueError:
                logger.error(f"檔案不在專案內：{local_file}")
                continue

            remote_file = posixpath.join(remote_path, relative_path)
            remote_dir = posixpath.dirname(remote_file)

            self._ensure_remote_dir_exists(remote_dir)

            try:
                self._upload_file(str(local_file), remote_file)
                total_files += 1
            except Exception as e:
                logger.error(f"上傳失敗 {local_file.name}: {e}")
                print(f"  [錯誤] 上傳 {local_file.name} 失敗: {e}")

        logger.info(f"指定檔案上傳完成。總共上傳 {total_files} 個檔案。")
        print(f"\n[成功] 指定檔案上傳完成。總共上傳 {total_files} 個檔案。")