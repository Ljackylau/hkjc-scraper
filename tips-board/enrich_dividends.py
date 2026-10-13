"""Enrich published archives from date-validated official all-race dividend pages."""
import argparse,concurrent.futures,json,re,time
from pathlib import Path
from bs4 import BeautifulSoup
from collector import request,parse_dividends,stamp
RAW='https://raw.githubusercontent.com/Ljackylau/hkjc-scraper/tips-data/records/'
def fetch_json(url):
    for attempt in range(3):
        try:return json.loads(request(url))
        except Exception:
            if attempt==2:raise
            time.sleep(2)
def enrich(meta,root):
    name=meta['date']+'.json';path=root/name
    m=json.load(open(path)) if path.exists() else fetch_json(RAW+name+'?t='+str(int(time.time())))
    if all(r.get('result',{}).get('dividends') for r in m['races']):return m['date'],len(m['races'])
    url='https://racing.hkjc.com/zh-hk/local/information/resultsall?Racecourse='+m['venue']+'&racedate='+m['date'].replace('-','/')
    cached=root.parent/(m['date']+'-official.html')
    if not cached.exists():cached.write_text(request(url))
    soup=BeautifulSoup(cached.read_text(),'html.parser');text=soup.get_text(' ',strip=True)
    d=re.search(r'賽事日期\s*[：:]\s*(\d+)/(\d+)/(\d+)',text)
    if not d or f'{int(d[3]):04}-{int(d[2]):02}-{int(d[1]):02}'!=m['date']:raise ValueError('Selected result date mismatch')
    expected={r['race']:r for r in m['races']};checked=set()
    for header in soup.select('div.bg_blue'):
        match=re.fullmatch(r'第\s*(\d+)\s*場',header.get_text(' ',strip=True))
        if not match:continue
        n=int(match[1]);table=header.find_next('table',class_='result');rows=[];withdrawn=[]
        for tr in table.select('tr'):
            c=[x.get_text(' ',strip=True) for x in tr.find_all('td')]
            if len(c)>=3 and re.match(r'^\d+',c[0]) and c[1].isdigit():rows.append(int(c[1]))
            if len(c)>=2 and c[1].isdigit() and ('退出' in c[0] or c[0].upper() in ('WV','WX','WD')):withdrawn.append(int(c[1]))
        if n not in expected or rows[:4]!=[h['no'] for h in expected[n]['result']['horses']]:raise ValueError(f'Official top-four mismatch: {m["date"]} R{n}')
        div=parse_dividends(table.find_next('table',class_='dividends'),require_qp=len(expected[n]['horses'])>=7)
        expected[n]['result'].update(dividends=div,pool_status={k:('settled' if div.get(k) else 'not_offered') for k in ('W','P','Q','QP')},dividend_unit='HKD per $10 stake, including principal',dividends_source=url,dividends_captured_at=stamp(),withdrawn=withdrawn)
        checked.add(n)
        if len(checked)==len(expected):break
    if len(checked)!=len(expected):raise ValueError('Incomplete official meeting')
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n');temp.replace(path)
    return m['date'],len(checked)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--records',type=Path,default=Path(__file__).parent/'_work'/'records');a=p.parse_args();a.records.mkdir(parents=True,exist_ok=True)
    history=fetch_json(RAW+'history.json?t='+str(int(time.time())))
    (a.records/'history.json').write_text(json.dumps(history,ensure_ascii=False,indent=2)+'\n')
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for row in pool.map(lambda m:enrich(m,a.records),history['meetings']):print('Dividends validated:',row,flush=True)
