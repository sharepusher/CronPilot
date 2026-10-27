"""注册审批读取面的数据库当前 actor 上下文。"""

from flask import g, session

from .services import resolve_user_management_actor

_G_KEY = '_registration_review_actor_scope'


def current_registration_actor_scope():
    """每请求只解析一次 actor，供列表、标题计数与导航 badge 同源消费。"""
    cached = getattr(g, _G_KEY, None)
    if cached is None:
        cached = resolve_user_management_actor(session.get('user_id'))
        setattr(g, _G_KEY, cached)
    return cached
