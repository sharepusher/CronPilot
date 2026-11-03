"""本地真实页面验收，唯一前缀 fixture，结束后清理；不修改已有账号/任务。"""
import argparse
import json
import sys
import uuid
from pathlib import Path

from apscheduler.jobstores.base import JobLookupError
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from flask import Flask
from playwright.sync_api import sync_playwright
from sqlalchemy import create_engine, delete, func, select, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import db
from configs import configs
from datas.model.cron_infos import CronInfos
from datas.model.operation_log import OperationLog
from datas.model.rbac_audit_log import RbacAuditLog
from datas.model.rbac_user import RbacUser
from datas.model.resource_group import ResourceGroup
from datas.model.tag import Tag
from datas.model.task_group import TaskGroup
from datas.model.task_tag import TaskTag
from datas.model.user_group import UserGroup


def verify(base_url, output, executable):
    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI=configs('cron_job_log_db_url'),
                      SQLALCHEMY_TRACK_MODIFICATIONS=False)
    db.init_app(app)
    prefix = 'noop_verify_' + uuid.uuid4().hex[:10]
    password = uuid.uuid4().hex + '!Proof9'
    user_ids = []
    group_id = task_id = None
    results = []
    with app.app_context():
        group = ResourceGroup(name=prefix)
        db.session.add(group)
        db.session.flush()
        group_id = group.id
        for role in ('operator', 'viewer', 'admin'):
            user = RbacUser(username=prefix + '_' + role, role=role,
                            is_active=1, auth_version=0, job_title='qa',
                            nickname='verification', email=prefix + '_' + role + '@example.invalid')
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            user_ids.append(user.id)
            db.session.add(UserGroup(user_id=user.id, group_id=group_id))
        task = CronInfos(task_name=prefix, task_keyword='original description',
                         req_url='https://8.8.8.8/noop-verification', req_method='GET',
                         req_body='', run_date='', day='', day_of_week='', hour='23',
                         minute='59', second='', timeout_sec=None, status=0,
                         scope_type='GROUP', created_at=1, updated_at=1,
                         last_operator_name='fixture', last_operated_at=1)
        db.session.add(task)
        db.session.flush()
        task_id = task.id
        db.session.add(TaskGroup(task_id=task_id, group_id=group_id))
        db.session.commit()

    def snapshot():
        with app.app_context():
            task = db.session.get(CronInfos, task_id)
            return (task.task_keyword, task.updated_at, task.last_operator_name,
                    task.last_operated_at, db.session.scalar(select(func.count()).select_from(
                        OperationLog).where(OperationLog.target_id == task_id)))

    def fixture_job_exists():
        engine = create_engine(configs('cron_db_url'))
        try:
            with engine.connect() as connection:
                return bool(connection.execute(text('SELECT COUNT(*) FROM apscheduler_jobs WHERE id=:id'),
                                               {'id': 'cron_%s' % task_id}).scalar_one())
        finally:
            engine.dispose()

    try:
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=executable)
            context = browser.new_context(viewport={'width': 1440, 'height': 1000})
            page = context.new_page()

            def login(role, target=page):
                target.goto(base_url + '/rbac/login')
                target.locator('[name=username]').fill('admin' if role == 'seed' else prefix + '_' + role)
                target.locator('[name=password]').fill(configs('login_pwd') if role == 'seed' else password)
                target.locator('button[type=submit]').click()
                target.wait_for_url('**/cron_list')

            login('operator')
            edit = base_url + '/cron_edit?id=' + str(task_id)
            page.goto(edit)
            page.locator('.js-cron-edit-noop').wait_for()
            posts = []
            page.on('request', lambda r: posts.append(r.url) if (
                r.method == 'POST' and '/cron_edit' in r.url) else None)
            before = snapshot()
            page.get_by_role('button', name='保存修改').click()
            page.get_by_text('未检测到变更，无需保存', exact=True).wait_for()
            assert not posts and snapshot() == before
            results.append({'case': 'click_noop', 'posts': 0, 'database_unchanged': True})
            description = page.locator('[name=task_keyword]')
            description.fill('temporary')
            description.fill('original description')
            description.press('Enter')
            page.wait_for_timeout(300)
            assert not posts and snapshot() == before
            results.append({'case': 'revert_and_enter', 'posts': 0})
            page.screenshot(path=str(output / 'operator-noop.png'), full_page=True)
            token = page.locator('meta[name=csrf-token]').get_attribute('content')
            payload = page.locator('form.tf-form').evaluate(
                '(form) => Object.fromEntries(new FormData(form).entries())')
            payload['csrf_token'] = token
            response = page.request.post(edit, form=payload,
                                         headers={'X-Requested-With': 'XMLHttpRequest'})
            assert response.json()['data']['outcome'] == 'no_change'
            assert snapshot() == before
            results.append({'case': 'bypass_js', 'outcome': 'no_change'})
            # A description-only edit must not create the deliberately absent scheduler job.
            assert not fixture_job_exists()
            description.fill('verified real description change')
            page.get_by_role('button', name='保存修改').click()
            page.wait_for_url('**/cron_list')
            assert len(posts) == 1 and snapshot()[0] == 'verified real description change'
            assert not fixture_job_exists()
            results.append({'case': 'description_change_without_scheduler_job', 'posts': 1})
            page.goto(edit)
            before = snapshot()
            payload['task_keyword'] = 'verified real description change'
            payload['edit_snapshot'] = page.locator('[name=edit_snapshot]').get_attribute('value')
            payload['csrf_token'] = page.locator('meta[name=csrf-token]').get_attribute('content')
            # Native form path without an Ajax header must PRG to same edit page.
            response = page.request.post(edit, form=payload, max_redirects=0)
            assert response.status == 302 and 'outcome=no_change' in response.headers['location']
            assert snapshot() == before
            results.append({'case': 'native_prg', 'status': 302})
            native_context = browser.new_context(java_script_enabled=False)
            native_page = native_context.new_page()
            login('operator', native_page)
            native_page.goto(edit)
            before = snapshot()
            # With JS disabled, shell transitions can keep Playwright's stability probe waiting.
            # A forced pointer click still performs the real browser's native form submission.
            native_page.get_by_role('button', name='保存修改').click(force=True)
            native_page.wait_for_url('**/cron_edit?**outcome=no_change')
            assert '未检测到变更，无需保存' in native_page.locator('[role=status]').inner_text()
            assert snapshot() == before
            native_page.screenshot(path=str(output / 'native-noop.png'), full_page=True)
            results.append({'case': 'javascript_disabled', 'outcome': 'no_change'})
            native_context.close()
            # Two live browser sessions with independently loaded signed originals.
            peer_context = browser.new_context()
            peer = peer_context.new_page()
            login('operator', peer)
            peer.goto(edit)
            peer.locator('[name=task_keyword]').fill('other editor description')
            peer.get_by_role('button', name='保存修改').click()
            peer.wait_for_url('**/cron_list')
            page.locator('[name=timeout_sec]').fill('10')
            page.get_by_role('button', name='保存修改').click()
            page.wait_for_url('**/cron_list')
            with app.app_context():
                stored = db.session.get(CronInfos, task_id)
                assert stored.task_keyword == 'other editor description' and stored.timeout_sec == 10
            results.append({'case': 'concurrent_unrelated_merge', 'passed': True})
            page.goto(edit)
            old_token = page.locator('[name=edit_snapshot]').get_attribute('value')
            peer.goto(edit)
            peer.locator('[name=task_keyword]').fill('newer peer description')
            peer.get_by_role('button', name='保存修改').click()
            peer.wait_for_url('**/cron_list')
            page.locator('[name=task_keyword]').fill('conflicting description')
            page.locator('[name=timeout_sec]').fill('20')
            page.get_by_role('button', name='保存修改').click()
            page.locator('.tf-container [role=alert]').wait_for()
            assert page.locator('[name=edit_snapshot]').get_attribute('value') == old_token
            with app.app_context():
                stored = db.session.get(CronInfos, task_id)
                assert stored.task_keyword == 'newer peer description' and stored.timeout_sec == 10
            page.screenshot(path=str(output / 'conflict.png'), full_page=True)
            conflict_payload = page.locator('form.tf-form').evaluate(
                '(form) => Object.fromEntries(new FormData(form).entries())')
            response = page.request.post(edit, form=conflict_payload)
            assert old_token in response.text() and 'conflicting description' in response.text()
            assert 'role="alert"' in response.text()
            results.append({'case': 'native_conflict_keeps_original_token', 'passed': True})
            page.get_by_role('button', name='重新加载', exact=True).click()
            page.get_by_role('heading', name='重新加载编辑页').wait_for()
            page.get_by_role('button', name='取消', exact=True).click()
            assert page.locator('[name=edit_snapshot]').get_attribute('value') == old_token
            page.get_by_role('button', name='重新加载', exact=True).click()
            page.get_by_role('button', name='确认', exact=True).click()
            page.wait_for_load_state('load')
            page.wait_for_function('(old) => document.querySelector("[name=edit_snapshot]").value !== old', arg=old_token)
            assert page.locator('[name=task_keyword]').input_value() == 'newer peer description'
            results.append({'case': 'conflict_rejects_partial_save_and_explicit_reload', 'passed': True})
            peer_context.close()
            # Pending tag text must be committed before preflight; no blur race may swallow it.
            page.locator('#tags_input').fill('pending-proof')
            page.get_by_role('button', name='保存修改').click()
            page.wait_for_url('**/cron_list')
            with app.app_context():
                tag_names = list(db.session.scalars(select(Tag.name).join(
                    TaskTag, Tag.id == TaskTag.tag_id).where(TaskTag.task_id == task_id)))
            assert tag_names == ['pending-proof']
            results.append({'case': 'pending_tag_input', 'saved': True})
            for role, expected in (('viewer', 403), ('admin', 200), ('seed', 403)):
                other = browser.new_context()
                denied = other.new_page()
                login(role, denied)
                response = denied.goto(edit)
                assert response.status == expected, (role, response.status)
                results.append({'case': role + '_access', 'status': expected})
                other.close()
            page.goto(edit)
            page.screenshot(path=str(output / 'operator-edit.png'), full_page=True)
            browser.close()
    finally:
        # Remove only the job ID belonging to the fixture, even if browser assertions fail.
        store = SQLAlchemyJobStore(url=configs('cron_db_url'))
        try:
            try:
                store.remove_job('cron_%s' % task_id)
            except JobLookupError:
                pass
        finally:
            store.engine.dispose()
        with app.app_context():
            # Specific fixture IDs only, no table truncation or existing-data writes.
            for model, condition in (
                (TaskTag, TaskTag.task_id == task_id), (TaskGroup, TaskGroup.task_id == task_id),
                (Tag, Tag.group_id == group_id),
                (OperationLog, OperationLog.target_id == task_id),
                (CronInfos, CronInfos.id == task_id),
                (RbacAuditLog, RbacAuditLog.user_id.in_(user_ids)),
                (UserGroup, UserGroup.user_id.in_(user_ids)),
                (RbacUser, RbacUser.id.in_(user_ids)),
                (ResourceGroup, ResourceGroup.id == group_id),
            ):
                db.session.execute(delete(model).where(condition))
            db.session.commit()
            remaining = db.session.scalar(select(func.count()).select_from(CronInfos).where(
                CronInfos.id == task_id))
            assert remaining == 0
    report = {'cases': results, 'fixture_cleanup': 'complete'}
    (output / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:5001')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--executable-path', default='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
    args = parser.parse_args()
    verify(args.base_url, args.output, args.executable_path)
