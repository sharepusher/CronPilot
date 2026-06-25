from flask import Blueprint

rbac = Blueprint('rbac', __name__, url_prefix='/rbac')


@rbac.app_context_processor
def inject_rbac_context():
    from .context import make_has_perm
    return {'has_perm': make_has_perm()}
