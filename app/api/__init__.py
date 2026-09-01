#!/usr/bin/python3
# -*- coding:utf-8 -*-
import logging
import time

from apiflask import APIBlueprint
from flask import request

logger = logging.getLogger(__name__)

api = APIBlueprint('api', __name__, tag='CronPilot Open API')

# ---------------------------------------------------------------------------
# S6 用户级 Token Scope 缓存（进程内 + TTL 安全网 + 事件驱动失效）
# ---------------------------------------------------------------------------
_SCOPE_CACHE = {}   # api_token → {user_id, role, group_ids, is_active, username, ts}
_CACHE_TTL = 120    # 秒（多 worker 安全网）


def _get_cached_user_scope(token):
    entry = _SCOPE_CACHE.get(token)
    if entry and (time.time() - entry['ts']) < _CACHE_TTL:
        return entry
    return None


def _set_cached_user_scope(token, scope):
    """缓存完整 scope dict，确保形状与 fresh scope 一致。"""
    _SCOPE_CACHE[token] = dict(scope, ts=time.time())


def invalidate_user_scope_cache(user_id):
    """事件驱动：清除该 user_id 的所有缓存条目。"""
    to_remove = [k for k, v in _SCOPE_CACHE.items() if v.get('user_id') == user_id]
    for k in to_remove:
        del _SCOPE_CACHE[k]


# ---------------------------------------------------------------------------
# Token 提取与鉴权
# ---------------------------------------------------------------------------

def _extract_bearer_token():
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:].strip()
        if token:
            return token
    return request.values.get('access_token', '')


@api.before_request
def _api_token_guard():
    """统一鉴权 + S6 用户级 Scope 解析。

    优先级：
      1. /api/auth/token 端点 → 豁免（用户通过 Basic Auth 获取 Token）
      2. 全局 token（conf.ini api_access_token）→ admin scope
      3. 用户 token（rbac_users.api_token，含过期检查）→ 用户 scope
      4. 无匹配 → 401（api_access_token 为空时放行，向后兼容）
    """
    if request.endpoint == 'api.api_auth_token':
        return None

    try:
        from configs import configs as _configs
        api_access_token = _configs('api_access_token') or ''
    except Exception:
        logger.error('API token guard: failed to read config, denying request',
                     exc_info=True)
        from datas.utils.json import api_return
        return api_return(errcode=1, errmsg='服务配置异常，请联系管理员'), 500

    token = _extract_bearer_token()

    if not api_access_token and not token:
        request._api_scope = {'role': 'admin'}
        return None

    if token and api_access_token and token == api_access_token:
        request._api_scope = {'role': 'admin'}
        return None

    if token:
        user_scope = _resolve_user_token(token)
        if user_scope is not None:
            if not user_scope.get('is_active'):
                from datas.utils.json import api_return
                _write_api_deny_audit()
                return api_return(errcode=1, errmsg='用户已停用'), 401
            if user_scope.get('expired'):
                from datas.utils.json import api_return
                return api_return(errcode=1, errmsg='Token 已过期，请重新获取'), 401
            request._api_scope = user_scope
            return None

    if not api_access_token:
        request._api_scope = {'role': 'admin'}
        return None

    from datas.utils.json import api_return
    _write_api_deny_audit()
    return api_return(errcode=1, errmsg='access_token错误或缺失'), 401


def _resolve_user_token(token):
    """查 rbac_users.api_token，含缓存和过期检查。"""
    if not token:
        return None

    cached = _get_cached_user_scope(token)
    if cached is not None:
        return cached

    try:
        from sqlalchemy import select

        from app import db
        from app.rbac.scope import get_user_group_ids
        from datas.model.rbac_user import RbacUser

        user = db.session.scalars(
            select(RbacUser).where(RbacUser.api_token == token)
        ).first()
        if user is None:
            return None

        expired = False
        if user.api_token_expires_at:
            from datas.utils.times import utc_now_hms
            try:
                if utc_now_hms() > int(user.api_token_expires_at):
                    expired = True
            except (ValueError, TypeError):
                expired = True

        group_ids = get_user_group_ids(user.id)
        scope = {
            'role': 'user',
            'user_id': user.id,
            'user_role': user.role or '',
            'username': user.username or '',
            'group_ids': group_ids,
            'is_active': bool(user.is_active),
            'expired': expired,
        }
        _set_cached_user_scope(token, scope)
        return scope
    except Exception:
        logger.warning('user token resolution failed', exc_info=True)
        return None


def check_api_scope(cron_info):
    """检查当前请求的 API Scope 是否允许操作目标任务。

    成功返回 None；失败返回与「任务不存在」相同的错误响应（防枚举）。
    """
    from app.rbac.policy import user_bypasses_scope
    from app.rbac.scope import has_scope

    scope = getattr(request, '_api_scope', None) or {'role': 'admin'}
    if scope.get('role') == 'admin':
        return None
    user_role = scope.get('user_role', '')
    username = scope.get('username', '')
    group_ids = scope.get('group_ids', [])
    if user_bypasses_scope(user_role, username=username, group_ids=group_ids):
        return None
    if has_scope(user_role, group_ids, cron_info, username=username):
        return None
    from datas.utils.json import api_return
    return api_return(errcode=1, errmsg='任务不存在'), 200


def _write_api_deny_audit():
    """记录 API 鉴权失败（rbac_audit_logs.action='api:deny'）。"""
    try:
        from app.rbac.services import write_audit_log
        write_audit_log(action='api:deny', resource=request.path, status='deny')
    except Exception:
        logger.warning('api deny audit write failed', exc_info=True)


from . import views
