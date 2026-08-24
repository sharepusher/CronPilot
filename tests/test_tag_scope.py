"""Tests for tag CRUD scope enforcement (S3 security fix)."""

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from flask import Flask


class TestTagScope(unittest.TestCase):

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
        app.config['CRON_CONFIG'] = {
            'is_dev': '0',
            'block_private_ip': '0',
            'url_allow_hosts': '',
            'url_ssrf_observe_only': '1',
        }
        from app import db
        db.init_app(app)
        from app.main import main as main_blueprint
        from app.rbac import rbac as rbac_blueprint
        app.register_blueprint(main_blueprint)
        app.register_blueprint(rbac_blueprint)
        self.app = app
        self.db = db
        self.client = app.test_client()
        with app.app_context():
            from datas.model.cron_infos import CronInfos  # noqa: F401
            from datas.model.rbac_user import RbacUser  # noqa: F401
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            from datas.model.resource_group import ResourceGroup  # noqa: F401
            from datas.model.user_group import UserGroup  # noqa: F401
            from datas.model.task_group import TaskGroup  # noqa: F401
            from datas.model.tag import Tag  # noqa: F401
            from datas.model.task_tag import TaskTag  # noqa: F401
            from datas.model.job_log import JobLog  # noqa: F401
            from datas.model.operation_log import OperationLog  # noqa: F401
            db.create_all()
            self._seed()

    def _seed(self):
        from datas.model.rbac_user import RbacUser
        from datas.model.resource_group import ResourceGroup
        from datas.model.user_group import UserGroup
        from datas.model.tag import Tag
        from datas.utils.times import get_now_time

        g1 = ResourceGroup(name='GroupA', description='', create_time=get_now_time())
        g2 = ResourceGroup(name='GroupB', description='', create_time=get_now_time())
        self.db.session.add_all([g1, g2])
        self.db.session.flush()
        self.g1_id = g1.id
        self.g2_id = g2.id

        biz_admin = RbacUser(username='biz_a', role='admin', is_active=1, create_time=get_now_time())
        biz_admin.set_password('pass')
        self.db.session.add(biz_admin)
        self.db.session.flush()
        self.db.session.add(UserGroup(user_id=biz_admin.id, group_id=g1.id))
        self.biz_admin_id = biz_admin.id

        tag_g1 = Tag(name='tag-g1', group_id=g1.id, created_by='seed', create_time=get_now_time(), update_time=get_now_time())
        tag_g2 = Tag(name='tag-g2', group_id=g2.id, created_by='seed', create_time=get_now_time(), update_time=get_now_time())
        tag_global = Tag(name='tag-global', group_id=None, created_by='seed', create_time=get_now_time(), update_time=get_now_time())
        self.db.session.add_all([tag_g1, tag_g2, tag_global])
        self.db.session.flush()
        self.tag_g1_id = tag_g1.id
        self.tag_g2_id = tag_g2.id
        self.tag_global_id = tag_global.id

        self.db.session.commit()

    def _login_as_biz_admin(self):
        with self.client.session_transaction() as sess:
            sess['is_login'] = True
            sess['username'] = 'biz_a'
            sess['role'] = 'admin'
            sess['user_id'] = self.biz_admin_id
            sess['group_ids'] = [self.g1_id]

    def tearDown(self):
        with self.app.app_context():
            self.db.drop_all()

    # ---- tag_create scope ----

    def test_create_own_group_allowed(self):
        """Biz admin can create tag in own group."""
        self._login_as_biz_admin()
        with self.app.app_context():
            r = self.client.post('/rbac/tags/create', data={
                'name': 'new-tag', 'group_id': str(self.g1_id)
            })
            self.assertIn(r.status_code, (200, 302))
            data = r.get_json(silent=True)
            if data:
                self.assertEqual(data.get('errcode'), 0, data.get('errmsg'))

    def test_create_other_group_blocked(self):
        """Biz admin CANNOT create tag in another group."""
        self._login_as_biz_admin()
        with self.app.app_context():
            r = self.client.post('/rbac/tags/create', data={
                'name': 'evil-tag', 'group_id': str(self.g2_id)
            })
            data = r.get_json(silent=True)
            self.assertIsNotNone(data)
            self.assertNotEqual(data.get('errcode'), 0)

    def test_create_global_blocked(self):
        """Biz admin CANNOT create global tag (group_id=None)."""
        self._login_as_biz_admin()
        with self.app.app_context():
            r = self.client.post('/rbac/tags/create', data={'name': 'global-tag'})
            data = r.get_json(silent=True)
            self.assertIsNotNone(data)
            self.assertNotEqual(data.get('errcode'), 0)

    # ---- tag_update scope ----

    def test_update_own_group_tag_allowed(self):
        """Biz admin can update tag in own group."""
        self._login_as_biz_admin()
        with self.app.app_context():
            r = self.client.post('/rbac/tags/update', data={
                'tag_id': str(self.tag_g1_id), 'new_name': 'renamed-g1'
            })
            data = r.get_json(silent=True)
            if data:
                self.assertEqual(data.get('errcode'), 0, data.get('errmsg'))

    def test_update_other_group_tag_blocked(self):
        """Biz admin CANNOT update tag in another group."""
        self._login_as_biz_admin()
        with self.app.app_context():
            r = self.client.post('/rbac/tags/update', data={
                'tag_id': str(self.tag_g2_id), 'new_name': 'evil-rename'
            })
            data = r.get_json(silent=True)
            self.assertIsNotNone(data)
            self.assertNotEqual(data.get('errcode'), 0)

    def test_update_global_tag_blocked(self):
        """Biz admin CANNOT update global tag."""
        self._login_as_biz_admin()
        with self.app.app_context():
            r = self.client.post('/rbac/tags/update', data={
                'tag_id': str(self.tag_global_id), 'new_name': 'evil-rename'
            })
            data = r.get_json(silent=True)
            self.assertIsNotNone(data)
            self.assertNotEqual(data.get('errcode'), 0)

    # ---- tag_delete scope ----

    def test_delete_own_group_tag_allowed(self):
        """Biz admin can delete tag in own group."""
        self._login_as_biz_admin()
        with self.app.app_context():
            r = self.client.post('/rbac/tags/delete', data={
                'tag_id': str(self.tag_g1_id), 'force': '1'
            })
            data = r.get_json(silent=True)
            if data:
                self.assertEqual(data.get('errcode'), 0, data.get('errmsg'))

    def test_delete_other_group_tag_blocked(self):
        """Biz admin CANNOT delete tag in another group."""
        self._login_as_biz_admin()
        with self.app.app_context():
            r = self.client.post('/rbac/tags/delete', data={
                'tag_id': str(self.tag_g2_id)
            })
            data = r.get_json(silent=True)
            self.assertIsNotNone(data)
            self.assertNotEqual(data.get('errcode'), 0)

    # ---- tag_tasks scope ----

    def test_tasks_other_group_tag_blocked(self):
        """Biz admin CANNOT view tasks of another group's tag."""
        self._login_as_biz_admin()
        with self.app.app_context():
            r = self.client.get(f'/rbac/tags/tasks?tag_id={self.tag_g2_id}')
            data = r.get_json(silent=True)
            self.assertIsNotNone(data)
            self.assertNotEqual(data.get('errcode'), 0)


if __name__ == '__main__':
    unittest.main()
