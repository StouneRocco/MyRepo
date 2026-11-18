"""Import des relevés CSV/XLSX : formats, fuseaux, rejets, doublons et rapport."""
import datetime as dt
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pymongo import ReplaceOne
from pymongo.errors import BulkWriteError

import import_temperatures
from import_temperatures import RESOURCE_DIR, insert_measurements, measurement, read_rows

ROW = {'timestamp': '2026-01-01 00:00:00.365', 'value': '16.08', 'room': '03-23-N', 'floor': 'N3', 'zone': 'ESEO'}
UTC = dt.timezone.utc


class MeasurementTests(unittest.TestCase):
    def test_naive_paris_time_is_stored_in_utc(self):
        doc = measurement({**ROW, 'timestamp': '2026-06-30 14:00:00'})
        self.assertEqual(doc['timestamp'], dt.datetime(2026, 6, 30, 12, tzinfo=UTC))
        winter = measurement({**ROW, 'timestamp': '2026-01-15 14:00:00'})
        self.assertEqual(winter['timestamp'], dt.datetime(2026, 1, 15, 13, tzinfo=UTC))

    def test_excel_datetime_objects_follow_the_same_timezone_rule(self):
        doc = measurement({**ROW, 'timestamp': dt.datetime(2026, 1, 1)})
        self.assertEqual(doc['timestamp'], dt.datetime(2025, 12, 31, 23, tzinfo=UTC))

    def test_explicit_offset_and_utc_suffix_are_respected(self):
        self.assertEqual(measurement({**ROW, 'timestamp': '2026-06-30T12:00:00Z'})['timestamp'],
                         dt.datetime(2026, 6, 30, 12, tzinfo=UTC))
        self.assertEqual(measurement({**ROW, 'timestamp': '2026-06-30T12:00:00+05:00'})['timestamp'],
                         dt.datetime(2026, 6, 30, 7, tzinfo=UTC))

    def test_configurable_timezone(self):
        with patch.dict(os.environ, {'TEMPERATURE_TIMEZONE': 'UTC'}):
            doc = measurement({**ROW, 'timestamp': '2026-06-30 12:00:00'})
        self.assertEqual(doc['timestamp'], dt.datetime(2026, 6, 30, 12, tzinfo=UTC))

    def test_naive_dst_times_are_rejected_when_ambiguous_or_nonexistent(self):
        row = {**ROW, 'value': '20'}
        self.assertIsNone(measurement({**row, 'timestamp': '2026-03-29 02:30:00'}))
        self.assertIsNone(measurement({**row, 'timestamp': '2026-10-25 02:30:00'}))
        self.assertIsNotNone(measurement({**row, 'timestamp': '2026-10-25T02:30:00+02:00'}))

    def test_french_decimal_comma_and_surrounding_spaces(self):
        doc = measurement({**ROW, 'value': ' 23,5 ', 'room': ' 03-23-N ', 'floor': ' N3 '})
        self.assertEqual((doc['temperature'], doc['room'], doc['floor']), (23.5, '03-23-N', 'N3'))

    def test_invalid_values_and_truncated_rows(self):
        for value in ('', None, 'nan', 'inf', '-inf', 'abc'):
            self.assertIsNone(measurement({**ROW, 'value': value}), value)
        self.assertIsNone(measurement({**ROW, 'timestamp': 'invalid'}))
        self.assertIsNone(measurement({**ROW, 'room': '  '}))
        self.assertIsNone(measurement({**ROW, 'room': None}))
        self.assertIsNone(measurement({'timestamp': ROW['timestamp']}))

    def test_negative_and_zero_temperatures_are_kept(self):
        self.assertEqual(measurement({**ROW, 'value': '0'})['temperature'], 0)
        self.assertEqual(measurement({**ROW, 'value': '-3.5'})['temperature'], -3.5)


class ReadRowsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.folder = Path(self.directory.name)

    def test_csv_delimiters_comma_semicolon_and_tab(self):
        for delimiter in (',', ';', '\t'):
            path = self.folder / 'data.csv'
            header = delimiter.join(['timestamp', 'value', 'room', 'floor', 'zone'])
            line = delimiter.join(['2026-01-01T00:00:00Z', '16.08', '03-23-N', 'N3', 'ESEO'])
            path.write_text(f'{header}\n{line}\n', encoding='utf-8')
            self.assertEqual(measurement(next(read_rows(path)))['temperature'], 16.08, repr(delimiter))

    def test_utf8_bom_and_extra_columns_are_accepted(self):
        path = self.folder / 'month.csv'
        path.write_text('timestamp;display name;sensor id;value;room;floor;zone\n'
                        '2026-06-30 23:55:00.021;Temperature;sensor;24.5;03-23-N;Etage 3;ESEO\n', encoding='utf-8-sig')
        doc = measurement(next(read_rows(path)))
        self.assertEqual(doc['temperature'], 24.5)
        self.assertEqual(doc['timestamp'], dt.datetime(2026, 6, 30, 21, 55, 0, 21000, tzinfo=UTC))

    def test_missing_required_column_is_reported(self):
        path = self.folder / 'bad.csv'
        path.write_text('timestamp,value,room\n2026-01-01T00:00:00Z,16,03-23-N\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Colonnes requises'):
            next(read_rows(path))

    def test_regular_xlsx_and_named_sheet(self):
        from openpyxl import Workbook
        workbook = Workbook()
        workbook.active.title = 'Autre'
        workbook.active.append(['rien'])
        sheet = workbook.create_sheet('Mesures')
        sheet.append(['timestamp', 'value', 'room', 'floor', 'zone'])
        sheet.append([dt.datetime(2026, 1, 1), 16.08, '03-23-N', 'N3', 'ESEO'])
        sheet.append([None, None, None, None, None])
        path = self.folder / 'data.xlsx'
        workbook.save(path)
        rows = list(read_rows(path, 'Mesures'))
        self.assertEqual(len(rows), 1)
        self.assertEqual(measurement(rows[0])['room'], '03-23-N')
        with self.assertRaises(ValueError):
            list(read_rows(path))

    def test_embedded_csv_with_extra_empty_excel_columns(self):
        from openpyxl import Workbook
        workbook = Workbook()
        workbook.active.append(['timestamp,value,room,floor,zone'])
        workbook.active.append(['2026-01-01T00:00:00Z,16.08,03-23-N,N3,ESEO'])
        # Une cellule formatée suffit à gonfler les dimensions Excel.
        workbook.active.cell(5, 3).number_format = '0.00'
        path = self.folder / 'full.xlsx'
        workbook.save(path)
        rows = list(read_rows(path))
        self.assertEqual(len(rows), 1)
        self.assertEqual(measurement(rows[0])['temperature'], 16.08)

    def test_real_workbook_and_room_codes(self):
        rows = list(read_rows(RESOURCE_DIR / 'température coupé.xlsx'))
        docs = [doc for row in rows if (doc := measurement(row))]
        self.assertEqual(len(rows), 3055)
        self.assertEqual(len(docs), 2944)
        self.assertTrue(any(doc['room'] == '03-23-N' for doc in docs))
        self.assertEqual(docs[0]['temperature'], 16.08)
        self.assertEqual(docs[0]['timestamp'], dt.datetime(2025, 12, 31, 23, 0, 0, 365000, tzinfo=UTC))


