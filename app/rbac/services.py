import json
import logging
import uuid

from flask import request, session
from sqlalchemy import func, select

from app import db

logger = logging.getLogger(__name__)
from configs import configs
from datas.model.rbac_audit_log import RbacAuditLog
from datas.model.rbac_registration_request_group import (
    RbacRegistrationRequestGroup,
)
from datas.model.rbac_user import RbacUser
from datas.utils.times import datetime_to_hms, utc_now_hms

from .policy import (
    ROLE_PERMISSIONS,
    SEED_ADMIN_USERNAME,
    effective_permissions,
    has_permission,
    is_seed_admin_username,
    user_bypasses_scope,
    user_scope_assignment_denial,
)
from .registration_requested_scope import normalize_registration_requested_scope

VALID_ROLES = frozenset(ROLE_PERMISSIONS.keys())
# 用于表单下拉的角色排序（高频→低频）
ROLE_ORDER = ['operator', 'viewer', 'admin']

# 审计列表展示（码 → 中文）；未知码原样回退
DEFAULT_USER_PASSWORD = 'changeme'

AUDIT_ACTION_LABELS = {
    'user:login': '登录',
    'user:logout': '登出',
    'user:create': '创建用户',
    'user:update': '更新用户',
    'user:password': '修改密码',
    'user:password_reset': '触发密码重置',
    'user:disable': '停用用户',
    'user:enable': '启用用户',  # 保留：用于展示历史审计记录（"停用不可恢复"策略后不再产生新记录）
    'user:reactivate': '同名覆盖启用',
    'permission:deny': '权限拒绝',
    'scope:deny': '作用域拒绝',
    'group:create': '创建业务组',
    'group:update': '更新业务组',
    'api:deny': 'API 鉴权失败',
    'user:register_apply': '注册申请',
    'user:register_approve': '审批通过',
    'user:register_reject': '审批拒绝',
    'user:register_expire': '注册过期',
}
AUDIT_STATUS_LABELS = {
    'allow': '允许',
    'deny': '拒绝',
}


def audit_action_label(action):
    action = action or ''
    return AUDIT_ACTION_LABELS.get(action, action)


def audit_status_label(status):
    status = status or ''
    return AUDIT_STATUS_LABELS.get(status, status)


def audit_resource_label(action, resource):
    """资源列可读说明；任务配置变更不在本表。"""
    resource = resource or ''
    action = action or ''
    if action == 'user:login':
        return '账号 %s' % resource if resource else '账号'
    if action == 'user:logout':
        return '账号 %s' % resource if resource else '账号'
    if action == 'user:create':
        return '新建账号 %s' % resource if resource else '新建账号'
    if action == 'user:update':
        return '账号 %s（角色/启用停用/密码等）' % resource if resource else '账号变更'
    if action == 'user:password':
        return '账号 %s 修改密码' % resource if resource else '修改密码'
    if action == 'user:password_reset':
        return '账号 %s 触发密码重置' % resource if resource else '触发密码重置'
    if action == 'user:disable':
        return '停用账号 %s' % resource if resource else '停用账号'
    if action == 'user:enable':  # 保留：用于展示历史审计记录
        return '启用账号 %s' % resource if resource else '启用账号'
    if action == 'permission:deny':
        return '缺少权限 %s' % resource if resource else '权限不足'
    if action == 'scope:deny':
        return '无权访问 %s' % resource if resource else '作用域不足'
    if action == 'group:create':
        return '业务组 %s' % resource if resource else '新建业务组'
    if action == 'group:update':
        return '业务组 %s' % resource if resource else '业务组变更'
    if action == 'api:deny':
        return '接口 %s 鉴权失败' % resource if resource else 'API 鉴权失败'
    return resource


def get_role_permission_set(role, username=None):
    return set(effective_permissions(role, username))


def ensure_seed_admin():
    """rbac_users 为空且 conf 有 login_pwd 时，种子用户名 admin（密码=login_pwd）。

    种子账号仅用于建用户/组与只读查看；任务写/下线须由种子创建的其它 admin 角色用户完成。
    不再提供空用户名 → legacy_admin 登录；首次部署依赖此种子或管理端手动建用户。
    """
    from app.auth.password import is_hashed_password

    count = db.session.scalar(select(func.count()).select_from(RbacUser)) or 0
    if count > 0:
        return False
    login_pwd = configs().get('login_pwd', '')
    if not login_pwd:
        return False
    user = RbacUser(
        username=SEED_ADMIN_USERNAME,
        role='admin',
        is_active=1,
        create_time=utc_now_hms(),
    )
    if is_hashed_password(login_pwd):
        user.password_hash = login_pwd
    else:
        user.set_password(login_pwd)
    try:
        db.session.add(user)
        db.session.commit()
    except Exception:
        logger.exception('ensure_seed_admin commit failed')
        db.session.rollback()
        return False
    return True


def ensure_existing_users_have_token():
    """为存量用户补签 API Token（S6 上线前创建的用户 api_token 为空）。

    服务启动时由 ensure_business_tables 调用，幂等。
    """
    users = db.session.execute(
        select(RbacUser).where(
            RbacUser.is_active == 1,
            (RbacUser.api_token == '') | (RbacUser.api_token.is_(None)),
        )
    ).scalars().all()
    if not users:
        return
    for user in users:
        _auto_issue_token(user)
    try:
        db.session.commit()
        print('OK: 已为 %d 名存量用户补签 API Token' % len(users))
    except Exception:
        logger.exception('ensure_existing_users_have_token commit failed for %d users', len(users))
        db.session.rollback()


def authenticate_user(username, password):
    if not password:
        return {'ok': False, 'role': '', 'username': '', 'user_id': None, 'msg': '密码不能为空'}
    username = (username or '').strip()
    if not username:
        return {'ok': False, 'role': '', 'username': '', 'user_id': None, 'msg': '请填写用户名'}
    ensure_seed_admin()
    user = db.session.scalars(
        select(RbacUser).where(
            RbacUser.username == username,
            RbacUser.is_active == 1,
        )
    ).first()
    if user and user.check_password(password):
        return {
            'ok': True,
            'role': user.role,
            'username': user.username,
            'user_id': user.id,
            'auth_version': int(user.auth_version or 0),
            'must_reset_password': bool(getattr(user, 'must_reset_password', 0)),
            'msg': '',
        }
    return {
        'ok': False,
        'role': '',
        'username': '',
        'user_id': None,
        'auth_version': 0,
        'must_reset_password': False,
        'msg': '用户名或密码有误',
    }


def _actor_group_ids_csv():
    """当前 session 用户的 group_ids 转为逗号包围格式（如 ',1,3,'）。"""
    ids = session.get('group_ids') or []
    if not ids:
        return ''
    return ',' + ','.join(str(g) for g in ids) + ','


def web_session_user_is_valid():
    """实时校验 Web Session 对应账号仍存在、启用且认证版本一致。

    OPT-P0-22 §4.4：Session 缺少 auth_version 键时 fail-closed（不得用 or 0 放行旧会话）。
    """
    user_id = session.get('user_id')
    if user_id is None:
        return False
    user = db.session.get(RbacUser, user_id)
    if not user or not user.is_active:
        return False
    if user.username != (session.get('username') or ''):
        return False
    if 'auth_version' not in session:
        return False
    return int(session['auth_version']) == int(user.auth_version or 0)


