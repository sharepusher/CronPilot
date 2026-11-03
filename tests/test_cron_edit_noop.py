"""验证无变更的实际 SQL/事务/外部副作用，以及真实变化不被误吞。"""
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from sqlalchemy import event, select

from app import db
from app.services.cron_edit_noop import cron_edit_is_noop
from app.services.cron_service import edit_cron_web, update_cron, upsert_cron_by_task_name
from datas.model.cron_infos import CronInfos
from datas.model.operation_log import OperationLog
from datas.model.rbac_user import RbacUser
from datas.model.resource_group import ResourceGroup
from datas.model.tag import Tag
from datas.model.task_group import TaskGroup
from datas.model.task_tag import TaskTag
from datas.model.user_group import UserGroup


class TestCronEditNoop(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.app = Flask(__name__, template_folder=str(root / 'app/templates'))
        self.app.config.update(TESTING=True, SECRET_KEY='test',
                               SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
                               SQLALCHEMY_TRACK_MODIFICATIONS=False,
                               CRON_CONFIG={'is_dev': '0'})
        db.init_app(self.app)
        from app.main import main
        self.app.register_blueprint(main)
        self.context = self.app.test_request_context('/cron_edit', method='POST')
        self.context.push()
        db.create_all()
        self.values = dict(task_name='noop', task_keyword='original', run_date='',
                           day_of_week='', day='', hour='1', minute='0', second='',
                           req_url='https://example.invalid/task', req_method='GET',
                           req_body='', timeout_sec=None)
        self.task = CronInfos(**self.values, status=0, scope_type='GROUP',
                              created_at=1, updated_at=1, last_operator_name='old',
                              last_operated_at=1)
        db.session.add_all([self.task, ResourceGroup(id=7, name='group'),
                            Tag(id=1, name='Alpha', group_id=7),
                            RbacUser(id=1, username='op', password_hash='test', role='operator',
                                     is_active=1, auth_version=0)])
        db.session.flush()
        db.session.add_all([TaskGroup(task_id=self.task.id, group_id=7),
                            TaskTag(task_id=self.task.id, tag_id=1),
                            UserGroup(user_id=1, group_id=7)])
        db.session.commit()
        self.task_id = self.task.id
        self.normalized = dict(self.values, scope_type='GROUP', group_id=7, tag_names=['Alpha'])
        self.raw = dict(self.normalized, timeout_sec='', ds_ms='2')
        self.sql = []

        def capture(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().split()[0].upper() in ('UPDATE', 'DELETE', 'INSERT'):
                self.sql.append(statement)

        self.capture = capture
        event.listen(db.engine, 'before_cursor_execute', capture)

    def tearDown(self):
        event.remove(db.engine, 'before_cursor_execute', self.capture)
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def assert_noop(self, action):
        self.sql.clear()
        with patch.object(db.session, 'commit', wraps=db.session.commit) as commit, \
                patch('app.services.cron_service.register_cron_job') as register, \
                patch('app.services.cron_service.scheduler') as scheduler:
            result = action()
        self.assertEqual(self.sql, [])
        commit.assert_not_called()
        register.assert_not_called()
        self.assertEqual(scheduler.mock_calls, [])
        self.assertEqual((self.task.updated_at, self.task.last_operator_name,
                          self.task.last_operated_at), (1, 'old', 1))
        self.assertEqual(list(db.session.scalars(select(OperationLog))), [])
        return result

    def test_direct_service_preserves_model_return_and_zero_side_effects(self):
        result = self.assert_noop(lambda: update_cron(self.task, self.normalized))
        self.assertIs(result, self.task)

    def test_web_noop_skips_dynamic_validation_and_preserves_legacy_tuple(self):
        with patch('app.services.cron_service.validate_cron_form', side_effect=AssertionError('dynamic')):
            result = self.assert_noop(lambda: edit_cron_web(self.raw, 0, {}, self.task_id))
        self.assertEqual(result, (None, None))

    def test_explicit_outcome(self):
        result = self.assert_noop(lambda: edit_cron_web(
            self.raw, 0, {}, self.task_id, return_outcome=True))
        self.assertEqual(result, (None, None, 'no_change'))

    def test_api_omitted_scope_and_tags_keep_existing_relations(self):
        raw = dict(self.values, timeout_sec='')
        with patch('app.services.cron_service.validate_cron_form', side_effect=AssertionError('DNS')):
            result = self.assert_noop(lambda: upsert_cron_by_task_name(raw, 0, {}))
        self.assertEqual(result, (None, self.task))

    def test_tag_duplicates_case_and_order_noop(self):
        data = dict(self.raw, tag_names=[' alpha ', 'ALPHA'])
        self.assertEqual(self.assert_noop(lambda: edit_cron_web(
            data, 0, {}, self.task_id)), (None, None))

    def test_expired_unchanged_one_shot_has_no_dynamic_validation(self):
        self.task.run_date = '2000-01-01 01:00'
        db.session.commit()
        self.raw.update(run_date=self.task.run_date, ds_ms='1')
        result = self.assert_noop(lambda: edit_cron_web(self.raw, 0, {}, self.task_id))
        self.assertEqual(result, (None, None))

    def test_every_field_and_command_change_is_not_noop(self):
        changes = dict(task_keyword='new', task_name='new', run_date='2035-01-01 01:00',
                       day_of_week='mon', day='2', hour='2', minute='5', second='0',
                       req_url='https://example.invalid/other', req_method='POST',
                       req_body='{}', timeout_sec=5, group_id=8, tag_names=[])
        for name, value in changes.items():
            with self.subTest(field=name):
                self.assertFalse(cron_edit_is_noop(self.task, dict(self.normalized, **{name: value})))
        self.assertFalse(cron_edit_is_noop(self.task, self.normalized, True))
        self.assertEqual(self.sql, [])

    def test_invalid_timeout_and_body_do_not_reach_writes(self):
        for fields in ({'timeout_sec': 'no'}, {'req_body': 'not JSON'}):
            with self.subTest(fields=fields):
                result = self.assert_noop(lambda: edit_cron_web(
                    dict(self.raw, **fields), 0, {}, self.task_id))
                self.assertIsNotNone(result[0])

    def test_legacy_group_only_input_is_not_swallowed(self):
        normalized = dict(self.values, group_id=8)
        self.assertFalse(cron_edit_is_noop(self.task, normalized))

    def test_read_only_comparison_does_not_flush_unrelated_pending_work(self):
        unrelated = ResourceGroup(name='pending-owned-by-caller')
        db.session.add(unrelated)
        self.sql.clear()
        self.assertTrue(cron_edit_is_noop(self.task, self.normalized))
        self.assertEqual(self.sql, [])
        self.assertIn(unrelated, db.session.new)

    def test_real_change_still_runs_full_validation(self):
        with patch('app.services.cron_service.validate_cron_form',
                   return_value=('DNS rejected', None, 'req_url')) as validate:
            result = self.assert_noop(lambda: edit_cron_web(
                dict(self.raw, task_keyword='new'), 0, {}, self.task_id))
        validate.assert_called_once()
        self.assertEqual(result, ('DNS rejected', 'req_url'))

    def test_description_change_writes_without_scheduling(self):
        with patch('app.services.cron_service.register_cron_job') as register, \
                patch('app.services.cron_service.scheduler'):
            result = update_cron(self.task, dict(self.normalized, task_keyword='new'))
        self.assertIs(result, self.task)
        self.assertEqual(self.task.task_keyword, 'new')
        self.assertTrue(self.sql)
        register.assert_not_called()

    def test_api_update_description_without_scheduler(self):
        with patch('app.services.cron_validator.validate_trigger_url', return_value=(True, '')), \
                patch('app.services.cron_service.register_cron_job', side_effect=RuntimeError('unavailable')) as reg, \
                patch('app.services.cron_service.scheduler') as sched:
            error, task = upsert_cron_by_task_name(dict(self.values, task_keyword='api update', timeout_sec=''), 0, {})
        self.assertIsNone(error)
        self.assertEqual(task.task_keyword, 'api update')
        reg.assert_not_called()
        self.assertEqual(sched.mock_calls, [])

    def test_shared_schedule_change_still_schedules(self):
        with patch('app.services.cron_service.register_cron_job') as reg, \
                patch('app.services.cron_service.scheduler') as sched, \
                patch('app.services.cron_edit_apply.scheduler', sched):
            update_cron(self.task, dict(self.normalized, minute='5', task_keyword='mixed'))
        reg.assert_called_once()
        sched.pause_job.assert_not_called()

    def test_anomalous_group_associations_rejected_without_dml(self):
        db.session.add(TaskGroup(task_id=self.task_id, group_id=8))
        db.session.commit()
        result = self.assert_noop(lambda: edit_cron_web(self.raw, 0, {}, self.task_id))
        self.assertIn('关联异常', result[0])

    def test_wrong_tag_namespace_rejected(self):
        db.session.get(Tag, 1).group_id = 8
        db.session.commit()
        result = self.assert_noop(lambda: edit_cron_web(self.raw, 0, {}, self.task_id))
        self.assertIn('标签关联异常', result[0])

    def test_global_and_running_noop(self):
        db.session.query(TaskGroup).delete()
        db.session.query(TaskTag).delete()
        self.task.scope_type = 'GLOBAL'
        self.task.status = 1
        db.session.commit()
        self.normalized.update(scope_type='GLOBAL', group_id=None, tag_names=[])
        self.assert_noop(lambda: update_cron(self.task, self.normalized))

    def test_route_ajax_and_native_noop(self):
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess.update(is_login=True, username='op', role='operator', group_ids=[7], user_id=1)
        raw = dict(self.raw, tags='Alpha')
        from app.services.cron_edit_concurrency import build_task_edit_snapshot
        raw['edit_snapshot'] = build_task_edit_snapshot(1, self.task)
        raw.pop('tag_names')
        with patch('app.main.views.authorize_resource', return_value=None):
            response = self.assert_noop(lambda: client.post(
                '/cron_edit?id=%s' % self.task_id, data=raw,
                headers={'X-Requested-With': 'XMLHttpRequest'}))
            body = response.get_json()
            self.assertEqual(body['data']['outcome'], 'no_change')
            self.assertEqual(body['errcode'], 0)
            self.assertFalse(body.get('url'))
            response = self.assert_noop(lambda: client.post(
                '/cron_edit?id=%s' % self.task_id, data=raw))
        self.assertEqual(response.status_code, 302)
        self.assertIn('outcome=no_change', response.location)


if __name__ == '__main__':
    unittest.main()
