"""Run actual extracted application HTTP routes with isolated memory-only fixtures."""
import argparse
import html
import importlib
import json
import os
import pkgutil
import re
import sys
import threading
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=50993)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--serve', action='store_true')
args = parser.parse_args()
root = Path.cwd().resolve()
assert (root / 'app/templates/redesign/_exec_logs_pagination.html').is_file()
assert '/private/tmp/' in str(root) and 'cronpilot-4.2.0' == root.name
os.environ['TEST_DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['CRONPILOT_SCHEDULER_ENABLED'] = 'false'
os.environ['FLASK_CONFIG'] = 'testing'
sys.path.insert(0, str(root))
import requests
from sqlalchemy.pool import StaticPool
from werkzeug.serving import make_server

import app as application
import config
import datas.model as models
from app.auth.password import hash_password
from datas.model.cron_infos import CronInfos
from datas.model.job_log import JobLog
from datas.model.rbac_registration_request import RbacRegistrationRequest  # noqa: F401
from datas.model.rbac_user import RbacUser
from datas.model.resource_group import ResourceGroup
from datas.model.task_group import TaskGroup
from datas.model.user_group import UserGroup

assert Path(application.__file__).resolve() == root / 'app/__init__.py'
for module in pkgutil.iter_modules(models.__path__):
    importlib.import_module('datas.model.' + module.name)
config.TestingConfig.SQLALCHEMY_ENGINE_OPTIONS = {
    'poolclass': StaticPool, 'connect_args': {'check_same_thread': False}}
app = application.create_app('testing')
app.config.update(SERVER_NAME=None, CSRF_BYPASS_IN_TESTING=False)
app.secret_key = 'isolated-packaged-template-proof-only'
db = application.db
with app.app_context():
    assert db.engine.url.database == ':memory:'
    db.create_all()
    user = RbacUser(username='package_operator', role='operator', is_active=1,
                    password_hash=hash_password('Package-proof-pass2026'), auth_version=0,
                    email='package-operator@example.invalid', nickname='Package Operator',
                    job_title='Verification')
    group = ResourceGroup(name='package-proof-group')
    task = CronInfos(task_name="Package O'Reilly proof", req_url='https://example.invalid/',
                     status=0, scope_type='GROUP', minute='*/5')
    db.session.add_all([user, group, task])
    db.session.flush()
    task_id = task.id
    db.session.add_all([UserGroup(user_id=user.id, group_id=group.id),
                        TaskGroup(task_id=task.id, group_id=group.id)])
    for i in range(45):
        db.session.add(JobLog(cron_info_id=task.id, trace_id='package-proof-%02d' % i,
                              status='fail', content='packaged log proof', http_status=500,
                              create_time=20261104000000 + i, take_time='1'))
    db.session.commit()
server = make_server('127.0.0.1', args.port, app)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
base = 'http://127.0.0.1:%d' % args.port
session = requests.Session()
rows = []
try:
    login = session.get(base + '/rbac/login', timeout=10)
    token = re.search(r'name="csrf_token"\s+value="([^"]+)"', login.text).group(1)
    response = session.post(base + '/rbac/login', data={
        'username': 'package_operator', 'password': 'Package-proof-pass2026',
        'csrf_token': html.unescape(token)}, allow_redirects=False, timeout=10)
    assert response.status_code == 302, response.status_code
    rows.append({'case': 'operator_login_post', 'status': response.status_code})
    for route in ('/job_log_all_list', '/job_log_list'):
        common = {'outcome': 'fail'}
        if route == '/job_log_list':
            common['id'] = task_id
        keyword = 'content' if route == '/job_log_list' else 'task_name'
        for partial in (False, True):
            page_ids = []
            for empty, page in ((False, 1), (False, 2), (True, 1)):
                params = dict(common, page=page)
                params[keyword] = '__no_matching_log__' if empty else (
                    'packaged log proof' if keyword == 'content' else "O'Reilly")
                if partial:
                    params['partial'] = '1'
                response = session.get(base + route, params=params, timeout=10)
                assert response.status_code == 200, (route, params, response.status_code)
                content = response.text
                if partial:
                    data = response.json()
                    assert data['total'] == (0 if empty else 45), data
                    content = data['rows']
                    assert 'github.com' not in data['pagination']
                    if not empty:
                        assert '?page=' in data['pagination']
                elif not empty:
                    heading = re.search(r'<thead>(.*?)</thead>', content, re.S).group(1)
                    assert len(re.findall(r'<th(?:\s|>)', heading)) == 7
                ids = re.findall(r'class="el-mono record-id" data-id="(\d+)"', content)
                assert len(ids) == (0 if empty else 20), (route, partial, page, len(ids))
                if not empty:
                    page_ids.append(set(ids))
                rows.append({'route': route, 'partial': partial, 'empty': empty,
                             'page': page, 'status': 200, 'row_count': len(ids)})
            assert page_ids[0].isdisjoint(page_ids[1]), 'page 2 did not advance'
    result = {'status': 'passed', 'role': 'operator', 'database': 'sqlite:///:memory:',
              'application_root': str(root), 'base_url': base, 'fixture_logs': 45,
              'checks': rows}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)
    if args.serve:
        thread.join()
finally:
    server.shutdown()
    server.server_close()
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
