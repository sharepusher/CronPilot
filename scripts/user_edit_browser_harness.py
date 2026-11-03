"""Isolated HTTP fixture and request-local observation for user-edit verification."""
import secrets
import threading
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest import mock

from flask import Flask, has_request_context, request
from sqlalchemy import event, func, select, text
from sqlalchemy.pool import StaticPool
from werkzeug.serving import WSGIRequestHandler, make_server

from app import db, register_hms_filters
from app.main import main
from app.rbac import rbac, services, views
from app.ui_mode import inject_ui_mode
from datas.model.rbac_audit_log import RbacAuditLog
from datas.model.rbac_registration_request import RbacRegistrationRequest  # noqa: F401
from datas.model.rbac_user import RbacUser
from datas.model.resource_group import ResourceGroup
from datas.model.user_group import UserGroup

ROOT = Path(__file__).resolve().parents[1]
URI = 'sqlite:///:memory:'


def require(ok, phase):
    if not ok:
        raise AssertionError(phase)


def validate_database(uri):
    require(uri == URI, 'isolation_requires_memory_database')


def prepare_output(output):
    output.mkdir(parents=True, exist_ok=True)
    require(not any(output.iterdir()), 'output_directory_must_be_empty')


class QuietHandler(WSGIRequestHandler):
    def log_request(self, *args, **kwargs):
        pass  # Never log query strings or form data.


class Injection:
    """One service call, one concrete Session, one fault; always restored."""
    def __init__(self, concrete, mode, trace):
        self.concrete, self.mode, self.trace = concrete, mode, trace
        self.hits = 0

    @contextmanager
    def apply(self):
        require(self.mode in (None, 'flush_after', 'commit_before', 'commit_after'),
                'invalid_fault_mode')
        with ExitStack() as stack:
            if self.mode:
                method = 'flush' if self.mode == 'flush_after' else 'commit'
                original = getattr(self.concrete, method)

                def invoke(*args, **kwargs):
                    if self.mode == 'commit_before':
                        self.hits += 1
                        raise RuntimeError('verification_commit_before')
                    result = original(*args, **kwargs)
                    if self.mode != 'flush_after' or self.trace['dml']:
                        self.hits += 1
                        raise RuntimeError('verification_' + self.mode)
                    return result

                stack.enter_context(mock.patch.object(self.concrete, method, side_effect=invoke))
            yield self
        self.trace['fault_hits'] = self.hits

    def verify(self):
        require(self.hits == (1 if self.mode else 0), 'fault_hit_count_invalid')


