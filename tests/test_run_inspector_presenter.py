# -*- coding: utf-8 -*-
import unittest
from types import SimpleNamespace

from app.services.run_inspector_presenter import (
    build_event_timeline,
    build_run_inspector_view,
    sanitize_url_for_display,
)


class TestRunInspectorPresenter(unittest.TestCase):
    def test_url_display_redacts_every_query_value_and_userinfo(self):
        raw = 'https://alice:pass@example.test:8443/hook?token=secret&x=2&x='
        displayed = sanitize_url_for_display(raw)
        self.assertEqual(
            displayed,
            'https://***:***@example.test:8443/hook?token=***&x=***&x=***',
        )
        for secret in ('alice', 'pass', 'secret', '2'):
            self.assertNotIn(secret, displayed)

    def test_viewer_url_strips_query_entirely(self):
        raw = 'https://example.test/hook?token=secret&sign=abc'
        displayed = sanitize_url_for_display(raw, strip_query=True)
        self.assertEqual(displayed, 'https://example.test/hook')
        self.assertNotIn('token', displayed)
        self.assertNotIn('secret', displayed)

    def test_invalid_url_fails_closed(self):
        self.assertEqual(
            sanitize_url_for_display('https://[bad-host'),
            '地址格式异常（已隐藏）',
        )

    def test_no_role_receives_raw_event_detail_json(self):
        event = SimpleNamespace(
            seq=1,
            occurred_at_ms=1_700_000_000_123,
            offset_ms=9,
            event_type='http.error',
            outcome='fail',
            detail='{"exc_detail":"private diagnostic","exc_type":"ConnectTimeout"}',
        )
        for role in ('viewer', 'operator', 'admin'):
            with self.subTest(role=role):
                row = build_event_timeline([event], viewer_role=role)[0]
                self.assertEqual(row['label'], 'HTTP 请求异常')
                self.assertNotIn('detail', row)
                self.assertNotIn('private diagnostic', row['summary'])
                self.assertNotIn('{', row['summary'])
                if role == 'viewer':
                    self.assertEqual(row['summary'], '请求异常')
                else:
                    self.assertEqual(row['summary'], '请求异常')

    def test_admin_timeline_summary_uses_whitelist_only(self):
        event = SimpleNamespace(
            seq=1,
            occurred_at_ms=1_700_000_000_123,
            offset_ms=9,
            event_type='ssrf.check',
            outcome='blocked',
            detail='{"block_type":"private_ip","block_detail":"should-not-leak"}',
        )
        row = build_event_timeline([event], viewer_role='admin')[0]
        self.assertEqual(row['summary'], '拦截：private_ip')
        self.assertNotIn('should-not-leak', row['summary'])

    def test_http_start_and_complete_summaries(self):
        start = SimpleNamespace(
            seq=1, occurred_at_ms=1, offset_ms=0,
            event_type='http.start', outcome='ok',
            detail='{"method":"post"}',
        )
        complete = SimpleNamespace(
            seq=2, occurred_at_ms=2, offset_ms=10,
            event_type='http.complete', outcome='ok',
            detail='{"http_status":200}',
        )
        rows = build_event_timeline([start, complete], viewer_role='operator')
        self.assertEqual(rows[0]['summary'], 'POST')
        self.assertEqual(rows[1]['summary'], 'HTTP 200')

    def test_http_error_summary_uses_failure_reason(self):
        event = SimpleNamespace(
            seq=1, occurred_at_ms=1, offset_ms=0,
            event_type='http.error', outcome='fail',
            detail='{"fail_reason":"client_incompatible","failure_stage":"transport"}',
        )
        row = build_event_timeline([event], viewer_role='admin')[0]
        self.assertEqual(row['summary'], 'HTTP 客户端初始化失败')

    def test_redirect_blocked_failure_reason_has_stable_label(self):
        jl = SimpleNamespace(
            id=12, status='fail', http_status=302, take_time=0.1,
            started_at='20260101120000', finished_at='20260101120001', create_time='20260101120000',
            trigger_source='manual', fail_reason='redirect_blocked', content='', actual_url='https://example.com/',
            trace_id='tid-redirect', timeout_sec=5, trigger_delay_ms=None,
            failure_stage='remote_response', transport_state='response_received', response_received=True,
        )
        cif = SimpleNamespace(id=1, task_name='t', req_method='GET', req_url='https://example.com/')
        run = build_run_inspector_view(jl, cif, viewer_role='admin')
        self.assertEqual(run['summary']['fail_reason'], '重定向已阻止')

    def test_role_matrix_for_response_and_business_logs(self):
        jl = SimpleNamespace(
            id=7,
            status='success',
            http_status=200,
            take_time=1.2,
            started_at='20260101120000',
            finished_at='20260101120001',
            create_time='20260101120000',
            trigger_source='schedule',
            fail_reason='',
            content='X' * 250,
            actual_url='https://example.com/?t=1',
            trace_id='tid',
            timeout_sec=5,
            trigger_delay_ms=3,
            failure_stage='remote_response',
            transport_state='response_received',
            response_received=True,
        )
        cif = SimpleNamespace(
            id=1, task_name='t', req_method='GET',
            req_url='https://example.com/path?token=secret',
        )
        items = [SimpleNamespace(content='biz-secret-step')]

        viewer = build_run_inspector_view(
            jl, cif, timeline=[], business_items=items, viewer_role='viewer',
        )
        self.assertEqual(viewer['request']['display_url'], 'https://example.com/path')
        self.assertEqual(viewer['response']['display_body'], '无权限查看正文')
        self.assertFalse(viewer['business_logs']['visible'])
        self.assertEqual(viewer['business_logs']['entries'], [])

        operator = build_run_inspector_view(
            jl, cif, timeline=[], business_items=items, viewer_role='operator',
        )
        self.assertIn('token=***', operator['request']['display_url'])
        self.assertTrue(operator['response']['body_visible'])
        self.assertEqual(len(operator['response']['display_body']), 201)  # 200 + …
        self.assertFalse(operator['business_logs']['visible'])

        admin = build_run_inspector_view(
            jl, cif, timeline=[], business_items=items, viewer_role='admin',
        )
        self.assertTrue(admin['business_logs']['visible'])
        self.assertEqual(admin['business_logs']['entries'], ['biz-secret-step'])
        self.assertTrue(admin['request']['actual_request_sent'])

    def test_no_http_response_has_explicit_label(self):
        jl = SimpleNamespace(
            id=9, status='error', http_status=None, take_time=1.2,
            started_at='20260101120000', finished_at='20260101120001', create_time='20260101120000',
            trigger_source='schedule', fail_reason='client_incompatible', content='client error', actual_url='https://example.com/',
            trace_id='tid', timeout_sec=5, trigger_delay_ms=None,
            failure_stage='transport', transport_state='failed_before_response', response_received=False,
        )
        cif = SimpleNamespace(id=1, task_name='t', req_method='GET', req_url='https://example.com/')
        run = build_run_inspector_view(jl, cif, viewer_role='admin')
        self.assertEqual(run['summary']['http_status_label'], '未获得 HTTP 响应')
        self.assertFalse(run['request']['actual_request_sent'])
        self.assertTrue(run['request']['parameter_prepared'])

    def test_transport_state_labels_distinguish_connect_and_read_timeout(self):
        base = dict(
            id=10, status='timeout', http_status=None, take_time=1.2,
            started_at='20260101120000', finished_at='20260101120001', create_time='20260101120000',
            trigger_source='schedule', fail_reason='timeout', content='timeout', actual_url='https://example.com/',
            trace_id='tid', timeout_sec=5, trigger_delay_ms=None,
            failure_stage='transport', response_received=False,
        )
        cif = SimpleNamespace(id=1, task_name='t', req_method='GET', req_url='https://example.com/')
        connect = build_run_inspector_view(
            SimpleNamespace(**base, transport_state='connect_failed'), cif, viewer_role='admin'
        )
        read = build_run_inspector_view(
            SimpleNamespace(**base, transport_state='sent_no_response'), cif, viewer_role='admin'
        )
        self.assertEqual(connect['summary']['transport_state'], 'connect_failed')
        self.assertEqual(read['summary']['transport_state'], 'sent_no_response')
        self.assertFalse(connect['request']['actual_request_sent'])
        self.assertTrue(read['request']['actual_request_sent'])

    def test_sent_state_is_treated_as_request_started(self):
        base = dict(
            id=11, status='error', http_status=None, take_time=1.2,
            started_at='20260101120000', finished_at='20260101120001', create_time='20260101120000',
            trigger_source='schedule', fail_reason='internal', content='error', actual_url='https://example.com/',
            trace_id='tid-sent', timeout_sec=5, trigger_delay_ms=None,
            failure_stage='transport', response_received=False, transport_state='sent',
        )
        cif = SimpleNamespace(id=1, task_name='t', req_method='GET', req_url='https://example.com/')
        run = build_run_inspector_view(SimpleNamespace(**base), cif, viewer_role='admin')
        self.assertTrue(run['request']['actual_request_sent'])

    def test_incomplete_flags_for_pending(self):
        jl = SimpleNamespace(
            id=8, status='pending', http_status=None, take_time=0,
            started_at='20260101120000', finished_at=None, create_time='20260101120000',
            trigger_source='schedule', fail_reason='', content='', actual_url='',
            trace_id='tid', timeout_sec=5, trigger_delay_ms=None,
        )
        cif = SimpleNamespace(id=1, task_name='t', req_method='GET', req_url='https://x/')
        run = build_run_inspector_view(jl, cif, viewer_role='admin')
        self.assertTrue(run['is_incomplete'])
        self.assertIn('最终结果未知', run['status_label'])


if __name__ == '__main__':
    unittest.main()
