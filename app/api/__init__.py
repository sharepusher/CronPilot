#!/usr/bin/python3 
# -*- coding:utf-8 -*-
from apiflask import APIBlueprint
from flask import request

api = APIBlueprint('api', __name__, tag='CronPilot Open API')


@api.before_request
def _api_token_guard():
    """统一 access_token 鉴权：替代各视图函数中的分散校验。
    语义：
      - conf.ini api_access_token 为空 → 放行所有请求（不做鉴权）。
      - 非空时：先读 Authorization: Bearer <token>，再回退到 query/form 参数 access_token。
      - 鉴权失败 → 返回 {errcode:1, errmsg:'access_token错误或缺失'}，HTTP 401。
    /api/swagger 与 /api/openapi.json 不经过此 Blueprint，天然豁免。
    """
    try:
        from configs import configs as _configs
        api_access_token = _configs('api_access_token') or ''
    except Exception:
        return None  # 配置读取异常时放行，不阻塞

    if not api_access_token:
        return None  # 未配置，放行所有

    # 优先读 Authorization: Bearer <token>
    auth_header = request.headers.get('Authorization', '')
    token = ''
    if auth_header.startswith('Bearer '):
        token = auth_header[7:].strip()

    # 回退：form / query 参数 access_token（向后兼容旧调用方）
    if not token:
        token = request.values.get('access_token', '')

    if token != api_access_token:
        from datas.utils.json import api_return
        _write_api_deny_audit()
        return api_return(errcode=1, errmsg='access_token错误或缺失'), 401

    return None  # 鉴权通过


def _write_api_deny_audit():
    """记录 API 鉴权失败（rbac_audit_logs.action='api:deny'），便于异常调用追溯。

    失败留痕是「API 层最小 Scope 止损」的一部分（见 doc/RBAC与群组权限管理评审报告.html）；
    不影响主流程——审计写入异常时静默忽略，不阻塞 401 响应。
    """
    try:
        from app.rbac.services import write_audit_log
        write_audit_log(action='api:deny', resource=request.path, status='deny')
    except Exception:
        pass


from . import views