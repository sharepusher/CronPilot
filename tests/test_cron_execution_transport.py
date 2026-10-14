# -*- coding: utf-8 -*-
"""Task trigger transport contract: a first-hop redirect is a failed run."""
import json
import os
import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class _RedirectResponse:
    text = 'redirecting'
    content = b'redirecting'

    def __init__(self, status_code):
        self.status_code = status_code
        self.headers = {'Location': '/destination?token=secret'}

    def json(self):
        raise ValueError('not JSON')


class _RedirectingSession:
    def __init__(self, status_code):
        self.status_code = status_code
        self.get_calls = []
        self.post_calls = []

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return _RedirectResponse(self.status_code)

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return _RedirectResponse(self.status_code)


class TestCronExecutionTransport(unittest.TestCase):
    def setUp(self):
        self.app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        self.app.secret_key = 'test-transport'
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            CRON_CONFIG={
                'api_key': '', 'error_keyword': '', 'fail_on_http_4xx_5xx': '0',
                'health_failing_threshold': '3',
            },
        )
        from app import db, scheduler
        db.init_app(self.app)
        scheduler.app = self.app
        self.db = db
        with self.app.app_context():
            from datas.model.cron_infos import CronInfos  # noqa: F401
            from datas.model.job_health import JobHealth  # noqa: F401
            from datas.model.job_log import JobLog  # noqa: F401
            from datas.model.job_log_event import JobLogEvent  # noqa: F401
            self.db.create_all()
            task = CronInfos(
                task_name='redirect-contract', task_keyword='',
                req_url='https://example.test/trigger?existing=1', req_method='GET',
                status=1, scope_type='GLOBAL',
            )
            self.db.session.add(task)
            self.db.session.commit()
            self.task_id = task.id

    def tearDown(self):
        with self.app.app_context():
            self.db.session.remove()
            self.db.drop_all()

    @patch('app.crons.wechat_info_err')
    @patch('app.crons.validate_and_resolve_url', return_value=(True, '', '93.184.216.34'))
    def test_redirect_statuses_are_logged_as_failed_without_requesting_location(self, _validate, _notify):
        from app.crons import cron_do
        from datas.model.cron_infos import CronInfos
        from datas.model.job_log import JobLog
        from datas.model.job_log_event import JobLogEvent

        for method in ('GET', 'POST'):
            for status_code in (301, 302, 303, 307, 308):
                with self.subTest(method=method, status_code=status_code):
                    with self.app.app_context():
                        task = CronInfos(
                            task_name='redirect-{}-{}'.format(method, status_code), task_keyword='',
                            req_url='https://example.test/trigger?existing=1', req_method=method,
                            status=1, scope_type='GLOBAL', req_body='{}' if method == 'POST' else '',
                        )
                        self.db.session.add(task)
                        self.db.session.commit()
                        task_id = task.id
                    session = _RedirectingSession(status_code)
                    with patch('app.crons.make_pinned_session', return_value=session):
                        with self.app.app_context():
                            # Call the undecorated body: the distributed lock has separate tests.
                            job_log_id = cron_do.__wrapped__(task_id, trigger_source='manual')
                            job_log = self.db.session.get(JobLog, job_log_id)
                            events = self.db.session.query(JobLogEvent).filter_by(trace_id=job_log.trace_id).all()

                    calls = session.get_calls if method == 'GET' else session.post_calls
                    self.assertEqual(len(calls), 1)
                    _url, kwargs = calls[0]
                    self.assertFalse(kwargs['allow_redirects'])
                    self.assertEqual(job_log.status, 'fail')
                    self.assertEqual(job_log.fail_reason, 'redirect_blocked')
                    self.assertEqual(job_log.http_status, status_code)
                    complete = next(event for event in events if event.event_type == 'http.complete')
                    detail = json.loads(complete.detail)
                    self.assertEqual(detail['http_status'], status_code)
                    self.assertEqual(detail['redirect_location'], 'https://example.test/destination?token=***')
                    self.assertNotIn('secret', complete.detail)

    @patch('app.crons.wechat_info_err')
    def test_execution_uses_the_only_checked_dns_answer_for_pinning(self, _notify):
        """The dispatch path must neither re-resolve nor create an unpinned session."""
        from app.crons import cron_do

        session = _RedirectingSession(200)
        with patch.dict(self.app.config['CRON_CONFIG'], {
            'api_key': '', 'error_keyword': '', 'fail_on_http_4xx_5xx': '0',
            'block_private_ip': '1', 'url_ssrf_observe_only': '0', 'url_allow_hosts': '',
        }, clear=True):
            with patch(
                'app.services.url_security._resolve_host_ips',
                side_effect=[{'93.184.216.34'}, AssertionError('must not resolve twice')],
            ) as resolver, patch('app.crons.make_pinned_session', return_value=session) as make_session:
                with self.app.app_context():
                    cron_do.__wrapped__(self.task_id, trigger_source='manual')

        self.assertEqual(resolver.call_count, 1)
        make_session.assert_called_once_with('93.184.216.34', 'example.test', 'https')
        self.assertEqual(len(session.get_calls), 1)

    @patch('app.crons.wechat_info_err')
    def test_execution_hard_block_creates_no_http_session_even_when_legacy_switches_are_set(self, _notify):
        """Observe-only and block_private_ip=0 cannot bypass dispatch-time safety."""
        from app.crons import cron_do
        from datas.model.job_log import JobLog
        from datas.model.job_log_event import JobLogEvent

        for switch in ({'url_ssrf_observe_only': '1'}, {'block_private_ip': '0'}):
            with self.subTest(switch=switch):
                config = {
                    'api_key': '', 'error_keyword': '', 'fail_on_http_4xx_5xx': '0',
                    'block_private_ip': '1', 'url_ssrf_observe_only': '0', 'url_allow_hosts': '',
                }
                config.update(switch)
                with patch.dict(self.app.config['CRON_CONFIG'], config, clear=True):
                    with patch('app.services.url_security._resolve_host_ips', return_value={'127.0.0.1'}) as resolver, \
                            patch('app.crons.make_pinned_session') as make_session:
                        with self.app.app_context():
                            job_log_id = cron_do.__wrapped__(self.task_id, trigger_source='manual')
                            job_log = self.db.session.get(JobLog, job_log_id)
                            event = self.db.session.query(JobLogEvent).filter_by(
                                trace_id=job_log.trace_id, event_type='ssrf.check').one()

                self.assertEqual(resolver.call_count, 1)
                make_session.assert_not_called()
                self.assertIn('安全校验未通过', job_log.content)
                self.assertEqual(event.outcome, 'blocked')


if __name__ == '__main__':
    unittest.main()
