"""Outil manage_users.py : rôles, désactivation, mot de passe et révocation des sessions."""
import unittest
from unittest.mock import patch

from bson import ObjectId
from werkzeug.security import check_password_hash

import manage_users


class ManageUsersTests(unittest.TestCase):
    def setUp(self):
        self.account = {'_id': ObjectId(), 'username': 'alice', 'role': 'operator'}
        patcher = patch('manage_users.MongoClient')
        self.mongo = patcher.start()
        self.addCleanup(patcher.stop)
        self.users = self.mongo.return_value.__enter__.return_value.__getitem__.return_value.users
        self.users.find_one.return_value = self.account
        self.users.count_documents.return_value = 2

    def run_tool(self, *arguments, passwords=()):
        with patch('sys.argv', ['manage_users.py', *arguments]), patch('getpass.getpass', side_effect=list(passwords)), \
                patch('builtins.print'), patch('sys.stderr'):
            manage_users.main()
        return self.users.update_one.call_args.args

    def assert_refused(self, *arguments, passwords=()):
        with self.assertRaises(SystemExit):
            self.run_tool(*arguments, passwords=passwords)
        self.users.update_one.assert_not_called()

    def test_any_change_revokes_existing_sessions(self):
        query, operation = self.run_tool('Alice', '--role', 'viewer')
        self.users.find_one.assert_called_once_with({'username': 'alice'})
        self.assertEqual(query, {'_id': self.account['_id']})
        self.assertEqual(operation, {'$inc': {'session_version': 1}, '$set': {'role': 'viewer'}})

    def test_revoke_only_does_not_modify_the_account(self):
        _, operation = self.run_tool('alice', '--revoke-sessions')
        self.assertEqual(operation, {'$inc': {'session_version': 1}})

    def test_disable_and_enable(self):
        self.assertEqual(self.run_tool('alice', '--disable')[1]['$set'], {'disabled': True})
        self.assertEqual(self.run_tool('alice', '--enable')[1]['$set'], {'disabled': False})

    def test_disable_and_enable_are_mutually_exclusive(self):
        self.assert_refused('alice', '--disable', '--enable')

    def test_last_active_operator_cannot_be_removed(self):
        self.users.count_documents.return_value = 1
        self.assert_refused('alice', '--disable')
        self.assert_refused('alice', '--role', 'viewer')
        # Retirer un lecteur ou promouvoir reste possible.
        self.users.find_one.return_value = {**self.account, 'role': 'viewer'}
        self.assertEqual(self.run_tool('alice', '--disable')[1]['$set'], {'disabled': True})

    def test_password_is_confirmed_hashed_and_never_an_argument(self):
        _, operation = self.run_tool('alice', '--password', passwords=['new password', 'new password'])
        stored = operation['$set']['password']
        self.assertNotEqual(stored, 'new password')
        self.assertTrue(check_password_hash(stored, 'new password'))

    def test_invalid_password_requests_are_refused_before_connecting(self):
        self.assert_refused('alice', '--password', passwords=['short', 'short'])
        self.assert_refused('alice', '--password', passwords=['new password', 'other password'])
        self.assert_refused('alice')
        self.mongo.assert_not_called()

    def test_unknown_account(self):
        self.users.find_one.return_value = None
        self.assert_refused('nobody', '--revoke-sessions')


if __name__ == '__main__':
    unittest.main()
