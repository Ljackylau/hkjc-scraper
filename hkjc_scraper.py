import re
import time
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from collections import Counter

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By  # 注意小寫 by
from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC  # 未使用可移除
from webdriver_manager.chrome import ChromeDriverManager


def build_url_with_params(base_url: str, **params) -> str:
    """以安全方式替換或新增 URL 上的查詢參數"""
    u = urlparse(base_url)
    q = parse_qs(u.query)
    for k, v in params.items():
        q[k] = [v]
    new_query = urlencode(q, doseq=True)
    return urlunparse((u.scheme, u.netloc, u.path, u.params, new_query, u.fragment))


def get_soup(driver) -> BeautifulSoup:
    """回傳當前頁面 BeautifulSoup 物件"""
    html = driver.page_source
    return BeautifulSoup(html, 'html.parser')


def wait_for_page(driver, timeout=15):
    """避免使用舊版沒有的 EC.any_of，用 lambda 等待穩定區塊"""
    WebDriverWait(driver, timeout).until(
        lambda d: d.find_elements(By.CSS_SELECTOR, "table.table_bd")
        or d.find_elements(By.CSS_SELECTOR, "td.f_fs13")
    )


def extract_venue(soup: BeautifulSoup) -> str:
    """
    從頁面判斷會期場地（沙田/跑馬地）
    策略：掃描頁面文字出現頻率，回傳最常出現者
    """
    venue_candidates = []
    for txt in soup.stripped_strings:
        if '沙田' in txt:
            venue_candidates.append('沙田')
        if '跑馬地' in txt:
            venue_candidates.append('跑馬地')
    if venue_candidates:
        c = Counter(venue_candidates)
        return c.most_common(1)[0][0]
    return ''


def normalize_class(text: str) -> str | None:
    """
    正規化級別為「第X班」
    支援：第5班 / 第 五 班 / 第五班 / 第 5 班
    若找不到「第X班」則回傳 None
    """
    if not text:
        return None
    m = re.search(r'第\s*([一二三四五六七八九十百千0-9]+)\s*班', text)
    if m:
        num = m.group(1)
        return f'第{num}班'
    return None


def extract_class_and_distance_parts(soup: BeautifulSoup) -> tuple[str, str]:
    """
    回傳 (級別, 距離)
    - 級別：只回傳「第X班」形態，找不到就空字串
    - 距離：回傳「XXXX米」，找不到就空字串
    優先於 header 區塊（f_fs12/f_fs13）內找；找不到再全頁搜尋。
    """
    pattern_dist = re.compile(r'(\d{3,4})\s*米')

    def scan_elements(selectors):
        cls_out, dist_out = '', ''
        for el in soup.select(selectors):
            txt = el.get_text(" ", strip=True)
            if not txt:
                continue
            # 去掉賽事編號 (H196) 類型雜訊
            txt_clean = re.sub(r'KATEX_INLINE_OPEN[A-Z]\d+KATEX_INLINE_CLOSE', '', txt)
            # 距離
            md = pattern_dist.search(txt_clean)
            if md and not dist_out:
                dist_out = f"{md.group(1)}米"
            # 級別（第X班）
            mc = normalize_class(txt_clean)
            if mc and not cls_out:
                cls_out = mc
            if cls_out and dist_out:
                return cls_out, dist_out
        return cls_out, dist_out

    # 1) 先掃 header 區塊
    cls1, dist1 = scan_elements('td.f_fs12, td.f_fs13, div.f_fs12, span.f_fs12')
    if cls1 or dist1:
        return cls1 or '', dist1 or ''

    # 2) 次要：全頁掃描
    cls2, dist2 = scan_elements('td, div, span, p')
    return cls2 or '', dist2 or ''


def parse_time_list(soup: BeautifulSoup, label_text: str) -> list:
    """
    從指定標籤行（例如「時間」）擷取多個時間，回傳 list
    僅保留時間，不處理「分段時間」
    """
    def label_matcher(s):
        return isinstance(s, str) and (label_text in s)

    cell = soup.find('td', string=label_matcher)
    times = []
    if cell:
        tds = cell.parent.find_all('td')
        for td in tds[1:]:
            text = td.get_text(" ", strip=True)
            tokens = re.findall(r'\d{1,2}[:：]\d{2}\.?\d*|\d{1,2}\.\d{2}', text)
            if tokens:
                times.extend(tokens)
            else:
                if text:
                    times.append(text)
    times = [t.strip() for t in times if t and t.strip()]
    return times


