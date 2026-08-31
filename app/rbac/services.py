import logging

from flask import request, session
from sqlalchemy import func, select

from app import db

logger = logging.getLogger(__name__)
from configs import configs
from datas.model.rbac_audit_log import RbacAuditLog
from datas.model.rbac_user import RbacUser
from datas.utils.times import datetime_to_hms, utc_now_hms

from .policy import ROLE_PERMISSIONS, SEED_ADMIN_USERNAME, effective_permissions, is_seed_admin_username

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
            'must_reset_password': bool(getattr(user, 'must_reset_password', 0)),
            'msg': '',
        }
    return {
        'ok': False,
        'role': '',
        'username': '',
        'user_id': None,
        'must_reset_password': False,
        'msg': '用户名或密码有误',
    }


def _actor_group_ids_csv():
    """当前 session 用户的 group_ids 转为逗号包围格式（如 ',1,3,'）。"""
    ids = session.get('group_ids') or []
    if not ids:
        return ''
    return ',' + ','.join(str(g) for g in ids) + ','


def write_audit_log(action='', resource='', status='allow', user_id=None, username=None, ip=None):
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


def create_user(username, role='viewer', email='', nickname='', job_title=''):
    """创建用户：默认密码 changeme，并标记首次登录须改密。自动签发 API Token。"""
    username = _normalize_username(username)
    if not username:
        return {'ok': False, 'msg': '用户名不能为空'}
    if len(username) > 64:
        return {'ok': False, 'msg': '用户名最长 64 字符'}
    err = _validate_role(role)
    if err:
        return {'ok': False, 'msg': err}
    exists = db.session.scalars(
        select(RbacUser).where(
            RbacUser.username == username,
            RbacUser.is_active == 1,
        )
    ).first()
    if exists:
        return {'ok': False, 'msg': '用户名已存在'}
    # 删除同名已停用旧记录（释放 UNIQUE 约束，与注册审批逻辑对齐）
    old_disabled = db.session.scalars(
        select(RbacUser).where(
            RbacUser.username == username,
            RbacUser.is_active == 0,
        )
    ).first()
    if old_disabled:
        db.session.delete(old_disabled)
        db.session.flush()
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
        db.session.commit()
    except Exception:
        logger.exception('create_user commit failed username=%s', username)
        db.session.rollback()
        return {'ok': False, 'msg': '创建失败'}
    write_audit_log(action='user:create', resource=username)
    return {'ok': True, 'msg': '创建成功', 'user_id': user.id}


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
    user.role = new_role
    user.is_active = new_active
    try:
        db.session.commit()
    except Exception:
        logger.exception('update_user commit failed user_id=%s', user_id)
        db.session.rollback()
        return {'ok': False, 'msg': '保存失败'}
    write_audit_log(action='user:update', resource=user.username)
    _invalidate_api_scope_cache(user_id)
    return {'ok': True, 'msg': '保存成功'}


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
    # 校验 group_ids（admin 可选 __ALL__）
    if not group_ids:
        return {'ok': False, 'msg': '请至少选择一个业务组'}
    str_ids = [str(g) for g in group_ids]
    has_all = GROUP_ALL_MARKER in str_ids
    if has_all and role != 'admin':
        return {'ok': False, 'msg': '非管理员角色不可选择全局权限'}
    if has_all:
        real_ids = [g for g in str_ids if g != GROUP_ALL_MARKER]
        if real_ids:
            return {'ok': False, 'msg': '「全部」与具体业务组不能同时选择'}
        gids_str = GROUP_ALL_MARKER
    else:
        cleaned_gids = []
        for g in group_ids:
            try:
                cleaned_gids.append(int(g))
            except (TypeError, ValueError):
                return {'ok': False, 'msg': '业务组参数无效'}
        if not cleaned_gids:
            return {'ok': False, 'msg': '请至少选择一个业务组'}
        gids_str = ','.join(str(g) for g in cleaned_gids)

    # 检查用户名是否已存在于 rbac_users（仅检查启用中的用户；停用用户可重新注册）
    exists = db.session.scalars(
        select(RbacUser).where(
            RbacUser.username == username,
            RbacUser.is_active == 1,
        )
    ).first()
    if exists:
        return {'ok': False, 'msg': '用户名"%s"已存在' % username}

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
    )
    req.set_password(password)
    try:
        db.session.add(req)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        # 唯一索引冲突 = 并发竞态，另一条 pending 抢先入库
        exc_str = str(exc).lower()
        if 'unique' in exc_str or 'duplicate' in exc_str:
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


