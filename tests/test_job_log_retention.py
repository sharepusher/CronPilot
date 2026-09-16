# -*- coding: utf-8 -*-
import unittest

from app.services.job_log_service import delete_job_logs_for_cron, trim_job_logs_for_cron


class TestJobLogRetention(unittest.TestCase):
    def test_legacy_delete_entry_points_are_non_destructive(self):
        self.assertEqual(delete_job_logs_for_cron(1), 0)
        self.assertEqual(trim_job_logs_for_cron(1, 1), 0)


if __name__ == '__main__':
    unittest.main()
