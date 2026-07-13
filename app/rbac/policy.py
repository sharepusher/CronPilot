ROLE_PERMISSIONS = {
    'viewer': {'cron:read', 'log:read'},
    'operator': {'cron:read', 'cron:write', 'log:read'},
    'admin': {
        'cron:read', 'cron:write', 'cron:retire',
        'log:read', 'user:manage', 'audit:read',
    },
}


def has_permission(role, permission):
    return permission in ROLE_PERMISSIONS.get(role, set())
