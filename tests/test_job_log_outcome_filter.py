# -*- coding:utf-8 -*-
"""OPT-P1-01c outcome 筛选。"""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.services.job_log_filter import job_log_outcome_clause


class TestJobLogOutcomeClause(unittest.TestCase):
    def test_all_empty(self):
        self.assertIsNone(job_log_outcome_clause(None))
        self.assertIsNone(job_log_outcome_clause(''))
        self.assertIsNone(job_log_outcome_clause('all'))

    def test_not_success(self):
        self.assertIsNotNone(job_log_outcome_clause('not_success'))

    def test_known_values(self):
        for v in ('success', 'fail', 'error', 'unknown'):
            self.assertIsNotNone(job_log_outcome_clause(v))


if __name__ == '__main__':
    unittest.main()
