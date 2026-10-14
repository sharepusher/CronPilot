# -*- coding: utf-8 -*-
import time
import unittest

from flask import Flask


class TestExecutionTracer(unittest.TestCase):
    def setUp(self):
        from app import db

        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(self.app)
        self.db = db
        with self.app.app_context():
            from datas.model.job_log_event import JobLogEvent  # noqa: F401
            db.create_all()

    def test_emits_epoch_millisecond_event_with_incrementing_sequence(self):
        from app.services.execution_tracer import ExecutionTracer
        from datas.model.job_log_event import JobLogEvent

        before = int(time.time() * 1000)
        with self.app.app_context():
            tracer = ExecutionTracer('trace-1', 9)
            self.assertTrue(tracer.emit('task.enqueued', detail={'scheduled_delay_ms': 12}))
            self.assertTrue(tracer.emit('task.start'))
            rows = self.db.session.query(JobLogEvent).order_by(JobLogEvent.seq).all()

        self.assertEqual([row.seq for row in rows], [1, 2])
        self.assertEqual(rows[0].trace_id, 'trace-1')
        self.assertGreaterEqual(rows[0].occurred_at_ms, before)
        self.assertLess(rows[0].occurred_at_ms, before + 10_000)
        self.assertIn('scheduled_delay_ms', rows[0].detail)

    def test_emits_run_id_for_strong_parent_link(self):
        from app.services.execution_tracer import ExecutionTracer
        from datas.model.job_log_event import JobLogEvent

        with self.app.app_context():
            tracer = ExecutionTracer('trace-run', 9, run_id=123)
            self.assertTrue(tracer.emit('task.start'))
            row = self.db.session.query(JobLogEvent).one()
        self.assertEqual(row.run_id, 123)
        self.assertEqual(row.schema_version, 1)

    def test_drops_unapproved_detail_fields_and_stops_at_event_budget(self):
        from app.services.execution_tracer import ExecutionTracer
        from datas.model.job_log_event import JobLogEvent

        with self.app.app_context():
            tracer = ExecutionTracer('trace-budget', 9)
            self.assertTrue(tracer.emit('http.start', detail={
                'method': 'GET', 'raw_url': 'must-not-persist',
            }))
            for _ in range(15):
                self.assertTrue(tracer.emit('task.start'))
            self.assertFalse(tracer.emit('task.start'))
            rows = self.db.session.query(JobLogEvent).order_by(JobLogEvent.seq).all()

        self.assertEqual(len(rows), 16)
        self.assertEqual(rows[0].detail, '{"method": "GET"}')

    def test_redirect_location_is_sanitized_before_persistence(self):
        from app.services.execution_tracer import ExecutionTracer, sanitize_event_url
        from datas.model.job_log_event import JobLogEvent

        location = sanitize_event_url(
            '/next?token=secret', base_url='https://example.com/start?sign=secret',
        )
        self.assertEqual(location, 'https://example.com/next?token=***')
        with self.app.app_context():
            tracer = ExecutionTracer('trace-redirect', 9)
            self.assertTrue(tracer.emit('http.complete', detail={
                'http_status': 302,
                'redirect_location': location,
                'unapproved': 'must-not-persist',
            }))
            row = self.db.session.query(JobLogEvent).one()
        self.assertIn('redirect_location', row.detail)
        self.assertNotIn('secret', row.detail)
        self.assertNotIn('unapproved', row.detail)
