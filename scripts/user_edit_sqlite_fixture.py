"""Fixtures and spawned workers; paths must belong to the verifier's private directory."""
import threading
from contextlib import nullcontext
from pathlib import Path
from unittest import mock

from flask import Flask
from sqlalchemy import event, func, select, text
from sqlalchemy.engine import Connection

from app import db, register_hms_filters
from app.docs import docs
from app.main import main
from app.rbac import rbac, services
from app.ui_mode import inject_ui_mode
from datas.model.rbac_audit_log import RbacAuditLog
from datas.model.rbac_registration_request import RbacRegistrationRequest  # noqa: F401
from datas.model.rbac_user import RbacUser
from datas.model.resource_group import ResourceGroup
from datas.model.user_group import UserGroup
from scripts.user_edit_browser_harness import Harness, Injection, require

ROOT = Path(__file__).resolve().parents[1]


def make_app(path, run_id):
    path = Path(path).resolve()
    require(path.parent.name.startswith('cronpilot-user-boundary-'), 'not_owned_temporary_path')
    require((path.parent / '.run-id').read_text() == run_id, 'file_owner_sentinel_mismatch')
    app = Flask(__name__, template_folder=str(ROOT / 'app/templates'),
                static_folder=str(ROOT / 'app/static'))
    app.secret_key = 'isolated-sqlite-boundary-' + run_id
    app.config.update(TESTING=True, CSRF_BYPASS_IN_TESTING=False, BASEDIR=str(ROOT),
                      SQLALCHEMY_DATABASE_URI='sqlite:///' + str(path),
                      SQLALCHEMY_TRACK_MODIFICATIONS=False,
                      SQLALCHEMY_ENGINE_OPTIONS={'connect_args': {'timeout': 5}})
    db.init_app(app)
    register_hms_filters(app)
    app.register_blueprint(main)
    app.register_blueprint(rbac)
    app.register_blueprint(docs)
    app.context_processor(inject_ui_mode)
    return app


class FileFixture:
    fixture = Harness.fixture
    state = Harness.state

    def __init__(self, path, run_id, mode, password):
        self.app = make_app(path, run_id)
        self.run_id, self.password, self.lock = run_id, password, threading.RLock()
        with self.app.app_context():
            actual = db.session.connection().exec_driver_sql('PRAGMA journal_mode=' + mode).scalar_one()
            require(actual.upper() == mode, 'requested_journal_mode_not_enabled')
            db.create_all()
            db.session.execute(text('CREATE TABLE verification_run (id TEXT PRIMARY KEY)'))
            db.session.execute(text('INSERT INTO verification_run VALUES (:id)'), {'id': run_id})
            db.session.commit()

    def values(self, target, actor):
        with self.app.app_context():
            user = db.session.get(RbacUser, target['id'])
            groups = list(db.session.scalars(select(UserGroup.group_id).where(
                UserGroup.user_id == user.id)))
            original = services.build_user_edit_snapshot(actor['id'], user, groups)
            requested = dict(services.project_user_edit_values(original), nickname='requested')
            return original, requested

    def close(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()


def _mutate_worker(path, run_id, actor_id, target_id, mutation, queue):
    from sqlalchemy import create_engine
    from sqlalchemy.exc import OperationalError
    engine = create_engine('sqlite:///' + str(path), connect_args={'timeout': 0})
    try:
        with engine.begin() as connection:
            require(connection.scalar(text('SELECT id FROM verification_run')) == run_id,
                    'mutation_sentinel_mismatch')
            user_id = actor_id if mutation.startswith('actor_') else target_id
            if mutation.endswith('_scope'):
                connection.execute(UserGroup.__table__.delete().where(UserGroup.user_id == user_id))
            else:
                values = {'actor_role': {'role': 'viewer', 'auth_version': 1},
                          'actor_inactive': {'is_active': 0, 'auth_version': 1},
                          'target_inactive': {'is_active': 0},
                          'same_field': {'nickname': 'concurrent'},
                          'equivalent': {'nickname': 'requested'},
                          'unrelated': {'email': 'concurrent@example.invalid'}}[mutation]
                connection.execute(RbacUser.__table__.update().where(RbacUser.id == user_id).values(**values))
        queue.put({'state': 'committed'})
    except OperationalError as error:
        code = getattr(error.orig, 'sqlite_errorcode', None)
        queue.put({'state': 'busy' if code == 5 else 'unexpected_db_error', 'code': code})
    except Exception:
        queue.put({'state': 'worker_error'})
    finally:
        engine.dispose()


def _service_worker(path, run_id, actor_id, target_id, original, requested, fault,
                    ready, release, queue):
    app = make_app(path, run_id)
    trace = {'dml': 0, 'relationship_dml': 0, 'commits': 0, 'cache_invalidations': 0,
             'invalidations': 0, 'physical_read': False, 'fault_hits': 0}
    try:
        with app.test_request_context('/rbac/users/edit', method='POST'):
            require(db.session.scalar(text('SELECT id FROM verification_run')) == run_id,
                    'service_sentinel_mismatch')
            session = db.session()
            paused = False
            def observe(conn, _cursor, statement, _params, _ctx, _many):
                nonlocal paused
                if statement.lstrip().startswith('SELECT rbac_users.') and not paused:
                    paused = True
                    trace['physical_read'] = conn.connection.driver_connection.in_transaction
                    if ready is not None:
                        ready.set()
                        require(release.wait(10), 'protected_worker_release_timeout')
                if statement.strip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE ')):
                    trace['dml'] += 1
                    if 'user_groups' in statement:
                        trace['relationship_dml'] += 1
            event.listen(db.engine, 'before_cursor_execute', observe)
            event.listen(session, 'after_commit', lambda _s: trace.update(commits=trace['commits'] + 1))
            real_execute = Connection.exec_driver_sql
            def restore_fault(conn, sql, *args, **kwargs):
                if sql.startswith('PRAGMA busy_timeout=') and sql != 'PRAGMA busy_timeout=0':
                    trace['restore_fault_hits'] = trace.get('restore_fault_hits', 0) + 1
                    raise RuntimeError('isolated_restore_failure')
                return real_execute(conn, sql, *args, **kwargs)
            real_invalidate = session.invalidate
            def invalidate():
                trace['invalidations'] += 1
                return real_invalidate()
            injection = Injection(session, fault if fault in (
                'commit_before', 'commit_after', 'flush_after') else None, trace)
            patch = mock.patch.object(Connection, 'exec_driver_sql', new=restore_fault) if (
                fault == 'restore_failure') else nullcontext()
            with patch, injection.apply(), mock.patch.object(session, 'invalidate', side_effect=invalidate), \
                    mock.patch('app.rbac.services._invalidate_api_scope_cache',
                               side_effect=lambda _id: trace.update(
                                   cache_invalidations=trace['cache_invalidations'] + 1)):
                result = services.update_user_management(
                    actor_id, target_id, original, requested,
                    services.build_user_edit_intent(original, requested), reason='isolated verification')
            if fault != 'restore_failure':
                injection.verify()
            trace['transaction_at_return'] = session.in_transaction()
            trace['outcome'] = result['outcome']
            trace['pool_timeout_after'] = session.connection().exec_driver_sql(
                'PRAGMA busy_timeout').scalar_one()
            session.rollback()
            event.remove(db.engine, 'before_cursor_execute', observe)
            queue.put(trace)
    except Exception:
        queue.put({'state': 'worker_error'})
    finally:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
