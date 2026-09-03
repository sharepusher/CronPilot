"""L2 persistent-DB integration tests for API /api/cron scope persistence.

Verifies that scope_type and group_id survive the full pipeline:
  _apply_api_scope → validate_cron_form → upsert_cron_by_task_name → DB

B-15 (upsert_cron_by_task_name dropping scope fields) has been fixed
by merging scope_type/group_id back from datas after validate_cron_form.
All 5 tests should now pass.
"""
import unittest
from unittest.mock import patch

from flask import request as flask_request
from sqlalchemy import select

from app import db
from app.api.views import _apply_api_scope
from app.services.cron_service import upsert_cron_by_task_name
from tests.integration_base import PersistentDBTestCase

_MOCK_OPERATOR = type('Op', (), {
    'operator_name': 'api-tester',
    'operator_type': 'api',
    'operator_id': '0',
    'roles': [],
    'group_ids': [],
    'permissions': ['cron:write', 'cron:read'],
})()


def _cron_data(**overrides):
    """Minimal valid cron form data."""
    d = {
        'task_name': 'test_task',
        'task_keyword': 'test',
        'minute': '*/5',
        'req_url': 'http://example.com/cb',
        'req_method': 'GET',
    }
    d.update(overrides)
    return d


class _ScopeTestBase(PersistentDBTestCase):
    """Common setup: seed resource groups."""

    @classmethod
    def _seed_data(cls):
        from datas.model.resource_group import ResourceGroup
        g1 = ResourceGroup(name='team-alpha')
        g2 = ResourceGroup(name='team-beta')
        db.session.add_all([g1, g2])
        db.session.commit()
        cls.g1_id = g1.id
        cls.g2_id = g2.id

    def _run_pipeline(self, form_data, scope):
        """Run the full scope + upsert pipeline in a request context.

        Returns (scope_err, upsert_err, cif_id).
        cif_id is the primary key (int) rather than the ORM object,
        to avoid DetachedInstanceError after the request context exits.
        """
        with self.app.test_request_context('/api/cron', method='POST'):
            flask_request._api_scope = scope

            scope_err = _apply_api_scope(form_data)
            if scope_err:
                return scope_err, None, None

            cron_config = {'is_dev': '0'}
            is_dev = 0

            with patch('app.services.cron_service.scheduler'), \
                 patch('app.services.operation_log_service.resolve_operator_from_request',
                       return_value=_MOCK_OPERATOR):
                upsert_err, cif = upsert_cron_by_task_name(
                    form_data, is_dev, cron_config
                )

            cif_id = cif.id if cif else None
            return None, upsert_err, cif_id


class TestApiGlobalScope(_ScopeTestBase):
    """Admin scope, no group_name → GLOBAL task."""

    def test_admin_global_task(self):
        from datas.model.cron_infos import CronInfos
        from datas.model.task_group import TaskGroup

        data = _cron_data(task_name='api_global_1')
        scope_err, upsert_err, cif_id = self._run_pipeline(
            data, scope={'role': 'admin'}
        )

        self.assertIsNone(scope_err)
        self.assertIsNone(upsert_err)
        self.assertIsNotNone(cif_id)

        with self.app.app_context():
            loaded = db.session.get(CronInfos, cif_id)
            self.assertEqual(loaded.scope_type, 'GLOBAL')

            count = db.session.scalar(
                select(db.func.count()).select_from(TaskGroup)
                .where(TaskGroup.task_id == cif_id)
            )
            self.assertEqual(count, 0, 'GLOBAL task must have no task_groups')


class TestApiGroupScopeAdmin(_ScopeTestBase):
    """Admin scope with group_name → GROUP task."""

    def test_admin_group_task(self):
        from datas.model.cron_infos import CronInfos
        from datas.model.task_group import TaskGroup

        data = _cron_data(task_name='api_group_admin', group_name='team-alpha')
        scope_err, upsert_err, cif_id = self._run_pipeline(
            data, scope={'role': 'admin'}
        )

        self.assertIsNone(scope_err)
        self.assertIsNone(upsert_err)
        self.assertIsNotNone(cif_id)

        with self.app.app_context():
            loaded = db.session.get(CronInfos, cif_id)
            self.assertEqual(loaded.scope_type, 'GROUP',
                             'B-15: scope_type should be GROUP')

            tg = db.session.scalars(
                select(TaskGroup).where(TaskGroup.task_id == cif_id)
            ).first()
            self.assertIsNotNone(tg, 'B-15: task_groups row should exist')
            self.assertEqual(tg.group_id, self.g1_id)


class TestApiSingleGroupOperator(_ScopeTestBase):
    """Single-group operator, no group_name → auto-assign."""

    def test_single_group_auto_assign(self):
        from datas.model.cron_infos import CronInfos
        from datas.model.task_group import TaskGroup

        data = _cron_data(task_name='api_auto_group')
        scope_err, upsert_err, cif_id = self._run_pipeline(
            data, scope={
                'role': 'user',
                'user_role': 'operator',
                'username': 'op1',
                'group_ids': [self.g1_id],
            }
        )

        self.assertIsNone(scope_err)
        self.assertIsNone(upsert_err)
        self.assertIsNotNone(cif_id)

        with self.app.app_context():
            loaded = db.session.get(CronInfos, cif_id)
            self.assertEqual(loaded.scope_type, 'GROUP')

            tg = db.session.scalars(
                select(TaskGroup).where(TaskGroup.task_id == cif_id)
            ).first()
            self.assertIsNotNone(tg)
            self.assertEqual(tg.group_id, self.g1_id)


class TestApiMultiGroupNoName(_ScopeTestBase):
    """Multi-group operator without group_name → error."""

    def test_multi_group_must_specify(self):
        data = _cron_data(task_name='api_multi_no_name')
        scope_err, upsert_err, cif = self._run_pipeline(
            data, scope={
                'role': 'user',
                'user_role': 'operator',
                'username': 'op_multi',
                'group_ids': [self.g1_id, self.g2_id],
            }
        )

        self.assertIsNotNone(scope_err,
                             'multi-group without group_name must fail')
        self.assertIn('group_name', scope_err)


class TestApiOperatorOutOfScope(_ScopeTestBase):
    """Operator specifying a group they don't belong to → error."""

    def test_out_of_scope_rejected(self):
        data = _cron_data(task_name='api_out_of_scope', group_name='team-beta')
        scope_err, upsert_err, cif = self._run_pipeline(
            data, scope={
                'role': 'user',
                'user_role': 'operator',
                'username': 'op_alpha_only',
                'group_ids': [self.g1_id],
            }
        )

        self.assertIsNotNone(scope_err,
                             'out-of-scope group must be rejected')


if __name__ == '__main__':
    unittest.main()
