import logging

from flask import Blueprint

logger = logging.getLogger(__name__)

rbac = Blueprint('rbac', __name__, url_prefix='/rbac')


@rbac.app_context_processor
def inject_rbac_context():
    from app.security.csrf import inject_csrf_context

    from .context import (
        get_current_group_ids,
        get_current_user,
        get_current_user_groups,
        make_has_perm,
        role_badge_class,
        role_display_name,
    )
    from .policy import is_seed_admin_username
    has_perm = make_has_perm()
    ctx = {
        'current_user': get_current_user(),
        'has_perm': has_perm,
        'current_group_ids': get_current_group_ids(),
        'current_user_groups': get_current_user_groups(),
        'role_display_name': role_display_name,
        'role_badge_class': role_badge_class,
        'is_seed_admin_username': is_seed_admin_username,
        'pending_reg_count': _get_pending_reg_count() if has_perm('user:manage') else 0,
    }
    ctx.update(inject_csrf_context())
    return ctx


def _get_pending_reg_count():
    """获取待审批注册申请数量（用于导航 badge）。"""
    from flask import session
    if 'is_login' not in session:
        return 0
    try:
        from app import db
        from app.repositories.registration_request_repository import RegistrationRequestRepository

        from .registration_scope import current_registration_actor_scope
        repo = RegistrationRequestRepository(db.session)
        actor_scope = current_registration_actor_scope()
        if not actor_scope['ok']:
            return 0
        if actor_scope['bypass']:
            return repo.get_pending_count_all()
        return repo.get_pending_count_by_groups(actor_scope['group_ids'])
    except Exception:
        logger.warning('pending_registration_count: DB query failed', exc_info=True)
        return 0


from . import views  # noqa: E402,F401
