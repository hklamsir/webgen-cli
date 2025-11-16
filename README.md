# WebGen CLI

一個以 LLM（DeepSeek）為後端的互動式 Python 工具，能夠根據自然語言描述快速生成多頁網站原型（HTML、CSS、JS, PHP），並支援本地預覽、FTP 部署與檔案同步。

## 主要特色 ##
- 使用 `python shell.py` 啟動互動式 CLI（命令集合放於 `commands/`）。
- 自動產生專案結構、頁面片段（存放於 `projects/<name>/workings/`）並組裝成最終 HTML（寫入 `projects/<name>/`）。
- 嚴格的 prompt 與 DOM 合約（`GLOBAL_DOM_CONTRACT`）來保證 header/footer 與全域腳本一致性。
- 內建 PHP 安全掃描（`scan_php_safety`）與寫入前的路徑檢查（`is_safe_path`）。

## 專案結構（概要） ##
```
webgen_cli/
│
├── shell.py                # (!! 程式進入點 !!)
├── config.json             # API 金鑰和 FTP 等等設定
│
├── config_log.py           # 核心：設定與日誌
├── llm_client.py           # 核心：管理所有 LLM 提示 (Prompts) 和 API 呼叫
├── file_manager.py         # 核心：檔案 I/O、解析和組裝
├── file_generator.py       # 核心：協調 llm_client 和 file_manager
├── ftp_deployer.py         # 核心：處理 FTP 上傳邏輯
│
├── project_manager.py      # 狀態：管理專案 (list, open, create)
├── project_session.py      # 狀態：管理活動專案 (包含 FileWatcher)
├── file_watcher.py         # 狀態：啟動/停止 Watchdog 監控
├── sync_handler.py         # 狀態：Watchdog 事件處理 (HTML -> workings/)
│
├── commands/               # (所有 Shell 命令模組)
│   ├── command_parser.py   # (共用) 自訂 Argparse 解析器
│   ├── command_settings.py # (共用) 集中化常數 (FTP, 忽略列表等)
│   ├── meta_commands.py    # (命令) help, exit, EOF
│   ├── project_commands.py # (命令) list, open, close
│   ├── gen_commands.py     # (命令) gen, addpage, edit
│   ├── file_commands.py    # (命令) dir, rename, delete, merge, updatehtml
│   └── deploy_commands.py  # (命令) deploy
│
├── projects/               # (!! 所有生成的網站專案存放於此 !!)
│   └── (範例專案)/
│       ├── _header.html    # (主要) 頁首模板 (完整 HTML 頭部)
│       ├── _footer.html    # (主要) 頁尾模板 (包含 JS 引用)
│       ├── index.html      # (主要) 最終組裝好的頁面
│       ├── contact.html    # (主要) 最終組裝好的頁面
│       ├── css/
│       │   └── main.css
│       ├── js/
│       │   └── script.js
│       └── workings/       # (!! AI 生成的原始檔 !!)
│           ├── _header.html
│           ├── _footer.html
│           ├── index.html  # (AI 只會生成 <main>...</main> 內容)
│           └── contact.html
│
└── logs/                   # (日誌)
    └── agent_00.log
    └── agent_01.log
```

## 專案架構（完整說明） ##
- **根程式與服務**:
  - `shell.py`：互動式 CLI（基於 Python `cmd`），負責命令注入、使用者互動與 session 管理。
  - `project_manager.py`、`project_session.py`：管理專案建立、開啟、關閉與當前工作目錄狀態。
- **LLM 與生成相關**:
  - `llm_client.py`：所有 prompt 模板、`GLOBAL_DOM_CONTRACT` 以及 DeepSeek API 呼叫封裝。
  - `file_generator.py`：負責生成流程（呼叫 `llm_client`）、並行任務、結果安全檢查（例如 `scan_php_safety`、`is_safe_path`）與寫入 `workings/`。
- **檔案處理與組裝**:
  - `file_manager.py`：安全的檔案讀寫、解析 LLM 回應、與把 `workings/_header.html` + 各頁 `<main>` + `workings/_footer.html` 組裝為最終 HTML（`assemble_html_files()`）。
  - `file_watcher.py` / `sync_handler.py`：可選的即時同步機制（基於 Watchdog），將本地變更同步回 `workings/` 或觸發重組裝。
- **命令模組**:
  - `commands/`：包含多個 mixin 命令模組（`gen_commands.py`, `project_commands.py`, `file_commands.py`, `deploy_commands.py` 等），各命令以 `do_<cmd>` 與 `complete_<cmd>` 實作。
- **部署與工具**:
  - `ftp_deployer.py`：處理 FTP 上傳流程與設定讀取（支援互動與無提示模式）。
  - `logs/`：日誌輸出，包含 LLM 輸出與錯誤記錄（例如 `agent.log`）。

**重要目錄約定**
- `projects/<project_name>/workings/`：LLM 產生的原始片段（header/footer 與各頁 `<main>` 內容）。
- `projects/<project_name>/`：組裝後的最終檔案（`index.html`, `css/main.css`, `js/script.js`, 以及 PHP 等資源）。
- `templates/`：本地範本，可用於參考或快速建立新專案樣板。

