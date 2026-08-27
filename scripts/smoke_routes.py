#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""关键路由冒烟测试 — 验证所有核心页面渲染无 500。

用法:
    python scripts/smoke_routes.py                  # 内存 SQLite 全量冒烟
    python scripts/smoke_routes.py --check           # 同上，CI 门禁模式
    python scripts/smoke_routes.py --live             # 对运行中的服务 HTTP 冒烟
    python scripts/smoke_routes.py --live --port 5860 # 指定端口
    python scripts/smoke_routes.py --ui v2            # 仅测 Redesign 模板

设计目的:
    跨层重命名、模板 filter 注册、Jinja2 语法变更等改动后，
    自动验证所有核心路由的渲染不报 500 / TemplateError。
    弥补单元测试无法覆盖 view→repo→model→template 完整链路的盲区。

覆盖维度:
    1. GET 页面渲染（v1 + v2 双模板）
    2. POST 表单提交（登录、新增任务、修改密码等）
    3. API 端点（JSON 响应）
    4. 内容断言（关键文案存在性）
    5. 错误路径（404、无权限 403、不存在的 ID）
"""

import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


# ---------------------------------------------------------------------------
# Route definitions
#
# format: (method, path, need_login, need_data, expect, content_assert, desc)
#   need_data: 'none' | 'seed' | 'admin'
#   expect: expected HTTP status code(s) as tuple
#   content_assert: string that must appear in response body (or None)
# ---------------------------------------------------------------------------

# -- GET pages (rendered via template) --

ROUTES_PAGES = [
    ('GET', '/cron_list',            True,  'none',  (200,),    '任务中心',   '任务中心'),
    ('GET', '/',                     True,  'none',  (200, 302), None,        '首页(→任务中心)'),
    ('GET', '/job_log_all_list',     True,  'none',  (200,),    None,         '全部执行记录'),
    ('GET', '/operation_log_list',   True,  'admin', (200,),    None,         '操作日志'),
    ('GET', '/cron_add',             True,  'none',  (200, 403), None,        '新增任务表单'),
    ('GET', '/api_doc',              True,  'none',  (200,),    None,         'API 文档页'),
]

ROUTES_RBAC_GET = [
    ('GET', '/rbac/login',               False, 'none',  (200,),    'csrf_token',  '登录页'),
    ('GET', '/rbac/register',            False, 'none',  (200,),    'csrf_token',  '注册页'),
    ('GET', '/rbac/forgot_password',     False, 'none',  (200,),    None,          '忘记密码页'),
    ('GET', '/rbac/password',            True,  'none',  (200,),    None,          '修改密码'),
    ('GET', '/rbac/profile',             True,  'none',  (200,),    None,          '个人资料'),
    ('GET', '/rbac/api_token',           True,  'none',  (200,),    None,          'API Token 管理'),
    ('GET', '/rbac/users',               True,  'admin', (200,),    None,          '用户管理列表'),
    ('GET', '/rbac/users/add',           True,  'admin', (200,),    None,          '新增用户表单'),
    ('GET', '/rbac/groups',              True,  'admin', (200,),    None,          '组管理列表'),
    ('GET', '/rbac/groups/add',          True,  'admin', (200,),    None,          '新增组表单'),
    ('GET', '/rbac/audit-logs',          True,  'admin', (200,),    None,          '审计日志'),
    ('GET', '/rbac/registration_review', True,  'admin', (200,),    None,          '注册审核'),
    ('GET', '/rbac/tags',                True,  'admin', (200,),    None,          '标签管理'),
]

ROUTES_WITH_DATA = [
    ('GET', '/job_log_detail?id={log_id}',           True, 'seed', (200,),    'Trace ID',  '执行记录详情'),
    ('GET', '/task_detail?id={cron_id}',              True, 'seed', (200, 302), None,     '任务详情'),
    ('GET', '/cron_edit?id={cron_id}',                True, 'seed', (200,),    None,      '编辑任务'),
    ('GET', '/job_log_list?id={cron_id}',             True, 'seed', (200,),    None,      '任务执行记录列表'),
    ('GET', '/cron_retire?id={cron_id}',              True, 'seed', (200,),    None,      '退役任务表单'),
    ('GET', '/job_log_item_list?trace_id={trace_id}', True, 'seed', (200, 302), None,      '执行进度列表'),
    ('GET', '/rbac/users/edit?id={user_id}',          True, 'seed', (200, 302), None,      '编辑用户'),
    ('GET', '/rbac/users/view?id={user_id}',          True, 'seed', (200,),    None,      '查看用户'),
    ('GET', '/rbac/tags/tasks?tag_id={tag_id}',       True, 'seed', (200,),    None,      '标签关联任务'),
]

# -- POST form submissions --

ROUTES_POST_FORMS = [
    # (method, path, need_login, need_data, post_data_key, expect, desc)
    ('POST', '/rbac/login',     False, 'none', 'login_valid',     (200, 302), '登录提交（有效）'),
    ('POST', '/rbac/login',     False, 'none', 'login_invalid',   (200, 302), '登录提交（无效密码）'),
    ('POST', '/rbac/register',  False, 'none', 'register',        (200, 302), '注册提交'),
    ('POST', '/cron_add',       True,  'none', 'cron_add',        (200, 302, 403), '新增任务提交'),
    ('POST', '/rbac/tags/create', True, 'admin', 'tag_create',    (200,),     '创建标签'),
    ('POST', '/update_status',  True,  'seed', 'status_toggle',   (200,),     '切换任务状态'),
]

# -- API endpoints --

ROUTES_API = [
    ('GET',  '/api/test',        False, 'none', (200,), 'errcode', 'API 健康检查'),
    ('GET',  '/api/cron/query',  True,  'none', (200,), None,      'API 任务列表'),
    ('GET',  '/api/cron/logs',   True,  'none', (200,), None,      'API 执行记录'),
]

ROUTES_API_WITH_DATA = [
    ('GET', '/api/cron/detail?id={cron_id}',           True, 'seed', (200,), None, 'API 任务详情'),
    ('GET', '/api/cron/log/detail?trace_id={trace_id}', True, 'seed', (200,), None, 'API 执行记录详情'),
]

# -- Error paths --

ROUTES_ERROR = [
    ('GET', '/nonexistent_page_404_probe',       True,  'none', (404,), None, '404 不存在页面'),
    ('GET', '/job_log_detail?id=999999',         True,  'none', (200,), None, '详情页不存在的 ID'),
    ('GET', '/cron_edit?id=999999',              True,  'none', (200, 302, 404), None, '编辑不存在的任务'),
    ('GET', '/rbac/users/edit?id=999999',        True,  'admin', (200, 302, 404), None, '编辑不存在的用户'),
]


# ---------------------------------------------------------------------------
# POST data factories
# ---------------------------------------------------------------------------

def _build_post_data(key, seed):
    """Build POST form data for different scenarios."""
    if key == 'login_valid':
        return {'username': seed['username'], 'password': seed['password']}
    if key == 'login_invalid':
        return {'username': seed['username'], 'password': 'wrong_password'}
    if key == 'register':
        return {
            'username': 'smoke_register_test',
            'password': 'TestPass123!',
            'password2': 'TestPass123!',
            'email': 'smoke@test.local',
        }
    if key == 'cron_add':
        return {
            'task_name': 'smoke_new_task',
            'req_url': 'http://example.com/smoke',
            'minute': '*/10',
        }
    if key == 'tag_create':
        return {'name': 'smoke-tag-test'}
    if key == 'status_toggle':
        return {'id': str(seed['cron_id']), 'status': '0'}
    return {}


# ---------------------------------------------------------------------------
# Internal (in-process) smoke test — uses Flask test client
# ---------------------------------------------------------------------------

def _make_test_app():
    """Create a Flask app with in-memory SQLite for smoke testing.

    Uses create_app('testing') with forced in-memory URI so that
    the real blueprints, filters, and before_request hooks are
    registered — exactly as they are in production.
    """
    os.environ['TEST_DATABASE_URL'] = 'sqlite:///:memory:'
    os.environ.setdefault('FLASK_CONFIG', 'testing')

    from app import create_app, db

    app = create_app('testing')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SERVER_NAME'] = 'localhost'

    # Import all models so db.create_all() sees every table
    import datas.model.cron_infos       # noqa: F401
    import datas.model.job_log          # noqa: F401
    import datas.model.job_log_items    # noqa: F401
    import datas.model.job_health       # noqa: F401
    import datas.model.operation_log    # noqa: F401
    import datas.model.rbac_user        # noqa: F401
    import datas.model.rbac_audit_log   # noqa: F401
    import datas.model.rbac_registration_request  # noqa: F401
    import datas.model.resource_group   # noqa: F401
    import datas.model.tag              # noqa: F401
    import datas.model.task_tag         # noqa: F401
    import datas.model.user_group      # noqa: F401
    import datas.model.task_group      # noqa: F401

    with app.app_context():
        db.drop_all()
        db.create_all()

    return app, db


def _seed_test_data(app, db):
    """Seed minimal test data for routes that need an ID."""
    from datas.utils.times import utc_now_hms
    from datas.model.cron_infos import CronInfos
    from datas.model.job_log import JobLog
    from datas.model.job_log_items import JobLogItems
    from datas.model.rbac_user import RbacUser
    from datas.model.tag import Tag
    from datas.model.resource_group import ResourceGroup
    from app.auth.password import hash_password
    import uuid

    with app.app_context():
        now = utc_now_hms()

        user = RbacUser(
            username='smoke_admin',
            password_hash=hash_password('smoke123'),
            role='admin',
            is_active=1,
            create_time=now,
        )
        db.session.add(user)
        db.session.flush()

        grp = ResourceGroup(name='smoke-group', create_time=now)
        db.session.add(grp)
        db.session.flush()

        cron = CronInfos(
            task_name='smoke_test_task',
            req_url='http://example.com/test',
            minute='*/5',
            created_at=now,
            updated_at=now,
            last_operator_name='smoke_admin',
        )
        db.session.add(cron)
        db.session.flush()

        trace_id = str(uuid.uuid4())
        log = JobLog(
            cron_info_id=cron.id,
            trace_id=trace_id,
            status='success',
            content='smoke test ok',
            create_time=now,
            started_at=now,
            finished_at=now,
        )
        db.session.add(log)
        db.session.flush()

        item = JobLogItems(
            trace_id=trace_id,
            content='step 1 ok',
        )
        db.session.add(item)

        tag = Tag(name='smoke-tag', create_time=now, update_time=now)
        db.session.add(tag)
        db.session.flush()

        db.session.commit()

        return {
            'user_id': user.id,
            'username': 'smoke_admin',
            'password': 'smoke123',
            'cron_id': cron.id,
            'log_id': log.id,
            'trace_id': trace_id,
            'tag_id': tag.id,
            'group_id': grp.id,
        }


def _login_test_client(client, username, password):
    """Login via test client and return session."""
    client.post('/rbac/login', data={
        'username': username,
        'password': password,
    }, follow_redirects=True)


def _check_result(status, expect, body, content_assert, label, verbose):
    """Check a single route result; returns (pass_bool, error_msg_or_None)."""
    if status == 500:
        msg = f'FAIL {label} → 500 Internal Server Error'
        if verbose:
            print(msg)
            if body:
                for line in body.split('\n'):
                    if 'Traceback' in line or 'Error' in line:
                        print(f'       {line.strip()[:200]}')
        return False, msg

    if expect and status not in expect:
        msg = f'FAIL {label} → {status} (expected {expect})'
        if verbose:
            print(msg)
        return False, msg

    if content_assert and body and content_assert not in body:
        msg = f'FAIL {label} → {status} missing "{content_assert}" in body'
        if verbose:
            print(msg)
        return False, msg

    if verbose:
        print(f'PASS {label} → {status}')
    return True, None


def _run_internal_smoke(ui_mode='all', verbose=False):
    """Run smoke tests using Flask test client (no live server needed)."""
    app, db = _make_test_app()

    passed = 0
    failed = 0
    errors = []

    ui_versions = []
    if ui_mode in ('all', 'v1'):
        ui_versions.append('v1')
    if ui_mode in ('all', 'v2'):
        ui_versions.append('v2')

    with app.app_context():
        seed = _seed_test_data(app, db)

    all_get_routes = ROUTES_PAGES + ROUTES_RBAC_GET + ROUTES_WITH_DATA + ROUTES_API + ROUTES_API_WITH_DATA + ROUTES_ERROR

    for ui_ver in ui_versions:
        with app.test_client() as client:
            client.set_cookie('cp_ui_version', ui_ver, domain='localhost')
            _login_test_client(client, seed['username'], seed['password'])

            # --- GET routes ---
            for method, path_tpl, need_login, need_data, expect, content_assert, desc in all_get_routes:
                path = path_tpl.format(**seed) if need_data == 'seed' else path_tpl
                label = f'[{ui_ver}] {method} {path} ({desc})'

                try:
                    resp = client.get(path)
                    body = resp.get_data(as_text=True)
                    ok, msg = _check_result(resp.status_code, expect, body, content_assert, label, verbose)
                    if ok:
                        passed += 1
                    else:
                        failed += 1
                        errors.append(msg)
                except Exception as exc:
                    failed += 1
                    msg = f'FAIL {label} → Exception: {exc}'
                    errors.append(msg)
                    if verbose:
                        print(msg)

            # --- POST form submissions ---
            if verbose:
                print(f'\n--- [{ui_ver}] POST 表单提交 ---')

            for method, path, need_login, need_data, post_key, expect, desc in ROUTES_POST_FORMS:
                data = _build_post_data(post_key, seed)
                label = f'[{ui_ver}] POST {path} ({desc})'

                try:
                    resp = client.post(path, data=data, follow_redirects=False)
                    body = resp.get_data(as_text=True)
                    ok, msg = _check_result(resp.status_code, expect, body, None, label, verbose)
                    if ok:
                        passed += 1
                    else:
                        failed += 1
                        errors.append(msg)
                except Exception as exc:
                    failed += 1
                    msg = f'FAIL {label} → Exception: {exc}'
                    errors.append(msg)
                    if verbose:
                        print(msg)

    return passed, failed, errors


# ---------------------------------------------------------------------------
# Live (HTTP) smoke test — curls a running server
# ---------------------------------------------------------------------------

def _run_live_smoke(port=5001, password='changeme', ui_mode='all', verbose=False):
    """Run smoke tests against a live server via HTTP requests."""
    import requests as req

    base = f'http://127.0.0.1:{port}'
    passed = 0
    failed = 0
    errors = []

    session = req.Session()
    session.headers['User-Agent'] = 'CronPilot-SmokeTest/1.0'

    login_html = session.get(f'{base}/rbac/login', timeout=5).text
    import re
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', login_html)
    if not m:
        m = re.search(r'value="([^"]+)"\s+name="csrf_token"', login_html)
    if not m:
        print('FAIL: cannot extract CSRF token from login page')
        return 0, 1, ['Cannot extract CSRF token']
    csrf = m.group(1)

    resp = session.post(f'{base}/rbac/login', data={
        'username': 'admin',
        'password': password,
        'csrf_token': csrf,
    }, allow_redirects=True, timeout=10)
    if resp.status_code not in (200, 302):
        print(f'FAIL: login returned {resp.status_code}')
        return 0, 1, [f'Login failed: {resp.status_code}']

    all_get_routes = ROUTES_PAGES + ROUTES_RBAC_GET + ROUTES_API + ROUTES_ERROR

    for method, path_tpl, need_login, need_data, expect, content_assert, desc in all_get_routes:
        if need_data == 'seed':
            continue

        url = base + path_tpl
        label = f'{method} {path_tpl} ({desc})'

        try:
            r = session.get(url, timeout=10, allow_redirects=True)
            body = r.text
            if r.status_code == 500 or 'system err' in body.lower():
                failed += 1
                msg = f'FAIL {label} → {r.status_code} (system err)'
                errors.append(msg)
                if verbose:
                    print(msg)
            else:
                ok, msg = _check_result(r.status_code, None, body, content_assert, label, verbose)
                if ok:
                    passed += 1
                else:
                    failed += 1
                    errors.append(msg)

        except Exception as exc:
            failed += 1
            msg = f'FAIL {label} → {exc}'
            errors.append(msg)
            if verbose:
                print(msg)

    return passed, failed, errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='CronPilot 关键路由冒烟测试')
    parser.add_argument('--check', action='store_true', help='CI 门禁模式（失败返回非零退出码）')
    parser.add_argument('--live', action='store_true', help='对运行中的服务做 HTTP 冒烟')
    parser.add_argument('--port', type=int, default=5001, help='Live 模式端口（默认 5001）')
    parser.add_argument('--password', default='changeme', help='Live 模式 admin 密码')
    parser.add_argument('--ui', choices=['all', 'v1', 'v2'], default='all', help='UI 版本')
    parser.add_argument('-v', '--verbose', action='store_true', help='显示每条路由结果')
    args = parser.parse_args()

    verbose = args.verbose or args.check
    start = time.time()

    if args.live:
        passed, failed, errs = _run_live_smoke(
            port=args.port, password=args.password,
            ui_mode=args.ui, verbose=verbose,
        )
    else:
        passed, failed, errs = _run_internal_smoke(
            ui_mode=args.ui, verbose=verbose,
        )

    elapsed = time.time() - start
    total = passed + failed

    print(f'\n{"="*50}')
    print(f'冒烟测试完成: {total} 路由, {passed} 通过, {failed} 失败 ({elapsed:.1f}s)')

    if errs:
        print(f'\n失败路由:')
        for e in errs:
            print(f'  {e}')

    if failed > 0:
        print(f'\nSMOKE_ROUTES: FAIL')
        sys.exit(1)
    else:
        print(f'\nSMOKE_ROUTES: OK')
        sys.exit(0)


if __name__ == '__main__':
    main()
