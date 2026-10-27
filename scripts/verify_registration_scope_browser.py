#!/usr/bin/env python3
"""R2-4 registration-review browser matrix with isolated, self-cleaning fixtures."""

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

from flask import current_app  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402

from app import create_app, db  # noqa: E402
from app.repositories.registration_request_repository import (  # noqa: E402
    RegistrationRequestRepository,
)
from app.services.pagination import PageQuery  # noqa: E402
from datas.model.rbac_registration_request import (  # noqa: E402
    RbacRegistrationRequest,
)
from datas.model.rbac_registration_request_group import (  # noqa: E402
    RbacRegistrationRequestGroup,
)
from datas.model.rbac_user import RbacUser  # noqa: E402
from datas.model.user_group import UserGroup  # noqa: E402
from datas.utils.times import utc_now_hms  # noqa: E402

PREFIX = 'r2_r4_'
MATRIX_PREFIX = PREFIX + 'matrix_'
PAGE_PREFIX = PREFIX + 'page_g1_'
GROUP_1 = 1
GROUP_10 = 10


def _password():
    alphabet = string.ascii_letters + string.digits + '-_!'
    return ''.join(secrets.choice(alphabet) for _ in range(28))


def _delete_fixture_rows():
    request_ids = list(db.session.scalars(
        select(RbacRegistrationRequest.id).where(
            RbacRegistrationRequest.username.like(PREFIX + '%')
        )
    ))
    if request_ids:
        db.session.execute(
            delete(RbacRegistrationRequestGroup).where(
                RbacRegistrationRequestGroup.registration_request_id.in_(request_ids)
            )
        )
        db.session.execute(
            delete(RbacRegistrationRequest).where(
                RbacRegistrationRequest.id.in_(request_ids)
            )
        )
    user_ids = list(db.session.scalars(
        select(RbacUser.id).where(RbacUser.username.like(PREFIX + '%'))
    ))
    if user_ids:
        db.session.execute(delete(UserGroup).where(UserGroup.user_id.in_(user_ids)))
        db.session.execute(delete(RbacUser).where(RbacUser.id.in_(user_ids)))


