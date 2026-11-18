"""API Flask : relais vers le récepteur de projection (port 5001) et ses pannes."""
import unittest
from unittest.mock import patch

from .support import bearer, load_app


class ProjectionApiTests(unittest.TestCase):
    def setUp(self):
        self.app = load_app()
        self.client = self.app.app.test_client()
        self.headers = bearer(self.app)
        patcher = patch.object(self.app.users, 'find_one', return_value={'username': 'test', 'role': 'operator'})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.room = self.app.PLAN_ROOMS[0]

    def post(self, path, payload):
        return self.client.post(path, json=payload, headers=self.headers)

    def test_commands_require_authentication(self):
        for path in ('/api/calibrate', '/api/project-room', '/api/project-temperatures', '/api/calibration-settings'):
            with self.subTest(path):
                self.assertEqual(self.client.post(path, json={}).status_code, 401)
        for path in ('/api/calibration-settings', '/api/projection-preview'):
            self.assertEqual(self.client.get(path).status_code, 401)

    def test_calibrate_forwards_and_reports_missing_receiver(self):
        with patch.object(self.app.requests, 'post') as post:
            self.assertEqual(self.post('/api/calibrate', {}).json, {'status': 'ok'})
        post.assert_called_once_with(f'{self.app.CAMERA_URL}/calibrate', timeout=5)
        with patch.object(self.app.requests, 'post', side_effect=self.app.requests.ConnectionError):
            self.assertEqual(self.post('/api/calibrate', {}).status_code, 502)
        with patch.object(self.app.requests, 'post') as post:
            post.return_value.raise_for_status.side_effect = self.app.requests.HTTPError
            self.assertEqual(self.post('/api/calibrate', {}).status_code, 502)

    def test_project_room_accepts_plan_rooms_and_clearing(self):
        for room_id in (self.room['id'], None):
            with patch.object(self.app.requests, 'post') as post:
                response = self.post('/api/project-room', {'roomId': room_id})
            self.assertEqual(response.json, {'status': 'ok', 'roomId': room_id})
            post.assert_called_once_with(f'{self.app.CAMERA_URL}/project-room', json={'roomId': room_id}, timeout=5)

    def test_project_room_rejects_unknown_rooms_without_forwarding(self):
        with patch.object(self.app.requests, 'post') as post:
            for payload in ([], {}, {'roomId': 'unknown'}, {'roomId': 3}, {'roomId': self.room['code']}):
                with self.subTest(payload=payload):
                    self.assertEqual(self.post('/api/project-room', payload).status_code, 400)
            post.assert_not_called()

    def test_shared_view_owns_projection_once_active(self):
        self.app.shared_view.active = True
        self.addCleanup(setattr, self.app.shared_view, 'active', False)
        with patch.object(self.app.requests, 'post') as post:
            self.assertEqual(self.post('/api/project-room', {'roomId': self.room['id']}).json['status'], 'shared-view')
            self.assertEqual(self.post('/api/project-temperatures', {}).json['status'], 'shared-view')
        post.assert_not_called()

    def test_project_temperatures_forwards_legacy_and_context_payloads(self):
        code = self.room['code']
        payloads = ({code: 21}, {},
                    {'temperatures': {code: 24.5}, 'context': {'day': '2026-06-30', 'minute': 1435, 'estimated': [code],
                                                               'roomCode': code, 'roomStats': {'min': 21, 'mean': 23, 'max': 25}}})
        for payload in payloads:
            with self.subTest(payload=payload), patch.object(self.app.requests, 'post') as post:
                self.assertEqual(self.post('/api/project-temperatures', payload).status_code, 200)
                post.assert_called_once_with(f'{self.app.CAMERA_URL}/project-temperatures', json=payload, timeout=5)

    def test_project_temperatures_rejects_invalid_values_and_context(self):
        code = self.room['code']
        invalid = ([], {'unknown': 21}, {code: True}, {code: '21'}, {code: float('inf')}, {code: None},
                   {'temperatures': {code: 21}, 'context': {'minute': 1440}},
                   {'temperatures': {code: 21}, 'context': {'roomCode': 'unknown'}},
                   {'temperatures': {code: 21}, 'context': []})
        with patch.object(self.app.requests, 'post') as post:
            for payload in invalid:
                with self.subTest(payload=payload):
                    self.assertEqual(self.post('/api/project-temperatures', payload).status_code, 400)
            post.assert_not_called()

    def test_project_temperatures_reports_missing_receiver(self):
        with patch.object(self.app.requests, 'post', side_effect=self.app.requests.Timeout):
            self.assertEqual(self.post('/api/project-temperatures', {}).status_code, 502)

    def test_calibration_settings_are_relayed_with_receiver_status(self):
        settings = {'mode': 'manual', 'corners': [[0, 0], [1, 0], [1, 1], [0, 1]], 'showGuide': True}
        with patch.object(self.app.requests, 'post') as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {**settings, 'automaticReady': False}
            response = self.post('/api/calibration-settings', settings)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['mode'], 'manual')
        post.assert_called_once_with(f'{self.app.CAMERA_URL}/calibration-settings', json=settings, timeout=5)
        with patch.object(self.app.requests, 'get') as get:
            get.return_value.status_code = 200
            get.return_value.json.return_value = settings
            self.assertEqual(self.client.get('/api/calibration-settings', headers=self.headers).json, settings)

    def test_receiver_conflicts_and_errors_keep_their_status(self):
        for status, body in ((400, {'error': 'Coins croisés.'}), (409, {'error': 'Calibration modifiée ailleurs.'})):
            with patch.object(self.app.requests, 'post') as post:
                post.return_value.status_code = status
                post.return_value.json.return_value = body
                response = self.post('/api/calibration-settings', {})
            self.assertEqual((response.status_code, response.json), (status, body))

    def test_invalid_settings_or_unreadable_receiver(self):
        with patch.object(self.app.requests, 'post') as post:
            self.assertEqual(self.post('/api/calibration-settings', []).status_code, 400)
            post.assert_not_called()
        with patch.object(self.app.requests, 'get', side_effect=self.app.requests.ConnectionError):
            self.assertEqual(self.client.get('/api/calibration-settings', headers=self.headers).status_code, 502)
        with patch.object(self.app.requests, 'get') as get:
            get.return_value.json.side_effect = ValueError('HTML instead of JSON')
            self.assertEqual(self.client.get('/api/calibration-settings', headers=self.headers).status_code, 502)

    def test_projection_preview_relays_image_and_settings_header(self):
        with patch.object(self.app.requests, 'get') as get:
            get.return_value.content = b'jpeg-test'
            get.return_value.headers = {'X-Calibration-Settings': '{"settingsRevision":4}'}
            response = self.client.get('/api/projection-preview', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b'jpeg-test')
        self.assertEqual(response.mimetype, 'image/jpeg')
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.headers['X-Calibration-Settings'], '{"settingsRevision":4}')
        with patch.object(self.app.requests, 'get', side_effect=self.app.requests.ConnectionError):
            self.assertEqual(self.client.get('/api/projection-preview', headers=self.headers).status_code, 502)


if __name__ == '__main__':
    unittest.main()
