import unittest

import cv2
import numpy as np

from projection_calibration import default_settings, validate_settings, projection_matrix, manual_from_automatic


class CalibrationTests(unittest.TestCase):
    def test_manual_override_starts_exactly_at_automatic_plan_and_freezes_it(self):
        source = [[.08,.24],[.94,.24],[.94,.8],[.08,.8]]
        automatic = np.array([[.7,.05,150],[.02,.8,30],[.00003,.00002,1.]])
        automatic_settings = default_settings()
        manual = manual_from_automatic(automatic_settings,source,1920,1080,automatic)
        pixels = (np.float32(source)*[1919,1079])[None]
        expected = cv2.perspectiveTransform(pixels, automatic)
        manual_matrix = projection_matrix(manual,1920,1080)
        np.testing.assert_allclose(cv2.perspectiveTransform(pixels,manual_matrix),expected,atol=.001)
        changed_auto = automatic.copy(); changed_auto[0,2] += 120
        np.testing.assert_allclose(projection_matrix(manual,1920,1080,changed_auto),manual_matrix)
        initial = np.array(manual['corners'])
        manual['corners'][0][0] += .02
        moved = cv2.perspectiveTransform(pixels,projection_matrix(manual,1920,1080))[0]
        np.testing.assert_allclose(moved[1:],initial[1:]*[1919,1079],atol=.001)
        self.assertNotEqual(manual['corners'][0],manual['initialCorners'][0])

    def test_manual_override_requires_automatic_calibration(self):
        with self.assertRaises(ValueError):
            manual_from_automatic(default_settings(),[[0,0],[1,0],[1,1],[0,1]],1920,1080,None)

    def test_moving_one_plan_corner_keeps_other_three_plan_anchors_fixed(self):
        source = [[.08, .24], [.94, .24], [.94, .8], [.08, .8]]
        for selected in range(4):
            target = [p[:] for p in source]
            target[selected] = [target[selected][0]+.03, target[selected][1]+.02]
            settings = validate_settings({'mode':'manual', 'sourceCorners':source, 'corners':target, 'showGuide':True})
            transformed = cv2.perspectiveTransform(np.float32([source])*[1919,1079], projection_matrix(settings,1920,1080))[0]
            np.testing.assert_allclose(transformed, np.array(target)*[1919,1079], atol=.001)
            others = [i for i in range(4) if i != selected]
            np.testing.assert_allclose(transformed[others], np.array(source)[others]*[1919,1079], atol=.001)

    def test_manual_operates_without_automatic_matrix(self):
        settings = {**default_settings(), 'mode': 'manual',
                    'corners': [[.1, .2], [.9, .1], [.8, .9], [.2, .8]]}
        matrix = projection_matrix(validate_settings(settings), 101, 101)
        source = np.float32([[[0, 0], [100, 0], [100, 100], [0, 100]]])
        actual = cv2.perspectiveTransform(source, matrix)[0]
        np.testing.assert_allclose(actual, np.array(settings['corners'])*100, atol=.001)

    def test_adjustment_is_applied_after_automatic_geometry(self):
        automatic = np.array([[.8, 0, 10], [0, .8, 5], [0, 0, 1.]])
        settings = default_settings()
        np.testing.assert_allclose(projection_matrix(settings, 101, 101, automatic), automatic)
        settings['corners'] = [[.1, 0], [1.1, 0], [1.1, 1], [.1, 1]]
        point = cv2.perspectiveTransform(np.float32([[[50, 50]]]), projection_matrix(settings, 101, 101, automatic))[0, 0]
        np.testing.assert_allclose(point, [60, 45], atol=.001)
        self.assertIsNone(projection_matrix(settings, 101, 101))

    def test_invalid_geometry_cannot_replace_a_valid_calibration(self):
        invalid = [None, {}, {**default_settings(), 'mode': 'unknown'},
                   {**default_settings(), 'showGuide': 'yes'},
                   {**default_settings(), 'corners': [[0, 0]]*4},
                   {**default_settings(), 'corners': [[0, 0], [1, 1], [1, 0], [0, 1]]},
                   {**default_settings(), 'corners': [[0, 0], [1, 0], [float('nan'), 1], [0, 1]]},
                   {**default_settings(), 'corners': [[True, 0], [1, 0], [1, 1], [0, 1]]}]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_settings(value)


if __name__ == '__main__':
    unittest.main()
