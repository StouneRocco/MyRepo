"""API Flask : comptes, sessions JWT, rôles, limitation des tentatives et en-têtes."""
import datetime as dt
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import jwt
from pymongo.errors import DuplicateKeyError, PyMongoError
from werkzeug.security import check_password_hash, generate_password_hash

from tests import ROOT
from .support import TEST_SECRET, bearer, load_app

PASSWORD = 'correct horse battery'


class TokenTests(unittest.TestCase):
    def setUp(self):
        self.app = load_app()
        self.client = self.app.app.test_client()
        self.operator = {'username': 'test', 'role': 'operator'}

    def get_plans(self, headers):
        with patch.object(self.app.users, 'find_one', return_value=self.operator):
            return self.client.get('/api/plans', headers=headers)

    def test_valid_token_gives_access(self):
        self.assertEqual(self.get_plans(bearer(self.app)).status_code, 200)

    def test_missing_malformed_expired_or_forged_tokens_are_refused(self):
        past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
        tokens = {
            'absent': {},
            'schema': {'Authorization': 'Basic dGVzdDp0ZXN0'},
            'garbage': {'Authorization': 'Bearer not-a-jwt'},
            'expired': {'Authorization': 'Bearer ' + jwt.encode({'sub': 'test', 'exp': past}, TEST_SECRET, algorithm='HS256')},
            'forged': {'Authorization': 'Bearer ' + jwt.encode({'sub': 'test', 'exp': past + dt.timedelta(hours=1)},
                                                              'another-secret-that-is-long-enough!!', algorithm='HS256')},
            'no expiry': {'Authorization': 'Bearer ' + jwt.encode({'sub': 'test'}, TEST_SECRET, algorithm='HS256')},
            'none algorithm': {'Authorization': 'Bearer ' + jwt.encode({'sub': 'test', 'exp': past + dt.timedelta(hours=1)},
                                                                      None, algorithm='none')},
        }
        for name, headers in tokens.items():
            with self.subTest(name):
                response = self.get_plans(headers)
                self.assertEqual(response.status_code, 401)
                self.assertTrue(response.is_json)

    def test_token_lifetime_is_twelve_hours(self):
        payload = jwt.decode(self.app.make_token('test', 4), TEST_SECRET, algorithms=['HS256'])
        remaining = payload['exp'] - dt.datetime.now(dt.timezone.utc).timestamp()
        self.assertAlmostEqual(remaining, 12 * 3600, delta=60)
        self.assertEqual((payload['sub'], payload['version']), ('test', 4))

    def test_deleted_disabled_or_revoked_accounts_lose_access(self):
        for account in (None, {'username': 'test', 'disabled': True}, {'username': 'test', 'session_version': 1}):
            with self.subTest(account=account), patch.object(self.app.users, 'find_one', return_value=account):
                self.assertEqual(self.client.get('/api/plans', headers=bearer(self.app)).status_code, 401)
        with patch.object(self.app.users, 'find_one', return_value={'username': 'test', 'session_version': 1}):
            self.assertEqual(self.client.get('/api/plans', headers=bearer(self.app, version=1)).status_code, 200)

    def test_viewer_can_read_but_never_command(self):
        with patch.object(self.app.users, 'find_one', return_value={'username': 'test', 'role': 'viewer'}), \
                patch.object(self.app.requests, 'post') as post:
            self.assertEqual(self.client.get('/api/plans', headers=bearer(self.app)).status_code, 200)
            for path in ('/api/calibrate', '/api/project-room', '/api/project-temperatures',
                         '/api/view-state', '/api/projection-retry', '/api/calibration-settings'):
                with self.subTest(path):
                    self.assertEqual(self.client.post(path, json={}, headers=bearer(self.app)).status_code, 403)
            post.assert_not_called()

    def test_short_jwt_secret_prevents_startup(self):
        spec = importlib.util.spec_from_file_location('app_short_secret', ROOT / 'backend' / 'app.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {'JWT_SECRET': 'short'}), patch('pymongo.MongoClient') as mongo, \
                self.assertRaisesRegex(RuntimeError, '32 octets'):
            spec.loader.exec_module(module)
        mongo.assert_not_called()


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.app = load_app()
        self.client = self.app.app.test_client()

    def test_first_account_becomes_operator_with_hashed_password(self):
        with patch.object(self.app.users, 'count_documents', return_value=0), \
                patch.object(self.app.users, 'insert_one') as insert:
            response = self.client.post('/api/register', json={'username': '  Alice ', 'password': PASSWORD})
        self.assertEqual(response.status_code, 201)
        self.assertEqual((response.json['username'], response.json['role']), ('alice', 'operator'))
        stored = insert.call_args.args[0]
        self.assertEqual(stored['username'], 'alice')
        self.assertNotEqual(stored['password'], PASSWORD)
        self.assertTrue(check_password_hash(stored['password'], PASSWORD))
        self.assertEqual(jwt.decode(response.json['token'], TEST_SECRET, algorithms=['HS256'])['sub'], 'alice')

    def test_registration_closed_after_first_account_unless_explicitly_opened(self):
        with patch.object(self.app.users, 'count_documents', return_value=1), \
                patch.object(self.app.users, 'insert_one') as insert:
            with patch.dict(os.environ, {'ALLOW_REGISTRATION': 'false'}):
                self.assertFalse(self.client.get('/api/config').json['registrationOpen'])
                self.assertEqual(self.client.post('/api/register', json={'username': 'bob', 'password': PASSWORD}).status_code, 403)
                insert.assert_not_called()
            with patch.dict(os.environ, {'ALLOW_REGISTRATION': 'TRUE'}):
                self.assertTrue(self.client.get('/api/config').json['registrationOpen'])
                response = self.client.post('/api/register', json={'username': 'bob', 'password': PASSWORD})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['role'], 'viewer')

    def test_duplicate_username_is_a_conflict(self):
        with patch.object(self.app.users, 'count_documents', return_value=0), \
                patch.object(self.app.users, 'insert_one', side_effect=DuplicateKeyError('dup')):
            self.assertEqual(self.client.post('/api/register', json={'username': 'alice', 'password': PASSWORD}).status_code, 409)

    def test_credentials_shape_and_length_are_validated(self):
        invalid = ([1], 'bad', {'username': None, 'password': PASSWORD}, {'username': 'test', 'password': 123},
                   {'username': 'ab', 'password': PASSWORD}, {'username': 'x' * 33, 'password': PASSWORD},
                   {'username': 'test', 'password': 'short'}, {'username': 'test', 'password': 'x' * 257})
        with patch.object(self.app.users, 'find_one') as find:
            for value in invalid:
                with self.subTest(value=value):
                    response = self.client.post('/api/login', json=value)
                    self.assertEqual(response.status_code, 400)
                    self.assertTrue(response.is_json)
            find.assert_not_called()

    def test_login_success_carries_role_and_session_version(self):
        account = {'username': 'alice', 'role': 'viewer', 'session_version': 3,
                   'password': generate_password_hash(PASSWORD)}
        with patch.object(self.app.users, 'find_one', return_value=account) as find:
            response = self.client.post('/api/login', json={'username': 'ALICE', 'password': PASSWORD})
        find.assert_called_once_with({'username': 'alice'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['role'], 'viewer')
        self.assertEqual(jwt.decode(response.json['token'], TEST_SECRET, algorithms=['HS256'])['version'], 3)

    def test_wrong_password_unknown_or_disabled_account_share_one_message(self):
        account = {'username': 'alice', 'password': generate_password_hash(PASSWORD)}
        messages = set()
        for found, password in ((account, 'wrong password'), (None, PASSWORD), ({**account, 'disabled': True}, PASSWORD)):
            with patch.object(self.app.users, 'find_one', return_value=found):
                response = self.client.post('/api/login', json={'username': 'alice', 'password': password})
            self.assertEqual(response.status_code, 401)
            messages.add(response.json['error'])
        self.assertEqual(len(messages), 1)


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        self.app = load_app()
        self.client = self.app.app.test_client()
        self.addCleanup(self.app.auth_attempts.clear)

    def login(self, address='10.0.0.1'):
        return self.client.post('/api/login', json={'username': 'test', 'password': PASSWORD},
                                environ_base={'REMOTE_ADDR': address})

    def test_twenty_attempts_per_minute_then_429(self):
        with patch.object(self.app.users, 'find_one', return_value=None):
            for _ in range(20):
                self.assertEqual(self.login().status_code, 401)
            response = self.login()
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.headers['Retry-After'], '60')
            # Une autre adresse n'est pas bloquée par la première.
            self.assertEqual(self.login('10.0.0.2').status_code, 401)

    def test_attempts_expire_after_one_minute(self):
        with patch.object(self.app.users, 'find_one', return_value=None):
            with patch.object(self.app.time, 'monotonic', return_value=1000):
                for _ in range(20):
                    self.login()
                self.assertEqual(self.login().status_code, 429)
            with patch.object(self.app.time, 'monotonic', return_value=1061):
                self.assertEqual(self.login().status_code, 401)

    def test_other_routes_are_not_limited(self):
        with patch.object(self.app.users, 'count_documents', return_value=1):
            for _ in range(25):
                self.assertEqual(self.client.get('/api/config').status_code, 200)
        self.assertEqual(len(self.app.auth_attempts), 0)


