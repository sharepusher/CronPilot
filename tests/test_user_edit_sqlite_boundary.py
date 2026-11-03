"""Memory-only guards for SQLite request-owned write admission and failure phases."""
import unittest
from types import SimpleNamespace
from unittest import mock

from sqlalchemy import event, text

from app.rbac.services import build_user_edit_intent, update_user_management
from app.services.sqlite_write_boundary import (
    SQLiteBoundaryError,
    begin_sqlite_write_boundary,
    rollback_or_invalidate,
)
from datas.model.rbac_audit_log import RbacAuditLog
from datas.model.rbac_user import RbacUser
from datas.model.resource_group import ResourceGroup
from datas.model.user_group import UserGroup
from tests import test_user_edit_change_set as fixtures

MODELS = (RbacUser, UserGroup, ResourceGroup, RbacAuditLog)


class TestSQLiteBoundary(unittest.TestCase):
    setUp = fixtures.TestUserEditChangeSet.setUp
    tearDown = fixtures.TestUserEditChangeSet.tearDown
    _service_values = fixtures.TestUserEditChangeSet._service_values

    def _save(self, original, requested):
        return update_user_management(self.actor_id, self.target_id, original, requested,
                                      build_user_edit_intent(original, requested))

    def test_acquisition_uses_session_connection_and_restores_timeout(self):
        with self.app.app_context():
            s = self.db.session()
            c = s.connection()
            c.exec_driver_sql('PRAGMA busy_timeout=1234')
            s.rollback()
            self.assertTrue(begin_sqlite_write_boundary(s, MODELS))
            c = s.connection()
            self.assertTrue(c.connection.driver_connection.in_transaction)
            self.assertEqual(c.exec_driver_sql('PRAGMA busy_timeout').scalar_one(), 1234)
            driver = c.connection.driver_connection
            s.rollback()
            self.assertFalse(driver.in_transaction)

    def test_service_protects_before_first_authorization_read(self):
        with self.app.test_request_context('/rbac/users/edit', method='POST'):
            original, requested = self._service_values(nickname='safe')
            phases = []
            def observe(conn, _cursor, statement, _params, _context, _many):
                if statement == 'BEGIN IMMEDIATE':
                    phases.append('begin')
                elif statement.lstrip().startswith('SELECT rbac_users.'):
                    self.assertEqual(phases[0], 'begin')
                    self.assertTrue(conn.connection.driver_connection.in_transaction)
                    phases.append('protected_read')
            event.listen(self.db.engine, 'before_cursor_execute', observe)
            try:
                result = self._save(original, requested)
            finally:
                event.remove(self.db.engine, 'before_cursor_execute', observe)
            self.assertEqual(result['outcome'], 'updated')
            self.assertIn('protected_read', phases)

    def test_pending_orm_work_refused_without_rollback_or_flush(self):
        with self.app.test_request_context('/rbac/users/edit', method='POST'):
            original, requested = self._service_values(nickname='safe')
            target = self.db.session.get(RbacUser, self.target_id)
            target.nickname = 'caller-owned'
            with mock.patch.object(self.db.session(), 'rollback') as rollback, \
                    mock.patch.object(self.db.session(), 'flush') as flush:
                result = self._save(original, requested)
            self.assertEqual(result['outcome'], 'failed')
            rollback.assert_not_called()
            flush.assert_not_called()
            self.assertEqual(target.nickname, 'caller-owned')

    def test_real_transaction_before_admission_is_rejected(self):
        with self.app.app_context():
            s = self.db.session()
            s.connection().exec_driver_sql('BEGIN')
            with self.assertRaisesRegex(SQLiteBoundaryError, 'already_started'):
                begin_sqlite_write_boundary(s, MODELS)
            s.rollback()

    def test_begin_failure_restores_timeout_and_is_failed_not_unknown(self):
        with self.app.test_request_context('/rbac/users/edit', method='POST'):
            original, requested = self._service_values(nickname='safe')
            s = self.db.session()
            with mock.patch('app.rbac.services.begin_sqlite_write_boundary',
                            side_effect=RuntimeError('fixed admission failure')):
                result = self._save(original, requested)
            self.assertEqual(result['outcome'], 'failed')
            self.assertFalse(s.in_transaction())
            self.assertEqual(self.db.session.get(RbacUser, self.target_id).nickname, 'old')

    def test_entry_rollback_failure_is_contained_and_invalidates(self):
        with self.app.test_request_context('/rbac/users/edit', method='POST'):
            original, requested = self._service_values(nickname='safe')
            s = self.db.session()
            with mock.patch.object(s, 'rollback', side_effect=RuntimeError('fixed rollback failure')), \
                    mock.patch.object(s, 'invalidate', wraps=s.invalidate) as invalidate:
                result = self._save(original, requested)
            self.assertEqual(result['outcome'], 'failed')
            invalidate.assert_called_once()

    def test_restore_failure_discards_connection(self):
        with self.app.app_context():
            s = self.db.session()
            connection = s.connection()
            execute = connection.exec_driver_sql
            def injected(sql, *args, **kwargs):
                if sql.startswith('PRAGMA busy_timeout=') and sql != 'PRAGMA busy_timeout=0':
                    raise RuntimeError('fixed restore failure')
                return execute(sql, *args, **kwargs)
            with mock.patch.object(connection, 'exec_driver_sql', side_effect=injected), \
                    mock.patch.object(s, 'invalidate', wraps=s.invalidate) as invalidate:
                with self.assertRaisesRegex(SQLiteBoundaryError, 'restore_failed'):
                    begin_sqlite_write_boundary(s, MODELS)
            invalidate.assert_called_once()

    def test_begin_sql_error_restores_original_timeout(self):
        with self.app.app_context():
            s = self.db.session()
            connection = s.connection()
            old = connection.exec_driver_sql('PRAGMA busy_timeout').scalar_one()
            execute = connection.exec_driver_sql
            def injected(sql, *args, **kwargs):
                if sql == 'BEGIN IMMEDIATE':
                    raise RuntimeError('fixed begin failure')
                return execute(sql, *args, **kwargs)
            with mock.patch.object(connection, 'exec_driver_sql', side_effect=injected):
                with self.assertRaises(RuntimeError):
                    begin_sqlite_write_boundary(s, MODELS)
            self.assertEqual(connection.exec_driver_sql('PRAGMA busy_timeout').scalar_one(), old)
            s.rollback()

    def test_no_commit_owned_by_helper(self):
        with self.app.app_context():
            s = self.db.session()
            with mock.patch.object(s, 'commit') as commit:
                begin_sqlite_write_boundary(s, MODELS)
                commit.assert_not_called()
                s.rollback()

    def test_cleanup_failure_is_not_raised_over_original_failure(self):
        session = mock.Mock()
        session.rollback.side_effect = RuntimeError('fixed rollback failure')
        self.assertFalse(rollback_or_invalidate(session))
        session.invalidate.assert_called_once()

    def test_cleanup_and_invalidation_failures_are_contained(self):
        session = mock.Mock()
        session.rollback.side_effect = RuntimeError('fixed rollback failure')
        session.invalidate.side_effect = RuntimeError('fixed invalidation failure')
        self.assertFalse(rollback_or_invalidate(session))

    def test_mysql_never_receives_sqlite_sql(self):
        session = mock.Mock()
        session.get_bind.return_value = SimpleNamespace(dialect=SimpleNamespace(name='mysql'))
        self.assertFalse(begin_sqlite_write_boundary(session, MODELS))
        session.connection.assert_not_called()

    def test_multiple_binds_rejected(self):
        session = mock.Mock()
        session.get_bind.side_effect = [object(), object()]
        with self.assertRaisesRegex(SQLiteBoundaryError, 'multiple_business_binds'):
            begin_sqlite_write_boundary(session, MODELS[:2])
        session.connection.assert_not_called()

    def test_sqlite_write_transaction_released_after_rollback(self):
        with self.app.app_context():
            s = self.db.session()
            begin_sqlite_write_boundary(s, MODELS)
            s.execute(text('SELECT 1'))
            self.assertTrue(rollback_or_invalidate(s))
            self.assertFalse(s.in_transaction())
