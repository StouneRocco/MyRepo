import csv
import os
from pathlib import Path
import tempfile
import unittest

from flask import Flask
from badgeage_views import BadgeageData,parse_timestamp,register_badgeage_views
from temperature_day import load_plans


class BadgeageTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)/'badgeages.csv'
        self.plans=load_plans()
        self.n3=self.plans[3]['rooms'][0]['code']
        self.n4=self.plans[4]['rooms'][0]['code']
        self.write([
            ('2026-03-01T23:30:00Z',self.n3),
            ('2026-03-02 09:00:00',self.n3),
            ('2026-03-03 10:00:00',self.n4),
            ('2026-06-01 12:00:00',self.n3),
            ('bad',self.n3),
            ('2026-03-02 11:00:00','unknown'),
        ])
        self.source=BadgeageData(self.path,self.plans)
        self.app=Flask(__name__)
        register_badgeage_views(self.app,lambda fn:fn,self.path)
        self.client=self.app.test_client()

    def write(self,rows):
        with self.path.open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.writer(stream,delimiter=';')
            writer.writerow(['DateHeure','Code salle'])
            writer.writerows(rows)

    def test_dates_follow_each_floor_and_do_not_hardcode_march(self):
        self.assertEqual(self.client.get('/api/badgeages/days/3').json,['2026-03-02','2026-06-01'])
        self.assertEqual(self.client.get('/api/badgeages/days/4').json,['2026-03-03'])

    def test_daily_and_hourly_counts_use_existing_plan_codes(self):
        response=self.client.get('/api/badgeages/day/3/2026-03-02')
        self.assertEqual(response.status_code,200)
        frame=response.json
        self.assertEqual(frame['total'],2)
        self.assertEqual(frame['hourTotals'][0],1)
        self.assertEqual(frame['hourTotals'][9],1)
        self.assertEqual(sum(frame['rooms'][self.n3]['hours']),2)
        self.assertEqual(len(frame['rooms']),len(self.plans[3]['rooms']))
        empty=self.plans[3]['rooms'][1]['code']
        self.assertEqual(frame['rooms'][empty]['total'],0)

    def test_unknown_floor_date_and_empty_floor_are_distinct(self):
        self.assertEqual(self.client.get('/api/badgeages/days/9').status_code,404)
        self.assertEqual(self.client.get('/api/badgeages/day/3/not-a-date').status_code,400)
        self.assertEqual(self.client.get('/api/badgeages/day/4/2026-03-02').status_code,404)
        self.assertEqual(self.client.get('/api/badgeages/day/3/2026-03-31').status_code,404)

    def test_missing_or_invalid_local_file_is_503(self):
        self.path.unlink()
        self.assertEqual(self.client.get('/api/badgeages/days/3').status_code,503)
        self.path.write_text('bad;columns\na;b\n',encoding='utf-8')
        self.assertEqual(self.client.get('/api/badgeages/days/3').status_code,503)

    def test_file_updates_invalidate_cached_aggregates(self):
        self.assertEqual(self.source.day(3,'2026-03-02')['total'],2)
        self.write([('2026-03-02 09:00:00',self.n3)]*3)
        self.assertEqual(self.source.day(3,'2026-03-02')['total'],3)

    def test_invalid_and_nonexistent_timestamps_are_ignored(self):
        for value in ('',None,'invalid','2026-03-29 02:30:00'):
            self.assertIsNone(parse_timestamp(value))

    def test_supplied_babas_data_reconciles_all_daily_totals(self):
        from badgeage_views import CSV_PATH
        source=BadgeageData(CSV_PATH,self.plans)
        expected={3:0,4:0}
        with CSV_PATH.open(encoding='utf-8-sig',newline='') as stream:
            for row in csv.DictReader(stream):
                floor=source.code_to_floor.get(row['Code salle'].strip())
                if floor is not None and parse_timestamp(row['DateHeure']) is not None:expected[floor]+=1
        for floor in (3,4):
            frames=[source.day(floor,day) for day in source.days(floor)]
            self.assertGreater(expected[floor],0)
            self.assertEqual(sum(frame['total'] for frame in frames),expected[floor])
            for frame in frames:
                self.assertEqual(frame['total'],sum(frame['hourTotals']))
                self.assertEqual(frame['total'],sum(room['total'] for room in frame['rooms'].values()))
