"""Negative guards for the isolated browser verifier (all DBs in memory)."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from scripts.user_edit_browser_harness import (
    Harness,
    Injection,
    prepare_output,
    validate_database,
    verify_results,
)


class TestIsolation(unittest.TestCase):
    def test_non_memory_database_rejected_before_engine_initialization(self):
        for uri in ('sqlite:///datas/job_log.sqlite', 'mysql+pymysql://localhost/test', '', None):
            with self.subTest(uri=uri), mock.patch('scripts.user_edit_browser_harness.db.init_app') as init:
                with self.assertRaisesRegex(AssertionError, 'isolation_requires_memory'):
                    Harness(uri)
                init.assert_not_called()

    def test_only_exact_memory_uri_allowed(self):
        validate_database('sqlite:///:memory:')

    def test_missing_duplicate_and_unpassed_results_fail(self):
        for rows, phase in (
            ([], 'required_cases_missing'),
            ([{'case_id': 'a', 'passed': True}] * 2, 'duplicate_case'),
            ([{'case_id': 'a', 'passed': False}], 'case_not_passed'),
        ):
            with self.subTest(phase=phase), self.assertRaisesRegex(AssertionError, phase):
                verify_results(rows, {'a'})

    def test_complete_result_set_passes(self):
        verify_results([{'case_id': 'a', 'passed': True}], {'a'})

    def test_stale_success_report_cannot_survive_another_run(self):
        with TemporaryDirectory() as folder:
            output = Path(folder)
            prepare_output(output)
            (output / 'results.json').write_text('{"status":"passed"}')
            with self.assertRaisesRegex(AssertionError, 'output_directory_must_be_empty'):
                prepare_output(output)

    def test_skipped_required_case_cannot_pass(self):
        with self.assertRaisesRegex(AssertionError, 'required_case_skipped'):
            verify_results([{'case_id': 'a', 'passed': True, 'skipped': True}], {'a'})

    def test_factory_real_login_and_csrf_without_network(self):
        import re
        harness = Harness()
        try:
            users = harness.fixture('guard')
            client = harness.app.test_client()
            login = client.get('/rbac/login')
            self.assertEqual(login.status_code, 200)
            token = re.search(r'name="csrf_token" value="([^"]+)"', login.text).group(1)
            denied = client.post('/rbac/login', data={
                'username': users['actor']['username'], 'password': harness.password})
            self.assertIn('CSRF', denied.json['errmsg'])
            result = client.post('/rbac/login', data={
                'username': users['actor']['username'], 'password': harness.password,
                'csrf_token': token, 'next': '/rbac/users'})
            self.assertEqual(result.status_code, 302)
            self.assertEqual(client.get('/rbac/users').status_code, 200)
            self.assertIsNone(harness.server)
        finally:
            harness.__exit__()


class TestInjection(unittest.TestCase):
    def setUp(self):
        from tests.test_registration import _make_app
        self.app, self.db = _make_app()
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.session = self.db.session()

    def tearDown(self):
        self.db.session.remove()
        self.ctx.pop()

    def test_unhit_fault_fails(self):
        injection = Injection(self.session, 'commit_before', {'dml': 0})
        with injection.apply():
            pass
        with self.assertRaisesRegex(AssertionError, 'fault_hit_count_invalid'):
            injection.verify()

    def test_duplicate_fault_hits_fail_and_original_method_restored(self):
        original = self.session.commit
        injection = Injection(self.session, 'commit_before', {'dml': 0})
        with injection.apply():
            for _ in range(2):
                with self.assertRaises(RuntimeError):
                    self.session.commit()
        with self.assertRaisesRegex(AssertionError, 'fault_hit_count_invalid'):
            injection.verify()
        self.assertEqual(self.session.commit, original)
        self.session.commit()

    def test_exception_restores_patch(self):
        original = self.session.commit
        injection = Injection(self.session, 'commit_before', {'dml': 0})
        with self.assertRaises(RuntimeError), injection.apply():
            self.session.commit()
        self.assertEqual(self.session.commit, original)
        injection.verify()

    def test_commit_after_performs_real_commit_then_raises(self):
        from sqlalchemy import text
        self.session.execute(text('CREATE TABLE proof (id INTEGER)'))
        self.session.commit()
        self.session.execute(text('INSERT INTO proof VALUES (1)'))
        injection = Injection(self.session, 'commit_after', {'dml': 1})
        with self.assertRaises(RuntimeError), injection.apply():
            self.session.commit()
        injection.verify()
        self.session.rollback()
        self.assertEqual(self.session.scalar(text('SELECT count(*) FROM proof')), 1)
