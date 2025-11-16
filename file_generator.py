import logging
import sys
import os
import re
import concurrent.futures
from pathlib import Path
from typing import List, Optional

import colorama
from colorama import Fore, Style
from tqdm import tqdm

try:
    import llm_client
    import file_manager
    from commands.command_settings import CommandSettings
except ImportError as e:
    print(f"錯誤：file_generator.py 無法導入模組: {e}", file=sys.stderr)
    sys.exit(1)

class FileGenerator:
    """
    負責所有與 AI 互動以生成或修改檔案內容的邏輯。
    """
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.logger.info("FileGenerator 已初始化。")

    @staticmethod
    def is_safe_path(project_path: Path, target_path: Path) -> bool:
        """檢查目標路徑是否在項目目錄內"""
        try:
            # 解析絕對路徑並檢查是否為項目目錄的子路徑
            return target_path.resolve().relative_to(project_path.resolve())
        except ValueError:
            return False  # 路徑越界
    
    @staticmethod
    def scan_php_safety(content: str) -> list[str]:
        """檢查PHP代碼中的危險模式"""
        dangers = []
        if re.search(r'\$_GET\s*\[\s*["\'].*["\']\s*\]', content) and not re.search(r'htmlspecialchars', content):
            dangers.append("未過濾的GET參數可能導致XSS")
        if re.search(r'SELECT.*\'.*\$_', content):  # 檢查字符串拼接SQL
            dangers.append("可能存在SQL注入風險，需使用預處理")
        if re.search(r'eval\s*\(', content):
            dangers.append("禁止使用eval()函數")
        return dangers

    def generate_initial_structure(self, description: str) -> List[str]:
        """
        步驟 1: 呼叫 LLM 生成檔案結構。
        """
        structure = llm_client.generate_structure(description, self.config)
        if not structure:
            self.logger.error("FileGenerator: generate_structure 返回空。")
            return []
        file_list = file_manager.parse_directory_structure(structure)
        # 使用集中定義的允許副檔名過濾
        allowed = tuple(CommandSettings.ALLOWED_PAGE_EXTENSIONS)
        file_list = [f for f in file_list if f.lower().endswith(allowed)]
        return file_list

    def _generate_and_write_file_worker(self, file_path_str: str, description: str, file_list: List[str], header_prompt: Optional[str], footer_prompt: Optional[str], project_path_str: str) -> tuple[str, str, str]:
        """
        (並行工作單元) 生成單一檔案內容。
        """
        try:
            # 1. 呼叫 LLM
            content_response = llm_client.generate_file_content(
                description, file_path_str, file_list, self.config, header_prompt, footer_prompt
            )
            
            # 2. 解析內容
            status = "success"
            if not content_response:
                file_content = ""
                status = "empty_response"
            else:
                file_content = file_manager.extract_and_clean_code(content_response, file_path_str)
                if not file_content:
                     file_content = ""
                     status = "extract_fail"

            # 3. 決定儲存路徑 (使用 pathlib)
            project_path = Path(project_path_str)
            if Path(file_path_str).suffix == '.html':
                target_path = project_path / CommandSettings.WORKINGS_DIR / file_path_str
            else:
                target_path = project_path / file_path_str

            # 4. 寫入檔案前先記錄日誌（使用tqdm兼容方式）
            #self.logger.info(f"即將寫入檔案： {target_path}")  # 提前記錄，避免與進度條衝突
            file_manager.write_file_safe(target_path, file_content)
            
            return file_path_str, status, str(target_path)

        except Exception as e:
            return file_path_str, "exception", str(e)

    def generate_project_files(self, project_path: Path, file_list: List[str], description: str, header_prompt: Optional[str], footer_prompt: Optional[str]) -> List[tuple[str, str]]:
        """
        步驟 2: 並行生成所有專案檔案。
        """
        max_workers = self.config.get("max_generation_workers", os.cpu_count() or 3)
        errors = []
        project_path_str = str(project_path)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self._generate_and_write_file_worker, f, description, file_list, header_prompt, footer_prompt, project_path_str): f for f in file_list}
            
            # (修正) 使用 with tqdm() as pbar，並呼叫 pbar.write() 來避免打斷進度條
            with tqdm(concurrent.futures.as_completed(futures), total=len(file_list), desc="生成進度", unit="file", ncols=80, colour='green') as pbar:
                for future in pbar:
                    fname, status, msg = future.result()
                    if status != "success":
                         errors.append((fname, msg))
                         pbar.write(f"{Fore.RED}[失敗] {fname}: {status}{Style.RESET_ALL}")
        
        print() # <-- (修正) 在進度條結束後補上一個換行
        return errors

    def add_new_page(self, project_path: Path, file_path: str, description: str, reference_context: str) -> bool:
        """
        處理 'addpage' 命令的 AI 生成邏輯，支持PHP文件。
        """
        # 檢查副檔名是否允許
        from commands.command_settings import CommandSettings
        ext = Path(file_path).suffix.lower()
        if ext and ext not in CommandSettings.ALLOWED_PAGE_EXTENSIONS:
            print(f"錯誤：不支援的檔案副檔名: {ext}")
            return False

        # 根據文件類型決定存儲路徑
        if file_path.endswith('.php'):
            target = project_path / file_path  # PHP直接放根目錄
        else:
            target = project_path / CommandSettings.WORKINGS_DIR / file_path  # HTML放workings目錄
        
        if not self.is_safe_path(project_path, target):
            print("錯誤：無效的文件路徑")
            return False
       
        # 調用LLM生成對應內容（需確保llm_client支持PHP生成）
        resp = llm_client.generate_addpage_content(description, file_path, self.config, reference_context)
        
        if resp:
            # 提取並清理代碼（PHP不需要移除HTML標籤）
            content = file_manager.extract_code_block(resp)
            # 特殊處理PHP代碼（如果有需要）
            if file_path.endswith('.php'):
                # 確保PHP開啟標籤存在
                if not content.strip().startswith('<?php'):
                    content = f'<?php\n\n{content}\n\n?>'
            issues = self.scan_php_safety(content)
            if issues:
                print("警告：PHP代碼存在安全風險：")
                for issue in issues:
                    print(f"- {issue}")
                if not self._confirm("是否繼續保存？"):
                    return False
        
            file_manager.write_file_safe(target, content)
            print(f"已建立 {file_path}")
            return True
        else:
            print("生成失敗。")
            return False

    def edit_existing_file(self, target_path: Path, file_path_str: str, original_content: str, description: str, reference_context: str, structure: Optional[List[str]], is_html_source: bool) -> bool:
        """
        處理 'edit' 命令的 AI 生成邏輯。
        """
        resp = llm_client.edit_file_content(file_path_str, original_content, description, self.config, structure, reference_context)
        
        if resp:
            if is_html_source:
                new_content = file_manager.extract_and_clean_code(resp, file_path_str)
            else:
                new_content = file_manager.extract_code_block(resp)
                
            if new_content:
                file_manager.write_file_safe(target_path, new_content)
                print("檔案已更新。")
                return True
            else:
                print("無法提取新內容。")
                return False
        else:
            print("AI 沒有回應。")
            return False
        