def write_audit_log(
    action='', resource='', status='allow', user_id=None, username=None, ip=None, detail=None
):
    try:
        entry = RbacAuditLog(
            user_id=user_id if user_id is not None else session.get('user_id'),
            username=username if username is not None else session.get('username', ''),
            action=action,
            resource=resource or '',
            ip=ip if ip is not None else (request.remote_addr or ''),
            status=status,
            create_time=utc_now_hms(),
            actor_group_ids=_actor_group_ids_csv(),
            detail=detail,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        logger.exception('write_audit_log commit failed action=%s resource=%s', action, resource)
        db.session.rollback()


def ensure_rbac_tables(app):
    with app.app_context():
        from datas.model.resource_group import ResourceGroup
        from datas.model.user_group import UserGroup

        RbacUser.__table__.create(db.engine, checkfirst=True)
        RbacAuditLog.__table__.create(db.engine, checkfirst=True)
        ResourceGroup.__table__.create(db.engine, checkfirst=True)
        UserGroup.__table__.create(db.engine, checkfirst=True)
        ensure_seed_admin()


def _normalize_username(username):
    return (username or '').strip()


def _validate_role(role):
    if role not in VALID_ROLES:
        return '角色无效，可选：viewer / operator / admin'
    return ''


def _count_active_admins(exclude_id=None):
    filters = [RbacUser.role == 'admin', RbacUser.is_active == 1]
    if exclude_id is not None:
        filters.append(RbacUser.id != exclude_id)
    return db.session.scalar(select(func.count()).select_from(RbacUser).where(*filters)) or 0


GROUP_ALL_MARKER = '__ALL__'


def role_requires_groups(role, username=None):
    """所有角色都须选择业务组；种子 admin 豁免。"""
    if is_seed_admin_username(username):
        return False
    return True


def validate_groups_for_role(role, group_ids, username=None):
    """成功返回 ''；失败返回错误文案。"""
    if not role_requires_groups(role, username):
        return ''
    str_ids = [str(g) for g in (group_ids or [])]
    has_all = GROUP_ALL_MARKER in str_ids
    real_ids = [g for g in (group_ids or []) if str(g) != GROUP_ALL_MARKER]
    if has_all and real_ids:
        return '「全部」与具体业务组不能同时选择'
    if has_all:
        return ''
    cleaned = []
    for g in real_ids:
        try:
            cleaned.append(int(g))
        except (TypeError, ValueError):
            return '业务组参数无效'
    if not cleaned:
        return '必须选择「全部」或至少一个业务组'
    return ''


SCOPE_ASSIGNMENT_ERROR_MESSAGES = {
    'actor_missing_or_inactive': '当前登录账号已失效，请重新登录',
    'actor_permission_denied': '您无权管理用户',
    'actor_global_assignment_denied': '您无权授予全局管理权限',
    'actor_group_assignment_denied': '不能分配您管理范围之外的业务组',
    'actor_target_management_denied': '该用户不在您的管理范围内',
    'target_role_global_forbidden': '仅 admin 角色可选择「全部（全局权限）」',
    'requested_groups_required': '必须选择「全部」或至少一个业务组',
    'scope_marker_mixed': '「全部」与具体业务组不能同时选择',
    'group_id_invalid': '业务组参数无效',
    'group_not_found': '存在无效业务组',
    'target_role_invalid': '角色无效，可选：viewer / operator / admin',
    'authorization_check_failed': '权限校验失败，请稍后重试',
}


def _scope_assignment_error(reason):
    return {
        'ok': False,
        'is_global': False,
        'group_ids': [],
        'reason': reason,
        'msg': SCOPE_ASSIGNMENT_ERROR_MESSAGES[reason],
    }


def _load_scope_assignment_actor(actor_user_id):
    """从数据库读取 actor 的当前授权事实；不读 Session。"""
    from .scope import get_user_group_ids

    actor = db.session.get(RbacUser, actor_user_id)
    if not actor or not actor.is_active:
        return None
    return {
        'role': actor.role,
        'username': actor.username,
        'group_ids': get_user_group_ids(actor.id),
    }


def resolve_user_management_actor(actor_user_id):
    """读取用户管理页面所需的数据库当前 actor Scope；不读 Session。"""
    try:
        actor = _load_scope_assignment_actor(actor_user_id)
    except Exception:
        logger.exception(
            'resolve_user_management_actor read failed actor_user_id=%s',
            actor_user_id,
        )
        return {
            'ok': False,
            'reason': 'authorization_check_failed',
            'actor_id': actor_user_id,
            'role': '',
            'username': '',
            'group_ids': [],
            'bypass': False,
        }
    if not actor:
        return {
            'ok': False,
            'reason': 'actor_missing_or_inactive',
            'actor_id': actor_user_id,
            'role': '',
            'username': '',
            'group_ids': [],
            'bypass': False,
        }
    bypass = user_bypasses_scope(
        actor['role'],
        username=actor['username'],
        group_ids=actor['group_ids'],
    )
    if not has_permission(
        actor['role'], 'user:manage', username=actor['username'],
    ):
        return {
            'ok': False,
            'reason': 'actor_permission_denied',
            'actor_id': actor_user_id,
            'role': actor['role'],
            'username': actor['username'],
            'group_ids': list(actor['group_ids']),
            'bypass': bypass,
        }
    return {
        'ok': True,
        'reason': 'allowed',
        'actor_id': actor_user_id,
        'role': actor['role'],
        'username': actor['username'],
        'group_ids': list(actor['group_ids']),
        'bypass': bypass,
    }


def validate_user_scope_assignment(
    actor_user_id,
    target_role,
    raw_group_ids,
    target_username=None,
    target_user_id=None,
):
    """只读校验 actor 是否可向 target 授予请求的用户 Scope。"""
    if _validate_role(target_role):
        return _scope_assignment_error('target_role_invalid')

    values = list(raw_group_ids or [])
    str_values = [str(value) for value in values]
    has_all = GROUP_ALL_MARKER in str_values
    concrete_values = [
        value for value in values if str(value) != GROUP_ALL_MARKER
    ]
    if has_all and concrete_values:
        return _scope_assignment_error('scope_marker_mixed')

    cleaned = []
    for value in concrete_values:
        try:
            cleaned.append(int(value))
        except (TypeError, ValueError):
            return _scope_assignment_error('group_id_invalid')
    cleaned = list(dict.fromkeys(cleaned))

    seed_target_empty_scope = (
        not has_all
        and not cleaned
        and target_role == 'admin'
        and is_seed_admin_username(target_username)
    )
    request_is_global = has_all or seed_target_empty_scope
    if not request_is_global and not cleaned:
        return _scope_assignment_error('requested_groups_required')

    try:
        if cleaned:
            from datas.model.resource_group import ResourceGroup

            found = db.session.scalars(
                select(ResourceGroup.id).where(ResourceGroup.id.in_(cleaned))
            ).all()
            if set(found) != set(cleaned):
                return _scope_assignment_error('group_not_found')
        actor = _load_scope_assignment_actor(actor_user_id)
    except Exception:
        logger.exception(
            'validate_user_scope_assignment read failed actor_user_id=%s',
            actor_user_id,
        )
        return _scope_assignment_error('authorization_check_failed')

    if not actor:
        return _scope_assignment_error('actor_missing_or_inactive')
    if (
        target_user_id is not None
        and not user_bypasses_scope(
            actor['role'],
            username=actor['username'],
            group_ids=actor['group_ids'],
        )
        and not user_in_management_scope(actor['group_ids'], target_user_id)
    ):
        return _scope_assignment_error('actor_target_management_denied')
    denial = user_scope_assignment_denial(
        actor['role'],
        actor['username'],
        actor['group_ids'],
        target_role,
        request_is_global,
        cleaned,
    )
    if denial:
        return _scope_assignment_error(denial)
    return {
        'ok': True,
        'is_global': request_is_global,
        'group_ids': cleaned,
        'reason': None,
        'msg': '',
    }


def user_must_reset_password(user_id):
    """实时查询用户是否仍须强制改密。"""
    if user_id is None:
        return False
    user = db.session.get(RbacUser, user_id)
    if not user or not user.is_active:
        return False
    return bool(getattr(user, 'must_reset_password', 0))


def user_needs_profile_completion(user_id):
    """实时查询用户是否缺失个人信息（email / nickname / job_title）。
    种子 admin 用户免检。"""
    if user_id is None:
        return False
    user = db.session.get(RbacUser, user_id)
    if not user or not user.is_active:
        return False
    if bool(getattr(user, 'must_reset_password', 0)):
        return False  # 密码重置优先，改密完成后再检查
    from .policy import is_seed_admin_username
    if is_seed_admin_username(user.username):
        return False
    return not all([
        getattr(user, 'email', None),
        getattr(user, 'nickname', None),
        getattr(user, 'job_title', None),
    ])


def save_profile_completion(user_id, email, nickname, job_title):
    """保存用户补全的个人信息。"""
    user = db.session.get(RbacUser, user_id)
    if not user or not user.is_active:
        return {'ok': False, 'msg': '用户不存在或已停用'}
    errors = []
    if not email or not email.strip():
        errors.append('邮箱')
    if not nickname or not nickname.strip():
        errors.append('花名')
    if not job_title or not job_title.strip():
        errors.append('岗位类型')
    if errors:
        return {'ok': False, 'msg': '请填写：' + '、'.join(errors)}
    user.email = email.strip()
    user.nickname = nickname.strip()
    user.job_title = job_title.strip()
    try:
        db.session.commit()
    except Exception:
        logger.exception('save_profile_completion commit failed user_id=%s', user.id)
        db.session.rollback()
        return {'ok': False, 'msg': '保存失败，请重试'}
    return {'ok': True, 'msg': '个人信息已补全'}


def update_own_profile(user_id, email, nickname, job_title):
    """当前登录用户自助修改花名、邮箱、岗位类型。"""
    user = db.session.get(RbacUser, user_id)
    if not user or not user.is_active:
        return {'ok': False, 'msg': '用户不存在或已停用'}
    errors = []
    email = (email or '').strip()
    nickname = (nickname or '').strip()
    job_title = (job_title or '').strip()
    if not email or '@' not in email:
        errors.append('邮箱格式不正确')
    if not nickname:
        errors.append('花名不能为空')
    elif len(nickname) > 64:
        errors.append('花名最长 64 字符')
    if not job_title:
        errors.append('请选择岗位类型')
    if job_title.startswith('other:'):
        custom = job_title[len('other:'):].strip()
        if not custom:
            errors.append('请填写自定义岗位名称')
        elif len(custom) > 20:
            errors.append('自定义岗位名称最长 20 字符')
        job_title = 'other:' + custom
    elif job_title and job_title not in VALID_JOB_TITLES:
        errors.append('岗位类型不合法')
    if errors:
        return {'ok': False, 'msg': '；'.join(errors)}
    user.email = email
    user.nickname = nickname
    user.job_title = job_title
    try:
        db.session.commit()
    except Exception:
        logger.exception('update_own_profile commit failed user_id=%s', user_id)
        db.session.rollback()
        return {'ok': False, 'msg': '保存失败，请重试'}
    return {'ok': True, 'msg': '个人资料已更新'}


def _auto_issue_token(user):
    """自动签发/重置 API Token（创建用户 / 改密码 / 改组时调用）。"""
    import secrets
    from datetime import datetime, timedelta

    user.api_token = secrets.token_urlsafe(32)
    user.api_token_expires_at = datetime_to_hms(datetime.now() + timedelta(days=API_TOKEN_TTL_DAYS))


def _replace_user_groups_in_session(user_id, group_ids):
    """在调用方事务中全量替换用户业务组；__ALL__ 表示无绑定行。"""
    from datas.model.user_group import UserGroup

    existing = db.session.scalars(
        select(UserGroup).where(UserGroup.user_id == user_id)
    ).all()
    for row in existing:
        db.session.delete(row)
    values = [str(g) for g in (group_ids or [])]
    if GROUP_ALL_MARKER in values:
        return
    for group_id in dict.fromkeys(int(g) for g in values):
        db.session.add(UserGroup(user_id=user_id, group_id=group_id))


def _normalize_group_ids_for_snapshot(group_ids):
    values = [str(g) for g in (group_ids or [])]
    if GROUP_ALL_MARKER in values:
        return []
    out = []
    for g in values:
        try:
            out.append(int(g))
        except (TypeError, ValueError):
            continue
    return sorted(dict.fromkeys(out))


def _user_profile_snapshot(user, group_ids):
    return {
        'role': user.role or '',
        'group_ids': sorted(int(g) for g in (group_ids or [])),
        'email': user.email or '',
        'nickname': user.nickname or '',
        'job_title': user.job_title or '',
        'is_active': int(user.is_active or 0),
    }


def _overwrite_disabled_user_inplace(
    user,
    *,
    role,
    email,
    nickname,
    job_title,
    group_ids,
    must_reset_password,
    status_reason,
    password_hash=None,
    password_plain=None,
):
    """覆盖启用已停用用户（调用方须已 FOR UPDATE；本函数不 commit）。

    返回审计快照 ``{'before': ..., 'after': ...}``。
    已启用用户抛出 ValueError。
    """
    if int(user.is_active or 0) == 1:
        raise ValueError('cannot overwrite active user')
    from .scope import get_user_group_ids

    before = _user_profile_snapshot(user, get_user_group_ids(user.id))
    user.role = role
    user.email = (email or '').strip() or None
    user.nickname = (nickname or '').strip() or None
    user.job_title = (job_title or '').strip() or None
    user.is_active = 1
    user.must_reset_password = int(must_reset_password)
    user.status_reason = status_reason
    user.auth_version = int(user.auth_version or 0) + 1
    if password_hash is not None:
        user.password_hash = password_hash
    elif password_plain is not None:
        user.set_password(password_plain)
    else:
        raise ValueError('password required for overwrite')
    _auto_issue_token(user)
    # 覆盖路径必须全量替换组，禁止 group_ids=None 时继承旧绑定
    _replace_user_groups_in_session(user.id, group_ids or [])
    after = _user_profile_snapshot(
        user, _normalize_group_ids_for_snapshot(group_ids or [])
    )
    return {'before': before, 'after': after}


def _write_reactivate_audit(
    username, user_id, source, before, after, request_id=None
):
    detail = {
        'user_id': user_id,
        'source': source,
        'before': before,
        'after': after,
    }
    if request_id is not None:
        detail['request_id'] = request_id
    write_audit_log(
        action='user:reactivate',
        resource=username,
        detail=json.dumps(detail, ensure_ascii=False, separators=(',', ':')),
    )


def create_user(
    username,
    role='viewer',
    email='',
    nickname='',
    job_title='',
    group_ids=None,
    confirm_reactivation=False,
):
    """创建用户；同名停用用户须确认后在原行上覆盖启用。"""
    username = _normalize_username(username)
    if not username:
        return {'ok': False, 'msg': '用户名不能为空'}
    if len(username) > 64:
        return {'ok': False, 'msg': '用户名最长 64 字符'}
    err = _validate_role(role)
    if err:
        return {'ok': False, 'msg': err}
    existing = db.session.scalars(
        select(RbacUser).where(RbacUser.username == username).with_for_update()
    ).first()
    if existing and existing.is_active:
        return {'ok': False, 'msg': '用户名已存在'}
    if existing and not confirm_reactivation:
        return {
            'ok': False,
            'msg': '该用户名属于已停用账号，确认后将覆盖更新原账号资料并重新启用',
            'confirm_reactivation': True,
            'user_id': existing.id,
        }
    if existing:
        try:
            snap = _overwrite_disabled_user_inplace(
                existing,
                role=role,
                email=email,
                nickname=nickname,
                job_title=job_title,
                group_ids=group_ids or [],
                must_reset_password=1,
                status_reason='管理员确认同名覆盖启用',
                password_plain=DEFAULT_USER_PASSWORD,
            )
            db.session.commit()
        except Exception:
            logger.exception('overwrite disabled user commit failed username=%s', username)
            db.session.rollback()
            return {'ok': False, 'msg': '覆盖启用失败'}
        _invalidate_api_scope_cache(existing.id)
        _write_reactivate_audit(
            username,
            existing.id,
            'admin_create',
            snap['before'],
            snap['after'],
        )
        return {
            'ok': True,
            'msg': '原账号资料已覆盖并重新启用',
            'user_id': existing.id,
            'reactivated': True,
        }
    user = RbacUser(
        username=username,
        role=role,
        is_active=1,
        must_reset_password=1,
        create_time=utc_now_hms(),
        email=(email or '').strip() or None,
        nickname=(nickname or '').strip() or None,
        job_title=(job_title or '').strip() or None,
    )
    user.set_password(DEFAULT_USER_PASSWORD)
    _auto_issue_token(user)
    try:
        db.session.add(user)
        db.session.flush()
        if group_ids is not None:
            _replace_user_groups_in_session(user.id, group_ids)
        db.session.commit()
    except Exception:
        logger.exception('create_user commit failed username=%s', username)
        db.session.rollback()
        return {'ok': False, 'msg': '创建失败'}
    write_audit_log(action='user:create', resource=username)
    return {'ok': True, 'msg': '创建成功', 'user_id': user.id, 'reactivated': False}


def update_user(user_id, role=None, is_active=None):
    """更新角色/启用状态；管理员不可在此设置密码。"""
    user = db.session.get(RbacUser, user_id)
    if not user:
        return {'ok': False, 'msg': '用户不存在'}
    # "停用不可恢复"策略：已停用用户不可通过任何路径恢复启用
    if is_active is not None and int(is_active) == 1 and user.is_active == 0:
        return {'ok': False, 'msg': '停用后不可恢复启用，如需使用请重新注册或由管理员创建'}
    session_uid = session.get('user_id')
    if is_active is not None and int(is_active) == 0 and session_uid == user.id:
        return {'ok': False, 'msg': '不能停用当前登录账号'}
    if is_active is not None and int(is_active) == 0 and is_seed_admin_username(user.username):
        return {'ok': False, 'msg': '系统管理员账号不可停用'}
    new_role = role if role is not None else user.role
    err = _validate_role(new_role)
    if err:
        return {'ok': False, 'msg': err}
    new_active = user.is_active if is_active is None else (1 if int(is_active) else 0)
    losing_admin = (
        user.role == 'admin'
        and user.is_active == 1
        and (new_role != 'admin' or new_active == 0)
    )
    if losing_admin and _count_active_admins(exclude_id=user.id) < 1:
        return {'ok': False, 'msg': '不能停用或降权最后一名启用中的管理员'}
    was_active = bool(user.is_active)
    user.role = new_role
    user.is_active = new_active
    if was_active and not new_active:
        user.auth_version = int(user.auth_version or 0) + 1
        user.api_token = None
        user.api_token_expires_at = None
    try:
        db.session.commit()
    except Exception:
        logger.exception('update_user commit failed user_id=%s', user_id)
        db.session.rollback()
        return {'ok': False, 'msg': '保存失败'}
    write_audit_log(action='user:update', resource=user.username)
    _invalidate_api_scope_cache(user_id)
    return {'ok': True, 'msg': '保存成功'}


def update_user_management(
    user_id,
    role,
    is_active,
    group_ids,
    email,
    nickname,
    job_title,
):
    """原子更新用户管理表单涉及的授权及资料字段。

    角色、业务组、资料和会话版本必须同一次提交，避免前两项成功后资料
    校验或提交失败而留下半完成授权状态。调用方已经完成 actor Scope 校验；
    此处仍独立校验目标字段和组存在性。
    """
    from datas.model.resource_group import ResourceGroup
    from datas.model.user_group import UserGroup

    try:
        new_active = 1 if int(is_active) else 0
    except (TypeError, ValueError):
        return {'ok': False, 'msg': '启用状态参数无效'}
    role_error = _validate_role(role)
    if role_error:
        return {'ok': False, 'msg': role_error}
    groups_error = validate_groups_for_role(role, group_ids)
    if groups_error:
        return {'ok': False, 'msg': groups_error}

    str_ids = [str(group_id) for group_id in (group_ids or [])]
    has_all = GROUP_ALL_MARKER in str_ids
    desired_group_ids = set()
    if not has_all:
        try:
            desired_group_ids = {
                int(group_id) for group_id in group_ids or []
                if str(group_id) != GROUP_ALL_MARKER
            }
        except (TypeError, ValueError):
            return {'ok': False, 'msg': '业务组参数无效'}

    try:
        user = db.session.scalar(
            select(RbacUser)
            .where(RbacUser.id == user_id)
            .with_for_update()
        )
        if not user:
            return {'ok': False, 'msg': '用户不存在'}
        if new_active == 1 and user.is_active == 0:
            return {'ok': False, 'msg': '停用后不可恢复启用，如需使用请重新注册或由管理员创建'}
        if new_active == 0 and is_seed_admin_username(user.username):
            return {'ok': False, 'msg': '系统管理员账号不可停用'}
        losing_admin = (
            user.role == 'admin'
            and user.is_active == 1
            and (role != 'admin' or new_active == 0)
        )
        if losing_admin and _count_active_admins(exclude_id=user.id) < 1:
            return {'ok': False, 'msg': '不能停用或降权最后一名启用中的管理员'}
        if desired_group_ids:
            found_group_ids = set(db.session.scalars(
                select(ResourceGroup.id).where(
                    ResourceGroup.id.in_(desired_group_ids)
                )
            ).all())
            if found_group_ids != desired_group_ids:
                return {'ok': False, 'msg': '存在无效业务组'}

        links = db.session.scalars(
            select(UserGroup)
            .where(UserGroup.user_id == user.id)
            .with_for_update()
        ).all()
        existing_group_ids = {link.group_id for link in links}
        role_changed = user.role != role
        groups_changed = existing_group_ids != desired_group_ids
        deactivated = bool(user.is_active) and not bool(new_active)

        user.role = role
        user.is_active = new_active
        user.email = (email or '').strip() or user.email
        user.nickname = (nickname or '').strip() or None
        user.job_title = (job_title or '').strip()
        for link in links:
            if link.group_id not in desired_group_ids:
                db.session.delete(link)
        for group_id in desired_group_ids - existing_group_ids:
            db.session.add(UserGroup(user_id=user.id, group_id=group_id))

        auth_changed = role_changed or groups_changed or deactivated
        if auth_changed:
            user.auth_version = int(user.auth_version or 0) + 1
            if deactivated:
                user.api_token = None
                user.api_token_expires_at = None
            else:
                _auto_issue_token(user)
        db.session.commit()
    except Exception:
        logger.exception('update_user_management commit failed user_id=%s', user_id)
        db.session.rollback()
        return {'ok': False, 'msg': '保存失败'}

    write_audit_log(action='user:update', resource=user.username)
    _invalidate_api_scope_cache(user.id)
    return {
        'ok': True,
        'msg': '保存成功',
        'auth_version_bumped': auth_changed,
    }


def validate_status_reason(reason):
    """停用/启用缘由：trim 后 1～500 字。成功返回 ('', reason)，失败返回 (msg, '')。"""
    text = (reason or '').strip()
    if not text:
        return '请填写缘由', ''
    if len(text) > 500:
        return '缘由最长 500 字', ''
    return '', text


def set_user_active(user_id, is_active, reason='', actor_user_id=None):
    """启用或停用用户。须填写缘由；不可停用自己；不可停用最后一名启用中的管理员。"""
    user = db.session.get(RbacUser, user_id)
    if not user:
        return {'ok': False, 'msg': '用户不存在'}
    err, reason = validate_status_reason(reason)
    if err:
        return {'ok': False, 'msg': err}
    actor_id = actor_user_id if actor_user_id is not None else session.get('user_id')
    want_active = 1 if int(is_active) else 0
    if want_active == 1:
        return {'ok': False, 'msg': '停用后不可恢复启用，如需使用请重新注册或由管理员创建'}
    if actor_id is not None and int(actor_id) == int(user.id):
        return {'ok': False, 'msg': '不能停用当前登录账号'}
    if want_active == 0 and is_seed_admin_username(user.username):
        return {'ok': False, 'msg': '系统管理员账号不可停用'}
    if (
        want_active == 0
        and user.role == 'admin'
        and user.is_active == 1
        and _count_active_admins(exclude_id=user.id) < 1
    ):
        return {'ok': False, 'msg': '不能停用最后一名启用中的管理员'}
    if int(user.is_active or 0) == want_active:
        return {
            'ok': True,
            'msg': '用户已是%s状态' % ('启用' if want_active else '停用'),
        }
    user.is_active = want_active
    user.status_reason = reason
    # 停用时立即清空 API Token（纵深防御 + 数据清洁）
    if want_active == 0:
        user.auth_version = int(user.auth_version or 0) + 1
        user.api_token = None
        user.api_token_expires_at = None
    try:
        db.session.commit()
    except Exception:
        logger.exception('set_user_active commit failed user_id=%s active=%s', user_id, want_active)
        db.session.rollback()
        return {'ok': False, 'msg': '保存失败'}
    action = 'user:enable' if want_active else 'user:disable'
    write_audit_log(
        action=action,
        resource='%s：%s' % (user.username, reason),
    )
    _invalidate_api_scope_cache(user_id)
    return {
        'ok': True,
        'msg': '已%s用户「%s」' % (('启用' if want_active else '停用'), user.username),
    }


def trigger_password_reset(user_id, actor_user_id=None):
    """管理员触发重置：恢复默认密码并标记强制改密。不可重置自己。不可重置已停用用户。"""
    user = db.session.get(RbacUser, user_id)
    if not user:
        return {'ok': False, 'msg': '用户不存在'}
    if not user.is_active:
        return {'ok': False, 'msg': '用户已停用，不可重置密码'}
    actor_id = actor_user_id if actor_user_id is not None else session.get('user_id')
    if actor_id is not None and int(actor_id) == int(user.id):
        return {'ok': False, 'msg': '不能重置当前登录账号密码，请使用「修改密码」'}
    user.set_password(DEFAULT_USER_PASSWORD)
    user.must_reset_password = 1
    _auto_issue_token(user)
    try:
        db.session.commit()
    except Exception:
        logger.exception('trigger_password_reset commit failed user_id=%s', user_id)
        db.session.rollback()
        return {'ok': False, 'msg': '触发重置失败'}
    write_audit_log(action='user:password_reset', resource=user.username)
    _invalidate_api_scope_cache(user_id)
    return {'ok': True, 'msg': '已触发密码重置，默认密码为 %s' % DEFAULT_USER_PASSWORD}


def change_own_password(user_id, old_password, new_password, confirm_password):
    """登录用户修改自己的密码。须校验旧密码；成功后清除强制改密标记并写审计。"""
    if user_id is None:
        return {'ok': False, 'msg': '未登录'}
    user = db.session.get(RbacUser, user_id)
    if not user or not user.is_active:
        return {'ok': False, 'msg': '用户不存在或已停用'}
    if not old_password:
        return {'ok': False, 'msg': '请填写当前密码'}
    if not user.check_password(old_password):
        return {'ok': False, 'msg': '当前密码不正确'}
    new_password = new_password or ''
    confirm_password = confirm_password or ''
    if not new_password:
        return {'ok': False, 'msg': '请填写新密码'}
    if len(new_password) < 6:
        return {'ok': False, 'msg': '新密码至少 6 位'}
    if new_password != confirm_password:
        return {'ok': False, 'msg': '两次输入的新密码不一致'}
    if old_password == new_password:
        return {'ok': False, 'msg': '新密码不能与当前密码相同'}
    user.set_password(new_password)
    user.must_reset_password = 0
    _auto_issue_token(user)
    try:
        db.session.commit()
    except Exception:
        logger.exception('change_own_password commit failed user_id=%s', user_id)
        db.session.rollback()
        return {'ok': False, 'msg': '保存失败'}
    _invalidate_api_scope_cache(user_id)
    write_audit_log(
        action='user:password',
        resource=user.username,
        user_id=user.id,
        username=user.username,
    )
    return {'ok': True, 'msg': '密码已修改'}


def get_user_by_id(user_id):
    return db.session.get(RbacUser, user_id)


def list_resource_groups():
    from datas.model.resource_group import ResourceGroup

    return db.session.scalars(
        select(ResourceGroup).order_by(ResourceGroup.id)
    ).all()


def get_resource_group(group_id):
    from datas.model.resource_group import ResourceGroup

    return db.session.get(ResourceGroup, group_id)


def create_resource_group(name, description=''):
    from datas.model.resource_group import ResourceGroup

    name = (name or '').strip()
    description = (description or '').strip()
    if not name:
        return {'ok': False, 'msg': '名称不能为空'}
    if len(name) > 64:
        return {'ok': False, 'msg': '名称最长 64 字符'}
    if len(description) > 255:
        return {'ok': False, 'msg': '描述最长 255 字符'}
    exists = db.session.scalars(
        select(ResourceGroup).where(ResourceGroup.name == name)
    ).first()
    if exists:
        return {'ok': False, 'msg': '名称已存在'}
    group = ResourceGroup(
        name=name,
        description=description,
        create_time=utc_now_hms(),
    )
    try:
        db.session.add(group)
        db.session.commit()
    except Exception:
        logger.exception('create_resource_group commit failed name=%s', name)
        db.session.rollback()
        return {'ok': False, 'msg': '创建失败'}
    write_audit_log(action='group:create', resource=name)
    return {'ok': True, 'msg': '创建成功', 'group_id': group.id}


def update_resource_group(group_id, name=None, description=None):
    from datas.model.resource_group import ResourceGroup

    group = db.session.get(ResourceGroup, group_id)
    if not group:
        return {'ok': False, 'msg': '业务组不存在'}
    if name is not None:
        name = (name or '').strip()
        if not name:
            return {'ok': False, 'msg': '名称不能为空'}
        if len(name) > 64:
            return {'ok': False, 'msg': '名称最长 64 字符'}
        group.name = name
    if description is not None:
        description = (description or '').strip()
        if len(description) > 255:
            return {'ok': False, 'msg': '描述最长 255 字符'}
        group.description = description
    try:
        db.session.commit()
    except Exception:
        logger.exception('update_resource_group commit failed group_id=%s', group_id)
        db.session.rollback()
        return {'ok': False, 'msg': '保存失败'}
    write_audit_log(action='group:update', resource=group.name)
    return {'ok': True, 'msg': '保存成功'}


def get_user_group_ids_for_user(user_id):
    from .scope import get_user_group_ids

    return get_user_group_ids(user_id)


API_TOKEN_TTL_DAYS = 30


def issue_user_api_token(user_id):
    """签发/重置用户 API Token（S6）。由 /api/auth/token 和 admin 重置按钮调用。

    返回 {'ok': bool, 'msg': str, 'token': str, 'expires_at': str}。
    """
    user = db.session.get(RbacUser, user_id)
    if not user:
        return {'ok': False, 'msg': '用户不存在', 'token': '', 'expires_at': ''}
    if not user.is_active:
        return {'ok': False, 'msg': '用户已停用', 'token': '', 'expires_at': ''}
    _auto_issue_token(user)
    try:
        db.session.commit()
    except Exception:
        logger.exception('issue_user_api_token commit failed user_id=%s', user_id)
        db.session.rollback()
        return {'ok': False, 'msg': '签发失败', 'token': '', 'expires_at': ''}
    _invalidate_api_scope_cache(user_id)
    write_audit_log(action='user:update', resource='%s:api_token:issue' % user.username)
    return {'ok': True, 'msg': 'Token 已重置', 'token': user.api_token, 'expires_at': user.api_token_expires_at}


def _invalidate_api_scope_cache(user_id):
    """事件驱动失效：用户角色/组/状态变更后清除该用户的 API scope 缓存。"""
    try:
        from app.api import invalidate_user_scope_cache
        invalidate_user_scope_cache(user_id)
    except Exception:
        logger.debug('_invalidate_api_scope_cache failed user_id=%s', user_id, exc_info=True)


def set_user_groups(user_id, group_ids, role=None, username=None):
    """替换用户业务组绑定。group_ids 为 int 列表（可含 __ALL__）。组变更后需重新登录生效。

    role: 校验用角色；默认取用户当前角色。
    username: 用于种子 admin 豁免校验。
    """
    from datas.model.resource_group import ResourceGroup
    from datas.model.user_group import UserGroup

    user = db.session.get(RbacUser, user_id)
    if not user:
        return {'ok': False, 'msg': '用户不存在'}
    check_role = role if role is not None else user.role
    check_username = username if username is not None else user.username
    err = validate_groups_for_role(check_role, group_ids, username=check_username)
    if err:
        return {'ok': False, 'msg': err}
    str_ids = [str(g) for g in (group_ids or [])]
    has_all = GROUP_ALL_MARKER in str_ids
    cleaned = []
    if not has_all:
        for g in group_ids or []:
            if str(g) == GROUP_ALL_MARKER:
                continue
            try:
                cleaned.append(int(g))
            except (TypeError, ValueError):
                return {'ok': False, 'msg': '业务组参数无效'}
    cleaned = list(dict.fromkeys(cleaned))
    if cleaned:
        found = db.session.scalars(
            select(ResourceGroup.id).where(ResourceGroup.id.in_(cleaned))
        ).all()
        if set(found) != set(cleaned):
            return {'ok': False, 'msg': '存在无效业务组'}
    try:
        existing = db.session.scalars(
            select(UserGroup).where(UserGroup.user_id == user_id)
        ).all()
        existing_group_ids = {row.group_id for row in existing}
        desired_group_ids = set(cleaned)
        for row in existing:
            if row.group_id not in desired_group_ids:
                db.session.delete(row)
        for gid in desired_group_ids - existing_group_ids:
            db.session.add(UserGroup(user_id=user_id, group_id=gid))
        if desired_group_ids != existing_group_ids:
            _auto_issue_token(user)
        db.session.commit()
    except Exception:
        logger.exception('set_user_groups commit failed user_id=%s', user_id)
        db.session.rollback()
        return {'ok': False, 'msg': '保存业务组失败'}
    write_audit_log(action='user:update', resource='%s:groups' % user.username)
    _invalidate_api_scope_cache(user_id)
    return {'ok': True, 'msg': '保存成功'}


def user_in_management_scope(actor_group_ids, target_user_id):
    """按组管理员是否可管理目标用户——判组交集。

    actor_group_ids: 当前登录 admin 的业务组 id 列表。
    target_user_id: 被操作的用户 id。
    返回 True 表示在 Scope 内（可管理）。
    """
    from .scope import get_user_group_ids

    target_gids = set(get_user_group_ids(target_user_id))
    actor_gids = set(int(g) for g in (actor_group_ids or []))
    return bool(actor_gids & target_gids)


# ---------------------------------------------------------------------------
# 用户注册审批（OPT-P1-10）
# ---------------------------------------------------------------------------

REGISTRATION_ROLES = ['operator', 'viewer', 'admin']
REGISTRATION_EXPIRE_DAYS = 30

# 岗位类型枚举（注册时下拉选择）
JOB_TITLE_CHOICES = [
    ('tech', '技术'),
    ('ops', '运维'),
    ('qa', '测试'),
    ('pm', '产品'),
    ('proj_mgr', '项目经理'),
    ('strategy', '策略'),
    ('operation', '运营'),
    ('other', '其他'),
]
VALID_JOB_TITLES = frozenset(k for k, _ in JOB_TITLE_CHOICES)
JOB_TITLE_OTHER_MAX_LEN = 20

REGISTRATION_SCOPE_ERROR_MESSAGES = {
    'groups_required': '请至少选择一个业务组',
    'empty_group_token': '业务组参数无效',
    'invalid_group_id': '业务组参数无效',
    'group_not_found': '选择的业务组不存在，请刷新后重试',
    'global_requires_admin': '非管理员角色不可选择全局权限',
    'global_and_specific_groups_mixed': '「全部」与具体业务组不能同时选择',
}


def _extract_username_from_email(email):
    """从邮箱地址提取 @ 前部分作为用户名。"""
    if not email or '@' not in email:
        return ''
    return email.split('@')[0].strip()


def submit_registration(email, password, confirm_password, role, group_ids, reason,
                        job_title='', nickname=''):
    """提交注册申请。返回 {'ok': bool, 'msg': str}。"""
    # 懒过期：每次提交申请时顺带清理超期 pending 记录
    expire_stale_registrations()
    email = (email or '').strip().lower()
    if not email or '@' not in email:
        return {'ok': False, 'msg': '请输入有效的邮箱地址'}
    username = _extract_username_from_email(email)
    if not username:
        return {'ok': False, 'msg': '无法从邮箱提取用户名'}
    if len(username) > 64:
        return {'ok': False, 'msg': '用户名（邮箱前缀）最长 64 字符'}
    if role not in REGISTRATION_ROLES:
        return {'ok': False, 'msg': '角色无效，可选：operator / viewer / admin'}
    password = password or ''
    confirm_password = confirm_password or ''
    if len(password) < 6:
        return {'ok': False, 'msg': '密码至少 6 位'}
    if password != confirm_password:
        return {'ok': False, 'msg': '两次密码不一致'}
    # 岗位类型校验
    job_title = (job_title or '').strip()
    if not job_title:
        return {'ok': False, 'msg': '请选择岗位类型'}
    if job_title.startswith('other:'):
        custom_part = job_title[len('other:'):].strip()
        if not custom_part:
            return {'ok': False, 'msg': '选择"其他"时请填写具体岗位名称'}
        if len(custom_part) > JOB_TITLE_OTHER_MAX_LEN:
            return {'ok': False, 'msg': '自定义岗位名称最长 %d 字符' % JOB_TITLE_OTHER_MAX_LEN}
        job_title = 'other:' + custom_part
    elif job_title not in VALID_JOB_TITLES:
        return {'ok': False, 'msg': '岗位类型无效'}
    # 花名校验
    nickname = (nickname or '').strip()
    if not nickname:
        return {'ok': False, 'msg': '请填写花名'}
    if len(nickname) > 64:
        return {'ok': False, 'msg': '花名最长 64 字符'}
    reason = (reason or '').strip()
    if not reason:
        return {'ok': False, 'msg': '请填写申请缘由'}
    if len(reason) > 500:
        return {'ok': False, 'msg': '申请缘由最长 500 字'}
    # R2-2C：同一个规范化结果驱动父表 CSV 与关联行，避免双重解释。
    from datas.model.resource_group import ResourceGroup
    try:
        valid_group_ids = set(db.session.scalars(
            select(ResourceGroup.id)
        ).all())
    except Exception:
        logger.exception('submit_registration group lookup failed')
        db.session.rollback()
        return {'ok': False, 'msg': '提交失败，请稍后重试'}
    requested_scope = normalize_registration_requested_scope(
        role,
        group_ids,
        valid_group_ids,
    )
    if not requested_scope['ok']:
        return {
            'ok': False,
            'msg': REGISTRATION_SCOPE_ERROR_MESSAGES.get(
                requested_scope['reason'],
                '业务组参数无效',
            ),
        }
    normalized_group_ids = requested_scope['group_ids']
    gids_str = (
        GROUP_ALL_MARKER
        if requested_scope['kind'] == 'global'
        else ','.join(str(group_id) for group_id in normalized_group_ids)
    )

    # 检查用户名是否已存在于 rbac_users（仅检查启用中的用户；停用用户可重新注册）
    exists = db.session.scalars(
        select(RbacUser).where(
            RbacUser.username == username,
            RbacUser.is_active == 1,
        )
    ).first()
    if exists:
        return {'ok': False, 'msg': '用户名"%s"已存在' % username}

    disabled = db.session.scalars(
        select(RbacUser).where(
            RbacUser.username == username,
            RbacUser.is_active == 0,
        )
    ).first()

    # 检查是否有同 username 的 pending 申请
    from datas.model.rbac_registration_request import RbacRegistrationRequest
    pending = db.session.scalars(
        select(RbacRegistrationRequest).where(
            RbacRegistrationRequest.username == username,
            RbacRegistrationRequest.status == 'pending',
        )
    ).first()
    if pending:
        return {'ok': False, 'msg': '该用户名已有待审批的申请，请等待审批结果'}

    req = RbacRegistrationRequest(
        email=email,
        username=username,
        role=role,
        group_ids=gids_str,
        job_title=job_title,
        nickname=nickname,
        reason=reason,
        status='pending',
        pending_username=username,
        create_time=utc_now_hms(),
        is_reactivation=1 if disabled else 0,
        target_user_id=disabled.id if disabled else None,
    )
    req.set_password(password)
    try:
        db.session.add(req)
        db.session.flush()
        for group_id in normalized_group_ids:
            db.session.add(RbacRegistrationRequestGroup(
                registration_request_id=req.id,
                group_id=group_id,
            ))
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        # 唯一索引冲突 = 并发竞态，另一条 pending 抢先入库
        exc_str = str(exc).lower()
        if (
            'pending_username' in exc_str
            or 'uix_reg_pending_username' in exc_str
        ):
            return {'ok': False, 'msg': '该用户名已有待审批的申请，请等待审批结果'}
        logger.exception('submit_registration failed for email=%s', email)
        return {'ok': False, 'msg': '提交失败，请稍后重试'}
    write_audit_log(
        action='user:register_apply',
        resource=username,
        user_id=0,
        username='anonymous',
        ip=request.remote_addr if request else '',
    )
    return {'ok': True, 'msg': '注册申请已提交，审批通过后使用注册账号密码登录'}


def check_registration_status(username):
    """登录失败时查询注册申请状态。返回 None 或 dict。"""
    from datas.model.rbac_registration_request import RbacRegistrationRequest
    req = db.session.scalars(
        select(RbacRegistrationRequest).where(
            RbacRegistrationRequest.username == username,
            RbacRegistrationRequest.status.in_(['pending', 'rejected']),
        ).order_by(RbacRegistrationRequest.id.desc())
    ).first()
    if not req:
        return None
    return {
        'status': req.status,
        'review_comment': req.review_comment or '',
    }


def _validate_registration_storage_consistency(req):
    """批准前核对父表 Scope、关联集合与当前资源组，返回唯一可信集合。"""
    from datas.model.resource_group import ResourceGroup

    relation_group_ids = list(db.session.scalars(
        select(RbacRegistrationRequestGroup.group_id)
        .where(
            RbacRegistrationRequestGroup.registration_request_id == req.id,
        )
        .with_for_update()
    ).all())
    valid_group_ids = set(db.session.scalars(
        select(ResourceGroup.id)
    ).all())
    requested_scope = normalize_registration_requested_scope(
        req.role,
        req.group_ids,
        valid_group_ids,
    )
    if not requested_scope['ok']:
        logger.warning(
            'registration approval storage invalid request_id=%s reason=%s',
            req.id,
            requested_scope['reason'],
        )
        return {
            'ok': False,
            'msg': '申请业务组数据异常，请联系管理员处理',
        }

    actual = set(relation_group_ids)
    expected = set(requested_scope['group_ids'])
    if len(actual) != len(relation_group_ids) or actual != expected:
        logger.warning(
            'registration approval storage mismatch request_id=%s '
            'expected=%s actual=%s',
            req.id,
            sorted(expected),
            sorted(actual),
        )
        return {
            'ok': False,
            'msg': '申请业务组数据不一致，请联系管理员处理',
        }
    return {
        'ok': True,
        'requested_scope': requested_scope,
        'group_ids': (
            [GROUP_ALL_MARKER]
            if requested_scope['kind'] == 'global'
            else list(requested_scope['group_ids'])
        ),
    }


def _validate_registration_approval_scope(req, reviewer_id, requested_scope=None):
    """使用与新增/编辑相同的数据库当前事实校验注册审批授予范围。"""
    if requested_scope is None:
        raw_group_ids = (
            [GROUP_ALL_MARKER]
            if req.group_ids.strip() == GROUP_ALL_MARKER
            else [value.strip() for value in req.group_ids.split(',') if value.strip()]
        )
    else:
        raw_group_ids = (
            [GROUP_ALL_MARKER]
            if requested_scope['kind'] == 'global'
            else list(requested_scope['group_ids'])
        )
    target_user_id = (
        req.target_user_id
        if int(getattr(req, 'is_reactivation', 0) or 0) == 1
        else None
    )
    return validate_user_scope_assignment(
        reviewer_id,
        req.role,
        raw_group_ids,
        target_username=req.username,
        target_user_id=target_user_id,
    )


def _registration_reject_denial(reason, msg='无权处理该申请'):
    """返回拒绝审批的受控失败结果，避免暴露申请的 Scope 细节。"""
    return {'ok': False, 'msg': msg, 'reason': reason}


def _audit_registration_reject_denial(request_id, actor_scope, reason):
    """记录拒绝审批的最小审计事实，不写入申请人或业务组等敏感上下文。"""
    write_audit_log(
        action='scope:deny',
        resource='registration_request:%s' % request_id,
        status='deny',
        user_id=actor_scope.get('actor_id'),
        username=actor_scope.get('username', ''),
        detail=json.dumps({'reason': reason}, ensure_ascii=False),
    )


def _authorize_registration_rejection(req, reviewer_id):
    """按数据库当前事实校验拒绝注册申请的权限与 Scope。

    审批通过会把目标 Scope 授予新用户；拒绝虽不授予权限，但同样能改变
    申请生命周期，不能成为 scoped admin 绕过注册审批队列可见性的入口。
    """
    actor_scope = resolve_user_management_actor(reviewer_id)
    if not actor_scope['ok']:
        if actor_scope['reason'] == 'authorization_check_failed':
            return _registration_reject_denial(
                actor_scope['reason'],
                msg='权限校验失败，请稍后重试',
            ), actor_scope
        return _registration_reject_denial(actor_scope['reason']), actor_scope

    try:
        storage_result = _validate_registration_storage_consistency(req)
    except Exception:
        trace_id = uuid.uuid4().hex
        logger.exception(
            'registration rejection consistency check failed '
            'trace_id=%s request_id=%s',
            trace_id,
            req.id,
        )
        db.session.rollback()
        return {
            'ok': False,
            'msg': '服务器内部错误，请稍后重试',
            'reason': 'storage_check_failed',
            'error_kind': 'internal',
            'trace_id': trace_id,
        }, actor_scope

    # 仅全局管理员可处理存储异常的遗留申请，避免该异常记录永久卡死。
    if actor_scope['bypass']:
        return {
            'ok': True,
            'storage_anomaly': not storage_result['ok'],
            'storage_reason': (
                storage_result.get('msg', '') if not storage_result['ok'] else ''
            ),
        }, actor_scope

    # Scoped actor 必须先能由父表、关联表和现存资源组还原可信 Scope。
    if not storage_result['ok']:
        return _registration_reject_denial('request_scope_unverifiable'), actor_scope

    requested_scope = storage_result['requested_scope']
    if requested_scope['kind'] != 'concrete':
        return _registration_reject_denial('global_scope_denied'), actor_scope

    requested_group_ids = set(requested_scope['group_ids'])
    actor_group_ids = set(actor_scope['group_ids'])
    if not requested_group_ids or not actor_group_ids:
        return _registration_reject_denial('no_scope_relation'), actor_scope

    if req.role in ('viewer', 'operator'):
        allowed = bool(requested_group_ids & actor_group_ids)
    elif req.role == 'admin':
        allowed = requested_group_ids.issubset(actor_group_ids)
    else:
        allowed = False
    if not allowed:
        return _registration_reject_denial('scope_denied'), actor_scope
    return {'ok': True, 'storage_anomaly': False, 'storage_reason': ''}, actor_scope


def approve_registration(request_id, reviewer_id=None):
    """审批通过注册申请。自动创建用户 + 绑定业务组 + 签发 Token。

    同名停用（OPT-P0-22）：在原 user 行上覆盖启用，保留 user_id。
    """
    from datas.model.rbac_registration_request import RbacRegistrationRequest

    req = db.session.scalars(
        select(RbacRegistrationRequest)
        .where(RbacRegistrationRequest.id == request_id)
        .with_for_update()
    ).first()
    if not req:
        return {'ok': False, 'msg': '申请不存在'}
    if req.status != 'pending':
        return {'ok': False, 'msg': '该申请已处理（%s）' % req.status}
    actor_user_id = reviewer_id or session.get('user_id')
    try:
        storage_result = _validate_registration_storage_consistency(req)
    except Exception:
        trace_id = uuid.uuid4().hex
        logger.exception(
            'registration approval consistency check failed '
            'trace_id=%s request_id=%s',
            trace_id,
            request_id,
        )
        db.session.rollback()
        return {
            'ok': False,
            'msg': '服务器内部错误，请稍后重试',
            'error_kind': 'internal',
            'trace_id': trace_id,
        }
    if not storage_result['ok']:
        return storage_result
    scope_result = _validate_registration_approval_scope(
        req,
        actor_user_id,
        requested_scope=storage_result['requested_scope'],
    )
    if not scope_result['ok']:
        return {'ok': False, 'msg': scope_result['msg']}

    def _reject_pending(msg, comment):
        req.status = 'rejected'
        req.pending_username = None
        req.review_comment = comment
        req.update_time = utc_now_hms()
        db.session.commit()
        return {'ok': False, 'msg': msg}

    target = None
    if int(getattr(req, 'is_reactivation', 0) or 0) == 1 and req.target_user_id:
        target = db.session.scalars(
            select(RbacUser)
            .where(RbacUser.id == req.target_user_id)
            .with_for_update()
        ).first()
        if not target or target.username != req.username:
            return _reject_pending(
                '同名停用目标用户已不存在或用户名不匹配，申请已自动拒绝',
                '同名停用目标无效',
            )
        if int(target.is_active or 0) == 1:
            return _reject_pending(
                '同名账号已启用，无法覆盖，申请已自动拒绝',
                '同名账号已启用，无法覆盖',
            )
    else:
        existing = db.session.scalars(
            select(RbacUser)
            .where(RbacUser.username == req.username)
            .with_for_update()
        ).first()
        if existing and existing.is_active:
            return _reject_pending(
                '用户名"%s"已被占用，申请已自动拒绝' % req.username,
                '用户名已被占用',
            )
        if existing and not existing.is_active:
            target = existing

    group_ids = storage_result['group_ids']
    reactivated = target is not None
    try:
        if target:
            snap = _overwrite_disabled_user_inplace(
                target,
                role=req.role,
                email=req.email,
                nickname=req.nickname or '',
                job_title=req.job_title or '',
                group_ids=group_ids,
                must_reset_password=0,
                status_reason='注册申请 #%s 同名覆盖启用：%s' % (req.id, req.reason),
                password_hash=req.password_hash,
            )
            user = target
        else:
            snap = None
            user = RbacUser(
                username=req.username,
                password_hash=req.password_hash,
                email=req.email,
                role=req.role,
                job_title=req.job_title or None,
                nickname=req.nickname or None,
                is_active=1,
                must_reset_password=0,
                create_time=utc_now_hms(),
            )
            _auto_issue_token(user)
            db.session.add(user)
            db.session.flush()
            _replace_user_groups_in_session(user.id, group_ids)
        req.status = 'approved'
        req.pending_username = None
        req.reviewer_id = actor_user_id
        req.update_time = utc_now_hms()
        db.session.commit()
    except Exception:
        trace_id = uuid.uuid4().hex
        logger.exception(
            'approve_registration failed trace_id=%s request_id=%s',
            trace_id,
            request_id,
        )
        db.session.rollback()
        return {
            'ok': False,
            'msg': '服务器内部错误，请稍后重试',
            'error_kind': 'internal',
            'trace_id': trace_id,
        }
    _invalidate_api_scope_cache(user.id)
    if reactivated and snap:
        _write_reactivate_audit(
            req.username,
            user.id,
            'registration_approve',
            snap['before'],
            snap['after'],
            request_id=req.id,
        )
    else:
        write_audit_log(action='user:register_approve', resource=req.username)
    return {
        'ok': True,
        'msg': (
            '已批准，原账号资料已覆盖并重新启用'
            if reactivated else '已批准，用户 %s 可正常登录' % req.username
        ),
        'user_id': user.id,
        'reactivated': reactivated,
    }


def reject_registration(request_id, reviewer_id, comment=''):
    """拒绝注册申请，并按数据库当前权限与业务组 Scope 授权。"""
    from datas.model.rbac_registration_request import RbacRegistrationRequest

    req = db.session.scalars(
        select(RbacRegistrationRequest)
        .where(RbacRegistrationRequest.id == request_id)
        .with_for_update()
    ).first()
    if not req:
        return {'ok': False, 'msg': '申请不存在'}
    if req.status != 'pending':
        return {'ok': False, 'msg': '该申请已处理（%s）' % req.status}
    authorization, actor_scope = _authorize_registration_rejection(
        req,
        reviewer_id,
    )
    if not authorization['ok']:
        _audit_registration_reject_denial(
            request_id,
            actor_scope,
            authorization['reason'],
        )
        return authorization
    req.status = 'rejected'
    req.pending_username = None
    req.reviewer_id = reviewer_id
    req.review_comment = (comment or '').strip()[:500]
    req.update_time = utc_now_hms()
    try:
        db.session.commit()
    except Exception:
        trace_id = uuid.uuid4().hex
        logger.exception(
            'reject_registration commit failed trace_id=%s request_id=%s',
            trace_id,
            request_id,
        )
        db.session.rollback()
        return {
            'ok': False,
            'msg': '服务器内部错误，请稍后重试',
            'error_kind': 'internal',
            'trace_id': trace_id,
        }
    write_audit_log(
        action='user:register_reject',
        resource=req.username,
        status='deny',
        user_id=actor_scope['actor_id'],
        username=actor_scope['username'],
        detail=json.dumps({
            'scope_resolution': (
                'global_anomaly_governance'
                if authorization['storage_anomaly'] else 'authorized'
            ),
        }, ensure_ascii=False),
    )
    return {'ok': True, 'msg': '已拒绝'}


def expire_stale_registrations():
    """将超过 REGISTRATION_EXPIRE_DAYS 天的 pending 申请标记为 expired。"""
    from datetime import datetime, timedelta

    from datas.model.rbac_registration_request import RbacRegistrationRequest

    cutoff_dt = datetime.now() - timedelta(days=REGISTRATION_EXPIRE_DAYS)
    cutoff_hms = datetime_to_hms(cutoff_dt)
    stale = db.session.scalars(
        select(RbacRegistrationRequest).where(
            RbacRegistrationRequest.status == 'pending',
            RbacRegistrationRequest.create_time < cutoff_hms,
        )
    ).all()
    expired_names = []
    for req in stale:
        req.status = 'expired'
        req.pending_username = None
        req.update_time = utc_now_hms()
        expired_names.append(req.username)
    if expired_names:
        try:
            db.session.commit()
        except Exception:
            logger.exception('expire_stale_registrations commit failed count=%d', len(expired_names))
            db.session.rollback()
            return
        for name in expired_names:
            write_audit_log(
                action='user:register_expire',
                resource=name,
                user_id=0,
                username='system',
            )
