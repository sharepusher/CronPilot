# -*- coding:utf-8 -*-
"""
API access_token 鉴权（HTTPTokenAuth）。

语义与现有 views.py 完全一致：
- conf.ini [default] api_access_token 为空时，放行所有请求（不做 token 校验）。
- 非空时，请求须携带匹配的 token（Header: Authorization: Bearer <token>
  或 query/form 字段 access_token，后者由 verify_token 内部兜底支持）。

Batch 4 各接口迁移时，用 @api.auth_required(token_auth) 替代视图函数内
的 if api_access_token: 分支。
"""
from apiflask.security import HTTPTokenAuth

token_auth = HTTPTokenAuth(scheme='Bearer')  # 默认读 Authorization: Bearer <token>


@token_auth.verify_token
def verify_token(token):
    """
    返回 truthy 值表示鉴权通过；返回 None/False 触发 401。
    token 来自 Authorization: Bearer <token> Header（apiflask/flask-httpauth 解析）。
    向后兼容：若 Header 中无 token，则回退读取 request.values['access_token']（query/form 参数），
    与现有调用方行为一致，无需调用方立即改接口。
    若 access_token 未在 conf.ini 配置，直接放行（返回 True）。
    """
    try:
        from configs import configs as _configs
        api_access_token = _configs('api_access_token') or ''
    except Exception:
        return True  # 配置读取失败时不阻塞请求，保持与现有行为一致

    if not api_access_token:
        return True

    # 若 Authorization header 未携带 token，回退到 form/query 参数
    if not token:
        from flask import request as _req
        token = _req.values.get('access_token', '')

    return token == api_access_token


@token_auth.error_handler
def token_error_handler(status_code):
    """将 401/403 包装成现有 {errcode, errmsg, data} 格式，保持 API 调用方感知一致。
    flask-httpauth 4.x 的 error_handler 签名为 (status_code: int)。
    """
    from flask import jsonify
    return jsonify({'errcode': 1, 'errmsg': 'access_token错误或缺失', 'data': ''}), status_code
