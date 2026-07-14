from flask import request, session
from sqlalchemy import func, select

from app import db
from configs import configs
from datas.model.rbac_audit_log import RbacAuditLog
from datas.model.rbac_user import RbacUser
from datas.utils.times import get_now_time

from .policy import ROLE_PERMISSIONS

VALID_ROLES = frozenset(ROLE_PERMISSIONS.keys())

# 空表种子：首个管理员固定用户名（Web 登录不再支持空用户名 / legacy_admin）
SEED_ADMIN_USERNAME = 'admin'

# 审计列表展示（码 → 中文）；未知码原样回退
AUDIT_ACTION_LABELS = {
    'user:login': '登录',
    'user:logout': '登出',
    'user:create': '创建用户',
    'user:update': '更新用户',
    'permission:deny': '权限拒绝',
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
        return '账号 %s（角色/启停/密码等）' % resource if resource else '账号变更'
    if action == 'permission:deny':
        return '缺少权限 %s' % resource if resource else '权限不足'
    return resource


def get_role_permission_set(role):
    return ROLE_PERMISSIONS.get(role, set())


def ensure_seed_admin():
    """rbac_users 为空且 conf 有 login_pwd 时，种子用户名 admin（密码=login_pwd）。

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
            'msg': '',
        }
    return {'ok': False, 'role': '', 'username': '', 'user_id': None, 'msg': '用户名或密码有误'}


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
        RbacUser.__table__.create(db.engine, checkfirst=True)
        RbacAuditLog.__table__.create(db.engine, checkfirst=True)
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


def create_user(username, password, role='viewer'):
    username = _normalize_username(username)
    if not username:
        return {'ok': False, 'msg': '用户名不能为空'}
    if len(username) > 64:
        return {'ok': False, 'msg': '用户名最长 64 字符'}
    if not password:
        return {'ok': False, 'msg': '密码不能为空'}
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
        create_time=get_now_time(),
    )
    user.set_password(password)
    try:
        db.session.add(user)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return {'ok': False, 'msg': '创建失败'}
    write_audit_log(action='user:create', resource=username)
    return {'ok': True, 'msg': '创建成功', 'user_id': user.id}


def update_user(user_id, role=None, is_active=None, password=None):
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
    if password:
        user.set_password(password)
    user.role = new_role
    user.is_active = new_active
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return {'ok': False, 'msg': '保存失败'}
    write_audit_log(action='user:update', resource=user.username)
    return {'ok': True, 'msg': '保存成功'}


def get_user_by_id(user_id):
    return db.session.get(RbacUser, user_id)
