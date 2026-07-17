# -*- coding: utf-8 -*-
"""执行记录 log_id 必填（与回调 / add_log 可追溯）。"""
import os
import unittest
from unittest.mock import patch

from flask import Flask

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class TestJobLogAlwaysHasLogId(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        from app import db
        db.init_app(app)
        self.app = app
        self.db = db
        with app.app_context():
            from datas.model.job_log import JobLog  # noqa: F401
            from datas.model.job_health import JobHealth  # noqa: F401
            db.create_all()

    def test_save_job_log_generates_log_id_when_missing(self):
        from app.crons import _save_job_log
        from datas.model.job_log import JobLog

        with self.app.app_context():
            with patch('app.crons._notify_job_outcome'):
                jl = _save_job_log(1, '请求链接不存在', '2026-07-13 12:00:00', 0)
            self.assertTrue(jl.log_id)
            self.assertGreaterEqual(len(jl.log_id), 8)
            row = self.db.session.get(JobLog, jl.id)
            self.assertEqual(row.log_id, jl.log_id)

    def test_save_job_log_keeps_provided_log_id(self):
        from app.crons import _save_job_log

        with self.app.app_context():
            with patch('app.crons._notify_job_outcome'):
                jl = _save_job_log(
                    1,
                    'ok',
                    '2026-07-13 12:00:00',
                    0.1,
                    log_id='fixed-uuid-for-test',
                    status='success',
                )
            self.assertEqual(jl.log_id, 'fixed-uuid-for-test')


if __name__ == '__main__':
    unittest.main(verbosity=2)
