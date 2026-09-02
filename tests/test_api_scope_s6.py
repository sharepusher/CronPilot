# -*- coding: utf-8 -*-
"""S6：用户级 API Token + 自动过期 + Scope 隔离。

覆盖：
- /api/auth/token 签发（Basic Auth / form 参数）
- Token 过期 → 401
- 用户 token → 按用户角色 + 所属组做 Scope 校验
- 组变更即时生效（缓存失效）
- 停用用户 → 401
- 越组操作 → 与「任务不存在」相同错误码（防枚举）
- 空 token + required=0 → 全放行（向后兼容）
- 缓存 TTL + 事件失效
"""
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from datas.utils.times import datetime_to_hms, str_to_hms

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _make_app():
    from flask import Flask

    import app.api as api_pkg
    from app import db

    app = Flask(__name__)
    app.secret_key = 'test-s6'
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    app.register_blueprint(api_pkg.api, url_prefix='/api')
    return app, db


class TestAuthTokenEndpoint(unittest.TestCase):
    """POST /api/auth/token — 签发 Token。"""

    def setUp(self):
        import app.api as api_pkg
        api_pkg._SCOPE_CACHE.clear()
        self.app, self.db = _make_app()
        self.client = self.app.test_client()
        with self.app.app_context():
            from datas.model.rbac_audit_log import RbacAuditLog
            from datas.model.rbac_user import RbacUser
            self.db.create_all()
            u = RbacUser(username='testuser', role='operator', is_active=1, create_time=str_to_hms('2026-01-01 00:00:00'))
            u.set_password('mypassword')
            self.db.session.add(u)
            self.db.session.commit()
            self.uid = u.id

    def test_form_auth_issues_token(self):
        with self.app.app_context():
            with patch('configs.configs', return_value=''):
                resp = self.client.post('/api/auth/token',
                                        data={'username': 'testuser', 'password': 'mypassword'})
            data = resp.get_json()
            self.assertEqual(data['errcode'], 0)
            self.assertIn('token', data.get('data', data.get('result', {})))
            self.assertIn('expires_at', data.get('data', data.get('result', {})))

    def test_basic_auth_issues_token(self):
        import base64
        cred = base64.b64encode(b'testuser:mypassword').decode()
        with self.app.app_context():
            with patch('configs.configs', return_value=''):
                resp = self.client.post('/api/auth/token',
                                        headers={'Authorization': 'Basic %s' % cred})
            data = resp.get_json()
            self.assertEqual(data['errcode'], 0)

    def test_wrong_password_401(self):
        with self.app.app_context():
            with patch('configs.configs', return_value=''):
                resp = self.client.post('/api/auth/token',
                                        data={'username': 'testuser', 'password': 'wrong'})
            self.assertEqual(resp.status_code, 401)

    def test_disabled_user_401(self):
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            u = self.db.session.get(RbacUser, self.uid)
            u.is_active = 0
            self.db.session.commit()
            with patch('configs.configs', return_value=''):
                resp = self.client.post('/api/auth/token',
                                        data={'username': 'testuser', 'password': 'mypassword'})
            self.assertEqual(resp.status_code, 401)


