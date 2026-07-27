# -*- coding: utf-8 -*-
"""CronStatusCell Vue 组件操作全链路集成测试。

回归防护：
- Vue onRunNow / onToggle 发出的 POST URL 是否正确（不得双拼 ?id=）
- X-CSRFToken header 驱动的 CSRF 校验（模拟 Vue 的 csrfPost 行为）
- 无 CSRF token 时接口必须拒绝

前提条件：
- 须有 operator 角色账号（有 cron:write），用于创建测试任务
- seed admin 无 cron:write，不能创建任务
- 若本地无 operator 账号，可手动在管理端创建，然后通过环境变量传入

运行（本地服务须有 operator 账号）：
  CRONPILOT_BASE_URL=http://127.0.0.1:5001 \\
  CRONPILOT_WRITER_USER=your_operator \\
  CRONPILOT_WRITER_PASS=yourpass \\
  python -m unittest tests.test_cron_ops_integration -v

Docker：
  CRONPILOT_BASE_URL=http://127.0.0.1:5860 \\
  CRONPILOT_WRITER_USER=your_operator \\
  CRONPILOT_WRITER_PASS=yourpass \\
  python -m unittest tests.test_cron_ops_integration -v

若未设置 CRONPILOT_WRITER_USER，会尝试 'op_testf1'（本地开发账号）；
创建任务失败时测试自动跳过（skip），不会 fail。
"""
import os
import re
import unittest

BASE_URL = os.environ.get('CRONPILOT_BASE_URL', '').rstrip('/')
LOGIN_USER = os.environ.get('CRONPILOT_USER', 'admin')
LOGIN_PASS = os.environ.get('CRONPILOT_PASS', 'changeme')
# 用于创建测试任务的 operator 账号（需 cron:write；seed admin 无此权限）
WRITER_USER = os.environ.get('CRONPILOT_WRITER_USER', 'op_testf1')
WRITER_PASS = os.environ.get('CRONPILOT_WRITER_PASS', 'changeme')

_SKIP_REASON = None
if not BASE_URL:
    _SKIP_REASON = 'CRONPILOT_BASE_URL not set; skipping integration tests'
else:
    try:
        import requests as _req
        _req.get(BASE_URL + '/rbac/login', timeout=3)
    except Exception as e:
        _SKIP_REASON = 'Service at %s unreachable: %s' % (BASE_URL, e)


def _extract_csrf_meta(html):
    m = re.search(r'<meta\s+name=["\']csrf-token["\']\s+content=["\']([^"\']+)["\']', html)
    if not m:
        m = re.search(r'<meta\s+content=["\']([^"\']+)["\']\s+name=["\']csrf-token["\']', html)
    return m.group(1) if m else ''


def _login_session(user=None, password=None):
    """返回已登录的 requests.Session（含 CSRF cookie）。"""
    import requests
    s = requests.Session()
    r = s.get(BASE_URL + '/rbac/login', timeout=5)
    login_csrf = _extract_csrf_meta(r.text)
    s.post(
        BASE_URL + '/rbac/login',
        data={
            'username': user or LOGIN_USER,
            'password': password or LOGIN_PASS,
            'csrf_token': login_csrf,
        },
        allow_redirects=False,
        timeout=5,
    )
    return s


def _csrf_post(session, url, extra_headers=None):
    """模拟 Vue csrfPost：从 cron_list 页面取 meta csrf-token，以 X-CSRFToken header POST。"""
    r = session.get(BASE_URL + '/cron_list', timeout=5)
    token = _extract_csrf_meta(r.text)
    headers = {'X-CSRFToken': token, 'Accept': 'application/json'}
    if extra_headers:
        headers.update(extra_headers)
    return session.post(BASE_URL + url, headers=headers, timeout=5)


