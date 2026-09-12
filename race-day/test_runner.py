import asyncio,json,sys,tempfile,unittest,subprocess
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import runner as r
import horse103_copy as h
import dragon_copy as d

class Tests(unittest.TestCase):
 def test_formula_and_cutoff(self):
  race={'id':'r','race_number':1};live={'lockTime':'2026-09-09T11:02:00Z','candidates':[{'horseNumber':1,'valueIndex':80},{'horseNumber':2,'valueIndex':60}]}
  entries=[{'horse_number':n,'horses':{'name_tc':str(n)}} for n in [1,2,3]]
  tickets=[{'race_id':101,'bet_type':'QP','scraped_at':'2026-09-09T11:01:59Z','horse_or_combo':'2-3','amount':100}, {'race_id':101,'bet_type':'QP','scraped_at':'2026-09-09T11:02:01Z','horse_or_combo':'1-3','amount':999999}]
  with patch.object(h,'get_entries',return_value=entries):out=h.capture_race(race,'2026-09-09',101,tickets,live_override=live)
  self.assertEqual([x['horse_number'] for x in out['ranking']],[2,1,3]);self.assertEqual(len(out['used_q_and_qp_tickets']),1)
 def test_empty_live_not_valid(self):
  self.assertFalse(r.valid_live({'candidates':[]},{},''))
 def test_wrong_lock_rejected(self):
  v={'candidates':[{}],'dataQuality':'ready','phase':'locked','lockTime':'2026-09-09T11:01:00Z'}
  self.assertFalse(r.valid_live(v,{'post_time':'19:05'},'2026-09-09'))
 def test_late_start_no_network(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(h,'get_base_race_id',side_effect=AssertionError('must not request')):
   states={};asyncio.run(r.horse_job({'race_number':1,'post_time':'01:00'},'2020-01-01',Path(tmp),states,None));self.assertEqual(states['1']['status'],'missed')
 def test_saved_not_overwritten(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'horse103'/'race_01.json';saved={'lock_time':'2020-01-01T00:57:00+08:00','ranking':[],'live103_raw':{'candidates':[]}};r.atomic(p,saved);states={}
   asyncio.run(r.horse_job({'race_number':1,'post_time':'01:00'},'2020-01-01',Path(tmp),states,None));self.assertEqual(json.loads(p.read_text()),saved)
 def test_pair_direction_and_threshold(self):
  result=d.compare({'1-2':'100','2-1':'100'},{'1-2':'70','2-1':'69'},'FCT')
  self.assertEqual([x['pair'] for x in result['pairs']],['2-1'])
 def test_two_publishers_preserve_original_and_each_other(self):
  def git(cwd,*args):return subprocess.run(['git',*args],cwd=cwd,check=True,capture_output=True,text=True).stdout.strip()
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);origin=root/'origin.git';seed=root/'seed';seed.mkdir()
   git(root,'init','--bare',str(origin));git(seed,'init','-b','main');git(seed,'config','user.name','test');git(seed,'config','user.email','test@example.invalid')
   (seed/'original.txt').write_text('untouched');git(seed,'add','.');git(seed,'commit','-m','base');git(seed,'remote','add','origin',str(origin));git(seed,'push','-u','origin','main');base=git(seed,'rev-parse','HEAD')
   one=root/'one';two=root/'two';git(root,'clone','-b','main',str(origin),str(one));git(root,'clone','-b','main',str(origin),str(two))
   with patch.object(r,'REPO',one),patch.object(r,'PUBLISH_ROOT',one):
    r.setup_data_branch();folder=one/'race-day-data'/'2026-09-13'/'early';r.atomic(folder/'status.json',{'early':1});r.publish(folder)
   with patch.object(r,'REPO',two),patch.object(r,'PUBLISH_ROOT',two):
    r.setup_data_branch();folder=two/'race-day-data'/'2026-09-13'/'late';r.atomic(folder/'status.json',{'late':1});r.publish(folder)
   self.assertEqual(git(root,'--git-dir='+str(origin),'rev-parse','main'),base)
   self.assertEqual(git(root,'--git-dir='+str(origin),'show','race-day-data:original.txt'),'untouched')
   self.assertIn('early',git(root,'--git-dir='+str(origin),'show','race-day-data:race-day-data/2026-09-13/early/status.json'))
   self.assertIn('late',git(root,'--git-dir='+str(origin),'show','race-day-data:race-day-data/2026-09-13/late/status.json'))

if __name__=='__main__':unittest.main()
