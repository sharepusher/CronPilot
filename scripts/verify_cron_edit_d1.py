"""D1 隔离端到端验收；D1_PREVIEW=1 保持 5003 预览，全局暂停禁止触发任务。"""
import configparser
from contextlib import contextmanager
import uuid
from sqlalchemy import create_engine, text
import importlib
import os
import sys
import tempfile
import threading
import json
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['CRONPILOT_SCHEDULER_ENABLED'] = 'false'

@contextmanager
def backend_url(directory):
    if os.environ.get('D1_BACKEND') != 'mysql':
        yield 'sqlite:///' + str(Path(directory) / 'isolated.sqlite')
        return
    from sqlalchemy.engine import make_url
    server_url = make_url('mysql+pymysql://root@127.0.0.1:33089/?charset=utf8mb4')
    server = create_engine(server_url)
    name = 'cronpilot_d1_' + uuid.uuid4().hex
    created = False
    try:
        with server.begin() as connection:
            connection.execute(text('CREATE DATABASE `%s`' % name))
            created = True
        yield str(server_url.set(database=name))
    finally:
        if created:
            with server.begin() as connection:
                connection.execute(text('DROP DATABASE `%s`' % name))
        server.dispose()


with tempfile.TemporaryDirectory(prefix='cronpilot-d1-browser-') as directory, backend_url(directory) as url:
    test_root = Path(directory)
    cfg = configparser.ConfigParser()
    cfg.read(ROOT / 'conf.ini')
    cfg.set('default', 'cron_db_url', url)
    cfg.set('default', 'cron_job_log_db_url', url)
    cfg.set('default', 'login_pwd', 'isolated-W1-password!')
    cfg.set('default', 'api_access_token', 'isolated-d1-token')
    cfg.set('default', 'api_access_token_required', '1')
    with (test_root / 'conf.ini').open('w') as file:
        cfg.write(file)
    import configs
    configs._proj_root = directory
    from app import create_app, db, scheduler
    from app.rbac.services import ensure_seed_admin
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    from werkzeug.serving import make_server

    app = create_app('development')
    app.config.update(DEBUG=False, TESTING=False)
    with app.app_context():
        for model_file in (ROOT / 'datas/model').glob('*.py'):
            importlib.import_module('datas.model.' + model_file.stem)
        db.create_all()
        ensure_seed_admin()
        from datas.model.cron_infos import CronInfos
        from datas.model.rbac_user import RbacUser
        from datas.model.resource_group import ResourceGroup
        from datas.model.task_group import TaskGroup
        from datas.model.user_group import UserGroup
        group = ResourceGroup(name='D1 验证组')
        user = RbacUser(username='d1_preview', role='operator', is_active=1, auth_version=0,
                        job_title='测试', nickname='预览用户', email='w1@example.invalid')
        user.set_password('D1-preview-only-2026!')
        task = CronInfos(task_name='D1暂停示例', task_keyword='修改说明验证不触碰调度器',
                         req_url='https://8.8.8.8/w1', req_method='GET', req_body='',
                         run_date='', day='', day_of_week='', hour='23', minute='59', second='',
                         status=0, scope_type='GROUP', created_at=1, updated_at=1,
                         last_operator_name='fixture', last_operated_at=1)
        db.session.add_all([group, user, task])
        db.session.flush()
        db.session.add_all([UserGroup(user_id=user.id, group_id=group.id),
                            TaskGroup(task_id=task.id, group_id=group.id)])
        db.session.commit()
    store = SQLAlchemyJobStore(url=url)
    store.start(scheduler.scheduler, 'default')
    preview_port = int(os.environ.get('D1_PREVIEW_PORT', '5003')) if os.environ.get('D1_PREVIEW') else 0
    server = make_server('127.0.0.1', preview_port, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # Verification output is transient until it has passed image governance.
        output_root = Path(tempfile.mkdtemp(prefix='cronpilot-d1-evidence-'))
        print('D1_EVIDENCE_DIR=' + str(output_root), flush=True)
        from scripts.verify_cron_edit_noop_browser import verify
        if not os.environ.get('D1_SKIP_BROWSER'):
            verify('http://127.0.0.1:%s' % server.server_port,
               output_root / 'noop',
               '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
        scheduler.scheduler.start(paused=True)
        from playwright.sync_api import sync_playwright
        output = output_root / 'd1'
        output.mkdir(parents=True, exist_ok=True)
        base = 'http://127.0.0.1:%s' % server.server_port
        with app.app_context():
            demo_id = db.session.scalar(db.select(CronInfos.id).where(CronInfos.task_name == 'D1暂停示例'))
        if os.environ.get('VERIFY_D2'):
            from scripts.verify_cron_status_d2 import verify as verify_d2
            verify_d2(app, scheduler, base, demo_id, output_root / 'd2')
        if os.environ.get('VERIFY_TIMEOUT'):
            from scripts.verify_cron_timeout import verify as verify_timeout
            verify_timeout(app, scheduler, base, demo_id, output_root / 'timeout')
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True,
                executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
            for javascript in (True, False):
                context = browser.new_context(java_script_enabled=javascript)
                page = context.new_page()
                page.goto(base + '/rbac/login')
                page.locator('[name=username]').fill('d1_preview')
                page.locator('[name=password]').fill('D1-preview-only-2026!')
                page.locator('button[type=submit]').click()
                page.wait_for_url('**/cron_list')
                edit = base + '/cron_edit?id=' + str(demo_id)
                page.goto(edit)
                page.locator('[name=minute]').fill('17' if javascript else '18')
                with patch.object(scheduler, 'get_job', side_effect=AssertionError('success queried')):
                    with page.expect_response(lambda r: '/cron_edit' in r.url and r.request.method == 'POST') as saved:
                        page.get_by_role('button', name='保存修改').click(force=True)
                    if javascript:
                        page.wait_for_url('**/cron_list')
                    else:
                        assert saved.value.json()['errcode'] == 0
                        page.wait_for_load_state('load')
                assert scheduler.get_job('cron_%s' % demo_id).next_run_time is None
                page.goto(edit)
                page.locator('[name=minute]').fill('27' if javascript else '28')
                with patch('app.services.cron_service.register_cron_job', side_effect=RuntimeError('SECRET')):
                    page.get_by_role('button', name='保存修改').click(force=True)
                    page.get_by_text('配置已保存，当前调度与目标不一致，请核实', exact=True).wait_for()
                    assert 'SECRET' not in page.locator('body').inner_text()
                    page.screenshot(path=str(output / ('ajax-error.png' if javascript else 'native-error.png')))
                context.close()
            browser.close()
        (output / 'web.json').write_text(json.dumps(dict(ajax_success=True, ajax_error=True,
            native_success=True, native_error=True, paused_registration=True)))
        client = app.test_client()
        data = dict(task_name='d1-api-proof', task_keyword='test task', hour='23', minute='58',
                    req_url='https://8.8.8.8/d1', req_method='GET', timeout_sec='5')
        api_results = []
        response = client.post('/api/cron', data=data, headers={'Authorization': 'Bearer isolated-d1-token'})
        assert response.status_code == 200, (response.status_code, response.data[:1000])
        assert json.loads(response.data)['errcode'] == 0, json.loads(response.data)
        for index, route in enumerate(('/api/cron', '/api/cron/add')):
            data['minute'] = str(10 + index)
            with patch.object(scheduler, 'get_job', side_effect=AssertionError('normal path queried')):
                response = client.post(route, data=data, headers={'Authorization': 'Bearer isolated-d1-token'})
            assert json.loads(response.data)['errcode'] == 0, json.loads(response.data)
            data['minute'] = str(20 + index)
            with patch('app.services.cron_service.register_cron_job', side_effect=RuntimeError('SECRET failure')):
                response = client.post(route, data=data, headers={'Authorization': 'Bearer isolated-d1-token'})
            assert json.loads(response.data)['errcode'] == 1, json.loads(response.data)
            assert '已保存' in json.loads(response.data)['errmsg']
            assert 'SECRET' not in json.loads(response.data)['errmsg']
            data['minute'] = str(30 + index)
            jobstore = scheduler.scheduler._jobstores['default']
            original_update = jobstore.update_job
            def lost_ack(job):
                original_update(job)
                raise RuntimeError('SECRET write applied but ack lost')
            with patch.object(jobstore, 'update_job', side_effect=lost_ack), \
                    patch.object(scheduler, 'get_job', wraps=scheduler.get_job) as query:
                response = client.post(route, data=data, headers={'Authorization': 'Bearer isolated-d1-token'})
                assert json.loads(response.data)['errcode'] == 0, json.loads(response.data)
                query.assert_called_once()
            api_results.append(dict(route=route, success_without_query=True, committed_error=True,
                                    lost_ack_confirmed=True))
        (output / 'api.json').write_text(
            json.dumps(api_results, ensure_ascii=False, indent=2))
        print('D1_API_VERIFIED', flush=True)
        if os.environ.get('D1_PREVIEW'):
            print('D1 preview ready: %s' % base, flush=True)
            threading.Event().wait()
    finally:
        server.shutdown()
        thread.join()
        store.shutdown()
        if scheduler.running:
            scheduler.shutdown()
