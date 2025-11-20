import requests
import json
import time
import logging
import re
from typing import List, Optional # 匯入 Optional
from tqdm import tqdm

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# [!! 重大更新 !!] DOM 互動合約 -> 全域 DOM 合約
# ----------------------------------------------------------------------------
# ... (GLOBAL_DOM_CONTRACT 保持不變) ...
GLOBAL_DOM_CONTRACT = """
**[!! 全域 DOM 互動合約 (Global DOM Contract) !!]**
為確保 `script.js` 能正確運作，`_header.html` 和 `js/script.js` **必須**嚴格遵守此合約：

1.  **行動選單按鈕 (漢堡)**: 
    * HTML: `<button id="hamburger-btn" ...>`
    * JS: `document.getElementById('hamburger-btn')`
2.  **行動選單容器 (下拉)**:
    * HTML: `<div id="mobile-menu" ...>`
    * JS: `document.getElementById('mobile-menu')`

`js/script.js` **只**應處理上述 ID。
`_header.html` **必須**生成包含上述 ID 的元素。
"""


# ----------------------------------------------------------------------------
# 提示模板 (Prompt Templates)
# ----------------------------------------------------------------------------
# ... (STRUCTURE_PROMPT_TEMPLATE 保持不變) ...
STRUCTURE_PROMPT_TEMPLATE = """
你是一個嚴格的網站架構師。
你的**唯一任務**是根據使用者描述，**必需**回傳一個 ```json ... ``` 程式碼區塊。

要求：
1.  **絕對不要**包含任何 HTML, CSS, 或 JS 程式碼。
2.  **僅回傳** JSON。
3.  **格式**：回傳一個 JSON **字串列表 (list of strings)**。
4.  **內容**：列表中的每個字串都必須是一個**相對於專案根目錄的檔案 path**。
5.  **模板 (極重要)**：
    * 你的結構**必須**包含 `_header.html` 和 `_footer.html`。
    * 你的結構應包含 `index.html`。
6.  **只包含程式碼檔案**：你的結構**只能**包含 .html, .css, .js 檔案。
7.  **所有html放在同一層目錄(.)，所有css檔放在css目錄(./css)，所有js檔放在js目錄(./js)。
8.  **CSS 規則 (極重要)**：你的結構**必須**只包含**一個** CSS 檔案，且其路徑**必須**是 `css/main.css`。
9.  **JS 規則 (極重要)**：你的結構**必須**只包含**一個** JS 檔案，且其路徑**必須**是 `js/script.js`。
10. **禁止資產檔案**：不要包含 .jpg, .png, .woff, .pdf, .ico。
11. **不要**包含根目錄 (例如 'my_project/') 在 path 中。

使用者描述：
"{user_input}"

請僅生成 ```json ... ``` 程式碼區塊，示例如下：
```json
[
  "_header.html",
  "_footer.html",
  "index.html",
  "css/main.css",
  "js/script.js"
]
```
"""

# ----------------------------------------------------------------------------
# [!! 新增 !!] Header 模板庫 (Template Library)
# ----------------------------------------------------------------------------
# ... (HEADER_STYLE_CHOOSER_TEMPLATE 保持不變) ...
HEADER_STYLE_CHOOSER_TEMPLATE = """
你是一位專業的設計總監。你的唯一任務是根據使用者的描述，從提供的風格列表中選擇最合適的一個。

**風格選項**：
1.  **V1_CLASSIC_BRIGHT**：(預設) 經典、專業、乾淨、明亮的設計。適用於企業、教育、內容型或標準網站。
2.  **V2_MODERN_DARK**：現代、大膽、深色的設計 (bg-gray-900)。適用於科技、遊戲、作品集或酷炫風格的網站。
3.  **V3_IMAGE_BRANDING**：使用高畫質圖片背景 (bg-cover, bg-blend-multiply) 和深色疊加。適用於需要強烈品牌形象和高級感的網站。
4.  **V4_MINIMAL_CENTERED**：簡約、優雅、Logo 居中的佈局。適用於時尚、部落格或個人品牌網站。

**使用者的主要描述**：
"---
{user_input}
---"

**指示**：
請**僅**回傳最合適的風格關鍵字（例如 `V1_CLASSIC_BRIGHT` 或 `V2_MODERN_DARK`）。
"""

# ... (HEADER_PROMPT_V1...V4 保持不變) ...
HEADER_PROMPT_V1_CLASSIC_BRIGHT = """
你是一個專業的全端工程師，專精於使用 **Tailwind CSS** 和 **Font Awesome**。
你的任務是生成 `_header.html` 模板檔案的內容，嚴格採用 **V1_CLASSIC_BRIGHT (經典明亮)** 風格。

**使用者的主要描述或特定指示**：
"---
{user_input}
---"

{dom_contract}

要求：
1.  **必須**生成完整的 HTML 開頭 (`<!DOCTYPE html>`, `<html lang="zh-Hant">`)。
2.  **必須**在 `<head>` 中加入：
    * **Tailwind CSS CDN**： `<script src="https://cdn.tailwindcss.com"></script>`
    * **Font Awesome CDN**： `<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">`
3.  **必須**使用 `<link>` 連結 `[專案結構]` 中所有的 .css 檔案 (例如 `css/main.css`)。
4.  **必須**生成 `<body>` 的 *開啟標籤* (例如 `<body class="font-sans leading-normal tracking-normal text-gray-800 bg-gray-50">`)。
5.  **風格 (V1_CLASSIC)**：**必須**建立一個使用 **Tailwind CSS** 樣式的 `<nav>` (例如 `bg-white shadow-md p-4 sticky top-0 z-50`)。
6.  **響應式漢堡選單佈局 (極重要)**：
    * **頂層列**：`nav` 內部應包含一個 `div` (例如 `<div class="container mx-auto flex justify-between items-center">`)，用於放置「網站標題」和「漢堡按鈕」。
    * **桌面選單**：`nav` 內部**也**應包含一個**桌面選單 `div`** (例如 `<div class="hidden md:flex space-x-4">...桌面連結...</div>`)。此 `div` 在手機上隱藏 (hidden)，在桌面上 (`md:`) 顯示為 `flex`。
    * **漢堡按鈕**：頂層列中**必須**包含漢堡按鈕。**必須**遵守 `[全域 DOM 互動合約]`，使用 `id="hamburger-btn"` (例如 `<button id="hamburger-btn" class="md:hidden text-gray-700 p-2 hover:bg-gray-100 rounded">...<i class="fas fa-bars"></i>...</button>`)。
    * **手機選單 (Dropdown)**：`nav` 內部**必須**包含一個**獨立的手機選單 `div`**。**必須**遵守 `[全域 DOM 互動合約]`，使用 `id="mobile-menu"` (例如 `<div id="mobile-menu" class="hidden md:hidden mt-4">...手機連結...</div>`)。
    * **[!!] 關鍵佈局**：`mobile-menu` **必須**位於頂層 `flex` 容器**之外**。
    * **手機連結**：`mobile-menu` 中的連結必須是 `class="block py-2 px-4 text-gray-700 hover:bg-gray-100"`。
7.  **[!! 重要 !!]** 你**不能**自己編寫 JavaScript 邏輯 (例如 `<script>` 標籤)。
8.  **[!! 重要 !!]** `js/script.js` 檔案將會負責處理 `id="hamburger-btn"` 和 `id="mobile-menu"` 的點擊切換邏輯。
9.  **語言**：**必須**使用**繁體中文**生成所有可見文字。
10. **僅回傳程式碼**：在回應中只包含 ```html ... ``` 程式碼區塊。

專案結構參考：
---
{file_list_str}
---
"""

