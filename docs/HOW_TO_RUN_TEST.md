# 測試啟動：

**執行測試 (Running Tests)**

- **說明**：本專案使用 `pytest` 為測試框架。建議在專案根目錄啟動虛擬環境後再執行測試。
- **在 Windows PowerShell (推薦)**：

```powershell
# 啟用虛擬環境（PowerShell）
.\.venv\Scripts\Activate.ps1

# 若出現執行政策錯誤，暫時放寬當前會話執行政策：
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

# 安裝測試套件（只需第一次）
pip install pytest

# 執行全部測試（簡潔輸出）
python -m pytest -q

# 執行單一測試檔案
python -m pytest tests/test_sync_handler.py -q

# 執行單一測試函式（範例）
python -m pytest tests/test_file_watcher.py::test_on_moved -q

# 詳細輸出
python -m pytest -v
```

- **在 Windows (cmd.exe)**：

```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
pip install pytest
python -m pytest -q
```

- **在 macOS / Linux (bash / zsh)**：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pytest
python3 -m pytest -q
```

- **其他注意事項**：
  - 若要快速安裝開發用套件，可使用 `pip install watchdog`（某些測試或本地即時同步功能會使用 `watchdog`）。
  - 測試檔位於 `tests/`，為了快速迭代可只執行單一檔案或單一測試。
  - 在 CI 中請使用 `python -m pytest -q` 或你偏好的 pytest 參數（例如 `--maxfail=1 -k <pattern>`）。