class TestTokenExpiry(unittest.TestCase):
    """Token 过期后 → 401。"""

    def setUp(self):
        import app.api as api_pkg
        api_pkg._SCOPE_CACHE.clear()
        self.app, self.db = _make_app()
        self.client = self.app.test_client()
        with self.app.app_context():
            from datas.model.cron_infos import CronInfos
            from datas.model.rbac_audit_log import RbacAuditLog
            from datas.model.rbac_user import RbacUser
            self.db.create_all()
            expired = datetime_to_hms(datetime.now() - timedelta(days=1))
            u = RbacUser(username='expired-user', role='operator', is_active=1,
                         api_token='expired-tok', api_token_expires_at=expired,
                         password_hash='x', create_time=str_to_hms('2026-01-01 00:00:00'))
            u_valid = RbacUser(username='valid-user', role='operator', is_active=1,
                               api_token='valid-tok',
                               api_token_expires_at=datetime_to_hms(datetime.now() + timedelta(days=10)),
                               password_hash='x', create_time=str_to_hms('2026-01-01 00:00:00'))
            self.db.session.add_all([u, u_valid])
            c = CronInfos(task_name='t1', req_url='http://x.com', scope_type='GLOBAL')
            self.db.session.add(c)
            self.db.session.commit()

    def _post_status(self, token):
        with patch('configs.configs', return_value='global-tok'), \
             patch('app.services.cron_service.scheduler') as ms:
            ms.pause_job.return_value = None
            ms.resume_job.return_value = None
            return self.client.post('/api/cron/status',
                                    data={'task_name': 't1'},
                                    headers={'Authorization': 'Bearer %s' % token})

    def test_expired_token_rejected(self):
        resp = self._post_status('expired-tok')
        self.assertEqual(resp.status_code, 401)
        self.assertIn('过期', resp.get_json().get('errmsg', ''))

    def test_valid_token_accepted(self):
        resp = self._post_status('valid-tok')
        self.assertNotEqual(resp.status_code, 401)


class TestScopeIsolation(unittest.TestCase):
    """用户 Token Scope 隔离 + 组变更即时生效。"""

    def setUp(self):
        import app.api as api_pkg
        api_pkg._SCOPE_CACHE.clear()
        self.app, self.db = _make_app()
        self.client = self.app.test_client()
        with self.app.app_context():
            from datas.model.cron_infos import CronInfos
            from datas.model.rbac_audit_log import RbacAuditLog
            from datas.model.rbac_user import RbacUser
            from datas.model.resource_group import ResourceGroup
            from datas.model.task_group import TaskGroup  # noqa: F401
            from datas.model.user_group import UserGroup
            self.db.create_all()

            g1 = ResourceGroup(name='G1', create_time=str_to_hms('2026-01-01 00:00:00'))
            g2 = ResourceGroup(name='G2', create_time=str_to_hms('2026-01-01 00:00:00'))
            self.db.session.add_all([g1, g2])
            self.db.session.flush()
            self.g1_id = g1.id
            self.g2_id = g2.id

            future = datetime_to_hms(datetime.now() + timedelta(days=30))
            u = RbacUser(username='bot', role='operator', is_active=1,
                         api_token='bot-tok', api_token_expires_at=future,
                         password_hash='x', create_time=str_to_hms('2026-01-01 00:00:00'))
            self.db.session.add(u)
            self.db.session.flush()
            self.u_id = u.id
            self.db.session.add(UserGroup(user_id=u.id, group_id=g1.id))

            tg = CronInfos(task_name='t-global', req_url='http://x.com', scope_type='GLOBAL')
            t1 = CronInfos(task_name='t-g1', req_url='http://x.com', scope_type='GROUP')
            t2 = CronInfos(task_name='t-g2', req_url='http://x.com', scope_type='GROUP')
            self.db.session.add_all([tg, t1, t2])
            self.db.session.flush()
            self.db.session.add(TaskGroup(task_id=t1.id, group_id=g1.id))
            self.db.session.add(TaskGroup(task_id=t2.id, group_id=g2.id))
            self.db.session.commit()

    def _post(self, task_name, token='bot-tok'):
        with patch('configs.configs', return_value='global-tok'), \
             patch('app.services.cron_service.scheduler') as ms:
            ms.pause_job.return_value = None
            ms.resume_job.return_value = None
            return self.client.post('/api/cron/status',
                                    data={'task_name': task_name},
                                    headers={'Authorization': 'Bearer %s' % token})

    def test_own_group_allowed(self):
        resp = self._post('t-g1')
        self.assertEqual(resp.get_json()['errcode'], 0)

    def test_global_task_allowed(self):
        resp = self._post('t-global')
        self.assertEqual(resp.get_json()['errcode'], 0)

    def test_other_group_denied(self):
        resp = self._post('t-g2')
        self.assertEqual(resp.get_json()['errmsg'], '任务不存在')

    def test_anti_enumeration(self):
        r1 = self._post('t-g2')
        r2 = self._post('no-such')
        self.assertEqual(r1.get_json()['errmsg'], r2.get_json()['errmsg'])

    def test_global_token_all_access(self):
        resp = self._post('t-g2', token='global-tok')
        self.assertNotEqual(resp.status_code, 401)

    def test_group_change_immediate(self):
        with self.app.app_context():
            resp1 = self._post('t-g2')
            self.assertEqual(resp1.get_json()['errmsg'], '任务不存在')

            from datas.model.user_group import UserGroup
            self.db.session.add(UserGroup(user_id=self.u_id, group_id=self.g2_id))
            self.db.session.commit()

            from app.api import invalidate_user_scope_cache
            invalidate_user_scope_cache(self.u_id)

            resp2 = self._post('t-g2')
            self.assertEqual(resp2.get_json()['errcode'], 0)

    def test_empty_global_passthrough(self):
        with patch('configs.configs', return_value=''), \
             patch('app.services.cron_service.scheduler') as ms:
            ms.pause_job.return_value = None
            resp = self.client.post('/api/cron/status', data={'task_name': 't-g1'})
        self.assertNotEqual(resp.status_code, 401)

    def test_wrong_token_401(self):
        resp = self._post('t-g1', token='bad')
        self.assertEqual(resp.status_code, 401)