HEADER_PROMPT_V2_MODERN_DARK = """
你是一個專業的全端工程師，專精於使用 **Tailwind CSS** 和 **Font Awesome**。
你的任務是生成 `_header.html` 模板檔案的內容，嚴格採用 **V2_MODERN_DARK (現代深色)** 風格。

**使用者的主要描述或特定指示**：
"---
{user_input}
---"

{dom_contract}

要求：
1.  **必須**生成完整的 HTML 開頭 (`<!DOCTYPE html>`, `<html lang="zh-Hant">`)。
2.  **必須**在 `<head>` 中加入：
    * **Tailwind CSS CDN**： `<script src="https://cdn.tailwindcss.com"></script>`
    * **Font Awesome CDN**： `<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">`
3.  **必須**使用 `<link>` 連結 `[專案結構]` 中所有的 .css 檔案 (例如 `css/main.css`)。
4.  **必須**生成 `<body>` 的 *開啟標籤* (例如 `<body class="font-sans leading-normal tracking-normal text-gray-800 bg-gray-100">`)。
5.  **風格 (V2_DARK)**：**必須**建立一個使用 **Tailwind CSS** 樣式的 `<nav>` (例如 `bg-gray-900 text-gray-100 shadow-lg p-4 sticky top-0 z-50`)。
6.  **響應式漢堡選單佈局 (極重要)**：
    * **頂層列**：`nav` 內部應包含一個 `div` (例如 `<div class="container mx-auto flex justify-between items-center">`)，用於放置「網站標題」和「漢堡按鈕」。
    * **桌面選單**：`nav` 內部**也**應包含一個**桌面選單 `div`** (例如 `<div class="hidden md:flex space-x-4">...桌面連結...</div>`)。
    * **漢堡按鈕**：頂層列中**必須**包含漢堡按鈕。**必須**遵守 `[全域 DOM 互動合約]`，使用 `id="hamburger-btn"` (例如 `<button id="hamburger-btn" class="md:hidden text-gray-300 p-2 hover:bg-gray-700 rounded">...<i class="fas fa-bars"></i>...</button>`)。
    * **手機選單 (Dropdown)**：`nav` 內部**必須**包含一個**獨立的手機選單 `div`**。**必須**遵守 `[全域 DOM 互動合約]`，使用 `id="mobile-menu"` (例如 `<div id="mobile-menu" class="hidden md:hidden mt-4 bg-gray-800 rounded-md shadow-lg">...手機連結...</div>`)。
    * **[!!] 關鍵佈局**：`mobile-menu` **必須**位於頂層 `flex` 容器**之外**，且**必須**有背景色 (如 `bg-gray-800`)。
    * **手機連結**：`mobile-menu` 中的連結必須是 `class="block py-2 px-4 text-gray-200 hover:bg-gray-700"`。
7.  **[!! 重要 !!]** 你**不能**自己編寫 JavaScript 邏輯 (例如 `<script>` 標籤)。
8.  **[!! 重要 !!]** `js/script.js` 檔案將會負責處理 `id="hamburger-btn"` 和 `id="mobile-menu"` 的點擊切換邏輯。
9.  **語言**：**必須**使用**繁體中文**生成所有可見文字。
10. **僅回傳程式碼**：在回應中只包含 ```html ... ``` 程式碼區塊。

專案結構參考：
---
{file_list_str}
---
"""

