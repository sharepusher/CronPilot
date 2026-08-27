# -*- coding:utf-8 -*-
import json
import os
import unittest
from unittest.mock import patch

from flask import Flask
from sqlalchemy import select

from app import register_hms_filters
from app.main import main as main_blueprint
from app.services.operation_log_service import (
    OperatorContext,
    build_cron_diff,
    format_detail_summary,
    operation_action_label,
    resolve_operator_from_request,
    trim_operation_logs,
)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class TestOperationLogHelpers(unittest.TestCase):
    def test_action_label(self):
        self.assertEqual(operation_action_label('create_cron'), '创建任务')
        self.assertEqual(operation_action_label('unknown_x'), 'unknown_x')
        self.assertEqual(operation_action_label('toggle_status'), '启动/暂停')
        resume = json.dumps({'status': {'old': 0, 'new': 1}})
        pause = json.dumps({'status': {'old': 1, 'new': 0}})
        self.assertEqual(operation_action_label('toggle_status', resume), '启动任务')
        self.assertEqual(operation_action_label('toggle_status', pause), '暂停任务')

    def test_build_cron_diff(self):
        diff = build_cron_diff({'hour': '9', 'minute': '0'}, {'hour': '10', 'minute': '0'})
        self.assertEqual(diff, {'hour': {'old': '9', 'new': '10'}})

    def test_format_detail_summary_update(self):
        detail = json.dumps({'hour': {'old': '9', 'new': '10'}}, ensure_ascii=False)
        self.assertIn('hour', format_detail_summary('update_cron', detail))
        self.assertIn('9→10', format_detail_summary('update_cron', detail))

    def test_format_detail_summary_toggle(self):
        resume = json.dumps({'status': {'old': 0, 'new': 1}}, ensure_ascii=False)
        pause = json.dumps({'status': {'old': 1, 'new': 0}}, ensure_ascii=False)
        self.assertEqual(format_detail_summary('toggle_status', resume), '启动：已暂停 → 运行中')
        self.assertEqual(format_detail_summary('toggle_status', pause), '暂停：运行中 → 已暂停')


