"""Status retry snapshots must not read expired ORM state after commit."""
import hashlib
import hmac
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from itsdangerous import URLSafeSerializer
from sqlalchemy import event
from sqlalchemy.orm.exc import StaleDataError

from app import db
from app.services import cron_status_apply as status
from tests import test_cron_edit_noop as fixture

FIELDS = ('run_date', 'day_of_week', 'day', 'hour', 'minute', 'second')


class TestStatusPostcommitSnapshot(unittest.TestCase):
    setUp = fixture.TestCronEditNoop.setUp
    tearDown = fixture.TestCronEditNoop.tearDown

    def test_legacy_digest_with_unicode_and_empty_values(self):
        values = dict(run_date='', day_of_week='周一', day=None, hour='2', minute='0', second='')
        old = hmac.new(b'test', json.dumps({k: values[k] or '' for k in FIELDS},
                                           sort_keys=True).encode(), hashlib.sha256).hexdigest()
        self.assertEqual(status.status_config(SimpleNamespace(**values)), old)
        self.assertEqual(status.status_config_snapshot(values), old)

    def test_expired_object_is_not_read_after_commit(self):
        expected = status.status_config(self.task)
        committed, reads, context = [], [], {}
        concrete = db.session()

        def mark(_session):
            committed.append(True)

        def reject_column_load(state):
            if committed and state.is_column_load:
                reads.append(True)
                raise RuntimeError('expired ORM read')

        event.listen(concrete, 'after_commit', mark)
        event.listen(concrete, 'do_orm_execute', reject_column_load)
        try:
            with patch.object(status, 'apply_status', return_value='已启动') as apply, \
                    patch('app.services.operation_log_service.record_operation'):
                result = status.save_status(self.task_id, 1, context=context)
            self.assertTrue(result[0])
            self.assertTrue(committed)
            self.assertEqual(reads, [])
            self.assertEqual(context['config'], expected)
            self.assertEqual(context['target'], 1)
            apply.assert_called_once()
        finally:
            event.remove(concrete, 'after_commit', mark)
            event.remove(concrete, 'do_orm_execute', reject_column_load)

    def test_digest_failure_rolls_back_before_commit(self):
        context = {}
        with patch.object(status, 'status_config_snapshot', side_effect=RuntimeError('SECRET')), \
                patch.object(status, 'apply_status') as apply:
            result = status.save_status(self.task_id, 1, context=context)
        self.assertFalse(result[0])
        self.assertNotIn('SECRET', result[1])
        self.assertEqual(context, {})
        self.assertEqual(db.session.get(fixture.CronInfos, self.task_id).status, 0)
        apply.assert_not_called()

    def test_real_jobstore_start_and_pause_without_expired_reads(self):
        from tests.test_cron_status_apply_d2 import TestStatusApplyD2

        with TestStatusApplyD2.scheduler(self) as api:
            for target in (1, 0):
                committed = []
                concrete = db.session()

                def mark(_session):
                    committed.append(True)

                def reject_column_load(state):
                    if committed and state.is_column_load:
                        raise RuntimeError('expired ORM read')

                event.listen(concrete, 'after_commit', mark)
                event.listen(concrete, 'do_orm_execute', reject_column_load)
                try:
                    context = {}
                    with patch('app.services.operation_log_service.record_operation'):
                        result = status.save_status(self.task_id, target, context=context)
                    self.assertTrue(result[0], result)
                    self.assertTrue(committed)
                    self.assertEqual(context['target'], target)
                    self.assertEqual(api.get_job('cron_%s' % self.task_id).next_run_time is None,
                                     target == 0)
                finally:
                    event.remove(concrete, 'after_commit', mark)
                    event.remove(concrete, 'do_orm_execute', reject_column_load)

    def test_commit_failure_never_returns_retry_context(self):
        context = {}
        with patch.object(db.session(), 'commit', side_effect=RuntimeError('SECRET')), \
                patch.object(status, 'apply_status') as apply:
            result = status.save_status(self.task_id, 1, context=context)
        self.assertFalse(result[0])
        self.assertIn('待核实', result[1])
        self.assertEqual(context, {})
        apply.assert_not_called()

    def test_retry_digest_failure_is_safe_and_does_not_write(self):
        context = {}
        with patch.object(status, 'status_config', side_effect=RuntimeError('SECRET')), \
                patch.object(status, 'apply_status') as apply:
            result = status.save_status(self.task_id, 0, expected_revision=1,
                                        expected_config='old-digest', context=context)
        self.assertFalse(result[0])
        self.assertNotIn('SECRET', result[1])
        self.assertEqual(context, {})
        self.assertEqual(db.session.get(fixture.CronInfos, self.task_id).status, 0)
        apply.assert_not_called()

    def test_commit_acknowledgement_lost_does_not_issue_retry(self):
        context = {}
        concrete = db.session()
        commit = concrete.commit

        def committed_then_raise():
            commit()
            raise RuntimeError('SECRET')

        with patch.object(concrete, 'commit', side_effect=committed_then_raise), \
                patch.object(status, 'apply_status') as apply:
            result = status.save_status(self.task_id, 1, context=context)
        self.assertFalse(result[0])
        self.assertIn('待核实', result[1])
        self.assertEqual(context, {})
        apply.assert_not_called()
        self.assertEqual(db.session.get(fixture.CronInfos, self.task_id).status, 1)

    def test_stale_error_during_commit_is_unknown(self):
        context = {}
        with patch.object(db.session(), 'commit', side_effect=StaleDataError('SECRET')), \
                patch.object(status, 'apply_status') as apply:
            result = status.save_status(self.task_id, 1, context=context)
        self.assertFalse(result[0])
        self.assertIn('待核实', result[1])
        self.assertEqual(context, {})
        apply.assert_not_called()

    def test_version_read_failure_keeps_committed_target_and_context(self):
        context = {}
        with patch('app.services.cron_edit_apply.current_version', side_effect=RuntimeError('SECRET')):
            result = status.save_status(self.task_id, 1, context=context)
        self.assertFalse(result[0])
        self.assertNotIn('SECRET', result[1])
        self.assertEqual(context['target'], 1)
        self.assertEqual(db.session.get(fixture.CronInfos, self.task_id).status, 1)

    def test_web_response_has_retry_token_without_postcommit_orm_read(self):
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess.update(is_login=True, user_id=1, username='op', role='operator', group_ids=[7])
        concrete = db.session()
        committed = []

        def mark(_session):
            committed.append(True)

        def reject_column_load(state):
            if committed and state.is_column_load:
                raise RuntimeError('expired ORM read')

        event.listen(concrete, 'after_commit', mark)
        event.listen(concrete, 'do_orm_execute', reject_column_load)
        try:
            with patch.object(status, 'apply_status', side_effect=status.EditWriteError('调度未确认')):
                response = client.post('/update_status', data={'id': self.task_id, 'status': '1'},
                                       headers={'X-Requested-With': 'XMLHttpRequest'})
            self.assertTrue(committed)
            body = response.get_json()
            self.assertEqual(body['errcode'], 1)
            token = body['result']['retry_token']
            data = URLSafeSerializer('test', salt='cron-status-retry-v1').loads(token)
            self.assertEqual((data['actor'], data['task'], data['target']), (1, self.task_id, 1))
            self.assertEqual(data['config'], status.status_config_snapshot(self.values))
        finally:
            event.remove(concrete, 'after_commit', mark)
            event.remove(concrete, 'do_orm_execute', reject_column_load)

        serializer = URLSafeSerializer('test', salt='cron-status-retry-v1')
        with patch.object(status, 'apply_status', return_value='已启动'):
            retry = client.post('/cron_status_apply', data={'id': self.task_id, 'status': '1',
                                                             'retry_token': token})
        self.assertEqual(retry.get_json()['errcode'], 0)
        altered = serializer.dumps(dict(data, actor=2))
        with patch.object(status, 'apply_status') as apply:
            denied = client.post('/cron_status_apply', data={'id': self.task_id, 'status': '1',
                                                              'retry_token': altered})
        self.assertEqual(denied.get_json()['errcode'], 1)
        apply.assert_not_called()

    def test_api_response_has_retry_header_without_postcommit_orm_read(self):
        from app.api import api

        self.app.register_blueprint(api, url_prefix='/api')
        client = self.app.test_client()
        concrete = db.session()
        committed = []

        def mark(_session):
            committed.append(True)

        def reject_column_load(state):
            if committed and state.is_column_load:
                raise RuntimeError('expired ORM read')

        event.listen(concrete, 'after_commit', mark)
        event.listen(concrete, 'do_orm_execute', reject_column_load)
        try:
            with patch('configs.configs', return_value=''), \
                    patch.object(status, 'apply_status', side_effect=status.EditWriteError('调度未确认')):
                response = client.post('/api/cron/status', data={'task_name': 'noop', 'status': '1'})
            self.assertTrue(committed)
            self.assertEqual(response.get_json()['errcode'], 1)
            token = response.headers['X-Cron-Status-Retry']
            data = URLSafeSerializer('test', salt='cron-status-api-retry-v1').loads(token)
            self.assertEqual((data['task'], data['target']), (self.task_id, 1))
            self.assertEqual(data['actor'], hmac.new(b'test', b'', hashlib.sha256).hexdigest())
            self.assertEqual(data['config'], status.status_config_snapshot(self.values))
        finally:
            event.remove(concrete, 'after_commit', mark)
            event.remove(concrete, 'do_orm_execute', reject_column_load)
