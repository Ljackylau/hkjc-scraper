"""Prepare public HKJC history before the live deadline, with receipt stamps.

Only numeric earlier race facts and earlier barrier trials are retained. The
2025/26 jockey prior stays frozen to match the research; current rider names
are rechecked against the pre-cutoff live roster by cold_top2_live.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import json
from pathlib import Path
import re
import threading
import time
import urllib.parse
import urllib.request

from lxml import html
from cold_top2_live import jockey_strengths
from runner import now, atomic

ROOT = 'https://racing.hkjc.com'
_pages = {}
_lock = threading.Lock()


def fetch(url):
    with _lock:
        saved = _pages.get(url)
    if saved is not None:
        return saved
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Cache-Control': 'no-cache'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                data = response.read()
            break
        except (OSError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    with _lock:
        _pages[url] = data
    return data


def text(node):
    return ' '.join(node.text_content().split())


def query_id(url, name):
    return next((v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).items()
                 if k.lower() == name.lower()), None)


def parse_card(data, date, venue, number):
    tree = html.fromstring(data)
    for s in tree.xpath('//script|//style'):
        s.drop_tree()
    body = text(tree)
    match = re.search(rf'Race\s+{number}\s*-.*?(Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday),\s*'
                      r'([A-Za-z]+\s+\d{1,2},\s*\d{4}),\s*(Sha Tin|Happy Valley),\s*(\d{1,2}:\d{2})(.*?)(?:Prize Money|Rating:)', body, re.I)
    if not match or datetime.strptime(match[2], '%B %d, %Y').date().isoformat() != date:
        raise ValueError('Racecard date/race identity mismatch')
    reported_venue = 'ST' if match[3].lower() == 'sha tin' else 'HV'
    if reported_venue != venue:
        raise ValueError('Racecard venue mismatch')
    surface = match[5].lower()
    track = 'AWT' if 'all weather' in surface or 'all-weather' in surface else 'TURF' if 'turf' in surface else None
    if not track:
        raise ValueError('Racecard surface unavailable')
    entries = {}
    for row in tree.xpath('//table[contains(concat(" ",normalize-space(@class)," ")," starter ")]//tr'):
        cells = row.xpath('./td')
        if not cells or not text(cells[0]).isdigit():
            continue
        horse_links = row.xpath('.//a[contains(translate(@href,"HORSEID","horseid"),"horseid")]/@href')
        jockey_links = row.xpath('.//a[contains(translate(@href,"JOCKEYID","jockeyid"),"jockeyid")]/@href')
        if not horse_links:
            continue
        h = int(text(cells[0]))
        entries[h] = {'horseid': query_id(horse_links[0], 'horseid'),
                      'jockeyid': query_id(jockey_links[0], 'jockeyid') if jockey_links else None}
    if not entries:
        raise ValueError('Racecard has no declared runners')
    return {'date': date, 'race': number, 'venue': venue, 'track': track,
            'post_time': match[4], 'entries': entries}


def parse_last_run(data, before):
    tree = html.fromstring(data)
    if not tree.xpath('//table[contains(@class,"horseProfile")]'):
        raise ValueError('Horse form page unavailable')
    rows = []
    for row in tree.xpath('//table[contains(@class,"bigborder")]//tr'):
        cells = row.xpath('./td')
        if len(cells) < 5:
            continue
        values = [text(c) for c in cells]
        try:
            day = datetime.strptime(values[2], '%d/%m/%y').date().isoformat()
        except ValueError:
            continue
        if day >= before or not values[1].isdigit():
            continue
        links = row.xpath('.//a[contains(translate(@href,"LOCALRESULTS","localresults"),"localresults")]/@href')
        ctx = values[3].split('/')
        venue = ctx[0].strip()
        track = 'AWT' if any('AWT' in x.upper() for x in ctx[1:]) else 'TURF' if any('TURF' in x.upper() for x in ctx[1:]) else None
        if links and venue in ('ST', 'HV') and track:
            rows.append({'past_date': day, 'past_finish': int(values[1]), 'venue': venue, 'track': track,
                         'result_url': urllib.parse.urljoin(ROOT, links[0])})
    return max(rows, key=lambda r: r['past_date']) if rows else None


def parse_field_size(data):
    tree = html.fromstring(data)
    starters = []
    for row in tree.xpath('//div[contains(@class,"performance")]//tbody/tr'):
        values = [text(c) for c in row.xpath('./td')]
        if len(values) >= 3 and values[1].isdigit() and values[0].upper() not in ('WV', 'WD', 'WITHDRAWN'):
            starters.append(int(values[1]))
    n = len(set(starters))
    if not 2 <= n <= 24:
        raise ValueError('Prior race field size unavailable')
    return n


def parse_trials(data, day):
    tree = html.fromstring(data)
    headings = tree.xpath('//div[contains(@class,"divFLeft") and contains(@class,"general_eng_text")]')
    actual = re.search(r'\d{2}/\d{2}/\d{4}', text(headings[0])) if headings else None
    if not actual or datetime.strptime(actual[0], '%d/%m/%Y').date().isoformat() != day:
        raise ValueError('Barrier trial page date mismatch')
    trials = []
    for bi, table in enumerate(tree.xpath('//table[contains(@class,"bigborder")]')):
        headers = table.xpath('preceding-sibling::table[1]')
        m = re.search(r'Batch\s*(\d+)', text(headers[0])) if headers else None
        batch = m[1] if m else str(bi)
        heat = []
        for row in table.xpath('./tr|./tbody/tr'):
            cells = row.xpath('./td')
            if len(cells) != 10:
                continue
            values = [text(c) for c in cells]
            links = cells[0].xpath('.//a/@href')
            horseid = query_id(links[0], 'horseid') if links else None
            running = re.findall(r'\d+', values[6])
            if not horseid or not running or not re.match(r'\d+\.\d{2}\.\d{2}', values[7]):
                continue
            heat.append({'horseid': horseid, 'trial_date': day, 'batch': batch,
                         'trial_rank': int(running[-1]),
                         'trial_failed': bool(re.search(r'failed|required', values[8], re.I))})
        for trial in heat:
            trial['trial_score'] = 1 - (trial['trial_rank'] - 1) / max(1, len(heat) - 1)
        trials.extend(heat)
    return trials


def load_trials(date):
    landing = html.fromstring(fetch(ROOT + '/en-us/local/information/btresult'))
    days = set()
    today = datetime.fromisoformat(date).date()
    for value in landing.xpath('//select[@id="selectId"]/option/@value'):
        try:
            day = datetime.strptime(value, '%d/%m/%Y').date()
        except ValueError:
            continue
        if 0 < (today - day).days <= 30:
            days.add(day.isoformat())
    if not days:
        raise ValueError('No prior-30-day trial calendar')
    def one(day):
        url = ROOT + '/en-us/local/information/archive/btresult?Date=' + day.replace('-', '%2F')
        return parse_trials(fetch(url), day)
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = [r for group in pool.map(one, sorted(days)) for r in group]
    latest = {}
    for r in sorted(rows, key=lambda r: (r['trial_date'], r['batch'])):
        latest[r['horseid']] = r
    return latest


def load_race(date, venue, number, trials):
    url = (ROOT + '/en-us/local/information/racecard?RaceNo=' + str(number)
           + '&Racecourse=' + venue + '&racedate=' + date.replace('-', '%2F'))
    card = parse_card(fetch(url), date, venue, number)
    strengths = jockey_strengths()
    def one(entry):
        number, runner = entry
        last = parse_last_run(fetch(ROOT + '/en-us/local/information/horse?horseid=' + runner['horseid'] + '&Option=1'), date)
        prior = {'missing_history': True}
        same = None
        if last:
            result_day = query_id(last['result_url'], 'racedate')
            if not result_day or result_day.replace('/', '-') != last['past_date']:
                raise ValueError('Prior result date mismatch')
            prior = {'past_date': last['past_date'], 'past_finish': last['past_finish'],
                     'past_field_size': parse_field_size(fetch(last['result_url']))}
            same = last['venue'] == venue and last['track'] == card['track']
        meta = {'jockey_strength': strengths.get(runner['jockeyid']), 'same_venue_track': same}
        trial = trials.get(runner['horseid'])
        if trial:
            meta.update({k: trial[k] for k in ('trial_date', 'trial_rank', 'trial_score', 'trial_failed')})
        return number, prior, meta
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(one, card['entries'].items()))
    return {'status': 'ready', 'date': date, 'race': number, 'venue': venue, 'track': card['track'],
            'post_time': card['post_time'],
            'prepared_at': now().isoformat(), 'source': 'HKJC pre-race card + strictly earlier races/trials',
            'jockey_prior_season': '2025/26', 'source_url': url,
            'prior_form': {n: p for n, p, m in results}, 'metadata': {n: m for n, p, m in results}}


async def prepare_context(date, venue, number, trials_task, folder, output):
    try:
        trials = await asyncio.shield(trials_task)
        value = await asyncio.to_thread(load_race, date, venue, number, trials)
        output.update(value)
    except Exception as exc:
        output.update(status='unavailable', reason=type(exc).__name__ + ': ' + str(exc)[:160])
    atomic(folder / f'race_{number:02d}_cold_history.json', output)