def _check_admin_approval_scope(req):
    """校验当前审批者是否有权审批 admin 角色申请。

    规则：审批者的业务组范围 ≥ 申请者请求的业务组。
    种子 admin 和拥有全部业务组的 admin 可审批任何 admin 申请。
    返回错误信息字符串，无错返回 None。
    """
    from .policy import is_seed_admin_username, user_bypasses_scope
    actor_role = session.get('role') or ''
    actor_username = session.get('username') or ''
    actor_gids = session.get('group_ids') or []
    # 种子 admin 或全局管理员直接通过
    if user_bypasses_scope(actor_role, username=actor_username, group_ids=actor_gids):
        return None
    # 非 admin 角色不可审批 admin 申请
    if actor_role != 'admin':
        return '仅管理员可审批 admin 角色申请'
    # 申请全局权限（__ALL__）：仅种子/全局 admin 可审批（上方已放行），按组管理员无权
    if req.group_ids.strip() == GROUP_ALL_MARKER:
        return '全局权限申请仅系统管理员可审批'
    # 按组管理员：检查业务组是否覆盖
    req_gids = set(int(g) for g in req.group_ids.split(',') if g.strip())
    actor_gids_set = set(actor_gids)
    if not req_gids.issubset(actor_gids_set):
        uncovered = req_gids - actor_gids_set
        return '您的业务组范围不覆盖该申请的部分业务组（组 ID：%s）' % ', '.join(str(g) for g in uncovered)
    return None


def approve_registration(request_id, reviewer_id=None):
    """审批通过注册申请。自动创建用户 + 绑定业务组 + 签发 Token。"""
    from datas.model.rbac_registration_request import RbacRegistrationRequest
    from datas.model.user_group import UserGroup

    req = db.session.get(RbacRegistrationRequest, request_id)
    if not req:
        return {'ok': False, 'msg': '申请不存在'}
    if req.status != 'pending':
        return {'ok': False, 'msg': '该申请已处理（%s）' % req.status}
    # admin 角色申请：审批者的业务组须覆盖申请者请求的业务组
    if req.role == 'admin':
        scope_err = _check_admin_approval_scope(req)
        if scope_err:
            return {'ok': False, 'msg': scope_err}
    # 再次检查用户名冲突（仅启用用户）
    exists = db.session.scalars(
        select(RbacUser).where(
            RbacUser.username == req.username,
            RbacUser.is_active == 1,
        )
    ).first()
    if exists:
        req.status = 'rejected'
        req.pending_username = None
        req.review_comment = '用户名已被占用'
        req.update_time = utc_now_hms()
        db.session.commit()
        return {'ok': False, 'msg': '用户名"%s"已被占用，申请已自动拒绝' % req.username}
    # 删除同名的已停用旧记录（释放 UNIQUE 约束）
    old_disabled = db.session.scalars(
        select(RbacUser).where(
            RbacUser.username == req.username,
            RbacUser.is_active == 0,
        )
    ).first()
    if old_disabled:
        db.session.delete(old_disabled)
        db.session.flush()

    # 创建用户
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
    try:
        db.session.add(user)
        db.session.flush()
        # 绑定业务组（__ALL__ 不写 user_group 行，与 set_user_groups 一致）
        if req.group_ids.strip() != GROUP_ALL_MARKER:
            gids = [int(g) for g in req.group_ids.split(',') if g.strip()]
            for gid in gids:
                db.session.add(UserGroup(user_id=user.id, group_id=gid))
        # 更新申请状态
        req.status = 'approved'
        req.pending_username = None
        req.reviewer_id = reviewer_id or session.get('user_id')
        req.update_time = utc_now_hms()
        db.session.commit()
    except Exception:
        logger.exception('approve_registration failed for request_id=%s', request_id)
        db.session.rollback()
        return {'ok': False, 'msg': '审批失败'}
    write_audit_log(action='user:register_approve', resource=req.username)
    return {'ok': True, 'msg': '已批准，用户 %s 可正常登录' % req.username}


def reject_registration(request_id, comment=''):
    """拒绝注册申请。"""
    from datas.model.rbac_registration_request import RbacRegistrationRequest

    req = db.session.get(RbacRegistrationRequest, request_id)
    if not req:
        return {'ok': False, 'msg': '申请不存在'}
    if req.status != 'pending':
        return {'ok': False, 'msg': '该申请已处理（%s）' % req.status}
    req.status = 'rejected'
    req.pending_username = None
    req.reviewer_id = session.get('user_id')
    req.review_comment = (comment or '').strip()[:500]
    req.update_time = utc_now_hms()
    try:
        db.session.commit()
    except Exception:
        logger.exception('reject_registration commit failed request_id=%s', request_id)
        db.session.rollback()
        return {'ok': False, 'msg': '操作失败'}
    write_audit_log(
        action='user:register_reject',
        resource=req.username,
        status='deny',
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
