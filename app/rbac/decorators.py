from functools import wraps

from flask import redirect, render_template, request, session

from datas.utils.json import json_response

from .authorize import AuthorizationError, authorize
from .policy import has_permission
from .services import write_audit_log


def require_permission(permission):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if 'is_login' not in session:
                next_url = request.full_path.rstrip('?')
                return redirect(f'/rbac/login?next={next_url}')
            role = session.get('role') or ''
            username = session.get('username') or ''
            if not has_permission(role, permission, username=username):
                write_audit_log(action='permission:deny', resource=permission, status='deny')
                return _forbidden_response(permission)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_login(func):
    """仅要求已登录（任意角色），用于改密等自助页。"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'is_login' not in session:
            next_url = request.full_path.rstrip('?')
            return redirect(f'/rbac/login?next={next_url}')
        return func(*args, **kwargs)
    return wrapper


def session_group_ids():
    gids = session.get('group_ids')
    if not isinstance(gids, list):
        return []
    out = []
    for g in gids:
        try:
            out.append(int(g))
        except (TypeError, ValueError):
            continue
    return out


def authorize_resource(permission, resource):
    """Permission + Scope；失败返回 Flask response，成功返回 None。"""
    try:
        authorize(
            session.get('role') or '',
            permission,
            resource,
            group_ids=session_group_ids(),
            username=session.get('username') or '',
        )
    except AuthorizationError as err:
        action = 'scope:deny' if err.kind == 'scope' else 'permission:deny'
        write_audit_log(
            action=action,
            resource=err.resource_label or permission,
            status='deny',
        )
        return _forbidden_response(err.message if err.kind == 'scope' else permission)
    return None


def _forbidden_response(permission):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        errmsg = permission
        if not errmsg.startswith('无权') and not errmsg.startswith('权限不足') and not errmsg.startswith('资源'):
            errmsg = '权限不足，需要 %s' % permission
        return json_response(
            errcode=1,
            errmsg=errmsg,
            status=403,
        )
    return render_template(
        'errors/error.html',
        icon='fa-lock',
        title='无权访问',
        description='您没有权限访问此页面，如需开通请联系管理员。',
        show_nav=False,
        home_url='/cron_list',
        home_text='返回任务中心',
    ), 403
