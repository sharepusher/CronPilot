"""隔离 harness 的 D2 真实 JobStore 和浏览器验证。"""
import json
from unittest.mock import patch

from playwright.sync_api import sync_playwright

from app import db
from app.services.cron_service import register_cron_job
from datas.model.cron_infos import CronInfos


def verify(app, scheduler, base, task_id, output):
    output.mkdir(parents=True, exist_ok=True)
    with app.app_context():
        task = db.session.get(CronInfos, task_id)
        name = task.task_name
        values = {k: getattr(task, k) or '' for k in ('run_date','day','day_of_week','hour','minute','second')}
        register_cron_job(task_id, values, paused=True)
    client = app.test_client()
    headers = {'Authorization': 'Bearer isolated-d1-token'}
    data = dict(task_name=name, status='1')
    with patch.object(scheduler.scheduler, 'resume_job', side_effect=RuntimeError('injected before write')):
        response = client.post('/api/cron/status', data=data, headers=headers)
    assert response.json['errcode'] == 1, response.json
    token = response.headers['X-Cron-Status-Retry']
    response = client.post('/api/cron/status', data=data, headers=dict(headers, **{'X-Cron-Status-Retry':token}))
    assert response.json['errcode'] == 0, response.json
    next_run = scheduler.get_job('cron_%s'%task_id).next_run_time
    response = client.post('/api/cron/status', data=data, headers=dict(headers, **{'X-Cron-Status-Retry':token}))
    assert response.json['errcode'] == 0
    assert scheduler.get_job('cron_%s'%task_id).next_run_time == next_run
    response = client.post('/api/cron/status', data=dict(data,status='0'),headers=headers)
    assert response.json['errcode'] == 0
    response = client.post('/api/cron/status',data=data,headers=dict(headers,**{'X-Cron-Status-Retry':token}))
    assert response.json['errcode'] == 1
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
        try:
            page=browser.new_page()
            page.goto(base+'/rbac/login')
            page.locator('[name=username]').fill('d1_preview')
            page.locator('[name=password]').fill('D1-preview-only-2026!')
            page.locator('button[type=submit]').click()
            page.wait_for_url('**/cron_list')
            page.get_by_text(name,exact=True).first.click()
            page.wait_for_load_state('load')
            # 详情的现有启动按钮触发明确目标与首次确认。
            button=page.locator('[onclick*="cpToggleTask"]').first
            button.click()
            page.get_by_role('heading',name='启动任务',exact=True).wait_for()
            with patch.object(scheduler.scheduler,'resume_job',side_effect=RuntimeError('injected transient')):
                page.get_by_role('button',name='确认',exact=True).click()
                page.get_by_role('button',name='重试启动',exact=True).wait_for()
            page.screenshot(path=str(output/'retry-visible.png'),full_page=True)
            page.get_by_role('button',name='重试启动',exact=True).click()
            page.wait_for_timeout(1200)
            assert scheduler.get_job('cron_%s'%task_id).next_run_time is not None
            page.screenshot(path=str(output/'retry-success.png'),full_page=True)
            with patch.object(scheduler.scheduler,'resume_job',side_effect=AssertionError('duplicate resume')):
                page.get_by_role('button',name='核实并重新应用目标',exact=True).click()
                page.wait_for_timeout(1200)

            csrf = page.locator('meta[name=csrf-token]').get_attribute('content')
            rejected = page.request.post(base+'/cron_status_apply', form=dict(
                id=str(task_id), status='0', retry_token='forged', csrf_token=csrf))
            assert rejected.json()['errcode'] == 1
            rejected_csrf = page.request.post(base+'/cron_status_apply', form=dict(
                id=str(task_id), status='0', retry_token='forged'))
            assert rejected_csrf.json()['errcode'] == 1
            assert 'CSRF' in rejected_csrf.json()['errmsg']
            from datas.model.rbac_user import RbacUser
            from datas.model.user_group import UserGroup
            with app.app_context():
                user = db.session.scalar(db.select(RbacUser).where(RbacUser.username == 'd1_preview'))
                uid = user.id
                gids = list(db.session.scalars(db.select(UserGroup.group_id).where(UserGroup.user_id == uid)))
                db.session.execute(UserGroup.__table__.delete().where(UserGroup.user_id == uid))
                db.session.commit()
            try:
                assert page.request.get(base+'/cron_status_check?id='+str(task_id)).status == 403
            finally:
                with app.app_context():
                    db.session.add_all([UserGroup(user_id=uid,group_id=gid) for gid in gids])
                    user = db.session.get(RbacUser,uid)
                    user.role = 'viewer'
                    db.session.commit()
            try:
                assert page.request.get(base+'/cron_status_check?id='+str(task_id)).status == 403
            finally:
                with app.app_context():
                    db.session.get(RbacUser,uid).role = 'operator'
                    db.session.commit()


        finally:
            browser.close()
    response = client.post('/api/cron/status', data=dict(data, status='0'), headers=headers)
    assert response.json['errcode'] == 0
    (output/'result.json').write_text(json.dumps(dict(api_retry=True,repeated_resume_keeps_next_run=True,
        stale_retry_rejected=True,browser_confirm_and_retry=True),indent=2))
    print('D2_VERIFIED',flush=True)
