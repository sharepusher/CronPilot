from urllib.parse import quote

from flask import redirect, render_template, request, session
from sqlalchemy import desc, select

from app import db
from app.common.functions import web_api_return
from app.services.pagination import PageQuery, paginate_select
from datas.model.rbac_audit_log import RbacAuditLog
from datas.model.rbac_user import RbacUser

from . import rbac
from .decorators import require_login, require_permission
from .services import (
    DEFAULT_USER_PASSWORD,
    VALID_ROLES,
    audit_action_label,
    audit_resource_label,
    audit_status_label,
    authenticate_user,
    change_own_password,
    create_resource_group,
    create_user,
    get_resource_group,
    get_user_by_id,
    get_user_group_ids_for_user,
    list_resource_groups,
    set_user_groups,
    trigger_password_reset,
    update_resource_group,
    update_user,
    user_must_reset_password,
    validate_groups_for_role,
    write_audit_log,
    set_user_active,
)


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


def _password_force_reset(user_id=None):
    return user_must_reset_password(
        user_id if user_id is not None else session.get('user_id')
    )


def _force_reset_allowed_path(path):
    if path.startswith('/static/'):
        return True
    if path in ('/rbac/password', '/rbac/logout', '/rbac/login'):
        return True
    return False


@rbac.before_app_request
def enforce_password_reset():
    """待重置用户访问受保护页时强制改密；实时读库，管理员触发后立即生效。"""
    if 'is_login' not in session:
        return None
    path = request.path or ''
    if _force_reset_allowed_path(path):
        return None
    if not _password_force_reset():
        return None
    reset_url = '/rbac/password'
    msg = '请先修改密码后再继续使用'
    if _wants_ajax_json():
        return web_api_return(code=1, msg=msg, url=reset_url)
    return redirect(reset_url)


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
        from .scope import get_user_group_ids
        session['group_ids'] = get_user_group_ids(result['user_id'])
    else:
        session.pop('user_id', None)
        session['group_ids'] = []
    write_audit_log(action='user:login', resource=result['username'])
    if result.get('must_reset_password'):
        return redirect('/rbac/password')
    return redirect(next_url)


@rbac.route('/logout', methods=['GET', 'POST'])
def logout():
    if session.get('is_login'):
        write_audit_log(action='user:logout', resource=session.get('username', ''))
    session.clear()
    return redirect('/rbac/login')


@rbac.route('/password', methods=['GET', 'POST'])
@require_login
def change_password():
    """任意已登录用户修改自己的密码；成功后清空会话并要求重新登录。"""
    force_reset = _password_force_reset()
    if request.method == 'GET':
        return render_template(
            'rbac/change_password.html',
            force_reset=force_reset,
        )
    result = change_own_password(
        session.get('user_id'),
        request.values.get('old_password', ''),
        request.values.get('new_password', ''),
        request.values.get('confirm_password', ''),
    )
    login_url = '/rbac/login?msg=%s' % quote('密码已修改，请重新登录')
    if result['ok']:
        session.clear()
    if _wants_ajax_json():
        return web_api_return(
            code=0 if result['ok'] else 1,
            msg=result['msg'] if not result['ok'] else '密码已修改，请重新登录',
            url=login_url if result['ok'] else '',
        )
    if result['ok']:
        return redirect(login_url)
    return render_template(
        'rbac/change_password.html',
        form_msg=result['msg'],
        force_reset=force_reset,
    )


@rbac.route('/users', methods=['GET'])
@require_permission('user:manage')
def users_list():
    page_query = PageQuery.from_args(request.args)
    page_data = paginate_select(
        db.session,
        select(RbacUser).order_by(desc(RbacUser.id)),
        page_query,
    )
    return render_template('rbac/users.html', page_data=page_data)


@rbac.route('/users/add', methods=['GET', 'POST'])
@require_permission('user:manage')
def users_add():
    groups = list_resource_groups()
    if request.method == 'GET':
        return render_template(
            'rbac/users_add.html',
            roles=sorted(VALID_ROLES),
            groups=groups,
            default_password=DEFAULT_USER_PASSWORD,
        )
    role = request.values.get('role', 'viewer')
    group_ids = request.values.getlist('group_ids')
    groups_err = validate_groups_for_role(role, group_ids)
    if groups_err:
        return _users_form_response(
            False,
            groups_err,
            template='rbac/users_add.html',
            groups=groups,
            default_password=DEFAULT_USER_PASSWORD,
        )
    if not groups and role != 'admin':
        return _users_form_response(
            False,
            '请先创建业务组，再添加非管理员用户',
            template='rbac/users_add.html',
            groups=groups,
            default_password=DEFAULT_USER_PASSWORD,
        )
    result = create_user(
        request.values.get('username', ''),
        role,
    )
    if result.get('ok') and result.get('user_id'):
        bound = set_user_groups(result['user_id'], group_ids, role=role)
        if not bound['ok']:
            orphan = get_user_by_id(result['user_id'])
            if orphan:
                try:
                    db.session.delete(orphan)
                    db.session.commit()
                except Exception:
                    db.session.rollback()
            return _users_form_response(
                False,
                bound['msg'],
                template='rbac/users_add.html',
                groups=groups,
                default_password=DEFAULT_USER_PASSWORD,
            )
    return _users_form_response(
        result['ok'],
        result['msg'],
        template='rbac/users_add.html',
        groups=groups,
        default_password=DEFAULT_USER_PASSWORD,
    )


