# -*- coding: utf-8 -*-
"""B0 / R3 observability contract gate.

Locks Tracer write whitelist ↔ Presenter summary keys, template hard bans,
role matrix smoke, and R1 outcome filter invariants.
"""
import json
import os
import unittest
from types import SimpleNamespace

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

from app.services import execution_tracer as tracer_mod
from app.services import run_inspector_presenter as presenter_mod
from app.services.job_log_filter import KNOWN_OUTCOMES, job_log_outcome_clause
from app.services.run_inspector_presenter import (
    build_event_timeline,
    build_run_inspector_view,
)


class TestObservabilityContractC1Labels(unittest.TestCase):
    def test_emitted_event_types_have_labels(self):
        missing = presenter_mod._EMITTED_EVENT_TYPES - set(presenter_mod._EVENT_LABELS)
        self.assertFalse(missing, 'emit types without labels: {}'.format(missing))


class TestObservabilityContractC2WriteDisplay(unittest.TestCase):
    def test_summary_keys_subset_of_detail_keys(self):
        for event_type, summary_keys in presenter_mod._SUMMARY_KEYS.items():
            detail_keys = tracer_mod._DETAIL_KEYS.get(event_type, set())
            self.assertTrue(
                set(summary_keys) <= set(detail_keys),
                '{}: summary {} not ⊆ detail {}'.format(
                    event_type, summary_keys, detail_keys,
                ),
            )

    def test_summary_never_leaks_forbidden_detail_values(self):
        poison = 'POISON_EXC_DETAIL_SHOULD_NOT_APPEAR'
        cases = [
            ('http.error', 'fail', {'exc_type': 'Timeout', 'exc_detail': poison}),
            ('http.timeout', 'timeout', {'exc_type': 'ReadTimeout', 'exc_detail': poison}),
            ('ssrf.check', 'blocked', {
                'block_type': 'private_ip',
                'block_detail': poison,
            }),
        ]
        for event_type, outcome, detail in cases:
            for role in ('viewer', 'operator', 'admin'):
                with self.subTest(event_type=event_type, role=role):
                    summary = presenter_mod._event_summary(
                        event_type, outcome, json.dumps(detail), role,
                    )
                    self.assertNotIn(poison, summary)
                    self.assertNotIn('{', summary)

    def test_unregistered_event_type_summary_empty(self):
        summary = presenter_mod._event_summary(
            'future.unknown', 'ok', '{"method":"GET"}', 'admin',
        )
        self.assertEqual(summary, '')


class TestObservabilityContractC3TemplateHardBan(unittest.TestCase):
    def test_run_inspector_template_forbids_raw_detail_paths(self):
        path = os.path.join(ROOT, 'app', 'templates', 'redesign', 'run_inspector.html')
        with open(path, encoding='utf-8') as f:
            template = f.read()
        for forbidden in (
            'event.detail',
            'ri-timeline-detail',
            'jl.',
            'cif.',
            'item.',
        ):
            self.assertNotIn(forbidden, template)

    def test_timeline_rows_have_no_detail_key(self):
        event = SimpleNamespace(
            seq=1,
            occurred_at_ms=1_700_000_000_000,
            offset_ms=1,
            event_type='http.error',
            outcome='fail',
            detail='{"exc_detail":"nope"}',
        )
        row = build_event_timeline([event], viewer_role='admin')[0]
        self.assertNotIn('detail', row)
        self.assertIn('summary', row)


class TestObservabilityContractC4RoleMatrix(unittest.TestCase):
    def test_role_matrix_smoke(self):
        jl = SimpleNamespace(
            id=1,
            status='success',
            http_status=200,
            take_time=1.0,
            started_at='20260101120000',
            finished_at='20260101120001',
            create_time='20260101120000',
            trigger_source='schedule',
            fail_reason='',
            content='BODY' * 80,
            actual_url='https://example.com/?t=1',
            trace_id='tid',
            timeout_sec=5,
            trigger_delay_ms=1,
        )
        cif = SimpleNamespace(
            id=1,
            task_name='t',
            req_method='GET',
            req_url='https://example.com/p?token=secret',
        )
        items = [SimpleNamespace(content='biz-step')]

        viewer = build_run_inspector_view(
            jl, cif, business_items=items, viewer_role='viewer',
        )
        self.assertNotIn('token=', viewer['request']['display_url'])
        self.assertEqual(viewer['response']['display_body'], '无权限查看正文')
        self.assertFalse(viewer['business_logs']['visible'])

        operator = build_run_inspector_view(
            jl, cif, business_items=items, viewer_role='operator',
        )
        self.assertIn('token=***', operator['request']['display_url'])
        self.assertTrue(operator['response']['body_visible'])
        self.assertFalse(operator['business_logs']['visible'])

        admin = build_run_inspector_view(
            jl, cif, business_items=items, viewer_role='admin',
        )
        self.assertTrue(admin['business_logs']['visible'])
        self.assertEqual(admin['business_logs']['entries'], ['biz-step'])


class TestObservabilityContractC5OutcomeFilter(unittest.TestCase):
    def test_in_progress_in_known_outcomes(self):
        self.assertIn('in_progress', KNOWN_OUTCOMES)

    def test_pending_running_not_in_not_success(self):
        from app.services.job_log_outcome import (
            STATUS_ERROR,
            STATUS_FAIL,
            STATUS_PENDING,
            STATUS_RUNNING,
            STATUS_TIMEOUT,
        )
        from datas.model.job_log import JobLog

        not_success = job_log_outcome_clause('not_success')
        expected = JobLog.status.in_((STATUS_FAIL, STATUS_ERROR, STATUS_TIMEOUT))
        self.assertEqual(str(not_success), str(expected))
        in_prog = job_log_outcome_clause('in_progress')
        expected_prog = JobLog.status.in_((STATUS_PENDING, STATUS_RUNNING))
        self.assertEqual(str(in_prog), str(expected_prog))


class TestObservabilityContractC6LockSuite(unittest.TestCase):
    def test_lock_primitive_suite_present(self):
        """C6: lock miss must not create runs — primitive covered by test_single_task_lock.

        Full cron_do→no-JobLog integration remains a R4 follow-up if still absent.
        """
        from tests import test_single_task_lock

        self.assertTrue(hasattr(test_single_task_lock, 'TestAcquireReleaseLock'))
        self.assertTrue(
            hasattr(test_single_task_lock.TestAcquireReleaseLock, 'test_second_acquire_fails')
        )


if __name__ == '__main__':
    unittest.main()
