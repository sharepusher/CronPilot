# -*- coding: utf-8 -*-
"""RBAC 全局 Scope、批量反馈与审批列表读取边界测试（S0 / B0 / R2-0）。

S0 故意在修复前保留漏洞路径的失败证据：正向基线必须通过，
scoped Biz Admin 的越权路径必须在当前实现上稳定变红。

B0 在修复批量反馈前冻结全成功、部分成功、全失败的响应真值契约。

R2-0 在修复审批列表前冻结精确组 token、数据库当前 actor、分页/计数
同源契约；旧实现上的安全红线应稳定失败，既有会话失效基线保持通过。
"""
import unittest
from unittest import mock

from datas.utils.times import utc_now_hms
from tests.test_registration import _make_app


class _GlobalScopeAssignmentFixture(unittest.TestCase):
    """S0 共享的内存数据库与 HTTP 驱动。"""

    def setUp(self):
        self.app, self.db = _make_app()
        self._prepare_database()

    def tearDown(self):
        with self.app.app_context():
            self.db.session.remove()
            self.db.drop_all()

    def _prepare_database(self):
        with self.app.app_context():
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            from datas.model.rbac_registration_request import RbacRegistrationRequest  # noqa: F401
            from datas.model.rbac_user import RbacUser
            from datas.model.resource_group import ResourceGroup
            from datas.model.user_group import UserGroup

            self.db.create_all()
            groups = [
                ResourceGroup(name=name, create_time=utc_now_hms())
                for name in ('S0-A', 'S0-B', 'S0-C')
            ]
            self.db.session.add_all(groups)
            self.db.session.flush()
            self.group_ids = [group.id for group in groups]

            actors = {
                'seed': ('admin', []),
                'global': ('s0_global_admin', []),
                'single': ('s0_single_admin', [self.group_ids[0]]),
                'multi': ('s0_multi_admin', self.group_ids[:2]),
                'operator': ('s0_operator', [self.group_ids[0]]),
                'viewer': ('s0_viewer', [self.group_ids[0]]),
            }
            self.actor_ids = {}
            for key, (username, group_ids) in actors.items():
                role = key if key in ('operator', 'viewer') else 'admin'
                user = RbacUser(
                    username=username,
                    role=role,
                    is_active=1,
                    auth_version=0,
                    create_time=utc_now_hms(),
                )
                user.set_password('test-password')
                self.db.session.add(user)
                self.db.session.flush()
                self.actor_ids[key] = user.id
                for group_id in group_ids:
                    self.db.session.add(UserGroup(user_id=user.id, group_id=group_id))

            target = RbacUser(
                username='s0_target',
                role='viewer',
                is_active=1,
                auth_version=0,
                email='before@example.invalid',
                nickname='before',
                job_title='qa',
                create_time=utc_now_hms(),
            )
            target.set_password('test-password')
            self.db.session.add(target)
            self.db.session.flush()
            self.target_id = target.id
            self.db.session.add(
                UserGroup(user_id=target.id, group_id=self.group_ids[0])
            )
            self.db.session.commit()

    def _login(self, client, actor_key):
        group_map = {
            'seed': [],
            'global': [],
            'single': [self.group_ids[0]],
            'multi': self.group_ids[:2],
            'operator': [self.group_ids[0]],
            'viewer': [self.group_ids[0]],
        }
        username_map = {
            'seed': 'admin',
            'global': 's0_global_admin',
            'single': 's0_single_admin',
            'multi': 's0_multi_admin',
            'operator': 's0_operator',
            'viewer': 's0_viewer',
        }
        role_map = {
            'operator': 'operator',
            'viewer': 'viewer',
        }
        with client.session_transaction() as session:
            session['is_login'] = True
            session['user_id'] = self.actor_ids[actor_key]
            session['username'] = username_map[actor_key]
            session['role'] = role_map.get(actor_key, 'admin')
            session['auth_version'] = 0
            session['group_ids'] = group_map[actor_key]

    @staticmethod
    def _ajax_headers():
        return {
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
        }

    def _post_add(self, client, username, group_ids):
        return client.post(
            '/rbac/users/add',
            data={
                'username': username,
                'role': 'admin',
                'group_ids': group_ids,
                'email': '%s@example.invalid' % username,
                'nickname': username,
                'job_title': 'qa',
            },
            headers=self._ajax_headers(),
        )

    def _post_edit(self, client, group_ids):
        return client.post(
            '/rbac/users/edit',
            data={
                'id': str(self.target_id),
                'role': 'admin',
                'is_active': '1',
                'group_ids': group_ids,
                'email': 'after@example.invalid',
                'nickname': 'after',
                'job_title': 'ops',
            },
            headers=self._ajax_headers(),
        )

class TestGlobalScopeAssignmentBaseline(_GlobalScopeAssignmentFixture):
    """已有正确能力的绿色基线。"""

    def test_seed_admin_can_add_global_admin(self):
        with self.app.test_client() as client:
            self._login(client, 'seed')
            response = self._post_add(client, 's0_seed_created', '__ALL__')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['errcode'], 0)

    def test_non_seed_global_admin_can_edit_to_global_admin(self):
        with self.app.test_client() as client:
            self._login(client, 'global')
            response = self._post_edit(client, '__ALL__')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['errcode'], 0)
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            from datas.model.user_group import UserGroup

            target = self.db.session.get(RbacUser, self.target_id)
            links = self.db.session.query(UserGroup).filter_by(user_id=self.target_id).all()
            self.assertEqual(target.role, 'admin')
            self.assertEqual(links, [])


class TestUserManagementCurrentActorRedLines(_GlobalScopeAssignmentFixture):
    """R-02：用户管理读取与目标操作不得信任陈旧 Session Scope。"""

    def _add_target(self, username, group_id):
        from datas.model.rbac_user import RbacUser
        from datas.model.user_group import UserGroup

        with self.app.app_context():
            user = RbacUser(
                username=username,
                role='viewer',
                is_active=1,
                auth_version=0,
                email='%s@example.invalid' % username,
                nickname=username,
                job_title='qa',
                create_time=utc_now_hms(),
            )
            user.set_password('test-password')
            self.db.session.add(user)
            self.db.session.flush()
            self.db.session.add(UserGroup(user_id=user.id, group_id=group_id))
            self.db.session.commit()
            return user.id

    def _downgrade_global_to_group_one(self):
        from datas.model.user_group import UserGroup

        with self.app.app_context():
            self.db.session.add(UserGroup(
                user_id=self.actor_ids['global'],
                group_id=self.group_ids[0],
            ))
            self.db.session.commit()

    def test_stale_global_session_lists_only_database_current_group(self):
        """B0: DB global→组 A 后，旧 Cookie 不得继续列出组 B。"""
        outside_id = self._add_target('r02_outside_list', self.group_ids[2])
        self._downgrade_global_to_group_one()

        with self.app.test_client() as client:
            self._login(client, 'global')
            response = client.get('/rbac/users?username=r02_outside_list')

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            'data-user-id="%s"' % outside_id,
            response.get_data(as_text=True),
        )
        with self.app.app_context():
            self.assertIsNotNone(self.db.session.get(
                __import__('datas.model.rbac_user', fromlist=['RbacUser']).RbacUser,
                outside_id,
            ))

    def test_stale_global_session_cannot_view_or_reset_outside_target(self):
        """B0: 详情与敏感 POST 均在目标读取/写入前拒绝。"""
        outside_id = self._add_target('r02_outside_action', self.group_ids[2])
        self._downgrade_global_to_group_one()

        with self.app.test_client() as client:
            self._login(client, 'global')
            view = client.get('/rbac/users/view?id=%s' % outside_id)
            reset = client.post(
                '/rbac/users/reset_token',
                data={'id': str(outside_id)},
                headers=self._ajax_headers(),
            )

        self.assertEqual(view.status_code, 302)
        self.assertEqual(view.headers['Location'], '/rbac/users')
        self.assertEqual(reset.status_code, 200)
        self.assertEqual(reset.get_json()['errcode'], 1)
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            target = self.db.session.get(RbacUser, outside_id)
            self.assertFalse(target.api_token)

    def test_database_role_downgrade_blocks_all_user_management_entries(self):
        """B0: admin→viewer 的旧 admin Cookie 不得进入任一用户管理入口。"""
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            actor = self.db.session.get(RbacUser, self.actor_ids['multi'])
            actor.role = 'viewer'
            self.db.session.commit()

        with self.app.test_client() as client:
            self._login(client, 'multi')
            requests = (
                ('list', client.get, '/rbac/users', {}),
                ('add', client.get, '/rbac/users/add', {}),
                ('edit', client.get, '/rbac/users/edit?id=%s' % self.target_id, {}),
                ('view', client.get, '/rbac/users/view?id=%s' % self.target_id, {}),
                ('reset_password', client.post, '/rbac/users/reset_password', {'id': self.target_id}),
                ('reset_token', client.post, '/rbac/users/reset_token', {'id': self.target_id}),
                ('set_active', client.get, '/rbac/users/set_active?id=%s' % self.target_id, {}),
            )
            for entry, method, url, data in requests:
                with self.subTest(entry=entry):
                    response = method(url, data=data, headers=self._ajax_headers())
                    self.assertEqual(response.status_code, 403)

    def test_atomic_user_update_bumps_auth_version_once_only_for_authorization_change(self):
        """B2: 角色/组变更与资料同事务，授权变更仅 bump 一次。"""
        from app.rbac.services import update_user_management
        from datas.model.rbac_user import RbacUser

        with self.app.test_request_context('/rbac/users/edit'):
            from flask import session

            session['user_id'] = self.actor_ids['seed']
            target = self.db.session.get(RbacUser, self.target_id)
            before = target.auth_version
            changed = update_user_management(
                self.target_id,
                role='admin',
                is_active=1,
                group_ids=[self.group_ids[0]],
                email='atomic@example.invalid',
                nickname='atomic',
                job_title='ops',
            )
            self.assertTrue(changed['ok'])
            self.assertTrue(changed['auth_version_bumped'])
            target = self.db.session.get(RbacUser, self.target_id)
            self.assertEqual(target.auth_version, before + 1)
            self.assertEqual(target.email, 'atomic@example.invalid')

            profile_only = update_user_management(
                self.target_id,
                role='admin',
                is_active=1,
                group_ids=[self.group_ids[0]],
                email='atomic@example.invalid',
                nickname='atomic-2',
                job_title='qa',
            )
            self.assertTrue(profile_only['ok'])
            self.assertFalse(profile_only['auth_version_bumped'])
            self.assertEqual(target.auth_version, before + 1)
            self.assertEqual(target.nickname, 'atomic-2')

    def test_scoped_admin_can_add_admin_in_own_group_subset(self):
        with self.app.test_client() as client:
            self._login(client, 'multi')
            response = self._post_add(
                client, 's0_subset_created', str(self.group_ids[0])
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['errcode'], 0)

    def test_all_marker_mixed_with_specific_group_is_rejected(self):
        with self.app.test_client() as client:
            self._login(client, 'seed')
            response = self._post_add(
                client,
                's0_mixed_scope',
                ['__ALL__', str(self.group_ids[0])],
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['errcode'], 1)

    def test_operator_and_viewer_cannot_write_users(self):
        for actor_key in ('operator', 'viewer'):
            username = 's0_forbidden_%s' % actor_key
            with self.subTest(actor=actor_key):
                with self.app.test_client() as client:
                    self._login(client, actor_key)
                    response = self._post_add(
                        client, username, str(self.group_ids[0])
                    )
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.get_json()['errcode'], 1)
                self.assertIsNone(self._find_user_id(username))

    def _find_user_id(self, username):
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser

            user = self.db.session.query(RbacUser).filter_by(username=username).first()
            return user.id if user else None


