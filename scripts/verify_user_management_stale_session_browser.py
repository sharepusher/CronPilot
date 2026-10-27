#!/usr/bin/env python3
"""Browser evidence for database-current authorization on RBAC user management."""

import argparse
import json
import os
import secrets
import shutil
import string
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('CRONPILOT_SCHEDULER_ENABLED', 'false')

from playwright.sync_api import sync_playwright  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402

from app import create_app, db  # noqa: E402
from datas.model.rbac_user import RbacUser  # noqa: E402
from datas.model.user_group import UserGroup  # noqa: E402
from datas.utils.times import utc_now_hms  # noqa: E402

PREFIX = 'r02_browser_'
GROUP_A = 1
GROUP_B = 10


def _password():
    alphabet = string.ascii_letters + string.digits + '-_!'
    return ''.join(secrets.choice(alphabet) for _ in range(28))


def _validate_base_url(value):
    parsed = urlparse(value)
    if parsed.scheme not in ('http', 'https') or parsed.hostname not in (
        '127.0.0.1', 'localhost',
    ):
        raise argparse.ArgumentTypeError('browser verification is local-only')
    return value.rstrip('/')


def _browser_executable():
    for path in (
        shutil.which('google-chrome'),
        shutil.which('chromium'),
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    ):
        if path and Path(path).is_file():
            return path
    return None


def _delete_fixture_rows():
    user_ids = list(db.session.scalars(
        select(RbacUser.id).where(RbacUser.username.like(PREFIX + '%'))
    ))
    if user_ids:
        db.session.execute(delete(UserGroup).where(UserGroup.user_id.in_(user_ids)))
        db.session.execute(delete(RbacUser).where(RbacUser.id.in_(user_ids)))


def _add_user(username, role, group_ids, password):
    user = RbacUser(
        username=username,
        role=role,
        is_active=1,
        auth_version=0,
        must_reset_password=0,
        email=username + '@example.invalid',
        nickname=username,
        job_title='qa',
        create_time=utc_now_hms(),
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    for group_id in group_ids:
        db.session.add(UserGroup(user_id=user.id, group_id=group_id))
    return user


def _prepare(password):
    from datas.model.resource_group import ResourceGroup

    available = set(db.session.scalars(
        select(ResourceGroup.id).where(ResourceGroup.id.in_([GROUP_A, GROUP_B]))
    ))
    if available != {GROUP_A, GROUP_B}:
        raise RuntimeError('requires existing resource groups 1 and 10')
    _delete_fixture_rows()
    actor = _add_user(PREFIX + 'global_admin', 'admin', [], password)
    in_scope = _add_user(PREFIX + 'group_a_target', 'viewer', [GROUP_A], password)
    outside = _add_user(PREFIX + 'group_b_target', 'viewer', [GROUP_B], password)
    global_target = _add_user(PREFIX + 'global_target', 'admin', [], password)
    db.session.commit()
    return actor.id, in_scope.id, outside.id, global_target.id


def _login(page, base_url, username, password):
    page.goto(base_url + '/rbac/login')
    page.locator('input[name="username"]').fill(username)
    page.locator('input[name="password"]').fill(password)
    with page.expect_navigation(wait_until='networkidle'):
        page.get_by_role('button', name='登录', exact=True).click()
    if '/rbac/login' in page.url:
        raise AssertionError('fixture login failed')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', type=_validate_base_url, default='http://127.0.0.1:5001')
    parser.add_argument('--output-dir', default='doc/qa/evidence/rbac-user-management-r02-2026-10-27')
    args = parser.parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    password = _password()
    app = create_app('development')
    evidence = {}

    with app.app_context():
        actor_id, in_scope_id, outside_id, global_target_id = _prepare(password)
        try:
            with sync_playwright() as playwright:
                options = {'headless': True}
                executable = _browser_executable()
                if executable:
                    options['executable_path'] = executable
                browser = playwright.chromium.launch(**options)
                context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                page = context.new_page()
                _login(page, args.base_url, PREFIX + 'global_admin', password)
                page.goto(args.base_url + '/rbac/users/edit?id=%s' % global_target_id)
                page.wait_for_load_state('networkidle')
                global_option = page.locator('option[value="__ALL__"]')
                assert global_option.get_attribute('selected') is not None
                page.screenshot(path=str(output_dir / 'global-scope-form-selected.png'), full_page=True)
                page.goto(args.base_url + '/rbac/users?username=' + PREFIX)
                page.wait_for_load_state('networkidle')
                initial = page.content()
                assert 'data-user-id="%s"' % in_scope_id in initial
                assert 'data-user-id="%s"' % outside_id in initial

                db.session.add(UserGroup(user_id=actor_id, group_id=GROUP_A))
                db.session.commit()
                page.goto(args.base_url + '/rbac/users?username=' + PREFIX)
                page.wait_for_load_state('networkidle')
                narrowed = page.content()
                assert 'data-user-id="%s"' % in_scope_id in narrowed
                assert 'data-user-id="%s"' % outside_id not in narrowed
                page.goto(args.base_url + '/rbac/users/view?id=%s' % outside_id)
                page.wait_for_load_state('networkidle')
                assert page.url.rstrip('/').endswith('/rbac/users')

                actor = db.session.get(RbacUser, actor_id)
                actor.role = 'viewer'
                db.session.commit()
                page.goto(args.base_url + '/rbac/users')
                page.wait_for_load_state('networkidle')
                assert page.locator('body').inner_text().find('无权访问') >= 0
                page.screenshot(path=str(output_dir / 'stale-session-downgraded.png'), full_page=True)
                evidence = {
                    'global_form_all_selected': True,
                    'initial_global_visible': [in_scope_id, outside_id],
                    'after_group_narrowing_visible': [in_scope_id],
                    'outside_detail_redirected': True,
                    'after_role_downgrade_forbidden': True,
                }
                context.close()
                browser.close()
        finally:
            _delete_fixture_rows()
            db.session.commit()
            evidence['residue_users'] = db.session.scalar(
                select(db.func.count()).select_from(RbacUser).where(
                    RbacUser.username.like(PREFIX + '%')
                )
            )
    if evidence['residue_users']:
        raise RuntimeError('fixture cleanup failed: %r' % evidence)
    path = output_dir / 'evidence.json'
    path.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print('R02_USER_MANAGEMENT_BROWSER: OK')
    print(path)


if __name__ == '__main__':
    main()
