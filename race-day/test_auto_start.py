import unittest
from datetime import datetime
from unittest.mock import patch
from auto_start import meeting,decision,check,HK

class AutoStartTests(unittest.TestCase):
    def config(self):return meeting([{'race_number':1,'venue':'沙田','post_time':'13:00'},{'race_number':2,'venue':'ST','post_time':'13:30'}],'2026-10-07')
    def at(self,clock):return datetime.fromisoformat('2026-10-07T'+clock+':00').replace(tzinfo=HK)
    def test_start_window_and_no_late_reconstruction(self):
        c=self.config()
        self.assertEqual(decision(c,self.at('10:59'),[]),'too_early')
        self.assertEqual(decision(c,self.at('11:00'),[]),'dispatch')
        self.assertEqual(decision(c,self.at('12:00'),[]),'dispatch')
        self.assertEqual(decision(c,self.at('12:01'),[]),'missed_start_window')
        self.assertEqual(decision(c,self.at('13:00'),[]),'already_started')
        self.assertEqual(decision(None,self.at('11:00'),[]),'no_meeting')
    def test_manual_or_auto_run_blocks_duplicate_even_after_failure(self):
        for status in ['queued','in_progress','completed']:
            run={'display_title':'Race Day 2026-10-07 · Run · ST','status':status,'conclusion':'failure'}
            self.assertEqual(decision(self.config(),self.at('11:00'),[run]),'already_dispatched')
        preflight={'display_title':'Race Day 2026-10-07 · Preflight · ST'}
        other={'display_title':'Race Day 2026-10-06 · Run · ST'}
        self.assertEqual(decision(self.config(),self.at('11:00'),[preflight,other]),'dispatch')
    def test_bad_schedule_fails_closed(self):
        examples=[[],[{'race_number':2,'venue':'ST','post_time':'13:00'}],[{'race_number':1,'venue':'unknown','post_time':'13:00'}],[{'race_number':1,'venue':'ST','post_time':'25:00'}],[{'race_number':1,'venue':'ST','post_time':'13:00'},{'race_number':2,'venue':'HV','post_time':'13:30'}],[{'race_number':1,'venue':'ST','post_time':'13:00'},{'race_number':2,'venue':'ST','post_time':'12:30'}]]
        self.assertIsNone(meeting(examples[0],'2026-10-07'))
        for rows in examples[1:]:
            with self.assertRaises(ValueError):meeting(rows,'2026-10-07')
    @patch('auto_start.notify')
    @patch('auto_start.GitHub')
    @patch('auto_start.get_races')
    def test_dry_run_does_not_dispatch_or_send(self,races,github,notify):
        races.return_value=[{'race_number':1,'venue':'HV','post_time':'13:00'}];github.return_value.runs.return_value=[]
        with patch.dict('os.environ',{'GITHUB_REPOSITORY':'owner/repo','GH_TOKEN':'test-only'}):
            r=check(self.at('11:00'),dry_run=True)
        self.assertEqual(r['status'],'dispatch');github.return_value.dispatch.assert_not_called();notify.assert_not_called()
    @patch('auto_start.notify',side_effect=RuntimeError('notification failed'))
    @patch('auto_start.GitHub')
    @patch('auto_start.get_races')
    def test_notification_failure_never_retries_accepted_dispatch(self,races,github,notify):
        races.return_value=[{'race_number':1,'venue':'HV','post_time':'13:00'}];github.return_value.runs.return_value=[]
        with patch.dict('os.environ',{'GITHUB_REPOSITORY':'owner/repo','GH_TOKEN':'test-only'}):r=check(self.at('11:00'))
        self.assertEqual(r['status'],'dispatch');github.return_value.dispatch.assert_called_once()

if __name__=='__main__':unittest.main()
