# -*- coding: utf-8 -*-
import unittest
from types import SimpleNamespace

from app.services.run_inspector_presenter import build_event_timeline, sanitize_url_for_display


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

    def test_invalid_url_fails_closed(self):
        self.assertEqual(
            sanitize_url_for_display('https://[bad-host'),
            '地址格式异常（已隐藏）',
        )

    def test_non_admin_does_not_receive_event_detail(self):
        event = SimpleNamespace(
            seq=1,
            occurred_at_ms=1_700_000_000_123,
            offset_ms=9,
            event_type='http.error',
            outcome='fail',
            detail='{"exc_detail":"private diagnostic"}',
        )
        row = build_event_timeline([event], include_detail=False)[0]
        self.assertEqual(row['label'], 'HTTP 请求异常')
        self.assertEqual(row['detail'], '')

    def test_admin_receives_structured_detail(self):
        event = SimpleNamespace(
            seq=1,
            occurred_at_ms=1_700_000_000_123,
            offset_ms=9,
            event_type='ssrf.check',
            outcome='blocked',
            detail='{"block_type":"private_ip"}',
        )
        row = build_event_timeline([event], include_detail=True)[0]
        self.assertEqual(row['detail'], '{"block_type": "private_ip"}')