class HttpBehaviourTests(unittest.TestCase):
    def setUp(self):
        self.app = load_app()
        self.client = self.app.app.test_client()

    def test_security_and_cache_headers(self):
        with patch.object(self.app.users, 'count_documents', return_value=1):
            response = self.client.get('/api/config')
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response.headers['X-Frame-Options'], 'DENY')
        self.assertEqual(response.headers['Referrer-Policy'], 'same-origin')
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_database_outage_is_a_json_503(self):
        with patch.object(self.app.users, 'count_documents', side_effect=PyMongoError('offline')), \
                self.assertLogs(self.app.app.logger, level='ERROR'):
            response = self.client.get('/api/config')
        self.assertEqual(response.status_code, 503)
        self.assertIn('MongoDB', response.json['error'])

    def test_unknown_api_route_is_json_and_never_the_web_app(self):
        for method in ('get', 'post'):
            response = getattr(self.client, method)('/api/not-a-route')
            self.assertEqual(response.status_code, 404 if method == 'get' else 405)
            self.assertTrue(response.is_json)

    def test_body_size_is_limited(self):
        response = self.client.post('/api/login', data='x' * (1024 * 1024 + 1), content_type='application/json')
        self.assertEqual(response.status_code, 413)


class SinglePageAppTests(unittest.TestCase):
    def setUp(self):
        self.app = load_app()
        self.client = self.app.app.test_client()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        dist = root / 'dist'
        (dist / 'assets').mkdir(parents=True)
        (dist / 'index.html').write_text('<div id="root"></div>', encoding='utf-8')
        (dist / 'assets' / 'app.js').write_text('console.log(1)', encoding='utf-8')
        (dist / 'sw.js').write_text('self.addEventListener', encoding='utf-8')
        (dist / 'manifest.webmanifest').write_text('{}', encoding='utf-8')
        (root / 'secret.txt').write_text('PRIVATE', encoding='utf-8')
        patcher = patch.object(self.app, 'DIST', str(dist))
        patcher.start()
        self.addCleanup(patcher.stop)

    def read(self, path):
        response = self.client.get(path)
        self.addCleanup(response.close)
        return response

    def test_index_and_client_routes_are_never_cached(self):
        for path in ('/', '/presence/n3'):
            response = self.read(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'id="root"', response.data)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_built_assets_are_served(self):
        response = self.read('/assets/app.js')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b'console.log(1)')

    def test_service_worker_and_manifest_are_always_revalidated(self):
        for path in ('/sw.js', '/manifest.webmanifest'):
            with self.subTest(path):
                response = self.read(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_files_outside_the_build_are_never_served(self):
        for path in ('/../secret.txt', '/..%2fsecret.txt', '/assets/../../secret.txt'):
            with self.subTest(path):
                self.assertNotIn(b'PRIVATE', self.read(path).data)


if __name__ == '__main__':
    unittest.main()
