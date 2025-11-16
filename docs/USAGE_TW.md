# 使用說明（繁體中文）

此文件針對本專案的開發者與 AI 編輯/代理（agents）提供操作說明、工作流程與重要規範。請在開始使用前完整閱讀。檔案位置與重要模組請參考下列說明。

---

## 目標概述

- 本專案是一套以 LLM（DeepSeek）為後端，交互式產生與編輯靜態網站頁面的工具。
- 主要互動介面為 `shell.py`，內含多個命令 mixin（放在 `commands/`）來完成專案建立、生成、編輯與部署等工作。

## 啟動與基本操作

1. 在專案根目錄執行 interactive shell：

```powershell
python shell.py
```

2. 在 shell 中常用命令：
- `gen --description "描述文本" [--header "頁首描述"] [--footer "頁尾描述"]`：建立新專案並由 LLM 生成完整結構與檔案。
- `addpage <file.html|file.php> "描述" [@ref ...]`：新增頁面（HTML 存於 `workings/`，PHP 放根目錄）。`@` 參考可指定現有檔案做為 style/context 參考。
- `edit <file> "描述" [@ref ...]`：編輯現有檔案，會把被編輯檔案內容與參考檔（`@`）傳給 LLM 作為上下文。
- `open <project_name>` / `create <project_name>` / `list`：專案管理相關命令（見 `project_commands.py`）。

範例：

```powershell
gen --description "簡單的餐廳網站，含菜單與聯絡表單" --header "品牌 Logo 與簡單 nav" --footer "版權信息"
addpage contact.html "聯絡表單頁面" @index.html @css/main.css
edit index.html "將主標題改為紅色" @workings/_header.html
```

---

## 詳細指令教學（初次使用者指南）

本章節為初次使用者提供各個指令的完整用法、參數解釋、實用範例與常見問題解答。請根據你的需求逐一參考相應指令的章節。

### 1. `gen` 指令 — 生成新網站專案

#### 指令用途
`gen` 是最核心的指令，用於建立一個完整的新網站專案。它會調用 LLM（DeepSeek）生成專案的檔案結構、頁面內容、樣式表與腳本。

#### 指令格式與參數說明

```
gen --description <描述或檔案路徑> [--header <描述或檔案路徑>] [--footer <描述或檔案路徑>]
```

**必需參數：**
- `--description` (或 `--desc`)：專案的主要描述。可以是：
  - 直接文字：`--description "一個簡單的餐廳網站"`
  - 檔案路徑：`--description descriptions/restaurant.txt`（系統會自動讀取檔案內容）

**可選參數：**
- `--header`：頁首（header）的特定需求描述。若未提供，系統會詢問或使用預設值。
- `--footer`：頁尾（footer）的特定需求描述。若未提供，系統會詢問或使用預設值。

#### 執行流程
1. 系統加載描述內容（若為檔案路徑則自動讀取）。
2. 提示使用者確認 main description、header 與 footer。
3. （可選）呼叫 AI 優化描述（會詢問使用者）。
4. 呼叫 LLM 生成檔案結構（JSON 格式）。
5. 根據結構並行生成所有檔案。
6. 組裝 HTML 檔案（header + 頁面內容 + footer）。
7. 嘗試在預設瀏覽器中開啟 `index.html` 預覽。

#### 使用範例

##### 範例 1：簡單的直文本描述

```powershell
gen --description "簡單的餐廳網站，展示菜單、營業時間與預約方式" --header "餐廳 Logo 與導覽列" --footer "版權信息與聯絡資訊"
```

**說明：** 系統會詢問專案名稱（例如 `restaurant`），然後依據描述生成完整網站。最終會在 `projects/restaurant/` 目錄下產生 `index.html` 及其他檔案。

##### 範例 2：使用 header/footer 預設值

```powershell
gen --description "線上書店，支援瀏覽、搜尋與購物車功能"
```

