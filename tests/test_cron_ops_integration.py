# -*- coding: utf-8 -*-
"""Redesign Dashboard 任务操作全链路集成测试。

回归防护：
- Dashboard 的立即执行/启停操作是否携带唯一 task id
- X-CSRFToken header 驱动的 CSRF 校验（模拟 Dashboard 的 $.post 行为）
- 无 CSRF token 时接口必须拒绝

前提条件：
- 须有 operator 角色账号（有 cron:write），用于创建测试任务
- seed admin 无 cron:write，不能创建任务
- 若本地无 operator 账号，可手动在管理端创建，然后通过环境变量传入

运行（本地服务须有 operator 账号，自动探测 :5001/:5860）：
  python -m unittest tests.test_cron_ops_integration -v

指定地址 / 账号：
  CRONPILOT_BASE_URL=http://... CRONPILOT_WRITER_USER=op CRONPILOT_WRITER_PASS=pw \\
  python -m unittest tests.test_cron_ops_integration -v

强制跳过：
  SKIP_INTEGRATION=1 python -m unittest tests.test_cron_ops_integration -v

若未设置 CRONPILOT_WRITER_USER，会尝试 'op_testf1'（本地开发账号）。
服务可用但测试任务创建失败时必须失败，不能以 skip 掩盖验证缺口。
"""
import html
import os
import re
import time
import unittest

BASE_URL = os.environ.get('CRONPILOT_BASE_URL', '').rstrip('/')
LOGIN_USER = os.environ.get('CRONPILOT_USER', 'admin')
LOGIN_PASS = os.environ.get('CRONPILOT_PASS', 'changeme')
# 用于创建测试任务的 operator 账号（需 cron:write；seed admin 无此权限）
WRITER_USER = os.environ.get('CRONPILOT_WRITER_USER', 'op_testf1')
WRITER_PASS = os.environ.get('CRONPILOT_WRITER_PASS', 'changeme')
# viewer 账号（无 cron:write；用于权限拒绝断言）
VIEWER_USER = os.environ.get('CRONPILOT_VIEWER_USER', 'integration-viewer')
VIEWER_PASS = os.environ.get('CRONPILOT_VIEWER_PASS', 'changeme')

_SKIP_REASON = None
if os.environ.get('SKIP_INTEGRATION', '').lower() in ('1', 'true', 'yes'):
    _SKIP_REASON = 'SKIP_INTEGRATION=1; skipping integration tests'
elif not BASE_URL:
    import requests as _req
    for _port in (5001, 5860):
        try:
            _req.get('http://127.0.0.1:%d/rbac/login' % _port, timeout=2)
            BASE_URL = 'http://127.0.0.1:%d' % _port
            break
        except Exception:
            pass
    if not BASE_URL:
        _SKIP_REASON = 'No CronPilot service on :5001 or :5860; set CRONPILOT_BASE_URL or start the service'
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


def _csrf_post(session, path, data, extra_headers=None):
    """模拟 Dashboard $.post：从 cron_list 页面取 CSRF token 后携带 id POST。"""
    r = session.get(BASE_URL + '/cron_list', timeout=5)
    token = _extract_csrf_meta(r.text)
    headers = {'X-CSRFToken': token, 'Accept': 'application/json'}
    if extra_headers:
        headers.update(extra_headers)
    return session.post(BASE_URL + path, data=data, headers=headers, timeout=5)


def _group_id_from_form(html_text):
    """从当前 Redesign 表单取得 operator 被允许使用的业务组。"""
    hidden = re.search(
        r'<input[^>]+name=["\']group_id["\'][^>]+value=["\'](\d+)["\']',
        html_text,
    )
    if hidden:
        return hidden.group(1)
    selected = re.search(
        r'<select[^>]+name=["\']group_id["\'][^>]*>.*?'
        r'<option[^>]+value=["\'](\d+)["\']',
        html_text,
        re.S,
    )
    if selected:
        return selected.group(1)
    raise AssertionError('cron_add 页面未提供可用业务组；operator 必须先绑定业务组')


def _create_test_task(session, prefix):
    """经真实 Web 表单创建作用域内任务，并从 Dashboard 行取得其数据库 ID。"""
    form = session.get(BASE_URL + '/cron_add', timeout=5)
    if form.status_code != 200:
        raise AssertionError('GET /cron_add failed: %s' % form.status_code)
    csrf = _extract_csrf_meta(form.text)
    if not csrf:
        raise AssertionError('cron_add 页面缺少 csrf token')
    task_name = '%s-%d' % (prefix, time.time_ns())
    create = session.post(
        BASE_URL + '/cron_add',
        data={
            'task_name': task_name,
            'task_keyword': 'automated integration test task',
            'group_id': _group_id_from_form(form.text),
            'ds_ms': '2',
            'minute': '30',
            'req_url': 'https://example.com/integration-test',
            'req_method': 'GET',
            'timeout_sec': '1',
            'csrf_token': csrf,
        },
        headers={'X-Requested-With': 'XMLHttpRequest'},
        timeout=5,
    )
    if create.status_code != 200:
        raise AssertionError('POST /cron_add failed: %s %s' % (create.status_code, create.text))
    payload = create.json()
    if payload.get('errcode') != 0:
        raise AssertionError('POST /cron_add rejected: %s' % payload)

    dashboard = session.get(BASE_URL + '/cron_list', timeout=5)
    name = re.escape(html.escape(task_name))
    match = re.search(
        r'href=["\'](/task_detail\?id=(\d+))["\'][^>]*>\s*%s\s*<' % name,
        dashboard.text,
    )
    if not match:
        raise AssertionError('新建任务未出现在 Dashboard: %s' % task_name)
    return match.group(2), dashboard.text


