import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing
from unittest.mock import patch
from flask import Flask
from electrical_views import register_electrical_views
from electrical_views import electrical_frame
from temperature_day import load_plans


class ElectricalViewsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'bos.db'
        with closing(sqlite3.connect(self.path)) as conn:
            conn.executescript('''
                CREATE TABLE electrical_meters(sensor_id TEXT, circuit_id TEXT, label TEXT, usage TEXT, included INTEGER);
                CREATE TABLE electrical_hourly(sensor_id TEXT, hour TEXT, energy_kwh REAL);
                CREATE TABLE circuit_rooms(circuit_id TEXT, room TEXT);
                INSERT INTO electrical_meters VALUES ('a','D1','Partagé','Lighting',1), ('b','D2','Parent','Lighting',0), ('c','D3','Absent','Heating',1);
                INSERT INTO electrical_hourly VALUES ('a','2026-01-01 12:00:00',2), ('b','2026-01-01 12:00:00',10), ('a','2026-01-02 00:00:00',5);
                INSERT INTO circuit_rooms VALUES ('D1','A'), ('D1','B');
            ''')
        app = Flask(__name__)
        register_electrical_views(app, lambda fn: fn)
        self.client = app.test_client()
        self.env = patch.dict(os.environ, {'BOS_DB_PATH': str(self.path)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_sums_included_meters_without_assigning_shared_energy(self):
        data = self.client.get('/api/electricity?day=2026-01-01').json
        self.assertEqual(data['total'], 2)
        circuits = {c['circuit_id']: c for c in data['circuits']}
        self.assertEqual(circuits['D1']['rooms'], ['A', 'B'])
        self.assertEqual(circuits['D2']['energy_kwh'], 10)
        self.assertIsNone(circuits['D3']['energy_kwh'])

    def test_missing_day_and_invalid_date(self):
        self.assertIsNone(self.client.get('/api/electricity?day=2026-01-03').json['total'])
        self.assertEqual(self.client.get('/api/electricity?day=9999-12-31').status_code, 400)

    def test_missing_database(self):
        with patch.dict(os.environ, {'BOS_DB_PATH': str(self.path.parent / 'missing.db')}):
            self.assertEqual(self.client.get('/api/electricity').status_code, 503)

    def test_hourly_map_allocates_shared_and_rejects_incomplete_data(self):
        room = load_plans()[3]['rooms'][0]['code']
        with closing(sqlite3.connect(self.path)) as conn:
            conn.executemany('INSERT INTO electrical_meters VALUES (?,?,?,?,?)', [
                ('d','D4','Dédié','Lighting',1), ('e','D5','Dédié','Lighting',1),
                ('f','D6','Partagé','Lighting',1)])
            conn.executemany('INSERT INTO circuit_rooms VALUES (?,?)', [
                ('D4',room), ('D5',room), ('D6',room), ('D6','AUTRE')])
            conn.executemany('INSERT INTO electrical_hourly VALUES (?,?,?)', [
                ('d','2026-01-01 10:00:00',0), ('e','2026-01-01 10:00:00',2),
                ('f','2026-01-01 10:00:00',30), ('d','2026-01-01 11:00:00',1)])
            conn.commit()
        electrical_frame.cache_clear()
        result = self.client.get('/api/electricity/day/3/2026-01-01').json['rooms'][room]
        self.assertEqual(result['meters'],3)
        self.assertEqual(result['sharedMeters'],1)
        self.assertEqual(result['hours'][10],17)
        self.assertEqual(result['dedicated'][10],2)
        self.assertEqual(result['shared'][10],15)
        self.assertIsNone(result['hours'][11])
        self.assertEqual(result['observed'][11],1)


if __name__ == '__main__':
    unittest.main()
