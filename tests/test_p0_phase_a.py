# -*- coding:utf-8 -*-
"""Phase A (P0) 回归测试：不依赖真实 MySQL，使用内存/SQLite。"""
import importlib
import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load_module(mod_name, rel_path):
    path = os.path.join(ROOT, rel_path)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


import importlib.util  # noqa: E402

url_security = _load_module('url_security', 'app/services/url_security.py')
password_mod = _load_module('password_mod', 'app/auth/password.py')


class TestUrlSecurity(unittest.TestCase):
    def setUp(self):
        self.cfg = {'block_private_ip': '1', 'url_allow_hosts': '', 'url_ssrf_observe_only': '0'}

    def test_reject_localhost_ip(self):
        ok, msg = url_security.validate_callback_url('http://127.0.0.1/callback', self.cfg)
        self.assertFalse(ok)
        self.assertIn('本机', msg)

    def test_reject_metadata_range(self):
        ok, msg = url_security.validate_callback_url('http://169.254.169.254/latest', self.cfg)
        self.assertFalse(ok)

    def test_allow_public_ip_literal(self):
        ok, msg = url_security.validate_callback_url('http://8.8.8.8/hook', self.cfg)
        self.assertTrue(ok, msg)

    def test_whitelist_host(self):
        cfg = dict(self.cfg, url_allow_hosts='8.8.8.8')
        ok, _ = url_security.validate_callback_url('http://8.8.8.8/x', cfg)
        self.assertTrue(ok)
        ok, msg = url_security.validate_callback_url('http://1.1.1.1/x', cfg)
        self.assertFalse(ok)
        self.assertIn('白名单', msg)

    def test_observe_only_allows_private(self):
        cfg = dict(self.cfg, url_ssrf_observe_only='1')
        ok, msg = url_security.validate_callback_url('http://127.0.0.1/x', cfg)
        self.assertTrue(ok, msg)


class TestPassword(unittest.TestCase):
    def test_plaintext_legacy(self):
        self.assertTrue(password_mod.verify_login_password('secret', 'secret'))
        self.assertFalse(password_mod.verify_login_password('wrong', 'secret'))

    def test_hashed_password(self):
        hashed = password_mod.hash_password('secret')
        self.assertTrue(password_mod.is_hashed_password(hashed))
        self.assertTrue(password_mod.verify_login_password('secret', hashed))
        self.assertFalse(password_mod.verify_login_password('wrong', hashed))


def _load_cron_validator():
    import types
    if 'app.services.cron_validator' in sys.modules:
        return sys.modules['app.services.cron_validator']
    app = types.ModuleType('app')
    services = types.ModuleType('app.services')
    app.services = services
    services.url_security = url_security
    sys.modules['app'] = app
    sys.modules['app.services'] = services
    sys.modules['app.services.url_security'] = url_security
    path = os.path.join(ROOT, 'app/services/cron_validator.py')
    spec = importlib.util.spec_from_file_location(
        'app.services.cron_validator', path
    )
    mod = importlib.util.module_from_spec(spec)
    services.cron_validator = mod
    sys.modules['app.services.cron_validator'] = mod
    spec.loader.exec_module(mod)
    return mod


class TestCronValidator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = _load_cron_validator()

    def test_valid_cron_fields(self):
        cfg = {'block_private_ip': '0'}
        err, norm = self.validator.validate_cron_form(
            {
                'task_name': 'job-a',
                'hour': '8',
                'minute': '30',
                'req_url': 'https://example.com/cb',
            },
            0,
            cfg,
            mode='add',
        )
        self.assertIsNone(err, err)
        self.assertEqual(norm['hour'], '8')

    def test_api_weekday_names(self):
        cfg = {'block_private_ip': '0'}
        err, norm = self.validator.validate_cron_form(
            {
                'task_name': 'job-b',
                'day_of_week': 'mon,wed',
                'hour': '9',
                'req_url': 'https://example.com/cb',
            },
            0,
            cfg,
            mode='add',
            api_mode=True,
        )
        self.assertIsNone(err, err)
        self.assertEqual(norm['day_of_week'], 'mon,wed')

    def test_reject_ssrf_url(self):
        cfg = {'block_private_ip': '1', 'url_allow_hosts': ''}
        err, _ = self.validator.validate_cron_form(
            {
                'task_name': 'job-c',
                'hour': '1',
                'req_url': 'http://127.0.0.1/internal',
            },
            0,
            cfg,
            mode='add',
        )
        self.assertIsNotNone(err)

    def test_valid_with_public_ip_url(self):
        cfg = {'block_private_ip': '1', 'url_allow_hosts': ''}
        err, norm = self.validator.validate_cron_form(
            {
                'task_name': 'job-d',
                'hour': '2',
                'req_url': 'http://8.8.8.8/cb',
            },
            0,
            cfg,
            mode='add',
        )
        self.assertIsNone(err, err)
        self.assertEqual(norm['req_url'], 'http://8.8.8.8/cb')


class TestJsonContract(unittest.TestCase):
    def test_json_response_errcode_int(self):
        from datas.utils.json import json_response
        with patch('datas.utils.json.jsonify', side_effect=lambda x: x):
            payload, status = json_response(errcode=0, errmsg='ok', url='/x')
        self.assertEqual(status, 200)
        self.assertEqual(payload['errcode'], 0)
        self.assertEqual(payload['errmsg'], 'ok')


if __name__ == '__main__':
    unittest.main(verbosity=2)
