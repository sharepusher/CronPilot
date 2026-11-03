"""Two owned HTTP instances sharing a private DB, with real browser actors."""
import threading
from contextlib import contextmanager
from unittest import mock

from flask import current_app
from sqlalchemy import event
from werkzeug.serving import make_server

from app import db
from app.rbac import services
from scripts.user_edit_browser_harness import QuietHandler, require
from scripts.user_edit_sqlite_fixture import FileFixture, make_app
from scripts.verify_user_edit_outcomes_browser import BUTTON, click_ajax, login, observe, ready


@contextmanager
def running_server(app, port=0):
    server = make_server('127.0.0.1', port, app, threaded=False, request_handler=QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:%s' % server.server_port
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        with app.app_context():
            db.session.remove()
            db.engine.dispose()


def browser_case(directory, mode, case, run_id, password, browser, output):
    from types import SimpleNamespace

    from flask import request
    path = directory / (mode + '_http_' + case + '.sqlite')
    fixture = FileFixture(path, run_id, mode, password)
    users = fixture.fixture('http_' + case)
    app_a = make_app(path, run_id)
    app_b = make_app(path, run_id)
    gate, release = threading.Event(), threading.Event()
    hits = []
    admitted = [False]
    protected = case.startswith('save_first')
    real_begin = services.begin_sqlite_write_boundary
    def gate_before(session, models):
        if current_app._get_current_object() is app_a and not hits:
            hits.append('before')
            gate.set()
            require(release.wait(10), 'http_before_gate_timeout')
        return real_begin(session, models)
    def gate_after(conn, _cursor, statement, _params, _ctx, _many):
        if statement == 'BEGIN IMMEDIATE':
            admitted[0] = True
        if request.method == 'POST' and admitted[0] and statement.lstrip().startswith(
                'SELECT rbac_users.') and not hits:
            require(conn.connection.driver_connection.in_transaction, 'http_read_not_protected')
            hits.append('protected')
            gate.set()
            require(release.wait(10), 'http_protected_gate_timeout')
    with app_a.app_context():
        engine_a = db.engine
    if protected:
        event.listen(engine_a, 'before_cursor_execute', gate_after)
    contexts = []
    try:
        with running_server(app_a) as url_a, running_server(app_b) as url_b:
            a_ctx, b_ctx = [browser.new_context(viewport={'width': 1440, 'height': 1000}) for _ in range(2)]
            contexts.extend((a_ctx, b_ctx))
            a, b = a_ctx.new_page(), b_ctx.new_page()
            for page in (a, b):
                page.set_default_timeout(12000)
            login(a, SimpleNamespace(url=url_a, password=password), users['actor'])
            login(b, SimpleNamespace(url=url_b, password=password), users['other'])
            a.goto(url_a + '/rbac/users/edit?id=' + str(users['target']['id']))
            revoke = case.endswith('role')
            b_target = users['actor'] if revoke else users['target']
            b.goto(url_b + '/rbac/users/edit?id=' + str(b_target['id']))
            for page in (a, b):
                observe(page)
            before_target = fixture.state(users['target'])
            before_actor = fixture.state(users['actor'])
            a.locator('#uf-nickname').fill('requested')
            if revoke:
                b.locator('#uf-role-select').select_option('viewer')
            else:
                b.locator('#uf-nickname').fill('concurrent')
            posts = []
            a.on('request', lambda r: posts.append(r) if r.method == 'POST' and '/users/edit' in r.url else None)
            patch = mock.patch.object(services, 'begin_sqlite_write_boundary', side_effect=gate_before)
            if protected:
                # Production function untouched; only the first protected read is paused.
                from contextlib import nullcontext
                patch = nullcontext()
            with patch:
                a.locator(BUTTON).click(no_wait_after=True)
                require(gate.wait(10), 'http_gate_not_reached')
                try:
                    b_data = click_ajax(b)
                    require(b_data['errcode'] == (1 if protected else 0), 'http_competitor_result_invalid')
                    if protected:
                        ready(b)
                        require(fixture.state(users['target']) == before_target, 'write_during_protection')
                        require(fixture.state(users['actor']) == before_actor, 'revoke_during_protection')
                finally:
                    release.set()
                a.wait_for_load_state('networkidle')
                if protected:
                    a.wait_for_url('**/rbac/users')
                else:
                    a.get_by_text('当前账号已无用户管理权限' if revoke else '该用户信息已变更',
                                  exact=False).first.wait_for(state='visible')
                    ready(a)
            require(len(a.verification_responses) == 1 and len(posts) == 1,
                    'http_submission_missing_or_repeated')
            a_data = a.verification_responses[0]
            after = fixture.state(users['target'])
            if protected:
                require(a_data['errcode'] == 0 and after['nickname'] == 'requested', 'http_save_first_failed')
                require(after['audit'] == before_target['audit'] + 1, 'http_audit_not_single')
                # Explicit fresh GET + manual second action, never automatic retry.
                b.reload()
                b.wait_for_load_state('networkidle')
                if revoke:
                    b.locator('#uf-role-select').select_option('viewer')
                else:
                    b.locator('#uf-nickname').fill('concurrent')
                # The navigation destroys old observers; install a fresh read-only observer.
                b.evaluate('''() => { jQuery.ajaxPrefilter(function(_o,_s,x) {
                    x.done(function(d) { console.debug('VERIFIER_RESPONSE:'+JSON.stringify({
                        errcode:d.errcode,errmsg:d.errmsg,url:d.url,data:d.data})); });
                }); }''')
                require(click_ajax(b)['errcode'] == 0, 'http_later_legal_write_failed')
            else:
                require(a_data['errcode'] == 1, 'http_stale_authorization_or_target_saved')
                require(after['nickname'] == ('original' if revoke else 'concurrent'), 'http_new_value_lost')
                require(after['audit'] == before_target['audit'] + (0 if revoke else 1),
                        'http_failed_request_created_success_audit')
            a.screenshot(path=str(output / (mode + '-' + case + '-actor.png')), full_page=True)
            b.screenshot(path=str(output / (mode + '-' + case + '-competitor.png')), full_page=True)
            return {'mode': mode, 'case_id': case, 'gate': hits[0], 'actor_posts': 1,
                    'actor_errcode': a_data['errcode'], 'competitor_errcode': b_data['errcode'],
                    'real_login_csrf_scope': True, 'two_http_instances': True, 'passed': True}
    finally:
        release.set()
        for context in contexts:
            context.close()
        if protected:
            event.remove(engine_a, 'before_cursor_execute', gate_after)
        fixture.close()
