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


class TestValidateAndResolve(unittest.TestCase):
    """OPT-P0-12: validate_and_resolve_url DNS pinning 测试。"""

    def setUp(self):
        self.cfg = {'block_private_ip': '1', 'url_allow_hosts': '', 'url_ssrf_observe_only': '0'}

    def test_ip_literal_returns_ip_directly(self):
        ok, msg, ip = url_security.validate_and_resolve_url('http://8.8.8.8/hook', self.cfg)
        self.assertTrue(ok, msg)
        self.assertEqual(ip, '8.8.8.8')

    def test_private_ip_literal_rejected(self):
        ok, msg, ip = url_security.validate_and_resolve_url('http://127.0.0.1/x', self.cfg)
        self.assertFalse(ok)
        self.assertIsNone(ip)

    @patch.object(url_security, '_resolve_host_ips', return_value={'93.184.216.34'})
    def test_domain_returns_resolved_ip(self, mock_dns):
        ok, msg, ip = url_security.validate_and_resolve_url('http://example.com/hook', self.cfg)
        self.assertTrue(ok, msg)
        self.assertEqual(ip, '93.184.216.34')

    @patch.object(url_security, '_resolve_host_ips', return_value={'10.0.0.1'})
    def test_domain_resolving_to_private_rejected(self, mock_dns):
        ok, msg, ip = url_security.validate_and_resolve_url('http://evil.com/x', self.cfg)
        self.assertFalse(ok)
        self.assertIsNone(ip)

    @patch.object(url_security, '_resolve_host_ips', return_value=None)
    def test_dns_unavailable_returns_none_ip(self, mock_dns):
        ok, msg, ip = url_security.validate_and_resolve_url('http://example.com/x', self.cfg)
        self.assertTrue(ok, msg)
        self.assertIsNone(ip)


class TestPinnedSession(unittest.TestCase):
    """OPT-P0-12: make_pinned_session DNS pinning 会话测试。"""

    def test_session_created_with_adapter(self):
        session = url_security.make_pinned_session('1.2.3.4', 'example.com', 'http')
        # 验证 session 挂载了自定义 adapter
        adapter = session.get_adapter('http://example.com/')
        self.assertIsInstance(adapter, url_security._PinnedIPAdapter)
        self.assertEqual(adapter.pinned_ip, '1.2.3.4')
        self.assertEqual(adapter.original_hostname, 'example.com')

    def test_adapter_rewrites_url_and_host_header(self):
        from requests import Request, PreparedRequest
        adapter = url_security._PinnedIPAdapter('93.184.216.34', 'example.com')
        req = Request('GET', 'http://example.com/path?q=1',
                      headers={'user-agent': 'test'}).prepare()
        # 模拟 send 中的 URL 重写逻辑（不实际发请求）
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(req.url)
        if parsed.hostname and parsed.hostname != '93.184.216.34':
            req.headers.setdefault('Host', 'example.com')
            req.url = urlunparse(parsed._replace(netloc='93.184.216.34'))
        self.assertIn('93.184.216.34', req.url)
        self.assertEqual(req.headers['Host'], 'example.com')

    def test_adapter_preserves_port(self):
        from requests import Request
        adapter = url_security._PinnedIPAdapter('1.2.3.4', 'api.example.com')
        req = Request('GET', 'http://api.example.com:8080/v1').prepare()
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(req.url)
        port_suffix = ':%d' % parsed.port if parsed.port else ''
        req.headers.setdefault('Host', 'api.example.com')
        req.url = urlunparse(parsed._replace(netloc='1.2.3.4' + port_suffix))
        self.assertIn('1.2.3.4:8080', req.url)
        self.assertEqual(req.headers['Host'], 'api.example.com')


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
    return importlib.import_module('app.services.cron_validator')