class Harness:
    def __init__(self, uri=URI):
        validate_database(uri)  # Must run before constructing any engine.
        self.run_id = secrets.token_hex(8)
        self.password = secrets.token_urlsafe(24)
        self.lock = threading.RLock()
        self.armed = None
        self.traces = []
        self.current = None
        self.stack = ExitStack()
        self.app = Flask(__name__, template_folder=str(ROOT / 'app/templates'),
                         static_folder=str(ROOT / 'app/static'))
        self.app.secret_key = secrets.token_hex(32)
        self.app.config.update(
            TESTING=True, CSRF_BYPASS_IN_TESTING=False,
            SQLALCHEMY_DATABASE_URI=uri, SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SQLALCHEMY_ENGINE_OPTIONS={'poolclass': StaticPool,
                                      'connect_args': {'check_same_thread': False}},
            CRON_CONFIG={'is_dev': '0'},
        )
        db.init_app(self.app)
        register_hms_filters(self.app)
        self.app.register_blueprint(main)
        self.app.register_blueprint(rbac)
        self.app.context_processor(inject_ui_mode)
        # No scheduler, development DB, API credentials, or production app factory.
        with self.app.app_context():
            db.create_all()
            self.engine = db.engine
            require(self.engine.url.database == ':memory:', 'engine_not_memory')
            require(isinstance(self.engine.pool, StaticPool), 'engine_not_shared_memory')
            db.session.execute(text('CREATE TABLE verification_run (id TEXT PRIMARY KEY)'))
            db.session.execute(text('INSERT INTO verification_run VALUES (:run)'),
                               {'run': self.run_id})
            db.session.commit()
        self._install()
        original_wsgi = self.app.wsgi_app

        def serialized_wsgi(environ, start_response):
            with self.lock:
                return original_wsgi(environ, start_response)

        self.app.wsgi_app = serialized_wsgi
        self.server = None

    def _install(self):
        @self.app.before_request
        def observe_request():
            require(db.session.scalar(text('SELECT id FROM verification_run')) == self.run_id,
                    'http_memory_sentinel_mismatch')
            if request.path == '/rbac/users/edit' and request.method == 'POST':
                self.current = {
                    'target_id': request.form.get('id'), 'service_calls': 0,
                    'dml': 0, 'relationship_dml': 0, 'commits': 0, 'rollbacks': 0,
                    'cache_invalidations': 0, 'fault_hits': 0,
                }
                concrete = db.session()
                for name, key in (('after_commit', 'commits'), ('after_rollback', 'rollbacks')):
                    def count(_session, key=key):
                        self.current[key] += 1
                    event.listen(concrete, name, count)

        @self.app.after_request
        def finish(response):
            if self.current is not None:
                self.current['http_status'] = response.status_code
                self.traces.append(self.current)
                self.current = None
            return response

        def sql(_conn, _cursor, statement, _params, _ctx, _many):
            if self.current is None or not has_request_context():
                return
            normalized = statement.strip().lower()
            if normalized.startswith(('insert ', 'update ', 'delete ')):
                self.current['dml'] += 1
                if 'user_groups' in normalized:
                    self.current['relationship_dml'] += 1

        event.listen(self.engine, 'after_cursor_execute', sql)
        self.stack.callback(event.remove, self.engine, 'after_cursor_execute', sql)
        original_service = views.update_user_management

        def service(*args, **kwargs):
            trace = self.current
            require(trace is not None, 'service_outside_observed_request')
            trace['service_calls'] += 1
            mode = None
            if self.armed:
                require(str(args[1]) == str(self.armed['target_id']), 'fault_wrong_target')
                mode = self.armed['mode']
                self.armed = None
            injection = Injection(db.session(), mode, trace)
            with injection.apply():
                result = original_service(*args, **kwargs)
            injection.verify()
            trace['service_outcome'] = result['outcome']
            return result

        original_invalidate = services._invalidate_api_scope_cache

        def invalidate(*args, **kwargs):
            if self.current is not None:
                self.current['cache_invalidations'] += 1
            return original_invalidate(*args, **kwargs)

        self.stack.enter_context(mock.patch.object(views, 'update_user_management', side_effect=service))
        self.stack.enter_context(mock.patch.object(services, '_invalidate_api_scope_cache',
                                                  side_effect=invalidate))

    def __enter__(self):
        self.server = make_server('127.0.0.1', 0, self.app, threaded=False,
                                  request_handler=QuietHandler)
        self.url = 'http://127.0.0.1:%s' % self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *exc):
        if self.server is not None:
            self.server.shutdown()
            self.thread.join(timeout=5)
            self.server.server_close()
        self.stack.close()
        with self.app.app_context():
            db.session.remove()
            self.engine.dispose()

    def fixture(self, case_id):
        with self.lock, self.app.app_context():
            prefix = self.run_id + '_' + case_id
            groups = [ResourceGroup(name=prefix + label, create_time=1) for label in 'ABC']
            db.session.add_all(groups)
            db.session.flush()
            users = {}
            roles = {'actor': 'admin', 'other': 'admin', 'global': 'admin',
                     'target': 'viewer', 'outside': 'viewer', 'operator': 'operator',
                     'viewer': 'viewer'}
            for label, role in roles.items():
                user = RbacUser(username=prefix + '_' + label, role=role,
                                email=label + '@example.invalid', nickname='original',
                                job_title='qa', is_active=1, auth_version=0, create_time=1)
                user.set_password(self.password)
                db.session.add(user)
                db.session.flush()
                users[label] = {'id': user.id, 'username': user.username}
                indexes = () if label == 'global' else ((1,) if label == 'outside' else (
                    (0, 1) if label == 'target' else (0, 2)))
                for index in indexes:
                    db.session.add(UserGroup(user_id=user.id, group_id=groups[index].id))
            db.session.commit()
            return users

    def state(self, target):
        with self.lock, self.app.app_context():
            user = db.session.get(RbacUser, target['id'])
            return {
                'email': user.email, 'nickname': user.nickname, 'job_title': user.job_title,
                'role': user.role, 'auth_version': user.auth_version,
                'groups': list(db.session.scalars(select(UserGroup.group_id).where(
                    UserGroup.user_id == user.id).order_by(UserGroup.group_id))),
                'secret': (user.api_token, user.api_token_expires_at, user.password_hash),
                'audit': db.session.scalar(select(func.count()).select_from(RbacAuditLog).where(
                    RbacAuditLog.resource == user.username, RbacAuditLog.action == 'user:update')),
            }

    def arm(self, target, mode):
        require(self.armed is None, 'fault_already_armed')
        require(mode in ('commit_before', 'commit_after', 'flush_after'), 'invalid_fault_mode')
        self.armed = {'target_id': target['id'], 'mode': mode}


def verify_results(results, required):
    ids = [row['case_id'] for row in results]
    require(len(ids) == len(set(ids)), 'duplicate_case_id')
    require(set(ids) == set(required), 'required_cases_missing_or_extra')
    require(all(row.get('passed') is True for row in results), 'case_not_passed')
    require(not any(row.get('skipped') for row in results), 'required_case_skipped')
