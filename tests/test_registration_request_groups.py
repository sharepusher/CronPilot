# -*- coding: utf-8 -*-
import importlib.util
import os
import unittest

from flask import Flask
from sqlalchemy import event, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app import db
from app.rbac.registration_requested_scope import (
    normalize_registration_requested_scope,
)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def _load_ensure():
    path = os.path.join(ROOT, 'scripts', 'ensure_business_tables.py')
    spec = importlib.util.spec_from_file_location(
        'ensure_business_tables_registration_groups_test', path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app


class TestRequestedScopeNormalizer(unittest.TestCase):
    def test_concrete_groups_are_trimmed_sorted_and_deduplicated(self):
        result = normalize_registration_requested_scope(
            'viewer', '2, 1,2', {1, 2},
        )
        self.assertTrue(result['ok'])
        self.assertEqual(result['kind'], 'concrete')
        self.assertEqual(result['group_ids'], (1, 2))
        self.assertTrue(result['normalized'])

    def test_global_requires_admin_and_cannot_mix_specific_groups(self):
        allowed = normalize_registration_requested_scope(
            'admin', '__ALL__', {1},
        )
        denied_role = normalize_registration_requested_scope(
            'viewer', '__ALL__', {1},
        )
        denied_mix = normalize_registration_requested_scope(
            'admin', '__ALL__,1', {1},
        )
        self.assertEqual(allowed['kind'], 'global')
        self.assertEqual(denied_role['reason'], 'global_requires_admin')
        self.assertEqual(
            denied_mix['reason'], 'global_and_specific_groups_mixed',
        )

    def test_invalid_and_missing_groups_fail_closed(self):
        cases = [
            ('', 'groups_required'),
            ('1,,2', 'empty_group_token'),
            ('abc', 'invalid_group_id'),
            ('0', 'invalid_group_id'),
            ('2', 'group_not_found'),
        ]
        for raw, reason in cases:
            with self.subTest(raw=raw):
                result = normalize_registration_requested_scope(
                    'viewer', raw, {1},
                )
                self.assertFalse(result['ok'])
                self.assertEqual(result['reason'], reason)


class TestRegistrationRequestGroupMigration(unittest.TestCase):
    def setUp(self):
        self.app = _make_app()
        self.ensure = _load_ensure()
        with self.app.app_context():
            from datas.model.rbac_registration_request import (  # noqa: F401
                RbacRegistrationRequest,
            )
            from datas.model.rbac_registration_request_group import (  # noqa: F401
                RbacRegistrationRequestGroup,
            )
            from datas.model.resource_group import ResourceGroup  # noqa: F401
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _add_group(self, group_id):
        from datas.model.resource_group import ResourceGroup

        db.session.add(ResourceGroup(
            id=group_id,
            name='group-%s' % group_id,
            description='',
            create_time=0,
        ))

    def _add_request(self, request_id, role, group_ids):
        from datas.model.rbac_registration_request import RbacRegistrationRequest

        username = 'request-%s' % request_id
        db.session.add(RbacRegistrationRequest(
            id=request_id,
            email='%s@example.invalid' % username,
            username=username,
            password_hash='not-used',
            role=role,
            group_ids=group_ids,
            job_title='qa',
            nickname=username,
            reason='migration test',
            status='approved',
            create_time=0,
            is_reactivation=0,
        ))

    def test_model_constraint_and_indexes(self):
        from datas.model.rbac_registration_request_group import (
            RbacRegistrationRequestGroup,
        )

        with self.app.app_context():
            indexes = {
                item['name']
                for item in inspect(db.engine).get_indexes(
                    'rbac_registration_request_groups'
                )
            }
            self.assertIn('ix_reg_req_groups_group_req', indexes)
            db.session.add(RbacRegistrationRequestGroup(
                registration_request_id=1, group_id=1,
            ))
            db.session.commit()
            db.session.add(RbacRegistrationRequestGroup(
                registration_request_id=1, group_id=1,
            ))
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_schema_compiles_for_mysql(self):
        from sqlalchemy.dialects import mysql
        from sqlalchemy.schema import CreateIndex, CreateTable

        from datas.model.rbac_registration_request_group import (
            RbacRegistrationRequestGroup,
        )

        table = RbacRegistrationRequestGroup.__table__
        ddl = str(CreateTable(table).compile(dialect=mysql.dialect()))
        indexes = ' '.join(
            str(CreateIndex(index).compile(dialect=mysql.dialect()))
            for index in table.indexes
        )
        self.assertIn('registration_request_id INTEGER NOT NULL', ddl)
        self.assertIn('uq_reg_req_groups_req_group', ddl)
        self.assertIn('ix_reg_req_groups_group_req', indexes)

    def test_first_backfill_and_repeat_are_idempotent(self):
        from datas.model.rbac_registration_request_group import (
            RbacRegistrationRequestGroup,
        )

        with self.app.app_context():
            for group_id in (1, 2, 3):
                self._add_group(group_id)
            self._add_request(1, 'viewer', '1,2')
            self._add_request(2, 'admin', '__ALL__')
            self._add_request(3, 'admin', '2,3')
            db.session.commit()

            self.ensure._ensure_rbac_registration_request_groups()
            self.ensure._ensure_rbac_registration_request_groups()

            pairs = set(db.session.execute(select(
                RbacRegistrationRequestGroup.registration_request_id,
                RbacRegistrationRequestGroup.group_id,
            )).all())
            self.assertEqual(pairs, {(1, 1), (1, 2), (3, 2), (3, 3)})
            flag = db.session.execute(text(
                'SELECT COUNT(*) FROM cp_schema_flags WHERE flag_name = :flag'
            ), {
                'flag': self.ensure.REGISTRATION_REQUEST_GROUPS_FLAG,
            }).scalar_one()
            self.assertEqual(flag, 1)
            cutover_flag = db.session.execute(text(
                'SELECT COUNT(*) FROM cp_schema_flags WHERE flag_name = :flag'
            ), {
                'flag': self.ensure.REGISTRATION_REQUEST_GROUPS_CUTOVER_FLAG,
            }).scalar_one()
            self.assertEqual(cutover_flag, 1)

    def test_existing_base_flag_gets_one_final_sync_before_cutover(self):
        """B/D 已完成的环境在首次 E1 启动时只允许最后一次补齐。"""
        from datas.model.rbac_registration_request_group import (
            RbacRegistrationRequestGroup,
        )

        with self.app.app_context():
            self._add_group(1)
            self._add_request(1, 'viewer', '1')
            db.session.execute(text(
                'CREATE TABLE cp_schema_flags ('
                'flag_name VARCHAR(64) PRIMARY KEY, applied_at BIGINT NOT NULL)'
            ))
            db.session.execute(text(
                'INSERT INTO cp_schema_flags (flag_name, applied_at) '
                'VALUES (:flag, 1)'
            ), {'flag': self.ensure.REGISTRATION_REQUEST_GROUPS_FLAG})
            db.session.commit()

            self.ensure._ensure_rbac_registration_request_groups()

            pairs = set(db.session.execute(select(
                RbacRegistrationRequestGroup.registration_request_id,
                RbacRegistrationRequestGroup.group_id,
            )).all())
            self.assertEqual(pairs, {(1, 1)})
            cutover = db.session.execute(text(
                'SELECT COUNT(*) FROM cp_schema_flags WHERE flag_name = :flag'
            ), {
                'flag': self.ensure.REGISTRATION_REQUEST_GROUPS_CUTOVER_FLAG,
            }).scalar_one()
            self.assertEqual(cutover, 1)

    def test_verify_only_repeat_emits_no_relation_dml(self):
        """切读标记存在后，完全一致的启动只读对账，不执行关联表 DML。"""
        with self.app.app_context():
            self._add_group(1)
            self._add_request(1, 'viewer', '1')
            db.session.commit()
            self.ensure._ensure_rbac_registration_request_groups()

            statements = []

            def capture(_conn, _cursor, statement, _params, _ctx, _many):
                normalized = ' '.join(statement.lower().split())
                if 'rbac_registration_request_groups' in normalized:
                    statements.append(normalized)

            event.listen(db.engine, 'before_cursor_execute', capture)
            try:
                self.ensure._ensure_rbac_registration_request_groups()
            finally:
                event.remove(db.engine, 'before_cursor_execute', capture)

            relation_dml = [
                statement for statement in statements
                if statement.startswith(('insert ', 'update ', 'delete '))
            ]
            self.assertEqual(relation_dml, [])

    def test_invalid_rows_receive_no_partial_backfill(self):
        from datas.model.rbac_registration_request_group import (
            RbacRegistrationRequestGroup,
        )

        with self.app.app_context():
            self._add_group(1)
            self._add_request(1, 'viewer', '1,999')
            self._add_request(2, 'viewer', '1,abc')
            self._add_request(3, 'viewer', '__ALL__')
            db.session.commit()

            self.ensure._ensure_rbac_registration_request_groups()

            count = db.session.scalar(
                select(db.func.count()).select_from(
                    RbacRegistrationRequestGroup
                )
            )
            self.assertEqual(count, 0)

    def test_cutover_refuses_missing_relation_without_repair(self):
        with self.app.app_context():
            self._add_group(1)
            self._add_request(1, 'viewer', '1')
            db.session.commit()
            self.ensure._ensure_rbac_registration_request_groups()
            db.session.execute(text(
                'DELETE FROM rbac_registration_request_groups'
            ))
            db.session.commit()

            with self.assertRaisesRegex(RuntimeError, 'drift after read cutover'):
                self.ensure._ensure_rbac_registration_request_groups()
            count = db.session.execute(text(
                'SELECT COUNT(*) FROM rbac_registration_request_groups'
            )).scalar_one()
            self.assertEqual(count, 0)

    def test_dual_written_request_after_cutover_verifies_without_repair(self):
        from datas.model.rbac_registration_request_group import (
            RbacRegistrationRequestGroup,
        )

        with self.app.app_context():
            self._add_group(1)
            self._add_request(1, 'viewer', '1')
            db.session.commit()
            self.ensure._ensure_rbac_registration_request_groups()

            self._add_request(2, 'viewer', '1')
            db.session.add(RbacRegistrationRequestGroup(
                registration_request_id=2,
                group_id=1,
            ))
            db.session.commit()
            self.ensure._ensure_rbac_registration_request_groups()

            pairs = set(db.session.execute(select(
                RbacRegistrationRequestGroup.registration_request_id,
                RbacRegistrationRequestGroup.group_id,
            )).all())
            self.assertEqual(pairs, {(1, 1), (2, 1)})

    def test_cutover_refuses_parent_only_request(self):
        with self.app.app_context():
            self._add_group(1)
            self._add_request(1, 'viewer', '1')
            db.session.commit()
            self.ensure._ensure_rbac_registration_request_groups()
            self._add_request(2, 'viewer', '1')
            db.session.commit()

            with self.assertRaisesRegex(RuntimeError, 'drift after read cutover'):
                self.ensure._ensure_rbac_registration_request_groups()
            count = db.session.execute(text(
                'SELECT COUNT(*) FROM rbac_registration_request_groups'
            )).scalar_one()
            self.assertEqual(count, 1)

    def test_cutover_refuses_extra_and_orphan_relations_without_repair(self):
        from datas.model.rbac_registration_request_group import (
            RbacRegistrationRequestGroup,
        )

        with self.app.app_context():
            for group_id in (1, 2):
                self._add_group(group_id)
            self._add_request(1, 'viewer', '1')
            db.session.commit()
            self.ensure._ensure_rbac_registration_request_groups()

            for request_id, group_id in ((1, 2), (999, 1)):
                with self.subTest(request_id=request_id, group_id=group_id):
                    db.session.add(RbacRegistrationRequestGroup(
                        registration_request_id=request_id,
                        group_id=group_id,
                    ))
                    db.session.commit()
                    with self.assertRaisesRegex(
                        RuntimeError, 'drift after read cutover',
                    ):
                        self.ensure._ensure_rbac_registration_request_groups()
                    row = db.session.query(
                        RbacRegistrationRequestGroup
                    ).filter_by(
                        registration_request_id=request_id,
                        group_id=group_id,
                    ).one_or_none()
                    self.assertIsNotNone(row)
                    db.session.delete(row)
                    db.session.commit()

    def test_insert_failure_rolls_back_and_does_not_write_flag(self):
        with self.app.app_context():
            self._add_group(1)
            self._add_request(1, 'viewer', '1')
            db.session.commit()
            db.session.execute(text(
                'CREATE TRIGGER fail_registration_group_insert '
                'BEFORE INSERT ON rbac_registration_request_groups '
                "BEGIN SELECT RAISE(ABORT, 'injected relation failure'); END"
            ))
            db.session.commit()

            with self.assertRaises(Exception):
                self.ensure._ensure_rbac_registration_request_groups()

            flag = db.session.execute(text(
                'SELECT COUNT(*) FROM cp_schema_flags WHERE flag_name = :flag'
            ), {
                'flag': self.ensure.REGISTRATION_REQUEST_GROUPS_FLAG,
            }).scalar_one()
            relation_count = db.session.execute(text(
                'SELECT COUNT(*) FROM rbac_registration_request_groups'
            )).scalar_one()
            self.assertEqual(flag, 0)
            cutover_flag = db.session.execute(text(
                'SELECT COUNT(*) FROM cp_schema_flags WHERE flag_name = :flag'
            ), {
                'flag': self.ensure.REGISTRATION_REQUEST_GROUPS_CUTOVER_FLAG,
            }).scalar_one()
            self.assertEqual(cutover_flag, 0)
            self.assertEqual(relation_count, 0)


if __name__ == '__main__':
    unittest.main()