HEADER_PROMPT_V3_IMAGE_BRANDING = """
你是一個專業的全端工程師，專精於使用 **Tailwind CSS** 和 **Font Awesome**。
你的任務是生成 `_header.html` 模板檔案的內容，嚴格採用 **V3_IMAGE_BRANDING (品牌圖片背景)** 風格。

**使用者的主要描述或特定指示**：
"---
{user_input}
---"

{dom_contract}

要求：
1.  **必須**生成完整的 HTML 開頭 (`<!DOCTYPE html>`, `<html lang="zh-Hant">`)。
2.  **必須**在 `<head>` 中加入：
    * **Tailwind CSS CDN**： `<script src="https://cdn.tailwindcss.com"></script>`
    * **Font Awesome CDN**： `<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">`
3.  **必須**使用 `<link>` 連結 `[專案結構]` 中所有的 .css 檔案 (例如 `css/main.css`)。
4.  **必須**生成 `<body>` 的 *開啟標籤* (例如 `<body class="font-sans leading-normal tracking-normal text-gray-800 bg-gray-50">`)。
5.  **風格 (V3_IMAGE)**：
    * **必須**建立一個使用 **Tailwind CSS** 樣式的 `<nav>`。
    * **[!!] 關鍵風格**：**必須**使用 `bg-cover` (背景覆蓋), `bg-center` (背景居中), `bg-gray-900` (深色底色), `text-white` (白色文字), `shadow-lg`, `p-4`, `sticky top-0 z-50`。
    * **[!!] 混合模式**：**必須**加入 `bg-blend-multiply` 類別，使圖片與深色底色混合，以確保文字可讀性。
    * **[!!] 圖片**：**必須**在 `<nav>` 標籤上使用 `style="..."` 屬性加入一個**高品質的背景圖片 URL**。
    * **範例 `<nav>` 標籤**：
      `<nav class="sticky top-0 z-50 p-4 text-white shadow-lg bg-cover bg-center bg-gray-900 bg-blend-multiply" style="background-image: url('https://images.unsplash.com/photo-1506748686214-e9df14d4d9d0?auto=format&fit=crop&w=1740');">`
6.  **響應式漢堡選單佈局 (極重要)**：
    * **頂層列**：`nav` 內部應包含一個 `div` (例如 `<div class="container mx-auto flex justify-between items-center">`)，用於放置「網站標題」和「漢堡按鈕」。
    * **桌面選單**：`nav` 內部**也**應包含一個**桌面選單 `div`** (例如 `<div class="hidden md:flex space-x-4">...桌面連結...</div>`)。
    * **漢堡按鈕**：頂層列中**必須**包含漢堡按鈕。**必須**遵守 `[全域 DOM 互動合約]`，使用 `id="hamburger-btn"` (例如 `<button id="hamburger-btn" class="md:hidden text-white p-2 hover:bg-white/20 rounded">...<i class="fas fa-bars"></i>...</button>`)。
    * **手機選單 (Dropdown)**：`nav` 內部**必須**包含一個**獨立的手機選單 `div`**。**必須**遵守 `[全域 DOM 互動合約]`，使用 `id="mobile-menu"`。
    * **[!!] 關鍵佈局**：`mobile-menu` **必須**位於頂層 `flex` 容器**之外**。
    * **[!!] 手機選單風格**：`mobile-menu` **必須**有**不透明**的深色背景 (例如 `bg-gray-900` 或 `bg-gray-800`)，以確保在頁面內容之上清晰顯示。
    * **範例**：`<div id="mobile-menu" class="hidden md:hidden mt-4 bg-gray-900 rounded-md shadow-lg">...手機連結...</div>`
    * **手機連結**：`mobile-menu` 中的連結必須是 `class="block py-2 px-4 text-white hover:bg-gray-700"`。
7.  **[!! 重要 !!]** 你**不能**自己編寫 JavaScript 邏輯 (例如 `<script>` 標籤)。
8.  **[!! 重要 !!]** `js/script.js` 檔案將會負責處理 `id="hamburger-btn"` 和 `id="mobile-menu"` 的點擊切換邏輯。
9.  **語言**：**必須**使用**繁體中文**生成所有可見文字。
10. **僅回傳程式碼**：在回應中只包含 ```html ... ``` 程式碼區塊。

專案結構參考：
---
{file_list_str}
---
"""

HEADER_PROMPT_V4_MINIMAL_CENTERED = """
你是一個專業的全端工程師，專精於使用 **Tailwind CSS** 和 **Font Awesome**。
你的任務是生成 `_header.html` 模板檔案的內容，嚴格採用 **V4_MINIMAL_CENTERED (簡約居中)** 風格。

**使用者的主要描述或特定指示**：
"---
{user_input}
---"

{dom_contract}

要求：
1.  **必須**生成完整的 HTML 開頭 (`<!DOCTYPE html>`, `<html lang="zh-Hant">`)。
2.  **必須**在 `<head>` 中加入：
    * **Tailwind CSS CDN**： `<script src="https://cdn.tailwindcss.com"></script>`
    * **Font Awesome CDN**： `<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">`
3.  **必須**使用 `<link>` 連結 `[專案結構]` 中所有的 .css 檔案 (例如 `css/main.css`)。
4.  **必須**生成 `<body>` 的 *開啟標籤* (例如 `<body class="font-sans leading-normal tracking-normal text-gray-800 bg-white">`)。
5.  **風格 (V4_MINIMAL)**：**必須**建立一個使用 **Tailwind CSS** 樣式的 `<nav>` (例如 `bg-white p-4 border-b border-gray-200 sticky top-0 z-50`)。
6.  **響應式「居中佈局」 (極重要)**：
    * **頂層列**：`nav` 內部應包含一個 `div` (例如 `<div class="container mx-auto flex justify-between items-center">`)，用於放置「網站標題/Logo」和「漢堡按鈕」。
    * **漢堡按鈕**：頂層列中**必須**包含漢堡按鈕。**必須**遵守 `[全域 DOM 互動合約]`，使用 `id="hamburger-btn"` (例如 `<button id="hamburger-btn" class="md:hidden text-gray-700 p-2 hover:bg-gray-100 rounded">...<i class="fas fa-bars"></i>...</button>`)。
    * **導覽容器 (新)**：`nav` 內部**必須**在「頂層列」**之後**包含一個**導覽容器** (例如 `<div class="w-full container mx-auto">`)。
    * **桌面選單 (居中)**：此「導覽容器」中應包含**桌面選單** (例如 `<div class="hidden md:flex justify-center space-x-6 py-2">...桌面連結...</div>`)。
    * **手機選單 (Dropdown)**：此「導覽容器」中**也**應包含**手機選單**。**必須**遵守 `[全域 DOM 互動合約]`，使用 `id="mobile-menu"` (例如 `<div id="mobile-menu" class="hidden md:hidden mt-2">...手機連結...</div>`)。
    * **手機連結**：`mobile-menu` 中的連結必須是 `class="block py-2 px-4 text-center text-gray-700 hover:bg-gray-100"` (文字居中)。
7.  **[!! 重要 !!]** 你**不能**自己編寫 JavaScript 邏輯 (例如 `<script>` 標籤)。
8.  **[!! 重要 !!]** `js/script.js` 檔案將會負責處理 `id="hamburger-btn"` 和 `id="mobile-menu"` 的點擊切換邏輯。
9.  **語言**：**必須**使用**繁體中文**生成所有可見文字。
10. **僅回傳程式碼**：在回應中只包含 ```html ... ``` 程式碼區塊。

專案結構參考：
---
{file_list_str}
---
"""

