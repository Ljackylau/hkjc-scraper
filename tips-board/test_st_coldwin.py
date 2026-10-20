import copy,unittest
from datetime import datetime
from st_coldwin import parse_authors,parse_form,collect,AUTHORS

class ColdWinTests(unittest.TestCase):
    def test_authors_date_and_four_picks_are_validated(self):
        body='賽事日期：21/10/2026 '+''.join(a+'貼士 第1場 1甲馬 2乙馬 3丙馬 4丁馬 ' for a in AUTHORS)
        self.assertEqual(parse_authors(body,'2026-10-21')[AUTHORS[0]][1][0]['no'],1)
        with self.assertRaises(ValueError):parse_authors(body,'2026-10-20')
        with self.assertRaises(ValueError):parse_authors(body.replace('4丁馬',''),'2026-10-21')

    def test_profile_target_and_future_results_cannot_change_features(self):
        def row(day,finish,positions):
            cells=['1',str(finish),day,'沙田 草地','1200','好','4','1','50','練','騎','1','1','120',positions,'1','1','1']
            return '<tr>'+''.join('<td>'+s+'</td>' for s in cells)+'</tr>'
        def markup(rows):return '<table class="horseProfile">馬甲 (L001)</table><table class="bigborder"><tr><th>實際負磅 沿途走位</th></tr>'+rows+'</table>'
        past=row('01/10/2026',3,'9 5 3')+row('01/09/2026',5,'5 5 5')+row('01/07/2026',2,'7 4 2')
        base=parse_form(markup(past),'HK_2025_L001','2026-10-21')
        polluted=parse_form(markup(row('21/10/2026',1,'1 1 1')+row('22/10/2026',1,'1 1 1')+past),'HK_2025_L001','2026-10-21')
        self.assertEqual(base,polluted);self.assertEqual(base['median'],7);self.assertEqual(base['last_finish'],3)
        with self.assertRaises(ValueError):parse_form(markup(past),'HK_2025_L002','2026-10-21')

    def test_collect_never_reads_started_locked_or_hv_races(self):
        t=datetime.fromisoformat('2026-10-21T12:00:00+08:00')
        def forbidden(*args):raise AssertionError('unexpected request')
        m={'date':'2026-10-21','venue':'ST','races':[{'race':1,'track':'TURF','off':'2026-10-21T11:00:00+08:00'},{'race':2,'track':'TURF','off':'2026-10-21T13:00:00+08:00','locked':True}]}
        original=copy.deepcopy(m);collect(m,forbidden,lambda:t.isoformat(),lambda:t,lambda h,r:h);self.assertEqual(m,original)
        m['venue']='HV';collect(m,forbidden,lambda:t.isoformat(),lambda:t,lambda h,r:h)

if __name__=='__main__':unittest.main()
