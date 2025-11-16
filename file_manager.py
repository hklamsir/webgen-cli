import os
import re
import json
import logging
from typing import List, Union
from pathlib import Path
from tqdm import tqdm
from commands.command_settings import CommandSettings

# 取得日誌記錄器
logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# 檔案與目錄操作 (使用 pathlib)
# ----------------------------------------------------------------------------

def create_project(project_name: str, config: dict) -> str:
    """
    在 'projects/' 目錄下建立一個新的專案資料夾。
    返回完整的專案路徑字串 (為了相容性)。
    """
    root_dir = Path(config.get("projects_root", "projects"))
    project_path = root_dir / project_name
    
    try:
        if not project_path.exists():
            project_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"專案資料夾已建立： {project_path}")
        else:
            logger.info(f"專案資料夾已存在： {project_path}")
        return str(project_path.resolve())
    except OSError as e:
        logger.error(f"建立專案資料夾 {project_path} 失敗： {e}")
        raise

def write_file_safe(file_path: Union[str, Path], content: str):
    """
    安全地將內容寫入檔案，自動建立不存在的目錄。
    接受 str 或 Path 物件。
    """
    target_path = Path(file_path).resolve()
    
    try:
        # 確保父目錄存在
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # 寫入檔案
        with target_path.open('w', encoding='utf-8') as f:
            f.write(content)
        
        # 關鍵修改：使用tqdm的寫入方法確保日誌輸出不擾亂進度條
        tqdm.write(f"成功寫入檔案： {target_path}")  # 替代 logger.info
        #logger.info(f"\n成功寫入檔案： {target_path}")  # 保留日誌記錄

    except IOError as e:
        tqdm.write(f"寫入檔案 {target_path} 失敗： {e}")
        logger.error(f"\n寫入檔案 {target_path} 失敗： {e}")
    except Exception as e:
        tqdm.write(f"寫入檔案 {target_path} 時發生未知錯誤： {e}")
        logger.error(f"\n寫入檔案 {target_path} 時發生未知錯誤： {e}")

# (舊的 create_directory_structure 已被 Path.mkdir(parents=True) 取代，可移除或保留為兼容層)

# ----------------------------------------------------------------------------
# LLM 回應解析
# ----------------------------------------------------------------------------

def parse_directory_structure(response: str) -> List[str]:
    """
    從 LLM 的回應中解析出 `json` 區塊，返回檔案路徑列表。
    """
    logger.info("開始解析 `json` 檔案列表結構...")
    # (此處的正則表達式邏輯無需更改，因為處理的是純文本內容)
    match = re.search(r"```\s*json(.*?)\n(.*?)\n```", response, re.DOTALL | re.IGNORECASE)
    
    json_text = ""
    if not match:
        stripped_response = response.strip()
        if stripped_response.startswith('[') and stripped_response.endswith(']'):
            json_text = stripped_response
        else:
            logger.error("解析失敗：未找到有效的 JSON 結構。")
            return []
    else:
        json_text = match.group(2).strip()

    try:
        file_list = json.loads(json_text)
        if not isinstance(file_list, list):
             return []
        
        valid_files = []
        for item in file_list:
            if isinstance(item, str):
                # 使用 Path 來標準化路徑分隔符，然後轉回字串供後續使用
                # 這能確保 'css\\style.css' 在 Linux 上被轉為 'css/style.css'
                normalized_path = Path(item).as_posix()
                valid_files.append(normalized_path)
        
        return valid_files

    except json.JSONDecodeError as e:
        logger.error(f"解析 JSON 結構失敗： {e}")
        return []

def extract_code_block(response: str) -> str:
    """從回應中提取第一個程式碼區塊。"""
    match = re.search(r"```[^\n]*\n([\s\S]*?)\n```", response, re.DOTALL)
    if match:
        return match.group(1).strip()
    return response.strip()

def extract_and_clean_code(response: str, file_path_str: str) -> str:
    """提取並清理程式碼，根據檔案類型移除多餘標籤。"""
    content = extract_code_block(response)
    if not content:
         return ""

    # 使用 Path 判斷副檔名更準確
    path_obj = Path(file_path_str)
    suffix = path_obj.suffix.lower()

    if suffix == '.js':
        content = re.sub(r"^\s*<script[^>]*>\s*|\s*</script>\s*$", "", content, flags=re.IGNORECASE)

    elif suffix == '.html' and not path_obj.name.startswith(('_', 'header', 'footer')):
        tags_to_remove = [
            r"<html[^>]*>", r"</html>",
            r"<head[^>]*>[\s\S]*?</head>",
            r"<body[^>]*>", r"</body>",
            r"<nav[^>]*>[\s\S]*?</nav>",
            r"<footer[^>]*>[\s\S]*?</footer>"
        ]
        for tag_pattern in tags_to_remove:
            content = re.sub(r"^\s*" + tag_pattern + r"\s*", "", content, flags=re.IGNORECASE | re.DOTALL)
            content = re.sub(r"\s*" + tag_pattern + r"\s*$", "", content, flags=re.IGNORECASE | re.DOTALL)
            
    return content.strip()

# ----------------------------------------------------------------------------
# 檔案組裝與合併 (使用 pathlib)
# ----------------------------------------------------------------------------

def read_file_safe(file_path: Union[str, Path]) -> str:
    """安全地讀取檔案內容。"""
    path_obj = Path(file_path)
    if not path_obj.exists():
        logger.warning(f"讀取失敗：找不到檔案 {path_obj}")
        return ""
    try:
        # Path.read_text 是一個便捷方法
        return path_obj.read_text(encoding='utf-8')
    except IOError as e:
        logger.error(f"讀取檔案 {path_obj} 失敗：{e}")
        return ""

def assemble_html_files(project_path: Union[str, Path], header_file: str, footer_file: str, page_files: List[str]):
    """
    從 'workings/' 讀取模板和內容，組裝後寫入專案根目錄。
    """
    logger.info("開始組裝 HTML 檔案...")
    
    proj_dir = Path(project_path)
    workings_dir = proj_dir / CommandSettings.WORKINGS_DIR
    
    header_content = read_file_safe(workings_dir / header_file)
    footer_content = read_file_safe(workings_dir / footer_file)
    
    if not header_content or not footer_content:
        logger.error("缺少 Header 或 Footer 模板，終止組裝。")
        return

    for page_file in page_files:
        page_content = read_file_safe(workings_dir / page_file)
        if page_content:
            final_html = f"{header_content}\n{page_content}\n{footer_content}"
            write_file_safe(proj_dir / page_file, final_html)
        else:
             logger.warning(f"  - 跳過組裝：{page_file} (內容為空)")

    logger.info("組裝完成。")

def merge_files(input_paths: List[str], output_path: str):
    """合併多個檔案。"""
    merged_content = []
    for path_str in input_paths:
        path = Path(path_str)
        if not path.exists():
             raise FileNotFoundError(f"找不到檔案：{path}")
        merged_content.append(path.read_text(encoding='utf-8'))
    
    out_path_obj = Path(output_path)
    # 確保輸出目錄存在
    out_path_obj.parent.mkdir(parents=True, exist_ok=True)
    out_path_obj.write_text("\n\n".join(merged_content), encoding='utf-8')
    logger.info(f"成功合併檔案至：{out_path_obj}")
    