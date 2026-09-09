import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright

class LiveChartTest(unittest.TestCase):
    def test_refresh_snapshot_and_reopen(self):
        with sync_playwright() as p:
            browser=p.chromium.launch()
            page=browser.new_page()
            errors=[]
            page.on('pageerror',lambda e: errors.append(str(e)))
            data={'date':'2099-09-09','venue':'HV','published_at':'2099-09-09T20:00:00+08:00','races':[{'race':7,'off_time':'22:15','status':'收集中','horse_numbers':[1,2,3],'pools':[]}]}
            page.route('https://raw.githubusercontent.com/**',lambda route:route.fulfill(json=data,headers={'access-control-allow-origin':'*'}))
            target=Path(__file__).with_name('chart.html')
            if not target.exists(): target=Path(__file__).with_name('live.html')
            page.goto(target.as_uri())
            page.evaluate('localStorage.clear()'); page.reload()
            page.wait_for_selector('.race')
            data['published_at']='2099-09-09T20:01:00+08:00'
            data['races'][0]['pools']=[{'pool':'FCT','compared_pairs':6,'baseline_time':'2099-09-09T20:00:00+08:00','final_time':'2099-09-09T20:01:00+08:00','source_updated':'2099-09-09T20:01:00+08:00','fresh':True,'current_odds':{'1-2':'10'},'horses':[{'horse':1,'count':2,'avg_drop_pct':45},{'horse':2,'count':1,'avg_drop_pct':40},{'horse':3,'count':1,'avg_drop_pct':35}]}]
            page.evaluate('tick()')
            page.wait_for_selector('circle')
            page.get_by_text('保存 T−10 快照').click()
            self.assertIn('1號 45.00%',page.locator('#app').inner_text())
            page.reload(); page.wait_for_selector('.race')
            self.assertIn('1號 45.00%',page.locator('#app').inner_text())
            self.assertIn('FCT',page.locator('#app').inner_text())
            self.assertNotIn('QIN',page.locator('#app').inner_text())
            self.assertEqual(errors,[])
            browser.close()