**說明：** 由於未提供 `--header` 與 `--footer`，系統會在 shell 中詢問：
```
--- 頁首設定 ---
? 請輸入頁首 (header) 描述 (留空則使用 AI 預設): 
```
如果直接按 Enter 留空，系統會使用內建預設值。

##### 範例 3：使用外部描述檔案

首先建立一個描述檔案 `project_descriptions/blog_site.txt`：

```
個人部落格網站，專注於旅遊筆記與攝影分享。
網站應包含：
- 首頁（展示最新文章）
- 分類頁面（按主題分類）
- 單篇文章頁面
- 聯絡頁面
風格應該是簡約但優雅，背景清爽。
```

然後執行：

```powershell
gen --description project_descriptions/blog_site.txt --header "部落格 Logo 與導覽" --footer "Powered by AI, 2025"
```

**說明：** 系統會自動讀取 `blog_site.txt` 的內容，並詢問 header/footer 的詳細需求。

##### 範例 4：與 AI 優化描述

```powershell
gen --description "遊戲開發工作室的官方網站"
```

執行後，系統會詢問：
```
是否開始 AI 優化您的需求描述? [y/n]: 
```

選擇 `y` 時，LLM 會自動豐富描述文字（例如補充功能說明、視覺風格建議等），並在最後詢問：
```
是否使用此優化後的描述來生成網站 (頁首/頁尾保留不變)? [y/n]:
```

##### 範例 5：使用多檔案參數（header 與 footer 也來自檔案）

建立 `project_descriptions/` 下的三個檔案：

**main.txt：**
```
教育培訓平台，提供線上課程與學習工具。
```

**header_spec.txt：**
```
專業的藍色主題導覽列，包含登入/註冊按鈕。
```

**footer_spec.txt：**
```
深灰色背景，包含公司資訊、社群連結與版權聲明。
```

執行：

```powershell
gen --description project_descriptions/main.txt --header project_descriptions/header_spec.txt --footer project_descriptions/footer_spec.txt
```

#### 常見問題與解決方法

| 問題 | 原因 | 解決方法 |
|------|------|--------|
| `錯誤：未設定 API Key` | `config.json` 缺少 `deepseek_api_key` | 編輯 `config.json`，加入有效的 DeepSeek API Key |
| `錯誤：主要描述內容為空` | 檔案路徑不存在或檔案為空 | 確認檔案路徑正確且檔案有內容 |
| `錯誤：無法從 AI 獲取檔案結構` | LLM 回傳格式不正確 | 檢查 `logs/agent.log`；嘗試用更短的描述重試 |
| 生成過程非常緩慢 | 描述過長或 LLM 負載高 | 拆分成多個較短的描述，分次生成 |
| `index.html` 預覽無法打開 | 瀏覽器路徑設定問題 | 手動打開 `projects/<project_name>/index.html` |

---

### 2. `addpage` 指令 — 新增頁面

#### 指令用途
在已開啟的專案中新增一個頁面或 PHP 文件。支援 HTML 與 PHP 兩種檔案類型。

#### 指令格式與參數說明

```
addpage <檔案名稱> "<頁面描述>" [@參考檔案1 @參考檔案2 ...]
```

**必需參數：**
- `<檔案名稱>`：新頁面的檔名，例如 `contact.html` 或 `api.php`。
  - HTML 檔案會被寫入 `workings/` 並稍後組裝。
  - PHP 檔案會直接寫入專案根目錄。
- `"<頁面描述>"`：對新頁面的功能描述，LLM 會根據此描述生成頁面內容。

**可選參數：**
- `@參考檔案`：參考現有檔案做為風格與上下文參考，例如 `@index.html` 或 `@css/main.css`。可指定多個參考檔案，用空格分隔。

