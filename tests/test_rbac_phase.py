import os
import unittest
from unittest.mock import patch

from flask import Flask, render_template, session

from app.main import main as main_blueprint
from app.rbac.context import make_has_perm
from app.rbac.policy import has_permission
from app.rbac.services import get_role_permission_set


class TestCheckPassForward(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.secret_key = 'test'
        app.config['TESTING'] = True
        app.register_blueprint(main_blueprint)
        self.client = app.test_client()

    def _location_path_query(self, resp):
        loc = resp.headers['Location']
        if loc.startswith('http://') or loc.startswith('https://'):
            from urllib.parse import urlparse
            parsed = urlparse(loc)
            return parsed.path + (('?' + parsed.query) if parsed.query else '')
        return loc

    def test_get_without_next_redirects_to_rbac_login(self):
        resp = self.client.get('/check_pass')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self._location_path_query(resp), '/rbac/login')

    def test_get_with_next_passthrough_matches_decorator_format(self):
        resp = self.client.get('/check_pass?next=/cron_list?task_name=x')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            self._location_path_query(resp),
            '/rbac/login?next=/cron_list?task_name=x',
        )

    def test_post_without_next_uses_307(self):
        resp = self.client.post('/check_pass')
        self.assertEqual(resp.status_code, 307)
        self.assertEqual(self._location_path_query(resp), '/rbac/login')

    def test_post_with_next_passthrough_matches_decorator_format(self):
        resp = self.client.post('/check_pass?next=/cron_list')
        self.assertEqual(resp.status_code, 307)
        self.assertEqual(self._location_path_query(resp), '/rbac/login?next=/cron_list')


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class TestRbacLogin(unittest.TestCase):
    def setUp(self):
        app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        app.secret_key = 'test'
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        from app import db
        db.init_app(app)
        app.register_blueprint(main_blueprint)
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(rbac_blueprint)
        self.app = app
        self.client = app.test_client()
        with app.app_context():
            from datas.model.rbac_user import RbacUser  # noqa: F401
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            db.create_all()

    def test_login_get_renders(self):
        resp = self.client.get('/rbac/login')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('密码', resp.get_data(as_text=True))

    def test_seed_admin_login_redirects_to_next(self):
        with patch(
            'app.rbac.services.configs',
            return_value={'login_pwd': 'changeme'},
        ):
            resp = self.client.post(
                '/rbac/login',
                data={
                    'username': 'admin',
                    'password': 'changeme',
                    'next': '/cron_list?task_name=x',
                },
            )
            self.assertEqual(resp.status_code, 302)
            self.assertIn('/cron_list?task_name=x', resp.headers['Location'])

    def test_empty_username_rejected(self):
        with patch(
            'app.rbac.services.configs',
            return_value={'login_pwd': 'changeme'},
        ):
            resp = self.client.post(
                '/rbac/login',
                data={'password': 'changeme', 'next': '/cron_list'},
                follow_redirects=False,
            )
            self.assertEqual(resp.status_code, 302)
            self.assertIn('msg=', resp.headers['Location'])
            from urllib.parse import unquote
            self.assertIn('用户名', unquote(resp.headers['Location']))



    def test_check_pass_forwards_next_to_login(self):
        resp = self.client.get('/check_pass?next=/cron_list?task_name=x')
        self.assertEqual(resp.status_code, 302)
        loc = resp.headers['Location']
        self.assertIn('/rbac/login?next=', loc)
        self.assertIn('task_name=x', loc)


class TestChangeOwnPassword(unittest.TestCase):
    def setUp(self):
        app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        app.secret_key = 'test'
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        from app import db
        db.init_app(app)
        app.register_blueprint(main_blueprint)
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(rbac_blueprint)
        self.app = app
        self.client = app.test_client()
        self.db = db
        with app.app_context():
            from datas.model.rbac_user import RbacUser  # noqa: F401
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            db.create_all()
            u = RbacUser(username='op1', role='operator', is_active=1, create_time='t')
            u.set_password('oldpass1')
            db.session.add(u)
            db.session.commit()
            self.user_id = u.id

    def _login(self):
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['username'] = 'op1'
            sess['role'] = 'operator'
            sess['user_id'] = self.user_id
            sess['group_ids'] = []

    def test_unauthenticated_redirects_to_login(self):
        resp = self.client.get('/rbac/password')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/rbac/login', resp.headers['Location'])

    def test_get_renders_form(self):
        self._login()
        resp = self.client.get('/rbac/password')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn('js-ajax-form', body)
        self.assertIn('js-ajax-submit', body)
        self.assertIn('当前密码', body)

    def test_wrong_old_password_rejected(self):
        self._login()
        resp = self.client.post(
            '/rbac/password',
            data={
                'old_password': 'wrong',
                'new_password': 'newpass1',
                'confirm_password': 'newpass1',
            },
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json().get('errcode'), 1)
        self.assertIn('当前密码', resp.get_json().get('errmsg', ''))

    def test_operator_can_change_own_password(self):
        self._login()
        resp = self.client.post(
            '/rbac/password',
            data={
                'old_password': 'oldpass1',
                'new_password': 'newpass1',
                'confirm_password': 'newpass1',
            },
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get('errcode'), 0)
        self.assertIn('/rbac/login', data.get('url', ''))
        self.assertIn('重新登录', data.get('errmsg', ''))
        with self.client.session_transaction() as sess:
            self.assertNotIn('is_login', sess)
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            u = self.db.session.get(RbacUser, self.user_id)
            self.assertTrue(u.check_password('newpass1'))
            self.assertFalse(u.check_password('oldpass1'))
            self.assertEqual(u.must_reset_password, 0)