# ----------------------------------------------------------------------------
# [!! 舊 HEADER_PROMPT_TEMPLATE 已被移除 !!]
# ----------------------------------------------------------------------------

FOOTER_PROMPT_TEMPLATE = """
你是一個專業的全端工程師，專精於使用 **Tailwind CSS**。
你的任務是生成 `_footer.html` 模板檔案的內容。

**使用者的主要描述或特定指示**：
"---
{user_input}
---"

要求：
1.  **必須**生成一個使用 **Tailwind CSS** 樣式的美觀 `<footer>` 區塊 (例如 `bg-gray-800 text-white p-10 mt-12`)。
2.  **語言**：**必須**使用**繁體中文**生成所有可見文字（例如頁尾的版權聲明），除非使用者在專案描述中明確指定了 other languages。
3.  **必須**使用 `<script src="..." defer>` 連結 `[專案結構]` 中所有的 .js 檔案 (例如 `script.js`)。
4.  **必須**生成 `</body>` 和 `</html>` 的 *關閉標籤*。
5.  **僅回傳程式碼**：在回應中只包含 ```html ... ``` 程式碼區塊。

專案結構參考：
---
{file_list_str}
---

請僅生成 `_footer.html` 的內容：
"""

# [!! 重大更新 !!] 更改 PAGE_CONTENT_PROMPT_TEMPLATE (Template #4) 以允許 In-Page JS
PAGE_CONTENT_PROMPT_TEMPLATE = """
你是一個專業的全端工程師，專精於使用 **Tailwind CSS** 和 **Font Awesome** 撰寫頁面內容。
我正在建立一個網站，專案描述如下：
"---
{user_input}
---"

你**目前**正在為以下**單一內容檔案**生成內容：
檔案路徑： `{file_path}`

{dom_contract}

**!! 極重要指令 (必須嚴格遵守) !!**
1.  你**只能**生成該頁面的**主要內容**。
2.  **地域**：香港；**語言**：**必須**使用**繁體中文**生成所有可見文字，除非使用者在專案描述中明確指定了其他語言。
3.  你**必須**使用 **Tailwind CSS** 樣式 (例如 `container mx-auto p-8`) 來排版內容。
4.  **使用圖示**：在適當的地方**加入 Font Awesome 圖示**以美化頁面 (例如 `<h2><i class="fas fa-map-marker-alt mr-2"></i>景點介紹</h2>`)。
5.  你**必須**使用 `<main>` 標籤包裹所有 HTML 內容 (例如 `<main class="container mx-auto my-12 p-4 min-h-screen">...內容...</main>`)。
6.  **ID 建立**：如果此頁面內容需要 JS 互動 (例如表單、圖片庫)，你**必須**為相關元素建立**邏輯清晰且唯一**的 `id` (例如 `id="contact-form"`)。
7.  **[!! 重要 !!] JavaScript 邏輯 (重要)**：
    * 如果此頁面 (`{file_path}`) 需要**頁面特定**的互動 (例如聯絡表單驗證、圖片庫輪播)，你**必須**將該 JS 邏輯放在一個 `<script>` 標籤中，該標籤應位於 `</main>` 標籤**之後**。
    * **禁止**：**絕對不要**在此處編寫**漢堡選單**的邏輯（`js/script.js` 會處理）。
    * **安全規則**：**禁止** `innerHTML`，**必須**使用 `textContent`。
    * **範例**：
        <main>
          <form id="contact-form">...</form>
        </main>
        <script>
          // (此頁面專用的 JS 邏輯)
          document.addEventListener('DOMContentLoaded', () => {{
            const form = document.getElementById('contact-form');
            if (form) {{
              form.addEventListener('submit', (e) => {{
                // ... 驗證邏輯 ...
              }});
            }}
          }});
        </script>
8.  **!! 絕對禁止 !!** 在你的回應中包含 `<html>`, `<head>`, `<body>`, `<!DOCTYPE>`, `<nav>` 或 `<footer>` 標籤。
9.  **!! 絕對禁止 !!** AI 若違反規則 #8，將導致整個專案失敗。
10. **僅回傳程式碼**：在回應中只包含 ```html ... ``` 程式碼區塊。

請僅生成 `{file_path}` 的 **<main> 內容** 和 **<script> 內容** (如果需要)：
"""

CSS_PROMPT_TEMPLATE = """
你是一個 CSS 專家，與 Tailwind CSS 協同工作。
你的任務是為 `{file_path}` 檔案生成**補充**的 CSS 規則。

要求：
1.  **不要**重設 (reset) 樣式，Tailwind 已經處理過了。
2.  **只**為 Tailwind 無法輕易處理的**自訂**樣式編寫 CSS (例如：複雜的動畫、特定的 `::before` / `::after` 偽元素)。
3.  **保持簡潔**。大部分樣式應由 Tailwind 處理。
4.  **僅回傳程式碼**：在回應中只包含 ```css ... ``` 程式碼區塊。

專案描述：
"---
{user_input}
---"

請僅生成 `{file_path}` 的內容：
"""

