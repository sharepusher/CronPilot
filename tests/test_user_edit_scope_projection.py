"""R5: partial form values must never replace full user authorization."""
import copy
import json
import re
import unittest
from unittest import mock

from sqlalchemy import delete, event, select

from app.rbac.services import (
    build_user_edit_intent,
    build_user_edit_snapshot,
    get_user_group_ids_for_user,
    project_user_edit_values,
    sign_user_edit_snapshot,
    update_user_management,
    verify_user_edit_snapshot,
)
from datas.model.rbac_audit_log import RbacAuditLog
from datas.model.rbac_user import RbacUser
from datas.model.resource_group import ResourceGroup
from datas.model.user_group import UserGroup
from datas.utils.times import utc_now_hms
from tests import test_user_edit_change_set as base_tests


class TestUserEditScopeProjection(unittest.TestCase):
    setUp = base_tests.TestUserEditChangeSet.setUp
    tearDown = base_tests.TestUserEditChangeSet.tearDown
    _login = base_tests.TestUserEditChangeSet._login
    _edit_token = base_tests.TestUserEditChangeSet._edit_token
    _same_values = base_tests.TestUserEditChangeSet._same_values
    _ajax_headers = staticmethod(base_tests.TestUserEditChangeSet._ajax_headers)

    def prepare(self, multi=False):
        groups = [ResourceGroup(name=n, create_time=utc_now_hms()) for n in ('R5-B', 'R5-C', 'R5-D')]
        self.db.session.add_all(groups)
        self.db.session.flush()
        self.b, self.c, self.d = [g.id for g in groups]
        self.bind(self.actor_id, [self.group_id, self.c] if multi else [self.group_id])
        self.bind(self.target_id, [self.group_id, self.b])
        target = self.db.session.get(RbacUser, self.target_id)
        target.api_token = 'r5-preserve-token'
        self.db.session.commit()
        original = build_user_edit_snapshot(
            self.actor_id, target, get_user_group_ids_for_user(self.target_id),
        )
        return original, project_user_edit_values(original)

    def bind(self, uid, groups):
        self.db.session.execute(delete(UserGroup).where(UserGroup.user_id == uid))
        self.db.session.add_all(UserGroup(user_id=uid, group_id=g) for g in groups)
        self.db.session.commit()

    def save(self, original, values):
        return update_user_management(self.actor_id, self.target_id, original, values,
                                      build_user_edit_intent(original, values))

    def test_profile_only_no_relationship_dml_or_auth_side_effects(self):
        with self.app.app_context():
            original, values = self.prepare()
            values['nickname'] = 'Summer'
            statements = []

            def capture(conn, cursor, statement, params, context, many):
                statements.append(statement.lower())

            event.listen(self.db.engine, 'before_cursor_execute', capture)
            try:
                with mock.patch('app.rbac.services._auto_issue_token') as issue, \
                        mock.patch('app.rbac.services._invalidate_api_scope_cache') as cache:
                    result = self.save(original, values)
                    self.assertTrue(result['ok'], result)
                    issue.assert_not_called()
                    cache.assert_not_called()
            finally:
                event.remove(self.db.engine, 'before_cursor_execute', capture)
            self.assertFalse(any('user_groups' in sql and sql.lstrip().startswith(
                ('insert', 'update', 'delete')) for sql in statements))
            target = self.db.session.get(RbacUser, self.target_id)
            self.assertEqual((target.nickname, target.role, target.email, target.auth_version,
                              target.api_token, target.job_title),
                             ('Summer', 'viewer', 'old@example.invalid', 0, 'r5-preserve-token', 'qa'))
            self.assertEqual(get_user_group_ids_for_user(self.target_id), [self.group_id, self.b])
            self.assertEqual(set(json.loads(self.db.session.scalar(select(RbacAuditLog)).detail)
                                 ['changes']), {'nickname'})

    def test_actual_group_change_retains_outside_and_replay_is_idempotent(self):
        with self.app.app_context():
            original, values = self.prepare(multi=True)
            values['group_ids'] = [self.c]
            result = self.save(original, values)
            self.assertTrue(result['ok'], result)
            self.assertEqual(get_user_group_ids_for_user(self.target_id), sorted([self.b, self.c]))
            self.assertEqual(self.db.session.get(RbacUser, self.target_id).auth_version, 1)
            detail = json.loads(self.db.session.scalar(select(RbacAuditLog)).detail)
            self.assertEqual(detail['changes']['group_ids'], {
                'before': [self.group_id, self.b], 'after': sorted([self.b, self.c]),
            })
            self.assertEqual(self.save(original, values)['outcome'], 'already_applied')
            self.assertEqual(len(self.db.session.scalars(select(RbacAuditLog)).all()), 1)

    def test_profile_only_preserves_concurrent_outside_groups_and_role(self):
        with self.app.app_context():
            original, values = self.prepare()
            self.bind(self.target_id, [self.group_id, self.d])
            target = self.db.session.get(RbacUser, self.target_id)
            target.role = 'admin'
            self.db.session.commit()
            values['nickname'] = 'Summer'
            self.assertTrue(self.save(original, values)['ok'])
            self.assertEqual(get_user_group_ids_for_user(self.target_id), [self.group_id, self.d])
            self.assertEqual(self.db.session.get(RbacUser, self.target_id).role, 'admin')

    def test_actual_auth_change_conflicts_with_concurrent_outside_change(self):
        with self.app.app_context():
            original, values = self.prepare(multi=True)
            self.bind(self.target_id, [self.group_id, self.d])
            values.update(nickname='Summer', group_ids=[self.c])
            self.assertEqual(self.save(original, values)['outcome'], 'conflict')
            self.assertEqual(self.db.session.get(RbacUser, self.target_id).nickname, 'old')
            self.assertEqual(get_user_group_ids_for_user(self.target_id), [self.group_id, self.d])
            self.assertIsNone(self.db.session.scalar(select(RbacAuditLog)))

    def test_locked_boundary_rejects_actor_scope_change_and_illegal_grant(self):
        with self.app.app_context():
            original, values = self.prepare(multi=True)
            values.update(nickname='Summer', group_ids=[self.d])
            self.assertFalse(self.save(original, values)['ok'])
            values['group_ids'] = [self.group_id]
            self.bind(self.actor_id, [self.group_id])
            self.assertFalse(self.save(original, values)['ok'])
            self.assertEqual(self.db.session.get(RbacUser, self.target_id).nickname, 'old')
            self.assertIsNone(self.db.session.scalar(select(RbacAuditLog)))

    def test_route_noop_and_profile_only_with_hidden_group(self):
        with self.app.app_context():
            self.prepare()
        with self.app.test_client() as client:
            self._login(client)
            token = self._edit_token(client)
            values = self._same_values(token)
            result = client.post('/rbac/users/edit', data=values, headers=self._ajax_headers())
            self.assertEqual(result.get_json()['data']['outcome'], 'no_change')
            values['nickname'] = 'Summer'
            result = client.post('/rbac/users/edit', data=values, headers=self._ajax_headers())
            self.assertEqual(result.get_json()['errcode'], 0)
        with self.app.app_context():
            self.assertEqual(get_user_group_ids_for_user(self.target_id), [self.group_id, self.b])
            self.assertEqual(self.db.session.get(RbacUser, self.target_id).auth_version, 0)

    def test_route_scope_change_rejects_even_noop(self):
        with self.app.app_context():
            self.prepare()
        with self.app.test_client() as client:
            self._login(client)
            token = self._edit_token(client)
            with self.app.app_context():
                self.bind(self.actor_id, [self.group_id, self.c])
            response = client.post('/rbac/users/edit', data=self._same_values(token),
                                   headers=self._ajax_headers())
            self.assertEqual(response.get_json()['errcode'], 1)

    def test_native_confirmation_echoes_t0_and_same_editable_projection(self):
        with self.app.app_context():
            self.prepare()
        with self.app.test_client() as client:
            self._login(client)
            token = self._edit_token(client)
            data = self._same_values(token)
            data['email'] = ''
            response = client.post('/rbac/users/edit', data=data)
            html = response.get_data(as_text=True)
            self.assertIn('value="' + token + '"', html)
            values = json.loads(re.search(r'var original = (.*);', html).group(1))
            self.assertEqual(values['group_ids'], [self.group_id])
            with self.app.app_context():
                snapshot = verify_user_edit_snapshot(self.app.secret_key, token,
                                                    self.actor_id, self.target_id)['snapshot']
                self.assertEqual(snapshot['group_ids'], [self.group_id, self.b])
                self.assertIsNone(self.db.session.scalar(select(RbacAuditLog)))

    def test_profile_field_conflict_rejects_without_group_or_audit_writes(self):
        with self.app.app_context():
            original, values = self.prepare()
            target = self.db.session.get(RbacUser, self.target_id)
            target.nickname = 'another-editor'
            self.db.session.commit()
            values['nickname'] = 'Summer'
            self.assertEqual(self.save(original, values)['outcome'], 'conflict')
            self.assertEqual(get_user_group_ids_for_user(self.target_id), [self.group_id, self.b])
            self.assertIsNone(self.db.session.scalar(select(RbacAuditLog)))

    def test_snapshot_rejects_old_missing_malformed_editor_boundary(self):
        with self.app.app_context():
            original, values = self.prepare()
            self.assertEqual(build_user_edit_intent(original, values), {})
            bad = [dict(original, schema_version=1), dict(original, schema_version=True)]
            missing = dict(original)
            del missing['editor_scope']
            bad.append(missing)
            for scope in (None, {}, {'bypass': 1, 'group_ids': []},
                          {'bypass': True, 'group_ids': [1]},
                          {'bypass': False, 'group_ids': []},
                          {'bypass': False, 'group_ids': [True]},
                          {'bypass': False, 'group_ids': [2, 1]}):
                bad.append(dict(original, editor_scope=scope))
            for snapshot in bad:
                with self.subTest(snapshot=snapshot):
                    result = verify_user_edit_snapshot(self.app.secret_key,
                        sign_user_edit_snapshot(self.app.secret_key, copy.deepcopy(snapshot)),
                        self.actor_id, self.target_id)
                    self.assertFalse(result['ok'])