class InsertTests(unittest.TestCase):
    def test_duplicates_are_kept_and_other_errors_are_raised(self):
        collection = MagicMock()
        collection.insert_many.side_effect = BulkWriteError({'nInserted': 1, 'writeErrors': [{'code': 11000}]})
        self.assertEqual(insert_measurements(collection, [{'room': 'a'}, {'room': 'b'}]), 1)
        collection.insert_many.side_effect = BulkWriteError({'nInserted': 0, 'writeErrors': [{'code': 121}]})
        with self.assertRaises(BulkWriteError):
            insert_measurements(collection, [{'room': 'a'}])
        collection.insert_many.side_effect = BulkWriteError({'nInserted': 1, 'writeErrors': [], 'writeConcernErrors': [{}]})
        with self.assertRaises(BulkWriteError):
            insert_measurements(collection, [{'room': 'a'}])

    def test_unordered_insert_counts_new_documents(self):
        collection = MagicMock()
        collection.insert_many.return_value.inserted_ids = [1, 2]
        self.assertEqual(insert_measurements(collection, [{'room': 'a'}, {'room': 'b'}]), 2)
        self.assertFalse(collection.insert_many.call_args.kwargs['ordered'])

    def test_replace_mode_upserts_on_room_and_timestamp(self):
        collection = MagicMock()
        collection.bulk_write.return_value.upserted_count = 1
        collection.bulk_write.return_value.modified_count = 2
        timestamp = dt.datetime(2026, 1, 1, tzinfo=UTC)
        batch = [{'room': 'a', 'timestamp': timestamp, 'temperature': 20}]
        self.assertEqual(insert_measurements(collection, batch, replace=True), 3)
        operation = collection.bulk_write.call_args.args[0][0]
        self.assertEqual(operation, ReplaceOne({'room': 'a', 'timestamp': timestamp}, batch[0], upsert=True))
        collection.insert_many.assert_not_called()


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / 'data.csv'
        self.source.write_text('timestamp;value;room;floor;zone\n'
                               '2026-06-30 12:00:00;23.5;03-23-N;N3;ESEO\n'
                               'invalid;20;03-23-N;N3;ESEO\n'
                               '2026-05-31 12:00:00;21;03-24-N;N3;ESEO\n', encoding='utf-8')
        self.report = self.root / 'report.json'

    def run_main(self, *arguments):
        with patch('sys.argv', ['import_temperatures.py', *arguments]), patch('builtins.print'):
            import_temperatures.main()
        return json.loads(self.report.read_text(encoding='utf-8'))

    def test_dry_run_reports_coverage_and_never_connects_to_database(self):
        with patch('import_temperatures.MongoClient') as mongo:
            data = self.run_main(str(self.source), '--dry-run', '--report', str(self.report))
        mongo.assert_not_called()
        self.assertEqual((data['valid'], data['rejected'], data['insertedOrUpdated']), (2, 1, 0))
        self.assertIsNone(data['unchangedOrDuplicate'])
        self.assertEqual(data['rejectedLineExamples'], [3])
        self.assertEqual(data['sha256'], hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual([(c['month'], c['room']) for c in data['coverage']],
                         [('2026-05', '03-24-N'), ('2026-06', '03-23-N')])

    def test_import_creates_indexes_inserts_and_reports_duplicates(self):
        with patch('import_temperatures.MongoClient') as mongo:
            collection = mongo.return_value.__enter__.return_value.__getitem__.return_value.__getitem__.return_value
            collection.insert_many.return_value.inserted_ids = [1]
            data = self.run_main(str(self.source), '--report', str(self.report))
        collection.create_index.assert_any_call([('room', 1), ('timestamp', 1)], unique=True)
        self.assertEqual(len(collection.insert_many.call_args.args[0]), 2)
        self.assertEqual((data['insertedOrUpdated'], data['unchangedOrDuplicate']), (1, 1))
        self.assertFalse(data['replaceExisting'])

    def test_replace_existing_is_explicit(self):
        with patch('import_temperatures.MongoClient') as mongo:
            collection = mongo.return_value.__enter__.return_value.__getitem__.return_value.__getitem__.return_value
            collection.bulk_write.return_value.upserted_count = 0
            collection.bulk_write.return_value.modified_count = 2
            data = self.run_main(str(self.source), '--replace-existing', '--report', str(self.report))
        collection.insert_many.assert_not_called()
        self.assertTrue(data['replaceExisting'])
        self.assertEqual(data['insertedOrUpdated'], 2)

    def test_file_is_required_when_several_sources_exist(self):
        (self.root / 'other.xlsx').write_bytes(b'')
        with patch.object(import_temperatures, 'RESOURCE_DIR', self.root), \
                patch('sys.argv', ['import_temperatures.py', '--dry-run']), \
                patch('sys.stderr'), self.assertRaises(SystemExit):
            import_temperatures.main()


if __name__ == '__main__':
    unittest.main()
