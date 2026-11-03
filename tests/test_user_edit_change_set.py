# -*- coding: utf-8 -*-
"""RBAC 用户编辑 U1：签名快照、规范化与写前意图契约。"""
import re
import unittest
from unittest import mock

from sqlalchemy import func, select

from datas.utils.times import utc_now_hms
from tests.test_registration import _make_app


class TestUserEditChangeSet(unittest.TestCase):
    def setUp(self):
        self.app, self.db = _make_app()
        with self.app.app_context():
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            from datas.model.rbac_registration_request import RbacRegistrationRequest  # noqa: F401
            from datas.model.rbac_user import RbacUser
            from datas.model.resource_group import ResourceGroup
            from datas.model.user_group import UserGroup

            self.db.create_all()
            group = ResourceGroup(name='U1-A', create_time=utc_now_hms())
            actor = RbacUser(
                username='u1_global_admin',
                role='admin',
                is_active=1,
                auth_version=0,
                create_time=utc_now_hms(),
            )
            actor.set_password('test-password')
            target = RbacUser(
                username='u1_target',
                role='viewer',
                is_active=1,
                auth_version=0,
                email='old@example.invalid',
                nickname='old',
                job_title='qa',
                create_time=utc_now_hms(),
            )
            target.set_password('test-password')
            self.db.session.add_all([group, actor, target])
            self.db.session.flush()
            self.db.session.add(UserGroup(user_id=target.id, group_id=group.id))
            self.db.session.commit()
            self.group_id = group.id
            self.actor_id = actor.id
            self.target_id = target.id

    def tearDown(self):
        with self.app.app_context():
            self.db.session.remove()
            self.db.drop_all()

    @staticmethod
    def _ajax_headers():
        return {
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
        }

    def _login(self, client):
        with client.session_transaction() as session:
            session.update({
                'is_login': True,
                'user_id': self.actor_id,
                'username': 'u1_global_admin',
                'role': 'admin',
                'auth_version': 0,
                'group_ids': [],
            })

    def _edit_token(self, client, target_id=None):
        target_id = target_id or self.target_id
        response = client.get('/rbac/users/edit?id=%s' % target_id)
        self.assertEqual(response.status_code, 200)
        match = re.search(
            r'name="edit_snapshot_token"\s+value="([^"]+)"',
            response.get_data(as_text=True),
        )
        self.assertIsNotNone(match)
        return match.group(1)

    def _same_values(self, token):
        return {
            'id': str(self.target_id),
            'edit_snapshot_token': token,
            'role': 'viewer',
            'group_ids': str(self.group_id),
            'email': 'old@example.invalid',
            'nickname': 'old',
            'job_title': 'qa',
        }

    def _service_values(self, **changes):
        from app.rbac.services import (
            build_user_edit_snapshot,
            get_user_group_ids_for_user,
        )
        from datas.model.rbac_user import RbacUser

        target = self.db.session.get(RbacUser, self.target_id)
        original = build_user_edit_snapshot(
            self.actor_id,
            target,
            get_user_group_ids_for_user(target.id),
        )
        requested = {field: original[field] for field in (
            'email', 'nickname', 'job_title', 'role', 'group_ids'
        )}
        requested.update(changes)
        return original, requested

    def test_snapshot_roundtrip_exact_schema_and_tamper_rejection(self):
        from app.rbac.services import (
            USER_EDIT_SNAPSHOT_KEYS,
            build_user_edit_snapshot,
            sign_user_edit_snapshot,
            verify_user_edit_snapshot,
        )
        from datas.model.rbac_user import RbacUser

        with self.app.app_context():
            target = self.db.session.get(RbacUser, self.target_id)
            snapshot = build_user_edit_snapshot(
                self.actor_id, target, [self.group_id, self.group_id]
            )
            self.assertEqual(set(snapshot), USER_EDIT_SNAPSHOT_KEYS)
            self.assertEqual(snapshot['group_ids'], [self.group_id])
            serialized = sign_user_edit_snapshot(self.app.secret_key, snapshot)
            verified = verify_user_edit_snapshot(
                self.app.secret_key, serialized, self.actor_id, self.target_id
            )
            self.assertTrue(verified['ok'])
            self.assertEqual(verified['snapshot'], snapshot)
            payload, signature = serialized.rsplit('.', 1)
            tampered = payload + '.' + ('A' if signature[0] != 'A' else 'B') + signature[1:]
            self.assertFalse(verify_user_edit_snapshot(
                self.app.secret_key, tampered, self.actor_id, self.target_id
            )['ok'])
            self.assertFalse(verify_user_edit_snapshot(
                self.app.secret_key, serialized, self.actor_id + 1, self.target_id
            )['ok'])
            serialized_text = str(snapshot).lower()
            for forbidden in ('password', 'api_token', 'session', 'csrf'):
                self.assertNotIn(forbidden, serialized_text)

    def test_normalization_and_intent_are_pure_and_order_insensitive(self):
        from app.rbac.services import (
            build_user_edit_intent,
            normalize_user_edit_values,
        )

        normalized = normalize_user_edit_values(
            'viewer',
            [self.group_id, self.group_id],
            email_present=True,
            email=' old@example.invalid ',
            nickname=' old ',
            job_title='qa',
        )
        self.assertTrue(normalized['ok'])
        self.assertEqual(normalized['values']['group_ids'], [self.group_id])
        snapshot = dict(
            normalized['values'],
            schema_version=2,
            editor_scope={'bypass': True, 'group_ids': []},
            actor_user_id=self.actor_id,
            target_user_id=self.target_id,
        )
        self.assertEqual(build_user_edit_intent(snapshot, normalized['values']), {})
        missing_email = normalize_user_edit_values(
            'viewer', [self.group_id], email_present=False, email=None,
            nickname='old', job_title='qa',
        )
        self.assertFalse(missing_email['ok'])
        too_long_other = normalize_user_edit_values(
            'viewer', [self.group_id], email_present=True, email='a@b.invalid',
            nickname='old', job_title='other', job_title_other='x' * 21,
        )
        self.assertFalse(too_long_other['ok'])

    def test_clear_email_confirmation_contract(self):
        from app.rbac.services import validate_user_edit_confirmation

        snapshot = {'email': 'old@example.invalid'}
        requested = {'email': None}
        first = validate_user_edit_confirmation(snapshot, requested, '', '')
        self.assertFalse(first['ok'])
        self.assertEqual(first['outcome'], 'confirm_required')
        empty_reason = validate_user_edit_confirmation(snapshot, requested, '1', '  ')
        self.assertFalse(empty_reason['ok'])
        accepted = validate_user_edit_confirmation(
            snapshot, requested, '1', '  账号不再使用邮箱  '
        )
        self.assertTrue(accepted['ok'])
        self.assertEqual(accepted['reason'], '账号不再使用邮箱')

    def test_route_no_change_does_not_enter_write_service(self):
        with self.app.test_client() as client:
            self._login(client)
            token = self._edit_token(client)
            with mock.patch('app.rbac.views.update_user_management') as update:
                response = client.post(
                    '/rbac/users/edit',
                    data=self._same_values(token),
                    headers=self._ajax_headers(),
                )
        payload = response.get_json()
        self.assertEqual(payload['errcode'], 0)
        self.assertEqual(payload['data']['outcome'], 'no_change')
        self.assertFalse(payload.get('url'))
        update.assert_not_called()

    def test_route_rejects_missing_snapshot_before_write(self):
        with self.app.test_client() as client:
            self._login(client)
            data = self._same_values('')
            with mock.patch('app.rbac.views.update_user_management') as update:
                response = client.post(
                    '/rbac/users/edit', data=data, headers=self._ajax_headers()
                )
        self.assertEqual(response.get_json()['errcode'], 1)
        self.assertIn('刷新', response.get_json()['errmsg'])
        update.assert_not_called()

    def test_route_requires_confirmation_before_clear_email(self):
        with self.app.test_client() as client:
            self._login(client)
            token = self._edit_token(client)
            data = self._same_values(token)
            data['email'] = ''
            with mock.patch('app.rbac.views.update_user_management') as update:
                response = client.post(
                    '/rbac/users/edit', data=data, headers=self._ajax_headers()
                )
        payload = response.get_json()
        self.assertEqual(payload['errcode'], 1)
        self.assertEqual(payload['data']['outcome'], 'confirm_required')
        self.assertTrue(payload['data']['confirm_clear_email'])
        update.assert_not_called()

    def test_native_clear_email_fallback_preserves_form_and_unique_names(self):
        with self.app.test_client() as client:
            self._login(client)
            token = self._edit_token(client)
            data = self._same_values(token)
            data.update({'email': '', 'nickname': '保留的输入'})
            response = client.post('/rbac/users/edit', data=data)
        html = response.get_data(as_text=True)
        form_match = re.search(
            r'<form[^>]*js-user-edit-form[^>]*>.*?</form>', html, re.S
        )
        self.assertIsNotNone(form_match)
        form_html = form_match.group(0)
        self.assertEqual(response.status_code, 200)
        self.assertIn('确认清空邮箱', html)
        self.assertIn('value="保留的输入"', html)
        self.assertIn('name="email" id="uf-email"', form_html)
        self.assertIn('id="uf-email" class="f-input uf-input" maxlength="128" value=""', form_html)
        self.assertEqual(len(re.findall(r'name="confirm_clear_email"', form_html)), 1)
        self.assertEqual(len(re.findall(r'name="email_clear_reason"', form_html)), 1)

        data.update({'confirm_clear_email': '1', 'email_clear_reason': '  '})
        with self.app.test_client() as client:
            self._login(client)
            response = client.post('/rbac/users/edit', data=data)
        retry_html = response.get_data(as_text=True)
        self.assertIn('请填写清空邮箱的变更理由', retry_html)
        self.assertIn('name="email_clear_reason"', retry_html)

    def test_u3_template_has_noop_preflight_and_input_modal_contract(self):
        with self.app.test_client() as client:
            self._login(client)
            response = client.get('/rbac/users/edit?id=%s' % self.target_id)
        html = response.get_data(as_text=True)
        form_match = re.search(
            r'<form[^>]*js-user-edit-form[^>]*>.*?</form>', html, re.S
        )
        self.assertIsNotNone(form_match)
        form_html = form_match.group(0)
        self.assertIn('cp:form-before-ajax-submit', html)
        self.assertIn('未检测到变更，无需保存', html)
        self.assertIn("title: '确认清空邮箱'", html)
        self.assertIn('清空理由', html)
        self.assertNotIn('name="email_clear_reason"', form_html)

    def test_native_outcome_prg_renders_stable_notice(self):
        with self.app.test_client() as client:
            self._login(client)
            for outcome, message in (
                ('no_change', '未检测到变更，无需保存'),
                ('already_applied', '目标状态已存在，无需重复保存'),
                ('conflict', '未覆盖新数据'),
                ('commit_unknown', '保存结果无法确认'),
            ):
                response = client.get(
                    '/rbac/users/edit?id=%s&outcome=%s'
                    % (self.target_id, outcome)
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn(message, response.get_data(as_text=True))

    def test_u3_audit_detail_parser_handles_v1_and_safe_fallbacks(self):
        import json

        from app.rbac.services import format_user_update_audit_detail

        valid = format_user_update_audit_detail(json.dumps({
            'schema_version': 1,
            'changes': {
                'email': {'before': 'old@example.invalid', 'after': None},
                'group_ids': {'before': [1], 'after': []},
            },
            'reason': '邮箱已注销',
        }))
        self.assertEqual(valid['state'], 'ok')
        self.assertEqual(valid['changes'][0]['after'], '—')
        self.assertTrue(valid['changes'][0]['cleared'])
        self.assertEqual(valid['changes'][1]['after'], '全部（全局权限）')
        self.assertEqual(valid['reason'], '邮箱已注销')
        self.assertEqual(
            format_user_update_audit_detail('{broken')['state'], 'invalid'
        )
        self.assertEqual(
            format_user_update_audit_detail(json.dumps({
                'schema_version': 2, 'changes': {'email': {}}
            }))['state'],
            'unsupported',
        )
        invalid = format_user_update_audit_detail(json.dumps({
            'schema_version': 1,
            'changes': {
                'nickname': {'before': '旧', 'after': '新'},
                'future_field': {'before': 'a', 'after': 'b'},
            },
        }))
        self.assertEqual(invalid, {'state': 'invalid', 'changes': [], 'reason': None})

    def test_u3_audit_page_escapes_reason_and_renders_changes(self):
        import json

        from datas.model.rbac_audit_log import RbacAuditLog

        with self.app.app_context():
            self.db.session.add(RbacAuditLog(
                user_id=self.actor_id,
                username='u1_global_admin',
                action='user:update',
                resource='u1_target',
                ip='127.0.0.1',
                status='allow',
                create_time=utc_now_hms(),
                actor_group_ids='',
                detail=json.dumps({
                    'schema_version': 1,
                    'changes': {
                        'email': {
                            'before': 'old@example.invalid',
                            'after': None,
                        },
                    },
                    'reason': '<script>alert(1)</script>',
                }),
            ))
            self.db.session.commit()
        with self.app.test_client() as client:
            self._login(client)
            response = client.get('/rbac/audit-logs')
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('old@example.invalid', html)
        self.assertIn('（已清空）', html)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html)
        self.assertNotIn('<script>alert(1)</script>', html)

    def test_route_conflict_preserves_database_current_value(self):
        from datas.model.rbac_audit_log import RbacAuditLog
        from datas.model.rbac_user import RbacUser

        with self.app.test_client() as client:
            self._login(client)
            token = self._edit_token(client)
            with self.app.app_context():
                target = self.db.session.get(RbacUser, self.target_id)
                target.nickname = 'concurrent'
                self.db.session.commit()
            data = self._same_values(token)
            data['nickname'] = 'requested'
            response = client.post(
                '/rbac/users/edit', data=data, headers=self._ajax_headers()
            )
        payload = response.get_json()
        self.assertEqual(payload['errcode'], 1)
        self.assertEqual(payload['data']['outcome'], 'conflict')
        with self.app.app_context():
            self.assertEqual(
                self.db.session.get(RbacUser, self.target_id).nickname,
                'concurrent',
            )
            self.assertEqual(self.db.session.scalar(select(RbacAuditLog)), None)

    def test_route_ignores_status_field_and_passes_u2_transaction_contract(self):
        with self.app.test_client() as client:
            self._login(client)
            token = self._edit_token(client)
            data = self._same_values(token)
            data.update({'nickname': 'new', 'is_active': '0'})
            with mock.patch(
                'app.rbac.views.update_user_management',
                return_value={'ok': True, 'msg': '保存成功'},
            ) as update:
                response = client.post(
                    '/rbac/users/edit', data=data, headers=self._ajax_headers()
                )
        self.assertEqual(response.get_json()['errcode'], 0)
        self.assertEqual(update.call_args.args[0], self.actor_id)
        self.assertEqual(update.call_args.args[1], self.target_id)
        self.assertEqual(update.call_args.args[3]['nickname'], 'new')
        self.assertNotIn('is_active', update.call_args.args[3])

    def test_disabled_target_get_and_post_go_to_read_only_detail(self):
        from datas.model.rbac_user import RbacUser

        with self.app.app_context():
            target = self.db.session.get(RbacUser, self.target_id)
            target.is_active = 0
            self.db.session.commit()
        with self.app.test_client() as client:
            self._login(client)
            get_response = client.get('/rbac/users/edit?id=%s' % self.target_id)
            post_response = client.post(
                '/rbac/users/edit',
                data={'id': str(self.target_id)},
                headers=self._ajax_headers(),
            )
        self.assertEqual(get_response.status_code, 302)
        self.assertIn('/rbac/users/view?id=%s' % self.target_id, get_response.headers['Location'])
        self.assertEqual(post_response.get_json()['errcode'], 1)
        self.assertIn('/rbac/users/view?id=%s' % self.target_id, post_response.get_json()['url'])

    def test_valid_clear_email_enters_current_write_boundary_explicitly(self):
        with self.app.test_client() as client:
            self._login(client)
            token = self._edit_token(client)
            data = self._same_values(token)
            data.update({
                'email': '',
                'confirm_clear_email': '1',
                'email_clear_reason': '不再使用该邮箱',
            })
            with mock.patch(
                'app.rbac.views.update_user_management',
                return_value={'ok': True, 'msg': '保存成功'},
            ) as update:
                response = client.post(
                    '/rbac/users/edit', data=data, headers=self._ajax_headers()
                )
        self.assertEqual(response.get_json()['errcode'], 0)
        self.assertIsNone(update.call_args.args[3]['email'])
        self.assertEqual(update.call_args.kwargs['reason'], '不再使用该邮箱')

    def test_u2_profile_update_and_audit_share_one_commit(self):
        import json

        from app.rbac.services import build_user_edit_intent, update_user_management
        from datas.model.rbac_audit_log import RbacAuditLog
        from datas.model.rbac_user import RbacUser

        with self.app.test_request_context('/rbac/users/edit', method='POST'):
            original, requested = self._service_values(nickname='new-nickname')
            with mock.patch('app.rbac.services._invalidate_api_scope_cache') as invalidate:
                result = update_user_management(
                    self.actor_id,
                    self.target_id,
                    original,
                    requested,
                    build_user_edit_intent(original, requested),
                )
            self.assertTrue(result['ok'])
            self.assertEqual(result['outcome'], 'updated')
            self.assertFalse(result['auth_version_bumped'])
            invalidate.assert_not_called()
            target = self.db.session.get(RbacUser, self.target_id)
            self.assertEqual(target.nickname, 'new-nickname')
            self.assertEqual(target.auth_version, 0)
            audits = self.db.session.scalars(select(RbacAuditLog)).all()
            self.assertEqual(len(audits), 1)
            detail = json.loads(audits[0].detail)
            self.assertEqual(set(detail), {'schema_version', 'changes'})
            self.assertEqual(set(detail['changes']), {'nickname'})
            self.assertEqual(
                detail['changes']['nickname'],
                {'before': 'old', 'after': 'new-nickname'},
            )
            for forbidden in ('password', 'api_token', 'session', 'csrf'):
                self.assertNotIn(forbidden, audits[0].detail.lower())

    def test_u2_clear_email_persists_null_and_trimmed_reason_in_audit(self):
        import json

        from app.rbac.services import build_user_edit_intent, update_user_management
        from datas.model.rbac_audit_log import RbacAuditLog
        from datas.model.rbac_user import RbacUser

        with self.app.test_request_context('/rbac/users/edit', method='POST'):
            original, requested = self._service_values(email=None)
            result = update_user_management(
                self.actor_id,
                self.target_id,
                original,
                requested,
                build_user_edit_intent(original, requested),
                reason='  邮箱已停用  ',
            )
            self.assertTrue(result['ok'])
            self.assertIsNone(self.db.session.get(RbacUser, self.target_id).email)
            audit = self.db.session.scalar(select(RbacAuditLog))
            detail = json.loads(audit.detail)
            self.assertEqual(detail['reason'], '邮箱已停用')
            self.assertEqual(
                detail['changes']['email'],
                {'before': 'old@example.invalid', 'after': None},
            )

    def test_u2_write_boundary_rejects_clear_email_without_reason(self):
        from app.rbac.services import build_user_edit_intent, update_user_management
        from datas.model.rbac_audit_log import RbacAuditLog
        from datas.model.rbac_user import RbacUser

        with self.app.test_request_context('/rbac/users/edit', method='POST'):
            original, requested = self._service_values(email=None)
            result = update_user_management(
                self.actor_id,
                self.target_id,
                original,
                requested,
                build_user_edit_intent(original, requested),
                reason='  ',
            )
            self.assertFalse(result['ok'])
            self.assertEqual(result['outcome'], 'failed')
            self.assertEqual(
                self.db.session.get(RbacUser, self.target_id).email,
                'old@example.invalid',
            )
            self.assertEqual(self.db.session.scalar(select(RbacAuditLog)), None)

    def test_u2_authorization_change_bumps_once_and_invalidates_after_commit(self):
        from app.rbac.services import build_user_edit_intent, update_user_management
        from datas.model.rbac_user import RbacUser

        with self.app.test_request_context('/rbac/users/edit', method='POST'):
            original, requested = self._service_values(role='operator')
            with mock.patch('app.rbac.services._invalidate_api_scope_cache') as invalidate:
                result = update_user_management(
                    self.actor_id,
                    self.target_id,
                    original,
                    requested,
                    build_user_edit_intent(original, requested),
                )
            self.assertTrue(result['ok'])
            self.assertTrue(result['auth_version_bumped'])
            target = self.db.session.get(RbacUser, self.target_id)
            self.assertEqual(target.role, 'operator')
            self.assertEqual(target.auth_version, 1)
            self.assertTrue(target.api_token)
            invalidate.assert_called_once_with(self.target_id)

    def test_u2_three_way_conflict_never_overwrites_concurrent_value(self):
        from app.rbac.services import build_user_edit_intent, update_user_management
        from datas.model.rbac_audit_log import RbacAuditLog
        from datas.model.rbac_user import RbacUser

        with self.app.test_request_context('/rbac/users/edit', method='POST'):
            original, requested = self._service_values(nickname='requested')
            target = self.db.session.get(RbacUser, self.target_id)
            target.nickname = 'concurrent'
            self.db.session.commit()
            result = update_user_management(
                self.actor_id,
                self.target_id,
                original,
                requested,
                build_user_edit_intent(original, requested),
            )
            self.assertFalse(result['ok'])
            self.assertEqual(result['outcome'], 'conflict')
            self.assertEqual(
                self.db.session.get(RbacUser, self.target_id).nickname,
                'concurrent',
            )
            self.assertEqual(self.db.session.scalar(
                select(RbacAuditLog).where(RbacAuditLog.action == 'user:update')
            ), None)

    def test_u2_already_applied_has_no_success_audit_or_auth_side_effect(self):
        from app.rbac.services import build_user_edit_intent, update_user_management
        from datas.model.rbac_audit_log import RbacAuditLog
        from datas.model.rbac_user import RbacUser

        with self.app.test_request_context('/rbac/users/edit', method='POST'):
            original, requested = self._service_values(nickname='requested')
            target = self.db.session.get(RbacUser, self.target_id)
            target.nickname = 'requested'
            self.db.session.commit()
            result = update_user_management(
                self.actor_id,
                self.target_id,
                original,
                requested,
                build_user_edit_intent(original, requested),
            )
            self.assertTrue(result['ok'])
            self.assertEqual(result['outcome'], 'already_applied')
            target = self.db.session.get(RbacUser, self.target_id)
            self.assertEqual(target.auth_version, 0)
            self.assertEqual(self.db.session.scalar(select(RbacAuditLog)), None)

    def test_u2_write_boundary_rejects_database_current_actor_downgrade(self):
        from app.rbac.services import build_user_edit_intent, update_user_management
        from datas.model.rbac_audit_log import RbacAuditLog
        from datas.model.rbac_user import RbacUser

        with self.app.test_request_context('/rbac/users/edit', method='POST'):
            original, requested = self._service_values(nickname='requested')
            actor = self.db.session.get(RbacUser, self.actor_id)
            actor.role = 'viewer'
            self.db.session.commit()
            result = update_user_management(
                self.actor_id,
                self.target_id,
                original,
                requested,
                build_user_edit_intent(original, requested),
            )
            self.assertFalse(result['ok'])
            self.assertEqual(result['outcome'], 'failed')
            self.assertEqual(self.db.session.get(RbacUser, self.target_id).nickname, 'old')
            self.assertEqual(self.db.session.scalar(select(RbacAuditLog)), None)

    def test_u2_audit_flush_failure_rolls_back_business_change(self):
        from app.rbac.services import build_user_edit_intent, update_user_management
        from datas.model.rbac_audit_log import RbacAuditLog
        from datas.model.rbac_user import RbacUser

        with self.app.test_request_context('/rbac/users/edit', method='POST'):
            original, requested = self._service_values(nickname='requested')
            with mock.patch.object(
                self.db.session,
                'flush',
                side_effect=RuntimeError('audit flush failed'),
            ):
                result = update_user_management(
                    self.actor_id,
                    self.target_id,
                    original,
                    requested,
                    build_user_edit_intent(original, requested),
                )
            self.assertFalse(result['ok'])
            self.assertEqual(result['outcome'], 'failed')
            self.assertEqual(self.db.session.get(RbacUser, self.target_id).nickname, 'old')
            self.assertEqual(self.db.session.scalar(select(RbacAuditLog)), None)

    def test_u2_commit_exception_is_unknown_and_invalidates_attempted_auth_change(self):
        from app.rbac.services import build_user_edit_intent, update_user_management

        with self.app.test_request_context('/rbac/users/edit', method='POST'):
            original, requested = self._service_values(role='operator')
            with mock.patch.object(
                self.db.session,
                'commit',
                side_effect=RuntimeError('connection lost during commit'),
            ), mock.patch(
                'app.rbac.services._invalidate_api_scope_cache'
            ) as invalidate:
                result = update_user_management(
                    self.actor_id,
                    self.target_id,
                    original,
                    requested,
                    build_user_edit_intent(original, requested),
                )
            self.assertFalse(result['ok'])
            self.assertEqual(result['outcome'], 'commit_unknown')
            invalidate.assert_called_once_with(self.target_id)


    def _echoed_token(self, response):
        html = response.get_data(as_text=True)
        match = re.search(r'name="edit_snapshot_token"\s+value="([^"]+)"', html)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_native_confirmation_preserves_t0_and_rejects_concurrent_email(self):
        from datas.model.rbac_audit_log import RbacAuditLog
        from datas.model.rbac_user import RbacUser

        with self.app.test_client() as client:
            self._login(client)
            token = self._edit_token(client)
            data = self._same_values(token)
            data.update(email='', nickname='requested')
            with self.app.app_context():
                target = self.db.session.get(RbacUser, self.target_id)
                target.email = 'concurrent@example.invalid'
                self.db.session.commit()
            response = client.post('/rbac/users/edit', data=data)
            self.assertEqual(self._echoed_token(response), token)
            self.assertIn('old@example.invalid', response.get_data(as_text=True))
            self.assertNotIn('concurrent@example.invalid', response.get_data(as_text=True))
            for reason in ('', 'x' * 501):
                data.update(confirm_clear_email='1', email_clear_reason=reason)
                response = client.post('/rbac/users/edit', data=data)
                self.assertEqual(self._echoed_token(response), token)
            data['email_clear_reason'] = 'account closed'
            response = client.post('/rbac/users/edit', data=data, headers=self._ajax_headers())
            self.assertEqual(response.get_json()['data']['outcome'], 'conflict')
        with self.app.app_context():
            target = self.db.session.get(RbacUser, self.target_id)
            self.assertEqual(target.email, 'concurrent@example.invalid')
            self.assertEqual(target.nickname, 'old')
            self.assertEqual(target.auth_version, 0)
            self.assertEqual(self.db.session.scalar(
                select(func.count()).select_from(RbacAuditLog)
            ), 0)

    def test_native_confirmation_allows_success_without_concurrent_change(self):
        from datas.model.rbac_user import RbacUser

        with self.app.test_client() as client:
            self._login(client)
            data = self._same_values(self._edit_token(client))
            data['email'] = ''
            response = client.post('/rbac/users/edit', data=data)
            data['edit_snapshot_token'] = self._echoed_token(response)
            data.update(confirm_clear_email='1', email_clear_reason='reason')
            response = client.post('/rbac/users/edit', data=data)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.location, '/rbac/users')
        with self.app.app_context():
            self.assertIsNone(self.db.session.get(RbacUser, self.target_id).email)

    def test_recoverable_input_errors_preserve_original_and_requested(self):
        with self.app.test_client() as client:
            self._login(client)
            token = self._edit_token(client)
            for changes in (
                {'email': 'invalid'}, {'nickname': 'x' * 65},
                {'job_title': 'other', 'job_title_other': 'x' * 21},
            ):
                with self.subTest(changes=changes):
                    data = self._same_values(token)
                    data.update(changes)
                    with mock.patch('app.rbac.views.sign_user_edit_snapshot') as sign:
                        response = client.post('/rbac/users/edit', data=data)
                    self.assertEqual(self._echoed_token(response), token)
                    self.assertIn('value="%s"' % next(iter(changes.values())),
                                  response.get_data(as_text=True))
                    sign.assert_not_called()

    def test_failed_write_echoes_original_token_and_requested_values(self):
        with self.app.test_client() as client:
            self._login(client)
            token = self._edit_token(client)
            data = self._same_values(token)
            data['nickname'] = 'requested'
            with mock.patch('app.rbac.views.update_user_management', return_value={
                'ok': False, 'outcome': 'failed', 'msg': '保存失败',
            }):
                response = client.post('/rbac/users/edit', data=data)
            self.assertEqual(self._echoed_token(response), token)
            self.assertIn('value="requested"', response.get_data(as_text=True))

    def test_invalid_snapshot_has_no_actionable_form_or_replacement_token(self):
        from app.rbac.services import sign_user_edit_snapshot, verify_user_edit_snapshot

        with self.app.test_client() as client:
            self._login(client)
            token = self._edit_token(client)
            original = verify_user_edit_snapshot(
                self.app.secret_key, token, self.actor_id, self.target_id,
            )['snapshot']
            tokens = ['', 'tampered']
            for change in ({'schema_version': 99}, {'actor_user_id': 999},
                           {'target_user_id': 999}):
                tokens.append(sign_user_edit_snapshot(self.app.secret_key, dict(original, **change)))
            for invalid in tokens:
                with self.subTest(token=invalid):
                    data = self._same_values(invalid)
                    with mock.patch('app.rbac.views.update_user_management') as update:
                        response = client.post('/rbac/users/edit', data=data)
                    html = response.get_data(as_text=True)
                    self.assertIn('重新加载编辑页', html)
                    self.assertNotIn('name="edit_snapshot_token"', html)
                    self.assertNotIn('class="js-ajax-form js-user-edit-form"', html)
                    self.assertNotIn('var original =', html)
                    update.assert_not_called()

    def test_invalid_scope_does_not_offer_silently_reduced_edit_form(self):
        with self.app.test_client() as client:
            self._login(client)
            data = self._same_values(self._edit_token(client))
            data['group_ids'] = '99999'
            response = client.post('/rbac/users/edit', data=data)
            self.assertIn('重新加载编辑页', response.get_data(as_text=True))
            self.assertNotIn('name="edit_snapshot_token"', response.get_data(as_text=True))

    def test_email_already_cleared_is_noop_after_confirmation(self):
        from datas.model.rbac_user import RbacUser

        with self.app.test_client() as client:
            self._login(client)
            data = self._same_values(self._edit_token(client))
            data.update(email='', confirm_clear_email='1', email_clear_reason='reason')
            with self.app.app_context():
                self.db.session.get(RbacUser, self.target_id).email = None
                self.db.session.commit()
            result = client.post('/rbac/users/edit', data=data, headers=self._ajax_headers())
            self.assertEqual(result.get_json()['data']['outcome'], 'already_applied')

    def test_originally_empty_email_does_not_clear_concurrently_added_email(self):
        from datas.model.rbac_user import RbacUser

        with self.app.app_context():
            self.db.session.get(RbacUser, self.target_id).email = None
            self.db.session.commit()
        with self.app.test_client() as client:
            self._login(client)
            data = self._same_values(self._edit_token(client))
            data.update(email='', nickname='requested')
            with self.app.app_context():
                self.db.session.get(RbacUser, self.target_id).email = 'new@example.invalid'
                self.db.session.commit()
            result = client.post('/rbac/users/edit', data=data, headers=self._ajax_headers())
            self.assertEqual(result.get_json()['errcode'], 0)
        with self.app.app_context():
            self.assertEqual(self.db.session.get(RbacUser, self.target_id).email,
                             'new@example.invalid')

    def test_authorization_unit_conflict_rejects_unchanged_requested_group(self):
        from datas.model.resource_group import ResourceGroup
        from datas.model.user_group import UserGroup

        with self.app.test_client() as client:
            self._login(client)
            data = self._same_values(self._edit_token(client))
            data['role'] = 'operator'
            with self.app.app_context():
                group = ResourceGroup(name='concurrent-group', create_time=utc_now_hms())
                self.db.session.add(group)
                self.db.session.flush()
                link = self.db.session.scalar(select(UserGroup).where(
                    UserGroup.user_id == self.target_id,
                ))
                link.group_id = group.id
                self.db.session.commit()
            result = client.post('/rbac/users/edit', data=data, headers=self._ajax_headers())
            self.assertEqual(result.get_json()['data']['outcome'], 'conflict')

    def test_actor_downgrade_after_native_confirmation_still_denies(self):
        from datas.model.rbac_user import RbacUser

        with self.app.test_client() as client:
            self._login(client)
            data = self._same_values(self._edit_token(client))
            data['email'] = ''
            response = client.post('/rbac/users/edit', data=data)
            self.assertEqual(self._echoed_token(response), data['edit_snapshot_token'])
            with self.app.app_context():
                self.db.session.get(RbacUser, self.actor_id).role = 'viewer'
                self.db.session.commit()
            data.update(confirm_clear_email='1', email_clear_reason='reason')
            self.assertEqual(client.post('/rbac/users/edit', data=data).status_code, 403)
        with self.app.app_context():
            self.assertEqual(self.db.session.get(RbacUser, self.target_id).email,
                             'old@example.invalid')


    def test_audit_v1_rejects_version_and_top_level_shape_errors(self):
        import json

        from app.rbac.services import format_user_update_audit_detail as parse

        base = {'schema_version': 1, 'changes': {
            'nickname': {'before': 'original', 'after': 'requested'},
        }}
        for payload in (
            None, [], {}, dict(base, schema_version=True),
            dict(base, schema_version=1.0), dict(base, schema_version='1'),
            dict(base, future_metadata='unknown'), {'schema_version': 1},
            dict(base, changes={}), dict(base, changes=[]),
        ):
            with self.subTest(payload=payload):
                self.assertEqual(parse(json.dumps(payload)), {
                    'state': 'invalid', 'changes': [], 'reason': None,
                })
        self.assertEqual(parse(json.dumps(dict(base, schema_version=2))), {
            'state': 'unsupported', 'changes': [], 'reason': None,
        })
        for empty in (None, ''):
            self.assertEqual(parse(empty)['state'], 'legacy')
        for non_text in (False, 0, []):
            self.assertEqual(parse(non_text)['state'], 'invalid')

    def test_audit_v1_rejects_any_bad_field_without_partial_output(self):
        import json

        from app.rbac.services import format_user_update_audit_detail as parse

        bad_changes = (
            {'future_field': {'before': 'x', 'after': 'y'}},
            {'email': {'before': 42, 'after': 'a@example.invalid'}},
            {'nickname': {'before': False, 'after': 'new'}},
            {'job_title': {'before': [], 'after': 'qa'}},
            {'role': {'before': None, 'after': 'viewer'}},
            {'role': {'before': True, 'after': 'viewer'}},
            {'group_ids': {'before': None, 'after': [1]}},
            {'group_ids': {'before': [True], 'after': [1]}},
            {'group_ids': {'before': [2, 1], 'after': [1]}},
            {'group_ids': {'before': [1, 1], 'after': [1]}},
            {'group_ids': {'before': ['1'], 'after': [1]}},
            {'email': {'before': 'x'}},
            {'email': {'before': 'x', 'after': 'y', 'extra': 'z'}},
            {'email': 'invalid-change-object'},
        )
        for changes in bad_changes:
            with self.subTest(changes=changes):
                # A valid field in the same event must also be suppressed.
                changes = dict(changes, nickname=changes.get('nickname', {
                    'before': 'never-show-before', 'after': 'never-show-after',
                }))
                self.assertEqual(parse(json.dumps({
                    'schema_version': 1, 'changes': changes,
                })), {'state': 'invalid', 'changes': [], 'reason': None})

    def test_audit_v1_reason_must_match_email_clear_event(self):
        import json

        from app.rbac.services import format_user_update_audit_detail as parse

        clear = {'schema_version': 1, 'changes': {
            'email': {'before': 'old@example.invalid', 'after': None},
        }}
        self.assertEqual(parse(json.dumps(clear))['state'], 'invalid')
        for reason in (None, '', ' ', 'x' * 501, 42, [], {}):
            with self.subTest(reason=reason):
                self.assertEqual(parse(json.dumps(dict(clear, reason=reason))), {
                    'state': 'invalid', 'changes': [], 'reason': None,
                })
        self.assertEqual(parse(json.dumps(dict(clear, reason=' valid ')))['reason'], 'valid')
        non_clear = {'schema_version': 1, 'changes': {
            'email': {'before': 'old@example.invalid', 'after': 'new@example.invalid'},
        }}
        self.assertEqual(parse(json.dumps(dict(non_clear, reason='unexpected')))['state'], 'invalid')

    def test_real_writer_audits_are_readable_without_business_revalidation(self):
        import json

        from app.rbac.services import format_user_update_audit_detail as parse
        from datas.model.rbac_audit_log import RbacAuditLog

        with self.app.test_client() as client:
            self._login(client)
            for changes in (
                {'nickname': 'new nickname'},
                {'role': 'operator'},
                {'email': '', 'confirm_clear_email': '1', 'email_clear_reason': 'reason'},
            ):
                page_token = self._edit_token(client)
                from app.rbac.services import verify_user_edit_snapshot
                snapshot = verify_user_edit_snapshot(
                    self.app.secret_key, page_token, self.actor_id, self.target_id,
                )['snapshot']
                data = dict(snapshot, id=str(self.target_id), edit_snapshot_token=page_token)
                data['group_ids'] = str(self.group_id)
                data.update(changes)
                response = client.post('/rbac/users/edit', data=data, headers=self._ajax_headers())
                self.assertEqual(response.get_json()['errcode'], 0)
        with self.app.app_context():
            rows = self.db.session.scalars(select(RbacAuditLog).where(
                RbacAuditLog.action == 'user:update',
            )).all()
            self.assertEqual(len(rows), 3)
            for row in rows:
                self.assertEqual(parse(row.detail)['state'], 'ok')
        # Historical role/job text need not match today's enums.
        self.assertEqual(parse(json.dumps({'schema_version': 1, 'changes': {
            'role': {'before': 'historical-role', 'after': 'viewer'},
            'job_title': {'before': 'historical-job', 'after': 'qa'},
        }}))['state'], 'ok')

    def test_bad_audit_is_atomic_in_full_and_partial_pages_and_db_unchanged(self):
        import json

        from datas.model.rbac_audit_log import RbacAuditLog

        detail = json.dumps({'schema_version': 1, 'changes': {
            'nickname': {'before': 'PRIVATE_BEFORE', 'after': 'PRIVATE_AFTER'},
            'future_field': {'before': '<script>window.p2_xss=1</script>', 'after': 'x'},
        }})
        with self.app.app_context():
            row = RbacAuditLog(
                user_id=self.actor_id, username='u1_global_admin',
                action='user:update', resource='p2_bad_audit', detail=detail,
                status='allow', create_time=utc_now_hms(), actor_group_ids='',
            )
            self.db.session.add(row)
            self.db.session.commit()
            row_id = row.id
        with self.app.test_client() as client:
            self._login(client)
            for suffix in ('', '?partial=1'):
                response = client.get('/rbac/audit-logs' + suffix)
                self.assertEqual(response.status_code, 200)
                html = (response.get_json()['rows'] if suffix
                        else response.get_data(as_text=True))
                self.assertIn('p2_bad_audit', html)
                self.assertIn('审计详情格式无效', html)
                self.assertNotIn('PRIVATE_BEFORE', html)
                self.assertNotIn('PRIVATE_AFTER', html)
                self.assertNotIn('window.p2_xss', html)
                self.assertNotIn('含未知字段，已安全忽略', html)
        with self.app.app_context():
            self.assertEqual(self.db.session.get(RbacAuditLog, row_id).detail, detail)


if __name__ == '__main__':
    unittest.main()
