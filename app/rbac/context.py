from flask import session

from .services import get_rbac_enabled, get_role_permission_set


def get_current_user():
    if 'is_login' not in session:
        return None
    return {
        'username': session.get('username', ''),
        'role': session.get('role', 'admin'),
        'user_id': session.get('user_id'),
    }


def make_has_perm():
    rbac_enabled = get_rbac_enabled()
    role = session.get('role', '')
    user_perms = get_role_permission_set(role) if rbac_enabled else None

    def _has_perm(permission):
        if not rbac_enabled:
            return True
        return permission in user_perms

    return _has_perm
