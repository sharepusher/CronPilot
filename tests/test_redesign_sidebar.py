# -*- coding:utf-8 -*-
"""OPT-P1-16 Redesign Sidebar — 角色权限导航回归测试。

验证新界面侧边栏在不同角色下的导航可见性：
  - Seed Admin：全部 12 项可见
  - Biz Admin：全部 12 项可见
  - Operator：7 项可见（含操作记录，无系统配置/管理）
  - Viewer：6 项可见（最小只读集，含个人资料）

本测试属于回归门禁，任何侧边栏权限逻辑修改后必须通过。
"""
import os
import re
import sys
import unittest

from flask import Flask, session

from app import register_hms_filters

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)


# Navigation items expected per role
ADMIN_NAV = {
    '任务中心', '执行记录',
    '业务组', '标签',
    '用户管理', '注册审批', '审计', '操作记录',
    '个人资料', '修改密码', 'API Token', 'API 文档',
}

OPERATOR_NAV = {
    '任务中心', '执行记录',
    '操作记录',
    '个人资料', '修改密码', 'API Token', 'API 文档',
}

VIEWER_NAV = {
    '任务中心', '执行记录',
    '个人资料', '修改密码', 'API Token', 'API 文档',
}


class TestRedesignSidebarPermissions(unittest.TestCase):
    """回归测试：redesign 侧边栏导航与 RBAC 权限一致性。

    使用纯模板渲染（不启动 scheduler / 不连接数据库），
    通过模拟 session 验证 has_perm 门控逻辑。
    """

    @classmethod
    def setUpClass(cls):
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
        register_hms_filters(app)

        from app.main import main as main_blueprint
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(main_blueprint)
        app.register_blueprint(rbac_blueprint)

        cls.app = app
        cls.db = db

        with app.app_context():
            from datas.model.rbac_user import RbacUser  # noqa: F401
            from datas.model.resource_group import ResourceGroup  # noqa: F401
            from datas.model.user_group import UserGroup  # noqa: F401
            from datas.model.cron_infos import CronInfos  # noqa: F401
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            from datas.model.task_group import TaskGroup  # noqa: F401
            from datas.model.tag import Tag  # noqa: F401
            from datas.model.task_tag import TaskTag  # noqa: F401
            from datas.model.job_log import JobLog  # noqa: F401
            from datas.model.operation_log import OperationLog  # noqa: F401
            db.create_all()
            cls._seed()

    @classmethod
    def _seed(cls):
        from datas.model.rbac_user import RbacUser
        from datas.model.resource_group import ResourceGroup
        from datas.model.user_group import UserGroup
        from datas.utils.times import utc_now_hms

        from werkzeug.security import generate_password_hash

        now = utc_now_hms()
        pw = generate_password_hash('test123')
        grp = ResourceGroup(name='TestGroup', description='测试组', create_time=now)
        cls.db.session.add(grp)
        cls.db.session.flush()

        users = [
            RbacUser(username='seed_admin', password_hash=pw, role='admin', is_active=1, create_time=now),
            RbacUser(username='biz_admin', password_hash=pw, role='admin', is_active=1, create_time=now),
            RbacUser(username='test_operator', password_hash=pw, role='operator', is_active=1, create_time=now),
            RbacUser(username='test_viewer', password_hash=pw, role='viewer', is_active=1, create_time=now),
        ]
        for u in users:
            cls.db.session.add(u)
        cls.db.session.flush()

        # Assign biz_admin and operator to group
        for u in users[1:3]:
            ug = UserGroup(user_id=u.id, group_id=grp.id)
            cls.db.session.add(ug)

        cls.db.session.commit()
        cls.users = {u.username: u for u in users}

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            cls.db.drop_all()

    def _render_sidebar(self, username):
        """模拟用户登录后渲染侧边栏，提取可见导航链接文本。"""
        user = self.users[username]
        with self.app.test_request_context('/'):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            session['is_login'] = True
            session['group_ids'] = []

            from app.rbac.context import make_has_perm

            has_perm = make_has_perm()

            rendered = self.app.jinja_env.get_template(
                'redesign/_sidebar.html'
            ).render(
                active_nav='dashboard',
                pending_reg_count=0,
                has_perm=has_perm,
                url_for=self.app.jinja_env.globals['url_for'],
            )

            # Extract link text from <span> inside cp-nav-item links
            links = re.findall(r'class="cp-nav-item[^"]*"[^>]*>\s*(?:<svg[^>]*>.*?</svg>\s*)?<span>(.*?)</span>', rendered, re.DOTALL)
            return set(links)

    def test_seed_admin_sees_all_nav(self):
        """Seed admin 应看到全部 11 个导航项。"""
        nav = self._render_sidebar('seed_admin')
        self.assertEqual(nav, ADMIN_NAV,
                         f"Seed admin nav mismatch.\n  Missing: {ADMIN_NAV - nav}\n  Extra: {nav - ADMIN_NAV}")

    def test_biz_admin_sees_all_nav(self):
        """Biz admin（带组分配）应看到全部 11 个导航项。"""
        nav = self._render_sidebar('biz_admin')
        self.assertEqual(nav, ADMIN_NAV,
                         f"Biz admin nav mismatch.\n  Missing: {ADMIN_NAV - nav}\n  Extra: {nav - ADMIN_NAV}")

    def test_operator_sees_limited_nav(self):
        """Operator 应只看到 6 个导航项（无系统配置/管理）。"""
        nav = self._render_sidebar('test_operator')
        self.assertEqual(nav, OPERATOR_NAV,
                         f"Operator nav mismatch.\n  Missing: {OPERATOR_NAV - nav}\n  Extra: {nav - OPERATOR_NAV}")

    def test_viewer_sees_minimal_nav(self):
        """Viewer 应只看到 5 个导航项（最小只读集）。"""
        nav = self._render_sidebar('test_viewer')
        self.assertEqual(nav, VIEWER_NAV,
                         f"Viewer nav mismatch.\n  Missing: {VIEWER_NAV - nav}\n  Extra: {nav - VIEWER_NAV}")

    def test_operator_no_admin_items(self):
        """Operator 不应看到任何管理项。"""
        nav = self._render_sidebar('test_operator')
        admin_only = {'用户管理', '注册审批', '审计', '业务组', '标签'}
        self.assertEqual(nav & admin_only, set(),
                         f"Operator sees admin items: {nav & admin_only}")

    def test_viewer_no_operation_log(self):
        """Viewer 不应看到操作记录（需 operation:read）。"""
        nav = self._render_sidebar('test_viewer')
        self.assertNotIn('操作记录', nav)


