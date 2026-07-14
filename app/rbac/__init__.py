from flask import Blueprint

rbac = Blueprint('rbac', __name__, url_prefix='/rbac')


@rbac.app_context_processor
def inject_rbac_context():
    from .context import get_current_group_ids, get_current_user, make_has_perm
    return {
        'current_user': get_current_user(),
        'has_perm': make_has_perm(),
        'current_group_ids': get_current_group_ids(),
    }


from . import views  # noqa: E402,F401