class TestGlobalScopeAssignmentPolicy(_GlobalScopeAssignmentFixture):
    """S1 纯策略与只读数据库适配器。"""

    def test_pure_policy_matrix(self):
        from app.rbac.policy import user_scope_assignment_denial

        cases = [
            ('seed_global', 'admin', 'admin', [], 'admin', True, [], None),
            ('global_global', 'admin', 's0_global_admin', [], 'admin', True, [], None),
            ('scoped_subset', 'admin', 'biz', [1, 2], 'admin', False, [1], None),
            (
                'scoped_global', 'admin', 'biz', [1], 'admin', True, [],
                'actor_global_assignment_denied',
            ),
            (
                'scoped_outside', 'admin', 'biz', [1], 'admin', False, [2],
                'actor_group_assignment_denied',
            ),
            (
                'operator', 'operator', 'op', [1], 'viewer', False, [1],
                'actor_permission_denied',
            ),
            (
                'global_non_admin_target', 'admin', 'admin', [], 'viewer', True, [],
                'target_role_global_forbidden',
            ),
            (
                'empty_specific_scope', 'admin', 'admin', [], 'admin', False, [],
                'requested_groups_required',
            ),
        ]
        for case in cases:
            name, role, username, actor_groups, target_role, is_global, groups, expected = case
            with self.subTest(case=name):
                self.assertEqual(
                    user_scope_assignment_denial(
                        role,
                        username,
                        actor_groups,
                        target_role,
                        is_global,
                        groups,
                    ),
                    expected,
                )

    def _validate(self, actor_key, target_role='admin', group_ids=None):
        from app.rbac.services import validate_user_scope_assignment

        return validate_user_scope_assignment(
            self.actor_ids[actor_key],
            target_role,
            ['__ALL__'] if group_ids is None else group_ids,
        )

    def test_service_allows_seed_global_and_scoped_subset(self):
        with self.app.app_context():
            self.assertTrue(self._validate('seed')['ok'])
            self.assertTrue(self._validate('global')['ok'])
            result = self._validate('multi', group_ids=[self.group_ids[0]])
            self.assertTrue(result['ok'])
            self.assertFalse(result['is_global'])
            self.assertEqual(result['group_ids'], [self.group_ids[0]])

    def test_service_rejects_scoped_global_and_outside_group(self):
        with self.app.app_context():
            global_result = self._validate('multi')
            outside_result = self._validate(
                'multi', group_ids=[self.group_ids[2]]
            )
        self.assertEqual(
            global_result['reason'], 'actor_global_assignment_denied'
        )
        self.assertEqual(
            outside_result['reason'], 'actor_group_assignment_denied'
        )

    def test_service_rejects_invalid_scope_parameters(self):
        cases = [
            (['__ALL__', self.group_ids[0]], 'scope_marker_mixed'),
            (['not-an-id'], 'group_id_invalid'),
            ([999999], 'group_not_found'),
            ([], 'requested_groups_required'),
        ]
        with self.app.app_context():
            for group_ids, expected in cases:
                with self.subTest(reason=expected):
                    result = self._validate('seed', group_ids=group_ids)
                    self.assertFalse(result['ok'])
                    self.assertEqual(result['reason'], expected)

    def test_service_rejects_global_scope_for_non_admin_target(self):
        with self.app.app_context():
            result = self._validate('seed', target_role='viewer')
        self.assertEqual(result['reason'], 'target_role_global_forbidden')

    def test_service_rejects_missing_and_inactive_actor(self):
        from app.rbac.services import validate_user_scope_assignment
        from datas.model.rbac_user import RbacUser

        with self.app.app_context():
            missing = validate_user_scope_assignment(
                999999, 'admin', ['__ALL__']
            )
            actor = self.db.session.get(RbacUser, self.actor_ids['global'])
            actor.is_active = 0
            self.db.session.commit()
            inactive = self._validate('global')
        self.assertEqual(missing['reason'], 'actor_missing_or_inactive')
        self.assertEqual(inactive['reason'], 'actor_missing_or_inactive')

    def test_service_uses_current_database_role_not_stale_session(self):
        from flask import session

        from datas.model.rbac_user import RbacUser

        with self.app.test_request_context():
            session['role'] = 'admin'
            session['username'] = 's0_multi_admin'
            session['group_ids'] = self.group_ids[:2]
            actor = self.db.session.get(RbacUser, self.actor_ids['multi'])
            actor.role = 'viewer'
            self.db.session.commit()
            result = self._validate('multi', group_ids=[self.group_ids[0]])
        self.assertEqual(result['reason'], 'actor_permission_denied')

    def test_service_uses_current_database_groups_not_stale_session(self):
        from flask import session

        from datas.model.user_group import UserGroup

        with self.app.test_request_context():
            session['role'] = 'admin'
            session['username'] = 's0_multi_admin'
            session['group_ids'] = self.group_ids[:2]
            link = self.db.session.query(UserGroup).filter_by(
                user_id=self.actor_ids['multi'],
                group_id=self.group_ids[1],
            ).one()
            self.db.session.delete(link)
            self.db.session.commit()
            result = self._validate('multi', group_ids=[self.group_ids[1]])
        self.assertEqual(result['reason'], 'actor_group_assignment_denied')

    def test_service_fails_closed_when_actor_read_raises(self):
        with self.app.app_context(), mock.patch(
            'app.rbac.services._load_scope_assignment_actor',
            side_effect=RuntimeError('simulated read failure'),
        ), mock.patch('app.rbac.services.logger.exception') as log_exception:
            result = self._validate('global')
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'authorization_check_failed')
        log_exception.assert_called_once()

    def test_service_validation_has_no_business_write_side_effect(self):
        from datas.model.rbac_audit_log import RbacAuditLog
        from datas.model.rbac_user import RbacUser
        from datas.model.user_group import UserGroup

        with self.app.app_context():
            before = (
                self.db.session.query(RbacUser).count(),
                self.db.session.query(UserGroup).count(),
                self.db.session.query(RbacAuditLog).count(),
            )
            self._validate('global')
            self._validate('multi')
            after = (
                self.db.session.query(RbacUser).count(),
                self.db.session.query(UserGroup).count(),
                self.db.session.query(RbacAuditLog).count(),
            )
        self.assertEqual(before, after)


