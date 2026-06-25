from functools import lru_cache

from configs import configs

from .policy import ROLE_PERMISSIONS


@lru_cache(maxsize=1)
def get_rbac_enabled():
    return configs().get('rbac_enable', '0') == '1'


def get_role_permission_set(role):
    return ROLE_PERMISSIONS.get(role, set())


def write_audit_log(**kwargs):
    pass

