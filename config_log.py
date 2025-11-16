import json
import logging
import os
import sys
import re
import mmap
from pathlib import Path
from colorama import Fore, Style

# 定義常數
DEFAULT_CONFIG_FILE = Path('config.json')
DEFAULT_LOG_DIR = Path('logs')

class ColoredFormatter(logging.Formatter):
    """
    自訂 Formatter，依 log level 輸出不同顏色。
    - ERROR: 紅色
    - WARNING: 黃色
    - INFO: 綠色
    - DEBUG: 灰色
    - CRITICAL: 亮紅
    """
    LEVEL_COLORS = {
        logging.DEBUG: Fore.LIGHTBLACK_EX,      # 灰色
        logging.INFO: Fore.GREEN,               # 綠色
        logging.WARNING: Fore.YELLOW,           # 黃色
        logging.ERROR: Fore.RED,                # 紅色
        logging.CRITICAL: Fore.RED + Style.BRIGHT,  # 亮紅
    }

    def format(self, record):
        color = self.LEVEL_COLORS.get(record.levelno, Fore.WHITE)
        message = super().format(record)
        return f"{color}{message}{Style.RESET_ALL}"


class CoreSystem:
    """
    核心系統類別，負責初始化日誌、載入設定檔等基礎設施。
    """
    def __init__(self, config_file: Path = DEFAULT_CONFIG_FILE, log_dir: Path = DEFAULT_LOG_DIR):
        self.config_file = Path(config_file)
        self.log_dir = Path(log_dir)
        self.log_file = None
        self.config = {}
        self.logger = logging.getLogger(__name__)

    def _count_lines_fast(self, path: Path, max_lines: int = 1000) -> int:
        """
        使用 mmap 高效計算檔案行數。
        若 mmap 失敗，回退到傳統方法。
        僅需掃描到 max_lines 行即可提前返回。
        """
        if not path.exists() or path.stat().st_size == 0:
            return 0

        try:
            with path.open('rb') as f:
                mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
                count = 0
                for i, byte in enumerate(mm):
                    if byte == ord('\n'):
                        count += 1
                        if count >= max_lines:
                            mm.close()
                            return count
                mm.close()
                return count + 1  # 最後一行無 \n
        except (ValueError, OSError, PermissionError) as e:
            # mmap 失敗，回退傳統方式
            self.logger.debug(f"mmap 失敗，回退傳統行數計算: {e}")
            try:
                with path.open('r', encoding='utf-8', errors='ignore') as f:
                    for i, _ in enumerate(f):
                        if i >= max_lines:
                            return max_lines
                    return i + 1
            except Exception:
                return 0

    def _find_latest_log(self) -> Path:
        """在 LOG_DIR 中查找最新的日誌檔案。若目錄不存在或為空則建立新檔案。"""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        log_files = []
        for f in self.log_dir.glob('agent_*.log'):
            if f.is_file():
                try:
                    mtime = f.stat().st_mtime
                    log_files.append((f, mtime))
                except Exception:
                    continue
        
        if log_files:
            newest_log = max(log_files, key=lambda x: x[1])[0]
            return newest_log
        
        default_log = self.log_dir / 'agent_00.log'
        default_log.touch(exist_ok=True)
        return default_log

    def _rotate_log_if_needed(self, path: Path, max_lines: int = 1000) -> Path:
        """
        若 path 行數 >= max_lines，建立下一個編號的檔案並回傳新路徑。
        使用高效行數計算。
        """
        if not path.exists():
            return path

        line_count = self._count_lines_fast(path, max_lines)
        if line_count < max_lines:
            return path

        # 解析檔名 (例如 agent_00.log)
        match = re.match(r'^(?P<prefix>.*?)(?P<num>\d+)(?P<ext>\.log)$', path.name)
        if not match:
            idx = 1
            while True:
                candidate = path.with_suffix(f"{path.suffix}.{idx}")
                if not candidate.exists():
                    candidate.touch()
                    return candidate
                idx += 1

        prefix = match.group('prefix')
        num = int(match.group('num'))
        ext = match.group('ext')

        while True:
            num += 1
            new_name = f"{prefix}{num:02d}{ext}"
            new_path = path.parent / new_name
            if not new_path.exists():
                new_path.touch()
                return new_path

    def setup_logging(self):
        """設定全域日誌記錄。"""
        self.log_file = self._find_latest_log()

        # 嘗試旋轉日誌
        try:
            self.log_file = self._rotate_log_if_needed(self.log_file, max_lines=1000)
        except Exception as e:
            print(f"警告：嘗試旋轉日誌檔時發生錯誤：{e}", file=sys.stderr)

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # 清除現有的 handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # 檔案 Handler (純文字，無顏色)
        log_format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        file_formatter = logging.Formatter(log_format_str)
        file_handler = logging.FileHandler(str(self.log_file), encoding='utf-8')
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        # 控制台 Handler (彩色輸出)
        stream_formatter = ColoredFormatter(log_format_str)
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(stream_formatter)
        root_logger.addHandler(stream_handler)

        # 第三方庫降噪
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("watchdog").setLevel(logging.WARNING)
        
        self.logger.info(f"日誌系統已啟動，記錄於: {self.log_file}")

    def load_config(self) -> dict:
        """載入並驗證設定檔。"""
        if not self.config_file.exists():
            print(f"錯誤：找不到 {self.config_file}。請確保設定檔存在。", file=sys.stderr)
            return {}
        try:
            with self.config_file.open('r', encoding='utf-8') as f:
                self.config = json.load(f)
                
            if "deepseek_api_key" not in self.config or not self.config["deepseek_api_key"]:
                print("警告：'deepseek_api_key' 未在設定中設定或為空。", file=sys.stdout)
            
            self.config.setdefault("chat_model", "deepseek-chat")
            self.config.setdefault("projects_root", "projects")
            
            return self.config
        except json.JSONDecodeError as e:
            print(f"錯誤：{self.config_file} JSON 格式錯誤：{e}", file=sys.stderr)
            return {}
        except Exception as e:
            print(f"載入 {self.config_file} 時發生錯誤：{e}", file=sys.stderr)
            return {}


# 建立一個全域實例供其他模組使用
core = CoreSystem()