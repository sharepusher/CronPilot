from functools import lru_cache

from flask import request, session
from sqlalchemy import select

from app import db
from configs import configs
from datas.model.rbac_audit_log import RbacAuditLog
from datas.model.rbac_user import RbacUser
from datas.utils.times import get_now_time
from app.auth.password import verify_login_password

from .policy import ROLE_PERMISSIONS


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