#### 執行流程
1. 確認已開啟專案（否則提示錯誤）。
2. 檢查檔案是否已存在（若存在則詢問是否覆蓋）。
3. 收集參考檔案的內容（若有）。
4. 呼叫 LLM 生成頁面內容。
5. 檢查安全性（若為 PHP，則檢查是否含有危險模式）。
6. 寫入檔案到適當位置。
7. 若為 HTML，自動重新組裝專案。

#### 使用範例

##### 範例 1：新增簡單的 HTML 頁面

假設已開啟 `restaurant` 專案。執行：

```powershell
addpage contact.html "聯絡我們頁面，包含聯絡表單與地圖"
```

**說明：** 系統會生成一個名為 `contact.html` 的新頁面，存放在 `projects/restaurant/workings/contact.html`。

##### 範例 2：新增頁面並參考現有檔案風格

```powershell
addpage gallery.html "圖片庫頁面，展示餐廳環境與料理照片" @index.html @css/main.css
```

**說明：** LLM 會參考 `index.html` 與 `css/main.css` 的風格與設計，確保新頁面與現有風格保持一致。

##### 範例 3：新增 PHP 文件（表單後端）

```powershell
addpage form_handler.php "表單提交處理 PHP 文件，使用 PDO 存入資料庫，並返回成功/失敗訊息" @contact.html
```

**說明：** 系統會：
1. 生成 PHP 代碼。
2. 掃描是否有安全風險（例如 SQL 注入、XSS）。
3. 若檢測到風險，提示使用者確認後再存入。
4. 將檔案寫入 `projects/restaurant/form_handler.php`（直接放在根目錄）。

#### 常見問題與解決方法

| 問題 | 原因 | 解決方法 |
|------|------|--------|
| `請先開啟專案` | 沒有開啟任何專案 | 執行 `open <project_name>` 或 `create <project_name>` 先開啟專案 |
| `檔案已存在，覆蓋？` | 欲新增的檔案已經存在 | 選 `n` 改用其他名稱，或選 `y` 覆蓋 |
| `錯誤：檔案必須是 .html 或 .php` | 副檔名不支援（例如 `.jsx`） | 改用 `.html` 或 `.php` |
| `警告：PHP 代碼存在安全風險` | LLM 生成的 PHP 有問題（例如 `eval()`） | 檢查警告內容，選 `n` 不存入，或 `y` 強制存入後自行修正 |
| 生成的頁面與預期風格不符 | 參考檔案不足或描述不夠清楚 | 提供更多 `@參考檔案`，或用 `edit` 指令修改 |

---

### 3. `edit` 指令 — 編輯現有檔案

#### 指令用途
編輯現有檔案（HTML、CSS、JavaScript、PHP 等），可將編輯需求傳給 LLM 自動完成修改。

#### 指令格式與參數說明

```
edit <檔案路徑> "<編輯需求>" [@參考檔案1 @參考檔案2 ...]
```

**必需參數：**
- `<檔案路徑>`：欲編輯的檔案，例如 `index.html` 或 `css/main.css`。系統會自動查詢 `workings/` 或專案根目錄。
- `"<編輯需求>"`：對修改的詳細說明，例如「將標題改為紅色」或「新增三列的產品展示區」。

**可選參數：**
- `@參考檔案`：參考現有檔案做為修改參考，確保修改風格一致。

#### 執行流程
1. 確認已開啟專案。
2. 查詢檔案（優先查 `workings/`，再查根目錄）。
3. 讀取檔案原始內容。
4. 收集參考檔案內容（若有）。
5. 若編輯的是 header/footer，也會讀取專案結構（所有檔案清單）。
6. 呼叫 LLM 進行修改，傳入原始內容、編輯需求與參考內容。
7. 寫入修改後的內容。
8. 若編輯的是 HTML 檔案（來自 `workings/`），自動重新組裝專案。

#### 使用範例

##### 範例 1：簡單的樣式修改

假設已開啟 `restaurant` 專案。執行：

```powershell
edit index.html "將主標題改為紅色，並增加字號"
```

