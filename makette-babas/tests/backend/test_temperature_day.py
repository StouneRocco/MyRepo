"""Données journalières : fuseau de Paris, créneaux de 5 min, interpolation et cache."""
import datetime as dt
import unittest
from unittest.mock import MagicMock, patch

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


class DailyEdgeCaseTests(unittest.TestCase):
    def frame(self, rows, day='2026-01-01'):
        collection = MagicMock()
        collection.find.return_value.sort.return_value = rows
        return daily_frame(collection, {'floor': 3, 'rooms': [{'id': 'r', 'code': '03-23-N'}]}, day)

    def test_autumn_day_lasts_25_hours_without_invalid_slot(self):
        begin, end = day_bounds('2026-10-25')
        self.assertEqual(end - begin, dt.timedelta(hours=25))
        self.assertEqual(self.frame([], '2026-10-25')['invalid_minutes'], [])

    def test_autumn_repeated_hour_shares_one_slot(self):
        # Limite documentée : les deux 02:30 locales tombent dans le même créneau, la dernière gagne.
        frame = self.frame([
            {'room': '03-23-N', 'timestamp': dt.datetime(2026, 10, 25, 0, 30), 'temperature': 20},
            {'room': '03-23-N', 'timestamp': dt.datetime(2026, 10, 25, 1, 30), 'temperature': 21},
        ], '2026-10-25')
        self.assertEqual(frame['series']['r'][30], 21)
        self.assertEqual(frame['counts']['r'], 2)

    def test_invalid_rows_and_unknown_rooms_are_ignored(self):
        utc = dt.timezone.utc
        frame = self.frame([
            {'room': '03-23-N', 'timestamp': dt.datetime(2025, 12, 31, 23, 0, tzinfo=utc), 'temperature': 0},
            {'room': '03-23-N', 'timestamp': dt.datetime(2025, 12, 31, 23, 5), 'temperature': None},
            {'room': '03-23-N', 'timestamp': dt.datetime(2025, 12, 31, 23, 10), 'temperature': float('nan')},
            {'room': '03-23-N', 'timestamp': dt.datetime(2025, 12, 31, 23, 15), 'temperature': '21'},
            {'room': '03-23-N', 'timestamp': dt.datetime(2025, 12, 31, 23, 20)},
            {'room': 'unknown', 'timestamp': dt.datetime(2025, 12, 31, 23, 25), 'temperature': 30},
        ])
        self.assertEqual(frame['series']['r'][:6], [0, None, None, None, None, None])
        self.assertEqual(frame['counts']['r'], 1)
        self.assertEqual(frame['step_minutes'], 5)

    def test_last_slot_of_the_day_is_2355(self):
        frame = self.frame([{'room': '03-23-N', 'timestamp': dt.datetime(2026, 1, 1, 22, 59), 'temperature': 19}])
        self.assertEqual(frame['series']['r'][287], 19)

    def test_gap_limit_is_inclusive_at_180_minutes(self):
        self.assertTrue(all(interpolate_gaps([10] + [None] * 35 + [20])[1][1:36]))
        self.assertFalse(any(interpolate_gaps([10] + [None] * 36 + [20])[1]))

    def test_interpolation_is_linear_and_rounded(self):
        filled, _ = interpolate_gaps([20, None, None, 21])
        self.assertEqual(filled, [20, 20.333, 20.667, 21])

    def test_invalid_slot_breaks_interpolation_on_both_sides(self):
        filled, estimated = interpolate_gaps([10, None, 99, None, 12], valid=[True, True, False, True, True])
        self.assertEqual(filled, [10, None, None, None, 12])
        self.assertFalse(any(estimated))

    def test_plans_have_unique_ids_and_bounds_enclosing_every_room(self):
        for floor, plan in load_plans().items():
            ids = [room['id'] for room in plan['rooms']]
            codes = [room['code'] for room in plan['rooms']]
            self.assertTrue(ids, floor)
            self.assertEqual(len(ids), len(set(ids)), floor)
            self.assertEqual(len(codes), len(set(codes)), floor)
            x, y, width, height = plan['bounds']
            for room in plan['rooms']:
                self.assertGreaterEqual(len(room['points']), 3)
                for px, py in room['points']:
                    self.assertTrue(x <= px <= x + width and y <= py <= y + height, (floor, room['code']))


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
        for day in ('invalid', '2026-02-30', '2026-1-1'):
            self.assertEqual(self.client.get(f'/api/day/3/{day}').status_code,400)
        self.collection.find.assert_not_called()

    def test_days_in_paris_and_database_unavailable(self):
        self.collection.aggregate.return_value = [{'_id':'2026-01-01'}]
        self.assertEqual(self.client.get('/api/days/3').json,['2026-01-01'])
        pipeline=self.collection.aggregate.call_args.args[0]
        self.assertEqual(pipeline[1]['$group']['_id']['$dateToString']['timezone'],'Europe/Paris')
        self.collection.aggregate.side_effect=PyMongoError('unavailable')
        with patch('temperature_day.time.monotonic',return_value=10**12):
            self.assertEqual(self.client.get('/api/days/3').status_code,503)

    def test_day_cache_reads_without_writes(self):
        self.collection.find.return_value.sort.return_value=[]
        first=self.client.get('/api/day/3/2026-01-01')
        second=self.client.get('/api/day/3/2026-01-01')
        self.assertEqual(first.status_code,200)
        self.assertEqual(first.json,second.json)
        self.assertEqual(self.collection.find.call_count,1)


class RegressionDataTests(unittest.TestCase):
    def test_spring_dst_never_interpolates_nonexistent_hours(self):
        plan=load_plans()[3];room=plan['rooms'][0]
        collection=MagicMock()
        collection.find.return_value.sort.return_value=[
            {'room':room['code'],'timestamp':dt.datetime(2026,3,29,0,55),'temperature':20.0},
            {'room':room['code'],'timestamp':dt.datetime(2026,3,29,1,5),'temperature':22.0}]
        frame=daily_frame(collection,plan,'2026-03-29')
        self.assertEqual(len(frame['invalid_minutes']),12)
        self.assertIsNone(frame['interpolated_series'][room['id']][30])
        self.assertFalse(frame['estimated'][room['id']][30])

    def test_day_cache_expires_after_import(self):
        from temperature_day import expiring_cache
        source=MagicMock(side_effect=[1,2])
        cached=expiring_cache(seconds=30)(source)
        with patch('temperature_day.time.monotonic',return_value=0):
            self.assertEqual(cached('day'),1)
            self.assertEqual(cached('day'),1)
        with patch('temperature_day.time.monotonic',return_value=31):
            self.assertEqual(cached('day'),2)