## 安裝與先決條件 ##
- Python 3.9+。
- 建議安裝套件：`requests`, `tqdm`, `colorama`, `watchdog`（若要即時同步）。
- 在專案根目錄建立或編輯 `config.json`，加入至少 `deepseek_api_key`。例如：

## 安裝與設定（步驟） ##
1. 安裝必要套件：

```powershell
pip install requests tqdm colorama watchdog
```

2. 設定 `config.json`：在專案根目錄建立 `config.json`，並至少填入 `deepseek_api_key與可選的 `ftp_config：

```json
{
  "deepseek_api_key": "YOUR_KEY",
  "ftp_config": {
    "host": "ftp.your-domain.com",
    "user": "ftp_username",
    "password": "ftp_password",
    "remote_path": "/public_html",
    "port": 21,
    "use_tls": true
  }
  "projects_root": "projects",
  "max_generation_workers": 5
}
```

<br>

## 🚀快速開始 ##
1. 在專案根目錄啟動 shell：

```powershell
python shell.py
```

2. 常用命令範例：
- `gen --description "簡單的餐廳網站，含菜單與聯絡表單" --header "品牌 Logo 與簡單 nav" --footer "版權信息"`
- `addpage contact.html "聯絡表單頁面" @index.html @css/main.css`
- `edit index.html "將主標題改為紅色" @workings/_header.html`
- `deploy -s`（無提示模式，自動使用 `config.json` 的 FTP 設定）

**常見指令說明（重點）**
- `gen`：生成新專案並呼叫 LLM 產生檔案結構與內容。
- `addpage`：在已開啟專案中新增 HTML 或 PHP 頁面（HTML 寫入 `workings/`，PHP 寫入專案根目錄）。
- `edit`：以 LLM 協助編輯現有檔案。
- `deploy`：透過 `ftp_deployer.py` 將專案上傳至遠端 FTP。
- `updatehtml`：手動重新組裝 HTML（由 `workings/_header.html` + 每頁 `<main>` + `workings/_footer.html` 組成）。

**所有指令解說可查看** [docs/USAGE_TW.md](docs/USAGE_TW.md)

<br>

---

**重要規範：LLM 與 DOM 合約**
- 所有 prompt 與回應模板集中於 `llm_client.py`。修改前請仔細閱讀 `GLOBAL_DOM_CONTRACT`。
- 結構生成（`generate_structure`）要求 LLM 僅回傳 JSON 陣列（檔案路徑列表），不得有其它多餘文字。
- 必須包含 `_header.html` 與 `_footer.html`，且每個專案僅允許一個 CSS (`css/main.css`) 與一個 JS (`js/script.js`)。
- 一般頁面只能生成 `<main>...</main>`（不得包含 `<!DOCTYPE>`, `<html>`, `<head>`, `<body>`）。若需要頁面專屬 JS（例如互動或遊戲），允許在 `</main>` 後加一個 `<script>` 區塊，但不得包含與漢堡選單（hamburger）功能重複的實作。
- `GLOBAL_DOM_CONTRACT` 要求 `id="hamburger-btn"` 與 `id="mobile-menu"` 等特定 DOM 元素存在，且其切換邏輯應放在全域 `js/script.js`。

**PHP 與安全性**
- `file_generator.scan_php_safety()` 會檢查不安全用法（例如未過濾的 `$_GET`、`eval()`、直拼 SQL 字串等）。
- 生成的 PHP 建議使用 PDO 與預處理語句，並採用 `htmlspecialchars()` 等輸出過濾。
- 若 LLM 生成的 PHP 被標示為高風險，系統會要求使用者確認後才寫入檔案。

**路徑與檔案寫入慣例**
- HTML（非 PHP）內容預設寫入 `projects/<name>/workings/`，並透過 `assemble_html_files()` 組裝為最終 HTML（寫入 `projects/<name>/`）。
- PHP 與其他資源（CSS、JS）會放在專案根目錄或其下對應資料夾。
- `FileGenerator.is_safe_path()` 會阻止路徑穿越與寫出專案根目錄之外的行為。

**除錯與日誌**
- 日誌目錄：`logs/`（可檢查 `agent.log` 以查看 LLM 輸出與錯誤）。
- 常見錯誤：API Key 缺失、LLM 回傳格式錯誤、路徑越界、PHP 安全警示。處理方式多在 `USAGE_TW.md` 中有詳細說明。

**開發者指南**
- 新增命令：請參考 `commands/` 中的 mixin 範例（使用 `CommandParser` 統一錯誤處理與參數解析）。
- 修改 prompt：若要改動 `GLOBAL_DOM_CONTRACT`，必須同時更新 `js/script.js` 與 header/footer 模板以保持一致性。
- 測試 LLM 行為：建議先以短描述嘗試，觀察 `logs/` 與 `tqdm` 輸出，再逐步調整 prompt。

## 聯絡與回饋 ##
若你發現 prompt、程式邏輯有待調整或想新增測試，請提出 issue 或在專案中註明建議。