**說明：** LLM 會讀取 `index.html` 的內容，找到主標題元素，並修改其 CSS 樣式（例如新增 `color: red; font-size: larger;`）。

##### 範例 2：複雜的內容修改，搭配參考檔案

```powershell
edit index.html "新增一個三欄的產品展示區，顯示餐廳的推薦菜色。每一欄應包含菜色圖片、名稱、敘述與價格" @gallery.html @css/main.css
```

**說明：** 
- LLM 會參考 `gallery.html` 與 `css/main.css` 的設計模式。
- 在 `index.html` 中新增一個結構相似但針對菜色的展示區。
- 確保新增區域與現有風格一致。

##### 範例 3：編輯 CSS 檔案

```powershell
edit css/main.css "新增一個深色模式的主題，顏色方案為深灰 (#2a2a2a) 背景、白色文字、橙色強調"
```

**說明：** LLM 會在 `css/main.css` 中新增相應的 CSS 規則（例如 `@media (prefers-color-scheme: dark)` 或其他主題機制）。

#### 常見問題與解決方法

| 問題 | 原因 | 解決方法 |
|------|------|--------|
| `找不到檔案` | 檔案路徑輸入錯誤或檔案實際不存在 | 確認檔案名稱與路徑正確；可先用 `list` 查看當前專案檔案 |
| `編輯後的內容格式錯誤` | LLM 回應格式問題 | 檢查日誌 (`logs/`)；嘗試用更明確的編輯需求重試 |
| `編輯後的 HTML 少了某些元素` | 通常是因為 LLM 誤解或刪除了不在編輯需求中的部分 | 使用 `@參考檔案` 提供更多上下文，或再次編輯來補回遺失的內容 |
| `修改被重新組裝後遺失` | 在 `workings/` 中編輯的 HTML 被重新組裝時意外覆蓋 | 確認編輯內容在 `<main>...</main>` 區塊內；若在 header/footer，改用 `edit _header.html` 等指令 |

---

### 4. `deploy` 指令 — 部署網站到 FTP 伺服器

#### 指令用途
將已開啟的專案上傳至遠端 FTP 伺服器。支援上傳整個專案或僅指定檔案，並提供互動模式與無提示模式。

#### 指令格式與參數說明

```
deploy [file1 file2 ...] [--host <主機>] [--user <使用者>] [--path <遠端路徑>] [--pass <密碼>] [-s|--silent]
```

**可選參數：**
- `file1 file2 ...`：欲上傳的檔案清單。若留空，則上傳整個專案。
- `--host <主機>`：FTP 伺服器位址（例如 `ftp.example.com`）。若未指定，使用 `config.json` 或提示輸入。
- `--user <使用者>`：FTP 使用者名稱。若未指定，使用 `config.json` 或提示輸入。
- `--path <遠端路徑>`：遠端基礎路徑（例如 `/public_html`）。若未指定，使用預設值。
- `--pass <密碼>`：FTP 密碼。若未指定，會提示輸入（不建議直接在指令中輸入密碼）。
- `-s` 或 `--silent`：啟用無提示模式，完全依賴 `config.json` 中的 `ftp_config` 設定，跳過所有互動式提示。

#### config.json FTP 設定範例

```json
{
  "deepseek_api_key": "YOUR_KEY",
  "ftp_config": {
    "host": "ftp.your-domain.com",
    "user": "ftp_username",
    "password": "ftp_password",
    "remote_path": "/public_html"
  }
}
```

#### 執行流程
1. 確認已開啟專案。
2. 根據 `--silent` 模式決定是否使用 `config.json` 設定或提示輸入。
3. 驗證 FTP 連接資訊。
4. 若指定檔案列表，則僅上傳指定檔案；否則上傳整個專案（忽略 `workings/` 等特定目錄）。
5. 確認上傳清單（非 silent 模式會提示）。
6. 連接 FTP 伺服器並上傳檔案。
7. 斷開連接，顯示部署完成。