class TestAutoResetOnMutation(unittest.TestCase):
    """密码变更 / 组变更 → Token 自动重置。"""

    def setUp(self):
        import app.api as api_pkg
        api_pkg._SCOPE_CACHE.clear()
        self.app, self.db = _make_app()
        with self.app.app_context():
            from datas.model.rbac_audit_log import RbacAuditLog
            from datas.model.rbac_user import RbacUser
            from datas.model.resource_group import ResourceGroup
            from datas.model.user_group import UserGroup
            self.db.create_all()

            g = ResourceGroup(name='G', create_time=str_to_hms('2026-01-01 00:00:00'))
            self.db.session.add(g)
            self.db.session.commit()
            self.g_id = g.id

    def test_create_user_auto_generates_token(self):
        from app.rbac.services import create_user

        with self.app.app_context():
            result = create_user('auto-tok', role='operator')
            self.assertTrue(result['ok'])
            from datas.model.rbac_user import RbacUser
            u = self.db.session.get(RbacUser, result['user_id'])
            self.assertIsNotNone(u.api_token)
            self.assertIsNotNone(u.api_token_expires_at)

    def test_password_change_resets_token(self):
        from app.rbac.services import change_own_password, create_user

        with self.app.app_context():
            result = create_user('pwd-test', role='operator')
            from datas.model.rbac_user import RbacUser
            u = self.db.session.get(RbacUser, result['user_id'])
            u.must_reset_password = 0
            self.db.session.commit()
            old_token = u.api_token

            change_own_password(u.id, 'changeme', 'newpass123', 'newpass123')
            self.db.session.expire(u)
            self.assertNotEqual(u.api_token, old_token, 'Token should reset on password change')

    def test_group_change_resets_token(self):
        from app.rbac.services import create_user, set_user_groups

        with self.app.app_context():
            result = create_user('grp-test', role='operator')
            self.assertTrue(result['ok'])
            from datas.model.rbac_user import RbacUser
            u = self.db.session.get(RbacUser, result['user_id'])
            old_token = u.api_token

            grp_result = set_user_groups(u.id, [self.g_id])
            self.assertTrue(grp_result['ok'], msg=grp_result.get('msg', ''))
            self.db.session.expire(u)
            new_token = u.api_token
            self.assertNotEqual(new_token, old_token, 'Token should reset on group change')


