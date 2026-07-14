from flask import Blueprint

rbac = Blueprint('rbac', __name__, url_prefix='/rbac')


@rbac.app_context_processor
def inject_rbac_context():
    from .context import get_current_user, make_has_perm
    from .services import get_rbac_enabled
    return {
        'current_user': get_current_user(),
        'has_perm': make_has_perm(),
        'rbac_enabled': get_rbac_enabled(),
    }


from . import views  # noqa: E402,F401
