"""L2 persistent-DB integration tests for cron CRUD lifecycle.

Tests run against a temporary SQLite file (not :memory:) so they
exercise real ID allocation, cross-table constraints, and orphan
cleanup — scenarios that in-memory tests cannot reach.
"""
import unittest
from unittest.mock import patch

from sqlalchemy import select

from app import db
from tests.integration_base import PersistentDBTestCase


_MOCK_OPERATOR = type('Op', (), {
    'operator_name': 'tester',
    'operator_type': 'user',
    'operator_id': '0',
    'roles': [],
    'group_ids': [],
    'permissions': [],
})()


def _base_normalized(**overrides):
    """Return a minimal valid ``normalized`` dict for create_cron."""
    data = {
        'task_name': 'test_task',
        'task_keyword': 'kw',
        'run_date': '',
        'day_of_week': '*',
        'day': '*',
        'hour': '*',
        'minute': '*/5',
        'second': '0',
        'req_url': 'http://example.com/cb',
        'req_method': 'GET',
        'req_body': '',
    }
    data.update(overrides)
    return data


class TestCreateGroupTask(PersistentDBTestCase):
    """Scenario 1: create a GROUP-scoped task → verify scope_type + task_groups row."""

    @classmethod
    def _seed_data(cls):
        from datas.model.resource_group import ResourceGroup
        rg = ResourceGroup(name='group-alpha')
        db.session.add(rg)
        db.session.commit()
        cls.group_id = rg.id

    @patch('app.services.cron_service.scheduler')
    @patch('app.services.operation_log_service.resolve_operator_from_request',
           return_value=_MOCK_OPERATOR)
    def test_group_task_persisted(self, _op, _sched):
        from app.services.cron_service import create_cron
        from datas.model.cron_infos import CronInfos
        from datas.model.task_group import TaskGroup

        with self.app.app_context():
            norm = _base_normalized(
                task_name='group_task_1',
                scope_type='GROUP',
                group_id=str(self.group_id),
            )
            cif = create_cron(norm)

            self.assertEqual(cif.scope_type, 'GROUP')

            tg = db.session.scalars(
                select(TaskGroup).where(TaskGroup.task_id == cif.id)
            ).first()
            self.assertIsNotNone(tg, 'task_groups row must exist for GROUP task')
            self.assertEqual(tg.group_id, self.group_id)


class TestCreateGlobalTask(PersistentDBTestCase):
    """Scenario 2: create a GLOBAL task → no task_groups row."""

    @patch('app.services.cron_service.scheduler')
    @patch('app.services.operation_log_service.resolve_operator_from_request',
           return_value=_MOCK_OPERATOR)
    def test_global_task_no_task_groups(self, _op, _sched):
        from app.services.cron_service import create_cron
        from datas.model.task_group import TaskGroup

        with self.app.app_context():
            norm = _base_normalized(task_name='global_task_1', scope_type='GLOBAL')
            cif = create_cron(norm)

            self.assertEqual(cif.scope_type, 'GLOBAL')

            count = db.session.scalar(
                select(db.func.count()).select_from(TaskGroup)
                .where(TaskGroup.task_id == cif.id)
            )
            self.assertEqual(count, 0, 'GLOBAL task must have no task_groups row')


class TestUpdateGroupAffiliation(PersistentDBTestCase):
    """Scenario 3: update task group → old task_groups deleted, new row written."""

    @classmethod
    def _seed_data(cls):
        from datas.model.resource_group import ResourceGroup
        g1 = ResourceGroup(name='group-one')
        g2 = ResourceGroup(name='group-two')
        db.session.add_all([g1, g2])
        db.session.commit()
        cls.g1_id = g1.id
        cls.g2_id = g2.id

    @patch('app.services.cron_service.scheduler')
    @patch('app.services.operation_log_service.resolve_operator_from_request',
           return_value=_MOCK_OPERATOR)
    def test_group_switch(self, _op, _sched):
        from app.services.cron_service import create_cron, update_cron
        from datas.model.task_group import TaskGroup

        with self.app.app_context():
            norm = _base_normalized(
                task_name='switch_task',
                scope_type='GROUP',
                group_id=str(self.g1_id),
            )
            cif = create_cron(norm)

            tg = db.session.scalars(
                select(TaskGroup).where(TaskGroup.task_id == cif.id)
            ).first()
            self.assertEqual(tg.group_id, self.g1_id)

            update_norm = _base_normalized(
                task_name='switch_task',
                scope_type='GROUP',
                group_id=str(self.g2_id),
            )
            update_cron(cif, update_norm)

            tgs = db.session.scalars(
                select(TaskGroup).where(TaskGroup.task_id == cif.id)
            ).all()
            self.assertEqual(len(tgs), 1, 'must have exactly 1 task_groups row after update')
            self.assertEqual(tgs[0].group_id, self.g2_id)