# [!! 更新 !!] 注入 GLOBAL_DOM_CONTRACT 並釐清職責
JS_PROMPT_TEMPLATE = """
你是一個專業的 JavaScript 開發人員，編寫安全、現代的程式碼。
你的任務是為 `{file_path}` (全域腳本) 檔案生成內容。

**使用者的主要描述或特定指示**：
"---
{user_input}
---"

{dom_contract}

**!! 極重要安全規則 !!**
1.  **禁止使用 `innerHTML`**：為了防止 XSS 攻擊，**必須**改用 `textContent` 或 `innerText` 來插入文字。
2.  **禁止 Base64**：**絕對禁止**在 JS 檔案中嵌入 base64 編碼的圖片、字型或聲音檔。
3.  **使用 `addEventListener`**：不要使用 `onclick` 這樣的 HTML 內聯事件。

要求：
1.  **[!! 職責釐清 !!]** 你的**唯一**任務是處理 `[全域 DOM 互動合約]` 中定義的元素。
2.  **在script.js中** 你**必須**編寫漢堡選單切換功能。
3.  **在script.js中** **必須**遵守 `[全域 DOM 互動合約]`，選取 `id="hamburger-btn"` 和 `id="mobile-menu"`。當按鈕被點擊時，切換 (toggle) `mobile-menu` 容器的 `hidden` CSS 類別。
4.  **在script.js中** 你的所有 JS 程式碼**必須**包裹在 `document.addEventListener('DOMContentLoaded', () => {{ ... }});` 事件監聽器中，以確保 DOM 已完全載入。
5.  **[!! 禁止 !!]** **絕對不要**編寫任何頁面特定的邏輯（例如表單驗證、圖片庫）。那些邏輯將由 HTML 頁面中的 `<script>` 標籤自行處理。
6.  **語言**：**必須**使用**繁體中文**生成所有插入到 DOM 的文字（例如 `textContent`），除非使用者在專案描述中明確指定了其他語言。
7.  **僅回傳程式碼**：在回應中只包含 ```javascript ... ``` 程式碼區塊。

請僅生成 `{file_path}` 的內容：
"""

# [!! 1. llm_client.py 更新 !!] 新增 {reference_context} 區塊
EDIT_FILE_PROMPT_TEMPLATE = """
你是一個專業的全端工程師，任務是修改現有的程式碼。

**使用者的修改要求**：
"---
{edit_prompt}
---"

**[!! 參考檔案上下文 (Context) !!]**
使用者提供了以下檔案的內容作為參考。
你**必須**使用這些檔案來理解專案的風格、結構和編碼慣例。
**不要**將此上下文視為你正在編輯的檔案。
---
{reference_context}
---

**你正在編輯的檔案**：
`{file_path}`

**[!! 專案結構參考 (僅在編輯 Header/Footer 時提供) !!]**
---
{project_structure}
---

{dom_contract}

**!! 極重要指令 (必須嚴格遵守) !!**
1.  你**必須**回傳**完整且已更新**的檔案內容。
2.  **不要**只回傳你修改的部分或 diff。
3.  **不要**在你的回應中加入任何解釋性的文字，只回傳 ```{language} ... ``` 程式碼區塊。
4.  **保持一致性**：確保你的修改與原始程式碼的風格和框架（Tailwind, Font Awesome）保持一致。
5.  **[!! 更新 !!]** 你**必須**遵守 `[全域 DOM 互動合約]` (針對 header/footer 相關元素)。
6.  **[!! 更新 !!]** 如果你正在編輯一個帶有**頁面特定** `<script>` 標籤的 HTML 檔案，請確保你的 HTML 變更與該腳本中的 `id` 保持一致。
7.  **結構感知 (Header/Footer)**：
    * 如果正在編輯 `_header.html`，請**務必**使用 `[專案結構參考]` 來更新 `<nav>` 中的所有連結。
    * **規則**：從 `[專案結構參考]` 列表中，找出所有`/workings`目錄、且**不以** `_` 開頭的 `.html` 檔案 (例如 `index.html`)。
    * **規則**：為所有找到的檔案在 `<nav>` 中建立連結及項目名稱。
    * 如果正在編輯 `_footer.html`，且頁尾中包含導覽連結，也請**務必**遵循上述規則更新連結。
8.  **語言**：**必須**使用**繁體中文**生成所有*新的*可見文字，除非使用者明確指定其他語言。
9.  **安全規則 (若為 JS)**：保持 `textContent` 的使用，**禁止** `innerHTML`。
10. **重要**：如果編輯的是html文件，只需生成<main>...</main><script>...</script>之間的內容，**不要**包含 `<html>`, `<head>`, `<body>`, `<!DOCTYPE>`, `<nav>` 或 `<footer>` 標籤。

**原始程式碼**：
"---
{original_code}
---"

請僅生成 `{file_path}` 的**完整新內容**：
"""

# ----------------------------------------------------------------------------
# [!! 更新 !!] 模板 8: 需求優化模板 (僅優化 Description)
# ----------------------------------------------------------------------------
PROMPT_OPTIMIZATION_TEMPLATE = """
你是一位專業的 AI 需求分析師和提示工程師 (Prompt Engineer)。
你的任務是**只優化使用者的「主要描述」**，使其更豐富、更清晰，以便 AI 生成器能更好地理解。

**語言**：你的輸出**必須**是**繁體中文**。
**地域**：香港
**輸出**：**僅**回傳優化後的「主要描述」文字，**不要**包含 "這是一個優化後的提示：" 這樣的開場白。

**使用者的原始「主要描述」：**
"---
{main_description}
---"

**上下文 (僅供參考，不要合併到輸出中)：**
* 頁首需求： "{header_description}"
* 頁尾需求： "{footer_description}"

**你的任務：**
請**僅**針對「主要描述」進行優化和豐富。
1.  澄清網站的主題和目標。
2.  豐富細節，確保 AI 能夠理解主體的風格（例如：專業、活潑、簡約）。
3.  **不要**在你的回覆中提及頁首或頁尾的具體內容，AI 會分開處理它們。

**範例輸出 (如果原始描述是 "一個關於狗的網站"):**
"建立一個內容豐富、充滿活力的網站，專門介紹各種犬種。網站應包含犬種介紹、飼養技巧和健康資訊區塊，整體風格應設計為家庭 friendly 且資訊豐富。"

請開始優化「主要描述」：
"""