class TestReadonlyQueryApis(unittest.TestCase):
    """只读查询接口：/api/cron/query 与 /api/cron/logs。"""

    def setUp(self):
        import app.api as api_pkg
        api_pkg._SCOPE_CACHE.clear()
        self.app, self.db = _make_app()
        self.client = self.app.test_client()
        with self.app.app_context():
            from datas.model.cron_infos import CronInfos
            from datas.model.job_log import JobLog
            from datas.model.rbac_audit_log import RbacAuditLog
            from datas.model.rbac_user import RbacUser
            from datas.model.resource_group import ResourceGroup
            from datas.model.task_group import TaskGroup  # noqa: F401
            from datas.model.user_group import UserGroup
            self.db.create_all()

            g1 = ResourceGroup(name='G1', create_time=str_to_hms('2026-01-01 00:00:00'))
            g2 = ResourceGroup(name='G2', create_time=str_to_hms('2026-01-01 00:00:00'))
            self.db.session.add_all([g1, g2])
            self.db.session.flush()

            future = datetime_to_hms(datetime.now() + timedelta(days=30))
            u = RbacUser(
                username='reader',
                role='operator',
                is_active=1,
                api_token='reader-tok',
                api_token_expires_at=future,
                password_hash='x',
                create_time=str_to_hms('2026-01-01 00:00:00'),
            )
            self.db.session.add(u)
            self.db.session.flush()
            self.db.session.add(UserGroup(user_id=u.id, group_id=g1.id))

            c_global = CronInfos(task_name='q-global', req_url='http://x.com', scope_type='GLOBAL')
            c_g1 = CronInfos(task_name='q-g1', req_url='http://x.com', scope_type='GROUP')
            c_g2 = CronInfos(task_name='q-g2', req_url='http://x.com', scope_type='GROUP')
            c_post = CronInfos(task_name='q-post', req_url='http://x.com', req_method='POST', scope_type='GROUP')
            self.db.session.add_all([c_global, c_g1, c_g2, c_post])
            self.db.session.flush()
            self.db.session.add(TaskGroup(task_id=c_g1.id, group_id=g1.id))
            self.db.session.add(TaskGroup(task_id=c_g2.id, group_id=g2.id))
            self.db.session.add(TaskGroup(task_id=c_post.id, group_id=g1.id))

            self.db.session.add_all([
                JobLog(cron_info_id=c_g1.id, trace_id='lg-1', status='success', create_time=str_to_hms('2026-01-01 10:00:00')),
                JobLog(cron_info_id=c_g1.id, trace_id='lg-2', status='fail', fail_reason='timeout', create_time=str_to_hms('2026-01-01 10:05:00')),
                JobLog(cron_info_id=c_g2.id, trace_id='lg-3', status='success', create_time=str_to_hms('2026-01-01 10:06:00')),
            ])
            self.db.session.commit()

    def _get(self, path, query='', token='reader-tok'):
        with patch('configs.configs', return_value='global-tok'):
            return self.client.get(
                '%s%s' % (path, query),
                headers={'Authorization': 'Bearer %s' % token},
            )

    def test_cron_query_respects_scope(self):
        resp = self._get('/api/cron/query', '?keyword=q-')
        data = resp.get_json()
        self.assertEqual(data['errcode'], 0)
        self.assertIn('total', data.get('data', {}))
        names = {item['task_name'] for item in data.get('data', {}).get('items', [])}
        self.assertIn('q-global', names)
        self.assertIn('q-g1', names)
        self.assertNotIn('q-g2', names)

    def test_cron_query_global_token_can_view_all(self):
        resp = self._get('/api/cron/query', '?keyword=q-', token='global-tok')
        data = resp.get_json()
        self.assertEqual(data['errcode'], 0)
        names = {item['task_name'] for item in data.get('data', {}).get('items', [])}
        self.assertIn('q-global', names)
        self.assertIn('q-g1', names)
        self.assertIn('q-g2', names)

    def test_cron_query_filter_req_method(self):
        resp = self._get('/api/cron/query', '?keyword=q-&req_method=POST')
        data = resp.get_json()
        self.assertEqual(data['errcode'], 0)
        names = {item['task_name'] for item in data.get('data', {}).get('items', [])}
        self.assertIn('q-post', names)
        self.assertNotIn('q-g1', names)

    def test_cron_logs_requires_task_name(self):
        resp = self._get('/api/cron/logs')
        self.assertEqual(resp.get_json().get('errcode'), 1)
        self.assertIn('task_name', resp.get_json().get('errmsg', ''))

    def test_cron_logs_respects_scope_and_anti_enumeration(self):
        denied = self._get('/api/cron/logs', '?task_name=q-g2')
        self.assertEqual(denied.get_json().get('errmsg'), '任务不存在')
        missing = self._get('/api/cron/logs', '?task_name=no-such')
        self.assertEqual(missing.get_json().get('errmsg'), '任务不存在')

    def test_cron_logs_returns_visible_logs(self):
        resp = self._get('/api/cron/logs', '?task_name=q-g1&limit=10')
        data = resp.get_json()
        self.assertEqual(data['errcode'], 0)
        items = data.get('data', {}).get('items', [])
        self.assertGreaterEqual(len(items), 2)
        self.assertEqual(data.get('data', {}).get('task_name'), 'q-g1')
        self.assertIn('total', data.get('data', {}))
        self.assertIn('content_preview', items[0])

    def test_cron_logs_status_filter(self):
        resp = self._get('/api/cron/logs', '?task_name=q-g1&status=fail&limit=10')
        data = resp.get_json()
        self.assertEqual(data['errcode'], 0)
        items = data.get('data', {}).get('items', [])
        self.assertTrue(items)
        for item in items:
            self.assertEqual(item.get('status'), 'fail')

    def test_cron_detail_respects_scope(self):
        allowed = self._get('/api/cron/detail', '?task_name=q-g1')
        self.assertEqual(allowed.get_json().get('errcode'), 0)
        denied = self._get('/api/cron/detail', '?task_name=q-g2')
        self.assertEqual(denied.get_json().get('errmsg'), '任务不存在')

    def test_cron_log_detail_respects_scope(self):
        own_logs = self._get('/api/cron/logs', '?task_name=q-g1&limit=1')
        log_id = own_logs.get_json().get('data', {}).get('items', [{}])[0].get('id')
        detail = self._get('/api/cron/log/detail', '?id=%s' % log_id)
        self.assertEqual(detail.get_json().get('errcode'), 0)

        other_logs = self._get('/api/cron/logs', '?task_name=q-g2&limit=1', token='global-tok')
        other_id = other_logs.get_json().get('data', {}).get('items', [{}])[0].get('id')
        denied = self._get('/api/cron/log/detail', '?id=%s' % other_id)
        self.assertEqual(denied.get_json().get('errmsg'), '任务不存在')


