import unittest
from cold_policy import calculate, format_cold

class ColdPartialTests(unittest.TestCase):
    def setUp(self):
        self.tip={'race':2,'freeze':'2026-10-01T13:26:50+08:00','market':[13,9],
                  'runner_rows':[['13','','','','','','Trainer'],['9','','','','','','Missing']]}
        def sample(source,received,odds):
            return {'state':'observed','source_updated_at':f'2026-10-01T{source}+08:00',
                    'received_at':f'2026-10-01T{received}+08:00',
                    'race_context':[{'race_number':1,'post_time':'2026-10-01T13:00:00+08:00'}],
                    'participants':[{'selection_id':'1','name':'Trainer','current_odds':odds}]}
        self.base=sample('12:40:00','12:59:20',100)
        self.end=sample('13:10:00','13:26:40',80)

    def test_one_missing_does_not_cancel_qualifier(self):
        result=calculate(self.tip,[self.base,self.end])
        self.assertEqual(result['cold_status'],'ready')
        self.assertEqual(result['cold'],[13])
        self.assertEqual(result['cold_compared'],[13])
        self.assertEqual(result['cold_missing'][0]['horse'],9)
        self.assertIn('部分資料不足：9號',format_cold(result))

    def test_all_missing_remains_unknown(self):
        self.tip['market']=[9]
        self.assertEqual(calculate(self.tip,[self.base,self.end])['cold_status'],'unavailable')

    def test_group_quote_is_never_assigned_to_individual(self):
        self.end['participants'].append({'name':'其他練馬師','is_other':True,'current_odds':2})
        result=calculate(self.tip,[self.base,self.end])
        self.assertEqual(result['cold'],[13])
        self.assertEqual(result['cold_missing'][0]['horse'],9)

    def test_late_and_closed_samples(self):
        late={**self.end,'received_at':'2026-10-01T13:26:51+08:00','participants':[]}
        self.assertEqual(calculate(self.tip,[self.base,self.end,late])['cold'],[13])
        closed={**self.end,'state':'suspended_or_closed','received_at':'2026-10-01T13:26:45+08:00'}
        self.assertEqual(calculate(self.tip,[self.base,self.end,closed])['cold_status'],'unavailable')

if __name__=='__main__':unittest.main()