# [!! 2. llm_client.py 更新 !!] 新增 {reference_context} 區塊
ADD_PAGE_PROMPT_TEMPLATE = """
你是一個專業的全端工程師，專精於使用 **Tailwind CSS** 和 **Font Awesome**。
你的任務是為使用者的新頁面生成內容。

**使用者的頁面描述**：
"---
{user_input}
---"

**[!! 參考檔案上下文 (Context) !!]**
使用者提供了以下檔案的內容作為參考。
你**必須**使用這些檔案來理解專案的風格、結構和編碼慣例。
**不要**將此上下文視為你正在編輯的檔案。
---
{reference_context}
---

**你正在生成的檔案**：
`{file_path}`

{dom_contract}

**!! 極重要指令 (必須嚴格遵守) !!**
1.  你**只能**生成該頁面的**主要內容**。
2.  **語言**：**必須**使用**繁體中文**生成所有可見文字，**地域**：香港。
3.  你**必須**使用 **Tailwind CSS** 樣式 (例如 `container mx-auto p-8`) 來排版內容。
4.  **使用圖示**：在適當的地方**加入 Font Awesome 圖示** (例如 `<i class="fas fa-gamepad mr-2"></i>`)。
5.  你**必須**使用 `<main>` 標籤包裹所有 HTML 內容 (例如 `<main class="container mx-auto my-12 p-4">...內容...</main>`)。
6.  **ID 建立**：你**必須**為此頁面 `<script>` 需要互動的元素建立**邏輯清晰且唯一**的 `id` (例如 `id="snake-board"`)。
7.  **JavaScript 邏輯 (重要)**：
    * 此頁面 (`{file_path}`) **必須**包含其**專屬**的 JavaScript 邏輯（例如遊戲、互動）。
    * 你**必須**將 JavaScript 程式碼放在 `<main>` 標籤**之後**的 `<script>` 區塊中。
    * **安全規則**：**禁止** `innerHTML`，**必須**使用 `textContent`。
    * **禁止**：**絕對不要**在此處編寫**漢堡選單**的邏輯（`js/script.js` 會處理）。
    * **範例**：
      <main>... (HTML 內容) ...</main>
      <script>
        // (此頁面專用的 JS 邏輯)
        document.addEventListener('DOMContentLoaded', () => {{
          const snakeBoard = document.getElementById('snake-board');
          // ... 遊戲邏輯 ...
        }});
      </script>
8.  **!! 絕對禁止 !!** 在你的回應中包含 `<html>`, `<head>`, `<body>`, `<!DOCTYPE>`, `<nav>` 或 `<footer>` 標籤。
9.  **!! 絕對禁止 !!** AI 若違反規則 #8，將導致整個專案失敗。
10. **僅回傳程式碼**：在回應中只包含 ```html ... ``` 程式碼區塊。

請僅生成 `{file_path}` 的 **<main> 內容** 和 **<script> 內容**：
"""

# PHP生成模板
ADDPAGE_PROMPT_PHP = """
你是一位專業的PHP開發工程師，擅長撰寫現代化的PHP腳本。
請根據以下描述生成符合要求的PHP文件內容。

文件路徑: {file_path}
描述: {description}

參考文件上下文:
{reference_context}

要求:
1. 代碼必須包含完整的PHP標籤 (<?php ... ?>)
2. 遵循PHPPSR規範，語法嚴格正確
3. 包含適當的註釋說明
4. 考慮安全性（如輸入過濾、SQL注入防護等）
5. 所有用戶輸入（$_GET/$_POST等）必須經過過濾：
   - 字符串用htmlspecialchars()防XSS
   - SQL查詢必須使用PDO預處理語句（禁止字符串拼接）
6. 文件操作（如fopen）僅允許操作項目目錄內的文件，並檢查路徑安全性
7. 禁止使用eval()、system()等危險函數，除非有嚴格的輸入驗證
8. 上傳文件必須驗證類型（MIME）和大小，並存儲在非網頁可訪問目錄
9. 僅返回PHP代碼

示例:
<?php
/**
 * 描述：{file_path}的功能說明
 */

// 業務邏輯代碼
echo "Hello, World!";
?>
"""

# ----------------------------------------------------------------------------
# 內部輔助函數
# ----------------------------------------------------------------------------

def _call_deepseek_api(api_key: str, model: str, prompt: str, max_retries: int = 3, timeout: int = 120) -> str:
# ... (_call_deepseek_api 保持不變) ...
    """
    內部函數，用於呼叫 DeepSeek API 並處理重試。
    """
    api_url = "https://api.deepseek.com/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 8192,
        "temperature": 0.1,
        "stream": False
    }

    for attempt in range(1, max_retries + 1):
        try:
            # [!! 更新 !!] 增加 addpage 的超時時間
            current_timeout = timeout
            # [!! 更新 !!] 增加 header chooser 的超時 (雖然它應該很快)
            if "遊戲" in prompt or "game" in prompt or "HEADER_STYLE_CHOOSER_TEMPLATE" in prompt:
                current_timeout = 180 
                 
            response = requests.post(
                api_url, 
                headers=headers, 
                data=json.dumps(payload), 
                timeout=current_timeout # 使用 current_timeout
            )

            if response.status_code == 200:
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                if content:
                    tqdm.write(f"成功從 DeepSeek API 獲取回應 (嘗試 {attempt})")
                    #logger.info(f"\n成功從 DeepSeek API 獲取回應 (嘗試 {attempt})")
                    return content
                else:
                    tqdm.write(f"API 回應格式錯誤或內容為空： {result}")
                    logger.error(f"\nAPI 回應格式錯誤或內容為空： {result}")
                    return "" # 回傳空字串而非 None

            elif response.status_code == 429:
                logger.warning(f"API 速率限制 (429)。第 {attempt}/{max_retries} 次嘗試，等待 5 秒後重試...")
                time.sleep(5)
            
            else:
                logger.error(f"API 請求失敗，狀態碼： {response.status_code}, 回應： {response.text}")
                return "" # 回傳空字串

        except requests.exceptions.Timeout:
            logger.warning(f"API 請求超時 (第 {attempt}/{max_retries} 次嘗試)...")
        
        except requests.exceptions.RequestException as e:
            logger.error(f"API 請求發生網路錯誤： {e} (第 {attempt}/{max_retries} 次嘗試)")
        
        if attempt < max_retries:
            time.sleep(2 ** attempt) # 指數退避

    logger.error(f"達到最大重試次數 ({max_retries})，放棄請求。")
    return "" # 回傳空字號

# ----------------------------------------------------------------------------
# 公開函數 (由 shell.py 呼叫)
# ----------------------------------------------------------------------------