def split_running_positions(raw: str, field_size: int | None) -> list:
    """
    沿途走位拆解：
      - 若有分隔符（- / 空白 / → 等）直接 split
      - 若為連續數字（如 4441 或 1110103），用「最多出賽匹數」判斷：
          優先切兩位數（10~field_size/19），否則取一位數
    """
    if not raw:
        return []
    # 標準分隔
    if re.search(r'[-–—－→> ]', raw):
        parts = re.split(r'[-–—－→>\s]+', raw.strip())
        return [p for p in parts if p]

    s = re.sub(r'\D', '', raw)  # 只留數字
    if not s:
        return []

    max_two_digit = field_size if (field_size and field_size >= 10) else 19
    max_two_digit = min(max_two_digit, 19)

    i, out = 0, []
    while i < len(s):
        # 優先取兩位數（10~max_two_digit）
        if i + 1 < len(s):
            two = int(s[i:i+2])
            if 10 <= two <= max_two_digit:
                out.append(str(two))
                i += 2
                continue
        # 取一位數
        out.append(s[i])
        i += 1
    return out


def scrape_single_race(driver, race_num):
    """爬取單場賽事"""
    try:
        current_url = driver.current_url
        race_url = build_url_with_params(current_url, RaceNo=str(race_num))
        driver.get(race_url)

        # 舊版相容：不用 EC.url_contains
        WebDriverWait(driver, 10).until(lambda d: f"RaceNo={race_num}" in d.current_url)
        wait_for_page(driver, timeout=15)

        soup = get_soup(driver)

        race_info = {}
        race_info['場次'] = f"第 {race_num} 場"

        # 級別 / 距離
        cls, dist = extract_class_and_distance_parts(soup)
        race_info['級別'] = cls
        race_info['距離'] = dist

        # 場地狀況
        track_condition = soup.find('td', string=re.compile('場地狀況'))
        if track_condition:
            next_td = track_condition.find_next_sibling('td')
            if next_td:
                race_info['場地狀況'] = next_td.get_text(strip=True)

        # 賽道
        track_type = soup.find('td', string=re.compile('賽道'))
        if track_type:
            next_td = track_type.find_next_sibling('td')
            if next_td:
                race_info['賽道'] = next_td.get_text(strip=True)

        # 只保留「時間」多欄位（不處理分段時間）
        race_info['時間_list'] = parse_time_list(soup, '時間')

        # 賽事結果表格
        results_list = []
        results_table = soup.select_one('table.table_bd')
        field_size = 0
        if results_table:
            rows = results_table.find_all('tr')
            headers = []
            if rows:
                header_cells = rows[0].find_all(['th', 'td'])
                headers = [h.get_text(strip=True) for h in header_cells]

            # 初步計數，估算該場匹數（排除空行）
            data_rows = []
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                if not cells or len(cells) <= 1:
                    continue
                if any(c.get_text(strip=True) for c in cells):
                    data_rows.append(row)
            field_size = len(data_rows)

            for row in data_rows:
                cells = row.find_all(['td', 'th'])
                row_data = {}
                for i, cell in enumerate(cells):
                    key = headers[i] if i < len(headers) else f"欄位{i+1}"
                    row_data[key] = cell.get_text(strip=True)
                if any(v for v in row_data.values()):
                    results_list.append(row_data)

        race_info['賽果數據'] = results_list
        race_info['field_size'] = field_size  # 提供給上層拆沿途走位使用

        return race_info

    except Exception as e:
        print(f"爬取第 {race_num} 場賽事時發生錯誤: {str(e)}")
        return None


