#!/usr/bin/env python3
"""Verify dashboard status controls on an owned SQLite database and paused scheduler."""
import argparse
import configparser
import importlib
import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['CRONPILOT_SCHEDULER_ENABLED'] = 'false'


def check_wire(request, task_id, csrf):
    data = parse_qs(request.post_data or '', keep_blank_values=True)
    assert urlsplit(request.url).path == '/update_status'
    assert not urlsplit(request.url).query
    assert data.get('id') == [str(task_id)]
    assert data.get('status') == ['1']
    assert data.get('csrf_token') == [csrf] and csrf


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--executable-path', required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    password = 'isolated-browser-verification-2026!'
    with tempfile.TemporaryDirectory(prefix='cp-dashboard-status-') as directory:
        root = Path(directory)
        uri = 'sqlite:///' + str(root / 'owned.sqlite')
        cfg = configparser.ConfigParser()
        cfg.read(ROOT / 'conf.local.sqlite.example')
        cfg.set('default', 'cron_db_url', uri)
        cfg.set('default', 'cron_job_log_db_url', uri)
        cfg.set('default', 'login_pwd', password)
        with (root / 'conf.ini').open('w') as f:
            cfg.write(f)
        import configs
        configs._proj_root = str(root)
        from playwright.sync_api import sync_playwright
        from werkzeug.serving import make_server

        from app import create_app, db, scheduler
        from app.services.cron_service import register_cron_job
        from datas.model.cron_infos import CronInfos
        from datas.model.rbac_user import RbacUser
        from datas.model.resource_group import ResourceGroup
        from datas.model.task_group import TaskGroup
        from datas.model.user_group import UserGroup

        app = create_app('development')
        app.config.update(DEBUG=False, TESTING=False)
        with app.app_context():
            for model in (ROOT / 'datas/model').glob('*.py'):
                importlib.import_module('datas.model.' + model.stem)
            db.create_all()
            group = ResourceGroup(name='dashboard-test')
            operator = RbacUser(username='dashboard_op', role='operator', is_active=1,
                                auth_version=0, nickname='Operator', job_title='test',
                                email='op@example.invalid')
            viewer = RbacUser(username='dashboard_viewer', role='viewer', is_active=1,
                              auth_version=0, nickname='Viewer', job_title='test',
                              email='viewer@example.invalid')
            operator.set_password(password)
            viewer.set_password(password)
            task = CronInfos(task_name='browser-status-isolated', task_keyword='test',
                             req_url='https://example.invalid/task', req_method='GET', req_body='',
                             run_date='', day_of_week='', day='', hour='23', minute='59', second='',
                             status=0, scope_type='GROUP', created_at=1, updated_at=1)
            db.session.add_all([group, operator, viewer, task])
            db.session.flush()
            task_id = task.id
            db.session.add_all([UserGroup(user_id=operator.id, group_id=group.id),
                                UserGroup(user_id=viewer.id, group_id=group.id),
                                TaskGroup(task_id=task.id, group_id=group.id)])
            db.session.commit()
            scheduler.scheduler.start(paused=True)
            register_cron_job(task_id, {'run_date': '', 'day_of_week': '', 'day': '',
                                        'hour': '23', 'minute': '59', 'second': ''}, paused=True)
        server = make_server('127.0.0.1', 0, app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = 'http://127.0.0.1:%d' % server.server_port
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True, executable_path=args.executable_path)
                try:
                    page = browser.new_page()

                    def login(target, username):
                        target.goto(base + '/rbac/login')
                        target.locator('[name=username]').fill(username)
                        target.locator('[name=password]').fill(password)
                        target.locator('button[type=submit]').click()
                        target.wait_for_url('**/cron_list')

                    def select_resume():
                        row = page.locator('tr').filter(has_text='browser-status-isolated')
                        row.get_by_role('button', name='更多操作').click()
                        row.get_by_text('恢复', exact=True).click()

                    login(page, 'dashboard_op')
                    page.route('**/static/js/cron-status.js', lambda route: route.fulfill(status=200, body=''))
                    page.reload()
                    try:
                        assert page.evaluate('typeof window.CpStatus !== "undefined"')
                    except AssertionError:
                        module_mutation_detected = True
                    else:
                        raise AssertionError('missing_module_not_detected')
                    page.unroute('**/static/js/cron-status.js')
                    page.reload()
                    assert page.evaluate('typeof window.CpStatus.perform === "function"')
                    csrf = page.locator('meta[name=csrf-token]').get_attribute('content')

                    def tamper(route):
                        data = parse_qs(route.request.post_data or '', keep_blank_values=True)
                        data['status'] = ['0']
                        route.continue_(post_data=urlencode(data, doseq=True))

                    page.route('**/update_status', tamper)
                    select_resume()
                    page.get_by_role('heading', name='启动任务', exact=True).wait_for()
                    with page.expect_response('**/update_status') as changed:
                        page.get_by_role('button', name='确认', exact=True).click()
                    altered = changed.value
                    assert altered.json()['errcode'] == 0
                    try:
                        check_wire(altered.request, task_id, csrf)
                    except AssertionError:
                        target_mutation_detected = True
                    else:
                        raise AssertionError('incorrect_target_not_detected')
                    with app.app_context():
                        db.session.expire_all()
                        assert db.session.get(CronInfos, task_id).status == 0
                        assert scheduler.get_job('cron_%s' % task_id).next_run_time is None
                    page.unroute('**/update_status')
                    page.reload()
                    csrf = page.locator('meta[name=csrf-token]').get_attribute('content')
                    select_resume()
                    page.get_by_role('heading', name='启动任务', exact=True).wait_for()
                    with page.expect_response('**/update_status') as submitted:
                        page.get_by_role('button', name='确认', exact=True).click()
                    response = submitted.value
                    check_wire(response.request, task_id, csrf)
                    assert response.json()['errcode'] == 0
                    with app.app_context():
                        db.session.expire_all()
                        assert db.session.get(CronInfos, task_id).status == 1
                        assert scheduler.get_job('cron_%s' % task_id).next_run_time is not None
                    page.locator('tr').filter(has_text='browser-status-isolated').get_by_text(
                        '运行中', exact=True).wait_for()
                    page.screenshot(path=str(output / 'operator-result.png'), full_page=True,
                                    animations='disabled')
                    other = browser.new_page()
                    login(other, 'dashboard_viewer')
                    row = other.locator('tr').filter(has_text='browser-status-isolated')
                    assert row.get_by_role('button', name='更多操作').count() == 0
                    viewer_csrf = other.locator('meta[name=csrf-token]').get_attribute('content')
                    denied = other.request.post(base + '/update_status', form={'id': str(task_id),
                                               'status': '0', 'csrf_token': viewer_csrf})
                    assert denied.status == 403
                    with app.app_context():
                        db.session.expire_all()
                        assert db.session.get(CronInfos, task_id).status == 1
                        assert scheduler.get_job('cron_%s' % task_id).next_run_time is not None
                    other.wait_for_load_state('networkidle')
                    other.screenshot(path=str(output / 'viewer-denied.png'), full_page=True,
                                     animations='disabled')
                    results = dict(operator=True, viewer_denied=True, request_body=True,
                                   jobstore=True, globally_paused=True,
                                   missing_module_detected=module_mutation_detected,
                                   altered_target_detected=target_mutation_detected)
                    (output / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
                    print('DASHBOARD_STATUS_BROWSER: OK', flush=True)
                finally:
                    browser.close()
        finally:
            server.shutdown()
            thread.join(timeout=5)
            with app.app_context():
                scheduler.scheduler.shutdown(wait=True)
                db.session.remove()
                db.engine.dispose()


if __name__ == '__main__':
    main()