def generate_structure(prompt: str, config: dict) -> str:
# ... (generate_structure 保持不變) ...
    """
    (步驟 1) 呼叫 LLM 僅生成專案的檔案結構。
    """
    api_key = config.get("deepseek_api_key", "")
    model = config.get("model", "deepseek-coder")
    
    if not api_key:
        logger.error("DeepSeek API Key 未在 config.json 中設定。")
        return ""

    full_prompt = STRUCTURE_PROMPT_TEMPLATE.format(user_input=prompt)
    logger.info("呼叫 API 以生成檔案結構...")
    
    response = _call_deepseek_api(api_key, model, full_prompt)
    return response

# [!! 重大更新 !!] generate_file_content 已重構以使用「風格選擇器」
def generate_file_content(
# ... (generate_file_content 保持不變) ...
    description: str, 
    file_path: str, 
    all_files: List[str], 
    config: dict, 
    header_override: Optional[str] = None, 
    footer_override: Optional[str] = None
) -> str:
    """
    (步驟 3) 呼叫 LLM 為單一檔案生成內容。
    """
    api_key = config.get("deepseek_api_key", "")
    # [!!] 區分 'coder' (用於生成) 和 'chat' (用於選擇)
    coder_model = config.get("model", "deepseek-coder")
    chat_model = config.get("chat_model", "deepseek-chat")

    if not api_key:
        logger.error(f"API Key 遺失，無法生成檔案 {file_path}")
        return ""

    file_list_str = "\n".join(all_files)
    full_prompt = "" # 初始化

    # 處理 Header (使用新的動態選擇器邏輯)
    if file_path.endswith(('_header.html', 'header.html')):
        
        # [!!] 邏輯更新：優先使用 header_override，如果為空，再使用通用的 description
        prompt_to_use_for_chooser = header_override if header_override else description
        
        # --- 步驟 1: 呼叫 AI (Chat Model) 選擇風格 ---
        tqdm.write("正在呼叫 AI (Chat Model) 為 Header 選擇風格...")
        chooser_prompt = HEADER_STYLE_CHOOSER_TEMPLATE.format(user_input=prompt_to_use_for_chooser)
        
        # 使用 chat model 進行選擇
        style_choice = _call_deepseek_api(api_key, chat_model, chooser_prompt, timeout=60).strip().replace("`", "")
        
        # 移除潛在的 "V1_CLASSIC_BRIGHT." 結尾句點
        if style_choice.endswith('.'):
            style_choice = style_choice[:-1]
            
        tqdm.write(f"AI 選擇的 Header 風格: [{style_choice}]")

        # --- 步驟 2: 根據風格選擇模板 ---
        template_map = {
            "V1_CLASSIC_BRIGHT": HEADER_PROMPT_V1_CLASSIC_BRIGHT,
            "V2_MODERN_DARK": HEADER_PROMPT_V2_MODERN_DARK,
            "V3_IMAGE_BRANDING": HEADER_PROMPT_V3_IMAGE_BRANDING,
            "V4_MINIMAL_CENTERED": HEADER_PROMPT_V4_MINIMAL_CENTERED
        }
        
        chosen_template = template_map.get(style_choice, HEADER_PROMPT_V1_CLASSIC_BRIGHT)
        
        if style_choice not in template_map:
            logger.warning(f"AI 返回未知風格 '{style_choice}'，將預設使用 V1_CLASSIC_BRIGHT。")
            style_choice = "V1_CLASSIC_BRIGHT (Default)" # 記錄預設行為

        # --- 步驟 3: 格式化最終提示 (使用 Coder Model) ---
        # [!!] 關鍵：這裡的 user_input 是用於 *填充* 模板的，我們使用 chooser 用的同一個
        full_prompt = chosen_template.format(
            file_list_str=file_list_str,
            user_input=prompt_to_use_for_chooser,
            dom_contract=GLOBAL_DOM_CONTRACT
        )
        log_msg = f"呼叫 API (Coder Model, {style_choice} Prompt) 以生成： {file_path}"
        if header_override:
            log_msg += " (使用自訂提示)"
        tqdm.write(log_msg)

    # 處理 Footer
    elif file_path.endswith(('_footer.html', 'footer.html')):
        prompt_to_use = footer_override if footer_override else description
        full_prompt = FOOTER_PROMPT_TEMPLATE.format(
            file_list_str=file_list_str,
            user_input=prompt_to_use
        )
        log_msg = f"呼叫 API (Footer Prompt) 以生成： {file_path}"
        if footer_override:
            log_msg += " (使用自訂提示)"
        tqdm.write(log_msg)

    # 處理 CSS 檔案
    elif file_path.endswith('.css'):
        full_prompt = CSS_PROMPT_TEMPLATE.format(
            user_input=description,
            file_path=file_path
        )
        tqdm.write(f"呼叫 API (CSS Prompt) 以生成： {file_path}")

    # 處理 JS 檔案
    elif file_path.endswith('.js'):
        full_prompt = JS_PROMPT_TEMPLATE.format(
            user_input=description,
            file_path=file_path,
            dom_contract=GLOBAL_DOM_CONTRACT
        )
        tqdm.write(f"呼叫 API (JS Prompt) 以生成： {file_path}")

    # 處理所有其他 .html 頁面
    elif file_path.endswith('.html'):
        full_prompt = PAGE_CONTENT_PROMPT_TEMPLATE.format(
            user_input=description,
            file_path=file_path,
            dom_contract=GLOBAL_DOM_CONTRACT
        )
        tqdm.write(f"呼叫 API (Page Content Prompt) 以生成： {file_path}")

    # 備用
    else:
        logger.warning(f"沒有為 {file_path} 找到特定的 Prompt，將使用通用內容 Prompt。")
        full_prompt = PAGE_CONTENT_PROMPT_TEMPLATE.format(
            user_input=description,
            file_path=file_path,
            dom_contract=GLOBAL_DOM_CONTRACT
        )

    # [!!] 最終呼叫：使用 'coder_model' 和 'full_prompt' 進行生成
    response = _call_deepseek_api(api_key, coder_model, full_prompt)
    return response

