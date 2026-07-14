ROLE_PERMISSIONS = {
    # viewer：只读任务与执行日志；不可见操作记录 / RBAC 用户与审计
    'viewer': {'cron:read', 'log:read'},
    # operator：可写任务 + 查看任务配置变更历史；不可下线、不可管用户、不可看 RBAC 审计
    'operator': {
        'cron:read', 'cron:write', 'log:read', 'operation:read',
    },
    # admin：全部 + 下线 + 用户管理 + RBAC 审计 + 操作记录
    'admin': {
        'cron:read', 'cron:write', 'cron:retire',
        'log:read', 'operation:read', 'user:manage', 'audit:read',
    },
}

# OPT-P2-12：admin 绕过 Resource Scope（不增第四角色）
SCOPE_BYPASS_ROLES = frozenset({'admin'})


def has_permission(role, permission):
    return permission in ROLE_PERMISSIONS.get(role, set())


def role_bypasses_scope(role):
    return (role or '') in SCOPE_BYPASS_ROLES


def check_policy(role, permission, resource):
    """Resource Policy 预留：当前恒 True。"""
    return True
