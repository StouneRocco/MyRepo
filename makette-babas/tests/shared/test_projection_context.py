"""Contexte du bandeau projeté : même validation dans le backend et le récepteur."""
import unittest

from projection_context import validate_context

CODES = {'03-23-N', '03-24-N'}
VALID = {'day': '2026-06-30', 'minute': 1435, 'roomCode': '03-23-N',
         'roomStats': {'min': 20, 'mean': 24.5, 'max': 26}, 'estimated': ['03-23-N']}


class ProjectionContextTests(unittest.TestCase):
    def test_complete_context_is_returned_normalized(self):
        self.assertEqual(validate_context(VALID, CODES), VALID)

    def test_empty_context_gets_defaults(self):
        self.assertEqual(validate_context({}, CODES),
                         {'day': '', 'minute': 0, 'estimated': [], 'roomCode': None, 'roomStats': {}})

    def test_unknown_keys_are_dropped(self):
        self.assertNotIn('extra', validate_context({**VALID, 'extra': '<script>'}, CODES))

    def test_missing_statistics_are_allowed(self):
        stats = {'min': None, 'mean': None, 'max': None}
        self.assertEqual(validate_context({**VALID, 'roomStats': stats}, CODES)['roomStats'], stats)

    def test_minute_must_be_an_integer_of_the_day(self):
        for minute in (-1, 1440, True, 60.0, '60', None):
            with self.subTest(minute=minute), self.assertRaises(ValueError):
                validate_context({**VALID, 'minute': minute}, CODES)
        self.assertEqual(validate_context({**VALID, 'minute': 0}, CODES)['minute'], 0)

    def test_day_must_be_an_iso_date(self):
        for day in ('30/06/2026', '2026-02-30', 'bad'):
            with self.subTest(day=day), self.assertRaises(ValueError):
                validate_context({**VALID, 'day': day}, CODES)

    def test_rooms_must_belong_to_the_plan(self):
        for changed in ({'roomCode': 'unknown'}, {'estimated': ['unknown']}, {'estimated': '03-23-N'}):
            with self.subTest(changed), self.assertRaises(ValueError):
                validate_context({**VALID, **changed}, CODES)

    def test_statistics_must_be_finite_numbers_with_known_names(self):
        for stats in ({'mean': float('nan')}, {'max': float('inf')}, {'min': True}, {'mean': '24'},
                      {'median': 24}, []):
            with self.subTest(stats=stats), self.assertRaises(ValueError):
                validate_context({**VALID, 'roomStats': stats}, CODES)

    def test_non_dictionary_is_refused(self):
        for value in (None, [], 'context'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_context(value, CODES)


if __name__ == '__main__':
    unittest.main()
