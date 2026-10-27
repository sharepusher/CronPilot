"""用户管理入口的数据库当前 actor 上下文。"""

from flask import g, session

from .services import resolve_user_management_actor

_G_KEY = '_user_management_actor_scope'


def current_user_management_actor_scope():
    """每个请求只读取一次当前 actor，禁止用户管理面回退 Session Scope。"""
    cached = getattr(g, _G_KEY, None)
    if cached is None:
        cached = resolve_user_management_actor(session.get('user_id'))
        setattr(g, _G_KEY, cached)
    return cached
