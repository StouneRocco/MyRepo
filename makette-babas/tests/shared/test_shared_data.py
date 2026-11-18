"""Cohérence des données partagées : catalogue N3, plans du site, échelle thermique."""
import json
import unittest
import xml.etree.ElementTree as ET

from tests import FIXTURES, ROOT

CATALOG = json.loads((ROOT / 'shared' / 'plan-n3.json').read_text(encoding='utf-8'))
SCALE = json.loads((ROOT / 'shared' / 'temperature-scale.json').read_text(encoding='utf-8'))


def svg_rooms(path):
    return {element.get('data-space-id'): element for element in ET.parse(path).getroot().iter()
            if element.tag.endswith('polygon') and element.get('data-selectable') == 'true'}


class PlanCatalogTests(unittest.TestCase):
    def test_rooms_have_unique_ids_and_n3_codes(self):
        ids = [room['id'] for room in CATALOG['rooms']]
        codes = [room['code'] for room in CATALOG['rooms']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(codes), len(set(codes)))
        self.assertTrue(all(code.startswith('03-') for code in codes))
        self.assertTrue(all(room['name'].strip() for room in CATALOG['rooms']))

    def test_polygons_lie_inside_declared_svg_bounds(self):
        x0, y0, x1, y1 = CATALOG['svgBounds']
        for room in CATALOG['rooms']:
            self.assertGreaterEqual(len(room['points']), 3, room['code'])
            for x, y in room['points']:
                self.assertTrue(x0 <= x <= x1 and y0 <= y <= y1, room['code'])

    def test_image_bounds_are_normalized_and_ordered(self):
        x0, y0, x1, y1 = CATALOG['imageBounds']
        self.assertTrue(0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1)

    def test_site_plan_n3_selects_the_same_rooms_as_the_projector(self):
        rooms = svg_rooms(ROOT / 'frontend' / 'public' / 'plans' / 'N3.svg')
        self.assertEqual(set(rooms), {room['id'] for room in CATALOG['rooms']})
        for room in CATALOG['rooms']:
            self.assertEqual(rooms[room['id']].get('data-room-code'), room['code'])

    def test_n4_codes_are_distinct_from_n3_codes(self):
        # Les badgeages associent chaque code à un seul étage.
        n4 = svg_rooms(ROOT / 'frontend' / 'public' / 'plans' / 'N4.svg')
        codes = [room.get('data-room-code') for room in n4.values()]
        self.assertTrue(codes)
        self.assertEqual(len(codes), len(set(codes)))
        self.assertTrue(all(code.startswith('04-') for code in codes))
        self.assertFalse(set(codes) & {room['code'] for room in CATALOG['rooms']})


class TemperatureScaleTests(unittest.TestCase):
    def test_scale_runs_from_12_blue_through_21_green_to_30_red(self):
        temperatures = [stop['temperature'] for stop in SCALE]
        self.assertEqual(temperatures, sorted(set(temperatures)))
        self.assertEqual((temperatures[0], temperatures[-1]), (12, 30))
        colors = {stop['temperature']: stop['color'] for stop in SCALE}
        self.assertEqual(colors[21], [34, 197, 94])
        self.assertGreater(colors[12][2], colors[12][0])
        self.assertGreater(colors[30][0], colors[30][2])

    def test_colors_are_rgb_bytes(self):
        for stop in SCALE:
            self.assertEqual(len(stop['color']), 3)
            self.assertTrue(all(isinstance(value, int) and 0 <= value <= 255 for value in stop['color']))

    def test_projector_matches_shared_color_samples(self):
        # Le même fichier est vérifié côté site (tests/frontend/heatmap.test.js).
        from room_projection import temperature_color
        samples = json.loads((FIXTURES / 'temperature-colors.json').read_text(encoding='utf-8'))['samples']
        for sample in samples:
            bgr = temperature_color(sample['temperature'])
            # Python arrondit les demi-unités au pair, JavaScript vers le haut : écart toléré d'une unité.
            for actual, expected in zip(reversed(bgr), sample['rgb']):
                self.assertLessEqual(abs(actual - expected), 1, sample)


if __name__ == '__main__':
    unittest.main()
