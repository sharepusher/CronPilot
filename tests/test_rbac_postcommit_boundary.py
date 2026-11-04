"""Real commit, default expiration, and real scope cache fault regressions."""
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from sqlalchemy import event

from app.api import _SCOPE_CACHE, _resolve_user_token
from app.rbac import services
from datas.model.rbac_user import RbacUser
from datas.model.resource_group import ResourceGroup
from tests import test_user_edit_change_set as edit_fixtures
from tests import test_user_reactivation as reactivation_fixtures


@contextmanager
def reject_postcommit_loads(db):
    session = db.session()
    state = {'commits': 0}

    def committed(_session):
        state['commits'] += 1

    def reject(ctx):
        if state['commits'] and ctx.is_column_load:
            raise AssertionError('postcommit ORM column read')

    event.listen(session, 'after_commit', committed)
    event.listen(session, 'do_orm_execute', reject)
    try:
        yield state
    finally:
        event.remove(session, 'after_commit', committed)
        event.remove(session, 'do_orm_execute', reject)


class TestRbacPostcommitBoundary(unittest.TestCase):
    def exercise(self, name, audit_failure=False):
        fixture = edit_fixtures.TestUserEditChangeSet()
        fixture.setUp()
        try:
            with fixture.app.test_request_context('/rbac/users/edit', method='POST'):
                user = fixture.db.session.get(RbacUser, fixture.target_id)
                user.role = 'operator'
                user.api_token = 'isolated-postcommit-old-token'
                group = ResourceGroup(name='postcommit-extra')
                fixture.db.session.add(group)
                fixture.db.session.commit()
                gid = group.id
                self.assertIsNotNone(_resolve_user_token('isolated-postcommit-old-token'))
                original, requested = fixture._service_values(role='viewer')
                calls = {
                    'edit': lambda: services.update_user_management(
                        fixture.actor_id, fixture.target_id, original, requested,
                        services.build_user_edit_intent(original, requested)),
                    'disable': lambda: services.set_user_active(fixture.target_id, 0, 'test', fixture.actor_id),
                    'reset': lambda: services.trigger_password_reset(fixture.target_id, fixture.actor_id),
                    'groups': lambda: services.set_user_groups(fixture.target_id, [gid]),
                    'password': lambda: services.change_own_password(
                        fixture.target_id, 'test-password', 'new-password', 'new-password'),
                    'token': lambda: services.issue_user_api_token(fixture.target_id),
                    'legacy': lambda: services.update_user(fixture.target_id, is_active=0),
                    'create': lambda: services.create_user('postcommit-new', group_ids=[gid]),
                }
                with reject_postcommit_loads(fixture.db):
                    if audit_failure:
                        # Real audit helper catches its own storage failure.
                        with patch.object(fixture.db.session, 'add', side_effect=RuntimeError('audit unavailable')):
                            # Token issuance doesn't add business rows before commit.
                            result = calls[name]()
                    else:
                        result = calls[name]()
                self.assertTrue(result['ok'], result)
                if name != 'create':
                    self.assertNotIn('isolated-postcommit-old-token', _SCOPE_CACHE)
                fixture.db.session.remove()
                stored = fixture.db.session.get(RbacUser, fixture.target_id)
                if name in ('disable', 'legacy'):
                    self.assertFalse(stored.is_active)
                if name == 'edit':
                    self.assertEqual(stored.role, 'viewer')
                    self.assertEqual(stored.auth_version, 1)
                if name == 'token':
                    self.assertEqual(result['token'], stored.api_token)
                    self.assertEqual(result['expires_at'], stored.api_token_expires_at)
                if name not in ('create',):
                    self.assertIsNone(_resolve_user_token('isolated-postcommit-old-token'))
                if name == 'create':
                    self.assertIsNotNone(fixture.db.session.get(RbacUser, result['user_id']))
        finally:
            _SCOPE_CACHE.clear()
            fixture.tearDown()

    def test_all_entrypoints_survive_expired_column_failure(self):
        for name in ('edit', 'disable', 'reset', 'groups', 'password', 'token', 'legacy', 'create'):
            with self.subTest(entry=name):
                self.exercise(name)

    def test_token_response_survives_separate_audit_failure(self):
        self.exercise('token', audit_failure=True)

    def test_new_requests_observe_downgrade_after_cached_token_is_revoked(self):
        fixture = edit_fixtures.TestUserEditChangeSet()
        fixture.setUp()
        try:
            from app.api import _api_token_guard, check_api_permission

            @fixture.app.route('/postcommit-write-probe')
            def write_probe():
                denied = _api_token_guard()
                if denied is not None:
                    return denied
                denied = check_api_permission('cron:write')
                return denied if denied is not None else ('ok', 200)

            with fixture.app.test_request_context():
                user = fixture.db.session.get(RbacUser, fixture.target_id)
                user.role = 'operator'
                user.api_token = 'isolated-http-old-token'
                fixture.db.session.commit()
            client = fixture.app.test_client()
            with patch('configs.configs', return_value='isolated-global-token'):
                self.assertEqual(client.get('/postcommit-write-probe', headers={
                    'Authorization': 'Bearer isolated-http-old-token'}).status_code, 200)
                with fixture.app.test_request_context():
                    original, requested = fixture._service_values(role='viewer')
                    with reject_postcommit_loads(fixture.db):
                        result = services.update_user_management(
                            fixture.actor_id, fixture.target_id, original, requested,
                            services.build_user_edit_intent(original, requested))
                    self.assertTrue(result['ok'])
                    fixture.db.session.remove()
                    token = fixture.db.session.get(RbacUser, fixture.target_id).api_token
                self.assertEqual(client.get('/postcommit-write-probe', headers={
                    'Authorization': 'Bearer isolated-http-old-token'}).status_code, 401)
                self.assertEqual(client.get('/postcommit-write-probe', headers={
                    'Authorization': 'Bearer ' + token}).status_code, 403)
        finally:
            _SCOPE_CACHE.clear()
            fixture.tearDown()

    def test_commit_failures_never_return_generated_token(self):
        for after_commit, rollback_fails in ((False, False), (True, False), (True, True)):
            with self.subTest(after_commit=after_commit, rollback_fails=rollback_fails):
                fixture = edit_fixtures.TestUserEditChangeSet()
                fixture.setUp()
                try:
                    with fixture.app.test_request_context():
                        user = fixture.db.session.get(RbacUser, fixture.target_id)
                        user.api_token = 'isolated-commit-token'
                        fixture.db.session.commit()
                        _resolve_user_token('isolated-commit-token')
                        session = fixture.db.session()
                        real_commit = session.commit

                        def fail_commit():
                            if after_commit:
                                real_commit()
                            raise RuntimeError('commit acknowledgement unavailable')

                        with patch.object(session, 'commit', side_effect=fail_commit):
                            if rollback_fails:
                                with patch.object(session, 'rollback', side_effect=RuntimeError('cleanup unavailable')):
                                    result = services.issue_user_api_token(fixture.target_id)
                            else:
                                result = services.issue_user_api_token(fixture.target_id)
                        self.assertFalse(result['ok'])
                        self.assertEqual(result['token'], '')
                        self.assertEqual(result['expires_at'], '')
                        self.assertNotIn('isolated-commit-token', _SCOPE_CACHE)
                finally:
                    _SCOPE_CACHE.clear()
                    fixture.tearDown()

    def test_creation_and_approval_keep_identity_without_postcommit_reads(self):
        for name in ('reactivate', 'approve_reactivate', 'approve_new'):
            with self.subTest(entry=name):
                fixture = reactivation_fixtures.TestDisabledUserOverwriteIdentity()
                fixture.setUp()
                try:
                    with fixture.app.test_request_context():
                        from flask import session

                        from datas.model.rbac_registration_request import RbacRegistrationRequest
                        session.update(user_id=fixture.reviewer_id, username='admin')
                        if name == 'approve_new':
                            req = fixture.db.session.get(RbacRegistrationRequest, fixture.request_id)
                            req.username = req.pending_username = 'new-approved-user'
                            req.is_reactivation = 0
                            req.target_user_id = None
                            fixture.db.session.commit()
                        with reject_postcommit_loads(fixture.db):
                            if name == 'reactivate':
                                result = services.create_user('returning', role='operator',
                                    group_ids=[fixture.new_group_id], confirm_reactivation=True)
                            else:
                                result = services.approve_registration(fixture.request_id)
                        self.assertTrue(result['ok'], result)
                        if name != 'approve_new':
                            self.assertEqual(result['user_id'], fixture.old_user_id)
                finally:
                    _SCOPE_CACHE.clear()
                    fixture.tearDown()