def scrape_hkjc_multiple_dates(base_url, race_dates):
    """爬取多個日期的香港賽馬會賽事結果"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    all_races_data = []

    try:
        for date_str in race_dates:
            print(f"\n開始爬取日期: {date_str}")

            url = build_url_with_params(base_url, RaceDate=date_str)
            driver.get(url)
            wait_for_page(driver, timeout=15)
            time.sleep(1.0)

            soup = get_soup(driver)

            meeting_venue = extract_venue(soup) or ''

            # 找出該日有多少場賽事
            link_elems = driver.find_elements(By.XPATH, "//a[contains(@href,'RaceNo=')]")
            race_nos = []
            for e in link_elems:
                href = e.get_attribute('href') or ''
                m = re.search(r'RaceNo=(\d+)', href)
                if m:
                    race_nos.append(int(m.group(1)))
            num_races = max(race_nos) if race_nos else 0
            print(f"找到 {num_races} 場賽事")

            if num_races == 0:
                print(f"日期 {date_str} 沒有找到賽事或頁面格式異動")
                continue

            # 逐場爬取
            for race_num in range(1, num_races + 1):
                print(f"  爬取第 {race_num} 場...")
                race_data = scrape_single_race(driver, race_num)

                if race_data:
                    field_size = race_data.get('field_size') or (
                        len(race_data.get('賽果數據', [])) if race_data.get('賽果數據') else None
                    )

                    if race_data.get('賽果數據'):
                        for result in race_data['賽果數據']:
                            record = {
                                '賽事日期': date_str,
                                '日期地點': meeting_venue,
                                '場次': race_data.get('場次', ''),
                                '級別': race_data.get('級別', ''),
                                '距離': race_data.get('距離', ''),
                                '場地狀況': race_data.get('場地狀況', ''),
                                '賽道': race_data.get('賽道', '')
                            }

                            # 加入「時間_1..n」
                            for i, t in enumerate(race_data.get('時間_list', []), 1):
                                record[f'時間_{i}'] = t

                            # 拆沿途走位（支援 4441 / 1110103）
                            result_clean = dict(result)
                            rp_key = next((k for k in result_clean.keys() if '沿途' in k or '走位' in k or '步程' in k), None)
                            if rp_key and result_clean.get(rp_key):
                                rp_text = result_clean.pop(rp_key)
                                rp_parts = split_running_positions(rp_text, field_size)
                                for i, p in enumerate(rp_parts, 1):
                                    record[f'沿途走位_{i}'] = p

                            # 其餘欄位照常加入
                            for k, v in result_clean.items():
                                record[k] = v

                            all_races_data.append(record)
                    else:
                        record = {
                            '賽事日期': date_str,
                            '日期地點': meeting_venue,
                            '場次': race_data.get('場次', ''),
                            '級別': race_data.get('級別', ''),
                            '距離': race_data.get('距離', ''),
                            '場地狀況': race_data.get('場地狀況', ''),
                            '賽道': race_data.get('賽道', '')
                        }
                        for i, t in enumerate(race_data.get('時間_list', []), 1):
                            record[f'時間_{i}'] = t
                        all_races_data.append(record)

                time.sleep(0.8)

            print(f"完成爬取日期: {date_str}")
            time.sleep(0.8)

    except Exception as e:
        print(f"爬取過程中發生錯誤: {str(e)}")

    finally:
        driver.quit()

    return all_races_data


def save_to_csv(data, filename='hkjc_race_results.csv'):
    """將爬取的資料保存為CSV檔案，增加「頭馬距離」並調整次序"""
    if not data:
        print("沒有資料可保存")
        return

    df = pd.DataFrame(data)

    # ----------- 基礎欄位 ----------- #
    base_columns = ['賽事日期', '日期地點', '場次', '級別', '距離', '場地狀況', '賽道']
    all_columns = df.columns.tolist()

    # 動態排序：時間_*、沿途走位_*
    def sort_by_index(prefix):
        cols = [c for c in all_columns if re.match(rf'^{prefix}_(\d+)$', c)]
        cols_sorted = sorted(cols, key=lambda x: int(re.search(r'(\d+)$', x).group(1)))
        for c in cols_sorted:
            all_columns.remove(c)
        return cols_sorted

    time_cols = sort_by_index('時間')
    rp_cols = sort_by_index('沿途走位')

    # 先放入基礎欄位
    ordered_columns = []
    for col in base_columns:
        if col in all_columns:
            ordered_columns.append(col)
            all_columns.remove(col)

    ordered_columns.extend(time_cols)
    ordered_columns.extend(rp_cols)

    # ----------- 特殊要求：調整「頭馬距離」位置 ----------- #
    # 如果賽果數據裡有「檔位」「頭馬距離」「完成時間」等欄位
    if '檔位' in all_columns and '完成時間' in all_columns:
        # 先插檔位
        ordered_columns.append('檔位')
        all_columns.remove('檔位')

        # 如果有頭馬距離，放在檔位之後
        if '頭馬距離' in all_columns:
            ordered_columns.append('頭馬距離')
            all_columns.remove('頭馬距離')

        # 接著放完成時間
        ordered_columns.append('完成時間')
        all_columns.remove('完成時間')

    # 其他剩下的欄位
    ordered_columns.extend(all_columns)

    # ----------- 輸出 ----------- #
    df = df[ordered_columns]
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"\n資料已成功保存到 {filename}")
    print(f"總共保存了 {len(df)} 筆記錄")


# 主程式
if __name__ == "__main__":
    base_url = "https://racing.hkjc.com/racing/information/Chinese/Racing/LocalResults.aspx"
    race_dates = [
        '2025/09/07',
        '2025/09/10',
        '2025/09/14',
]

    print("=" * 50)
    print("香港賽馬會賽事結果爬蟲")
    print("=" * 50)
    print(f"基礎URL: {base_url}")
    print(f"爬取日期: {', '.join(race_dates)}")
    print("=" * 50)

    start_time = datetime.now()
    print(f"\n開始時間: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    all_data = scrape_hkjc_multiple_dates(base_url, race_dates)

    if all_data:
        output_filename = f"hkjc_races_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        save_to_csv(all_data, output_filename)
    else:
        print("未能爬取到任何資料")

    end_time = datetime.now()
    duration = end_time - start_time
    print(f"\n結束時間: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"總執行時間: {duration}")

    print("\n爬取完成!")
