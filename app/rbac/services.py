from flask import request, session
from sqlalchemy import func, select

from app import db
from configs import configs
from datas.model.rbac_audit_log import RbacAuditLog
from datas.model.rbac_user import RbacUser
from datas.utils.times import get_now_time

from .policy import ROLE_PERMISSIONS, SEED_ADMIN_USERNAME, effective_permissions

VALID_ROLES = frozenset(ROLE_PERMISSIONS.keys())

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
    'user:enable': '启用用户',
    'permission:deny': '权限拒绝',
    'scope:deny': '作用域拒绝',
    'group:create': '创建业务组',
    'group:update': '更新业务组',
    'api:deny': 'API 鉴权失败',
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
    if action == 'user:enable':
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
        create_time=get_now_time(),
    )
    if is_hashed_password(login_pwd):
        user.password_hash = login_pwd
    else:
        user.set_password(login_pwd)
    try:
        db.session.add(user)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return False
    return True


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


def write_audit_log(action='', resource='', status='allow', user_id=None, username=None, ip=None):
    try:
        entry = RbacAuditLog(
            user_id=user_id if user_id is not None else session.get('user_id'),
            username=username if username is not None else session.get('username', ''),
            action=action,
            resource=resource or '',
            ip=ip if ip is not None else (request.remote_addr or ''),
            status=status,
            create_time=get_now_time(),
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
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


def role_requires_groups(role):
    """非 admin 必须绑定至少一个业务组。"""
    return (role or '') != 'admin'


def validate_groups_for_role(role, group_ids):
    """成功返回 ''；失败返回错误文案。"""
    if not role_requires_groups(role):
        return ''
    cleaned = []
    for g in group_ids or []:
        try:
            cleaned.append(int(g))
        except (TypeError, ValueError):
            return '业务组参数无效'
    if not cleaned:
        return '非管理员用户必须至少选择一个业务组'
    return ''


def user_must_reset_password(user_id):
    """实时查询用户是否仍须强制改密。"""
    if user_id is None:
        return False
    user = db.session.get(RbacUser, user_id)
    if not user or not user.is_active:
        return False
    return bool(getattr(user, 'must_reset_password', 0))


def create_user(username, role='viewer'):
    """创建用户：默认密码 changeme，并标记首次登录须改密。"""
    username = _normalize_username(username)
    if not username:
        return {'ok': False, 'msg': '用户名不能为空'}
    if len(username) > 64:
        return {'ok': False, 'msg': '用户名最长 64 字符'}
    err = _validate_role(role)
    if err:
        return {'ok': False, 'msg': err}
    exists = db.session.scalars(
        select(RbacUser).where(RbacUser.username == username)
    ).first()
    if exists:
        return {'ok': False, 'msg': '用户名已存在'}
    user = RbacUser(
        username=username,
        role=role,
        is_active=1,
        must_reset_password=1,
        create_time=get_now_time(),
    )
    user.set_password(DEFAULT_USER_PASSWORD)
    try:
        db.session.add(user)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return {'ok': False, 'msg': '创建失败'}
    write_audit_log(action='user:create', resource=username)
    return {'ok': True, 'msg': '创建成功', 'user_id': user.id}


def update_user(user_id, role=None, is_active=None):
    """更新角色/启用状态；管理员不可在此设置密码。"""
    user = db.session.get(RbacUser, user_id)
    if not user:
        return {'ok': False, 'msg': '用户不存在'}
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
        db.session.rollback()
        return {'ok': False, 'msg': '保存失败'}
    write_audit_log(action='user:update', resource=user.username)
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
    if want_active == 0 and actor_id is not None and int(actor_id) == int(user.id):
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
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return {'ok': False, 'msg': '保存失败'}
    action = 'user:enable' if want_active else 'user:disable'
    write_audit_log(
        action=action,
        resource='%s：%s' % (user.username, reason),
    )
    return {
        'ok': True,
        'msg': '已%s用户「%s」' % (('启用' if want_active else '停用'), user.username),
    }


def trigger_password_reset(user_id, actor_user_id=None):
    """管理员触发重置：恢复默认密码并标记强制改密。不可重置自己。"""
    user = db.session.get(RbacUser, user_id)
    if not user:
        return {'ok': False, 'msg': '用户不存在'}
    actor_id = actor_user_id if actor_user_id is not None else session.get('user_id')
    if actor_id is not None and int(actor_id) == int(user.id):
        return {'ok': False, 'msg': '不能重置当前登录账号密码，请使用「修改密码」'}
    user.set_password(DEFAULT_USER_PASSWORD)
    user.must_reset_password = 1
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return {'ok': False, 'msg': '触发重置失败'}
    write_audit_log(action='user:password_reset', resource=user.username)
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
    try:
        db.session.commit()
    except Exception:
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


def create_resource_group(name, code=None, description=''):
    from datas.model.resource_group import ResourceGroup

    from .group_code import generate_group_code

    name = (name or '').strip()
    description = (description or '').strip()
    if not name:
        return {'ok': False, 'msg': '名称不能为空'}
    if len(name) > 64:
        return {'ok': False, 'msg': '名称最长 64 字符'}
    if len(description) > 255:
        return {'ok': False, 'msg': '描述最长 255 字符'}
    code = (code or '').strip()
    if not code:
        existing = db.session.scalars(select(ResourceGroup.code)).all()
        code = generate_group_code(name, existing_codes=existing)
    if not code:
        return {'ok': False, 'msg': '无法根据名称生成编码'}
    if len(code) > 64:
        return {'ok': False, 'msg': '编码最长 64 字符'}
    exists = db.session.scalars(
        select(ResourceGroup).where(ResourceGroup.code == code)
    ).first()
    if exists:
        return {'ok': False, 'msg': '编码已存在'}
    group = ResourceGroup(
        name=name,
        code=code,
        description=description,
        create_time=get_now_time(),
    )
    try:
        db.session.add(group)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return {'ok': False, 'msg': '创建失败'}
    write_audit_log(action='group:create', resource=code)
    return {'ok': True, 'msg': '创建成功', 'group_id': group.id, 'code': code}


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
        db.session.rollback()
        return {'ok': False, 'msg': '保存失败'}
    write_audit_log(action='group:update', resource=group.code)
    return {'ok': True, 'msg': '保存成功'}


def get_user_group_ids_for_user(user_id):
    from .scope import get_user_group_ids

    return get_user_group_ids(user_id)


def set_user_groups(user_id, group_ids, role=None):
    """替换用户业务组绑定。group_ids 为 int 列表。组变更后需重新登录生效。

    role: 校验用角色；默认取用户当前角色。非 admin 不得空组。
    """
    from datas.model.resource_group import ResourceGroup
    from datas.model.user_group import UserGroup

    user = db.session.get(RbacUser, user_id)
    if not user:
        return {'ok': False, 'msg': '用户不存在'}
    check_role = role if role is not None else user.role
    err = validate_groups_for_role(check_role, group_ids)
    if err:
        return {'ok': False, 'msg': err}
    cleaned = []
    for g in group_ids or []:
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
        db.session.commit()
    except Exception:
        db.session.rollback()
        return {'ok': False, 'msg': '保存业务组失败'}
    write_audit_log(action='user:update', resource='%s:groups' % user.username)
    return {'ok': True, 'msg': '保存成功'}