#### 使用範例

##### 範例 1：互動模式部署整個專案

假設已開啟 `restaurant` 專案。執行：

```powershell
deploy
```

**執行過程：**
```
--- 完整專案上傳 ---
確認上傳 *整個專案* 'restaurant' 至 ftp.example.com:/public_html/restaurant？ [y/n]: y
[!] 無提示上傳 *整個專案* 'restaurant' 至 ftp.example.com:/public_html/restaurant
連接成功，開始上傳...
部署完成！
```

**說明：** 系統會詢問 FTP 伺服器資訊，然後上傳整個 `projects/restaurant/` 目錄（自動忽略 `workings/` 等）。

##### 範例 2：上傳指定檔案

```powershell
deploy index.html css/main.css js/script.js
```

**執行過程：**
```
--- 指定檔案上傳 ---
  - [準備] index.html
  - [準備] css/main.css
  - [準備] js/script.js
確認上傳 3 個檔案至 ftp.example.com:/public_html/restaurant？ [y/n]: y
連接成功，開始上傳...
部署完成！
```

**說明：** 只上傳指定的三個檔案，而不是整個專案。適合快速發布單一變更。

##### 範例 3：無提示模式（依賴 config.json）

```powershell
deploy -s
```

或

```powershell
deploy index.html css/main.css -s
```

**執行過程：**
```
[!] 啟用無提示模式 (-s)，使用 config.json 中的 ftp設定...
[!] 無提示上傳 *整個專案* 'restaurant' 至 ftp.example.com:/public_html/restaurant
連接成功，開始上傳...
部署完成！
```

**說明：** 
- 不詢問任何資訊，直接使用 `config.json` 中的設定。
- 適合自動化腳本或 CI/CD 流程。
- 若 `config.json` 設定不完整，會顯示錯誤提示。

##### 範例 4：指定 FTP 參數

```powershell
deploy --host ftp.staging.com --user staging_user --path /website_staging
```

**說明：** 
- 使用指定的 FTP 伺服器與路徑，而不使用 `config.json` 預設值。
- 會提示輸入密碼（不顯示在指令上）。
- 適合部署到多個不同伺服器的情況。

#### 常見問題與解決方法

| 問題 | 原因 | 解決方法 |
|------|------|--------|
| `請先開啟專案` | 沒有開啟任何專案 | 執行 `open <project_name>` 先開啟專案 |
| `錯誤：無提示模式失敗` | `config.json` 中 `ftp_config` 設定不完整 | 補全 `host`、`user`、`password`、`remote_path` 四個欄位 |
| `連接失敗` | FTP 伺服器位址、帳號或密碼錯誤 | 確認 FTP 伺服器資訊正確；檢查防火牆是否允許 FTP（port 21）連接 |
| `[警告] 找不到或不安全: xxx` | 指定的檔案不存在或路徑超出專案邊界 | 確認檔案名稱正確；不要使用 `../` 等路徑穿越語法 |
| `上傳成功但遠端網站無法訪問` | 遠端目錄結構不同或伺服器設定問題 | 確認遠端有 `index.html`；檢查伺服器的預設文檔設定 |

---

### 5. 檔案操作指令

#### `dir` — 列出專案目錄結構

```powershell
dir
```

以樹狀結構列出目前開啟專案中的所有檔案與目錄（自動忽略 `workings/`、`__pycache__` 等）。

**範例：**
```powershell
dir
```

**輸出：**
```
專案 'restaurant' 結構：
├── index.html
├── contact.html
├── css/
│   └── main.css
├── js/
│   └── script.js
└── form_handler.php
```

#### `rename` — 重新命名檔案

```powershell
rename <舊名稱> <新名稱>
```

重新命名檔案或目錄。會自動同時更新 `workings/` 中的同名檔案（若存在）。

**範例：**
```powershell
rename old_page.html new_page.html
```

**說明：** 重新命名後，系統建議執行 `updatehtml` 重新組裝 HTML。