class TestResolveOperator(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.secret_key = 'test'
        app.config['TESTING'] = True
        self.app = app

    def test_no_request_is_system(self):
        with self.app.app_context():
            op = resolve_operator_from_request()
            self.assertEqual(op.operator_type, 'system')
            self.assertEqual(op.operator_name, '系统')

    def test_web_session_user(self):
        with self.app.test_request_context('/cron_add', method='POST'):
            from flask import session
            session['user_id'] = 4
            session['username'] = 'alice'
            session['role'] = 'admin'
            op = resolve_operator_from_request()
            self.assertEqual(op.operator_type, 'user')
            self.assertEqual(op.operator_id, '4')
            self.assertEqual(op.operator_name, 'alice')
            self.assertEqual(op.roles, ['admin'])

    def test_api_path_is_api_client(self):
        with self.app.test_request_context(
            '/api/cron', method='POST', data={'access_token': 'tok'}
        ):
            op = resolve_operator_from_request()
            self.assertEqual(op.operator_type, 'api_client')
            self.assertEqual(op.operator_name, 'API集成')
            self.assertTrue(op.operator_id)


class TestOperationLogListAndWrite(unittest.TestCase):
    def setUp(self):
        app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        app.secret_key = 'test'
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['CRON_CONFIG'] = {
            'is_dev': '0',
            'block_private_ip': '0',
            'url_allow_hosts': '',
            'url_ssrf_observe_only': '0',
        }
        from app import db
        db.init_app(app)
        register_hms_filters(app)
        app.register_blueprint(main_blueprint)
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(rbac_blueprint)
        self.app = app
        self.client = app.test_client()
        with app.app_context():
            from datas.model.cron_infos import CronInfos  # noqa: F401
            from datas.model.operation_log import OperationLog  # noqa: F401
            from datas.model.rbac_user import RbacUser  # noqa: F401
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            from datas.model.resource_group import ResourceGroup  # noqa: F401
            from datas.model.user_group import UserGroup  # noqa: F401
            from datas.model.task_group import TaskGroup  # noqa: F401
            from datas.model.tag import Tag  # noqa: F401
            from datas.model.task_tag import TaskTag  # noqa: F401
            db.create_all()

    def test_operator_forbidden_on_list(self):
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = 'viewer'
            sess['username'] = 'view'
        self.assertEqual(self.client.get('/operation_log_list').status_code, 403)

    def test_operator_can_list_rows(self):
        from app import db
        from datas.model.cron_infos import CronInfos
        from datas.model.operation_log import OperationLog
        from datas.utils.times import get_now_time, utc_now_hms, str_to_hms

        with self.app.app_context():
            now = utc_now_hms()
            cif = CronInfos(
                task_name='daily',
                task_keyword='kw',
                req_url='https://example.com/d',
                status=1,
                created_at=now,
                updated_at=now,
                scope_type='GLOBAL',
            )
            db.session.add(cif)
            db.session.flush()
            db.session.add(
                OperationLog(
                    create_time=str_to_hms('2026-07-14 10:00:00'),
                    action='create_cron',
                    channel='web',
                    operator_type='user',
                    operator_id='2',
                    operator_name='op',
                    operator_roles_json='["operator"]',
                    operator_permissions_json='[]',
                    target_type='cron',
                    target_id=cif.id,
                    task_name='daily',
                    detail_json='{"hour":"9"}',
                    result='ok',
                )
            )
            db.session.commit()

        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = 'operator'
            sess['username'] = 'op'
            sess['user_id'] = 2
            sess['group_ids'] = []
        resp = self.client.get('/operation_log_list')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn('创建任务', html)
        self.assertIn('daily', html)

    def test_admin_lists_rows(self):
        from app import db
        from datas.model.operation_log import OperationLog
        from datas.utils.times import str_to_hms

        with self.app.app_context():
            db.session.add(
                OperationLog(
                    create_time=str_to_hms('2026-07-14 10:00:00'),
                    action='create_cron',
                    channel='web',
                    operator_type='user',
                    operator_id='1',
                    operator_name='admin',
                    operator_roles_json='["admin"]',
                    operator_permissions_json='[]',
                    task_name='daily',
                    detail_json='{"hour":"9"}',
                    result='ok',
                )
            )
            db.session.commit()

        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = 'admin'
            sess['username'] = 'ops_admin'
            sess['user_id'] = 1
        resp = self.client.get('/operation_log_list')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn('创建任务', html)
        self.assertIn('daily', html)
        self.assertIn('admin', html)

    def test_web_create_writes_operation_log(self):
        from app import db
        from datas.model.operation_log import OperationLog

        with patch('app.services.cron_service.scheduler') as sch:
            sch.add_job.return_value = None
            with self.client.session_transaction() as sess:
                sess['is_login'] = True
                sess['role'] = 'admin'
                sess['username'] = 'ops_admin'
                sess['user_id'] = 1
            resp = self.client.post(
                '/cron_add',
                data={
                    'task_name': 'op-log-create',
                    'task_keyword': '备注说明足够长',
                    'hour': '9',
                    'minute': '0',
                    'req_url': 'https://example.com/hook',
                },
            )
            self.assertEqual(resp.status_code, 200)
            payload = resp.get_json()
            self.assertEqual(payload.get('errcode'), 0, payload)

        with self.app.app_context():
            row = db.session.scalars(
                select(OperationLog).where(OperationLog.task_name == 'op-log-create')
            ).first()
            self.assertIsNotNone(row)
            self.assertEqual(row.action, 'create_cron')
            self.assertEqual(row.channel, 'web')
            self.assertEqual(row.operator_name, 'ops_admin')
            self.assertEqual(row.operator_type, 'user')

    def test_duplicate_task_name_returns_field(self):
        with patch('app.services.cron_service.scheduler') as sch:
            sch.add_job.return_value = None
            with self.client.session_transaction() as sess:
                sess['is_login'] = True
                sess['role'] = 'admin'
                sess['username'] = 'ops_admin'
                sess['user_id'] = 1
            data = {
                'task_name': 'dup-name-job',
                'task_keyword': '备注说明足够长',
                'hour': '9',
                'minute': '0',
                'req_url': 'https://example.com/hook',
            }
            resp1 = self.client.post('/cron_add', data=data)
            self.assertEqual(resp1.get_json().get('errcode'), 0)
            resp2 = self.client.post('/cron_add', data=data)
            payload = resp2.get_json()
            self.assertEqual(payload.get('errcode'), 1)
            self.assertIn('已被占用', payload.get('errmsg') or '')
            self.assertEqual((payload.get('data') or {}).get('field'), 'task_name')

    def test_retire_writes_operation_log(self):
        from app import db
        from datas.model.cron_infos import CronInfos
        from datas.model.operation_log import OperationLog
        from datas.utils.times import str_to_hms

        with self.app.app_context():
            cif = CronInfos(
                task_name='op-retire',
                task_keyword='说明',
                req_url='https://example.com/x',
                status=1,
                created_at=str_to_hms('2026-01-01 00:00:00'),
                updated_at=str_to_hms('2026-01-01 00:00:00'),
            )
            db.session.add(cif)
            db.session.commit()
            cron_id = cif.id

        with patch('app.services.cron_service.scheduler') as sch:
            sch.remove_job.side_effect = Exception('no job')
            with self.client.session_transaction() as sess:
                sess['is_login'] = True
                sess['role'] = 'admin'
                sess['username'] = 'ops_admin'
                sess['user_id'] = 1
            resp = self.client.post(
                '/cron_retire',
                data={'id': str(cron_id), 'reason': '业务下线审计'},
            )
            self.assertEqual(resp.status_code, 200)

        with self.app.app_context():
            row = db.session.scalars(
                select(OperationLog).where(OperationLog.action == 'retire_cron')
            ).first()
            self.assertIsNotNone(row)
            self.assertEqual(row.task_name, 'op-retire')
            detail = json.loads(row.detail_json)
            self.assertEqual(detail.get('reason'), '业务下线审计')

    def test_trim_keeps_newest(self):
        from app import db
        from datas.model.operation_log import OperationLog
        from datas.utils.times import str_to_hms

        with self.app.app_context():
            for i in range(5):
                db.session.add(
                    OperationLog(
                        create_time=str_to_hms('2026-07-14 10:0%d:00' % i),
                        action='create_cron',
                        channel='web',
                        operator_type='user',
                        operator_name='u',
                        task_name='t%d' % i,
                        result='ok',
                    )
                )
            db.session.commit()
            deleted = trim_operation_logs(2)
            db.session.commit()
            self.assertEqual(deleted, 3)
            left = list(
                db.session.scalars(
                    select(OperationLog).order_by(OperationLog.id.asc())
                )
            )
            self.assertEqual(len(left), 2)
            self.assertEqual(left[0].task_name, 't3')


class TestRecordOperationIsolated(unittest.TestCase):
    def test_system_operator_explicit(self):
        from app.services.operation_log_service import record_operation

        op = OperatorContext(
            operator_type='system',
            operator_name='系统',
            roles=['system'],
            permissions=['*'],
        )
        self.assertEqual(op.operator_type, 'system')
        self.assertTrue(callable(record_operation))


if __name__ == '__main__':
    unittest.main()
