# -*- coding:utf-8 -*-
"""编辑任务不得默认把暂停态改成运行中。"""
import os
import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

from app import db
from app.services.cron_service import update_cron
from datas.model.cron_infos import CronInfos
from datas.model.operation_log import OperationLog  # noqa: F401
from datas.utils.times import get_now_time


class TestCronEditPreservesPause(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(self.app)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        now = get_now_time()
        self.cif = CronInfos(
            task_name='paused-job',
            task_keyword='kw',
            run_date='',
            day_of_week='',
            day='',
            hour='1',
            minute='0',
            second='',
            req_url='https://example.com/job',
            status=0,
            created_at=now,
            updated_at=now,
            scope_type='GLOBAL',
            group_id=None,
        )
        db.session.add(self.cif)
        db.session.commit()
        self.norm = {
            'task_name': 'paused-job',
            'task_keyword': 'kw-updated',
            'run_date': '',
            'day_of_week': '',
            'day': '',
            'hour': '2',
            'minute': '0',
            'second': '',
            'req_url': 'https://example.com/job',
        }

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_edit_without_resume_keeps_paused(self):
        mock_sched = MagicMock()
        with patch('app.services.cron_service.scheduler', mock_sched):
            with patch('app.services.cron_service.register_cron_job'):
                with patch(
                    'app.services.operation_log_service.resolve_operator_from_request'
                ) as resolve:
                    from app.services.operation_log_service import OperatorContext
                    resolve.return_value = OperatorContext(
                        operator_type='user',
                        operator_name='editor',
                        roles=['operator'],
                        permissions=[],
                    )
                    update_cron(self.cif, self.norm, resume_after_save=False)
        db.session.refresh(self.cif)
        self.assertEqual(self.cif.status, 0)
        self.assertEqual(self.cif.task_keyword, 'kw-updated')
        self.assertEqual(self.cif.last_operator_name, 'editor')
        self.assertTrue(self.cif.last_operated_at)
        mock_sched.pause_job.assert_called()

    def test_edit_with_resume_starts_job(self):
        mock_sched = MagicMock()
        with patch('app.services.cron_service.scheduler', mock_sched):
            with patch('app.services.cron_service.register_cron_job'):
                with patch(
                    'app.services.operation_log_service.resolve_operator_from_request'
                ) as resolve:
                    from app.services.operation_log_service import OperatorContext
                    resolve.return_value = OperatorContext(
                        operator_type='user',
                        operator_name='editor',
                        roles=['operator'],
                        permissions=[],
                    )
                    update_cron(self.cif, self.norm, resume_after_save=True)
        db.session.refresh(self.cif)
        self.assertEqual(self.cif.status, 1)


if __name__ == '__main__':
    unittest.main()
