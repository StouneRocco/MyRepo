"""API locale du vrai récepteur (port 5001), caméra et fenêtres OpenCV remplacées par des doubles."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

from tests import ROOT


class ReceiverApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        camera = MagicMock()
        camera.read.return_value = (True, np.zeros((120, 160, 3), dtype=np.uint8))
        spec = importlib.util.spec_from_file_location('receiver_api_tests', ROOT / 'projector-pi' / 'color_receiver.py')
        cls.module = importlib.util.module_from_spec(spec)
        windows = [patch.object(cv2, name) for name in ('namedWindow', 'moveWindow', 'setWindowProperty',
                                                        'setMouseCallback', 'imshow', 'destroyAllWindows')]
        with patch.object(cv2, 'VideoCapture', return_value=camera), patch.object(cv2, 'waitKey', return_value=ord('q')), \
                patch('threading.Thread'), patch('builtins.print'):
            for window in windows:
                window.start()
            try:
                spec.loader.exec_module(cls.module)
            finally:
                for window in windows:
                    window.stop()
        # La boucle principale a tourné une fois puis libéré la caméra sur 'q'.
        camera.release.assert_called_once()

    def setUp(self):
        self.receiver = self.module
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        values = dict(calibration_settings=self.receiver.default_settings(), automatic_settings=self.receiver.default_settings(),
                      settings_revision=10, automatic_matrix=np.eye(3), selected_room_id=None, room_temperatures={},
                      heatmap_enabled=True, projection_context={}, calibration_requested=False, control_corner=None,
                      settings_path=Path(directory.name) / '.projection_calibration.json')
        for name, value in values.items():
            setattr(self.receiver, name, value)
        self.client = self.receiver.app.test_client()
        self.room = next(iter(self.receiver.ROOMS.values()))

    def manual(self, **changes):
        return {'mode': 'manual', 'corners': [[.1, .1], [.9, .1], [.9, .9], [.1, .9]], 'showGuide': True, **changes}

    # --- Commandes de projection -------------------------------------------------------------

    def test_calibrate_request_is_handed_to_the_main_loop(self):
        self.assertEqual(self.client.post('/calibrate').json, {'status': 'ok'})
        self.assertTrue(self.receiver.calibration_requested)

    def test_project_room_selects_clears_and_redraws(self):
        version = self.receiver.temperature_version
        self.assertEqual(self.client.post('/project-room', json={'roomId': self.room['id']}).status_code, 200)
        self.assertEqual(self.receiver.selected_room_id, self.room['id'])
        self.assertEqual(self.receiver.temperature_version, version + 1)
        self.client.post('/project-room', json={'roomId': None})
        self.assertIsNone(self.receiver.selected_room_id)
        for payload in ({}, [], {'roomId': 'unknown'}, {'roomId': 1}):
            self.assertEqual(self.client.post('/project-room', json=payload).status_code, 400)

    def test_temperatures_with_context_selection_and_heatmap(self):
        context = {'day': '2026-06-30', 'minute': 840, 'estimated': [], 'roomCode': self.room['code'], 'roomStats': {'mean': 23.5}}
        response = self.client.post('/project-temperatures', json={'temperatures': {self.room['code']: 23.5}, 'heatmap': False,
                                                                   'context': context, 'roomId': self.room['id']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.receiver.room_temperatures, {self.room['code']: 23.5})
        self.assertFalse(self.receiver.heatmap_enabled)
        self.assertEqual(self.receiver.projection_context['day'], '2026-06-30')
        self.assertEqual(self.receiver.selected_room_id, self.room['id'])

    def test_legacy_temperature_dictionary_keeps_current_selection(self):
        self.receiver.selected_room_id = self.room['id']
        self.assertEqual(self.client.post('/project-temperatures', json={self.room['code']: 21}).status_code, 200)
        self.assertEqual(self.receiver.room_temperatures, {self.room['code']: 21})
        self.assertEqual(self.receiver.selected_room_id, self.room['id'])
        self.assertEqual(self.receiver.projection_context, {})

    def test_invalid_temperature_payloads_change_nothing(self):
        code = self.room['code']
        invalid = ([], {'unknown': 21}, {code: '21'},
                   {'temperatures': {code: 21}, 'heatmap': 'yes'},
                   {'temperatures': {code: 21}, 'roomId': {}},
                   {'temperatures': {code: 21}, 'roomId': 'unknown'},
                   {'temperatures': {code: 21}, 'context': {'minute': -5}})
        for payload in invalid:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post('/project-temperatures', json=payload).status_code, 400)
        self.assertEqual(self.receiver.room_temperatures, {})
        self.assertTrue(self.receiver.heatmap_enabled)

    # --- Calibration ------------------------------------------------------------------------

    def test_settings_read_includes_plan_corners_and_revision(self):
        data = self.client.get('/calibration-settings').json
        self.assertEqual((data['mode'], data['settingsRevision'], data['automaticReady']), ('automatic', 10, True))
        self.assertEqual(len(data['planCorners']), 4)
        for x, y in data['planCorners']:
            self.assertTrue(0 <= x <= 1 and 0 <= y <= 1)

    def test_temporary_manual_move_is_applied_without_saving(self):
        with patch.object(self.receiver, 'save_calibration') as save:
            response = self.client.post('/calibration-settings', json={**self.manual(), 'persist': False, 'expectedRevision': 10})
        self.assertEqual(response.status_code, 200)
        save.assert_not_called()
        self.assertEqual(self.receiver.calibration_settings['mode'], 'manual')
        self.assertEqual(response.json['settingsRevision'], 11)
        self.assertEqual(self.receiver.automatic_settings['mode'], 'automatic')

    def test_saved_automatic_adjustment_becomes_the_automatic_reference(self):
        settings = {**self.receiver.default_settings(), 'corners': [[.02, 0], [1, 0], [1, 1], [0, 1]]}
        with patch.object(self.receiver, 'save_calibration') as save:
            self.assertEqual(self.client.post('/calibration-settings', json=settings).status_code, 200)
        save.assert_called_once()
        self.assertEqual(self.receiver.automatic_settings['corners'][0], [.02, 0])

    def test_invalid_settings_are_rejected_without_side_effect(self):
        for payload in ([], self.manual(corners=[[0, 0], [1, 1], [1, 0], [0, 1]]), self.manual(persist='yes'),
                        self.manual(corners=[[0, 0], [2, 0], [1, 1], [0, 1]])):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post('/calibration-settings', json=payload).status_code, 400)
        self.assertEqual(self.receiver.settings_revision, 10)
        self.assertEqual(self.receiver.calibration_settings['mode'], 'automatic')

    def test_stale_or_malformed_revision_is_a_conflict(self):
        for expected in (9, 11, True, '10', 10.0):
            with self.subTest(expected=expected), patch.object(self.receiver, 'save_calibration') as save:
                response = self.client.post('/calibration-settings', json={**self.manual(), 'expectedRevision': expected})
                self.assertEqual(response.status_code, 409)
                save.assert_not_called()
        self.assertEqual(self.receiver.settings_revision, 10)

    def test_failed_save_keeps_previous_settings(self):
        with patch.object(self.receiver, 'save_calibration', side_effect=OSError('disk full')):
            response = self.client.post('/calibration-settings', json=self.manual())
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.receiver.calibration_settings['mode'], 'automatic')
        self.assertEqual(self.receiver.settings_revision, 10)

    def test_manual_adjustment_starts_from_automatic_alignment(self):
        self.receiver.automatic_matrix = None
        self.assertEqual(self.client.post('/calibration-settings', json={'action': 'adjust-automatic'}).status_code, 409)
        self.receiver.automatic_matrix = np.eye(3)
        response = self.client.post('/calibration-settings', json={'action': 'adjust-automatic'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.json['mode'], response.json['showGuide']), ('manual', True))
        np.testing.assert_allclose(response.json['sourceCorners'], self.receiver.plan_corners)
        np.testing.assert_allclose(response.json['corners'], self.receiver.plan_corners, atol=1e-5)

    def test_return_to_automatic_is_persisted(self):
        self.receiver.calibration_settings = self.manual()
        with patch.object(self.receiver, 'save_calibration') as save:
            response = self.client.post('/calibration-settings', json={'action': 'resume-automatic', 'expectedRevision': 10})
        self.assertEqual(response.status_code, 200)
        save.assert_called_once_with(self.receiver.automatic_settings)
        self.assertEqual(response.json['settingsRevision'], 11)
        self.assertEqual(self.receiver.calibration_settings['mode'], 'automatic')

    def test_save_writes_complete_json_atomically(self):
        settings = self.manual()
        self.receiver.save_calibration(settings)
        self.assertEqual(json.loads(self.receiver.settings_path.read_text(encoding='utf-8')), settings)
        self.assertFalse(self.receiver.settings_path.with_suffix('.tmp').exists())

    # --- Supervision et aperçu --------------------------------------------------------------

    def test_health_distinguishes_camera_and_render_loop(self):
        self.receiver.camera_available = False
        self.receiver.last_render_at = 0
        data = self.client.get('/health').json
        self.assertFalse(data['cameraAvailable'])
        self.assertIsNone(data['renderAgeSeconds'])
        self.receiver.last_render_at = self.receiver.time.monotonic() - 1
        self.assertGreaterEqual(self.client.get('/health').json['renderAgeSeconds'], 1)

    def test_preview_is_a_jpeg_with_current_settings(self):
        self.receiver.preview_frame = np.full((540, 960, 3), 200, dtype=np.uint8)
        response = self.client.get('/projection-preview')
        self.assertEqual(response.mimetype, 'image/jpeg')
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(json.loads(response.headers['X-Calibration-Settings'])['settingsRevision'], 10)
        image = cv2.imdecode(np.frombuffer(response.data, np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(image.shape, (540, 960, 3))

    # --- Fenêtre « Controle PC » ------------------------------------------------------------

    def test_mouse_drags_only_the_nearest_corner_in_manual_mode(self):
        self.receiver.calibration_settings = self.manual()
        self.receiver.control_mouse(cv2.EVENT_LBUTTONDOWN, 96, 54, 0, None)
        self.assertEqual(self.receiver.control_corner, 0)
        self.receiver.control_mouse(cv2.EVENT_MOUSEMOVE, 0, 0, 0, None)
        self.assertEqual(self.receiver.calibration_settings['corners'], [[0, 0], [.9, .1], [.9, .9], [.1, .9]])
        self.assertEqual(self.receiver.settings_revision, 11)
        self.receiver.control_mouse(cv2.EVENT_LBUTTONUP, 0, 0, 0, None)
        self.assertIsNone(self.receiver.control_corner)

    def test_crossing_drag_and_automatic_mode_are_ignored(self):
        self.receiver.calibration_settings = self.manual()
        self.receiver.control_mouse(cv2.EVENT_LBUTTONDOWN, 96, 54, 0, None)
        self.receiver.control_mouse(cv2.EVENT_MOUSEMOVE, 950, 530, 0, None)
        self.assertEqual(self.receiver.calibration_settings['corners'][0], [.1, .1])
        self.receiver.calibration_settings = self.receiver.default_settings()
        self.receiver.control_mouse(cv2.EVENT_LBUTTONDOWN, 0, 0, 0, None)
        self.assertIsNone(self.receiver.control_corner)
        self.assertEqual(self.receiver.settings_revision, 10)


if __name__ == '__main__':
    unittest.main()
