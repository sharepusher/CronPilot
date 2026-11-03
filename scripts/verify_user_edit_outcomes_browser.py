#!/usr/bin/env python3
"""Real-browser seven-outcome verification, exclusively against owned memory HTTP app."""
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

from scripts.user_edit_browser_harness import Harness, prepare_output, require, verify_results

CASES = (
    'updated', 'no_change', 'no_change_server', 'confirm_cancel_save',
    'confirm_server', 'already_applied', 'conflict', 'failed_field', 'failed_flush',
    'unknown_before', 'unknown_after', 'unknown_after_auth', 'recovery',
    'global_updated', 'global_no_change', 'scope_denied', 'operator_denied', 'viewer_denied',
    'native_no_change', 'native_confirm', 'native_updated', 'native_already_applied',
    'native_conflict', 'native_failed', 'native_unknown_before', 'native_unknown_after',
    'csrf_denied',
)
FORM = 'form.js-user-edit-form'
BUTTON = 'button.js-ajax-submit'


def login(page, h, user, native=False):
    response = page.goto(h.url + '/rbac/login?next=/rbac/users')
    require(response.status == 200, 'login_get_failed')
    page.locator('[name=username]').fill(user['username'])
    page.locator('[name=password]').fill(h.password)
    page.locator('#login-submit').click(force=native)
    # Non-admin roles cannot view the requested destination; authentication still executes.
    page.wait_for_url('**/rbac/users')
    page.wait_for_load_state('networkidle')


def observe(page):
    page.verification_responses = []
    def response_message(message):
        if message.text.startswith('VERIFIER_RESPONSE:'):
            page.verification_responses.append(json.loads(message.text[len('VERIFIER_RESPONSE:'):]))
    page.on('console', response_message)
    page.evaluate('''() => {
        window.verificationEvents = [];
        jQuery(document).on('cp:form-outcome.verification', function(_e, data) {
            window.verificationEvents.push(data.data.outcome);
        });
        jQuery.ajaxPrefilter(function(_options, _original, xhr) {
            xhr.done(function(data) {
                console.debug('VERIFIER_RESPONSE:' + JSON.stringify({
                    errcode:data.errcode, errmsg:data.errmsg, url:data.url,
                    data: data.data && {outcome:data.data.outcome, field:data.data.field}}));
            });
        });
    }''')


def post_response(response):
    return response.request.method == 'POST' and urlsplit(response.url).path == '/rbac/users/edit'


def click_ajax(page):
    with page.expect_event('console', predicate=lambda message: message.text.startswith(
            'VERIFIER_RESPONSE:')) as captured, page.expect_response(post_response) as response:
        page.locator(BUTTON).click()
    require(response.value.status == 200, 'ajax_http_error')
    page.wait_for_load_state('networkidle')
    return json.loads(captured.value.text[len('VERIFIER_RESPONSE:'):])


def ready(page):
    page.wait_for_function('''() => {
        const b = jQuery('form.js-user-edit-form button.js-ajax-submit');
        return b.length === 1 && !b.prop('disabled') && !b.data('loading');
    }''')


def native_submit(page):
    with page.expect_navigation() as navigation:
        page.locator(BUTTON).click(force=True)
    page.wait_for_load_state('networkidle')
    return navigation.value.status


def bypass_post(page, omit_csrf=False):
    return page.evaluate('''async ({omitCsrf}) => {
        const f = document.querySelector('form.js-user-edit-form');
        const body = new URLSearchParams(new FormData(f));
        if (omitCsrf) body.delete('csrf_token');
        const r = await fetch(f.action, {method:'POST', body,
            headers:{'X-Requested-With':'XMLHttpRequest'}});
        return r.json();
    }''', {'omitCsrf': omit_csrf})


def concurrent(browser, h, users, nickname):
    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
    try:
        other = context.new_page()
        login(other, h, users['other'])
        other.goto(h.url + '/rbac/users/edit?id=' + str(users['target']['id']))
        observe(other)
        other.locator('#uf-nickname').fill(nickname)
        require(click_ajax(other)['errcode'] == 0, 'concurrent_setup_failed')
        other.wait_for_url('**/rbac/users')
    finally:
        context.close()


