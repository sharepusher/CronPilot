from urllib.parse import quote

from flask import redirect, render_template, request, session
from sqlalchemy import desc

from app import db
from app.common.functions import web_api_return
from datas.model.rbac_user import RbacUser

from . import rbac
from .decorators import require_permission
from .services import (
    VALID_ROLES,
    authenticate_user,
    create_user,
    get_rbac_enabled,
    get_user_by_id,
    update_user,
    write_audit_log,
)


def _users_feature_or_redirect():
    """rbac_enable=0 时管理面不可用（装饰器会旁路权限，须额外闸门）。"""
    if not get_rbac_enabled():
        return redirect('/cron_list')
    return None


def _wants_ajax_json():
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return True
    accept = request.headers.get('Accept') or ''
    return 'application/json' in accept


def _users_form_response(ok, msg, url='/rbac/users', template=None, **ctx):
    """Ajax → JSON（含 url 跳转）；普通 POST → 成功重定向 / 失败回渲染表单。"""
    if _wants_ajax_json():
        return web_api_return(code=0 if ok else 1, msg=msg, url=url if ok else '')
    if ok:
        return redirect(url)
    if template:
        return render_template(template, form_msg=msg, roles=sorted(VALID_ROLES), **ctx)
    return redirect(url)


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


@rbac.route('/users', methods=['GET'])
@require_permission('user:manage')
def users_list():
    blocked = _users_feature_or_redirect()
    if blocked is not None:
        return blocked
    page = int(request.args.get('page') or 1)
    page_data = (
        db.session.query(RbacUser)
        .order_by(desc(RbacUser.id))
        .paginate(page=page, per_page=20)
    )
    return render_template('rbac/users.html', page_data=page_data)


@rbac.route('/users/add', methods=['GET', 'POST'])
@require_permission('user:manage')
def users_add():
    blocked = _users_feature_or_redirect()
    if blocked is not None:
        return blocked
    if request.method == 'GET':
        return render_template('rbac/users_add.html', roles=sorted(VALID_ROLES))
    result = create_user(
        request.values.get('username', ''),
        request.values.get('password', ''),
        request.values.get('role', 'viewer'),
    )
    return _users_form_response(
        result['ok'],
        result['msg'],
        template='rbac/users_add.html',
    )


@rbac.route('/users/edit', methods=['GET', 'POST'])
@require_permission('user:manage')
def users_edit():
    blocked = _users_feature_or_redirect()
    if blocked is not None:
        return blocked
    user_id = request.values.get('id')
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return _users_form_response(False, '参数错误', url='/rbac/users')
    user = get_user_by_id(user_id)
    if not user:
        return _users_form_response(False, '用户不存在', url='/rbac/users')
    if request.method == 'GET':
        return render_template(
            'rbac/users_edit.html',
            user=user,
            roles=sorted(VALID_ROLES),
        )
    password = request.values.get('password', '')
    result = update_user(
        user_id,
        role=request.values.get('role', user.role),
        is_active=request.values.get('is_active', user.is_active),
        password=password if password else None,
    )
    if not result['ok']:
        user.role = request.values.get('role', user.role)
        try:
            user.is_active = int(request.values.get('is_active', user.is_active))
        except (TypeError, ValueError):
            pass
    return _users_form_response(
        result['ok'],
        result['msg'],
        template='rbac/users_edit.html',
        user=user,
    )