def _add_user(username, group_ids, password):
    user = RbacUser(
        username=username,
        role='admin',
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


def _add_request(username, role, group_ids, status='pending'):
    csv_groups = '__ALL__' if group_ids == '__ALL__' else ','.join(
        str(value) for value in group_ids
    )
    request = RbacRegistrationRequest(
        email=username + '@example.invalid',
        username=username,
        password_hash='r2-r4-fixture-not-for-login',
        role=role,
        group_ids=csv_groups,
        job_title='qa',
        nickname=username,
        reason='R2-4 browser scope verification',
        status=status,
        pending_username=username if status == 'pending' else None,
        create_time=utc_now_hms(),
    )
    db.session.add(request)
    db.session.flush()
    if group_ids != '__ALL__':
        for group_id in group_ids:
            db.session.add(RbacRegistrationRequestGroup(
                registration_request_id=request.id,
                group_id=group_id,
            ))


def _prepare(password):
    from datas.model.resource_group import ResourceGroup

    actual_group_ids = set(db.session.scalars(
        select(ResourceGroup.id).where(ResourceGroup.id.in_([GROUP_1, GROUP_10]))
    ))
    if actual_group_ids != {GROUP_1, GROUP_10}:
        raise RuntimeError('R2-4 requires existing resource groups 1 and 10')

    _delete_fixture_rows()
    _add_user(PREFIX + 'group1_admin', [GROUP_1], password)
    _add_user(PREFIX + 'group10_admin', [GROUP_10], password)
    _add_user(PREFIX + 'multi_admin', [GROUP_1, GROUP_10], password)
    _add_user(PREFIX + 'global_admin', [], password)

    matrix = [
        ('viewer_g1', 'viewer', [GROUP_1], 'pending'),
        ('viewer_g10', 'viewer', [GROUP_10], 'pending'),
        ('viewer_g1_g10', 'viewer', [GROUP_1, GROUP_10], 'pending'),
        ('admin_g1', 'admin', [GROUP_1], 'pending'),
        ('admin_g10', 'admin', [GROUP_10], 'pending'),
        ('admin_g1_g10', 'admin', [GROUP_1, GROUP_10], 'pending'),
        ('admin_global', 'admin', '__ALL__', 'pending'),
        ('approved_g1', 'viewer', [GROUP_1], 'approved'),
    ]
    for name, role, groups, status in matrix:
        _add_request(MATRIX_PREFIX + name, role, groups, status)
    for index in range(21):
        _add_request(PAGE_PREFIX + '%02d' % index, 'viewer', [GROUP_1])
    db.session.commit()


def _expectations():
    repo = RegistrationRequestRepository(db.session)
    result = {}
    for name, group_ids in {
        'group1': [GROUP_1],
        'group10': [GROUP_10],
        'multi': [GROUP_1, GROUP_10],
    }.items():
        page = repo.paginate_by_groups(
            PageQuery(per_page=200),
            group_ids,
            search_username=MATRIX_PREFIX,
        )
        result[name] = {
            'users': sorted(row.username for row in page.items),
            'total': page.total,
            'badge': repo.get_pending_count_by_groups(group_ids),
            'actor_group_ids': group_ids,
        }
    page = repo.paginate_all(
        PageQuery(per_page=200), search_username=MATRIX_PREFIX
    )
    result['global'] = {
        'users': sorted(row.username for row in page.items),
        'total': page.total,
        'badge': repo.get_pending_count_all(),
    }
    return result


def _login(page, base_url, username, password, expected_group_ids):
    page.goto(base_url + '/rbac/login')
    page.locator('input[name="username"]').fill(username)
    page.locator('input[name="password"]').fill(password)
    with page.expect_navigation(wait_until='networkidle'):
        page.get_by_role('button', name='登录', exact=True).click()
    if '/rbac/login' in page.url:
        raise AssertionError('R2-4 fixture login failed for %s' % username)
    cookie_name = current_app.config.get('SESSION_COOKIE_NAME', 'session')
    cookie = next(
        item for item in page.context.cookies() if item['name'] == cookie_name
    )
    serializer = current_app.session_interface.get_signing_serializer(current_app)
    session_data = serializer.loads(cookie['value'])
    actual_group_ids = sorted(int(value) for value in session_data.get('group_ids', []))
    assert session_data.get('username') == username, session_data
    assert actual_group_ids == sorted(expected_group_ids), session_data


def _visible_usernames(page):
    values = page.locator(
        'tbody tr:not(.rr-detail-row) > td:nth-child(2)'
    ).all_inner_texts()
    return sorted(
        value.strip() for value in values if value.strip().startswith(MATRIX_PREFIX)
    )


def _verify_view(page, base_url, expected, screenshot_path):
    page.goto(base_url + '/rbac/registration_review?username=' + MATRIX_PREFIX)
    page.wait_for_load_state('networkidle')
    actual_users = _visible_usernames(page)
    total = page.locator('.count').inner_text().strip()
    heading_badge = page.locator('.pg-badge-count').inner_text().strip()
    nav_badge = page.locator('.cp-nav-badge').inner_text().strip()
    page.screenshot(path=str(screenshot_path), full_page=True)
    assert actual_users == expected['users'], (actual_users, expected['users'])
    assert total == '%d total' % expected['total'], total
    assert heading_badge == str(expected['badge']), heading_badge
    assert nav_badge == str(expected['badge']), nav_badge
    return {
        'users': actual_users,
        'total': expected['total'],
        'heading_badge': int(heading_badge),
        'nav_badge': int(nav_badge),
    }


def _verify_page_two(page, base_url, expected_badge, screenshot_path):
    page.goto(
        base_url
        + '/rbac/registration_review?username='
        + PAGE_PREFIX
        + '&page=2'
    )
    page.wait_for_load_state('networkidle')
    html = page.content()
    assert PAGE_PREFIX + '00' in html
    assert PAGE_PREFIX + '20' not in html
    assert page.locator('.count').inner_text().strip() == '21 total'
    assert page.locator('.pg-badge-count').inner_text().strip() == str(expected_badge)
    assert page.locator('.cp-nav-badge').inner_text().strip() == str(expected_badge)
    page.screenshot(path=str(screenshot_path), full_page=True)


def _downgrade_global_actor():
    actor = db.session.scalar(
        select(RbacUser).where(RbacUser.username == PREFIX + 'global_admin')
    )
    db.session.add(UserGroup(user_id=actor.id, group_id=GROUP_1))
    db.session.commit()


def _residue():
    users = db.session.scalar(
        select(db.func.count()).select_from(RbacUser).where(
            RbacUser.username.like(PREFIX + '%')
        )
    )
    requests = db.session.scalar(
        select(db.func.count()).select_from(RbacRegistrationRequest).where(
            RbacRegistrationRequest.username.like(PREFIX + '%')
        )
    )
    return {'users': users, 'requests': requests}


def _validate_base_url(value):
    parsed = urlparse(value)
    if parsed.scheme not in ('http', 'https') or parsed.hostname not in (
        '127.0.0.1', 'localhost'
    ):
        raise argparse.ArgumentTypeError('R2-4 browser verification is local-only')
    return value.rstrip('/')


def _browser_executable(explicit_path=None):
    candidates = [
        explicit_path,
        shutil.which('google-chrome'),
        shutil.which('chromium'),
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--base-url', type=_validate_base_url, default='http://127.0.0.1:5001'
    )
    parser.add_argument(
        '--output-dir',
        default='doc/qa/evidence/rbac-registration-r2-4-2026-10-26',
    )
    parser.add_argument('--browser-executable')
    args = parser.parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    password = _password()
    app = create_app('development')
    evidence = {}

    with app.app_context():
        try:
            _prepare(password)
            expected = _expectations()
            with sync_playwright() as playwright:
                executable = _browser_executable(args.browser_executable)
                launch_options = {'headless': True}
                if executable:
                    launch_options['executable_path'] = executable
                browser = playwright.chromium.launch(**launch_options)
                for name, username in {
                    'group1': PREFIX + 'group1_admin',
                    'group10': PREFIX + 'group10_admin',
                    'multi': PREFIX + 'multi_admin',
                }.items():
                    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                    page = context.new_page()
                    _login(
                        page,
                        args.base_url,
                        username,
                        password,
                        expected[name]['actor_group_ids'],
                    )
                    evidence[name] = _verify_view(
                        page,
                        args.base_url,
                        expected[name],
                        output_dir / ('%s.png' % name),
                    )
                    if name == 'group1':
                        _verify_page_two(
                            page,
                            args.base_url,
                            expected[name]['badge'],
                            output_dir / 'group1-page2.png',
                        )
                    context.close()

                context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                page = context.new_page()
                _login(page, args.base_url, PREFIX + 'global_admin', password, [])
                evidence['global'] = _verify_view(
                    page,
                    args.base_url,
                    expected['global'],
                    output_dir / 'global.png',
                )
                _downgrade_global_actor()
                evidence['stale_session_downgraded'] = _verify_view(
                    page,
                    args.base_url,
                    expected['group1'],
                    output_dir / 'stale-session-downgraded.png',
                )
                context.close()
                browser.close()
        finally:
            _delete_fixture_rows()
            db.session.commit()
            evidence['residue'] = _residue()

    if evidence['residue'] != {'users': 0, 'requests': 0}:
        raise RuntimeError('R2-4 fixture cleanup failed: %r' % evidence['residue'])
    evidence_path = output_dir / 'evidence.json'
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )
    print('R2_4_BROWSER_MATRIX: OK')
    print(str(evidence_path))
    return 0


if __name__ == '__main__':
    sys.exit(main())
