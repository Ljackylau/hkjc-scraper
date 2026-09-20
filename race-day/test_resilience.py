import asyncio
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch
import runner as r
import resilience


class ResilienceTests(unittest.TestCase):
    def test_valid_live_survives_ticket_failure_and_is_reused(self):
        race={'id':'r6','race_number':6,'post_time':'21:45'}
        date='2026-09-16';target=r.horse.hk_datetime(date,'21:42');clock=[target]
        live={'lockTime':target.isoformat(),'dataQuality':'ready','phase':'locked','candidates':[{'horseNumber':1}]}
        async def sleep(seconds):clock[0]+=timedelta(seconds=seconds)
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);states={}
            def tickets():
                self.assertTrue((folder/'horse103/race_06_live.json').exists())
                raise RuntimeError('tickets offline')
            with patch.object(r,'now',side_effect=lambda:clock[0]),patch.object(r.asyncio,'sleep',side_effect=sleep),patch.object(r.horse,'get_races',return_value=[race]),patch.object(r.horse,'request',return_value=live) as request,patch.object(r.horse,'get_base_race_id',return_value=100),patch.object(r.horse,'get_tickets',side_effect=tickets):
                asyncio.run(r.horse_job(race,date,folder,states,None))
            self.assertEqual(request.call_count,1)
            self.assertEqual(states['6']['status'],'partial')
            self.assertFalse((folder/'horse103/race_06.json').exists())
            saved=json.loads((folder/'horse103/race_06_live.json').read_text())
            self.assertEqual(saved['live_received_at'],target.isoformat())

    def test_archive_roundtrip_excludes_dragon_and_contains_checksums(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'data';r.atomic(root/'2026-09-16/late/horse103/race_06_live.json',{'raw':1})
            r.atomic(root/'2026-09-16/late/dragon/results.json',{'large':True})
            out=Path(tmp)/'backup.zip';manifest=resilience.archive(root,out)
            with zipfile.ZipFile(out) as z:
                self.assertEqual(len(z.namelist()),2)
                for name,digest in manifest['files'].items():
                    self.assertEqual(resilience.hashlib.sha256(z.read(name)).hexdigest(),digest)

    def test_health_outage_is_explicit(self):
        with patch.object(resilience.horse,'get_races',side_effect=RuntimeError('offline')),patch.object(resilience.horse,'rest',side_effect=RuntimeError('offline')):
            result=resilience.health('2026-09-20')
        self.assertFalse(result['ok'])
        self.assertFalse(result['checks']['schedule']['ok'])