def check_state(before, after, changes=None, audits=0, auth=False):
    expected = dict(before)
    expected.update(changes or {})
    expected['audit'] += audits
    if auth:
        expected['auth_version'] += 1
        require(after['secret'] != before['secret'], 'auth_token_not_changed')
        expected['secret'] = after['secret']
    require(after == expected, 'persistence_or_side_effect_mismatch')
    return {'changed_fields': sorted(key for key in before if before[key] != after[key]
                                    and key != 'secret'),
            'credentials_changed': before['secret'] != after['secret'],
            'audit_delta': after['audit'] - before['audit'],
            'auth_version_delta': after['auth_version'] - before['auth_version'],
            'outside_groups_preserved': after['groups'] == before['groups']}


class Runner:
    def __init__(self, h, browser, output):
        self.h, self.browser, self.output = h, browser, output
        self.results = []
        self.case_id = None

    def run_case(self, case_id):
        self.case_id = case_id
        native = case_id.startswith('native_')
        users = self.h.fixture(case_id)
        context = self.browser.new_context(java_script_enabled=not native,
                                           viewport={'width': 1440, 'height': 1000})
        try:
            page = context.new_page()
            page.set_default_timeout(12000)
            role = 'global' if case_id.startswith('global_') else (
                case_id.split('_')[0] if case_id in ('operator_denied', 'viewer_denied') else 'actor')
            login(page, self.h, users[role], native)
            target = users['outside'] if case_id == 'scope_denied' else users['target']
            edit_url = self.h.url + '/rbac/users/edit?id=' + str(target['id'])
            response = page.goto(edit_url)
            page.wait_for_load_state('networkidle')
            if case_id.endswith('_denied') and case_id != 'csrf_denied':
                require(page.locator(FORM).count() == 0, 'unauthorized_edit_form_visible')
                if role in ('operator', 'viewer'):
                    require(response.status == 403, 'role_not_forbidden')
                else:
                    require(page.url != edit_url, 'outside_scope_not_redirected')
                    baseline = self.h.state(target)
                    token = page.locator('meta[name=csrf-token]').get_attribute('content')
                    denied = page.evaluate('''async ({id, csrf}) => {
                        const body = new URLSearchParams({id,csrf_token:csrf,nickname:'denied'});
                        const r = await fetch('/rbac/users/edit', {method:'POST',body,
                            headers:{'X-Requested-With':'XMLHttpRequest'}});
                        return r.json();
                    }''', {'id': str(target['id']), 'csrf': token})
                    require(denied['errcode'] == 1, 'outside_scope_post_not_denied')
                    check_state(baseline, self.h.state(target))
                page.screenshot(path=str(self.output / (case_id + '.png')), full_page=True)
                self.results.append({'case_id': case_id, 'semantic': 'access_denied',
                                     'role': role, 'http_status': response.status, 'passed': True})
                return
            require(response.status == 200, 'edit_get_failed')
            page.locator(FORM).wait_for(state='visible')
            if not native:
                observe(page)
            posts = []
            page.on('request', lambda req: posts.append(req) if (
                req.method == 'POST' and urlsplit(req.url).path == '/rbac/users/edit') else None)
            trace_start = len(self.h.traces)
            before = self.h.state(target)
            data, semantic, changes, audits, auth = None, None, {}, 0, False
            mode = None
            notice = None
            if 'already_applied' in case_id or 'conflict' in case_id:
                concurrent(self.browser, self.h, users,
                           'requested' if 'already_applied' in case_id else 'concurrent')
                before = self.h.state(target)
                # Exclude the other authenticated writer from this request's evidence.
                trace_start = len(self.h.traces)
            if case_id == 'csrf_denied':
                data = bypass_post(page, omit_csrf=True)
                require(data['errcode'] == 1 and 'CSRF' in data['errmsg'], 'csrf_not_rejected')
                semantic = 'failed'
            elif case_id in ('no_change', 'global_no_change', 'native_no_change'):
                semantic, notice = 'no_change', '未检测到变更，无需保存'
                if native:
                    native_submit(page)
                    require('outcome=no_change' in page.url, 'native_noop_not_prg')
                else:
                    page.locator(BUTTON).click()
                    require(not posts, 'frontend_noop_posted')
            elif case_id == 'no_change_server':
                data, semantic = bypass_post(page), 'no_change'
            elif case_id in ('confirm_cancel_save', 'confirm_server', 'native_confirm'):
                page.locator('#uf-email').fill('')
                if native:
                    old_token = page.locator('[name=edit_snapshot_token]').input_value()
                    native_submit(page)
                    require(page.locator('[name=edit_snapshot_token]').input_value() == old_token,
                            'native_confirmation_replaced_baseline')
                    require(page.locator('#uf-email').input_value() == '', 'native_email_input_lost')
                    page.locator('#uf-email-clear-reason').wait_for(state='visible')
                    check_state(before, self.h.state(target))
                    page.screenshot(path=str(self.output / (case_id + '-fallback.png')), full_page=True)
                    page.locator('#uf-email-clear-reason').fill('native isolated verification')
                    native_submit(page)
                    page.wait_for_url('**/rbac/users')
                    semantic, changes, audits = 'updated', {'email': None}, 1
                else:
                    if case_id == 'confirm_server':
                        page.evaluate("jQuery('form.js-user-edit-form').off('cp:form-before-ajax-submit')")
                        data = click_ajax(page)
                        require(data['data']['outcome'] == 'confirm_required', 'server_confirm_not_reached')
                    else:
                        page.locator(BUTTON).click()
                    modal = page.locator('.cp-modal-overlay')
                    modal.get_by_text('确认清空邮箱', exact=True).wait_for(state='visible')
                    modal.get_by_role('button', name='取消', exact=True).wait_for(state='visible')
                    modal.get_by_role('button', name='确认清空并保存', exact=True).wait_for(state='visible')
                    page.screenshot(path=str(self.output / (case_id + '-modal.png')), full_page=True)
                    if case_id == 'confirm_server':
                        modal.get_by_role('button', name='取消', exact=True).click()
                        semantic = 'confirm_required'
                    else:
                        require(not posts, 'clear_email_post_before_confirmation')
                        modal.get_by_role('button', name='取消', exact=True).click()
                        require(not posts, 'clear_email_cancel_posted')
                        check_state(before, self.h.state(target))
                        page.locator(BUTTON).click()
                        modal.locator('textarea').fill('isolated verification')
                        with page.expect_event('console', predicate=lambda message: message.text.startswith(
                                'VERIFIER_RESPONSE:')) as captured, page.expect_response(post_response) as saved:
                            modal.get_by_role('button', name='确认清空并保存', exact=True).click()
                        require(saved.value.status == 200, 'confirmation_save_http_error')
                        page.wait_for_url('**/rbac/users')
                        data = json.loads(captured.value.text[len('VERIFIER_RESPONSE:'):])
                        semantic, changes, audits = 'updated', {'email': None}, 1
            else:
                semantic = 'updated'
                page.locator('#uf-nickname').fill('requested')
                if 'already_applied' in case_id:
                    semantic, notice = 'already_applied', '目标状态已存在，无需重复保存'
                elif 'conflict' in case_id:
                    semantic, notice = 'conflict', '该用户信息已变更'
                    page.locator('#uf-email').fill('requested@example.invalid')
                elif case_id in ('failed_field', 'native_failed'):
                    page.locator('#uf-job-title-select').select_option('' if native else 'other')
                    if not native:
                        page.locator('[name=job_title_other]').fill(' ')
                    semantic, notice = 'failed', '岗位'
                elif case_id == 'failed_flush':
                    mode, semantic, notice = 'flush_after', 'failed', '保存失败'
                elif 'unknown_' in case_id:
                    mode = 'commit_before' if case_id.endswith('before') else 'commit_after'
                    if case_id == 'unknown_after_auth':
                        page.locator('#uf-role-select').select_option('operator')
                    semantic, notice = 'commit_unknown', '保存结果无法确认'
                if mode:
                    self.h.arm(target, mode)
                if native:
                    native_submit(page)
                else:
                    data = click_ajax(page)
                if semantic == 'updated':
                    page.wait_for_url('**/rbac/users')
                    changes, audits = {'nickname': 'requested'}, 1
                elif mode == 'commit_after':
                    changes, audits = {'nickname': 'requested'}, 1
                    if case_id == 'unknown_after_auth':
                        changes['role'] = 'operator'
                        auth = True
            if notice:
                page.get_by_text(notice, exact=False).first.wait_for(state='visible')
            if semantic in ('already_applied', 'conflict', 'commit_unknown', 'failed'):
                require('/rbac/users/edit' in page.url, 'error_or_equivalent_not_staying_on_edit')
                if not native:
                    ready(page)
                    if semantic in ('already_applied', 'conflict', 'commit_unknown'):
                        require(data['data']['outcome'] == semantic, 'explicit_outcome_mismatch')
            if semantic == 'no_change' and data:
                require(data['data']['outcome'] == 'no_change', 'server_noop_mismatch')
            if semantic == 'updated' and data:
                require(data['errcode'] == 0, 'update_response_not_success')
            effects = check_state(before, self.h.state(target), changes, audits, auth)
            page.screenshot(path=str(self.output / (case_id + '.png')), full_page=True)
            events = page.evaluate('window.verificationEvents || []') if not native else []
            if not native and semantic in ('already_applied', 'conflict', 'commit_unknown'):
                require(events == [semantic], 'outcome_event_missing_or_duplicate')
            if case_id == 'confirm_server':
                require(events == ['confirm_required'], 'confirm_event_missing')
            expected_posts = 0 if case_id in ('no_change', 'global_no_change') else 1
            if case_id == 'native_confirm':
                expected_posts = 2  # Unconfirmed native POST, then explicit confirmation.
            require(len(posts) == expected_posts, 'unexpected_or_automatic_post')
            traces = self.h.traces[trace_start:]
            require(len(traces) == expected_posts, 'http_observer_post_mismatch')
            if traces:
                trace = traces[-1]
                require(trace['relationship_dml'] == 0, 'relationship_dml_unexpected')
                require(trace['cache_invalidations'] == (1 if auth else 0), 'cache_side_effect_mismatch')
                if semantic in ('no_change', 'already_applied', 'conflict', 'confirm_required'):
                    require(trace['dml'] == 0 and trace['commits'] == 0, 'readonly_outcome_wrote')
                if mode:
                    require(trace['fault_hits'] == 1 and trace['service_calls'] == 1,
                            'fault_or_service_count_mismatch')
                if semantic == 'updated' or mode == 'commit_after':
                    require(trace['commits'] == 1, 'success_not_single_commit')
            # A second no-op click after a recoverable outcome proves the actual guard unlocks.
            # Unknown/conflict must first refresh to re-establish a trusted current baseline.
            button_reused = None
            if not native and semantic in ('already_applied', 'conflict', 'commit_unknown', 'failed'):
                page.reload()
                page.wait_for_load_state('networkidle')
                count = len(posts)
                page.locator(BUTTON).click()
                page.get_by_text('未检测到变更，无需保存', exact=True).wait_for(state='visible')
                require(len(posts) == count, 'recovered_noop_posted')
                ready(page)
                button_reused = True
            self.results.append({
                'case_id': case_id, 'semantic': semantic, 'role': role,
                'channel': 'native' if native else ('browser_fetch' if case_id in (
                    'csrf_denied', 'no_change_server') else 'actual_button'),
                'preflight_bypassed': case_id == 'confirm_server', 'posts': expected_posts,
                'response': ({key: data[key] for key in ('errcode', 'errmsg', 'url') if key in data}
                             if data else None),
                'actual_outcome': (data.get('data', {}).get('outcome')
                                   if data and isinstance(data.get('data'), dict) else None),
                'outcome_present': bool(data and isinstance(data.get('data'), dict)
                                        and 'outcome' in data['data']),
                'events': events, 'path': urlsplit(page.url).path, 'effects': effects,
                'traces': traces, 'button_reused_after_refresh': button_reused, 'passed': True,
            })
        finally:
            context.close()


