import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from room_projection import PLAN, ROOMS, image_points, projection_points, temperature_color, validate_temperatures, TEMPERATURE_SCALE, render_temperature_canvas


class RoomProjectionTests(unittest.TestCase):
    def test_summary_counts_only_plan_rooms_and_keeps_missing_distinct(self):
        from room_projection import projection_summary
        a, b = list(ROOMS)[:2]
        values = {ROOMS[a]['code']: 0, ROOMS[b]['code']: 24, 'unknown': 99}
        summary = projection_summary(values, a)
        self.assertEqual(summary['count'], 2)
        self.assertEqual(summary['missing'], len(ROOMS)-2)
        self.assertEqual(summary['mean'], 12)
        self.assertEqual(summary['temperature'], 0)
        self.assertIsNone(projection_summary({}, a)['temperature'])

    def test_projected_legend_matches_shared_heatmap_scale(self):
        import numpy as np
        from room_projection import render_projection_info
        image = render_projection_info(np.zeros((1080,1920,3), dtype=np.uint8), {})
        for offset, value in ((0,12),(899,30)):
            np.testing.assert_array_equal(image[935,480+offset], temperature_color(value))
        self.assertFalse(image[250:850].any())
        self.assertFalse(image[:250,:250].any())
        self.assertFalse(image[:250,1670:].any())

    def test_catalog_matches_source_svg(self):
        root = ET.parse(Path(__file__).resolve().parent.parent / "ressources" / "plan_N3_Structure_modifie.svg")
        polygons = {e.get("data-space-id"): e for e in root.iter()
                    if e.get("data-selectable") == "true"}
        self.assertEqual(set(ROOMS), set(polygons))
        for room_id, room in ROOMS.items():
            points = [list(map(float, point.split(",")))
                      for point in polygons[room_id].get("points").split()]
            self.assertEqual(room["points"], points)

    def test_all_rooms_inside_reference_image(self):
        for room_id in ROOMS:
            for x, y in image_points(room_id, 4967, 3509):
                self.assertTrue(0 <= x <= 4967 and 0 <= y <= 3509)

    def test_mapping_can_be_adjusted_and_scales_with_canvas(self):
        room_id = next(iter(ROOMS))
        with patch.dict("os.environ", {"PLAN_IMAGE_BOUNDS": "[0, 0, 1, 1]"}):
            small = image_points(room_id, 100, 100)
            large = image_points(room_id, 200, 300)
            for (x, y), (xx, yy) in zip(small, large):
                self.assertAlmostEqual(xx, 2 * x)
                self.assertAlmostEqual(yy, 3 * y)

    def test_projection_area_is_65_percent(self):
        def area(points):
            return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1]))) / 2
        for room_id in ROOMS:
            original = image_points(room_id, 1820, 980)
            reduced = projection_points(room_id, 1820, 980)
            self.assertAlmostEqual(area(reduced) / area(original), 0.65)
            for axis in (0, 1):
                self.assertGreater(min(p[axis] for p in reduced), min(p[axis] for p in original))
                self.assertLess(max(p[axis] for p in reduced), max(p[axis] for p in original))


class TemperatureProjectionTests(unittest.TestCase):
    def test_selected_room_lights_up_without_temperature_and_clears(self):
        import cv2
        import numpy as np
        room_id = next(iter(ROOMS))
        zone = (50, 50, 1820, 980)
        canvas = render_temperature_canvas(1920, 1080, zone, {}, room_id)
        mask = np.zeros((1080, 1920), dtype=np.uint8)
        points = np.rint(projection_points(room_id, 1820, 980)).astype(np.int32) + [50, 50]
        cv2.fillPoly(mask, [points.astype(np.int32)], 1)
        self.assertTrue(np.all(canvas[mask == 1] == 255))
        self.assertFalse(render_temperature_canvas(1920, 1080, zone, {}).any())

    def test_selection_preserves_other_room_temperature(self):
        import numpy as np
        a, b = list(ROOMS)[:2]
        values = {ROOMS[a]['code']: 21, ROOMS[b]['code']: 24}
        plain = render_temperature_canvas(1920, 1080, (50, 50, 1820, 980), values)
        selected = render_temperature_canvas(1920, 1080, (50, 50, 1820, 980), values, a)
        b_mask = np.all(plain == temperature_color(24), axis=2)
        self.assertTrue(b_mask.any())
        np.testing.assert_array_equal(selected[b_mask], plain[b_mask])
        self.assertTrue(np.any(selected != plain))

    def test_canvas_is_black_without_measurements(self):
        canvas = render_temperature_canvas(1920, 1080, (50, 50, 1820, 980), {})
        self.assertFalse(canvas.any())

    def test_canvas_contains_only_measured_room_color_and_black(self):
        import cv2
        import numpy as np

        room_id = next(iter(ROOMS))
        color = temperature_color(24)
        canvas = render_temperature_canvas(1920, 1080, (50, 50, 1820, 980),
                                           {ROOMS[room_id]["code"]: 24})
        mask = np.zeros((1080, 1920), dtype=np.uint8)
        points = np.rint(projection_points(room_id, 1820, 980)).astype(np.int32) + [50, 50]
        cv2.fillPoly(mask, [points.astype(np.int32)], 1)
        self.assertTrue(np.all(canvas[mask == 0] == 0))
        self.assertTrue(np.all(canvas[mask == 1] == color))
        self.assertFalse(render_temperature_canvas(1920, 1080, (50, 50, 1820, 980), {}).any())

    def test_scale_anchors_and_saturation(self):
        self.assertEqual(temperature_color(12), (235, 99, 37))
        self.assertEqual(temperature_color(21), (94, 197, 34))
        self.assertEqual(temperature_color(30), (68, 68, 239))
        self.assertEqual(temperature_color(-10), temperature_color(12))
        self.assertEqual(temperature_color(50), temperature_color(30))

    def test_continuous_gradient(self):
        for low, high in zip([stop["temperature"] for stop in TEMPERATURE_SCALE], [stop["temperature"] for stop in TEMPERATURE_SCALE][1:]):
            expected = tuple(round((a + b) / 2) for a, b in zip(temperature_color(low), temperature_color(high)))
            self.assertEqual(temperature_color((low + high) / 2), expected)
        self.assertEqual(temperature_color(20.999), temperature_color(21.001))

    def test_missing_measurement_is_black(self):
        for value in (None, float('nan'), float('inf'), '21', True):
            self.assertEqual(temperature_color(value), (0, 0, 0))

    def test_validate_room_codes_and_clear_all(self):
        self.assertEqual(validate_temperatures({'03-23-N': 21}), {'03-23-N': 21})
        self.assertEqual(validate_temperatures({}), {})
        for values in (None, [], {'unknown': 21}, {'03-23-N': '21'}, {'03-23-N': True}, {'03-23-N': float('nan')}):
            with self.assertRaises(ValueError):
                validate_temperatures(values)


if __name__ == "__main__":
    unittest.main()
