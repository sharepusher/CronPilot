from flask import Blueprint

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
    has_perm = make_has_perm()
    ctx = {
        'current_user': get_current_user(),
        'has_perm': has_perm,
        'current_group_ids': get_current_group_ids(),
        'current_user_groups': get_current_user_groups(),
        'role_display_name': role_display_name,
        'role_badge_class': role_badge_class,
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

        from .policy import is_seed_admin_username, user_bypasses_scope
        repo = RegistrationRequestRepository(db.session)
        bypasses = user_bypasses_scope(
            session.get('role') or '',
            username=session.get('username') or '',
            group_ids=session.get('group_ids') or [],
        )
        if bypasses:
            return repo.get_pending_count_all()
        return repo.get_pending_count_by_groups(session.get('group_ids') or [])
    except Exception:
        return 0


from . import views  # noqa: E402,F401