@rbac.route('/users/edit', methods=['GET', 'POST'])
@require_permission('user:manage')
def users_edit():
    user_id = request.values.get('id')
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return _users_form_response(False, '参数错误', url='/rbac/users')
    user = get_user_by_id(user_id)
    if not user:
        return _users_form_response(False, '用户不存在', url='/rbac/users')
    session_uid = session.get('user_id')
    if session_uid is not None and int(session_uid) == int(user.id):
        msg = '不能在用户管理中编辑自己的账号；请使用「修改密码」调整密码'
        if _wants_ajax_json():
            return web_api_return(code=1, msg=msg, url='/rbac/password')
        return redirect('/rbac/password')
    groups = list_resource_groups()
    if request.method == 'GET':
        return render_template(
            'rbac/users_edit.html',
            user=user,
            roles=sorted(VALID_ROLES),
            groups=groups,
            user_group_ids=get_user_group_ids_for_user(user.id),
            default_password=DEFAULT_USER_PASSWORD,
        )
    new_role = request.values.get('role', user.role)
    group_ids = request.values.getlist('group_ids')
    groups_err = validate_groups_for_role(new_role, group_ids)
    if groups_err:
        return _users_form_response(
            False,
            groups_err,
            template='rbac/users_edit.html',
            user=user,
            groups=groups,
            user_group_ids=get_user_group_ids_for_user(user.id),
            default_password=DEFAULT_USER_PASSWORD,
        )
    result = update_user(
        user_id,
        role=new_role,
        is_active=request.values.get('is_active', user.is_active),
    )
    if result['ok']:
        bound = set_user_groups(user_id, group_ids, role=new_role)
        if not bound['ok']:
            result = bound
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
        groups=groups,
        user_group_ids=get_user_group_ids_for_user(user.id),
        default_password=DEFAULT_USER_PASSWORD,
    )


@rbac.route('/users/reset_password', methods=['GET', 'POST'])
@require_permission('user:manage')
def users_reset_password():
    user_id = request.values.get('id')
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return _users_form_response(False, '参数错误', url='/rbac/users')
    result = trigger_password_reset(user_id, actor_user_id=session.get('user_id'))
    return _users_form_response(
        result['ok'],
        result['msg'],
        url='/rbac/users',
    )


@rbac.route('/users/set_active', methods=['GET', 'POST'])
@require_permission('user:manage')
def users_set_active():
    user_id = request.values.get('id')
    try:
        user_id = int(user_id)
        is_active = int(request.values.get('is_active'))
    except (TypeError, ValueError):
        return _users_form_response(False, '参数错误', url='/rbac/users')
    user = get_user_by_id(user_id)
    if not user:
        return _users_form_response(False, '用户不存在', url='/rbac/users')
    if request.method == 'GET':
        return render_template(
            'rbac/users_set_active.html',
            user=user,
            target_active=is_active,
        )
    result = set_user_active(
        user_id,
        is_active,
        reason=request.values.get('reason', ''),
        actor_user_id=session.get('user_id'),
    )
    return _users_form_response(
        result['ok'],
        result['msg'],
        url='/rbac/users',
        template='rbac/users_set_active.html',
        user=user,
        target_active=is_active,
    )


@rbac.route('/groups', methods=['GET'])
@require_permission('user:manage')
def groups_list():
    return render_template(
        'rbac/groups.html',
        groups=list_resource_groups(),
    )


@rbac.route('/groups/add', methods=['GET', 'POST'])
@require_permission('user:manage')
def groups_add():
    if request.method == 'GET':
        return render_template('rbac/groups_add.html')
    result = create_resource_group(
        request.values.get('name', ''),
        None,
        request.values.get('description', ''),
    )
    return _users_form_response(
        result['ok'],
        result['msg'] if not result.get('ok') else (
            '%s（编码 %s）' % (result['msg'], result.get('code') or '')
        ),
        url='/rbac/groups',
        template='rbac/groups_add.html',
    )


@rbac.route('/groups/edit', methods=['GET', 'POST'])
@require_permission('user:manage')
def groups_edit():
    group_id = request.values.get('id')
    try:
        group_id = int(group_id)
    except (TypeError, ValueError):
        return _users_form_response(False, '参数错误', url='/rbac/groups')
    group = get_resource_group(group_id)
    if not group:
        return _users_form_response(False, '业务组不存在', url='/rbac/groups')
    if request.method == 'GET':
        return render_template('rbac/groups_edit.html', group=group)
    result = update_resource_group(
        group_id,
        name=request.values.get('name', group.name),
        description=request.values.get('description', group.description),
    )
    if not result['ok']:
        group.name = request.values.get('name', group.name)
        group.description = request.values.get('description', group.description)
    return _users_form_response(
        result['ok'],
        result['msg'],
        url='/rbac/groups',
        template='rbac/groups_edit.html',
        group=group,
    )


@rbac.route('/audit-logs', methods=['GET'])
@require_permission('audit:read')
def audit_logs():
    page_query = PageQuery.from_args(request.args)
    page_data = paginate_select(
        db.session,
        select(RbacAuditLog).order_by(desc(RbacAuditLog.id)),
        page_query,
    )
    return render_template(
        'rbac/audit_logs.html',
        page_data=page_data,
        audit_action_label=audit_action_label,
        audit_status_label=audit_status_label,
        audit_resource_label=audit_resource_label,
    )
