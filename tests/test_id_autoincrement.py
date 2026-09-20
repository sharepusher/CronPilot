# -*- coding: utf-8 -*-
"""Database-owned ID allocation regression tests (OPT-P0-21)."""
import importlib.util
import os
import sys
import unittest

from flask import Flask
from sqlalchemy import inspect, text

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load_ensure():
    path = os.path.join(ROOT, 'scripts', 'ensure_business_tables.py')
    spec = importlib.util.spec_from_file_location('ensure_business_tables_id_test', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestDatabaseOwnedIds(unittest.TestCase):
    def setUp(self):
        from app import db

        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(self.app)
        self.db = db

    def test_orm_primary_keys_are_database_generated(self):
        from datas.model.cron_infos import CronInfos
        from datas.model.job_log import JobLog
        from datas.model.job_log_event import JobLogEvent

        with self.app.app_context():
            self.db.create_all()
            cron = CronInfos(task_name='id-test', task_keyword='id-test')
            self.db.session.add(cron)
            self.db.session.flush()
            log = JobLog(
                trace_id='id-test-log', cron_info_id=cron.id,
                content='', create_time=1,
            )
            event = JobLogEvent(
                trace_id='id-test-event', cron_id=cron.id, seq=1,
                event_type='test', occurred_at_ms=1, offset_ms=0,
                outcome='ok', detail='{}',
            )
            self.db.session.add_all([log, event])
            self.db.session.flush()
            self.assertIsInstance(cron.id, int)
            self.assertIsInstance(log.id, int)
            self.assertIsInstance(event.id, int)
            self.assertGreater(cron.id, 0)
            self.assertGreater(log.id, 0)
            self.assertGreater(event.id, 0)

    def test_existing_bigint_event_table_switches_without_changing_rows(self):
        mod = _load_ensure()
        with self.app.app_context():
            self.db.session.execute(text(
                'CREATE TABLE job_log_events ('
                'id BIGINT NOT NULL, trace_id VARCHAR(65) NOT NULL, '
                'cron_id INTEGER NOT NULL, seq INTEGER NOT NULL, '
                'event_type VARCHAR(48) NOT NULL, occurred_at_ms BIGINT NOT NULL, '
                'offset_ms INTEGER NOT NULL, duration_ms INTEGER, '
                'outcome VARCHAR(16) NOT NULL, detail TEXT NOT NULL, '
                'run_id BIGINT, schema_version SMALLINT DEFAULT 1, '
                'PRIMARY KEY (id), '
                'CONSTRAINT uq_job_log_events_trace_seq UNIQUE (trace_id, seq))'
            ))
            self.db.session.execute(text(
                "INSERT INTO job_log_events "
                "(id, trace_id, cron_id, seq, event_type, occurred_at_ms, "
                "offset_ms, outcome, detail) VALUES "
                "(9007199254740001, 'legacy', 7, 1, 'test', 1, 0, 'ok', '{}')"
            ))
            self.db.session.commit()
            mod._ensure_sqlite_event_id_autoincrement()
            ddl = self.db.session.execute(text(
                "SELECT sql FROM sqlite_master WHERE type='table' "
                "AND name='job_log_events'"
            )).scalar_one()
            self.assertIn('"id" INTEGER PRIMARY KEY', ddl)
            row = self.db.session.execute(text(
                "SELECT id, trace_id FROM job_log_events"
            )).one()
            self.assertEqual((row[0], row[1]), (9007199254740001, 'legacy'))
            self.db.session.execute(text(
                "INSERT INTO job_log_events "
                "(trace_id, cron_id, seq, event_type, occurred_at_ms, "
                "offset_ms, outcome, detail) VALUES "
                "('new', 7, 1, 'test', 2, 0, 'ok', '{}')"
            ))
            self.db.session.commit()
            new_id = self.db.session.execute(text(
                "SELECT id FROM job_log_events WHERE trace_id='new'"
            )).scalar_one()
            self.assertEqual(new_id, 9007199254740002)
            self.assertEqual(
                inspect(self.db.engine).get_indexes('job_log_events'),
                [],
            )