class TestGlobalScopeAssignmentRedline(_GlobalScopeAssignmentFixture):
    """修复前应稳定失败的安全红线。"""

    def _user_snapshot(self, username):
        with self.app.app_context():
            from datas.model.rbac_audit_log import RbacAuditLog
            from datas.model.rbac_user import RbacUser
            from datas.model.user_group import UserGroup

            user = self.db.session.query(RbacUser).filter_by(username=username).first()
            if not user:
                return None
            group_ids = tuple(sorted(
                row.group_id
                for row in self.db.session.query(UserGroup).filter_by(user_id=user.id)
            ))
            success_audits = self.db.session.query(RbacAuditLog).filter(
                RbacAuditLog.resource.in_([username, '%s:groups' % username]),
                RbacAuditLog.status == 'allow',
            ).count()
            return (
                user.id, user.role, user.is_active, user.api_token is not None,
                user.api_token_expires_at,
                user.email, user.nickname, user.job_title, group_ids, success_audits,
            )

    def _assert_denied_without_add_side_effect(self, actor_key, username, group_ids):
        before = self._user_snapshot(username)
        with self.app.test_client() as client:
            self._login(client, actor_key)
            response = self._post_add(client, username, group_ids)
        payload = response.get_json()
        after = self._user_snapshot(username)
        failures = []
        if response.status_code not in (200, 403):
            failures.append('unexpected_status=%s' % response.status_code)
        if not payload or payload.get('errcode') != 1:
            failures.append('request_was_not_denied payload=%r' % payload)
        if before != after:
            failures.append('database_changed before=%r after=%r' % (before, after))
        self.assertEqual(failures, [])

    def _assert_denied_without_edit_side_effect(self, actor_key, group_ids):
        before = self._user_snapshot('s0_target')
        with self.app.test_client() as client:
            self._login(client, actor_key)
            response = self._post_edit(client, group_ids)
        payload = response.get_json()
        after = self._user_snapshot('s0_target')
        failures = []
        if response.status_code not in (200, 403):
            failures.append('unexpected_status=%s' % response.status_code)
        if not payload or payload.get('errcode') != 1:
            failures.append('request_was_not_denied payload=%r' % payload)
        if before != after:
            failures.append('database_changed before=%r after=%r' % (before, after))
        self.assertEqual(failures, [])

    def test_single_group_admin_direct_all_add_is_rejected_without_side_effect(self):
        self._assert_denied_without_add_side_effect(
            'single', 's0_single_global_add', '__ALL__'
        )

    def test_multi_group_admin_direct_all_add_is_rejected_without_side_effect(self):
        self._assert_denied_without_add_side_effect(
            'multi', 's0_multi_global_add', '__ALL__'
        )

    def test_single_group_admin_direct_all_edit_is_rejected_without_side_effect(self):
        self._assert_denied_without_edit_side_effect('single', '__ALL__')

    def test_multi_group_admin_direct_all_edit_is_rejected_without_side_effect(self):
        self._assert_denied_without_edit_side_effect('multi', '__ALL__')

    def test_multi_group_admin_out_of_scope_group_is_rejected_without_side_effect(self):
        self._assert_denied_without_add_side_effect(
            'multi', 's0_out_of_scope_add', str(self.group_ids[2])
        )

    def test_multi_group_admin_out_of_scope_edit_is_rejected_without_side_effect(self):
        self._assert_denied_without_edit_side_effect('multi', str(self.group_ids[2]))


