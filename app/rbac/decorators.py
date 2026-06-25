from functools import wraps

from flask import redirect, render_template, request, session

from datas.utils.json import json_response

from .policy import has_permission
from .services import get_rbac_enabled, write_audit_log


def require_permission(permission):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if 'is_login' not in session:
                next_url = request.full_path.rstrip('?')
                return redirect(f'/rbac/login?next={next_url}')
            if not get_rbac_enabled():
                return func(*args, **kwargs)
            role = session.get('role', 'admin')
            if not has_permission(role, permission):
                write_audit_log(action='permission:deny', resource=permission, status='deny')
                return _forbidden_response(permission)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def _forbidden_response(permission):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return json_response(
            errcode=1,
            errmsg='权限不足，需要 %s' % permission,
            status=403,
        )
    return render_template('rbac/forbidden.html', permission=permission), 403