class TestCacheMechanics(unittest.TestCase):
    """缓存 TTL + 事件失效。"""

    def _make_scope(self, user_id=1, user_role='operator', group_ids=None,
                     is_active=True, username='u', expired=False):
        return {
            'role': 'user', 'user_id': user_id, 'user_role': user_role,
            'username': username, 'group_ids': list(group_ids or [1]),
            'is_active': is_active, 'expired': expired,
        }

    def test_ttl_expiry(self):
        import app.api as api_pkg
        api_pkg._SCOPE_CACHE.clear()
        api_pkg._set_cached_user_scope('tok', self._make_scope())
        self.assertIsNotNone(api_pkg._get_cached_user_scope('tok'))
        api_pkg._SCOPE_CACHE['tok']['ts'] -= api_pkg._CACHE_TTL + 1
        self.assertIsNone(api_pkg._get_cached_user_scope('tok'))

    def test_invalidate_user(self):
        import app.api as api_pkg
        api_pkg._SCOPE_CACHE.clear()
        api_pkg._set_cached_user_scope('tok-a', self._make_scope(user_id=1, username='a'))
        api_pkg._set_cached_user_scope('tok-b', self._make_scope(user_id=2, username='b'))
        api_pkg.invalidate_user_scope_cache(1)
        self.assertIsNone(api_pkg._get_cached_user_scope('tok-a'))
        self.assertIsNotNone(api_pkg._get_cached_user_scope('tok-b'))

    def test_cache_shape_matches_fresh_scope(self):
        """S-4 regression: cached dict must have role='user', not user.role."""
        import app.api as api_pkg
        api_pkg._SCOPE_CACHE.clear()
        scope = self._make_scope(user_role='admin', group_ids=[1])
        api_pkg._set_cached_user_scope('tok-admin', scope)
        cached = api_pkg._get_cached_user_scope('tok-admin')
        self.assertEqual(cached['role'], 'user',
                         "cached role must be 'user', not the user's actual role")
        self.assertEqual(cached['user_role'], 'admin')
        self.assertIn('expired', cached)
        self.assertIn('group_ids', cached)


