# -*- coding: utf-8 -*-
import importlib.util
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load_ensure():
    path = os.path.join(ROOT, 'scripts', 'ensure_business_tables.py')
    spec = importlib.util.spec_from_file_location('ensure_business_tables_test', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestEnsureBusinessTablesBackend(unittest.TestCase):
    def test_backend_detection(self):
        mod = _load_ensure()
        self.assertEqual(mod.business_db_backend('sqlite:////tmp/x.db'), 'sqlite')
        self.assertEqual(mod.business_db_backend('sqlite:///:memory:'), 'sqlite')
        self.assertEqual(
            mod.business_db_backend('mysql+pymysql://u:p@127.0.0.1:3306/cron'),
            'mysql',
        )
        self.assertEqual(mod.business_db_backend('mysql://u:p@localhost/db'), 'mysql')
        self.assertEqual(mod.business_db_backend('postgresql://localhost/db'), '')
        self.assertEqual(mod.business_db_backend(''), '')


class TestEnsureCronInfosColumns(unittest.TestCase):
    def test_adds_only_req_method_and_req_body_for_legacy_table(self):
        mod = _load_ensure()
        executed_sql = []

        class _Conn:
            def execute(self, stmt):
                executed_sql.append(str(stmt))

        class _BeginCtx:
            def __enter__(self):
                return _Conn()

            def __exit__(self, exc_type, exc_val, exc_tb):
                return False

        fake_engine = SimpleNamespace(begin=lambda: _BeginCtx())
        fake_db = SimpleNamespace(engine=fake_engine)
        fake_inspector = SimpleNamespace(
            has_table=lambda name: name == 'cron_infos',
            get_columns=lambda name: [
                {'name': 'id'},
                {'name': 'req_url'},
                {'name': 'created_at'},
                {'name': 'updated_at'},
                {'name': 'retire_reason'},
                {'name': 'retired_at'},
                {'name': 'scope_type'},
                {'name': 'group_id'},
            ],
        )

        with patch.object(mod, 'db', fake_db), patch('sqlalchemy.inspect', return_value=fake_inspector):
            mod._ensure_cron_infos_columns()

        self.assertEqual(len(executed_sql), 2)
        sql_text = '\n'.join(executed_sql)
        self.assertIn('ALTER TABLE cron_infos ADD COLUMN req_method VARCHAR(10) DEFAULT', sql_text)
        self.assertIn('ALTER TABLE cron_infos ADD COLUMN req_body TEXT DEFAULT', sql_text)

    def test_does_nothing_when_columns_already_exist(self):
        mod = _load_ensure()
        executed_sql = []

        class _Conn:
            def execute(self, stmt):
                executed_sql.append(str(stmt))

        class _BeginCtx:
            def __enter__(self):
                return _Conn()

            def __exit__(self, exc_type, exc_val, exc_tb):
                return False

        fake_engine = SimpleNamespace(begin=lambda: _BeginCtx())
        fake_db = SimpleNamespace(engine=fake_engine)
        fake_inspector = SimpleNamespace(
            has_table=lambda name: name == 'cron_infos',
            get_columns=lambda name: [
                {'name': 'id'},
                {'name': 'req_url'},
                {'name': 'created_at'},
                {'name': 'updated_at'},
                {'name': 'retire_reason'},
                {'name': 'retired_at'},
                {'name': 'scope_type'},
                {'name': 'group_id'},
                {'name': 'req_method'},
                {'name': 'req_body'},
            ],
        )

        with patch.object(mod, 'db', fake_db), patch('sqlalchemy.inspect', return_value=fake_inspector):
            mod._ensure_cron_infos_columns()

        self.assertEqual(executed_sql, [])

    def test_mysql_uses_text_without_default_for_req_body(self):
        mod = _load_ensure()
        executed_sql = []

        class _Conn:
            def execute(self, stmt):
                executed_sql.append(str(stmt))

        class _BeginCtx:
            def __enter__(self):
                return _Conn()

            def __exit__(self, exc_type, exc_val, exc_tb):
                return False

        fake_engine = SimpleNamespace(begin=lambda: _BeginCtx())
        fake_db = SimpleNamespace(engine=fake_engine)
        fake_inspector = SimpleNamespace(
            has_table=lambda name: name == 'cron_infos',
            get_columns=lambda name: [
                {'name': 'id'},
                {'name': 'req_url'},
                {'name': 'created_at'},
                {'name': 'updated_at'},
                {'name': 'retire_reason'},
                {'name': 'retired_at'},
                {'name': 'scope_type'},
                {'name': 'group_id'},
            ],
        )

        with patch.object(mod, 'db', fake_db), patch('sqlalchemy.inspect', return_value=fake_inspector):
            mod._ensure_cron_infos_columns(backend='mysql')

        sql_text = '\n'.join(executed_sql)
        self.assertIn('ALTER TABLE cron_infos ADD COLUMN req_body TEXT', sql_text)
        self.assertNotIn("ALTER TABLE cron_infos ADD COLUMN req_body TEXT DEFAULT ''", sql_text)


if __name__ == '__main__':
    unittest.main()