class TestRedesignSidebarHTTPAccess(unittest.TestCase):
    """回归测试：通过 HTTP 请求验证角色反向路径（403 拦截）。"""

    @classmethod
    def setUpClass(cls):
        app = Flask(
            __name__,
            template_folder=os.path.join(ROOT, 'app', 'templates'),
            static_folder=os.path.join(ROOT, 'app', 'static'),
        )
        app.secret_key = 'test'
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['CRON_CONFIG'] = {
            'is_dev': '0',
            'block_private_ip': '0',
            'url_allow_hosts': '',
            'url_ssrf_observe_only': '1',
        }

        from app import db
        db.init_app(app)
        register_hms_filters(app)

        from app.main import main as main_blueprint
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(main_blueprint)
        app.register_blueprint(rbac_blueprint)

        cls.app = app
        cls.db = db

        with app.app_context():
            from datas.model.rbac_user import RbacUser  # noqa: F401
            from datas.model.resource_group import ResourceGroup  # noqa: F401
            from datas.model.user_group import UserGroup  # noqa: F401
            from datas.model.cron_infos import CronInfos  # noqa: F401
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            from datas.model.task_group import TaskGroup  # noqa: F401
            from datas.model.tag import Tag  # noqa: F401
            from datas.model.task_tag import TaskTag  # noqa: F401
            from datas.model.job_log import JobLog  # noqa: F401
            from datas.model.operation_log import OperationLog  # noqa: F401
            db.create_all()
            cls._seed()

    @classmethod
    def _seed(cls):
        from datas.model.rbac_user import RbacUser
        from datas.model.resource_group import ResourceGroup
        from datas.model.user_group import UserGroup
        from datas.utils.times import utc_now_hms

        from werkzeug.security import generate_password_hash

        now = utc_now_hms()
        pw = generate_password_hash('test123')
        grp = ResourceGroup(name='TestGroup2', description='测试组', create_time=now)
        cls.db.session.add(grp)
        cls.db.session.flush()

        users = [
            RbacUser(username='admin2', password_hash=pw, role='admin', is_active=1, create_time=now),
            RbacUser(username='op2', password_hash=pw, role='operator', is_active=1, create_time=now),
            RbacUser(username='viewer2', password_hash=pw, role='viewer', is_active=1, create_time=now),
        ]
        for u in users:
            cls.db.session.add(u)
        cls.db.session.flush()

        ug = UserGroup(user_id=users[1].id, group_id=grp.id)
        cls.db.session.add(ug)
        cls.db.session.commit()
        cls.users = {u.username: u for u in users}

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            cls.db.drop_all()

    def _login_client(self, username):
        """返回已登录的 test_client。"""
        client = self.app.test_client()
        user = self.users[username]
        with client.session_transaction() as sess:
            sess['user_id'] = user.id
            sess['username'] = user.username
            sess['role'] = user.role
            sess['is_login'] = True
            sess['group_ids'] = []
        return client

    def test_viewer_denied_cron_add(self):
        """Viewer 访问 /cron_add 应返回 403。"""
        client = self._login_client('viewer2')
        resp = client.get('/cron_add')
        self.assertEqual(resp.status_code, 403)

    def test_viewer_denied_users_list(self):
        """Viewer 访问 /rbac/users 应返回 403。"""
        client = self._login_client('viewer2')
        resp = client.get('/rbac/users')
        self.assertEqual(resp.status_code, 403)

    def test_viewer_denied_operation_log(self):
        """Viewer 访问 /operation_log_list 应返回 403。"""
        client = self._login_client('viewer2')
        resp = client.get('/operation_log_list')
        self.assertEqual(resp.status_code, 403)

    def test_operator_denied_users_list(self):
        """Operator 访问 /rbac/users 应返回 403。"""
        client = self._login_client('op2')
        resp = client.get('/rbac/users')
        self.assertEqual(resp.status_code, 403)

    def test_operator_allowed_cron_add(self):
        """Operator 有 cron:write，访问 /cron_add 应返回 200。"""
        client = self._login_client('op2')
        resp = client.get('/cron_add')
        self.assertIn(resp.status_code, [200, 302])

    def test_admin_allowed_users_list(self):
        """Admin 有 user:manage，访问 /rbac/users 应返回 200。"""
        client = self._login_client('admin2')
        resp = client.get('/rbac/users')
        self.assertEqual(resp.status_code, 200)


if __name__ == '__main__':
    unittest.main()
