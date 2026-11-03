"""Review reproduction: independent temporary SQLite connections; no development DB.

Run from repository root: .venv-py311/bin/python doc/qa/evidence/v4.2.0-review-2026-10-30/sqlite_authorization_race.py
Expected while defect exists: three observed=True records. This is evidence, not fix acceptance.
"""
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from flask import Flask
from sqlalchemy import create_engine, event

from app import db
from app.rbac.services import (
    build_user_edit_intent, build_user_edit_snapshot, project_user_edit_values,
    update_user_management,
)
from app.services.cron_edit_concurrency import build_task_edit_snapshot, save_task_edit
from datas.model.cron_infos import CronInfos
from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
from datas.model.rbac_user import RbacUser
from datas.model.resource_group import ResourceGroup
from datas.model.task_group import TaskGroup
from datas.model.user_group import UserGroup


def run_case(case):
    with TemporaryDirectory(prefix='cronpilot-review-race-') as directory:
        uri = 'sqlite:///' + str(Path(directory) / 'isolated.sqlite')
        app = Flask(__name__)
        app.config.update(SECRET_KEY='review-only', SQLALCHEMY_DATABASE_URI=uri,
                          SQLALCHEMY_TRACK_MODIFICATIONS=False)
        db.init_app(app)
        with app.test_request_context('/review', method='POST'):
            db.create_all()
            db.session.add_all([
                RbacUser(id=1, username='actor', role='operator' if case == 'task_revoke' else 'admin',
                         is_active=1, auth_version=0, password_hash='test', job_title='qa'),
                RbacUser(id=2, username='target', role='viewer', is_active=1, auth_version=0,
                         password_hash='test', job_title='qa', nickname='original'),
                ResourceGroup(id=1, name='A'),
            ])
            raw = dict(task_name='review', task_keyword='original', run_date='', day_of_week='',
                       day='', hour='1', minute='0', second='', req_url='https://example.invalid/task',
                       req_method='GET', req_body='', timeout_sec='')
            task = CronInfos(**dict(raw, timeout_sec=None), status=0, scope_type='GROUP')
            db.session.add(task)
            db.session.flush()
            task_id = task.id
            db.session.add_all([UserGroup(user_id=1, group_id=1), UserGroup(user_id=2, group_id=1),
                                TaskGroup(task_id=task_id, group_id=1)])
            db.session.commit()
            if case == 'task_revoke':
                original = build_task_edit_snapshot(1, task)
            else:
                original = build_user_edit_snapshot(1, db.session.get(RbacUser, 2), [1])
                requested = dict(project_user_edit_values(original), nickname='request-value')
            external = create_engine(uri)
            injected = []

            def inject(_conn, _cursor, statement, _params, _context, _many):
                prefix = 'SELECT cron_infos.' if case == 'task_revoke' else 'SELECT user_groups.'
                if not injected and statement.lstrip().startswith(prefix):
                    injected.append(True)
                    with external.begin() as connection:
                        mutation = (dict(nickname='concurrent-value') if case == 'user_conflict'
                                    else dict(role='viewer', auth_version=1))
                        connection.execute(RbacUser.__table__.update().where(
                            RbacUser.id == (2 if case == 'user_conflict' else 1)).values(**mutation))

            event.listen(db.engine, 'before_cursor_execute', inject)
            try:
                if case == 'task_revoke':
                    with patch('app.services.cron_validator.validate_trigger_url', return_value=(True, '')), \
                            patch('app.services.cron_service.register_cron_job'), \
                            patch('app.services.cron_edit_concurrency.scheduler'):
                        result = save_task_edit(1, task_id, original, dict(
                            raw, task_keyword='request-value', scope_type='GROUP', group_id=1,
                            tag_names=[]), 0, {})
                else:
                    result = update_user_management(1, 2, original, requested,
                                                    build_user_edit_intent(original, requested))
            finally:
                event.remove(db.engine, 'before_cursor_execute', inject)
            db.session.expire_all()
            value = (db.session.get(CronInfos, task_id).task_keyword if case == 'task_revoke'
                     else db.session.get(RbacUser, 2).nickname)
            record = dict(case=case, independent_commit=bool(injected), outcome=result['outcome'],
                          current_actor_role=db.session.get(RbacUser, 1).role, stored_value=value,
                          observed=bool(injected) and result['outcome'] == 'updated' and value == 'request-value')
            db.session.remove()
            external.dispose()
            db.engine.dispose()
            return record


if __name__ == '__main__':
    results = [run_case(case) for case in ('task_revoke', 'user_revoke', 'user_conflict')]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    assert all(record['observed'] for record in results), 'Evidence changed; reassess the findings'
