# -*- coding:utf-8 -*-
"""
B2 per-task timeout_sec 配置单元测试

覆盖：
- cron_validator: 合法值、边界值、非法值、空值（默认 NULL）
- ensure_business_tables: cron_infos.timeout_sec 列存在性
- cron_service: apply_normalized_to_model 正确写入 timeout_sec
"""
import importlib
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load_cron_validator():
    return importlib.import_module('app.services.cron_validator')


_CRON_CONFIG = {'block_private_ip': '0', 'url_ssrf_observe_only': '0', 'url_allow_hosts': ''}


def _base_form(**overrides):
    """构造一个合法的基础表单，可通过 overrides 修改任意字段。"""
    form = {
        'task_name': 'test_b2_task',
        'task_keyword': 'unit test for B2',
        'ds_ms': '2',
        'day': '*',
        'day_of_week': '*',
        'hour': '*',
        'minute': '*/5',
        'second': '0',
        'req_url': 'http://example.com/',
        'req_method': 'GET',
        'req_body': '',
    }
    form.update(overrides)
    return form


class TestTimeoutSecValidator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.validator = _load_cron_validator()

    def _validate(self, **form_overrides):
        form = _base_form(**form_overrides)
        return self.validator.validate_cron_form(form, is_dev=0, cron_config=_CRON_CONFIG)

    # 合法值
    def test_valid_timeout_1(self):
        err, normalized, _ = self._validate(timeout_sec='1')
        self.assertIsNone(err)
        self.assertEqual(normalized['timeout_sec'], 1)

    def test_valid_timeout_60(self):
        err, normalized, _ = self._validate(timeout_sec='60')
        self.assertIsNone(err)
        self.assertEqual(normalized['timeout_sec'], 60)

    def test_valid_timeout_120(self):
        err, normalized, _ = self._validate(timeout_sec='120')
        self.assertIsNone(err)
        self.assertEqual(normalized['timeout_sec'], 120)

    # 边界：留空 → None
    def test_empty_timeout_becomes_none(self):
        err, normalized, _ = self._validate(timeout_sec='')
        self.assertIsNone(err)
        self.assertIsNone(normalized['timeout_sec'])

    def test_none_timeout_becomes_none(self):
        form = _base_form()
        form.pop('timeout_sec', None)
        err, normalized, _ = self.validator.validate_cron_form(form, is_dev=0, cron_config=_CRON_CONFIG)
        self.assertIsNone(err)
        self.assertIsNone(normalized.get('timeout_sec'))

    # 非法值
    def test_invalid_timeout_zero(self):
        err, _, field = self._validate(timeout_sec='0')
        self.assertIsNotNone(err)
        self.assertEqual(field, 'timeout_sec')

    def test_invalid_timeout_negative(self):
        err, _, field = self._validate(timeout_sec='-1')
        self.assertIsNotNone(err)
        self.assertEqual(field, 'timeout_sec')

    def test_invalid_timeout_over_max(self):
        err, _, field = self._validate(timeout_sec='121')
        self.assertIsNotNone(err)
        self.assertEqual(field, 'timeout_sec')

    def test_invalid_timeout_non_integer(self):
        err, _, field = self._validate(timeout_sec='abc')
        self.assertIsNotNone(err)
        self.assertEqual(field, 'timeout_sec')

    def test_invalid_timeout_float(self):
        err, _, field = self._validate(timeout_sec='5.5')
        self.assertIsNotNone(err)
        self.assertEqual(field, 'timeout_sec')


class TestCronInfosTimeoutSecColumn(unittest.TestCase):
    """确保 CronInfos 模型有 timeout_sec 列（B2-1 验收）。"""

    def test_model_has_timeout_sec(self):
        from datas.model.cron_infos import CronInfos
        self.assertTrue(
            hasattr(CronInfos, 'timeout_sec'),
            'CronInfos 模型缺少 timeout_sec 字段',
        )

    def test_ensure_tables_ddl_contains_timeout_sec(self):
        """ensure_business_tables.py 中须有 timeout_sec 补列语句。"""
        import inspect
        import scripts.ensure_business_tables as etm
        src = inspect.getsource(etm)
        self.assertIn('timeout_sec', src)


class TestApplyNormalizedTimeout(unittest.TestCase):
    """cron_service.apply_normalized_to_model 正确写入 timeout_sec。"""

    def _make_normalized(self, timeout_sec=None):
        return {
            'task_name': 'test', 'task_keyword': 'kw',
            'run_date': '', 'day_of_week': '*', 'day': '*',
            'hour': '*', 'minute': '*/5', 'second': '0',
            'req_url': 'http://127.0.0.1/', 'req_method': 'GET', 'req_body': '',
            'timeout_sec': timeout_sec,
        }

    def test_apply_timeout_value(self):
        from app.services.cron_service import apply_normalized_to_model
        from datas.model.cron_infos import CronInfos
        cif = CronInfos()
        apply_normalized_to_model(cif, self._make_normalized(timeout_sec=30))
        self.assertEqual(cif.timeout_sec, 30)

    def test_apply_timeout_none(self):
        from app.services.cron_service import apply_normalized_to_model
        from datas.model.cron_infos import CronInfos
        cif = CronInfos()
        apply_normalized_to_model(cif, self._make_normalized(timeout_sec=None))
        self.assertIsNone(cif.timeout_sec)


if __name__ == '__main__':
    unittest.main()
