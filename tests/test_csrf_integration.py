# -*- coding: utf-8 -*-
"""CSRF 全链路集成测试（requests.Session，不依赖浏览器）。

回归防护：
- js-ajax-form 的 AJAX 提交若未在 POST body 中包含 csrf_token，服务端应拒绝（errcode=1）
- 带正确 csrf_token 的提交应通过 CSRF 校验（errcode=0 或业务层错误）

测试方式：
  - 通过 requests.Session 模拟完整 cookie/CSRF 流程（GET 页面 → 提取 token → POST）
  - 默认跳过（SKIP_INTEGRATION=1 或服务未运行），可通过环境变量 CRONPILOT_BASE_URL 指定地址

运行示例（本地服务 :5001）：
  CRONPILOT_BASE_URL=http://127.0.0.1:5001 python -m unittest tests.test_csrf_integration -v

运行示例（Docker :5860）：
  CRONPILOT_BASE_URL=http://127.0.0.1:5860 python -m unittest tests.test_csrf_integration -v
"""
import os
import re
import unittest

BASE_URL = os.environ.get('CRONPILOT_BASE_URL', '').rstrip('/')
LOGIN_USER = os.environ.get('CRONPILOT_USER', 'admin')
LOGIN_PASS = os.environ.get('CRONPILOT_PASS', 'changeme')

_SKIP_REASON = None
if not BASE_URL:
    _SKIP_REASON = 'CRONPILOT_BASE_URL not set; skipping integration tests'
else:
    try:
        import requests as _req
        _req.get(BASE_URL + '/rbac/login', timeout=3)
    except Exception as e:
        _SKIP_REASON = 'Service at %s unreachable: %s' % (BASE_URL, e)


def _extract_csrf(html):
    m = re.search(r'<meta\s+name=["\']csrf-token["\']\s+content=["\']([^"\']+)["\']', html)
    if not m:
        m = re.search(r'<meta\s+content=["\']([^"\']+)["\']\s+name=["\']csrf-token["\']', html)
    return m.group(1) if m else ''


@unittest.skipIf(_SKIP_REASON, _SKIP_REASON)
class TestCsrfGroupsAdd(unittest.TestCase):
    """groups/add：带/不带 csrf_token 行为差异断言。"""

    @classmethod
    def setUpClass(cls):
        import requests
        cls.session = requests.Session()
        # 1. 获取登录页 CSRF
        r = cls.session.get(BASE_URL + '/rbac/login', timeout=5)
        login_csrf = _extract_csrf(r.text)
        # 2. 登录
        cls.session.post(
            BASE_URL + '/rbac/login',
            data={'username': LOGIN_USER, 'password': LOGIN_PASS, 'csrf_token': login_csrf},
            allow_redirects=False,
            timeout=5,
        )

    def _get_page_csrf(self, path):
        r = self.session.get(BASE_URL + path, timeout=5)
        self.assertEqual(r.status_code, 200, 'GET %s failed: %s' % (path, r.status_code))
        token = _extract_csrf(r.text)
        self.assertTrue(token, 'No csrf-token meta tag found in %s' % path)
        return token

    def test_post_without_csrf_token_is_rejected(self):
        """不带 csrf_token 的 POST 必须被拒绝（errcode != 0 或非 200）。"""
        # 注意：不取 csrf token，直接 POST
        resp = self.session.post(
            BASE_URL + '/rbac/groups/add',
            data={'name': 'IntegrationNoToken', 'description': 'should fail'},
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
            timeout=5,
        )
        self.assertIn(resp.status_code, (200, 400, 403),
                      'Unexpected status %s' % resp.status_code)
        if resp.status_code == 200:
            data = resp.get_json() if hasattr(resp, 'get_json') else resp.json()
            self.assertNotEqual(data.get('errcode'), 0,
                                'POST without csrf_token should not succeed: %s' % data)
            self.assertIn('csrf', (data.get('errmsg') or '').lower(),
                          'errmsg should mention csrf when token is missing: %s' % data)

    def test_post_with_csrf_token_passes_csrf_check(self):
        """带正确 csrf_token 的 POST 必须通过 CSRF 校验（errcode 由业务层决定，非 csrf 错误）。"""
        csrf = self._get_page_csrf('/rbac/groups/add')
        resp = self.session.post(
            BASE_URL + '/rbac/groups/add',
            data={'name': 'IntegrationWithToken', 'description': 'csrf pass test', 'csrf_token': csrf},
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
            timeout=5,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # CSRF 通过后：errcode=0（创建成功）或业务错误（如重名）；但 errmsg 不应提 csrf
        if data.get('errcode') != 0:
            self.assertNotIn('csrf', (data.get('errmsg') or '').lower(),
                             'Should not be a CSRF error when token is provided: %s' % data)


@unittest.skipIf(_SKIP_REASON, _SKIP_REASON)
class TestCsrfUsersAdd(unittest.TestCase):
    """users/add：带/不带 csrf_token 行为差异断言。"""

    @classmethod
    def setUpClass(cls):
        import requests
        cls.session = requests.Session()
        r = cls.session.get(BASE_URL + '/rbac/login', timeout=5)
        login_csrf = _extract_csrf(r.text)
        cls.session.post(
            BASE_URL + '/rbac/login',
            data={'username': LOGIN_USER, 'password': LOGIN_PASS, 'csrf_token': login_csrf},
            allow_redirects=False,
            timeout=5,
        )

    def _get_page_csrf(self, path):
        r = self.session.get(BASE_URL + path, timeout=5)
        self.assertEqual(r.status_code, 200)
        token = _extract_csrf(r.text)
        self.assertTrue(token)
        return token

    def test_post_without_csrf_token_is_rejected(self):
        resp = self.session.post(
            BASE_URL + '/rbac/users/add',
            data={'username': 'integration_no_token', 'role': 'operator'},
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
            timeout=5,
        )
        self.assertIn(resp.status_code, (200, 400, 403))
        if resp.status_code == 200:
            data = resp.json()
            self.assertNotEqual(data.get('errcode'), 0)
            self.assertIn('csrf', (data.get('errmsg') or '').lower(),
                          'Should mention csrf: %s' % data)

    def test_post_with_csrf_token_passes_csrf_check(self):
        csrf = self._get_page_csrf('/rbac/users/add')
        resp = self.session.post(
            BASE_URL + '/rbac/users/add',
            data={'username': 'integration_with_token', 'role': 'admin', 'csrf_token': csrf},
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
            timeout=5,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        if data.get('errcode') != 0:
            self.assertNotIn('csrf', (data.get('errmsg') or '').lower(),
                             'Should not be a CSRF error: %s' % data)


if __name__ == '__main__':
    unittest.main()