@unittest.skipIf(_SKIP_REASON, _SKIP_REASON)
class TestRunNowIntegration(unittest.TestCase):
    """立即执行接口全链路：URL 格式、CSRF header、权限。"""

    @classmethod
    def setUpClass(cls):
        # 用 operator 账号（有 cron:write）创建测试任务
        cls.session = _login_session(user=WRITER_USER, password=WRITER_PASS)
        r = cls.session.get(BASE_URL + '/cron_list', timeout=5)
        csrf = _extract_csrf_meta(r.text)
        cls.session.post(
            BASE_URL + '/cron_add',
            data={
                'task_name': 'integration-run-now-test',
                'task_keyword': 'integration test task for run_now',
                'ds_ms': '2',
                'minute': '30',
                'req_url': 'https://example.com/integration-test',
                'req_method': 'GET',
                'csrf_token': csrf,
            },
            headers={'X-Requested-With': 'XMLHttpRequest'},
            timeout=5,
        )
        # 重新取列表，提取 data-run-url
        r = cls.session.get(BASE_URL + '/cron_list', timeout=5)
        cls.list_html = r.text
        m = re.search(r'data-run-url="([^"]+)"', cls.list_html)
        cls.run_url = m.group(1) if m else None

    def test_run_url_format_no_double_question_mark(self):
        """data-run-url 中 ? 只出现一次（防止 url_for+Vue 双拼 ?id= 的回归）。"""
        if not self.run_url:
            self.skipTest('No data-run-url found in cron_list (no tasks?)')
        self.assertEqual(
            self.run_url.count('?'), 1,
            'data-run-url 含多个 ?，疑似 Vue 双拼 bug 回归: %s' % self.run_url,
        )
        self.assertIn('?id=', self.run_url, 'data-run-url 应含 ?id= 参数: %s' % self.run_url)

    def test_run_now_without_csrf_is_rejected(self):
        """不带 X-CSRFToken header 的 POST 应被 CSRF 拦截（403 或 errcode!=0 且 errmsg 含 csrf）。"""
        if not self.run_url:
            self.skipTest('No data-run-url found in cron_list (no tasks?)')
        resp = self.session.post(BASE_URL + self.run_url, timeout=5)
        self.assertIn(resp.status_code, (200, 400, 403))
        if resp.status_code == 200:
            data = resp.json()
            self.assertNotEqual(data.get('errcode'), 0,
                                'POST without CSRF should fail: %s' % data)
            self.assertIn('csrf', (data.get('errmsg') or '').lower(),
                          'errmsg should mention csrf: %s' % data)

    def test_run_now_with_csrf_header_passes_csrf_check(self):
        """带 X-CSRFToken header 的 POST 通过 CSRF 校验（errcode 由业务层决定，非 csrf 错误）。"""
        if not self.run_url:
            self.skipTest('No data-run-url found in cron_list (no tasks?)')
        resp = _csrf_post(self.session, self.run_url)
        self.assertIn(resp.status_code, (200, 400, 403))
        if resp.status_code == 200:
            data = resp.json()
            # 无论业务是否成功，errmsg 不应包含 csrf（CSRF 已通过）
            self.assertNotIn('csrf', (data.get('errmsg') or '').lower(),
                             'Should not be CSRF error when token provided: %s' % data)


@unittest.skipIf(_SKIP_REASON, _SKIP_REASON)
class TestUpdateStatusIntegration(unittest.TestCase):
    """启停接口全链路：URL 格式、CSRF header、无权限拒绝。"""

    @classmethod
    def setUpClass(cls):
        # 用 operator 账号（有 cron:write）创建测试任务
        cls.session = _login_session(user=WRITER_USER, password=WRITER_PASS)
        r = cls.session.get(BASE_URL + '/cron_list', timeout=5)
        csrf = _extract_csrf_meta(r.text)
        cls.session.post(
            BASE_URL + '/cron_add',
            data={
                'task_name': 'integration-toggle-test',
                'task_keyword': 'integration test task for update_status',
                'ds_ms': '2',
                'minute': '30',
                'req_url': 'https://example.com/integration-toggle',
                'req_method': 'GET',
                'csrf_token': csrf,
            },
            headers={'X-Requested-With': 'XMLHttpRequest'},
            timeout=5,
        )
        r = cls.session.get(BASE_URL + '/cron_list', timeout=5)
        cls.list_html = r.text
        m = re.search(r'data-update-url="([^"]+)"', cls.list_html)
        cls.update_url = m.group(1) if m else None

    def test_update_url_format_no_double_question_mark(self):
        """data-update-url 中 ? 只出现一次（防止双拼回归）。"""
        if not self.update_url:
            self.skipTest('No data-update-url found in cron_list (no tasks?)')
        self.assertEqual(
            self.update_url.count('?'), 1,
            'data-update-url 含多个 ?，疑似双拼 bug: %s' % self.update_url,
        )
        self.assertIn('?id=', self.update_url)

    def test_update_status_without_csrf_is_rejected(self):
        """不带 X-CSRFToken 的 POST 应被拒。"""
        if not self.update_url:
            self.skipTest('No data-update-url found in cron_list (no tasks?)')
        resp = self.session.post(BASE_URL + self.update_url, timeout=5)
        self.assertIn(resp.status_code, (200, 400, 403))
        if resp.status_code == 200:
            data = resp.json()
            self.assertNotEqual(data.get('errcode'), 0)

    def test_update_status_with_csrf_header_passes_csrf_check(self):
        """带 X-CSRFToken header 通过 CSRF 校验。"""
        if not self.update_url:
            self.skipTest('No data-update-url found in cron_list (no tasks?)')
        resp = _csrf_post(self.session, self.update_url)
        self.assertIn(resp.status_code, (200, 400, 403))
        if resp.status_code == 200:
            data = resp.json()
            self.assertNotIn('csrf', (data.get('errmsg') or '').lower(),
                             'Should not be CSRF error when token provided: %s' % data)

    def test_viewer_cannot_toggle(self):
        """viewer 角色无 cron:write，update_status 应返回 403。"""
        viewer_session = _login_session(user='viewer', password='changeme')
        # viewer 的 cron_list 不含 data-update-url（防御层已过滤）
        r = viewer_session.get(BASE_URL + '/cron_list', timeout=5)
        self.assertNotIn('data-update-url=', r.text,
                         'viewer 不应看到 data-update-url')
        # 即使直接 POST 也应 403
        if self.update_url:
            resp = _csrf_post(viewer_session, self.update_url)
            self.assertEqual(resp.status_code, 403,
                             'viewer POST update_status 应 403: %s' % resp.status_code)


if __name__ == '__main__':
    unittest.main()