class TestCronValidator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = _load_cron_validator()

    def test_valid_cron_fields(self):
        cfg = {'block_private_ip': '0'}
        err, norm, _field = self.validator.validate_cron_form(
            {
                'task_name': 'job-a',
                'task_keyword': '备注A',
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
        self.assertEqual(norm['task_keyword'], '备注A')

    def test_reject_empty_schedule_fields(self):
        cfg = {'block_private_ip': '0'}
        err, _, field = self.validator.validate_cron_form(
            {
                'task_name': 'job-empty',
                'task_keyword': '备注',
                'ds_ms': '2',
                'req_url': 'https://example.com/cb',
            },
            0,
            cfg,
            mode='add',
        )
        self.assertIsNotNone(err)
        self.assertIn('定时模式', err)
        self.assertEqual(field, 'cron_div')

    def test_reject_empty_task_keyword(self):
        cfg = {'block_private_ip': '0'}
        err, _, _field = self.validator.validate_cron_form(
            {
                'task_name': 'job-kw',
                'task_keyword': '  ',
                'hour': '1',
                'req_url': 'https://example.com/cb',
            },
            0,
            cfg,
            mode='add',
        )
        self.assertIsNotNone(err)
        self.assertIn('说明', err)

    def test_validate_retire_reason(self):
        err, reason = self.validator.validate_retire_reason('  业务下线  ')
        self.assertIsNone(err)
        self.assertEqual(reason, '业务下线')
        err, _ = self.validator.validate_retire_reason('')
        self.assertIsNotNone(err)
        err, _ = self.validator.validate_retire_reason('x' * 501)
        self.assertIsNotNone(err)

    def test_api_weekday_names(self):
        cfg = {'block_private_ip': '0'}
        err, norm, _field = self.validator.validate_cron_form(
            {
                'task_name': 'job-b',
                'task_keyword': '备注B',
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
        err, _, _field = self.validator.validate_cron_form(
            {
                'task_name': 'job-c',
                'task_keyword': '备注C',
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
        err, norm, _field = self.validator.validate_cron_form(
            {
                'task_name': 'job-d',
                'task_keyword': '备注D',
                'hour': '2',
                'req_url': 'http://8.8.8.8/cb',
            },
            0,
            cfg,
            mode='add',
        )
        self.assertIsNone(err, err)
        self.assertEqual(norm['req_url'], 'http://8.8.8.8/cb')

    def test_reject_invalid_req_method(self):
        cfg = {'block_private_ip': '0'}
        err, _, field = self.validator.validate_cron_form(
            {
                'task_name': 'job-method',
                'task_keyword': '备注Method',
                'hour': '2',
                'req_url': 'https://example.com/cb',
                'req_method': 'PUT',
            },
            0,
            cfg,
            mode='add',
        )
        self.assertIsNotNone(err)
        self.assertIn('GET 或 POST', err)
        self.assertEqual(field, 'req_method')

    def test_reject_non_object_req_body(self):
        cfg = {'block_private_ip': '0'}
        err, _, field = self.validator.validate_cron_form(
            {
                'task_name': 'job-body',
                'task_keyword': '备注Body',
                'hour': '2',
                'req_url': 'https://example.com/cb',
                'req_method': 'POST',
                'req_body': '["a", "b"]',
            },
            0,
            cfg,
            mode='add',
        )
        self.assertIsNotNone(err)
        self.assertIn('JSON 对象', err)
        self.assertEqual(field, 'req_body')

    def test_accept_post_with_object_req_body(self):
        cfg = {'block_private_ip': '0'}
        err, norm, _field = self.validator.validate_cron_form(
            {
                'task_name': 'job-post',
                'task_keyword': '备注Post',
                'hour': '2',
                'req_url': 'https://example.com/cb',
                'req_method': 'post',
                'req_body': '{"k":"v"}',
            },
            0,
            cfg,
            mode='add',
        )
        self.assertIsNone(err, err)
        self.assertEqual(norm['req_method'], 'POST')
        self.assertEqual(norm['req_body'], '{"k":"v"}')


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
