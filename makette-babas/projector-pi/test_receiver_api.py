"""Parcours HTTP du vrai récepteur, acquisition et fenêtres remplacées par des doubles."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np


class ReceiverApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        camera=MagicMock()
        camera.read.return_value=(True,np.zeros((120,160,3),dtype=np.uint8))
        path=Path(__file__).with_name('color_receiver.py')
        spec=importlib.util.spec_from_file_location('receiver_api_tests',path)
        cls.module=importlib.util.module_from_spec(spec)
        with patch.object(cv2,'VideoCapture',return_value=camera),patch.object(cv2,'namedWindow'),patch.object(cv2,'moveWindow'),patch.object(cv2,'setWindowProperty'),patch.object(cv2,'setMouseCallback'),patch.object(cv2,'imshow'),patch.object(cv2,'destroyAllWindows'),patch.object(cv2,'waitKey',return_value=ord('q')),patch('threading.Thread'):
            spec.loader.exec_module(cls.module)
        camera.release.assert_called_once()

    def setUp(self):
        self.receiver=self.module
        self.receiver.calibration_settings=self.receiver.default_settings()
        self.receiver.automatic_settings=self.receiver.default_settings()
        self.receiver.settings_revision=10
        self.receiver.automatic_matrix=np.eye(3)
        self.client=self.receiver.app.test_client()

    def test_stale_calibration_is_rejected_without_writing_or_moving(self):
        payload={**self.receiver.default_settings(),'expectedRevision':9}
        with patch.object(self.receiver,'save_calibration') as save:
            response=self.client.post('/calibration-settings',json=payload)
        self.assertEqual(response.status_code,409)
        save.assert_not_called()
        self.assertEqual(self.receiver.settings_revision,10)

    def test_return_to_automatic_is_persisted(self):
        with patch.object(self.receiver,'save_calibration') as save:
            response=self.client.post('/calibration-settings',json={'action':'resume-automatic','expectedRevision':10})
        self.assertEqual(response.status_code,200)
        save.assert_called_once()
        self.assertEqual(response.json['settingsRevision'],11)

    def test_heatmap_flag_does_not_remove_numeric_measurements(self):
        room=next(iter(self.receiver.ROOMS.values()))
        response=self.client.post('/project-temperatures',json={'temperatures':{room['code']:23.5},'heatmap':False})
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.receiver.room_temperatures[room['code']],23.5)
        self.assertFalse(self.receiver.heatmap_enabled)
        self.assertEqual(self.client.post('/project-temperatures',json={'temperatures':{},'roomId':{}}).status_code,400)

    def test_health_distinguishes_camera_and_render_loop(self):
        self.receiver.camera_available=False
        response=self.client.get('/health')
        self.assertEqual(response.status_code,200)
        self.assertFalse(response.json['cameraAvailable'])
        self.assertIn('renderAgeSeconds',response.json)