@unittest.skipIf(_SKIP_REASON, _SKIP_REASON)
class TestRunNowIntegration(unittest.TestCase):
    """立即执行接口全链路：URL 格式、CSRF header、权限。"""

    @classmethod
    def setUpClass(cls):
        # 用 operator 账号（有 cron:write）经当前 Redesign 表单创建测试任务。
        cls.session = _login_session(user=WRITER_USER, password=WRITER_PASS)
        cls.task_id, cls.list_html = _create_test_task(cls.session, 'integration-run-now')
        cls.run_path = '/cron_run_now'

    def test_dashboard_run_action_has_one_task_id(self):
        """Dashboard 行操作必须把该任务 ID 仅作为一次函数参数传入。"""
        self.assertIn(
            'onclick="cpRunNow(%s, this)"' % self.task_id,
            self.list_html,
            'Dashboard 未为新建任务渲染立即执行操作',
        )

    def test_run_now_without_csrf_is_rejected(self):
        """不带 X-CSRFToken header 的 POST 应被 CSRF 拦截（403 或 errcode!=0 且 errmsg 含 csrf）。"""
        resp = self.session.post(
            BASE_URL + self.run_path, data={'id': self.task_id}, timeout=5
        )
        self.assertIn(resp.status_code, (200, 400, 403))
        if resp.status_code == 200:
            data = resp.json()
            self.assertNotEqual(data.get('errcode'), 0,
                                'POST without CSRF should fail: %s' % data)
            self.assertIn('csrf', (data.get('errmsg') or '').lower(),
                          'errmsg should mention csrf: %s' % data)

    def test_run_now_with_csrf_header_passes_csrf_check(self):
        """带 X-CSRFToken header 的 POST 通过 CSRF 校验（errcode 由业务层决定，非 csrf 错误）。"""
        resp = _csrf_post(self.session, self.run_path, {'id': self.task_id})
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
        # 用 operator 账号（有 cron:write）经当前 Redesign 表单创建测试任务。
        cls.session = _login_session(user=WRITER_USER, password=WRITER_PASS)
        cls.task_id, cls.list_html = _create_test_task(cls.session, 'integration-toggle')
        cls.update_path = '/update_status'

    def test_dashboard_toggle_action_has_one_task_id(self):
        """Dashboard 的状态菜单必须把该任务 ID 仅作为一次函数参数传入。"""
        self.assertIn(
            'onclick="cpToggleStatus(%s, 0, this)"' % self.task_id,
            self.list_html,
            'Dashboard 未为新建任务渲染暂停操作',
        )

    def test_update_status_without_csrf_is_rejected(self):
        """不带 X-CSRFToken 的 POST 应被拒。"""
        resp = self.session.post(
            BASE_URL + self.update_path, data={'id': self.task_id}, timeout=5
        )
        self.assertIn(resp.status_code, (200, 400, 403))
        if resp.status_code == 200:
            data = resp.json()
            self.assertNotEqual(data.get('errcode'), 0)

    def test_update_status_with_csrf_header_passes_csrf_check(self):
        """带 X-CSRFToken header 通过 CSRF 校验。"""
        resp = _csrf_post(self.session, self.update_path, {'id': self.task_id})
        self.assertIn(resp.status_code, (200, 400, 403))
        if resp.status_code == 200:
            data = resp.json()
            self.assertNotIn('csrf', (data.get('errmsg') or '').lower(),
                             'Should not be CSRF error when token provided: %s' % data)

    def test_viewer_cannot_toggle(self):
        """viewer 角色无 cron:write，update_status 应返回 403。"""
        viewer_session = _login_session(user=VIEWER_USER, password=VIEWER_PASS)
        r = viewer_session.get(BASE_URL + '/cron_list', timeout=5)
        self.assertNotIn(
            'onclick="cpToggleStatus(%s,' % self.task_id,
            r.text,
            'viewer 不应看到该任务的启停操作',
        )
        # 即使直接 POST 也应 403
        resp = _csrf_post(viewer_session, self.update_path, {'id': self.task_id})
        self.assertEqual(resp.status_code, 403,
                         'viewer POST update_status 应 403: %s' % resp.status_code)


if __name__ == '__main__':
    unittest.main()
