#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""OPT-P1-11：task_groups / tags / task_tags 数据模型与迁移测试。"""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from flask import Flask
from app import db as _db
from datas.utils.times import str_to_hms, utc_now_hms


def _make_app():
    """创建带 SQLite 内存库的测试 Flask app。"""
    app = Flask(
        __name__,
        template_folder=os.path.join(ROOT, 'app', 'templates'),
        static_folder=os.path.join(ROOT, 'app', 'static'),
    )
    app.secret_key = 'test-secret-key-task-groups'
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    _db.init_app(app)
    return app, _db


class TestTaskGroupModel(unittest.TestCase):
    """task_groups 表 CRUD。"""

    def setUp(self):
        self.app, self.db = _make_app()
        with self.app.app_context():
            from datas.model.cron_infos import CronInfos  # noqa: F401
            from datas.model.resource_group import ResourceGroup  # noqa: F401
            from datas.model.task_group import TaskGroup  # noqa: F401
            self.db.create_all()

    def tearDown(self):
        with self.app.app_context():
            self.db.drop_all()

    def test_create_task_group(self):
        """可创建 task_group 关联记录。"""
        with self.app.app_context():
            from datas.model.task_group import TaskGroup
            tg = TaskGroup(task_id=1, group_id=2)
            self.db.session.add(tg)
            self.db.session.commit()
            self.assertIsNotNone(tg.id)

    def test_unique_constraint(self):
        """同一 (task_id, group_id) 不可重复。"""
        with self.app.app_context():
            from datas.model.task_group import TaskGroup
            from sqlalchemy.exc import IntegrityError
            self.db.session.add(TaskGroup(task_id=1, group_id=2))
            self.db.session.commit()
            self.db.session.add(TaskGroup(task_id=1, group_id=2))
            with self.assertRaises(IntegrityError):
                self.db.session.commit()

    def test_multi_group_per_task(self):
        """一个任务可关联多个组。"""
        with self.app.app_context():
            from datas.model.task_group import TaskGroup
            self.db.session.add(TaskGroup(task_id=10, group_id=1))
            self.db.session.add(TaskGroup(task_id=10, group_id=2))
            self.db.session.add(TaskGroup(task_id=10, group_id=3))
            self.db.session.commit()
            rows = self.db.session.query(TaskGroup).filter_by(task_id=10).all()
            self.assertEqual(len(rows), 3)
            gids = {r.group_id for r in rows}
            self.assertEqual(gids, {1, 2, 3})


class TestTagModel(unittest.TestCase):
    """tags 表 CRUD。"""

    def setUp(self):
        self.app, self.db = _make_app()
        with self.app.app_context():
            from datas.model.tag import Tag  # noqa: F401
            self.db.create_all()

    def tearDown(self):
        with self.app.app_context():
            self.db.drop_all()

    def test_create_tag(self):
        with self.app.app_context():
            from datas.model.tag import Tag
            t = Tag(name='JP', created_by='admin', create_time=str_to_hms('2026-08-05 00:00:00'), update_time=str_to_hms('2026-08-05 00:00:00'))
            self.db.session.add(t)
            self.db.session.commit()
            self.assertIsNotNone(t.id)

    def test_unique_name_same_group(self):
        """同组内标签名不可重复。"""
        with self.app.app_context():
            from datas.model.tag import Tag
            from sqlalchemy.exc import IntegrityError
            self.db.session.add(Tag(name='JP', group_id=1, created_by='a', create_time=utc_now_hms(), update_time=utc_now_hms()))
            self.db.session.commit()
            self.db.session.add(Tag(name='JP', group_id=1, created_by='b', create_time=utc_now_hms(), update_time=utc_now_hms()))
            with self.assertRaises(IntegrityError):
                self.db.session.commit()

    def test_same_name_different_group_allowed(self):
        """不同组内同名标签可共存。"""
        with self.app.app_context():
            from datas.model.tag import Tag
            self.db.session.add(Tag(name='JP', group_id=1, created_by='a', create_time=utc_now_hms(), update_time=utc_now_hms()))
            self.db.session.add(Tag(name='JP', group_id=2, created_by='b', create_time=utc_now_hms(), update_time=utc_now_hms()))
            self.db.session.commit()
            count = self.db.session.query(Tag).filter_by(name='JP').count()
            self.assertEqual(count, 2)


