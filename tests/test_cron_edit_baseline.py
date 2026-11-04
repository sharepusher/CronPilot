"""Exercise the actual baseline command and detect injected observable regressions."""
import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from app import db
from datas.model.cron_infos import CronInfos
from scripts import verify_cron_edit_baseline as baseline

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {'no_change', 'unrelated_merge', 'same_field_conflict',
            'scheduler_failure', 'audit_failure', 'paused_registration'}


class TestCurrentBaselineCommand(unittest.TestCase):
    def test_subprocess_executes_all_six_contracts(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/verify_cron_edit_baseline.py')],
                                cwd=str(ROOT), text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        records = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        self.assertEqual({record['case'] for record in records}, EXPECTED)
        self.assertEqual(len(records), 6)
        self.assertTrue(all(record['passed'] for record in records))
        self.assertIn('CRON_EDIT_BASELINE: OK cases=6 mode=current_contract', result.stdout)
        self.assertEqual(next(row for row in records if row['case'] == 'no_change')['commit_attempts'], 0)

    def test_real_noop_commit_mutation_makes_command_fail(self):
        original = baseline.update_cron

        def extra_commit(task, values):
            db.session.commit()
            return original(task, values)

        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(baseline, 'update_cron', side_effect=extra_commit), \
                patch('sys.argv', ['verify_cron_edit_baseline.py']), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(baseline.main(), 1)
        self.assertIn('FAIL case=no_change', stderr.getvalue())
        self.assertNotIn('CRON_EDIT_BASELINE: OK', stdout.getvalue())

    def test_real_partial_save_on_conflict_is_detected(self):
        original = baseline.save_task_edit

        def partial_save(actor, task_id, *args, **kwargs):
            result = original(actor, task_id, *args, **kwargs)
            if result['outcome'] == 'conflict':
                db.session.get(CronInfos, task_id).timeout_sec = 99
                db.session.commit()
            return result

        with patch.object(baseline, 'save_task_edit', side_effect=partial_save):
            with self.assertRaisesRegex(AssertionError, 'read_only_submission_changed_state'):
                baseline.run_case('same_field_conflict')

    def test_real_unpaused_registration_is_detected(self):
        original = baseline.register_cron_job
        calls = []

        def unpaused(*args, **kwargs):
            calls.append(True)
            if len(calls) == 2:
                kwargs['paused'] = False
            return original(*args, **kwargs)

        with patch.object(baseline, 'register_cron_job', side_effect=unpaused):
            with self.assertRaisesRegex(AssertionError, 'paused_job_target_wrong'):
                baseline.run_case('paused_registration')
        self.assertEqual(len(calls), 2)

    def test_missing_case_cannot_claim_complete_success(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(baseline, 'CASES', ('no_change',)), \
                patch('sys.argv', ['verify_cron_edit_baseline.py']), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(baseline.main(), 1)
        self.assertIn('case_matrix_incomplete', stderr.getvalue())
        self.assertNotIn('CRON_EDIT_BASELINE: OK', stdout.getvalue())

    def test_unknown_case_is_rejected(self):
        with self.assertRaisesRegex(AssertionError, 'unknown_case'):
            baseline.run_case('not-a-case')


if __name__ == '__main__':
    unittest.main()
