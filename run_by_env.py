import os
from datetime import datetime
from hkjc_scraper import scrape_hkjc_multiple_dates, save_to_csv

if __name__ == "__main__":
    base_url = os.getenv(
        "BASE_URL",
        "https://racing.hkjc.com/racing/information/Chinese/Racing/LocalResults.aspx"
    )
    race_dates_env = os.getenv("RACE_DATES", "")
    race_dates = [d.strip() for d in race_dates_env.split(",") if d.strip()] or [
        '2025/09/07',
        '2025/09/10',
        '2025/09/14',
    ]
    print(f"使用日期: {race_dates}")
    data = scrape_hkjc_multiple_dates(base_url, race_dates)
    if data:
        out = f"hkjc_races_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        save_to_csv(data, out)
    else:
        print("未能爬取到任何資料")