class TestGlobalScopeAssignmentRouteGuard(_GlobalScopeAssignmentFixture):
    """S2 路由写入边界、响应与拒绝审计。"""

    def _target_state(self):
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            from datas.model.user_group import UserGroup

            user = self.db.session.get(RbacUser, self.target_id)
            group_ids = tuple(sorted(
                row.group_id
                for row in self.db.session.query(UserGroup).filter_by(
                    user_id=user.id
                )
            ))
            return (
                user.role,
                user.is_active,
                user.api_token is not None,
                user.email,
                user.nickname,
                user.job_title,
                group_ids,
            )

    def test_native_add_global_scope_denial_has_no_business_side_effect(self):
        username = 's2_native_denied_add'
        with self.app.test_client() as client:
            self._login(client, 'multi')
            response = client.post(
                '/rbac/users/add',
                data={
                    'username': username,
                    'role': 'admin',
                    'group_ids': '__ALL__',
                    'email': 'native@example.invalid',
                    'nickname': 'native',
                    'job_title': 'qa',
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn('您无权授予全局管理权限', response.get_data(as_text=True))
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser

            self.assertIsNone(
                self.db.session.query(RbacUser).filter_by(username=username).first()
            )


    def test_native_edit_global_scope_denial_has_no_business_side_effect(self):
        before = self._target_state()
        with self.app.test_client() as client:
            self._login(client, 'multi')
            response = client.post(
                '/rbac/users/edit',
                data={
                    'id': str(self.target_id),
                    'role': 'admin',
                    'is_active': '1',
                    'group_ids': '__ALL__',
                    'email': 'native-after@example.invalid',
                    'nickname': 'native-after',
                    'job_title': 'ops',
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn('您无权授予全局管理权限', response.get_data(as_text=True))
        self.assertEqual(before, self._target_state())

    def test_edit_uses_database_target_scope_not_stale_session_groups(self):
        from datas.model.user_group import UserGroup

        with self.app.app_context():
            target_link = self.db.session.query(UserGroup).filter_by(
                user_id=self.target_id,
                group_id=self.group_ids[0],
            ).one()
            target_link.group_id = self.group_ids[1]
            actor_link = self.db.session.query(UserGroup).filter_by(
                user_id=self.actor_ids['multi'],
                group_id=self.group_ids[1],
            ).one()
            self.db.session.delete(actor_link)
            self.db.session.commit()
        before = self._target_state()
        with self.app.test_client() as client:
            self._login(client, 'multi')
            response = self._post_edit(client, str(self.group_ids[0]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['errcode'], 1)
        self.assertIn('不在您的管理范围', response.get_json()['errmsg'])
        self.assertEqual(before, self._target_state())

    def test_confirm_reactivation_cannot_bypass_scope_guard(self):
        from datas.model.rbac_user import RbacUser
        from datas.model.user_group import UserGroup

        with self.app.app_context():
            disabled = RbacUser(
                username='s2_disabled_target',
                role='viewer',
                is_active=0,
                auth_version=1,
                create_time=utc_now_hms(),
            )
            disabled.set_password('old-password')
            self.db.session.add(disabled)
            self.db.session.flush()
            self.db.session.add(UserGroup(
                user_id=disabled.id,
                group_id=self.group_ids[0],
            ))
            self.db.session.commit()
            disabled_id = disabled.id
        with self.app.test_client() as client:
            self._login(client, 'multi')
            response = client.post(
                '/rbac/users/add',
                data={
                    'username': 's2_disabled_target',
                    'role': 'admin',
                    'group_ids': '__ALL__',
                    'job_title': 'qa',
                    'confirm_reactivation': '1',
                },
                headers=self._ajax_headers(),
            )
        self.assertEqual(response.get_json()['errcode'], 1)
        with self.app.app_context():
            user = self.db.session.get(RbacUser, disabled_id)
            self.assertEqual(user.is_active, 0)
            self.assertEqual(user.role, 'viewer')

    def test_denial_audit_contains_only_stable_security_metadata(self):
        import json

        from datas.model.rbac_audit_log import RbacAuditLog

        with self.app.test_client() as client:
            self._login(client, 'multi')
            response = self._post_add(client, 's2_audit_denied', '__ALL__')
        self.assertEqual(response.get_json()['errcode'], 1)
        with self.app.app_context():
            entry = self.db.session.query(RbacAuditLog).filter_by(
                action='scope:deny',
                resource='users:add',
                status='deny',
            ).one()
            detail = json.loads(entry.detail)
            self.assertEqual(detail['entry'], 'users:add')
            self.assertEqual(detail['reason'], 'actor_global_assignment_denied')
            self.assertIsNone(detail['target_user_id'])
            self.assertNotIn('s2_audit_denied', entry.detail)
            self.assertNotIn('token', entry.detail.lower())

    def test_denial_audit_failure_does_not_fail_open(self):
        username = 's2_audit_failure_denied'
        with self.app.test_client() as client, mock.patch(
            'app.rbac.views.write_audit_log',
            side_effect=RuntimeError('simulated audit failure'),
        ), mock.patch.object(self.app.logger, 'error') as log_error:
            self._login(client, 'multi')
            response = self._post_add(client, username, '__ALL__')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['errcode'], 1)
        log_error.assert_called_once()
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser

            self.assertIsNone(
                self.db.session.query(RbacUser).filter_by(username=username).first()
            )


class TestGlobalScopeAssignmentPageExposure(_GlobalScopeAssignmentFixture):
    """S3 页面只暴露当前 actor 真正可授予的全局 Scope 能力。"""

    def _get_add_html(self, actor_key):
        with self.app.test_client() as client:
            self._login(client, actor_key)
            response = client.get('/rbac/users/add')
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    def _get_edit_html(self, actor_key):
        with self.app.test_client() as client:
            self._login(client, actor_key)
            response = client.get('/rbac/users/edit?id=%s' % self.target_id)
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    def _create_global_admin_target(self):
        from datas.model.rbac_user import RbacUser

        with self.app.app_context():
            user = RbacUser(
                username='s3_global_form_target',
                role='admin',
                is_active=1,
                auth_version=0,
                email='s3_global_form_target@example.invalid',
                nickname='global-form',
                job_title='qa',
                create_time=utc_now_hms(),
            )
            user.set_password('test-password')
            self.db.session.add(user)
            self.db.session.commit()
            return user.id

    def test_global_admin_edit_replays_all_marker_without_group_rows(self):
        """B0: 零 UserGroup 行的 global admin 必须选中 __ALL__。"""
        target_id = self._create_global_admin_target()
        with self.app.test_client() as client:
            self._login(client, 'seed')
            response = client.get('/rbac/users/edit?id=%s' % target_id)
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        group_select = html.split('id="uf-group-select"', 1)[1].split('</select>', 1)[0]
        self.assertIn('<option value="__ALL__" selected>', group_select)
        self.assertNotIn(
            '<option value="%s" selected>' % self.group_ids[0], group_select,
        )

    def test_seed_and_global_admin_pages_expose_global_option(self):
        for actor_key in ('seed', 'global'):
            with self.subTest(actor=actor_key):
                html = self._get_add_html(actor_key)
                self.assertIn('<option value="__ALL__"', html)
                self.assertIn('全部（全局权限）', html)

    def test_multi_group_admin_add_and_edit_hide_global_option(self):
        for page_html in (
            self._get_add_html('multi'),
            self._get_edit_html('multi'),
        ):
            self.assertNotIn('<option value="__ALL__"', page_html)
            self.assertIn('您只能将用户分配到当前管理的业务组', page_html)

    def test_single_group_admin_keeps_locked_group_without_global_option(self):
        html = self._get_add_html('single')
        self.assertNotIn('<option value="__ALL__"', html)
        self.assertIn('name="group_ids" value="%s"' % self.group_ids[0], html)
        self.assertIn('您的业务组已由系统自动设置，无法更改', html)

    def test_database_scope_downgrade_hides_option_despite_global_session(self):
        from datas.model.user_group import UserGroup

        with self.app.app_context():
            self.db.session.add(UserGroup(
                user_id=self.actor_ids['global'],
                group_id=self.group_ids[0],
            ))
            self.db.session.commit()
        html = self._get_add_html('global')
        self.assertNotIn('<option value="__ALL__"', html)
        self.assertIn('name="group_ids" value="%s"' % self.group_ids[0], html)
        self.assertIn('您的业务组已由系统自动设置，无法更改', html)

    def test_native_validation_rerender_preserves_global_admin_option(self):
        with self.app.test_client() as client:
            self._login(client, 'global')
            response = client.post(
                '/rbac/users/add',
                data={
                    'username': 's3_global_rerender',
                    'role': 'admin',
                    'group_ids': '__ALL__',
                    'job_title': '',
                },
            )
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('岗位类型为必填项', html)
        self.assertIn('<option value="__ALL__"', html)

    def test_native_validation_rerender_keeps_scoped_option_hidden(self):
        with self.app.test_client() as client:
            self._login(client, 'multi')
            response = client.post(
                '/rbac/users/add',
                data={
                    'username': 's3_scoped_rerender',
                    'role': 'admin',
                    'group_ids': str(self.group_ids[0]),
                    'job_title': '',
                },
            )
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('岗位类型为必填项', html)
        self.assertNotIn('<option value="__ALL__"', html)
        self.assertIn('您只能将用户分配到当前管理的业务组', html)


class TestRegistrationReviewScopeRedLines(_GlobalScopeAssignmentFixture):
    """R2-0：审批列表读取 Scope 的红线与既有绿色基线。"""

    def setUp(self):
        super().setUp()
        with self.app.app_context():
            from datas.model.resource_group import ResourceGroup

            # 显式制造 1/10 数字边界；不得依赖自增恰好生成某个 ID。
            self.group_10 = ResourceGroup(
                id=10,
                name='R2-Group-10',
                create_time=utc_now_hms(),
            )
            self.db.session.add(self.group_10)
            self.db.session.commit()

    def _create_review_request(
        self, username, group_ids, role='viewer', status='pending',
        with_relations=True,
    ):
        from datas.model.rbac_registration_request import RbacRegistrationRequest

        with self.app.app_context():
            req = RbacRegistrationRequest(
                email='%s@example.invalid' % username,
                username=username,
                password_hash='not-used-by-r2-read-test',
                role=role,
                group_ids=group_ids,
                job_title='qa',
                nickname=username,
                reason='R2-0 list scope red line',
                status=status,
                pending_username=username if status == 'pending' else None,
                create_time=utc_now_hms(),
            )
            self.db.session.add(req)
            self.db.session.flush()
            if with_relations and group_ids != '__ALL__':
                from datas.model.rbac_registration_request_group import RbacRegistrationRequestGroup

                for group_id in {int(value) for value in group_ids.split(',')}:
                    self.db.session.add(RbacRegistrationRequestGroup(
                        registration_request_id=req.id, group_id=group_id,
                    ))
            self.db.session.commit()
            return req.id

    def test_association_boundaries_share_list_and_count(self):
        """R2-2D：多组不重复、非法角色/缺关联/全局污染均拒绝。"""
        from app.repositories.registration_request_repository import RegistrationRequestRepository
        from app.services.pagination import PageQuery
        from datas.model.rbac_registration_request_group import RbacRegistrationRequestGroup

        self._create_review_request('d_operator', '1,2', role='operator')
        self._create_review_request('d_admin_subset', '1,2', role='admin')
        self._create_review_request('d_admin_outside', '1,3', role='admin')
        self._create_review_request('d_missing', '1', with_relations=False)
        self._create_review_request('d_unknown_role', '1', role='unknown')
        global_id = self._create_review_request('d_global', '__ALL__', role='admin')
        with self.app.app_context():
            self.db.session.add(RbacRegistrationRequestGroup(
                registration_request_id=global_id, group_id=1,
            ))
            self.db.session.commit()
            repo = RegistrationRequestRepository(self.db.session)
            for groups, expected in [
                ([], set()),
                ([1], {'d_operator'}),
                ([1, 2], {'d_operator', 'd_admin_subset'}),
            ]:
                with self.subTest(groups=groups):
                    page = repo.paginate_by_groups(PageQuery(), groups)
                    self.assertEqual({row.username for row in page.items}, expected)
                    self.assertEqual(len(page.items), len(expected))
                    self.assertEqual(page.total, len(expected))
                    self.assertEqual(repo.get_pending_count_by_groups(groups), len(expected))
            self.assertEqual(repo.paginate_all(PageQuery()).total, 6)

    def test_visibility_sql_compiles_for_both_backends(self):
        """双分支集合查询必须同时编译到 SQLite 与 MySQL。"""
        from sqlalchemy import select
        from sqlalchemy.dialects import mysql, sqlite

        from app.repositories.registration_request_repository import RegistrationRequestRepository
        from datas.model.rbac_registration_request import RbacRegistrationRequest

        stmt = select(RbacRegistrationRequest).where(
            RegistrationRequestRepository._scoped_visibility([1, 2]),
        )
        for dialect in (sqlite.dialect(), mysql.dialect()):
            sql = str(stmt.compile(dialect=dialect)).upper()
            self.assertIn('UNION ALL', sql)
            self.assertIn('SUM(CASE WHEN', sql)
            self.assertIn('GROUP BY', sql)
            self.assertNotIn(' LIKE ', sql)
            self.assertNotIn('EXISTS', sql)

    def _get_review(self, actor_key, query=''):
        with self.app.test_client() as client:
            self._login(client, actor_key)
            response = client.get('/rbac/registration_review%s' % query)
            return response, response.get_data(as_text=True)

    def test_group_1_does_not_match_group_10_in_rows_total_or_badge(self):
        """RL-01：完整 token 1 不得命中字符串 token 10。"""
        allowed = 'r2_group_1_allowed'
        leaked = 'r2_group_10_must_be_hidden'
        self._create_review_request(allowed, str(self.group_ids[0]))
        self._create_review_request(leaked, '10')

        response, html = self._get_review('single')

        self.assertEqual(response.status_code, 200)
        self.assertIn(allowed, html)
        self.assertNotIn(leaked, html)
        self.assertIn('1 total', html)
        self.assertIn('注册审批 <span class="pg-badge-count">1</span>', html)

    def test_group_10_does_not_match_group_1_reverse_baseline(self):
        """RL-02：反向数字边界基线，避免只覆盖一个字符串方向。"""
        from datas.model.user_group import UserGroup

        actor_id = self.actor_ids['single']
        with self.app.app_context():
            link = self.db.session.query(UserGroup).filter_by(
                user_id=actor_id,
            ).one()
            link.group_id = 10
            self.db.session.commit()
        hidden = 'r2_group_1_reverse_hidden'
        self._create_review_request(hidden, str(self.group_ids[0]))

        # Session 同步成组 10；该用例只验证 token 方向，不测试陈旧 Session。
        with self.app.test_client() as client:
            self._login(client, 'single')
            with client.session_transaction() as session:
                session['group_ids'] = [10]
            response = client.get('/rbac/registration_review')
            html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(hidden, html)
        self.assertIn('0 total', html)

    def test_viewer_request_with_exact_intersection_remains_visible(self):
        """RL-03：viewer/operator 使用精确交集，而不是完整子集。"""
        username = 'r2_intersection_allowed'
        self._create_review_request(
            username, '%s,10' % self.group_ids[0], role='viewer',
        )

        response, html = self._get_review('single')

        self.assertEqual(response.status_code, 200)
        self.assertIn(username, html)
        self.assertIn('1 total', html)

    def test_admin_partial_subset_excluded_from_rows_total_and_badge(self):
        """RL-04：admin 请求组必须被 actor 完整覆盖，且在分页前排除。"""
        allowed = 'r2_admin_subset_allowed'
        hidden = 'r2_admin_partial_subset_hidden'
        self._create_review_request(
            allowed, str(self.group_ids[0]), role='admin',
        )
        self._create_review_request(
            hidden,
            '%s,%s' % (self.group_ids[0], self.group_ids[1]),
            role='admin',
        )

        response, html = self._get_review('single')

        self.assertEqual(response.status_code, 200)
        self.assertIn(allowed, html)
        self.assertNotIn(hidden, html)
        self.assertIn('1 total', html)
        self.assertIn('<span class="cp-nav-badge">1</span>', html)
        self.assertIn('注册审批 <span class="pg-badge-count">1</span>', html)

    def test_database_global_to_scoped_overrides_stale_global_session(self):
        """RL-05：数据库 global→组 1 后，旧 global Session 不得继续全量读取。"""
        from datas.model.user_group import UserGroup

        allowed = 'r2_downgrade_group_1_allowed'
        hidden = 'r2_downgrade_group_2_hidden'
        self._create_review_request(allowed, str(self.group_ids[0]))
        # 使用组 2 隔离 actor 来源；1/10 token 碰撞由 RL-01/RL-10 单独负责。
        self._create_review_request(hidden, str(self.group_ids[1]))
        with self.app.app_context():
            self.db.session.add(UserGroup(
                user_id=self.actor_ids['global'],
                group_id=self.group_ids[0],
            ))
            self.db.session.commit()

        response, html = self._get_review('global')

        self.assertEqual(response.status_code, 200)
        self.assertIn(allowed, html)
        self.assertNotIn(hidden, html)
        self.assertIn('1 total', html)
        self.assertIn('<span class="cp-nav-badge">1</span>', html)

    def test_actor_scope_is_resolved_once_per_request(self):
        """R2-1：列表、标题与导航 badge 复用同一请求级 actor 结果。"""
        from app.rbac.services import resolve_user_management_actor

        with mock.patch(
            'app.rbac.registration_scope.resolve_user_management_actor',
            wraps=resolve_user_management_actor,
        ) as resolver, self.app.test_client() as client:
            self._login(client, 'single')
            response = client.get('/rbac/registration_review')

        self.assertEqual(response.status_code, 200)
        resolver.assert_called_once_with(self.actor_ids['single'])

    def test_database_group_shrink_overrides_stale_multi_group_session(self):
        """RL-06：DB 组 1,2→1 后，旧 Session 不得继续读取组 2。"""
        from datas.model.user_group import UserGroup

        allowed = 'r2_shrink_group_1_allowed'
        hidden = 'r2_shrink_group_2_hidden'
        self._create_review_request(allowed, str(self.group_ids[0]))
        self._create_review_request(hidden, str(self.group_ids[1]))
        with self.app.app_context():
            link = self.db.session.query(UserGroup).filter_by(
                user_id=self.actor_ids['multi'],
                group_id=self.group_ids[1],
            ).one()
            self.db.session.delete(link)
            self.db.session.commit()

        response, html = self._get_review('multi')

        self.assertEqual(response.status_code, 200)
        self.assertIn(allowed, html)
        self.assertNotIn(hidden, html)
        self.assertIn('1 total', html)
        self.assertIn('<span class="cp-nav-badge">1</span>', html)

    def test_disabled_actor_session_is_revoked_existing_green_baseline(self):
        """RL-07：停用已由 auth_version/active 全局守卫处理，不是新红线。"""
        from datas.model.rbac_user import RbacUser

        with self.app.test_client() as client:
            self._login(client, 'single')
            with self.app.app_context():
                actor = self.db.session.get(
                    RbacUser, self.actor_ids['single'],
                )
                actor.is_active = 0
                actor.auth_version = 1
                self.db.session.commit()
            response = client.get('/rbac/registration_review')
            with client.session_transaction() as session:
                self.assertNotIn('is_login', session)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/rbac/login?msg=', response.headers['Location'])

    def test_database_role_downgrade_overrides_stale_admin_permission(self):
        """RL-08：数据库当前角色无 user:manage 时固定返回 403。"""
        from datas.model.rbac_user import RbacUser

        with self.app.test_client() as client:
            self._login(client, 'single')
            with self.app.app_context():
                actor = self.db.session.get(
                    RbacUser, self.actor_ids['single'],
                )
                actor.role = 'viewer'
                self.db.session.commit()
            response = client.get('/rbac/registration_review')

        self.assertEqual(response.status_code, 403)
        self.assertNotIn('rr-select-all', response.get_data(as_text=True))

    def test_scope_query_failure_returns_generic_500_without_raw_error(self):
        """RL-09：授权查询故障不得回退 Session 或伪装为空列表。"""
        raw_error = 'scope database password must stay server-side'
        old_propagate = self.app.config.get('PROPAGATE_EXCEPTIONS')
        self.app.config['PROPAGATE_EXCEPTIONS'] = False
        try:
            with mock.patch(
                'app.repositories.registration_request_repository.'
                'RegistrationRequestRepository.paginate_by_groups',
                side_effect=RuntimeError(raw_error),
            ), self.app.test_client() as client:
                self._login(client, 'single')
                response = client.get('/rbac/registration_review')
        finally:
            self.app.config['PROPAGATE_EXCEPTIONS'] = old_propagate

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn(raw_error, body)
        self.assertNotIn('暂无注册申请', body)

    def test_mixed_scope_pagination_uses_authorized_total_and_items(self):
        """RL-10：跨页 items/total/pages 必须基于同一授权集合。"""
        from app.repositories.registration_request_repository import (
            RegistrationRequestRepository,
        )
        from app.services.pagination import PageQuery
        from datas.model.rbac_registration_request import RbacRegistrationRequest

        with self.app.app_context():
            rows = []
            for index in range(21):
                username = 'r2_page_allowed_%02d' % index
                rows.append(RbacRegistrationRequest(
                    email='%s@example.invalid' % username,
                    username=username,
                    password_hash='not-used-by-r2-read-test',
                    role='viewer',
                    group_ids=str(self.group_ids[0]),
                    job_title='qa',
                    nickname=username,
                    reason='R2-0 pagination allowed',
                    status='pending',
                    pending_username=username,
                    create_time=utc_now_hms(),
                ))
            for index in range(5):
                username = 'r2_page_group_10_hidden_%02d' % index
                rows.append(RbacRegistrationRequest(
                    email='%s@example.invalid' % username,
                    username=username,
                    password_hash='not-used-by-r2-read-test',
                    role='viewer',
                    group_ids='10',
                    job_title='qa',
                    nickname=username,
                    reason='R2-0 pagination hidden',
                    status='pending',
                    pending_username=username,
                    create_time=utc_now_hms(),
                ))
            self.db.session.add_all(rows)
            self.db.session.flush()
            from datas.model.rbac_registration_request_group import RbacRegistrationRequestGroup

            self.db.session.add_all([
                RbacRegistrationRequestGroup(
                    registration_request_id=row.id, group_id=int(row.group_ids),
                ) for row in rows
            ])
            self.db.session.commit()
            repo = RegistrationRequestRepository(self.db.session)
            first = repo.paginate_by_groups(
                PageQuery(page=1, per_page=20),
                [self.group_ids[0]],
                status='pending',
            )
            second = repo.paginate_by_groups(
                PageQuery(page=2, per_page=20),
                [self.group_ids[0]],
                status='pending',
            )

        self.assertEqual(first.total, 21)
        self.assertEqual(first.pages, 2)
        self.assertEqual(len(first.items), 20)
        self.assertEqual(len(second.items), 1)
        self.assertTrue(all(
            'group_10_hidden' not in item.username
            for item in first.items + second.items
        ))

    def test_status_and_username_filters_never_expand_scope(self):
        """RL-11：筛选只能缩小数据库当前授权集合。"""
        allowed = 'r2_filter_allowed'
        leaked = 'r2_filter_group_10_hidden'
        self._create_review_request(allowed, str(self.group_ids[0]))
        self._create_review_request(leaked, '10')

        response, html = self._get_review(
            'single', '?status=pending&username=r2_filter',
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(allowed, html)
        self.assertNotIn(leaked, html)
        self.assertIn('1 total', html)

    def test_current_global_admin_retains_full_visibility(self):
        """RL-12：数据库当前 global admin 的合法全量读取不能回退。"""
        first = 'r2_global_group_1_visible'
        second = 'r2_global_all_visible'
        self._create_review_request(first, str(self.group_ids[0]))
        self._create_review_request(second, '__ALL__', role='admin')

        response, html = self._get_review('global')

        self.assertEqual(response.status_code, 200)
        self.assertIn(first, html)
        self.assertIn(second, html)
        self.assertIn('2 total', html)
        self.assertIn('注册审批 <span class="pg-badge-count">2</span>', html)

    def test_http_filters_pagination_and_badges_share_scoped_set(self):
        """R2-3：筛选、第二页、页面与导航 badge 均不扩展授权集合。"""
        for index in range(21):
            self._create_review_request(
                'r2_r3_pending_allowed_%02d' % index,
                str(self.group_ids[0]),
                status='pending',
            )
        self._create_review_request(
            'r2_r3_approved_allowed',
            str(self.group_ids[0]),
            status='approved',
        )
        self._create_review_request(
            'r2_r3_pending_group_10_hidden',
            '10',
            status='pending',
        )

        response, html = self._get_review(
            'single',
            '?status=pending&username=r2_r3_pending&page=2&per_page=20',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('r2_r3_pending_allowed_00', html)
        self.assertNotIn('r2_r3_pending_allowed_20', html)
        self.assertNotIn('r2_r3_pending_group_10_hidden', html)
        self.assertIn('21 total', html)
        self.assertIn('<span class="cp-nav-badge">21</span>', html)
        self.assertIn('注册审批 <span class="pg-badge-count">21</span>', html)

        response, html = self._get_review(
            'single', '?status=approved&username=r2_r3_approved',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('r2_r3_approved_allowed', html)
        self.assertIn('1 total', html)
        self.assertIn('<span class="cp-nav-badge">21</span>', html)

        response, html = self._get_review(
            'single', '?status=pending&username=group_10_hidden',
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('r2_r3_pending_group_10_hidden', html)
        self.assertIn('0 total', html)
        self.assertIn('<span class="cp-nav-badge">21</span>', html)


class TestRegistrationApprovalScopeClosure(_GlobalScopeAssignmentFixture):
    """S4 单条/批量审批必须与新增/编辑使用同一数据库授权事实。"""

    def _create_request(self, username, role, group_ids, with_relations=True):
        from datas.model.rbac_registration_request import RbacRegistrationRequest
        from datas.model.rbac_registration_request_group import (
            RbacRegistrationRequestGroup,
        )

        with self.app.app_context():
            req = RbacRegistrationRequest(
                email='%s@example.invalid' % username,
                username=username,
                password_hash='not-used-by-scope-test',
                role=role,
                group_ids=group_ids,
                job_title='qa',
                nickname=username,
                reason='S4 scope closure',
                status='pending',
                pending_username=username,
                create_time=utc_now_hms(),
            )
            self.db.session.add(req)
            self.db.session.flush()
            if with_relations and group_ids != '__ALL__':
                for group_id in {int(value) for value in group_ids.split(',')}:
                    self.db.session.add(RbacRegistrationRequestGroup(
                        registration_request_id=req.id,
                        group_id=group_id,
                    ))
            self.db.session.commit()
            return req.id

    def _request_state(self, request_id, username):
        from datas.model.rbac_registration_request import RbacRegistrationRequest
        from datas.model.rbac_user import RbacUser
        from datas.model.user_group import UserGroup

        with self.app.app_context():
            req = self.db.session.get(RbacRegistrationRequest, request_id)
            user = self.db.session.query(RbacUser).filter_by(
                username=username,
            ).first()
            groups = [] if not user else sorted(
                row.group_id
                for row in self.db.session.query(UserGroup).filter_by(
                    user_id=user.id,
                )
            )
            return req.status, user.role if user else None, groups

    def _post_single(self, actor_key, request_id):
        with self.app.test_client() as client:
            self._login(client, actor_key)
            return client.post(
                '/rbac/registration_review/approve',
                data={'id': str(request_id)},
                headers=self._ajax_headers(),
            )

    def _post_batch(self, actor_key, request_ids):
        with self.app.test_client() as client:
            self._login(client, actor_key)
            return client.post(
                '/rbac/registration_review/batch_approve',
                data={'ids': ','.join(str(value) for value in request_ids)},
                headers=self._ajax_headers(),
            )

    def _post_batch_reject(self, actor_key, request_ids, comment='B0 feedback test'):
        with self.app.test_client() as client:
            self._login(client, actor_key)
            return client.post(
                '/rbac/registration_review/batch_reject',
                data={
                    'ids': ','.join(str(value) for value in request_ids),
                    'comment': comment,
                },
                headers=self._ajax_headers(),
            )

    def _post_single_reject(self, actor_key, request_id, comment='single scope test'):
        with self.app.test_client() as client:
            self._login(client, actor_key)
            return client.post(
                '/rbac/registration_review/reject',
                data={'id': str(request_id), 'comment': comment},
                headers=self._ajax_headers(),
            )

    def _set_request_status(self, request_id, status):
        from datas.model.rbac_registration_request import RbacRegistrationRequest

        with self.app.app_context():
            req = self.db.session.get(RbacRegistrationRequest, request_id)
            req.status = status
            req.pending_username = None
            self.db.session.commit()

    def _assert_batch_summary(
        self, payload, *, errcode, outcome, success_count, failure_count,
        failure_ids, expects_url,
    ):
        """B0 target contract: response truth must match per-item DB truth."""
        self.assertEqual(payload['errcode'], errcode)
        if expects_url:
            self.assertEqual(payload['url'], '/rbac/registration_review')
        else:
            self.assertIsNone(payload['url'])
        self.assertIn(
            'data', payload,
            '批量结果必须返回结构化 data 摘要，不能只返回人类可读 errmsg',
        )
        summary = payload.get('data')
        if summary is None:
            return
        self.assertEqual(summary['outcome'], outcome)
        self.assertEqual(summary['success_count'], success_count)
        self.assertEqual(summary['failure_count'], failure_count)
        self.assertEqual(summary['total'], success_count + failure_count)
        self.assertEqual(summary['failure_count'], len(summary['failures']))
        self.assertEqual(
            [failure['id'] for failure in summary['failures']], failure_ids,
        )
        self.assertEqual(payload['result'], summary)

    def test_batch_internal_error_exposes_trace_id_not_raw_exception(self):
        """B1: 系统异常仅暴露通用文案和可查日志关联号。"""
        username = 'b1_internal_error'
        request_id = self._create_request(
            username, 'viewer', str(self.group_ids[0]),
        )
        raw_error = 'database password leaked by driver'
        with mock.patch(
            'app.rbac.views.approve_registration',
            side_effect=RuntimeError(raw_error),
        ), self.assertLogs('tests.test_registration', level='ERROR') as logs:
            response = self._post_batch('global', [request_id])
        payload = response.get_json()
        failure = payload['data']['failures'][0]
        self.assertEqual(payload['errcode'], 1)
        self.assertEqual(failure['msg'], '服务器内部错误，请稍后重试')
        self.assertRegex(failure['trace_id'], r'^[0-9a-f]{32}$')
        self.assertNotIn(raw_error, response.get_data(as_text=True))
        self.assertTrue(any(failure['trace_id'] in line for line in logs.output))

    def test_single_scoped_admin_cannot_approve_global_request(self):
        username = 's4_single_global_denied'
        request_id = self._create_request(username, 'admin', '__ALL__')
        response = self._post_single('multi', request_id)
        self.assertEqual(response.get_json()['errcode'], 1)
        self.assertEqual(
            self._request_state(request_id, username),
            ('pending', None, []),
        )

    def test_single_global_admin_can_approve_global_request(self):
        username = 's4_single_global_allowed'
        request_id = self._create_request(username, 'admin', '__ALL__')
        response = self._post_single('global', request_id)
        self.assertEqual(response.get_json()['errcode'], 0)
        self.assertEqual(
            self._request_state(request_id, username),
            ('approved', 'admin', []),
        )

    def test_scoped_admin_cannot_approve_non_admin_outside_scope(self):
        username = 's4_viewer_outside_denied'
        request_id = self._create_request(
            username,
            'viewer',
            str(self.group_ids[2]),
        )
        response = self._post_single('multi', request_id)
        self.assertEqual(response.get_json()['errcode'], 1)
        self.assertEqual(
            self._request_state(request_id, username),
            ('pending', None, []),
        )

    def test_database_downgrade_overrides_stale_global_session(self):
        from datas.model.user_group import UserGroup

        username = 's4_stale_global_denied'
        request_id = self._create_request(username, 'admin', '__ALL__')
        with self.app.app_context():
            self.db.session.add(UserGroup(
                user_id=self.actor_ids['global'],
                group_id=self.group_ids[0],
            ))
            self.db.session.commit()
        response = self._post_single('global', request_id)
        self.assertEqual(response.get_json()['errcode'], 1)
        self.assertEqual(
            self._request_state(request_id, username),
            ('pending', None, []),
        )

    def test_batch_approve_partial_failure_has_truthful_contract(self):
        """B0 red line: partial completion must not use a success redirect."""
        allowed_name = 's4_batch_subset_allowed'
        denied_name = 's4_batch_global_denied'
        allowed_id = self._create_request(
            allowed_name,
            'admin',
            str(self.group_ids[0]),
        )
        denied_id = self._create_request(denied_name, 'admin', '__ALL__')
        response = self._post_batch('multi', [allowed_id, denied_id])
        payload = response.get_json()
        self._assert_batch_summary(
            payload,
            errcode=1,
            outcome='partial_failure',
            success_count=1,
            failure_count=1,
            failure_ids=[denied_id],
            expects_url=False,
        )
        self.assertEqual(
            self._request_state(allowed_id, allowed_name),
            ('approved', 'admin', [self.group_ids[0]]),
        )
        self.assertEqual(
            self._request_state(denied_id, denied_name),
            ('pending', None, []),
        )

    def test_batch_approve_all_success_has_truthful_contract(self):
        """B0 green behavior target: all completed items may redirect."""
        global_name = 's4_batch_global_allowed'
        viewer_name = 's4_batch_viewer_allowed'
        global_id = self._create_request(global_name, 'admin', '__ALL__')
        viewer_id = self._create_request(
            viewer_name,
            'viewer',
            str(self.group_ids[2]),
        )
        response = self._post_batch('global', [global_id, viewer_id])
        payload = response.get_json()
        self._assert_batch_summary(
            payload,
            errcode=0,
            outcome='all_success',
            success_count=2,
            failure_count=0,
            failure_ids=[],
            expects_url=True,
        )
        self.assertEqual(
            self._request_state(global_id, global_name),
            ('approved', 'admin', []),
        )
        self.assertEqual(
            self._request_state(viewer_id, viewer_name),
            ('approved', 'viewer', [self.group_ids[2]]),
        )

    def test_batch_approve_all_failure_has_truthful_contract(self):
        """B0 red line: no successful item must be a visible failure."""
        denied_name = 's4_batch_all_denied'
        denied_id = self._create_request(denied_name, 'admin', '__ALL__')
        response = self._post_batch('multi', [denied_id])
        payload = response.get_json()
        self._assert_batch_summary(
            payload,
            errcode=1,
            outcome='all_failure',
            success_count=0,
            failure_count=1,
            failure_ids=[denied_id],
            expects_url=False,
        )
        self.assertEqual(
            self._request_state(denied_id, denied_name),
            ('pending', None, []),
        )

    def test_batch_approve_duplicate_ids_are_rejected_before_any_write(self):
        """重复 ID 不得先成功一次、再被误报为部分失败。"""
        username = 's4_batch_duplicate_approve'
        request_id = self._create_request(
            username, 'viewer', str(self.group_ids[0]),
        )
        response = self._post_batch('global', [request_id, request_id])
        payload = response.get_json()
        self.assertEqual(payload['errcode'], 1)
        self.assertIn('不可重复', payload['errmsg'])
        self.assertIsNone(payload.get('data'))
        self.assertEqual(
            self._request_state(request_id, username),
            ('pending', None, []),
        )

    def test_batch_approve_invalid_token_is_rejected_before_any_write(self):
        """混入非法 token 时不得静默忽略并处理剩余 ID。"""
        username = 's4_batch_invalid_approve'
        request_id = self._create_request(
            username, 'viewer', str(self.group_ids[0]),
        )
        with self.app.test_client() as client:
            self._login(client, 'global')
            response = client.post(
                '/rbac/registration_review/batch_approve',
                data={'ids': '%s,not-an-id' % request_id},
                headers=self._ajax_headers(),
            )
        payload = response.get_json()
        self.assertEqual(payload['errcode'], 1)
        self.assertIn('参数无效', payload['errmsg'])
        self.assertEqual(
            self._request_state(request_id, username),
            ('pending', None, []),
        )

    def test_batch_reject_partial_failure_has_truthful_contract(self):
        """B0 red line: reject uses the same partial-result contract."""
        allowed_name = 's4_batch_reject_allowed'
        denied_name = 's4_batch_reject_processed'
        allowed_id = self._create_request(
            allowed_name, 'viewer', str(self.group_ids[0]),
        )
        denied_id = self._create_request(
            denied_name, 'viewer', str(self.group_ids[0]),
        )
        self._set_request_status(denied_id, 'approved')
        response = self._post_batch_reject('global', [allowed_id, denied_id])
        payload = response.get_json()
        self._assert_batch_summary(
            payload,
            errcode=1,
            outcome='partial_failure',
            success_count=1,
            failure_count=1,
            failure_ids=[denied_id],
            expects_url=False,
        )
        self.assertEqual(
            self._request_state(allowed_id, allowed_name),
            ('rejected', None, []),
        )
        self.assertEqual(
            self._request_state(denied_id, denied_name),
            ('approved', None, []),
        )

    def test_batch_reject_all_failure_has_truthful_contract(self):
        """B0 red line: processed rows do not become a fake success."""
        first_name = 's4_batch_reject_all_processed_a'
        second_name = 's4_batch_reject_all_processed_b'
        first_id = self._create_request(
            first_name, 'viewer', str(self.group_ids[0]),
        )
        second_id = self._create_request(
            second_name, 'viewer', str(self.group_ids[0]),
        )
        self._set_request_status(first_id, 'approved')
        self._set_request_status(second_id, 'rejected')
        response = self._post_batch_reject('global', [first_id, second_id])
        payload = response.get_json()
        self._assert_batch_summary(
            payload,
            errcode=1,
            outcome='all_failure',
            success_count=0,
            failure_count=2,
            failure_ids=[first_id, second_id],
            expects_url=False,
        )
        self.assertEqual(
            self._request_state(first_id, first_name),
            ('approved', None, []),
        )
        self.assertEqual(
            self._request_state(second_id, second_name),
            ('rejected', None, []),
        )

    def test_batch_reject_all_success_has_truthful_contract(self):
        """B0 green behavior target: fully rejected batch may redirect."""
        first_name = 's4_batch_reject_all_allowed_a'
        second_name = 's4_batch_reject_all_allowed_b'
        first_id = self._create_request(
            first_name, 'viewer', str(self.group_ids[0]),
        )
        second_id = self._create_request(
            second_name, 'viewer', str(self.group_ids[1]),
        )
        response = self._post_batch_reject('global', [first_id, second_id])
        payload = response.get_json()
        self._assert_batch_summary(
            payload,
            errcode=0,
            outcome='all_success',
            success_count=2,
            failure_count=0,
            failure_ids=[],
            expects_url=True,
        )
        self.assertEqual(
            self._request_state(first_id, first_name),
            ('rejected', None, []),
        )
        self.assertEqual(
            self._request_state(second_id, second_name),
            ('rejected', None, []),
        )

    def test_batch_reject_duplicate_ids_are_rejected_before_any_write(self):
        """拒绝入口必须复用重复 ID 零写入规则。"""
        username = 's4_batch_duplicate_reject'
        request_id = self._create_request(
            username, 'viewer', str(self.group_ids[0]),
        )
        response = self._post_batch_reject(
            'global', [request_id, request_id],
        )
        payload = response.get_json()
        self.assertEqual(payload['errcode'], 1)
        self.assertIn('不可重复', payload['errmsg'])
        self.assertEqual(
            self._request_state(request_id, username),
            ('pending', None, []),
        )

    def test_single_scoped_admin_cannot_reject_outside_scope(self):
        """B0: 拒绝必须和审批一样在服务边界校验目标 Scope。"""
        username = 's4_reject_outside_scope'
        request_id = self._create_request(
            username, 'viewer', str(self.group_ids[2]),
        )

        response = self._post_single_reject('multi', request_id)

        self.assertEqual(response.get_json()['errcode'], 1)
        self.assertEqual(
            self._request_state(request_id, username),
            ('pending', None, []),
        )

    def test_single_scoped_admin_cannot_reject_global_request(self):
        """B0: __ALL__ 申请只能由 seed/global admin 拒绝。"""
        username = 's4_reject_global_scope'
        request_id = self._create_request(username, 'admin', '__ALL__')

        response = self._post_single_reject('multi', request_id)

        self.assertEqual(response.get_json()['errcode'], 1)
        self.assertEqual(
            self._request_state(request_id, username),
            ('pending', None, []),
        )

    def test_scoped_admin_can_reject_intersecting_viewer_request(self):
        """B0 green: viewer/operator 申请与 actor 组相交即可拒绝。"""
        username = 's4_reject_viewer_intersection'
        request_id = self._create_request(
            username,
            'viewer',
            '%s,%s' % (self.group_ids[1], self.group_ids[2]),
        )

        response = self._post_single_reject('multi', request_id)

        self.assertEqual(response.get_json()['errcode'], 0)
        self.assertEqual(
            self._request_state(request_id, username),
            ('rejected', None, []),
        )

    def test_scoped_admin_cannot_reject_admin_partial_subset(self):
        """B0: admin 申请须完整落在 actor 当前组集合中。"""
        username = 's4_reject_admin_partial_subset'
        request_id = self._create_request(
            username,
            'admin',
            '%s,%s' % (self.group_ids[1], self.group_ids[2]),
        )

        response = self._post_single_reject('multi', request_id)

        self.assertEqual(response.get_json()['errcode'], 1)
        self.assertEqual(
            self._request_state(request_id, username),
            ('pending', None, []),
        )

    def test_scoped_admin_cannot_reject_storage_mismatch_request(self):
        """B0: 关联表异常时 scoped admin 必须拒绝，而不是猜测 Scope。"""
        username = 's4_reject_storage_mismatch_denied'
        request_id = self._create_request(
            username,
            'viewer',
            str(self.group_ids[0]),
            with_relations=False,
        )

        response = self._post_single_reject('multi', request_id)

        self.assertEqual(response.get_json()['errcode'], 1)
        self.assertEqual(
            self._request_state(request_id, username),
            ('pending', None, []),
        )

    def test_global_admin_can_reject_storage_mismatch_request(self):
        """B0: 全局管理员可关闭异常遗留申请，避免其永久卡在待审批队列。"""
        username = 's4_reject_storage_mismatch_global'
        request_id = self._create_request(
            username,
            'viewer',
            str(self.group_ids[0]),
            with_relations=False,
        )

        response = self._post_single_reject('global', request_id)

        self.assertEqual(response.get_json()['errcode'], 0)
        self.assertEqual(
            self._request_state(request_id, username),
            ('rejected', None, []),
        )

    def test_reject_database_downgrade_overrides_stale_global_session(self):
        """B0: 拒绝授权读取数据库当前 Scope，不能信任陈旧 Session。"""
        from datas.model.user_group import UserGroup

        username = 's4_reject_stale_global_denied'
        request_id = self._create_request(username, 'admin', '__ALL__')
        with self.app.app_context():
            self.db.session.add(UserGroup(
                user_id=self.actor_ids['global'],
                group_id=self.group_ids[0],
            ))
            self.db.session.commit()

        response = self._post_single_reject('global', request_id)

        self.assertEqual(response.get_json()['errcode'], 1)
        self.assertEqual(
            self._request_state(request_id, username),
            ('pending', None, []),
        )

    def test_batch_scoped_admin_rejects_only_authorized_items(self):
        """B0: 混合批量不得把范围外申请伪装为成功或实际写入。"""
        allowed_name = 's4_reject_batch_allowed'
        denied_name = 's4_reject_batch_denied'
        allowed_id = self._create_request(
            allowed_name, 'viewer', str(self.group_ids[0]),
        )
        denied_id = self._create_request(
            denied_name, 'viewer', str(self.group_ids[2]),
        )

        payload = self._post_batch_reject(
            'multi', [allowed_id, denied_id], comment='mixed scope check',
        ).get_json()

        self._assert_batch_summary(
            payload,
            errcode=1,
            outcome='partial_failure',
            success_count=1,
            failure_count=1,
            failure_ids=[denied_id],
            expects_url=False,
        )
        self.assertEqual(
            self._request_state(allowed_id, allowed_name),
            ('rejected', None, []),
        )
        self.assertEqual(
            self._request_state(denied_id, denied_name),
            ('pending', None, []),
        )

    def test_single_approve_refuses_missing_relation_without_side_effect(self):
        from datas.model.rbac_registration_request_group import (
            RbacRegistrationRequestGroup,
        )

        username = 'e1_missing_relation'
        request_id = self._create_request(
            username, 'viewer', str(self.group_ids[0]),
        )
        with self.app.app_context():
            link = self.db.session.query(
                RbacRegistrationRequestGroup
            ).filter_by(registration_request_id=request_id).one()
            self.db.session.delete(link)
            self.db.session.commit()

        response = self._post_single('global', request_id)

        self.assertEqual(response.get_json()['errcode'], 1)
        self.assertIn('数据不一致', response.get_json()['errmsg'])
        self.assertEqual(
            self._request_state(request_id, username),
            ('pending', None, []),
        )

    def test_single_approve_refuses_extra_relation_on_global_request(self):
        from datas.model.rbac_registration_request_group import (
            RbacRegistrationRequestGroup,
        )

        username = 'e1_global_extra_relation'
        request_id = self._create_request(username, 'admin', '__ALL__')
        with self.app.app_context():
            self.db.session.add(RbacRegistrationRequestGroup(
                registration_request_id=request_id,
                group_id=self.group_ids[0],
            ))
            self.db.session.commit()

        response = self._post_single('global', request_id)

        self.assertEqual(response.get_json()['errcode'], 1)
        self.assertIn('数据不一致', response.get_json()['errmsg'])
        self.assertEqual(
            self._request_state(request_id, username),
            ('pending', None, []),
        )

    def test_single_approve_refuses_invalid_csv_and_deleted_group(self):
        from datas.model.resource_group import ResourceGroup

        cases = (
            ('e1_invalid_csv', '1,abc', False),
            ('e1_deleted_group', str(self.group_ids[2]), True),
        )
        for username, raw_groups, with_relations in cases:
            with self.subTest(username=username):
                request_id = self._create_request(
                    username,
                    'viewer',
                    raw_groups,
                    with_relations=with_relations,
                )
                if username == 'e1_deleted_group':
                    with self.app.app_context():
                        group = self.db.session.get(
                            ResourceGroup, self.group_ids[2],
                        )
                        self.db.session.delete(group)
                        self.db.session.commit()

                response = self._post_single('global', request_id)

                self.assertEqual(response.get_json()['errcode'], 1)
                self.assertIn('数据异常', response.get_json()['errmsg'])
                self.assertEqual(
                    self._request_state(request_id, username),
                    ('pending', None, []),
                )

    def test_batch_storage_mismatch_is_truthful_partial_failure(self):
        from datas.model.rbac_registration_request_group import (
            RbacRegistrationRequestGroup,
        )

        allowed_name = 'e1_batch_consistent'
        denied_name = 'e1_batch_mismatch'
        allowed_id = self._create_request(
            allowed_name, 'viewer', str(self.group_ids[0]),
        )
        denied_id = self._create_request(
            denied_name, 'viewer', str(self.group_ids[0]),
        )
        with self.app.app_context():
            link = self.db.session.query(
                RbacRegistrationRequestGroup
            ).filter_by(registration_request_id=denied_id).one()
            self.db.session.delete(link)
            self.db.session.commit()

        payload = self._post_batch(
            'global', [allowed_id, denied_id],
        ).get_json()

        self._assert_batch_summary(
            payload,
            errcode=1,
            outcome='partial_failure',
            success_count=1,
            failure_count=1,
            failure_ids=[denied_id],
            expects_url=False,
        )
        self.assertEqual(
            self._request_state(allowed_id, allowed_name),
            ('approved', 'viewer', [self.group_ids[0]]),
        )
        self.assertEqual(
            self._request_state(denied_id, denied_name),
            ('pending', None, []),
        )

    def test_batch_consistency_query_error_returns_trace_id(self):
        username = 'e1_consistency_query_error'
        request_id = self._create_request(
            username, 'viewer', str(self.group_ids[0]),
        )
        raw_error = 'relation database credential must stay in logs'
        with mock.patch(
            'app.rbac.services._validate_registration_storage_consistency',
            side_effect=RuntimeError(raw_error),
        ), self.assertLogs('app.rbac.services', level='ERROR') as logs:
            response = self._post_batch('global', [request_id])

        payload = response.get_json()
        failure = payload['data']['failures'][0]
        self.assertEqual(failure['msg'], '服务器内部错误，请稍后重试')
        self.assertRegex(failure['trace_id'], r'^[0-9a-f]{32}$')
        self.assertNotIn(raw_error, response.get_data(as_text=True))
        self.assertTrue(any(failure['trace_id'] in line for line in logs.output))
        self.assertEqual(
            self._request_state(request_id, username),
            ('pending', None, []),
        )
