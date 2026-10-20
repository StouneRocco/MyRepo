import datetime as dt
import unittest
from unittest.mock import MagicMock

from flask import Flask
from pymongo.errors import PyMongoError
from temperature_day import day_bounds, daily_frame, interpolate_gaps, load_plans, register_temperature_views


class DailyDataTests(unittest.TestCase):
    def test_plan_n3_matches_projector_ids_and_geometry(self):
        import json
        from temperature_day import ROOT
        catalog = json.loads((ROOT/'shared/plan-n3.json').read_text(encoding="utf-8"))
        self.assertEqual(load_plans()[3]['rooms'], catalog['rooms'])
        self.assertTrue(all(room['code'].startswith('04-') for room in load_plans()[4]['rooms']))

    def test_timezone_and_midnight(self):
        begin, end = day_bounds('2026-01-01')
        self.assertEqual(begin.isoformat(), '2025-12-31T23:00:00+00:00')
        self.assertEqual(end-begin, dt.timedelta(days=1))
        spring, spring_end = day_bounds('2026-03-29')
        self.assertEqual(spring_end-spring, dt.timedelta(hours=23))
        with self.assertRaises(ValueError):
            day_bounds('2026-1-1')

    def test_real_schema_last_value_per_bucket_and_no_database_writes(self):
        collection = MagicMock()
        collection.find.return_value.sort.return_value = [
            {'room': '03-23-N', 'timestamp': dt.datetime(2025,12,31,23,0), 'temperature': 16},
            {'room': '03-23-N', 'timestamp': dt.datetime(2025,12,31,23,4), 'temperature': 17},
            {'room': '03-23-N', 'timestamp': dt.datetime(2025,12,31,23,10), 'temperature': 19},
        ]
        plan = {'floor': 3, 'rooms': [{'id': 'projector-id', 'code': '03-23-N'}]}
        result = daily_frame(collection, plan, '2026-01-01')
        self.assertEqual(result['series']['projector-id'][:3], [17, None, 19])
        self.assertEqual(result['interpolated_series']['projector-id'][:3], [17, 18, 19])
        self.assertEqual(result['estimated']['projector-id'][:3], [False, True, False])
        self.assertEqual(result['counts']['projector-id'], 3)
        self.assertEqual(len(result['series']['projector-id']), 288)
        query = collection.find.call_args.args[0]
        self.assertIn('room', query)
        self.assertIsInstance(query['timestamp']['$gte'], dt.datetime)
        collection.insert_one.assert_not_called()
        collection.update_one.assert_not_called()
        collection.create_index.assert_not_called()

    def test_interpolation_never_extrapolates_or_fills_long_gaps(self):
        filled, estimated = interpolate_gaps([None, 10, None, 12, None])
        self.assertEqual(filled, [None,10,11,12,None])
        self.assertEqual(estimated, [False,False,True,False,False])
        long = [10] + [None]*36 + [12]
        self.assertEqual(interpolate_gaps(long)[0], long)
        self.assertEqual(interpolate_gaps([None]*288), ([None]*288,[False]*288))


class DailyEndpointTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.collection = MagicMock()
        register_temperature_views(self.app, self.collection, lambda fn: fn)
        self.client = self.app.test_client()

    def test_plans_and_invalid_requests(self):
        self.assertEqual([p['floor'] for p in self.client.get('/api/plans').json], [3,4])
        self.assertEqual(self.client.get('/api/days/9').status_code,404)
        self.assertEqual(self.client.get('/api/day/9/2026-01-01').status_code,404)
        self.assertEqual(self.client.get('/api/day/3/invalid').status_code,400)

    def test_days_in_paris_and_database_unavailable(self):
        self.collection.aggregate.return_value = [{'_id':'2026-01-01'}]
        self.assertEqual(self.client.get('/api/days/3').json,['2026-01-01'])
        pipeline=self.collection.aggregate.call_args.args[0]
        self.assertEqual(pipeline[1]['$group']['_id']['$dateToString']['timezone'],'Europe/Paris')
        self.collection.aggregate.side_effect=PyMongoError('unavailable')
        self.assertEqual(self.client.get('/api/days/3').status_code,503)

    def test_day_cache_reads_without_writes(self):
        self.collection.find.return_value.sort.return_value=[]
        first=self.client.get('/api/day/3/2026-01-01')
        second=self.client.get('/api/day/3/2026-01-01')
        self.assertEqual(first.status_code,200)
        self.assertEqual(first.json,second.json)
        self.assertEqual(self.collection.find.call_count,1)
