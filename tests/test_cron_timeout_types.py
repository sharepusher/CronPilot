"""共享规范化必须接受真实 Schema 的 int 输出，拒绝非法类型而非截断。"""
import unittest

from app.api.schemas import CronUpsertIn
from app.services.cron_validator import normalize_cron_form


class TestCronTimeoutTypes(unittest.TestCase):
    def raw(self, **fields):
        return dict(task_name='timeout-probe', task_keyword='type regression', hour='12',
                    minute='0', req_url='https://8.8.8.8/probe', **fields)

    def normalize(self, raw):
        return normalize_cron_form(raw, 0, mode='add', api_mode=True)

    def test_real_schema_integer_and_repeated_normalization(self):
        for value in ('1', '5', '120'):
            data = CronUpsertIn().load(self.raw(timeout_sec=value))
            self.assertIs(type(data['timeout_sec']), int)
            error, normalized, field = self.normalize(data)
            self.assertIsNone(error)
            self.assertEqual(normalized['timeout_sec'], int(value))
            self.assertIsNone(self.normalize(normalized)[0])

    def test_missing_and_schema_default(self):
        for raw in (self.raw(), CronUpsertIn().load(self.raw())):
            error, normalized, field = self.normalize(raw)
            self.assertIsNone(error)
            self.assertIsNone(normalized['timeout_sec'])

    def test_valid_shared_values(self):
        for value, expected in ((5, 5), ('5', 5), (' 5 ', 5), (1, 1), (120, 120),
                                (None, None), ('', None), ('   ', None)):
            with self.subTest(value=value):
                error, normalized, field = self.normalize(self.raw(timeout_sec=value))
                self.assertIsNone(error)
                self.assertEqual(normalized['timeout_sec'], expected)
                self.assertIn(type(normalized['timeout_sec']), (int, type(None)))

    def test_invalid_shared_values_are_field_errors(self):
        for value in (0, '0', -1, 121, True, False, 5.5, '5.5', [], {}, 'bad'):
            with self.subTest(value=value):
                error, normalized, field = self.normalize(self.raw(timeout_sec=value))
                self.assertIsNotNone(error)
                self.assertIsNone(normalized)
                self.assertEqual(field, 'timeout_sec')

    def test_modern_schema_still_rejects_invalid_and_empty(self):
        from marshmallow import ValidationError
        for value in ('', '0', '121', 'bad', '5.5'):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                CronUpsertIn().load(self.raw(timeout_sec=value))