def verify(output, executable=None):
    prepare_output(output)
    with Harness() as h, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=executable)
        runner = Runner(h, browser, output)
        try:
            for case_id in CASES:
                print('CASE_START: ' + case_id, flush=True)
                runner.run_case(case_id)
                print('CASE_PASS: ' + case_id, flush=True)
            verify_results(runner.results, CASES)
            require({row['semantic'] for row in runner.results} >= {
                'updated', 'no_change', 'confirm_required', 'already_applied',
                'conflict', 'failed', 'commit_unknown'}, 'seven_semantic_states_incomplete')
            result = {'status': 'passed', 'run_id': h.run_id, 'cases': runner.results,
                      'environment': {'database': 'sqlite:///:memory:', 'browser': browser.version,
                                      'csrf_bypass': False, 'production_code_modified': False}}
            (output / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
            print('RBAC_OUTCOMES: OK cases=%s isolated_memory=1 seven_states=1' % len(runner.results))
            return result
        except Exception as error:
            # Never stringify arbitrary browser/DB errors (they may contain credentials).
            (output / 'failure.json').write_text(json.dumps({
                'status': 'failed', 'case_id': runner.case_id,
                'error_type': type(error).__name__,
                'phase': error.args[0] if type(error) is AssertionError else 'browser_or_environment',
            }, ensure_ascii=False, indent=2))
            raise
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--executable-path')
    args = parser.parse_args()
    try:
        verify(args.output_dir, args.executable_path)
    except Exception as error:
        print('RBAC_OUTCOMES: FAILED type=' + type(error).__name__, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
