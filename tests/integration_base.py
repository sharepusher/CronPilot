"""Base class for persistent-DB integration tests (L2 layer).

Uses a temporary SQLite file per test class, deleted on teardown.
Compared to in-memory:
  - Tests real ID allocation / reuse behavior
  - Tests cross-table constraint persistence
  - Tests ensure_business_tables ALTER logic
Compared to connecting to dev DB:
  - Fully isolated — datas/job_log.sqlite is never touched
"""
import os
import tempfile
import unittest

import flask

from app import db


class PersistentDBTestCase(unittest.TestCase):
    """Integration test base that creates a temporary SQLite file.

    Subclasses override ``_seed_data()`` to insert fixture rows.
    The scheduler is NOT started; tests that call ``create_cron`` /
    ``update_cron`` should patch ``app.services.cron_service.scheduler``.
    """

    @classmethod
    def setUpClass(cls):
        cls._db_fd, cls._db_path = tempfile.mkstemp(suffix='.sqlite')
        app = flask.Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{cls._db_path}'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['SECRET_KEY'] = 'integration-test'
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        db.init_app(app)
        cls.app = app
        with app.app_context():
            from datas.model.cron_infos import CronInfos  # noqa: F401
            from datas.model.job_log import JobLog  # noqa: F401
            from datas.model.operation_log import OperationLog  # noqa: F401
            from datas.model.resource_group import ResourceGroup  # noqa: F401
            from datas.model.task_group import TaskGroup  # noqa: F401
            db.create_all()
            cls._seed_data()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
        os.close(cls._db_fd)
        os.unlink(cls._db_path)

    @classmethod
    def _seed_data(cls):
        """Override in subclass to insert test fixtures."""
        pass
