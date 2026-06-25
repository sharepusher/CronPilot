from urllib.parse import quote

from flask import redirect, render_template, request, session

from . import rbac
from .services import authenticate_user, write_audit_log


@rbac.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template(
            'rbac/login.html',
            next_url=request.args.get('next', '/cron_list'),
            msg=request.args.get('msg', ''),
        )
    result = authenticate_user(
        request.values.get('username', '').strip(),
        request.values.get('password', ''),
    )
    next_url = request.values.get('next', '/cron_list')
    if not result['ok']:
        return redirect(
            '/rbac/login?msg=%s&next=%s' % (quote(result['msg']), quote(next_url))
        )
    session['is_login'] = True
    session['username'] = result['username']
    session['role'] = result['role']
    if result.get('user_id') is not None:
        session['user_id'] = result['user_id']
    else:
        session.pop('user_id', None)
    write_audit_log(action='user:login', resource=result['username'])
    return redirect(next_url)


@rbac.route('/logout', methods=['GET', 'POST'])
def logout():
    if session.get('is_login'):
        write_audit_log(action='user:logout', resource=session.get('username', ''))
    session.clear()
    return redirect('/rbac/login')
