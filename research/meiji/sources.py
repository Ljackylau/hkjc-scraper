"""Public HKJC fact parsers. Text mentions are evidence flags, not trip ratings."""
import re,urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup

def text(x):return x.get_text(' ',strip=True)
def horse_id(node):
 a=node.select_one('a[href*="horseid="],a[href*="HorseId="]')
 if not a:return None
 return next((v[0] for k,v in urllib.parse.parse_qs(urllib.parse.urlsplit(a['href']).query).items() if k.lower()=='horseid'),None)
def iso(s,fmt='%d/%m/%Y'):return datetime.strptime(s,fmt).date().isoformat()
def date_guard(soup,date,label):
 t=soup.get_text(' ',strip=True)
 expected=datetime.fromisoformat(date).strftime('%d/%m/%Y')
 if not re.search(label+r'\s*[:：]?\s*'+re.escape(expected),t):raise ValueError('Source date mismatch: '+date)

def event_flags(comment,before):
 # Exclude dated veterinary addenda unavailable before the target meeting.
 chunks=re.split(r'(<\s*\d{1,2}/\d{1,2}/\d{4}[^>]*>)',comment);kept=[];available=True
 for chunk in chunks:
  match=re.match(r'<\s*(\d{1,2}/\d{1,2}/\d{4})',chunk)
  if match:available=iso(match[1])<before
  elif available:kept.append(chunk)
 s=' '.join(kept)
 def mention(pattern):
  return int(any(not re.search(r'(?:並無|未有|沒有|並未)\s*$',s[max(0,m.start()-5):m.start()]) for m in re.finditer(pattern,s)))
 return {'blocked':mention('受阻|受困|未能望空|無法望空|勒避|收慢'),
         'wide':mention('外疊|三疊|四疊|沒有遮擋|無遮擋'),
         'slow_start':mention('出閘緩慢|起步緩慢|躍出時失蹄'),
         'over_racing':mention('搶口|昂首|難以穩定'),
         'health':mention('心律不正常|流鼻血|不良於行|喘鳴')}

def parse_reports(body,date,venue):
 soup=BeautifulSoup(body,'html.parser');date_guard(soup,date,'賽事日期');out=[]
 for table in soup.select('table.rirr'):
  heading=table.find_previous_sibling('p');match=re.search(r'第\s*(\d+)\s*場',text(heading) if heading else '')
  if not match:raise ValueError('Report race identity absent')
  for tr in table.select('tbody tr'):
   c=tr.find_all('td',recursive=False)
   if len(c)!=7 or not text(c[1]).isdigit():continue
   ident=horse_id(c[3])
   if ident:out.append({'date':date,'venue':venue,'race':int(match[1]),'no':int(text(c[1])),'horse_id':ident,'comment':text(c[6])})
 if not out:raise ValueError('No report rows')
 return out

def parse_trial(body,date):
 soup=BeautifulSoup(body,'html.parser');date_guard(soup,date,'試閘日期');out=[]
 for batch,table in enumerate(soup.select('table.bigborder'),1):
  heat=[]
  for tr in table.select('tr'):
   c=tr.find_all('td',recursive=False)
   if len(c)!=10:continue
   ident=horse_id(c[0]);running=[int(x) for x in re.findall(r'\d+',text(c[6]))]
   if not ident or not running:continue
   comment=text(c[9]);heat.append({'horse_id':ident,'date':date,'batch':batch,'rank':running[-1],'positive':int(bool(re.search('未催策|無須催策|輕鬆|收韁|緊韁|從容|有餘未盡|反應良好',comment))),'negative':int(bool(re.search('催策無反應|疲態|力弱|追勢平平|反應一般',comment))),'failed':int(bool(re.search('不及格|未及格|須再試|failed',text(c[8]),re.I)))})
  for h in heat:h['field']=len(heat)
  out.extend(heat)
 if not out:raise ValueError('No trial rows')
 return out

def parse_results(body,date,venue,race):
 soup=BeautifulSoup(body,'html.parser');table=soup.select_one('table.draggable')
 if not table:raise ValueError('No official results table')
 # The selected race tab, date heading and venue must agree with the requested identity.
 page=soup.get_text(' ',strip=True);date_guard(soup,date,'賽事日期')
 title=soup.select_one('.race_tab .on')
 if title and re.search(r'\d+',text(title)) and int(re.search(r'\d+',text(title))[0])!=race:raise ValueError('Result race mismatch')
 headers=[re.sub(r'\s','',text(c)) for c in table.select('thead tr')[-1].find_all(['td','th'])]
 def col(label):
  return next((i for i,x in enumerate(headers) if label in x),None)
 run=col('沿途');draw=col('檔位');rating=None
 if run is None or draw is None:raise ValueError('Result running-position/draw columns absent')
 out=[]
 for tr in table.select('tbody tr'):
  c=tr.find_all('td',recursive=False)
  if len(c)<=max(run,draw) or not text(c[1]).isdigit() or not re.match(r'^\d+',text(c[0])):continue
  ident=horse_id(c[2]);positions=[int(x) for x in re.findall(r'\d+',text(c[run]))]
  if not ident:raise ValueError('Result horse identity absent')
  out.append({'date':date,'venue':venue,'race':race,'horse_id':ident,'no':int(text(c[1])),'finish':int(re.match(r'^\d+',text(c[0]))[0]),'draw':int(text(c[draw])),'positions':positions})
 if not out:raise ValueError('No actual starters')
 for h in out:h['field']=len(out)
 return out

def normalize_report(row):
 from datetime import timedelta
 chunks=re.split(r'(<\s*\d{1,2}/\d{1,2}/\d{4}[^>]*>)',row['comment']);available=(datetime.fromisoformat(row['date']).date()+timedelta(days=1)).isoformat();versions=[]
 for chunk in chunks:
  m=re.match(r'<\s*(\d{1,2}/\d{1,2}/\d{4})',chunk)
  if m:available=iso(m[1])
  elif chunk.strip():versions.append({'available_date':available,'flags':event_flags(chunk,'9999-12-31')})
 return {k:v for k,v in row.items() if k!='comment'}|{'versions':versions}
