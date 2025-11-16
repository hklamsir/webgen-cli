"""
pytest 單元測試：CommandSettings 類別的 merge_ftp_config() 與副檔名驗證邏輯。
"""

import pytest
import sys
import os
from pathlib import Path

# 確保能匯入 commands 模組
sys.path.insert(0, str(Path(__file__).parent.parent))

from commands.command_settings import CommandSettings


class TestMergeFtpConfig:
    """merge_ftp_config() 的測試套件。"""

    def test_empty_config(self):
        """空 config dict 應回傳預設值。"""
        result = CommandSettings.merge_ftp_config({})
        assert result == CommandSettings.FTP_DEFAULTS
        assert result['host'] == 'ftpupload.net'
        assert result['port'] == 21
        assert result['use_tls'] is True

    def test_merge_with_ftp_config_key(self):
        """從 config['ftp_config'] 讀取並合併設定。"""
        config = {
            'ftp_config': {
                'host': 'example.com',
                'user': 'testuser',
                'password': 'testpass',
            }
        }
        result = CommandSettings.merge_ftp_config(config)
        assert result['host'] == 'example.com'
        assert result['user'] == 'testuser'
        assert result['password'] == 'testpass'
        # 未提供的應使用預設
        assert result['port'] == 21
        assert result['use_tls'] is True

    def test_merge_with_ftp_key(self):
        """支援舊的 config['ftp'] 鍵名。"""
        config = {
            'ftp': {
                'host': 'oldstyle.com',
                'port': 2121,
            }
        }
        result = CommandSettings.merge_ftp_config(config)
        assert result['host'] == 'oldstyle.com'
        assert result['port'] == 2121

    def test_ftp_config_takes_precedence(self):
        """同時存在時，ftp_config 優先於 ftp。"""
        config = {
            'ftp_config': {'host': 'priority.com'},
            'ftp': {'host': 'secondary.com'},
        }
        result = CommandSettings.merge_ftp_config(config)
        assert result['host'] == 'priority.com'

    def test_none_values_ignored(self):
        """None 值應被跳過，使用預設值。"""
        config = {
            'ftp_config': {
                'host': 'example.com',
                'user': None,
                'password': None,
            }
        }
        result = CommandSettings.merge_ftp_config(config)
        assert result['host'] == 'example.com'
        assert result['user'] is None  # 預設本身是 None
        assert result['password'] is None

    def test_remote_path_normalization_with_slash(self):
        """remote_path 已有 / 時，不應重複添加。"""
        config = {
            'ftp_config': {
                'remote_path': '/public_html/'
            }
        }
        result = CommandSettings.merge_ftp_config(config)
        assert result['remote_path'] == '/public_html/'

    def test_remote_path_normalization_without_slash(self):
        """remote_path 缺少 / 時，應自動添加。"""
        config = {
            'ftp_config': {
                'remote_path': '/public_html'
            }
        }
        result = CommandSettings.merge_ftp_config(config)
        assert result['remote_path'] == '/public_html/'

    def test_use_tls_override(self):
        """use_tls 設定應可被覆蓋。"""
        config = {
            'ftp_config': {
                'use_tls': False
            }
        }
        result = CommandSettings.merge_ftp_config(config)
        assert result['use_tls'] is False

    def test_invalid_config_returns_defaults(self):
        """無效的 config 類型應回傳預設值。"""
        result1 = CommandSettings.merge_ftp_config(None)
        result2 = CommandSettings.merge_ftp_config("not a dict")
        result3 = CommandSettings.merge_ftp_config([])
        
        assert result1 == CommandSettings.FTP_DEFAULTS
        assert result2 == CommandSettings.FTP_DEFAULTS
        assert result3 == CommandSettings.FTP_DEFAULTS

    def test_invalid_ftp_config_value(self):
        """若 ftp_config 值無效，應使用預設。"""
        config = {
            'ftp_config': "not a dict"
        }
        result = CommandSettings.merge_ftp_config(config)
        assert result == CommandSettings.FTP_DEFAULTS


class TestAllowedPageExtensions:
    """ALLOWED_PAGE_EXTENSIONS 副檔名驗證的測試。"""

    def test_allowed_extensions(self):
        """檢查所有允許的副檔名。"""
        expected = ('.html', '.php', '.css', '.js', '.md', '.txt')
        assert CommandSettings.ALLOWED_PAGE_EXTENSIONS == expected

    def test_extension_is_tuple(self):
        """ALLOWED_PAGE_EXTENSIONS 應為 tuple（不可變）。"""
        assert isinstance(CommandSettings.ALLOWED_PAGE_EXTENSIONS, tuple)

    def test_common_extensions_included(self):
        """驗證常見副檔名都被包含。"""
        common = ['.html', '.php', '.css', '.js']
        for ext in common:
            assert ext in CommandSettings.ALLOWED_PAGE_EXTENSIONS

    def test_extension_validation_helper(self):
        """測試副檔名檢驗的邏輯 (模擬實際使用)。"""
        test_cases = [
            ('index.html', True),
            ('style.css', True),
            ('script.js', True),
            ('api.php', True),
            ('readme.md', True),
            ('notes.txt', True),
            ('archive.zip', False),
            ('image.png', False),
            ('video.mp4', False),
            ('script.exe', False),
        ]
        
        for filename, should_pass in test_cases:
            ext = Path(filename).suffix.lower()
            is_allowed = ext in CommandSettings.ALLOWED_PAGE_EXTENSIONS
            assert is_allowed == should_pass, f"副檔名 {ext} 檢驗失敗"


