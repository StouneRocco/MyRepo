"""API Flask : lecture des températures instantanées et de la plage disponible."""
import datetime as dt
import unittest
from unittest.mock import MagicMock, patch

from .support import bearer, load_app

UTC = dt.timezone.utc


class TemperatureApiTests(unittest.TestCase):
    def setUp(self):
        self.app = load_app()
        self.client = self.app.app.test_client()
        self.headers = bearer(self.app)
        self.collection = MagicMock()
        for patcher in (patch.object(self.app.users, 'find_one', return_value={'username': 'test'}),
                        patch.object(self.app, 'temperatures', self.collection)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def read(self, timestamp):
        return self.client.get('/api/temperatures', query_string={'timestamp': timestamp}, headers=self.headers)

    def test_read_routes_require_authentication(self):
        for path in ('/api/temperatures', '/api/temperatures/range', '/api/plans', '/api/days/3',
                     '/api/day/3/2026-01-01', '/api/badgeages/days/3', '/api/badgeages/day/3/2026-03-02'):
            with self.subTest(path):
                self.assertEqual(self.client.get(path).status_code, 401)

    def test_timestamp_must_be_iso_with_timezone(self):
        for timestamp in ('', 'bad', '2026-01-01T00:00:00', '2026-13-01T00:00:00Z', '9999-12-31T23:59:59+00:00'):
            with self.subTest(timestamp):
                self.assertEqual(self.read(timestamp).status_code, 400)
        self.collection.aggregate.assert_not_called()

    def test_closest_measurement_per_room_within_ten_minutes(self):
        self.collection.aggregate.return_value = [{'_id': '03-23-N', 'temperature': 16.08},
                                                  {'_id': '03-24-N', 'temperature': 0}]
        response = self.read('2026-06-30T14:00:00+02:00')
        self.assertEqual(response.json, {'03-23-N': 16.08, '03-24-N': 0})
        pipeline = self.collection.aggregate.call_args.args[0]
        target = dt.datetime(2026, 6, 30, 12, tzinfo=UTC)
        self.assertEqual(pipeline[0]['$match']['timestamp'], {'$gte': target - dt.timedelta(minutes=10),
                                                              '$lte': target + dt.timedelta(minutes=10)})
        self.assertEqual(pipeline[1]['$addFields']['distance']['$abs']['$subtract'][1], target)
        self.assertEqual(list(pipeline[2]['$sort'])[0], 'distance')

    def test_utc_suffix_is_accepted(self):
        self.collection.aggregate.return_value = []
        self.assertEqual(self.read('2026-01-01T00:00:00Z').json, {})

    def test_range_empty_and_populated(self):
        self.collection.find_one.return_value = None
        self.assertEqual(self.client.get('/api/temperatures/range', headers=self.headers).json,
                         {'minTimestamp': None, 'maxTimestamp': None})
        self.collection.find_one.side_effect = [{'timestamp': dt.datetime(2026, 1, 1)},
                                                {'timestamp': dt.datetime(2026, 6, 30, 21, 55)}]
        self.assertEqual(self.client.get('/api/temperatures/range', headers=self.headers).json,
                         {'minTimestamp': '2026-01-01T00:00:00+00:00', 'maxTimestamp': '2026-06-30T21:55:00+00:00'})

    def test_daily_responses_cannot_be_cached(self):
        response = self.client.get('/api/plans', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')


if __name__ == '__main__':
    unittest.main()
