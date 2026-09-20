"""Independent HKJC feasibility check. No predictions or betting actions."""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from dragon_copy import meeting_candidates, HKJC_RACECARD, HKJC_ENTRIES, now


async def probe():
    from playwright.async_api import async_playwright
    report={'source':'HKJC direct','checked_at':datetime.now(timezone.utc).isoformat(),
            'mode':'feasibility_only','ready_for_automatic_fallback':False,'pages':[]}
    async with async_playwright() as p:
        browser=await p.chromium.launch()
        context=await browser.new_context(timezone_id='Asia/Hong_Kong',locale='zh-HK')
        try:
            # Odds feasibility needs meeting identity, not a complete schedule.
            # Check timing separately before any future live collector is enabled.
            landing=await context.new_page()
            candidates=[]
            for url in (HKJC_RACECARD,HKJC_ENTRIES):
                await landing.goto(url,wait_until='domcontentloaded',timeout=25000)
                hrefs=await landing.locator('a').evaluate_all('els => els.map(e => e.href)')
                candidates=meeting_candidates(hrefs,now().date())
                if candidates:break
            await landing.close()
            if not candidates:raise RuntimeError('No official current/future meeting links')
            date,venue=candidates[0]
            meeting={'date':date,'venue':venue,'schedule_validated':False}
            report['meeting']=meeting
            for route in ('wp','qin','qpl'):
                page=await context.new_page()
                url=f"https://bet.hkjc.com/ch/racing/{route}/{meeting['date']}/{meeting['venue']}/1"
                row={'url':url,'route':route}
                try:
                    response=await page.goto(url,wait_until='domcontentloaded',timeout=25000)
                    row['http_status']=response.status if response else None
                    await page.wait_for_function("document.querySelectorAll('[id^=qb_]').length > 0",timeout=15000)
                    row['raw']=await page.evaluate("""() => ({text:document.body.innerText,
                        cells:Array.from(document.querySelectorAll('[id^="qb_"]')).map(e=>({id:e.id,value:e.innerText}))})""")
                    row['odds_elements_found']=len(row['raw']['cells'])
                    row['note']='DOM evidence only; timestamps, pool identities and race identity still require validation'
                except Exception as e:
                    row['error']=str(e)[:500]
                    row['text_excerpt']=(await page.locator('body').inner_text(timeout=3000))[:2000]
                finally:
                    row['received_at']=datetime.now(timezone.utc).isoformat()
                    report['pages'].append(row)
                    await page.close()
        except Exception as e:report['error']=str(e)[:500]
        finally:await browser.close()
    Path('hkjc-probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='pages'},ensure_ascii=False))
    for row in report['pages']:print(row['route'],row.get('odds_elements_found',0),row.get('error',''))


if __name__=='__main__':asyncio.run(probe())
