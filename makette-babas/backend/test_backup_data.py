import datetime as dt
import gzip
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

from bson import ObjectId, json_util
from backup_data import backup, restore


class BackupTests(unittest.TestCase):
    def test_roundtrip_preserves_bson_and_refuses_overwrite(self):
        doc={'_id':ObjectId(),'timestamp':dt.datetime(2026,6,30,12),'temperature':23.5}
        source=MagicMock()
        tables={}
        for name in ('temperature_measurements','users','viewer_state','import_runs'):
            table=MagicMock();table.find.return_value.batch_size.return_value=[doc] if name=='temperature_measurements' else []
            tables[name]=table
        source.__getitem__.side_effect=tables.__getitem__
        destination=MagicMock();destination.list_collection_names.return_value=[]
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            target=Path(directory)/'backup.json.gz'
            backup(source,target)
            with self.assertRaises(ValueError):backup(source,target)
            restore(destination,target)
        restored=destination.__getitem__.return_value.insert_many.call_args.args[0][0]
        self.assertEqual(restored,doc)

    def test_restore_never_writes_to_a_populated_database(self):
        destination=MagicMock();destination.list_collection_names.return_value=['users']
        with self.assertRaises(ValueError):restore(destination,'unused.json.gz')
        destination.__getitem__.assert_not_called()
