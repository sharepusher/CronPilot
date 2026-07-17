# -*- coding:utf-8 -*-
"""Tier 3 前置：scheduler_db / 去 records。"""
import os
import sys
import tempfile
import unittest

from sqlalchemy import create_engine, text

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class TestSchedulerDb(unittest.TestCase):
    def test_fetch_empty_url(self):
        from app.services.scheduler_db import fetch_apscheduler_job_ids

        self.assertEqual(fetch_apscheduler_job_ids(''), set())
        self.assertEqual(fetch_apscheduler_job_ids(None), set())

    def test_fetch_job_ids_from_sqlite(self):
        from app.services.scheduler_db import fetch_apscheduler_job_ids

        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        try:
            url = 'sqlite:///' + path
            engine = create_engine(url)
            with engine.begin() as conn:
                conn.execute(text(
                    'CREATE TABLE apscheduler_jobs ('
                    'id VARCHAR(191) PRIMARY KEY, '
                    'next_run_time FLOAT, '
                    'job_state BLOB)'
                ))
                conn.execute(text(
                    "INSERT INTO apscheduler_jobs (id, next_run_time, job_state) "
                    "VALUES ('cron_1', NULL, X'00'), ('cron_2', NULL, X'00')"
                ))
            engine.dispose()
            ids = fetch_apscheduler_job_ids(url)
            self.assertEqual(ids, {'cron_1', 'cron_2'})
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def test_no_records_import_in_scheduler_paths(self):
        roots = [
            os.path.join(ROOT, 'app', 'CuBackgroundScheduler.py'),
            os.path.join(ROOT, 'app', 'CuGeventScheduler.py'),
            os.path.join(ROOT, 'app', 'crons.py'),
            os.path.join(ROOT, 'app', 'services', 'scheduler_db.py'),
        ]
        for path in roots:
            with open(path, 'r', encoding='utf-8') as f:
                src = f.read()
            self.assertNotIn('import records', src, path)
            self.assertNotIn('records.', src, path)


if __name__ == '__main__':
    unittest.main()
