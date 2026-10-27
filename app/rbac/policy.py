ROLE_PERMISSIONS = {
    # viewer：只读任务与执行日志；不可见变更记录 / RBAC 用户与访问审计
    'viewer': {'cron:read', 'log:read'},
    # operator：可写任务 + 查看任务配置变更历史；不可下线、不可管用户、不可看访问审计
    'operator': {
        'cron:read', 'cron:write', 'log:read', 'operation:read',
    },
    # admin：全部 + 下线 + 用户管理 + 访问审计 + 变更记录
    'admin': {
        'cron:read', 'cron:write', 'cron:retire',
        'log:read', 'operation:read', 'user:manage', 'audit:read',
    },
}

# OPT-P2-12：admin 绕过 Resource Scope（不增第四角色）
SCOPE_BYPASS_ROLES = frozenset({'admin'})

# 空表种子账号固定用户名：仅建用户/组 + 只读全库，无任务写/下线
SEED_ADMIN_USERNAME = 'admin'
SEED_ADMIN_PERMISSIONS = frozenset({
    'cron:read', 'log:read', 'operation:read', 'user:manage', 'audit:read',
})

SCOPE_ASSIGN_DENY_PERMISSION = 'actor_permission_denied'
SCOPE_ASSIGN_DENY_GLOBAL = 'actor_global_assignment_denied'
SCOPE_ASSIGN_DENY_GROUP = 'actor_group_assignment_denied'
SCOPE_ASSIGN_DENY_TARGET_ROLE = 'target_role_global_forbidden'
SCOPE_ASSIGN_DENY_GROUPS_REQUIRED = 'requested_groups_required'


def is_seed_admin_username(username):
    return (username or '') == SEED_ADMIN_USERNAME


def effective_permissions(role, username=None):
    """角色权限；种子用户名 admin 裁剪为 SEED_ADMIN_PERMISSIONS。"""
    base = ROLE_PERMISSIONS.get(role or '', set())
    if is_seed_admin_username(username):
        return frozenset(base & SEED_ADMIN_PERMISSIONS)
    return frozenset(base)


def has_permission(role, permission, username=None):
    return permission in effective_permissions(role, username)


def role_bypasses_scope(role):
    """Deprecated: 不区分种子/管理员；请用 user_bypasses_scope。"""
    return (role or '') in SCOPE_BYPASS_ROLES


def user_bypasses_scope(role, username=None, group_ids=None):
    """种子 admin 永远全局；管理员 admin 需看 group_ids。"""
    if (role or '') not in SCOPE_BYPASS_ROLES:
        return False
    if is_seed_admin_username(username):
        return True
    return not group_ids


def user_scope_assignment_denial(
    actor_role,
    actor_username,
    actor_group_ids,
    target_role,
    request_is_global,
    requested_group_ids,
):
    """纯策略：返回 Scope 授予拒绝原因码；允许时返回 None。

    输入必须已由服务层规范化；本函数不读 Session/DB，不写日志。
    """
    if not has_permission(actor_role, 'user:manage', username=actor_username):
        return SCOPE_ASSIGN_DENY_PERMISSION

    actor_groups = frozenset(actor_group_ids or [])
    requested_groups = frozenset(requested_group_ids or [])
    actor_is_global = user_bypasses_scope(
        actor_role,
        username=actor_username,
        group_ids=actor_groups,
    )

    if request_is_global:
        if target_role != 'admin':
            return SCOPE_ASSIGN_DENY_TARGET_ROLE
        if not actor_is_global:
            return SCOPE_ASSIGN_DENY_GLOBAL
        return None

    if not requested_groups:
        return SCOPE_ASSIGN_DENY_GROUPS_REQUIRED
    if actor_is_global:
        return None
    if not requested_groups.issubset(actor_groups):
        return SCOPE_ASSIGN_DENY_GROUP
    return None


def check_policy(role, permission, resource):
    """Resource Policy 预留：当前恒 True。"""
    return True
