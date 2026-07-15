from flask import Blueprint

rbac = Blueprint('rbac', __name__, url_prefix='/rbac')


@rbac.app_context_processor
def inject_rbac_context():
    from .context import (
        get_current_group_ids,
        get_current_user,
        get_current_user_groups,
        make_has_perm,
        role_badge_class,
        role_display_name,
    )
    return {
        'current_user': get_current_user(),
        'has_perm': make_has_perm(),
        'current_group_ids': get_current_group_ids(),
        'current_user_groups': get_current_user_groups(),
        'role_display_name': role_display_name,
        'role_badge_class': role_badge_class,
    }


from . import views  # noqa: E402,F401
