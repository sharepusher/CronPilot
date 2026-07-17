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


class TestEnsureRbacUsersColumns(unittest.TestCase):
    def test_alter_ddl_is_sqlite_and_mysql_compatible(self):
        """补列 DDL 不使用仅 SQLite/仅 MySQL 方言；两端均接受 SMALLINT/VARCHAR DEFAULT。"""
        mod = _load_ensure()
        # 通过函数源确认关键语句形态（两端通用 ALTER ADD COLUMN）
        import inspect as py_inspect
        src = py_inspect.getsource(mod._ensure_rbac_users_columns)
        self.assertIn('ALTER TABLE rbac_users ADD COLUMN must_reset_password', src)
        self.assertIn('SMALLINT NOT NULL DEFAULT 0', src)
        self.assertIn('ALTER TABLE rbac_users ADD COLUMN status_reason', src)
        self.assertNotIn('AUTOINCREMENT', src)
        self.assertNotIn('AUTO_INCREMENT', src)
        cron_src = py_inspect.getsource(mod._ensure_cron_infos_columns)
        self.assertIn('last_operator_name', cron_src)
        self.assertIn('last_operated_at', cron_src)
        self.assertIn('req_method', cron_src)
        self.assertIn('req_body', cron_src)
        self.assertIn("backend == 'mysql'", cron_src)

    def test_adds_must_reset_password_column(self):
        from flask import Flask
        from sqlalchemy import inspect, text

        from app import db

        mod = _load_ensure()
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(app)
        with app.app_context():
            db.session.execute(text(
                'CREATE TABLE rbac_users ('
                'id INTEGER PRIMARY KEY, '
                'username VARCHAR(64) NOT NULL, '
                'password_hash VARCHAR(255) NOT NULL, '
                'role VARCHAR(20) NOT NULL, '
                'is_active SMALLINT NOT NULL, '
                "create_time VARCHAR(25) NOT NULL DEFAULT '')"
            ))
            db.session.commit()
            cols_before = {c['name'] for c in inspect(db.engine).get_columns('rbac_users')}
            self.assertNotIn('must_reset_password', cols_before)
            self.assertNotIn('status_reason', cols_before)
            mod._ensure_rbac_users_columns()
            cols_after = {c['name'] for c in inspect(db.engine).get_columns('rbac_users')}
            self.assertIn('must_reset_password', cols_after)
            self.assertIn('status_reason', cols_after)
            mod._ensure_rbac_users_columns()
            cols_again = {c['name'] for c in inspect(db.engine).get_columns('rbac_users')}
            self.assertIn('must_reset_password', cols_again)
            self.assertIn('status_reason', cols_again)


class TestEnsureCronInfosColumns(unittest.TestCase):
    def test_adds_only_req_method_and_req_body_for_legacy_table(self):
        from types import SimpleNamespace
        from unittest.mock import patch

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
                {'name': 'last_operator_name'},
                {'name': 'last_operated_at'},
            ],
        )

        with patch.object(mod, 'db', fake_db), patch('sqlalchemy.inspect', return_value=fake_inspector):
            mod._ensure_cron_infos_columns()

        self.assertEqual(len(executed_sql), 2)
        sql_text = '\n'.join(executed_sql)
        self.assertIn('ALTER TABLE cron_infos ADD COLUMN req_method VARCHAR(10) DEFAULT', sql_text)
        self.assertIn('ALTER TABLE cron_infos ADD COLUMN req_body TEXT DEFAULT', sql_text)

    def test_does_nothing_when_columns_already_exist(self):
        from types import SimpleNamespace
        from unittest.mock import patch

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
                {'name': 'last_operator_name'},
                {'name': 'last_operated_at'},
            ],
        )

        with patch.object(mod, 'db', fake_db), patch('sqlalchemy.inspect', return_value=fake_inspector):
            mod._ensure_cron_infos_columns()

        self.assertEqual(executed_sql, [])

    def test_mysql_uses_text_without_default_for_req_body(self):
        from types import SimpleNamespace
        from unittest.mock import patch

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
                {'name': 'last_operator_name'},
                {'name': 'last_operated_at'},
            ],
        )

        with patch.object(mod, 'db', fake_db), patch('sqlalchemy.inspect', return_value=fake_inspector):
            mod._ensure_cron_infos_columns(backend='mysql')

        sql_text = '\n'.join(executed_sql)
        self.assertIn('ALTER TABLE cron_infos ADD COLUMN req_body TEXT', sql_text)
        self.assertNotIn("ALTER TABLE cron_infos ADD COLUMN req_body TEXT DEFAULT ''", sql_text)


if __name__ == '__main__':
    unittest.main()