class TestR3Permissions(unittest.TestCase):
    def setUp(self):
        app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        app.secret_key = 'test'
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        from app import db
        db.init_app(app)
        app.register_blueprint(main_blueprint)
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(rbac_blueprint)
        self.app = app
        self.client = app.test_client()
        with app.app_context():
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            db.create_all()

    def _login_as(self, role):
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = role

    def test_viewer_cron_write_routes_return_403(self):
        self._login_as('viewer')
        for path in ('/cron_add', '/cron_edit?id=1'):
            resp = self.client.get(path)
            self.assertEqual(resp.status_code, 403, path)
        resp = self.client.post('/update_status?id=1')
        self.assertEqual(resp.status_code, 403)

    def test_viewer_log_delete_returns_410(self):
        self._login_as('viewer')
        resp = self.client.post('/job_log_delete', data={'job_log_id': '1'})
        self.assertEqual(resp.status_code, 410)
        resp = self.client.post('/job_batch_delete', data={'id': '1'})
        self.assertEqual(resp.status_code, 410)

    def test_viewer_cron_retire_returns_403(self):
        self._login_as('viewer')
        resp = self.client.get('/cron_retire?id=1')
        self.assertEqual(resp.status_code, 403)

    def test_unauthenticated_redirects_to_rbac_login_with_next(self):
        resp = self.client.get('/cron_list')
        self.assertEqual(resp.status_code, 302)
        loc = resp.headers['Location']
        self.assertIn('/rbac/login?next=', loc)
        self.assertIn('/cron_list', loc)


class TestLifecycleNoDelete(unittest.TestCase):
    def setUp(self):
        app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        app.secret_key = 'test'
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        from app import db
        db.init_app(app)
        app.register_blueprint(main_blueprint)
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(rbac_blueprint)
        self.client = app.test_client()

    def test_operator_cron_del_returns_410(self):
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = 'operator'
        resp = self.client.post('/cron_batch_del', data={'id': '1'})
        self.assertEqual(resp.status_code, 410)
        resp = self.client.get('/cron_del?id=1')
        self.assertEqual(resp.status_code, 410)

    def test_operator_cannot_retire(self):
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = 'operator'
        resp = self.client.get('/cron_retire?id=1')
        self.assertEqual(resp.status_code, 403)

    def test_admin_retire_requires_reason_and_writes_fields(self):
        from app import db
        from datas.model.cron_infos import CronInfos

        with self.client.application.app_context():
            db.create_all()
            cif = CronInfos(
                task_name='retire-me',
                task_keyword='说明',
                req_url='https://example.com/x',
                status=1,
                created_at='2026-01-01 00:00:00',
                updated_at='2026-01-01 00:00:00',
            )
            db.session.add(cif)
            db.session.commit()
            cron_id = cif.id

        with patch('app.services.cron_service.scheduler') as sch:
            sch.remove_job.side_effect = Exception('no job')
            with self.client.session_transaction() as sess:
                sess['is_login'] = True
                sess['role'] = 'admin'
            resp = self.client.post(
                '/cron_retire',
                data={'id': str(cron_id)},
            )
            self.assertEqual(resp.status_code, 200)
            payload = resp.get_json()
            self.assertEqual(payload.get('errmsg'), '请填写下线原因')

            resp = self.client.post(
                '/cron_retire',
                data={'id': str(cron_id), 'reason': '测试下线'},
            )
            self.assertEqual(resp.status_code, 200)

        with self.client.application.app_context():
            row = db.session.get(CronInfos, cron_id)
            self.assertEqual(row.status, -1)
            self.assertEqual(row.retire_reason, '测试下线')
            self.assertTrue(row.retired_at)


class TestCronListRetireButtonVisibility(unittest.TestCase):
    """未下线任务对所有角色展示「下线」；仅 admin 可进表单，其它角色为提示入口。"""

    def setUp(self):
        app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        app.secret_key = 'test'
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        from app import db
        db.init_app(app)
        app.register_blueprint(main_blueprint)
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(rbac_blueprint)
        self.app = app
        self.client = app.test_client()
        self.db = db
        with app.app_context():
            from datas.model.cron_infos import CronInfos  # noqa: F401
            from datas.model.rbac_user import RbacUser  # noqa: F401
            db.create_all()
            cif = CronInfos(
                task_name='visible-retire',
                task_keyword='说明',
                req_url='https://example.com/r',
                status=1,
                created_at='t',
                updated_at='t',
            )
            db.session.add(cif)
            db.session.commit()

    def _login(self, role):
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = role
            # 全权限 admin 不得用种子用户名 admin（种子无 cron:write/retire）
            sess['username'] = 'ops_admin' if role == 'admin' else role
            sess['group_ids'] = []

    def test_operator_sees_retire_denied_tip_not_form_link(self):
        self._login('operator')
        html = self.client.get('/cron_list').get_data(as_text=True)
        self.assertIn('下线</a>', html)
        self.assertIn('class="js-retire-denied"', html)
        self.assertIn('当前账号不可下线', html)
        self.assertNotIn('/cron_retire?', html)

    def test_viewer_sees_retire_denied_tip(self):
        self._login('viewer')
        html = self.client.get('/cron_list').get_data(as_text=True)
        self.assertIn('下线</a>', html)
        self.assertIn('class="js-retire-denied"', html)

    def test_admin_sees_retire_form_link(self):
        self._login('admin')
        html = self.client.get('/cron_list').get_data(as_text=True)
        self.assertIn('下线</a>', html)
        self.assertIn('/cron_retire?', html)
        self.assertNotIn('class="js-retire-denied"', html)

    def test_seed_admin_sees_retire_denied_tip(self):
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = 'admin'
            sess['username'] = 'admin'
            sess['group_ids'] = []
        html = self.client.get('/cron_list').get_data(as_text=True)
        self.assertIn('下线</a>', html)
        self.assertIn('class="js-retire-denied"', html)
        self.assertNotIn('/cron_retire?', html)


