# -*- coding:utf-8 -*-
"""统一授权：Permission → Scope → Policy stub（OPT-P2-12）。"""
from .policy import check_policy, has_permission
from .scope import has_scope


class AuthorizationError(Exception):
    def __init__(self, kind, message, resource_label=''):
        self.kind = kind  # 'permission' | 'scope' | 'policy'
        self.message = message
        self.resource_label = resource_label or ''
        super(AuthorizationError, self).__init__(message)


def authorize(role, permission, resource, group_ids=None, username=None):
    """
    鉴权成功返回 None；失败抛 AuthorizationError。
    resource 为 None 时仅检查 Permission（无 Scope）。
    """
    role = role or ''
    if not has_permission(role, permission, username=username):
        raise AuthorizationError(
            'permission',
            '权限不足，需要 %s' % permission,
            permission,
        )
    if resource is not None and not has_scope(role, group_ids, resource):
        rid = getattr(resource, 'id', None)
        label = 'cron:%s' % rid if rid is not None else 'resource'
        raise AuthorizationError(
            'scope',
            '无权访问该资源（作用域不足）',
            label,
        )
    if not check_policy(role, permission, resource):
        raise AuthorizationError(
            'policy',
            '资源策略拒绝访问',
            getattr(resource, 'id', '') or '',
        )
    return None
