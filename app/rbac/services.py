from functools import lru_cache

from flask import request, session
from sqlalchemy import func, select

from app import db
from configs import configs
from datas.model.rbac_audit_log import RbacAuditLog
from datas.model.rbac_user import RbacUser
from datas.utils.times import get_now_time
from app.auth.password import verify_login_password

from .policy import ROLE_PERMISSIONS

VALID_ROLES = frozenset(ROLE_PERMISSIONS.keys())


@lru_cache(maxsize=1)
def get_rbac_enabled():
    return configs().get('rbac_enable', '0') == '1'


def get_role_permission_set(role):
    return ROLE_PERMISSIONS.get(role, set())


def authenticate_user(username, password):
    if not password:
        return {'ok': False, 'role': '', 'username': '', 'user_id': None, 'msg': '密码不能为空'}
    if not username:
        login_pwd = configs().get('login_pwd', '')
        if not login_pwd:
            return {'ok': False, 'role': '', 'username': '', 'user_id': None, 'msg': '请联系管理员'}
        if verify_login_password(password, login_pwd):
            return {
                'ok': True,
                'role': 'admin',
                'username': 'legacy_admin',
                'user_id': None,
                'msg': '',
            }
        return {'ok': False, 'role': '', 'username': '', 'user_id': None, 'msg': '密码有误'}
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
    if not get_rbac_enabled():
        return
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