class TestNavHasPerm(unittest.TestCase):
    def setUp(self):
        app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        app.secret_key = 'test'
        app.config['TESTING'] = True
        app.register_blueprint(main_blueprint)
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(rbac_blueprint)
        self.app = app

    def _render_nav(self, role):
        with self.app.app_context():
            with self.app.test_request_context():
                session['is_login'] = True
                session['role'] = role
                return render_template('rbac/_nav.html', active='cron_list')

    def test_viewer_nav_hides_cron_add(self):
        html = self._render_nav('viewer')
        self.assertIn('任务中心', html)
        self.assertIn('任务执行记录', html)
        self.assertNotIn('任务添加', html)
        self.assertNotIn('用户管理', html)

    def test_operator_nav_shows_cron_add(self):
        html = self._render_nav('operator')
        self.assertIn('任务添加', html)
        self.assertNotIn('用户管理', html)

    def test_admin_nav_shows_users_and_audit(self):
        html = self._render_nav('admin')
        self.assertIn('用户管理', html)
        self.assertIn('审计', html)
        self.assertIn('操作记录', html)

    def test_operator_nav_hides_audit(self):
        html = self._render_nav('operator')
        self.assertNotIn('审计', html)
        self.assertNotIn('用户管理', html)
        self.assertIn('操作记录', html)

    def test_any_role_nav_shows_change_password(self):
        for role in ('admin', 'operator', 'viewer'):
            html = self._render_nav(role)
            self.assertIn('修改密码', html, role)

    def test_cron_edit_nav_shows_edit_not_add(self):
        with self.app.app_context():
            with self.app.test_request_context():
                session['is_login'] = True
                session['role'] = 'operator'
                html = render_template('rbac/_nav.html', active='cron_edit')
        self.assertIn('任务编辑', html)
        self.assertNotIn('任务添加', html)

    def test_viewer_nav_hides_operation_and_rbac(self):
        html = self._render_nav('viewer')
        self.assertNotIn('操作记录', html)
        self.assertNotIn('用户管理', html)
        self.assertNotIn('审计', html)


class TestNotFound(unittest.TestCase):
    def setUp(self):
        app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        app.secret_key = 'test'
        app.config['TESTING'] = True
        app.register_blueprint(main_blueprint)
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(rbac_blueprint)
        self.client = app.test_client()

    def test_guest_404_renders_minimal_page(self):
        resp = self.client.get('/__no_such_route__')
        self.assertEqual(resp.status_code, 404)
        body = resp.get_data(as_text=True)
        self.assertIn('页面不存在', body)
        self.assertIn('前往登录', body)
        self.assertNotIn('任务中心', body)

    def test_logged_in_404_renders_nav_and_home_link(self):
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
        resp = self.client.get('/__no_such_route__')
        self.assertEqual(resp.status_code, 404)
        body = resp.get_data(as_text=True)
        self.assertIn('页面不存在', body)
        self.assertIn('返回任务中心', body)
        self.assertIn('任务中心', body)


