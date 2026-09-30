import unittest
from datetime import datetime
from double_shadow import parse, eligible, HK


class DoubleTest(unittest.TestCase):
    def raw(self):
        return {'text':'第 1 場\n沙田, 01/10/2026 13:00\n第 2 場\n沙田, 01/10/2026 13:30',
                'source_text':'更新時間: 01/10/2026 12:56:00',
                'cells':[{'id':f'qb_DBL_{a}_{b}','value':str(a*10+b)} for a in range(1,5) for b in range(1,5)]}
    def test_ordered_pairs(self):
        r=parse(self.raw(),'2026-10-01','ST',1,datetime(2026,10,1,12,56,10,tzinfo=HK))
        self.assertEqual(r['odds']['DBL']['1-2'],'12')
        self.assertEqual(r['odds']['DBL']['2-1'],'21')
        self.assertTrue(r['matrix_complete'])
    def test_wrong_date_rejected(self):
        with self.assertRaisesRegex(ValueError,'identity'):
            parse(self.raw(),'2026-09-27','ST',1,datetime(2026,10,1,12,56,10,tzinfo=HK))
    def test_stale_rejected(self):
        with self.assertRaisesRegex(ValueError,'stale'):
            parse(self.raw(),'2026-10-01','ST',1,datetime(2026,10,1,12,59,tzinfo=HK))
    def test_missing_and_caps_marked(self):
        raw=self.raw();raw['cells'][0]['value']='999';raw['cells'][1]['value']='退出'
        r=parse(raw,'2026-10-01','ST',1,datetime(2026,10,1,12,56,10,tzinfo=HK))
        self.assertEqual(r['capped_cells'],['1-1'])
        self.assertFalse(r['matrix_complete'])
    def test_late_received_snapshot_rejected(self):
        r=parse(self.raw(),'2026-10-01','ST',1,datetime(2026,10,1,12,56,51,tzinfo=HK))
        target=datetime(2026,10,1,13,tzinfo=HK)
        cutoff=datetime(2026,10,1,12,56,50,tzinfo=HK)
        self.assertFalse(eligible(r,cutoff,target))
        r['received_at']='2026-10-01T12:56:49+08:00'
        self.assertTrue(eligible(r,cutoff,target))
        self.assertFalse(eligible(r,cutoff,target.replace(minute=5)))


if __name__=='__main__':unittest.main()
