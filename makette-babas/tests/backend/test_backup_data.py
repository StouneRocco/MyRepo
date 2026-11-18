"""Sauvegarde/restauration MongoDB : fidélité BSON et protections contre l'écrasement."""
import datetime as dt
import gzip
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from bson import ObjectId, json_util

import backup_data
from backup_data import COLLECTIONS, backup, restore


def source_database(documents):
    database, tables = MagicMock(), {}
    for name in COLLECTIONS:
        table = MagicMock()
        table.find.return_value.batch_size.return_value = documents.get(name, [])
        tables[name] = table
    database.__getitem__.side_effect = tables.__getitem__
    return database


def empty_destination():
    destination, tables = MagicMock(), {}
    destination.list_collection_names.return_value = []
    destination.__getitem__.side_effect = lambda name: tables.setdefault(name, MagicMock())
    return destination, tables


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.target = Path(self.directory.name) / 'backup.json.gz'

    def write_backup(self, lines, header=None):
        with gzip.open(self.target, 'wt', encoding='utf-8') as stream:
            stream.write(json_util.dumps(header or {'format': 'maquette-backup-v1'}) + '\n')
            for line in lines:
                stream.write(json_util.dumps(line) + '\n')

    def test_roundtrip_preserves_bson_types_per_collection(self):
        measurement = {'_id': ObjectId(), 'timestamp': dt.datetime(2026, 6, 30, 12), 'temperature': 23.5}
        account = {'_id': ObjectId(), 'username': 'alice', 'password': 'hash'}
        backup(source_database({'temperature_measurements': [measurement], 'users': [account]}), self.target)
        destination, tables = empty_destination()
        restore(destination, self.target)
        self.assertEqual(tables['temperature_measurements'].insert_many.call_args.args[0], [measurement])
        self.assertEqual(tables['users'].insert_many.call_args.args[0], [account])
        self.assertNotIn('viewer_state', tables)
        destination.users.create_index.assert_called_once_with('username', unique=True)

    def test_existing_or_interrupted_backup_is_never_overwritten(self):
        backup(source_database({}), self.target)
        before = self.target.read_bytes()
        with self.assertRaises(ValueError):
            backup(source_database({}), self.target)
        self.assertEqual(self.target.read_bytes(), before)
        other = self.target.with_name('other.json.gz')
        other.with_suffix('.gz.partial').write_text('interrupted')
        with self.assertRaises(FileExistsError):
            backup(source_database({}), other)
        self.assertFalse(other.exists())

    def test_restore_never_writes_to_a_populated_database(self):
        destination = MagicMock()
        destination.list_collection_names.return_value = ['users']
        with self.assertRaises(ValueError):
            restore(destination, 'unused.json.gz')
        destination.__getitem__.assert_not_called()

    def test_unknown_format_or_collection_is_refused(self):
        self.write_backup([], header={'format': 'other'})
        with self.assertRaisesRegex(ValueError, 'Format'):
            restore(empty_destination()[0], self.target)
        self.target.unlink()
        self.write_backup([{'collection': 'system.users', 'document': {'_id': 1}}])
        destination, tables = empty_destination()
        with self.assertRaisesRegex(ValueError, 'Collection'):
            restore(destination, self.target)
        self.assertEqual(tables, {})

    def test_large_collections_are_restored_in_batches_of_1000(self):
        self.write_backup([{'collection': 'temperature_measurements', 'document': {'_id': i}} for i in range(2500)])
        destination, tables = empty_destination()
        restore(destination, self.target)
        sizes = [len(call.args[0]) for call in tables['temperature_measurements'].insert_many.call_args_list]
        self.assertEqual(sizes, [1000, 1000, 500])


class CommandLineTests(unittest.TestCase):
    def test_restore_requires_another_explicit_database_before_connecting(self):
        for arguments in (['restore', 'file.json.gz'], ['restore', 'file.json.gz', '--database', 'calibration_app_pc']):
            with self.subTest(arguments), patch('sys.argv', ['backup_data.py', *arguments]), \
                    patch.dict(os.environ, {'MONGO_DB': 'calibration_app_pc'}), \
                    patch('backup_data.MongoClient') as mongo, patch('sys.stderr'), self.assertRaises(SystemExit):
                backup_data.main()
            mongo.assert_not_called()

    def test_restore_uses_the_named_database(self):
        with patch('sys.argv', ['backup_data.py', 'restore', 'file.json.gz', '--database', 'restore_test']), \
                patch('backup_data.MongoClient') as mongo, patch('backup_data.restore') as restore_mock, patch('builtins.print'):
            backup_data.main()
        client = mongo.return_value.__enter__.return_value
        client.__getitem__.assert_called_once_with('restore_test')
        restore_mock.assert_called_once()


if __name__ == '__main__':
    unittest.main()
