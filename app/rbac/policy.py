ROLE_PERMISSIONS = {
    'viewer': {'cron:read', 'log:read'},
    'operator': {'cron:read', 'cron:write', 'log:read', 'log:delete'},
    'admin': {
        'cron:read', 'cron:write', 'cron:delete',
        'log:read', 'log:delete', 'user:manage', 'audit:read',
    },
}


def has_permission(role, permission):
    return permission in ROLE_PERMISSIONS.get(role, set())