# [!! 3. llm_client.py 更新 !!] 新增 reference_context 參數
def edit_file_content(
    file_path: str, 
    original_code: str, 
    edit_prompt: str, 
    config: dict,
    project_structure: Optional[List[str]] = None,
    reference_context: str = "" # [!!] 新增參數
) -> str:
    """
    (步驟 7) 呼叫 LLM 迭代修改一個現有檔案的內容。
    """
    api_key = config.get("deepseek_api_key", "")
    model = config.get("model", "deepseek-coder")

    if not api_key:
        logger.error(f"API Key 遺失，無法編輯檔案 {file_path}")
        return ""

    language = "code"
    if file_path.endswith('.html'):
        language = "html"
    elif file_path.endswith('.js'):
        language = "javascript"
    elif file_path.endswith('.css'):
        language = "css"
    elif file_path.endswith('.php'):
        language = "php"

    # [!! 3. llm_client.py 更新 !!] 準備結構字串
    structure_str = "N/A (僅在編輯 Header/Footer 時提供)"
    if project_structure:
        structure_str = "本專案包含以下檔案：\n" + "\n".join(project_structure)

    # [!!] 確保如果 reference_context 為空，我們傳入 "N/A"
    if not reference_context:
        reference_context = "N/A (使用者未提供 @ 參考檔案)"

    full_prompt = EDIT_FILE_PROMPT_TEMPLATE.format(
        edit_prompt=edit_prompt,
        file_path=file_path,
        original_code=original_code,
        language=language,
        project_structure=structure_str,
        dom_contract=GLOBAL_DOM_CONTRACT,
        reference_context=reference_context # [!!] 傳入 reference_context
    )
    
    logger.info(f"呼叫 API (Edit Prompt) 以修改： {file_path}")
    
    response = _call_deepseek_api(api_key, model, full_prompt)
    return response

def optimize_prompt(
# ... (optimize_prompt 保持不變) ...
    main_description: str,
    header_description: Optional[str],
    footer_description: Optional[str],
    config: dict
) -> str:
    """
    (新增) 呼叫 LLM (Chat) 優化使用者的分散輸入，整合成一個連貫的描述。
    """
    api_key = config.get("deepseek_api_key", "")
    model = config.get("chat_model", "deepseek-chat")
    
    if not api_key:
        logger.error("DeepSeek API Key 未設定，無法優化提示。")
        return "" 

    full_prompt = PROMPT_OPTIMIZATION_TEMPLATE.format(
        main_description=main_description,
        header_description=header_description or "預設導覽列",
        footer_description=footer_description or "預設頁尾"
    )
    
    logger.info(f"呼叫 API ({model}) 以優化提示...")
    
    response = _call_deepseek_api(api_key, model, full_prompt)
    return response.strip() 

# [!! 4. llm_client.py 更新 !!] 新增 reference_context 參數
def generate_addpage_content(
    description: str,
    file_path: str, 
    config: dict,
    reference_context: str = "" # [!!] 新增參數
) -> str:
    """
    (新增) 呼叫 LLM 為 addpage 命令生成內容 (main + script)。
    """
    api_key = config.get("deepseek_api_key", "")
    model = config.get("model", "deepseek-coder") # 使用 coder 模型

    if not api_key:
        logger.error(f"API Key 遺失，無法生成 addpage 內容 {file_path}")
        return ""

    # [!!] 確保如果 reference_context 為空，我們傳入 "N/A"
    if not reference_context:
        reference_context = "N/A (使用者未提供 @ 參考檔案)"

    if file_path.endswith('.php'):
        description = redact_sensitive_info(description)
        full_prompt = ADDPAGE_PROMPT_PHP.format(file_path=file_path,description=description,reference_context=reference_context)
    else:
        full_prompt = ADD_PAGE_PROMPT_TEMPLATE.format(
        user_input=description,
        file_path=file_path,
        dom_contract=GLOBAL_DOM_CONTRACT,
        reference_context=reference_context # [!!] 傳入 reference_context
    )
    
    logger.info(f"呼叫 API (Add Page Prompt) 以生成： {file_path}")
    
    response = _call_deepseek_api(api_key, model, full_prompt) # timeout 邏輯已移至 _call_deepseek_api
    return response

# llm_client.py → 最終安全版 redact_sensitive_info
def redact_sensitive_info(text: str) -> str:
    """最強敏感資訊過濾器 — 保證所有測試通過"""
    if not text:
        return text

    #logger = logging.getLogger(__name__)
    original = text

    # 嚴格優先順序：越精準的規則越前面！
    patterns = [
        # 1. AWS Access Key（20 字元）
        (r'(?i)AKIA[0-9A-Z]{16}', '***AWS_ACCESS_KEY***'),

        # 2. GitHub Token（ghp_ / gho_ / ghs_ / ghu_ / ghr_）
        (r'(?i)gh[po s r]_?[A-Za-z0-9]{35,40}', '***GITHUB_TOKEN***'),

        # 3. GitLab Token
        (r'(?i)glpat-[A-Za-z0-9_-]{20,}', '***GITLAB_TOKEN***'),

        # 4. OpenAI Key（sk- 開頭）
        (r'(?i)sk[-_]?[A-Za-z0-9_-]{40,}', '***OPENAI_KEY***'),

        # 5. 資料庫連接字串（必須在通用密碼規則之前！）
        (r'(?i)(mysql|postgres|mongodb|redis|sqlserver)://[^@\s]+@', r'\1://***:***@'),

        # 6. 通用密碼（關鍵：放在 API key 前面）
        (r'(?i)(pass(?:word)?|pwd|secret|private[-_]?key)\s*[:=]\s*["\']?([^"\']{4,})["\']?', r'password = "***REDACTED***"'),

        # 7. 通用 API key / token（放最後）
        (r'(?i)(api[-_]?key|token|auth[-_]?token|bearer|secret)\s*[:=]\s*["\']?([A-Za-z0-9_-]{8,})["\']?', r'\1 = "***REDACTED***"'),

        # 8. 信用卡號
        (r'\b(?:\d[ -]*?){13,19}\b', '***CARD***'),

        # 9. IP 位址
        (r'\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b', '***IP***'),

        # 10. Email
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', '***@***'),
    ]

    for pattern, repl in patterns:
        text = re.sub(pattern, repl, text)

    if text != original:
        logger.debug("已過濾敏感資訊")

    return text.strip()