class TestRbacUsersManage(unittest.TestCase):
    def setUp(self):
        app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        app.secret_key = 'test'
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        from app import db
        db.init_app(app)
        app.register_blueprint(main_blueprint)
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(rbac_blueprint)
        self.app = app
        self.client = app.test_client()
        self.db = db
        with app.app_context():
            from datas.model.rbac_user import RbacUser  # noqa: F401
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            from datas.model.resource_group import ResourceGroup  # noqa: F401
            from datas.model.user_group import UserGroup  # noqa: F401
            db.create_all()
            g = ResourceGroup(
                name='Default',
                code='default',
                description='',
                create_time='t',
            )
            db.session.add(g)
            db.session.commit()
            self.group_id = g.id

    def _login(self, role='admin', user_id=None):
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = role
            sess['username'] = role
            if user_id is not None:
                sess['user_id'] = user_id

    def test_operator_users_list_403(self):
        self._login('operator')
        resp = self.client.get('/rbac/users')
        self.assertEqual(resp.status_code, 403)

    def test_admin_create_and_list_users(self):
        self._login('admin')
        resp = self.client.post(
            '/rbac/users/add',
            data={
                'username': 'alice',
                'role': 'viewer',
                'group_ids': str(self.group_id),
            },
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertEqual(payload.get('errcode'), 0)
        self.assertEqual(payload.get('url'), '/rbac/users')
        resp = self.client.get('/rbac/users')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn('alice', body)
        self.assertIn('待重置', body)
        with self.app.app_context():
            from sqlalchemy import select
            from datas.model.rbac_user import RbacUser
            from app.rbac.services import DEFAULT_USER_PASSWORD
            alice = self.db.session.scalars(
                select(RbacUser).where(RbacUser.username == 'alice')
            ).first()
            self.assertIsNotNone(alice)
            self.assertEqual(alice.must_reset_password, 1)
            self.assertTrue(alice.check_password(DEFAULT_USER_PASSWORD))

    def test_add_form_has_ajax_submit_button(self):
        self._login('admin')
        resp = self.client.get('/rbac/users/add')
        body = resp.get_data(as_text=True)
        self.assertIn('js-ajax-form', body)
        self.assertIn('js-ajax-submit', body)
        self.assertIn('changeme', body)
        self.assertNotIn('name="password"', body)

    def test_native_post_add_redirects_to_list(self):
        """无 Ajax 头时成功应 302 回列表，避免浏览器落在裸 JSON 页。"""
        self._login('admin')
        resp = self.client.post(
            '/rbac/users/add',
            data={
                'username': 'bob',
                'role': 'viewer',
                'group_ids': str(self.group_id),
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/rbac/users', resp.headers['Location'])

    def test_edit_role_keeps_existing_group_without_unique_conflict(self):
        from sqlalchemy import select
        from datas.model.rbac_user import RbacUser
        from datas.model.user_group import UserGroup

        with self.app.app_context():
            user = RbacUser(username='davy', role='viewer', is_active=1, create_time='t')
            user.set_password('x')
            self.db.session.add(user)
            self.db.session.commit()
            user_id = user.id
            self.db.session.add(UserGroup(user_id=user_id, group_id=self.group_id))
            self.db.session.commit()

        self._login('admin', user_id=999)
        resp = self.client.post(
            '/rbac/users/edit',
            data={
                'id': str(user_id),
                'role': 'operator',
                'is_active': '1',
                'group_ids': str(self.group_id),
            },
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json().get('errcode'), 0)
        with self.app.app_context():
            user = self.db.session.get(RbacUser, user_id)
            rows = self.db.session.scalars(
                select(UserGroup).where(UserGroup.user_id == user_id)
            ).all()
            self.assertEqual(user.role, 'operator')
            self.assertEqual([row.group_id for row in rows], [self.group_id])

    def test_cannot_disable_last_admin(self):
        from datas.model.rbac_user import RbacUser

        with self.app.app_context():
            admin = RbacUser(username='solo', role='admin', is_active=1, create_time='t')
            admin.set_password('x')
            self.db.session.add(admin)
            self.db.session.commit()
            admin_id = admin.id

        self._login('admin', user_id=999)
        resp = self.client.post(
            '/rbac/users/edit',
            data={
                'id': str(admin_id),
                'role': 'viewer',
                'is_active': '1',
                'group_ids': str(self.group_id),
            },
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('最后一名', resp.get_json().get('errmsg', ''))

    def test_cannot_disable_self(self):
        from datas.model.rbac_user import RbacUser

        with self.app.app_context():
            a1 = RbacUser(username='a1', role='admin', is_active=1, create_time='t')
            a1.set_password('x')
            a2 = RbacUser(username='a2', role='admin', is_active=1, create_time='t')
            a2.set_password('x')
            self.db.session.add_all([a1, a2])
            self.db.session.commit()
            self_id = a1.id

        self._login('admin', user_id=self_id)
        edit = self.client.post(
            '/rbac/users/edit',
            data={'id': str(self_id), 'role': 'admin', 'is_active': '0'},
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(edit.status_code, 200)
        self.assertIn('修改密码', edit.get_json().get('errmsg', ''))
        resp = self.client.post(
            '/rbac/users/set_active',
            data={'id': str(self_id), 'is_active': '0', 'reason': '自测停用'},
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('当前登录', resp.get_json().get('errmsg', ''))


class TestForcedPasswordReset(unittest.TestCase):
    """新建用户强制改密 + 管理员触发重置。"""

    def setUp(self):
        app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        app.secret_key = 'test'
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        from app import db
        db.init_app(app)
        app.register_blueprint(main_blueprint)
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(rbac_blueprint)
        self.app = app
        self.client = app.test_client()
        self.db = db
        with app.app_context():
            from datas.model.rbac_user import RbacUser
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            from datas.model.resource_group import ResourceGroup
            from datas.model.user_group import UserGroup  # noqa: F401
            db.create_all()
            g = ResourceGroup(
                name='Default',
                code='default',
                description='',
                create_time='t',
            )
            db.session.add(g)
            admin = RbacUser(
                username='mgr',
                role='admin',
                is_active=1,
                must_reset_password=0,
                create_time='t',
            )
            admin.set_password('admin-pass')
            existing = RbacUser(
                username='oldie',
                role='viewer',
                is_active=1,
                must_reset_password=0,
                create_time='t',
            )
            existing.set_password('oldie-pass')
            db.session.add_all([admin, existing])
            db.session.commit()
            self.group_id = g.id
            self.admin_id = admin.id
            self.existing_id = existing.id

    def _login_session(self, username, role, user_id, group_ids=None):
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['username'] = username
            sess['role'] = role
            sess['user_id'] = user_id
            sess['group_ids'] = list(group_ids or [])

    def test_existing_user_not_migrated_to_force_reset(self):
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            u = self.db.session.get(RbacUser, self.existing_id)
            self.assertEqual(u.must_reset_password, 0)
        resp = self.client.post(
            '/rbac/login',
            data={'username': 'oldie', 'password': 'oldie-pass', 'next': '/cron_list'},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/cron_list', resp.headers['Location'])

    def test_new_user_login_forces_password_change(self):
        from app.rbac.services import DEFAULT_USER_PASSWORD

        self._login_session('mgr', 'admin', self.admin_id)
        resp = self.client.post(
            '/rbac/users/add',
            data={
                'username': 'newbie',
                'role': 'viewer',
                'group_ids': str(self.group_id),
                'password': 'ignored-secret',
            },
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(resp.get_json().get('errcode'), 0)
        with self.client.session_transaction() as sess:
            sess.clear()
        login = self.client.post(
            '/rbac/login',
            data={
                'username': 'newbie',
                'password': DEFAULT_USER_PASSWORD,
                'next': '/cron_list',
            },
        )
        self.assertEqual(login.status_code, 302)
        self.assertIn('/rbac/password', login.headers['Location'])
        blocked = self.client.get('/cron_list')
        self.assertEqual(blocked.status_code, 302)
        self.assertIn('/rbac/password', blocked.headers['Location'])
        form = self.client.get('/rbac/password')
        self.assertEqual(form.status_code, 200)
        body = form.get_data(as_text=True)
        self.assertIn('须先修改密码', body)
        self.assertNotIn('返回任务中心', body)

    def test_failed_reset_keeps_force_and_success_clears(self):
        from app.rbac.services import DEFAULT_USER_PASSWORD, create_user, set_user_groups

        with self.app.app_context():
            created = create_user('force_me', 'viewer')
            self.assertTrue(created['ok'])
            set_user_groups(created['user_id'], [self.group_id], role='viewer')
            user_id = created['user_id']

        login = self.client.post(
            '/rbac/login',
            data={'username': 'force_me', 'password': DEFAULT_USER_PASSWORD},
        )
        self.assertIn('/rbac/password', login.headers['Location'])
        fail = self.client.post(
            '/rbac/password',
            data={
                'old_password': 'wrong',
                'new_password': 'newpass1',
                'confirm_password': 'newpass1',
            },
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(fail.get_json().get('errcode'), 1)
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            u = self.db.session.get(RbacUser, user_id)
            self.assertEqual(u.must_reset_password, 1)
        blocked = self.client.get('/cron_list')
        self.assertEqual(blocked.status_code, 302)
        self.assertIn('/rbac/password', blocked.headers['Location'])

        ok = self.client.post(
            '/rbac/password',
            data={
                'old_password': DEFAULT_USER_PASSWORD,
                'new_password': 'newpass1',
                'confirm_password': 'newpass1',
            },
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(ok.get_json().get('errcode'), 0)
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            u = self.db.session.get(RbacUser, user_id)
            self.assertEqual(u.must_reset_password, 0)
            self.assertTrue(u.check_password('newpass1'))
        relogin = self.client.post(
            '/rbac/login',
            data={'username': 'force_me', 'password': 'newpass1', 'next': '/cron_list'},
        )
        self.assertEqual(relogin.status_code, 302)
        self.assertIn('/cron_list', relogin.headers['Location'])
        self.assertEqual(self.client.get('/cron_list').status_code, 200)

    def test_admin_trigger_reset_restricts_active_session(self):
        from app.rbac.services import DEFAULT_USER_PASSWORD

        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            target = RbacUser(
                username='session_user',
                role='operator',
                is_active=1,
                must_reset_password=0,
                create_time='t',
            )
            target.set_password('live-pass')
            self.db.session.add(target)
            self.db.session.commit()
            target_id = target.id

        self._login_session('session_user', 'operator', target_id, [self.group_id])
        self.assertEqual(self.client.get('/cron_list').status_code, 200)

        admin_client = self.app.test_client()
        with admin_client.session_transaction() as sess:
            sess['is_login'] = True
            sess['username'] = 'mgr'
            sess['role'] = 'admin'
            sess['user_id'] = self.admin_id
            sess['group_ids'] = []
        reset = admin_client.post(
            '/rbac/users/reset_password?id=%s' % target_id,
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(reset.get_json().get('errcode'), 0)
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            u = self.db.session.get(RbacUser, target_id)
            self.assertEqual(u.must_reset_password, 1)
            self.assertTrue(u.check_password(DEFAULT_USER_PASSWORD))
            self.assertFalse(u.check_password('live-pass'))

        blocked = self.client.get('/cron_list')
        self.assertEqual(blocked.status_code, 302)
        self.assertIn('/rbac/password', blocked.headers['Location'])
        ajax_blocked = self.client.get(
            '/cron_list',
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(ajax_blocked.get_json().get('errcode'), 1)
        self.assertIn('/rbac/password', ajax_blocked.get_json().get('url', ''))

    def test_admin_cannot_reset_self(self):
        self._login_session('mgr', 'admin', self.admin_id)
        resp = self.client.post(
            '/rbac/users/reset_password?id=%s' % self.admin_id,
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(resp.get_json().get('errcode'), 1)
        self.assertIn('当前登录', resp.get_json().get('errmsg', ''))

    def test_edit_ignores_password_field(self):
        self._login_session('mgr', 'admin', self.admin_id)
        resp = self.client.post(
            '/rbac/users/edit',
            data={
                'id': str(self.existing_id),
                'role': 'viewer',
                'is_active': '1',
                'group_ids': str(self.group_id),
                'password': 'hacked-pass',
            },
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(resp.get_json().get('errcode'), 0)
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            u = self.db.session.get(RbacUser, self.existing_id)
            self.assertTrue(u.check_password('oldie-pass'))
            self.assertFalse(u.check_password('hacked-pass'))
            self.assertEqual(u.must_reset_password, 0)

    def test_users_list_shows_reset_and_reactivate_actions(self):
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            disabled = RbacUser(
                username='paused',
                role='viewer',
                is_active=0,
                must_reset_password=1,
                status_reason='请假停用',
                create_time='t',
            )
            disabled.set_password('x')
            self.db.session.add(disabled)
            self.db.session.commit()
            disabled_id = disabled.id

        self._login_session('mgr', 'admin', self.admin_id)
        html = self.client.get('/rbac/users').get_data(as_text=True)
        self.assertIn('重置密码', html)
        self.assertIn('/rbac/users/reset_password?id=', html)
        self.assertIn('恢复启用', html)
        self.assertTrue(
            ('/rbac/users/set_active?id=%s&is_active=1' % disabled_id) in html
            or ('/rbac/users/set_active?id=%s&amp;is_active=1' % disabled_id) in html
        )
        self.assertIn('user-row-inactive', html)
        self.assertIn('user-status-reset', html)
        self.assertIn('待重置', html)
        self.assertIn('请假停用', html)
        self.assertIn('btn-info', html)
        # 编辑在操作列末尾（他人行）；当前用户仅「修改密码」
        reset_pos = html.find('重置密码')
        edit_pos = html.rfind('>编辑</a>')
        self.assertGreater(edit_pos, reset_pos)
        self.assertIn('修改密码', html)
        self.assertIn('/rbac/password', html)
        self.assertIn('账号/角色/业务组不可自改', html)

    def test_cannot_edit_self_via_users_edit(self):
        self._login_session('mgr', 'admin', self.admin_id)
        resp = self.client.get(
            '/rbac/users/edit?id=%s' % self.admin_id,
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(resp.get_json().get('errcode'), 1)
        self.assertIn('修改密码', resp.get_json().get('errmsg', ''))
        self.assertIn('/rbac/password', resp.get_json().get('url', ''))
        post = self.client.post(
            '/rbac/users/edit',
            data={
                'id': str(self.admin_id),
                'role': 'viewer',
                'is_active': '1',
                'group_ids': str(self.group_id),
            },
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(post.get_json().get('errcode'), 1)
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            u = self.db.session.get(RbacUser, self.admin_id)
            self.assertEqual(u.role, 'admin')

    def test_set_active_requires_reason_and_can_reactivate(self):
        self._login_session('mgr', 'admin', self.admin_id)
        form = self.client.get(
            '/rbac/users/set_active?id=%s&is_active=0' % self.existing_id
        )
        self.assertEqual(form.status_code, 200)
        body = form.get_data(as_text=True)
        self.assertIn('停用缘由', body)
        self.assertIn('js-ajax-submit', body)

        missing = self.client.post(
            '/rbac/users/set_active',
            data={'id': str(self.existing_id), 'is_active': '0', 'reason': ''},
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(missing.get_json().get('errcode'), 1)
        self.assertIn('缘由', missing.get_json().get('errmsg', ''))

        disable = self.client.post(
            '/rbac/users/set_active',
            data={
                'id': str(self.existing_id),
                'is_active': '0',
                'reason': '违规操作暂停',
            },
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(disable.get_json().get('errcode'), 0)
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            from datas.model.rbac_audit_log import RbacAuditLog
            from sqlalchemy import select
            u = self.db.session.get(RbacUser, self.existing_id)
            self.assertEqual(u.is_active, 0)
            self.assertEqual(u.status_reason, '违规操作暂停')
            row = self.db.session.scalars(
                select(RbacAuditLog).where(RbacAuditLog.action == 'user:disable')
            ).first()
            self.assertIsNotNone(row)
            self.assertIn('违规操作暂停', row.resource or '')

        enable = self.client.post(
            '/rbac/users/set_active',
            data={
                'id': str(self.existing_id),
                'is_active': '1',
                'reason': '问题已处理，恢复使用',
            },
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(enable.get_json().get('errcode'), 0)
        with self.app.app_context():
            from datas.model.rbac_user import RbacUser
            u = self.db.session.get(RbacUser, self.existing_id)
            self.assertEqual(u.is_active, 1)
            self.assertEqual(u.status_reason, '问题已处理，恢复使用')

    def test_cannot_disable_self_via_set_active(self):
        self._login_session('mgr', 'admin', self.admin_id)
        resp = self.client.post(
            '/rbac/users/set_active',
            data={
                'id': str(self.admin_id),
                'is_active': '0',
                'reason': '自测停用',
            },
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(resp.get_json().get('errcode'), 1)
        self.assertIn('当前登录', resp.get_json().get('errmsg', ''))


class TestRbacAuditLogs(unittest.TestCase):
    def setUp(self):
        app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        app.secret_key = 'test'
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        from app import db
        db.init_app(app)
        app.register_blueprint(main_blueprint)
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(rbac_blueprint)
        self.app = app
        self.client = app.test_client()
        self.db = db
        with app.app_context():
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            db.create_all()

    def _login(self, role='admin'):
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['role'] = role
            sess['username'] = role

    def test_operator_audit_logs_403(self):
        self._login('operator')
        resp = self.client.get('/rbac/audit-logs')
        self.assertEqual(resp.status_code, 403)

    def test_admin_lists_audit_rows(self):
        from datas.model.rbac_audit_log import RbacAuditLog

        with self.app.app_context():
            self.db.session.add(
                RbacAuditLog(
                    username='admin',
                    user_id=1,
                    action='user:login',
                    resource='admin',
                    ip='127.0.0.1',
                    status='allow',
                    create_time='2026-07-14 10:00:00',
                )
            )
            self.db.session.commit()

        self._login('admin')
        resp = self.client.get('/rbac/audit-logs')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn('登录', body)
        self.assertIn('用户 ID', body)
        self.assertIn('账号 admin', body)
        self.assertIn('<td>1</td>', body)
        self.assertNotIn('js-ajax-form', body)
        self.assertNotIn('legacy_admin', body)

    def test_audit_labels_unit(self):
        from app.rbac.services import (
            audit_action_label,
            audit_resource_label,
            audit_status_label,
        )
        self.assertEqual(audit_action_label('user:login'), '登录')
        self.assertEqual(audit_status_label('deny'), '拒绝')
        self.assertEqual(
            audit_resource_label('permission:deny', 'user:manage'),
            '缺少权限 user:manage',
        )
        self.assertEqual(audit_action_label('unknown:x'), 'unknown:x')


class TestRbacTriangularAcceptance(unittest.TestCase):
    """阶段 7：viewer / operator / admin 真实登录矩阵。"""

    def setUp(self):
        app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        app.secret_key = 'test'
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        from app import db
        db.init_app(app)
        app.register_blueprint(main_blueprint)
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(rbac_blueprint)
        self.app = app
        self.client = app.test_client()
        self.db = db
        app.config['CRON_CONFIG'] = {'is_dev': '0'}
        with app.app_context():
            from datas.model.rbac_user import RbacUser
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            from datas.model.cron_infos import CronInfos  # noqa: F401
            from datas.model.resource_group import ResourceGroup  # noqa: F401
            from datas.model.user_group import UserGroup  # noqa: F401
            from datas.model.operation_log import OperationLog  # noqa: F401
            db.create_all()
            for name, role, pwd in (
                ('tri_admin', 'admin', 'admin-pass'),
                ('tri_op', 'operator', 'op-pass'),
                ('tri_view', 'viewer', 'view-pass'),
            ):
                u = RbacUser(username=name, role=role, is_active=1, create_time='t')
                u.set_password(pwd)
                db.session.add(u)
            db.session.commit()

    def _login(self, username, password):
        with self.client.session_transaction() as sess:
            sess.clear()
        return self.client.post(
            '/rbac/login',
            data={'username': username, 'password': password, 'next': '/cron_list'},
        )

    def test_viewer_operator_admin_route_matrix(self):
        # viewer：只读
        self.assertEqual(self._login('tri_view', 'view-pass').status_code, 302)
        self.assertEqual(self.client.get('/cron_list').status_code, 200)
        self.assertEqual(self.client.get('/cron_add').status_code, 403)
        self.assertEqual(self.client.get('/cron_retire?id=1').status_code, 403)
        self.assertEqual(self.client.get('/rbac/users').status_code, 403)
        self.assertEqual(self.client.get('/rbac/audit-logs').status_code, 403)
        self.assertEqual(self.client.get('/operation_log_list').status_code, 403)

        # operator：可写任务 + 操作记录；不可退休/管用户/RBAC 审计
        self.assertEqual(self._login('tri_op', 'op-pass').status_code, 302)
        self.assertEqual(self.client.get('/cron_list').status_code, 200)
        self.assertEqual(self.client.get('/cron_add').status_code, 200)
        self.assertEqual(self.client.get('/cron_retire?id=1').status_code, 403)
        self.assertEqual(self.client.get('/rbac/users').status_code, 403)
        self.assertEqual(self.client.get('/rbac/audit-logs').status_code, 403)
        self.assertEqual(self.client.get('/operation_log_list').status_code, 200)

        # admin：用户管理 + RBAC 审计 + 操作记录
        self.assertEqual(self._login('tri_admin', 'admin-pass').status_code, 302)
        self.assertEqual(self.client.get('/cron_add').status_code, 200)
        self.assertEqual(self.client.get('/rbac/users').status_code, 200)
        self.assertEqual(self.client.get('/rbac/audit-logs').status_code, 200)
        self.assertEqual(self.client.get('/operation_log_list').status_code, 200)
        list_html = self.client.get('/cron_list').get_data(as_text=True)
        self.assertIn('用户管理', list_html)
        self.assertIn('审计', list_html)
        self.assertIn('操作记录', list_html)
        self.assertEqual(self._login('tri_op', 'op-pass').status_code, 302)
        op_list = self.client.get('/cron_list').get_data(as_text=True)
        self.assertIn('操作记录', op_list)
        self.assertNotIn('用户管理', op_list)
        self.assertNotIn('/rbac/audit-logs', op_list)


class TestRbacPolicy(unittest.TestCase):
    def test_viewer_cannot_write(self):
        self.assertFalse(has_permission('viewer', 'cron:write'))

    def test_operator_cannot_retire_cron(self):
        self.assertFalse(has_permission('operator', 'cron:retire'))

    def test_admin_has_retire(self):
        self.assertTrue(has_permission('admin', 'cron:retire'))

    def test_admin_has_user_manage(self):
        self.assertTrue(has_permission('admin', 'user:manage'))

    def test_admin_has_audit_read(self):
        self.assertTrue(has_permission('admin', 'audit:read'))

    def test_operator_has_operation_read_not_audit(self):
        self.assertTrue(has_permission('operator', 'operation:read'))
        self.assertFalse(has_permission('operator', 'audit:read'))
        self.assertFalse(has_permission('operator', 'user:manage'))

    def test_viewer_no_operation_or_audit(self):
        self.assertFalse(has_permission('viewer', 'operation:read'))
        self.assertFalse(has_permission('viewer', 'audit:read'))
        self.assertFalse(has_permission('viewer', 'user:manage'))

    def test_no_delete_permissions(self):
        self.assertFalse(has_permission('admin', 'cron:delete'))
        self.assertFalse(has_permission('operator', 'log:delete'))


class TestMakeHasPerm(unittest.TestCase):
    def test_has_perm_respects_role(self):
        app = Flask(__name__)
        app.secret_key = 'test'
        app.config['TESTING'] = True
        with app.test_request_context():
            session['role'] = 'viewer'
            has_perm = make_has_perm()
            self.assertTrue(has_perm('cron:read'))
            self.assertFalse(has_perm('cron:write'))
            self.assertFalse(has_perm('cron:retire'))

    def test_rbac_enabled_uses_preloaded_set(self):
        app = Flask(__name__)
        app.secret_key = 'test'
        app.config['TESTING'] = True
        with app.test_request_context():
            session['role'] = 'viewer'
            with patch('app.rbac.context.get_role_permission_set', return_value={'cron:read'}) as mocked_perms:
                has_perm = make_has_perm()
                self.assertTrue(has_perm('cron:read'))
                self.assertFalse(has_perm('cron:write'))
                for _ in range(198):
                    has_perm('cron:read')
                mocked_perms.assert_called_once_with('viewer', username='')

    def test_admin_permission_set(self):
        perms = get_role_permission_set('admin')
        self.assertIn('user:manage', perms)
        self.assertIn('operation:read', perms)
        self.assertIn('audit:read', perms)
        self.assertIn('cron:write', perms)


class TestSeedAdminPermissions(unittest.TestCase):
    """种子用户名 admin：只读 + 用户管理；任务写/下线须非种子的 admin 角色用户。"""

    def test_seed_username_strips_write_and_retire(self):
        from app.rbac.policy import has_permission

        self.assertTrue(has_permission('admin', 'user:manage', username='admin'))
        self.assertTrue(has_permission('admin', 'cron:read', username='admin'))
        self.assertTrue(has_permission('admin', 'audit:read', username='admin'))
        self.assertFalse(has_permission('admin', 'cron:write', username='admin'))
        self.assertFalse(has_permission('admin', 'cron:retire', username='admin'))

    def test_created_admin_keeps_full_matrix(self):
        from app.rbac.policy import has_permission

        self.assertTrue(has_permission('admin', 'cron:write', username='ops_admin'))
        self.assertTrue(has_permission('admin', 'cron:retire', username='ops_admin'))
        self.assertTrue(has_permission('admin', 'user:manage', username='ops_admin'))


class TestUserTopbar(unittest.TestCase):
    """管理端顶栏：身份 / 角色 / Scope / 退出。"""

    def setUp(self):
        app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        app.secret_key = 'test'
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        from app import db
        db.init_app(app)
        app.register_blueprint(main_blueprint)
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(rbac_blueprint)
        self.app = app
        self.client = app.test_client()
        self.db = db
        with app.app_context():
            from datas.model.rbac_user import RbacUser  # noqa: F401
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            from datas.model.resource_group import ResourceGroup
            db.create_all()
            g = ResourceGroup(
                name='支付业务',
                code='pay',
                description='',
                create_time='t',
            )
            db.session.add(g)
            db.session.commit()
            self.group_id = g.id

    def _login(self, role='admin', username='u1', group_ids=None):
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['username'] = username
            sess['role'] = role
            sess['user_id'] = 1
            sess['group_ids'] = list(group_ids or [])

    def test_admin_shows_no_scope_labels(self):
        self._login('admin', 'summer', group_ids=[self.group_id])
        resp = self.client.get('/rbac/password')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn('rbac-topbar', body)
        self.assertIn('topbar-identity', body)
        self.assertIn('summer', body)
        self.assertIn('业务管理员', body)
        self.assertIn('topbar-role-admin', body)
        self.assertNotIn('系统管理员', body)
        self.assertNotIn('全局可见', body)
        self.assertNotIn('支付业务', body)
        self.assertNotIn('未分配业务组', body)
        self.assertIn('/rbac/logout', body)
        self.assertEqual(body.count('退出'), 1)
        self.assertNotIn('href="/logout"', body)

    def test_seed_admin_shows_system_admin_label(self):
        self._login('admin', 'admin', group_ids=[])
        resp = self.client.get('/rbac/password')
        body = resp.get_data(as_text=True)
        self.assertIn('系统管理员', body)
        self.assertIn('topbar-role-seed', body)
        self.assertNotIn('业务管理员', body)

    def test_operator_with_groups_shows_names(self):
        self._login('operator', 'op1', group_ids=[self.group_id])
        resp = self.client.get('/rbac/password')
        body = resp.get_data(as_text=True)
        self.assertIn('operator', body)
        self.assertIn('支付业务', body)
        self.assertNotIn('全局可见', body)
        self.assertNotIn('未分配业务组', body)
        self.assertNotIn('操作员', body)

    def test_operator_without_groups_warns(self):
        self._login('operator', 'op2', group_ids=[])
        resp = self.client.get('/rbac/password')
        body = resp.get_data(as_text=True)
        self.assertIn('未分配业务组', body)
        self.assertNotIn('全局可见', body)

    def test_guest_404_has_no_topbar(self):
        resp = self.client.get('/no-such-page-xyz')
        self.assertEqual(resp.status_code, 404)
        body = resp.get_data(as_text=True)
        self.assertNotIn('class="rbac-topbar"', body)
        self.assertIn('前往登录', body)

    def test_get_current_user_groups_uses_session_ids(self):
        from app.rbac.context import get_current_user_groups

        with self.app.test_request_context():
            session['is_login'] = True
            session['role'] = 'operator'
            session['group_ids'] = [self.group_id]
            groups = get_current_user_groups()
            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0]['name'], '支付业务')
            # 请求内缓存
            session['group_ids'] = []
            self.assertEqual(get_current_user_groups()[0]['name'], '支付业务')


if __name__ == '__main__':
    unittest.main()