class TestApiRolePermission(unittest.TestCase):
    """S-5: check_api_permission() — 角色能力校验。

    直接测试函数逻辑，不经过 HTTP 端点链，避免 apiflask schema 依赖。
    """

    def setUp(self):
        self.app, self.db = _make_app()

    def _call(self, required_perm, scope):
        """在 request context 中调用 check_api_permission。"""
        from app.api import check_api_permission
        with self.app.test_request_context('/api/test'):
            from flask import request
            request._api_scope = scope
            return check_api_permission(required_perm)

    def _viewer_scope(self):
        return {'role': 'user', 'user_role': 'viewer', 'username': 'v1',
                'group_ids': [1], 'is_active': True, 'expired': False}

    def _operator_scope(self):
        return {'role': 'user', 'user_role': 'operator', 'username': 'op1',
                'group_ids': [1], 'is_active': True, 'expired': False}

    def _admin_scope(self):
        return {'role': 'user', 'user_role': 'admin', 'username': 'a1',
                'group_ids': [1], 'is_active': True, 'expired': False}

    def _global_admin_scope(self):
        return {'role': 'admin'}

    def _seed_admin_scope(self):
        return {'role': 'user', 'user_role': 'admin', 'username': 'admin',
                'group_ids': [1], 'is_active': True, 'expired': False}

    def test_viewer_denied_cron_write(self):
        result = self._call('cron:write', self._viewer_scope())
        self.assertIsNotNone(result, 'viewer should be denied cron:write')
        resp, code = result
        self.assertEqual(code, 403)

    def test_viewer_denied_cron_retire(self):
        result = self._call('cron:retire', self._viewer_scope())
        self.assertIsNotNone(result)
        self.assertEqual(result[1], 403)

    def test_viewer_allowed_cron_read(self):
        result = self._call('cron:read', self._viewer_scope())
        self.assertIsNone(result, 'viewer should be allowed cron:read')

    def test_viewer_allowed_log_read(self):
        result = self._call('log:read', self._viewer_scope())
        self.assertIsNone(result, 'viewer should be allowed log:read')

    def test_operator_allowed_cron_write(self):
        result = self._call('cron:write', self._operator_scope())
        self.assertIsNone(result, 'operator should be allowed cron:write')

    def test_operator_denied_cron_retire(self):
        result = self._call('cron:retire', self._operator_scope())
        self.assertIsNotNone(result, 'operator should be denied cron:retire')
        self.assertEqual(result[1], 403)

    def test_operator_denied_user_manage(self):
        result = self._call('user:manage', self._operator_scope())
        self.assertIsNotNone(result)
        self.assertEqual(result[1], 403)

    def test_admin_allowed_cron_retire(self):
        result = self._call('cron:retire', self._admin_scope())
        self.assertIsNone(result, 'admin should be allowed cron:retire')

    def test_admin_allowed_user_manage(self):
        result = self._call('user:manage', self._admin_scope())
        self.assertIsNone(result, 'admin should be allowed user:manage')

    def test_global_token_bypasses_all(self):
        result = self._call('cron:retire', self._global_admin_scope())
        self.assertIsNone(result, 'global admin token should bypass all checks')

    def test_seed_admin_denied_cron_write(self):
        """Seed admin (username='admin') has SEED_ADMIN_PERMISSIONS, not cron:write."""
        result = self._call('cron:write', self._seed_admin_scope())
        self.assertIsNotNone(result, 'seed admin should be denied cron:write')
        self.assertEqual(result[1], 403)

    def test_seed_admin_allowed_user_manage(self):
        result = self._call('user:manage', self._seed_admin_scope())
        self.assertIsNone(result, 'seed admin should be allowed user:manage')

    def test_error_message_contains_hint(self):
        result = self._call('cron:write', self._viewer_scope())
        resp_data = result[0].get_json()
        self.assertIn('权限不足', resp_data.get('errmsg', ''))


if __name__ == '__main__':
    unittest.main()
