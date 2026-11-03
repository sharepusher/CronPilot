"""由隔离 D1 harness 调用的超时字段真实端点/浏览器验收。"""
import json
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from sqlalchemy import event, select

from app import db
from datas.model.cron_infos import CronInfos
from datas.model.resource_group import ResourceGroup


def verify(app, scheduler, base, demo_id, output):
    output.mkdir(parents=True, exist_ok=True)
    client = app.test_client()
    headers = {'Authorization': 'Bearer isolated-d1-token'}
    results = []

    def stored(name):
        with app.app_context():
            row = db.session.scalar(select(CronInfos).where(CronInfos.task_name == name))
            return row.timeout_sec, row.edit_revision

    with app.app_context():
        engine = db.engine
        db.session.add(ResourceGroup(name='timeout-outside-group'))
        db.session.commit()

    def no_effect_request(route, data, expected, status=200):
        writes = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().split()[0].upper() in ('INSERT', 'UPDATE', 'DELETE'):
                writes.append(statement)
        event.listen(engine, 'before_cursor_execute', capture)
        try:
            with patch('app.services.cron_service.register_cron_job') as register, \
                    patch.object(scheduler, 'get_job') as query:
                response = client.post(route, data=data, headers=headers)
                assert response.status_code == status, (response.status_code, response.data[:500])
                assert response.json['errcode'] == expected, response.json
                register.assert_not_called()
                query.assert_not_called()
                assert not writes, writes
        finally:
            event.remove(engine, 'before_cursor_execute', capture)

    for index, route in enumerate(('/api/cron', '/api/cron/add')):
        name = 'timeout-api-%s' % index
        data = dict(task_name=name, task_keyword='timeout type proof', hour='23', minute='58',
                    req_url='https://8.8.8.8/timeout', req_method='GET', timeout_sec='5',
                    group_name='timeout-outside-group')
        response = client.post(route, data=data, headers=headers)
        assert response.status_code == 200 and response.json['errcode'] == 0, response.data
        assert stored(name)[0] == 5
        data['timeout_sec'] = '17'
        with patch('app.services.cron_service.register_cron_job') as register, \
                patch.object(scheduler, 'get_job') as query:
            response = client.post(route, data=data, headers=headers)
            assert response.json['errcode'] == 0, response.json
            register.assert_not_called()
            query.assert_not_called()
        before = stored(name)
        assert before[0] == 17
        no_effect_request(route, data, 0)
        assert stored(name) == before
        for value in ('0', '121', 'bad', '5.5'):
            no_effect_request(route, dict(data, timeout_sec=value), 1,
                              status=422 if index == 0 else 200)
            assert stored(name) == before
        if index == 0:
            no_effect_request(route, dict(data, timeout_sec=''), 1, status=422)
            data.pop('timeout_sec')  # Schema 默认 None，保持原有覆盖语义。
        else:
            data['timeout_sec'] = ''
        response = client.post(route, data=data, headers=headers)
        assert response.json['errcode'] == 0, response.json
        assert stored(name)[0] is None
        no_effect_request(route, data, 0)
        denied = client.post(route, data=data, headers={'Authorization': 'Bearer invalid-proof-token'})
        assert denied.status_code == 401
        results.append(dict(route=route, create=5, update=17, cleared=True, noop_zero_dml=True,
                            invalid_zero_dml=True, timeout_only_zero_scheduler=True, unauthorized=401))

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True,
            executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
        try:
            page = browser.new_page()
            page.goto(base + '/rbac/login')
            page.locator('[name=username]').fill('d1_preview')
            page.locator('[name=password]').fill('D1-preview-only-2026!')
            page.locator('button[type=submit]').click()
            page.wait_for_url('**/cron_list')
            edit = base + '/cron_edit?id=' + str(demo_id)
            for value, expected in (('12', 12), ('', None)):
                page.goto(edit)
                page.locator('[name=timeout_sec]').fill(value)
                with patch('app.services.cron_service.register_cron_job') as register, \
                        patch.object(scheduler, 'get_job') as query:
                    page.get_by_role('button', name='保存修改').click()
                    page.wait_for_url('**/cron_list')
                    register.assert_not_called()
                    query.assert_not_called()
                with app.app_context():
                    assert db.session.get(CronInfos, demo_id).timeout_sec == expected
            page.goto(edit)
            posts = []
            page.on('request', lambda r: posts.append(r.url) if (
                '/cron_edit' in r.url and r.method == 'POST') else None)
            page.get_by_role('button', name='保存修改').click()
            page.get_by_text('未检测到变更，无需保存', exact=True).wait_for()
            assert not posts
            page.screenshot(path=str(output / 'operator-timeout-noop.png'), full_page=True)
            # 全局 Token 在另一个业务组创建任务，验证反向对象授权。
            with app.app_context():
                outside = db.session.scalar(select(CronInfos.id).where(CronInfos.task_name == 'timeout-api-0'))
            denied = page.goto(base + '/cron_edit?id=' + str(outside))
            assert denied.status == 403
            page.screenshot(path=str(output / 'operator-outside-scope.png'), full_page=True)
        finally:
            browser.close()
    (output / 'result.json').write_text(json.dumps(dict(api=results, web=dict(
        saved=12, cleared=True, noop_posts=0, outside_scope=403)), ensure_ascii=False, indent=2))
    print('TIMEOUT_TYPES_VERIFIED', flush=True)