class TestTaskTagModel(unittest.TestCase):
    """task_tags 表 CRUD。"""

    def setUp(self):
        self.app, self.db = _make_app()
        with self.app.app_context():
            from datas.model.tag import Tag  # noqa: F401
            from datas.model.task_tag import TaskTag  # noqa: F401
            self.db.create_all()

    def tearDown(self):
        with self.app.app_context():
            self.db.drop_all()

    def test_create_task_tag(self):
        with self.app.app_context():
            from datas.model.task_tag import TaskTag
            tt = TaskTag(task_id=1, tag_id=2)
            self.db.session.add(tt)
            self.db.session.commit()
            self.assertIsNotNone(tt.id)

    def test_unique_constraint(self):
        """同一 (task_id, tag_id) 不可重复。"""
        with self.app.app_context():
            from datas.model.task_tag import TaskTag
            from sqlalchemy.exc import IntegrityError
            self.db.session.add(TaskTag(task_id=1, tag_id=2))
            self.db.session.commit()
            self.db.session.add(TaskTag(task_id=1, tag_id=2))
            with self.assertRaises(IntegrityError):
                self.db.session.commit()

    def test_multi_tags_per_task(self):
        """一个任务可有多个标签。"""
        with self.app.app_context():
            from datas.model.task_tag import TaskTag
            self.db.session.add(TaskTag(task_id=10, tag_id=1))
            self.db.session.add(TaskTag(task_id=10, tag_id=2))
            self.db.session.commit()
            rows = self.db.session.query(TaskTag).filter_by(task_id=10).all()
            self.assertEqual(len(rows), 2)


class TestMigrateGroupIdToTaskGroups(unittest.TestCase):
    """group_id -> task_groups 数据迁移（OPT-P1-11）。

    测试迁移场景：模拟旧表有 group_id 列时的迁移 + 迁移后列已删除。
    """

    def setUp(self):
        self.app, self.db = _make_app()
        with self.app.app_context():
            from datas.model.cron_infos import CronInfos  # noqa: F401
            from datas.model.resource_group import ResourceGroup  # noqa: F401
            from datas.model.task_group import TaskGroup  # noqa: F401
            self.db.create_all()

    def tearDown(self):
        with self.app.app_context():
            self.db.drop_all()

    def test_migration_with_legacy_group_id(self):
        """模拟旧表有 group_id 列时的迁移。"""
        with self.app.app_context():
            from datas.model.task_group import TaskGroup
            from sqlalchemy import text, inspect
            # 手动添加 group_id 列（模拟旧表）
            insp = inspect(self.db.engine)
            cols = {c['name'] for c in insp.get_columns('cron_infos')}
            if 'group_id' not in cols:
                with self.db.engine.begin() as conn:
                    conn.execute(text("ALTER TABLE cron_infos ADD COLUMN group_id INTEGER"))
            # 插入旧格式数据（需包含所有 NOT NULL 字段）
            _ins = (
                "INSERT INTO cron_infos "
                "(task_name, task_keyword, scope_type, group_id, "
                "last_operator_name, last_operated_at) VALUES "
            )
            with self.db.engine.begin() as conn:
                conn.execute(text(_ins + "('task1', 'kw', 'GROUP', 1, '', '')"))
                conn.execute(text(_ins + "('task2', 'kw', 'GROUP', 2, '', '')"))
                conn.execute(text(
                    "INSERT INTO cron_infos "
                    "(task_name, task_keyword, scope_type, "
                    "last_operator_name, last_operated_at) VALUES "
                    "('task3', 'kw', 'GLOBAL', '', '')"
                ))
            # 执行迁移
            with self.db.engine.begin() as conn:
                conn.execute(text(
                    "INSERT OR IGNORE INTO task_groups (task_id, group_id) "
                    "SELECT id, group_id FROM cron_infos "
                    "WHERE scope_type = 'GROUP' AND group_id IS NOT NULL"
                ))
            rows = self.db.session.query(TaskGroup).all()
            self.assertEqual(len(rows), 2)
            migrated = {(r.task_id, r.group_id) for r in rows}
            self.assertEqual(len(migrated), 2)

    def test_model_has_no_group_id(self):
        """CronInfos model 不再有 group_id 属性。"""
        from datas.model.cron_infos import CronInfos
        self.assertFalse(hasattr(CronInfos, 'group_id'))

    def test_new_tasks_use_task_groups(self):
        """新创建的任务通过 task_groups 表关联组。"""
        with self.app.app_context():
            from datas.model.cron_infos import CronInfos
            from datas.model.task_group import TaskGroup
            t = CronInfos(task_name='new-task', scope_type='GROUP')
            self.db.session.add(t)
            self.db.session.flush()
            self.db.session.add(TaskGroup(task_id=t.id, group_id=1))
            self.db.session.add(TaskGroup(task_id=t.id, group_id=2))
            self.db.session.commit()
            rows = self.db.session.query(TaskGroup).filter_by(task_id=t.id).all()
            self.assertEqual(len(rows), 2)
            self.assertEqual({r.group_id for r in rows}, {1, 2})


if __name__ == '__main__':
    unittest.main()