#### `delete` — 刪除檔案

```powershell
delete <檔案路徑>
```

安全地刪除檔案。會檢查路徑安全性以防止誤刪。

**範例：**
```powershell
delete contact.html
```

**執行過程：**
```
即將刪除: contact.html
確認刪除？ [y/n]: y
已刪除: contact.html
建議執行 'updatehtml'。
```

#### `merge` — 合併檔案

```powershell
merge <輸入檔案1> [輸入檔案2 ...] <輸出檔案>
```

將多個檔案的內容合併至一個檔案。最後一個參數為輸出檔案。

**範例：**
```powershell
merge css/reset.css css/main.css css/combined.css
```

**說明：** 會將 `reset.css` 與 `main.css` 的內容依序合併到 `combined.css`。

#### `updatehtml` — 手動重新組裝 HTML

```powershell
updatehtml
```

手動重新組裝 HTML 檔案。系統會把 `workings/_header.html` + 各頁內容 + `workings/_footer.html` 合併成最終 HTML。

**範例：**
```powershell
updatehtml
```

**說明：** 在編輯 `workings/` 中的頁面或 header/footer 後，可執行此命令重新組裝。

---

### 6. 專案管理指令

#### `list` — 列出所有專案

```powershell
list
```

列出 `projects/` 目錄下的所有專案。

**範例：**
```powershell
list
```

**輸出：**
```
可用的專案 (3):
  - restaurant
  - blog
  - ecommerce
```

#### `open` — 開啟專案

```powershell
open <專案名稱>
```

開啟已存在的專案，用於後續編輯、新增頁面、部署等操作。開啟後，Shell 的提示符會變更為 `(專案名) $ `。

**範例：**
```powershell
open restaurant
```

**執行過程：**
```
已開啟專案: restaurant

(restaurant) $ 
```

#### `close` — 關閉目前專案

```powershell
close
```

關閉目前開啟的專案。提示符會恢復為 `(website-gen) $ `。

**範例：**
```powershell
close
```

**執行過程：**
```
正在關閉專案: restaurant
專案已關閉。

(website-gen) $ 
```

---

### 7. 系統命令

#### `help` — 顯示幫助資訊

```powershell
help [命令名稱]
```

顯示所有可用命令的列表，或某個特定命令的詳細說明。

**範例 1：顯示所有命令**
```powershell
help
```

**輸出：**
```
可用命令：

  gen              根據自然語言描述，透過互動式流程生成一個新網站。
  addpage          新增頁面: addpage <file.html|file.php> "<描述>" [@ref ...]
  edit             編輯檔案: edit <file> "<描述>" [@ref ...]
  deploy           部署專案至 FTP。
  ...
```

**範例 2：查看特定命令說明**
```powershell
help gen
```

#### `exit` / `quit` — 退出 Shell

```powershell
exit
```

或按 `Ctrl+D` 快速退出。

**說明：** 若有開啟的專案會自動關閉並清理資源。

---

## LLM 使用規則與 Prompt 約定（重要）

- 所有 prompt 與回應處理邏輯集中於 `llm_client.py`。在修改 prompt 模板前，務必了解 `GLOBAL_DOM_CONTRACT` 的內容與限制。
- 結構生成（`generate_structure`）要求 LLM 僅回傳一個 JSON 陣列（檔案路徑清單），不得輸出其他文字；`file_manager.parse_directory_structure()` 會解析這段 JSON。
- Header/Footer 規則：生成的結構必須包含 `_header.html` 與 `_footer.html`，且必須只有一個 CSS（`css/main.css`）與一個 JS（`js/script.js`）。
- Page 內容：一般頁面只能生成 `<main>...</main>` 區塊（不得產生 `<html>`, `<head>`, `<body>`, `<!DOCTYPE>` 等），如需頁面專屬 JS（例如遊戲、互動），允許在 `</main>` 後提供一個 `<script>` 區塊，但不得包含與漢堡選單相關的邏輯。
- 全域 DOM 合約（`GLOBAL_DOM_CONTRACT`）定義：`_header.html` 必須包含 `id=\"hamburger-btn\"` 的按鈕與 `id=\"mobile-menu\"` 的行動選單容器，且切換邏輯必須放在全域 `js/script.js`。

