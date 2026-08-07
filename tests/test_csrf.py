# -*- coding: utf-8 -*-
"""OPT-P0-11 CSRF unit tests (bypass disabled)."""
import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from flask import Flask

from app.security.csrf import CSRF_PARAM, CSRF_SESSION_KEY, ensure_csrf_token, validate_csrf


class TestCsrfHelpers(unittest.TestCase):
    def test_validate_accepts_matching_token(self):
        app = Flask(__name__)
        app.secret_key = 'csrf-helper-secret-key!'
        with app.test_request_context('/', method='POST', data={CSRF_PARAM: 'abc'}):
            from flask import session
            session[CSRF_SESSION_KEY] = 'abc'
            self.assertTrue(validate_csrf())

    def test_validate_rejects_mismatch_and_missing(self):
        app = Flask(__name__)
        app.secret_key = 'csrf-helper-secret-key!'
        with app.test_request_context('/', method='POST', data={CSRF_PARAM: 'wrong'}):
            from flask import session
            session[CSRF_SESSION_KEY] = 'right'
            self.assertFalse(validate_csrf())
        with app.test_request_context('/', method='POST', data={}):
            from flask import session
            session[CSRF_SESSION_KEY] = 'right'
            self.assertFalse(validate_csrf())

    def test_ensure_creates_token(self):
        app = Flask(__name__)
        app.secret_key = 'csrf-helper-secret-key!'
        with app.test_request_context('/'):
            t1 = ensure_csrf_token()
            t2 = ensure_csrf_token()
            self.assertTrue(t1)
            self.assertEqual(t1, t2)


class TestCsrfOnUpdateStatus(unittest.TestCase):
    def setUp(self):
        app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        app.secret_key = 'csrf-route-secret-key!!'
        app.config['TESTING'] = True
        app.config['CSRF_BYPASS_IN_TESTING'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        from app import db
        from app.main.views import main as main_blueprint
        from app.rbac import rbac as rbac_blueprint

        db.init_app(app)
        app.register_blueprint(main_blueprint)
        app.register_blueprint(rbac_blueprint)
        self.app = app
        self.client = app.test_client()
        self.db = db
        with app.app_context():
            from datas.model.cron_infos import CronInfos
            from datas.model.task_group import TaskGroup  # noqa: F401
            from datas.model.tag import Tag  # noqa: F401
            from datas.model.task_tag import TaskTag  # noqa: F401
            db.create_all()
            row = CronInfos(
                task_name='csrf-task',
                task_keyword='k',
                req_url='https://example.com/x',
                status=1,
                created_at='t',
                updated_at='t',
            )
            db.session.add(row)
            db.session.commit()
            self.cron_id = row.id

    def _login(self):
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = 'admin'
            sess['username'] = 'ops_admin'
            sess['group_ids'] = []
            sess[CSRF_SESSION_KEY] = 'good-csrf-token-32chars-min!!'

    def test_get_update_status_method_not_allowed(self):
        self._login()
        resp = self.client.get('/update_status?id=%s' % self.cron_id)
        self.assertEqual(resp.status_code, 405)

    def test_post_without_token_rejected(self):
        self._login()
        resp = self.client.post('/update_status?id=%s' % self.cron_id)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json().get('errcode'), 1)
        self.assertIn('CSRF', resp.get_json().get('errmsg') or '')

    def test_post_with_token_ok(self):
        self._login()
        with patch('app.main.views.scheduler') as sch:
            sch.pause_job.return_value = None
            sch.resume_job.return_value = None
            resp = self.client.post(
                '/update_status?id=%s' % self.cron_id,
                data={CSRF_PARAM: 'good-csrf-token-32chars-min!!'},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json().get('errcode'), 0)

    def test_login_page_has_csrf_fields(self):
        resp = self.client.get('/rbac/login')
        html = resp.get_data(as_text=True)
        self.assertIn('name="csrf-token"', html)
        self.assertIn('name="csrf_token"', html)


if __name__ == '__main__':
    unittest.main()
