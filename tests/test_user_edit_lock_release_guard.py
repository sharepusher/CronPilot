"""Lock-release observations must precede framework cleanup; SQLite is not a lock oracle."""
import unittest
from unittest import mock

from sqlalchemy import event
from sqlalchemy.exc import OperationalError

from app.rbac.services import build_user_edit_intent, update_user_management
from datas.model.rbac_user import RbacUser
from scripts import verify_user_edit_transaction_mysql as harness
from tests import test_user_edit_change_set as fixtures


class TestLockReleaseLifecycle(unittest.TestCase):
    setUp = fixtures.TestUserEditChangeSet.setUp
    tearDown = fixtures.TestUserEditChangeSet.tearDown
    _service_values = fixtures.TestUserEditChangeSet._service_values

    def test_route_enters_top_level_service_without_pending_business_writes(self):
        with self.app.test_client() as client:
            fixtures.TestUserEditChangeSet._login(self, client)
            token = fixtures.TestUserEditChangeSet._edit_token(self, client)
            values = fixtures.TestUserEditChangeSet._same_values(self, token)
            values['nickname'] = 'changed'
            statements = []

            def capture(conn, cursor, statement, parameters, context, many):
                if statement.lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE ')):
                    statements.append(statement)

            def inspect_boundary(*args, **kwargs):
                self.assertEqual(statements, [])
                self.assertFalse(self.db.session.new or self.db.session.dirty or self.db.session.deleted)
                return update_user_management(*args, **kwargs)

            with self.app.app_context():
                engine = self.db.engine
            event.listen(engine, 'before_cursor_execute', capture)
            try:
                with mock.patch('app.rbac.views.update_user_management', side_effect=inspect_boundary) as save:
                    response = client.post('/rbac/users/edit', data=values,
                                           headers=fixtures.TestUserEditChangeSet._ajax_headers())
                self.assertEqual(response.get_json()['errcode'], 0)
                save.assert_called_once()
            finally:
                event.remove(engine, 'before_cursor_execute', capture)

    def _run(self, outcome, suppress=False):
        with self.app.test_request_context('/rbac/users/edit', method='POST'):
            original, requested = self._service_values(nickname='requested')
            target = self.db.session.get(RbacUser, self.target_id)
            if outcome == 'conflict':
                target.nickname = 'concurrent'
            elif outcome == 'already_applied':
                target.nickname = 'requested'
            else:
                requested['email'] = None
            self.db.session.commit()
            concrete = self.db.session()
            identity = harness.request._get_current_object()
            real_rollback = concrete.rollback
            calls = []

            def rollback():
                calls.append('rollback')
                if not suppress or len(calls) == 1:
                    return real_rollback()

            with mock.patch.object(concrete, 'rollback', side_effect=rollback):
                result = update_user_management(
                    self.actor_id, self.target_id, original, requested,
                    build_user_edit_intent(original, requested),
                )
            self.assertEqual(result['outcome'], outcome)
            self.assertEqual(len(calls), 2)
            active, _ = harness.capture_exit(concrete, identity)
            self.assertEqual(active, suppress)
        self.assertFalse(concrete.in_transaction())
        return active

    def test_conflict_is_clean_before_teardown(self):
        self._run('conflict')

    def test_already_applied_is_clean_before_teardown(self):
        self._run('already_applied')

    def test_locked_failure_is_clean_before_teardown(self):
        self._run('failed')

    def test_missing_conflict_rollback_is_visible_before_teardown(self):
        self.assertTrue(self._run('conflict', suppress=True))

    def test_missing_already_applied_rollback_is_visible_before_teardown(self):
        self.assertTrue(self._run('already_applied', suppress=True))

    def test_missing_failed_rollback_is_visible_before_teardown(self):
        self.assertTrue(self._run('failed', suppress=True))

    def test_observation_rejects_ended_request(self):
        with self.app.test_request_context('/'):
            concrete = self.db.session()
            identity = harness.request._get_current_object()
        with self.assertRaisesRegex(harness.VerificationError, 'request_ended'):
            harness.capture_exit(concrete, identity)

    def test_observation_rejects_replaced_session(self):
        with self.app.test_request_context('/'):
            concrete = self.db.session()
            identity = harness.request._get_current_object()
            self.db.session.remove()
            with self.assertRaisesRegex(harness.VerificationError, 'session_replaced'):
                harness.capture_exit(concrete, identity)

    def test_observation_rejects_another_request(self):
        with self.app.test_request_context('/'):
            concrete = self.db.session()
            with self.assertRaisesRegex(harness.VerificationError, 'request_changed'):
                harness.capture_exit(concrete, object())


class TestLockProbeFailureSemantics(unittest.TestCase):
    def setUp(self):
        self.connection = mock.MagicMock()
        self.connection.scalar.side_effect = [12, 50]
        self.probe = harness.LockProbe(self.connection)

    def test_probe_matches_actual_row_and_always_rolls_back(self):
        self.connection.execute.return_value.all.return_value = [(7,)]
        result = self.probe.lock('rbac_users', 7)
        self.assertEqual((result['state'], result['row_count']), ('acquired', 1))
        self.connection.begin.return_value.rollback.assert_called_once()

    def test_missing_or_wrong_row_never_counts_as_release(self):
        for rows in ([], [(8,)], [(7,), (7,)]):
            with self.subTest(rows=rows):
                self.connection.execute.return_value.all.return_value = rows
                with self.assertRaisesRegex(harness.VerificationError, 'row_missing'):
                    self.probe.lock('rbac_users', 7)

    def test_only_1205_is_a_blocked_probe_not_network_or_deadlock(self):
        for code in (1205, 1213, 2006, 2013, 1142):
            with self.subTest(code=code):
                raw = RuntimeError(code, 'PRIVATE DATABASE DETAILS')
                self.connection.execute.side_effect = OperationalError('sql', {}, raw)
                if code == 1205:
                    self.assertEqual(self.probe.lock('rbac_users', 7)['state'], 'blocked')
                else:
                    with self.assertRaisesRegex(harness.VerificationError, '^probe_query_failed$'):
                        self.probe.lock('rbac_users', 7)
        self.assertEqual(self.connection.begin.return_value.rollback.call_count, 5)

    def test_probe_resource_identifiers_cannot_be_injected(self):
        for table, key in (('rbac_users; DROP TABLE x', 7), ('rbac_users', '7'),
                           ('rbac_users', True)):
            with self.assertRaisesRegex(harness.VerificationError, 'resource_invalid'):
                self.probe.lock(table, key)
        self.connection.begin.assert_not_called()

    def test_original_session_timeout_is_restored(self):
        self.probe.restore()
        self.assertEqual(self.connection.execute.call_args.args[1], {'value': 50})
        self.connection.invalidate.assert_not_called()

    def test_failed_cleanup_discards_connection(self):
        self.connection.execute.side_effect = RuntimeError('PRIVATE')
        with self.assertRaisesRegex(harness.VerificationError, '^probe_cleanup_failed$'):
            self.probe.restore()
        self.connection.invalidate.assert_called_once()


if __name__ == '__main__':
    unittest.main()
