"""healthcheck.py : code de sortie utilisé par start-pc.ps1 pour attendre MongoDB."""
import os
import runpy
import unittest
from unittest.mock import patch

from pymongo.errors import ServerSelectionTimeoutError

from tests import ROOT

SCRIPT = str(ROOT / 'backend' / 'healthcheck.py')


class HealthcheckTests(unittest.TestCase):
    def test_available_database_exits_normally(self):
        with patch('pymongo.MongoClient') as mongo, patch.dict(os.environ, {'MONGO_URI': 'mongodb://example:27017'}):
            runpy.run_path(SCRIPT, run_name='__main__')
        mongo.assert_called_once_with('mongodb://example:27017', serverSelectionTimeoutMS=1000)
        mongo.return_value.__enter__.return_value.admin.command.assert_called_once_with('ping')

    def test_unavailable_database_exits_with_code_1(self):
        with patch('pymongo.MongoClient') as mongo:
            mongo.return_value.__enter__.return_value.admin.command.side_effect = ServerSelectionTimeoutError('down')
            with self.assertRaises(SystemExit) as stop:
                runpy.run_path(SCRIPT, run_name='__main__')
        self.assertEqual(stop.exception.code, 1)


if __name__ == '__main__':
    unittest.main()
