import copy,unittest
from features import build,BASE,EXTRA
from sources import event_flags,normalize_report,parse_trial,parse_results
from model import ordered,train
from build_inputs import parse_summary
class Cutoffs(unittest.TestCase):
 def setUp(self):
  self.card={'date':'2026-10-19','venue':'ST','distance':1200,'track':'TURF','horses':[{'no':1,'horse_id':'H1','jockey_id':'J1','rating':50,'X':[0.]*len(BASE)}]}
  self.past={'date':'2026-10-11','venue':'ST','distance':1200,'track':'TURF','horse_id':'H1','jockey_id':'J1','rating':52,'finish':2,'positions':[8,7,2],'field':12}
 def test_same_day_future_results_and_trials_do_not_change_features(self):
  a=build(self.card,[self.past],[],[])
  b=build(self.card,[self.past,{**self.past,'date':'2026-10-19','finish':1},{**self.past,'date':'2026-10-21','finish':1}],[{'horse_id':'H1','date':'2026-10-19','batch':1,'rank':1,'field':4,'positive':1,'negative':0,'failed':0}],[])
  self.assertEqual(a,b)
 def test_unknown_is_explicit_and_not_positive_trial(self):
  h=build(self.card,[],[],[])[0];d=dict(zip(BASE+EXTRA,h['X_enhanced']))
  self.assertEqual(d['history_missing'],1);self.assertEqual(d['style_missing'],1);self.assertEqual(d['trip_missing'],1);self.assertEqual(d['trial_missing'],1);self.assertEqual(d['trial_positive'],0)
 def test_own_current_draw_is_not_used_as_running_style(self):
  h=build(self.card,[self.past],[],[])[0];self.assertEqual(h['evidence']['running_style'],'closer');self.assertEqual(h['evidence']['distance_starts'],1)
 def test_dated_future_veterinary_addendum_excluded(self):
  s='直路受困。<20/10/2026 獸醫報告增補>發現心律不正常。'
  self.assertEqual(event_flags(s,'2026-10-19')['health'],0);self.assertEqual(event_flags(s,'2026-10-21')['health'],1)
  row=normalize_report({'date':'2026-10-11','horse_id':'H1','comment':s});h=build(self.card,[self.past],[],[row])[0]
  self.assertEqual(h['evidence']['report_flags']['health'],0);self.assertEqual(h['evidence']['report_flags']['blocked'],1)
 def test_negative_phrase_not_health_or_blocked_signal(self):
  self.assertEqual(event_flags('沒有受阻，並無心律不正常。','2026-10-19')['blocked'],0);self.assertEqual(event_flags('沒有受阻，並無心律不正常。','2026-10-19')['health'],0)
 def test_trial_after_target_not_used_and_previous_quality_is_retained(self):
  t={'horse_id':'H1','date':'2026-10-16','batch':1,'rank':4,'field':7,'positive':1,'negative':0,'failed':0}
  h=build(self.card,[self.past],[t],[])[0];self.assertEqual(h['evidence']['trial']['positive'],1);self.assertEqual(h['evidence']['trial']['rank'],4)
 def test_date_mismatched_trial_fails(self):
  with self.assertRaises(ValueError):parse_trial('<div>試閘日期:20/10/2026</div>','2026-10-16')
 def test_missing_official_running_positions_column_fails(self):
  with self.assertRaises(ValueError):parse_results('<div>賽事日期:14/10/2026</div><table class="draggable"><thead><tr><td>馬號</td></tr></thead></table>','2026-10-14','HV',2)
 def test_dead_heat_is_an_actual_starter_and_top_three_finish(self):
  body='<div>賽事日期:11/10/2026</div><table class="draggable"><thead><tr><td>名次</td><td>馬號</td><td>馬名</td><td>檔位</td><td>沿途走位</td></tr></thead><tbody><tr><td>2 平頭馬</td><td>7</td><td><a href="/horse?horseid=H1">甲</a></td><td>2</td><td>4 3 2</td></tr></tbody></table>'
  r=parse_results(body,'2026-10-11','ST',6);self.assertEqual(r[0]['finish'],2);self.assertEqual(r[0]['field'],1)
 def test_reserve_numbers_cannot_replace_declared_horses(self):
  card={**self.card,'race':1};html='<table id="PastRacingIncidentExt"><tr><td>1</td><td>H1</td><td><a href="/horse?horseid=H1">甲</a></td><td>11/10/2026</td><td>88</td><td>受困</td></tr><tr><td colspan="6">後備馬匹</td></tr><tr><td>1</td><td>OTHER</td><td><a href="/horse?horseid=OTHER">乙</a></td><td>11/10/2026</td><td>88</td><td>受困</td></tr></table>'
  rows=parse_summary(html,card);self.assertEqual(len(rows),1);self.assertEqual(rows[0]['horse_id'],'H1')
 def test_current_labels_are_not_feature_inputs(self):
  a=build(self.card,[self.past],[],[]);c=copy.deepcopy(self.card);c['labels']={'1':{'win':1,'place':1,'M1':1}};self.assertEqual(a,build(c,[self.past],[],[]))
if __name__=='__main__':unittest.main()
