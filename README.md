# HKJC Scraper (Selenium)

此專案以 Selenium + BeautifulSoup 爬取香港賽馬會賽事結果，輸出 CSV。
請確保遵守目標網站的使用條款，僅於合法與合規的情境使用。

## 兩種執行方式

### A. GitHub Codespaces（互動執行）
1. 進入本 repo，點擊綠色按鈕 Code → Create codespace on main
2. 等待 Codespace 建好（會自動安裝 Python/Chrome/套件）
3. 在下方 Terminal 輸入：

python hkjc_scraper.py


產生的 CSV 會出現在工作目錄

### B. GitHub Actions（一鍵雲端跑）
1. 進入本 repo → Actions → Run HKJC Scraper
2. 點 Run workflow，可輸入 `race_dates`（以逗號分隔），若留空則用程式預設
3. 執行完後，在該工作流程頁面「Artifacts」下載 CSV

## 環境需求（如本地端執行）
- Python 3.11+
- Google Chrome（Headless 可）
- `pip install -r requirements.txt`