class TestIgnoreList:
    """IGNORE_LIST 與 is_ignored() 的測試。"""

    def test_ignore_list_is_frozenset(self):
        """IGNORE_LIST 應為 frozenset（不可變）。"""
        assert isinstance(CommandSettings.IGNORE_LIST, frozenset)

    def test_ignore_list_contents(self):
        """檢查忽略清單包含的項目。"""
        expected_items = {'.git', '.vscode', '__pycache__', '.DS_Store', 'workings'}
        assert CommandSettings.IGNORE_LIST == expected_items

    def test_is_ignored_basename_matching(self):
        """is_ignored() 應根據基礎名稱比對。"""
        assert CommandSettings.is_ignored('workings') is True
        assert CommandSettings.is_ignored('.git') is True
        assert CommandSettings.is_ignored('__pycache__') is True
        
        assert CommandSettings.is_ignored('index.html') is False
        assert CommandSettings.is_ignored('myfile.txt') is False

    def test_is_ignored_with_paths(self):
        """is_ignored() 應只比對基礎名稱，忽略路徑前綴。"""
        assert CommandSettings.is_ignored('/home/user/workings') is True
        assert CommandSettings.is_ignored('projects/workings') is True
        assert CommandSettings.is_ignored('dir/.git') is True
        
        assert CommandSettings.is_ignored('projects/myfile.txt') is False


class TestWorkingsDir:
    """WORKINGS_DIR 常數的測試。"""

    def test_workings_dir_value(self):
        """WORKINGS_DIR 應為 'workings'。"""
        assert CommandSettings.WORKINGS_DIR == 'workings'

    def test_workings_dir_in_ignore_list(self):
        """WORKINGS_DIR 應包含在 IGNORE_LIST 中。"""
        assert CommandSettings.WORKINGS_DIR in CommandSettings.IGNORE_LIST


class TestFtpDefaults:
    """FTP_DEFAULTS 設定字典的測試。"""

    def test_ftp_defaults_keys(self):
        """FTP_DEFAULTS 應包含所有必要的鍵。"""
        required_keys = {'host', 'user', 'password', 'remote_path', 'port', 'use_tls'}
        assert set(CommandSettings.FTP_DEFAULTS.keys()) == required_keys

    def test_ftp_defaults_values(self):
        """檢查預設值的合理性。"""
        assert isinstance(CommandSettings.FTP_DEFAULTS['host'], str)
        assert isinstance(CommandSettings.FTP_DEFAULTS['port'], int)
        assert isinstance(CommandSettings.FTP_DEFAULTS['use_tls'], bool)
        assert CommandSettings.FTP_DEFAULTS['port'] == 21
        assert CommandSettings.FTP_DEFAULTS['use_tls'] is True


class TestIntegration:
    """整合測試：多個功能一起運作。"""

    def test_full_deployment_config_scenario(self):
        """模擬完整的部署配置場景。"""
        # 使用者的 config.json
        user_config = {
            'deepseek_api_key': 'sk-xxx',
            'ftp_config': {
                'host': 'myserver.com',
                'user': 'myuser',
                'password': 'mypass',
                'remote_path': '/website',
                'use_tls': False,
            }
        }
        
        # 合併後的 FTP 設定
        ftp_settings = CommandSettings.merge_ftp_config(user_config)
        
        assert ftp_settings['host'] == 'myserver.com'
        assert ftp_settings['user'] == 'myuser'
        assert ftp_settings['password'] == 'mypass'
        assert ftp_settings['remote_path'] == '/website/'  # 應被標準化
        assert ftp_settings['port'] == 21  # 預設值
        assert ftp_settings['use_tls'] is False

    def test_file_deployment_with_extensions(self):
        """測試檔案部署時的副檔名檢查。"""
        files_to_deploy = [
            'index.html',
            'style.css',
            'script.js',
            'api.php',
            'readme.md',
        ]
        
        # 檢查所有檔案副檔名是否允許
        allowed_count = 0
        for filename in files_to_deploy:
            ext = Path(filename).suffix.lower()
            if ext in CommandSettings.ALLOWED_PAGE_EXTENSIONS:
                allowed_count += 1
        
        assert allowed_count == len(files_to_deploy)

    def test_directory_traversal_with_ignore_list(self):
        """測試目錄遍歷時的忽略邏輯。"""
        # 模擬目錄結構中的目錄名稱
        dirs_to_check = [
            'css',
            'workings',  # 應被忽略
            '.git',  # 應被忽略
            '__pycache__',  # 應被忽略
            'js',
        ]
        
        valid_dirs = []
        for dirname in dirs_to_check:
            if not CommandSettings.is_ignored(dirname):
                valid_dirs.append(dirname)
        
        assert len(valid_dirs) == 2  # 只有 'css' 和 'js' 是有效的
        assert 'workings' not in valid_dirs
        assert '.git' not in valid_dirs
        assert '__pycache__' not in valid_dirs
        assert 'css' in valid_dirs
        assert 'js' in valid_dirs


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