## PHP 與安全性檢查

- `file_generator.scan_php_safety()` 會檢查一些危險模式（例如未過濾的 `$_GET`、`eval()`、可能的 SQL 字串拼接）。
- 生成 PHP 時，必須使用 PDO 預處理語句、使用 `htmlspecialchars()` 或等效過濾，並禁止 `eval()`、`system()` 等危險函式。若 LLM 生成的 PHP 被標示為有問題，`addpage` 會提示並要求使用者確認後才儲存。

## 檔案寫入與路徑安全

- HTML 頁面（除 PHP）預設寫入到 `projects/<name>/workings/`，之後再由 `assemble_html_files()` 組裝到根目錄；PHP 與其他資源會放在專案根目錄。
- `FileGenerator.is_safe_path()` 會拒絕跨出專案根目錄的路徑（防止目錄穿越）。在新增或寫入檔案前，請先確認欲寫入路徑安全。

## 組裝流程（工作原理）

1. `gen`：
  - 透過 `llm_client.generate_structure()` 取得專案檔案清單（JSON）。
  - 根據清單並行呼叫 `llm_client.generate_file_content()` 為每個檔案生成內容（`FileGenerator.generate_project_files()`）。
  - 將 HTML 片段寫入 `workings/`，其他檔案寫入指定位置。
  - 呼叫 `file_manager.assemble_html_files()` 把 `_header.html` + 每頁 `<main>` + `_footer.html` 合併為最終 HTML 檔案。

## 日誌、偵錯與常見問題

- 日誌資料夾：`logs/`（如果需要更詳細日誌，檢查 `system_core.setup_logging()` 或 `config_log.py` 的設定）。
- 常見錯誤：
  - **API Key 未設定**：`config.json` 未包含 `deepseek_api_key`，會在呼叫 LLM 時失敗。
  - **LLM 回傳格式錯誤**：若結構生成未回傳合法 JSON，`parse_directory_structure()` 會回傳空列表，導致生成失敗。
  - **檔案路徑越界**：請確認 `is_safe_path()` 檢查通過。
  - **PHP 安全警告**：若 LLM 生成的 PHP 觸發安全檢測，系統會提示並暫停儲存。

## 延伸開發與貢獻提示

- 若要新增命令，請遵循 `commands/` 中現有的 mixin 風格；使用 `CommandParser`（`commands/command_parser.py`）來統一錯誤處理。
- 修改 prompt 模板時務必：
  1. 不要破壞 `GLOBAL_DOM_CONTRACT`（除非你也會更新 `js/script.js` 與 header templates）。
  2. 維持對輸出格式的嚴格要求（例如 `generate_structure` 必須只輸出 JSON 陣列）。
- 想在本地測試 LLM 行為時，先用較短的 `description` 測試，再觀察 `logs/` 與 `tqdm` 輸出。

## 部署

- 若要使用 FTP 部署，請檢查 `ftp_deployer.py`，確保 `config.json` 中包含相應的 FTP 設定（伺服器位址、帳號、密碼等），並注意不要把敏感資料直接提交到版本控制。

## 範例工作流程（快速示範）

1. 編輯 `config.json` 並加入 `deepseek_api_key`。
2. 啟動 shell： `python shell.py`。
3. 執行：

```powershell
gen --description "旅遊部落格，含景點介紹與聯絡頁" --header "Logo 與導覽" --footer "版權資訊"
```

4. 當生成完成後，預覽 `projects/<project_name>/index.html`（shell 會嘗試開啟瀏覽器預覽）。


---