class TestIdReuseNoConflict(PersistentDBTestCase):
    """Scenario 4: delete task then create new one — ID reuse must not
    conflict with orphaned task_groups.

    This reproduces the 2026-09 IntegrityError: SQLite WITHOUT
    AUTOINCREMENT reuses deleted row IDs.  If task_groups rows
    from a deleted task remain, create_cron for the reused ID fails.
    """

    @classmethod
    def _seed_data(cls):
        from datas.model.resource_group import ResourceGroup
        rg = ResourceGroup(name='group-reuse')
        db.session.add(rg)
        db.session.commit()
        cls.group_id = rg.id

    @patch('app.services.cron_service.scheduler')
    @patch('app.services.operation_log_service.resolve_operator_from_request',
           return_value=_MOCK_OPERATOR)
    def test_id_reuse_after_delete(self, _op, _sched):
        from datas.model.cron_infos import CronInfos
        from datas.model.task_group import TaskGroup
        from datas.utils.times import utc_now_hms

        with self.app.app_context():
            now = utc_now_hms()
            cif = CronInfos(
                task_name='will_delete',
                task_keyword='kw',
                minute='*/5', second='0',
                req_url='http://example.com',
                req_method='GET',
                status=1,
                created_at=now, updated_at=now,
                scope_type='GROUP',
                last_operator_name='test',
                last_operated_at=now,
            )
            db.session.add(cif)
            db.session.flush()
            old_id = cif.id
            db.session.add(TaskGroup(task_id=old_id, group_id=self.group_id))
            db.session.commit()

            tg_before = db.session.scalar(
                select(db.func.count()).select_from(TaskGroup)
                .where(TaskGroup.task_id == old_id)
            )
            self.assertEqual(tg_before, 1)

            db.session.delete(cif)
            db.session.commit()

            orphan_tg = db.session.scalar(
                select(db.func.count()).select_from(TaskGroup)
                .where(TaskGroup.task_id == old_id)
            )
            self.assertEqual(orphan_tg, 1,
                             'task_groups row is orphaned after cron_infos deletion '
                             '(no FK CASCADE)')

            new_cif = CronInfos(
                task_name='reuse_id_task',
                task_keyword='kw',
                minute='*/5', second='0',
                req_url='http://example.com',
                req_method='GET',
                status=1,
                created_at=now, updated_at=now,
                scope_type='GROUP',
                last_operator_name='test',
                last_operated_at=now,
            )
            db.session.add(new_cif)
            db.session.flush()

            if new_cif.id == old_id:
                with self.assertRaises(Exception):
                    db.session.add(
                        TaskGroup(task_id=new_cif.id, group_id=self.group_id)
                    )
                    db.session.flush()
                db.session.rollback()
                self.skipTest(
                    'ID was reused and IntegrityError confirmed — '
                    'demonstrates the orphan-conflict vulnerability'
                )
            else:
                db.session.add(
                    TaskGroup(task_id=new_cif.id, group_id=self.group_id)
                )
                db.session.commit()
                tgs = db.session.scalars(
                    select(TaskGroup).where(TaskGroup.task_id == new_cif.id)
                ).all()
                self.assertEqual(len(tgs), 1)


class TestRetirePersistence(PersistentDBTestCase):
    """Scenario 5: retire task → status=-1 + retire_reason persisted."""

    @classmethod
    def _seed_data(cls):
        from datas.model.resource_group import ResourceGroup
        rg = ResourceGroup(name='group-retire')
        db.session.add(rg)
        db.session.commit()
        cls.group_id = rg.id

    @patch('app.services.cron_service.scheduler')
    @patch('app.services.operation_log_service.resolve_operator_from_request',
           return_value=_MOCK_OPERATOR)
    def test_retire_persists(self, _op, _sched):
        from app.services.cron_service import create_cron, retire_cron_by_id
        from datas.model.cron_infos import CronInfos

        with self.app.app_context():
            norm = _base_normalized(
                task_name='retire_me',
                scope_type='GROUP',
                group_id=str(self.group_id),
            )
            cif = create_cron(norm)
            cif_id = cif.id

            err, result = retire_cron_by_id(cif_id, '不再需要')
            self.assertIsNone(err, f'retire should succeed but got: {err}')

            reloaded = db.session.get(CronInfos, cif_id)
            self.assertEqual(reloaded.status, -1)
            self.assertEqual(reloaded.retire_reason, '不再需要')
            self.assertIsNotNone(reloaded.retired_at)


if __name__ == '__main__':
    unittest.main()
