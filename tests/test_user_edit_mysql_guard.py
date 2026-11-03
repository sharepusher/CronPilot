"""P1-B: reject unsafe resources before any DDL or fixture writes."""
import ast
import contextlib
import io
import unittest
from pathlib import Path
from unittest import mock

from scripts import verify_user_edit_transaction_mysql as guard


class TestUserEditMysqlGuard(unittest.TestCase):
    database = 'cronpilot_user_edit_verify_012345abcdef'

    def _connection(self):
        engine = mock.MagicMock()
        connection = engine.connect.return_value.__enter__.return_value
        connection.scalar.return_value = self.database
        return engine, connection

    def test_invalid_urls_never_initialize_app_or_connect(self):
        for url in (
            'not-a-url', 'sqlite:///:memory:',
            'postgresql://user:secret@localhost/db',
            'mysql+pymysql://user:secret@localhost/production',
            'mysql+pymysql://user:secret@localhost/',
            'mysql+mysqldb://user:secret@localhost/' + self.database,
            'mysql+pymysql://user:secret@localhost/x' + self.database,
            'mysql+pymysql://user:secret@localhost/' + self.database + 'extra',
        ):
            with self.subTest(url=url), mock.patch.object(guard, '_make_app') as factory:
                with self.assertRaises(guard.VerificationError) as caught:
                    guard.verify(url)
                factory.assert_not_called()
                self.assertNotIn('secret', str(caught.exception))

    def test_accepts_only_exact_dedicated_mysql_url(self):
        self.assertEqual(guard.assert_isolated_database(
            'mysql+pymysql://user:secret@localhost/' + self.database,
        ), self.database)

    def test_nonempty_table_or_view_never_reaches_ddl(self):
        for tables, views in ((['sentinel'], []), (['rbac_users'], []), ([], ['sentinel_view'])):
            with self.subTest(tables=tables, views=views):
                engine, _connection = self._connection()
                with mock.patch.object(guard, 'inspect') as inspect_db, mock.patch.object(
                    guard.db.metadata, 'create_all',
                ) as create:
                    inspect_db.return_value.get_table_names.return_value = tables
                    inspect_db.return_value.get_view_names.return_value = views
                    with self.assertRaises(guard.VerificationError):
                        guard.prepare_empty_schema(engine, self.database)
                    create.assert_not_called()

    def test_default_schema_mismatch_never_inspects_or_writes(self):
        engine, connection = self._connection()
        connection.scalar.return_value = 'production'
        with mock.patch.object(guard, 'inspect') as inspect_db, mock.patch.object(
            guard.db.metadata, 'create_all',
        ) as create:
            with self.assertRaises(guard.VerificationError):
                guard.prepare_empty_schema(engine, self.database)
            inspect_db.assert_not_called()
            create.assert_not_called()

    def test_inspection_error_does_not_fall_back_to_empty(self):
        engine, _connection = self._connection()
        with mock.patch.object(guard, 'inspect') as inspect_db, mock.patch.object(
            guard.db.metadata, 'create_all',
        ) as create:
            inspect_db.return_value.get_table_names.side_effect = RuntimeError('inspection failed')
            with self.assertRaises(RuntimeError):
                guard.prepare_empty_schema(engine, self.database)
            create.assert_not_called()

    def test_only_four_tables_and_non_idempotent_create(self):
        engine, connection = self._connection()
        with mock.patch.object(guard, 'inspect') as inspect_db, mock.patch.object(
            guard.db.metadata, 'create_all',
        ) as create:
            inspect_db.return_value.get_table_names.return_value = []
            inspect_db.return_value.get_view_names.return_value = []
            guard.prepare_empty_schema(engine, self.database)
            create.assert_called_once_with(
                bind=connection, tables=guard._verification_tables(), checkfirst=False,
            )
            self.assertEqual([table.name for table in create.call_args.kwargs['tables']],
                             ['rbac_users', 'resource_groups', 'user_groups', 'rbac_audit_logs'])
            connection.commit.assert_called_once()

    def test_preparation_failure_prevents_any_fixture_dml(self):
        app = guard._make_app('sqlite:///:memory:')
        with mock.patch.object(guard, 'prepare_empty_schema', side_effect=RuntimeError), mock.patch.object(
            guard.db.session, 'add_all',
        ) as seed:
            with self.assertRaises(RuntimeError):
                guard._run_verification(app, self.database)
            seed.assert_not_called()

    def test_cli_failure_is_nonzero_and_redacts_connection_exception(self):
        url = 'mysql+pymysql://user:TOPSECRET@localhost/' + self.database
        stream = io.StringIO()
        app = guard._make_app('sqlite:///:memory:')
        with mock.patch.object(guard, '_make_app', return_value=app), mock.patch.object(
            guard, '_run_verification', side_effect=RuntimeError(url),
        ), mock.patch('sys.argv', ['verify', '--database-url', url]), contextlib.redirect_stderr(stream):
            self.assertEqual(guard.main(), 1)
        self.assertIn('FAILED', stream.getvalue())
        self.assertNotIn('TOPSECRET', stream.getvalue())
        self.assertNotIn('mysql+pymysql://', stream.getvalue())

    def test_no_destructive_sql_or_global_create_calls_in_script(self):
        tree = ast.parse(Path(guard.__file__).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertNotIn(node.func.attr, ('drop_all', 'drop'))
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                self.assertNotIn('DROP TABLE', node.value.upper())
                self.assertNotIn('TRUNCATE ', node.value.upper())


if __name__ == '__main__':
    unittest.main()
