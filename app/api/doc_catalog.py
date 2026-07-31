"""API 文档目录（管理端只读展示）。

说明：
- 这里定义“查询语义”接口白名单，而不是按 HTTP 方法粗暴判断。
- 管理端 API 文档页只展示 query_semantic=True 且当前用户有权限的条目。
- 信息不完整（无摘要/路径/响应说明）的条目自动过滤，避免空壳展示。
"""
from functools import lru_cache


DOC_ITEMS = [
    {
        'id': 'api-test',
        'method': 'GET',
        'path': '/api/test',
        'summary': '接口连通性测试',
        'description': '用于验证 API 服务可达与鉴权链路是否正常。',
        'required_permission': 'cron:read',
        'query_semantic': True,
        'params': [],
        'response': '返回 {errcode:0, errmsg:"test"}。',
        'example': 'curl -H "Authorization: Bearer <token>" http://<host>/api/test',
    },
    {
        'id': 'openapi-json',
        'method': 'GET',
        'path': '/api/openapi.json',
        'summary': 'OpenAPI JSON 规范下载',
        'description': '用于查询接口契约（字段、示例、错误码），供调用方集成时参考。',
        'required_permission': 'cron:read',
        'query_semantic': True,
        'params': [],
        'response': '返回 OpenAPI 3.0 JSON 文档。',
        'example': 'curl -H "Authorization: Bearer <token>" http://<host>/api/openapi.json',
    },
    {
        'id': 'cron-query',
        'method': 'GET',
        'path': '/api/cron/query',
        'summary': '任务查询',
        'description': '按 task_name/keyword/status 查询任务列表；结果自动按当前调用方权限与 Scope 过滤。',
        'required_permission': 'cron:read',
        'query_semantic': True,
        'params': ['task_name（可选，精确）', 'keyword（可选，模糊）', 'status（可选，-1/0/1）', 'scope_type（可选，GLOBAL/GROUP）', 'group_id（可选）', 'req_method（可选，GET/POST）', 'updated_from（可选）', 'updated_to（可选）', 'limit（可选）', 'offset（可选）'],
        'response': '返回 items 列表（任务状态、作用域、触发 URL 等只读信息）。',
        'example': (
            'curl -H "Authorization: Bearer <token>" '
            '"http://<host>/api/cron/query?keyword=demo&status=1&req_method=GET&limit=20&offset=0"'
        ),
    },
    {
        'id': 'cron-logs',
        'method': 'GET',
        'path': '/api/cron/logs',
        'summary': '任务执行日志查询',
        'description': '按 task_name 查询执行日志（倒序）；结果受当前调用方 Scope 控制。',
        'required_permission': 'log:read',
        'query_semantic': True,
        'params': ['task_name（必填）', 'status（可选）', 'http_status（可选）', 'beg_time（可选）', 'end_time（可选）', 'limit（可选）', 'offset（可选）'],
        'response': '返回 items 列表（status/http_status/take_time/fail_reason 等执行结果字段）。',
        'example': (
            'curl -H "Authorization: Bearer <token>" '
            '"http://<host>/api/cron/logs?task_name=demo&status=fail&limit=20"'
        ),
    },
    {
        'id': 'cron-detail',
        'method': 'GET',
        'path': '/api/cron/detail',
        'summary': '任务详情查询',
        'description': '按 task_name（或 id）查询单个任务详情；结果受当前调用方 Scope 控制。',
        'required_permission': 'cron:read',
        'query_semantic': True,
        'params': ['task_name（与 id 二选一）', 'id（与 task_name 二选一）'],
        'response': '返回任务完整只读详情（调度字段、作用域、状态、触发配置等）。',
        'example': 'curl -H "Authorization: Bearer <token>" "http://<host>/api/cron/detail?task_name=demo"',
    },
    {
        'id': 'cron-log-detail',
        'method': 'GET',
        'path': '/api/cron/log/detail',
        'summary': '执行日志详情查询',
        'description': '按 id 或 log_id 查询单条执行日志详情；结果受任务 Scope 控制。',
        'required_permission': 'log:read',
        'query_semantic': True,
        'params': ['id（与 log_id 二选一）', 'log_id（与 id 二选一）'],
        'response': '返回单条执行日志详情（状态、耗时、HTTP 码、失败原因、内容等）。',
        'example': 'curl -H "Authorization: Bearer <token>" "http://<host>/api/cron/log/detail?id=123"',
    },
    {
        # 非查询语义：用于签发凭证，不在只读查询文档中展示
        'id': 'auth-token',
        'method': 'POST',
        'path': '/api/auth/token',
        'summary': '获取或续签 API Token',
        'description': '认证后签发新 Token，会改变凭证状态。',
        'required_permission': 'cron:read',
        'query_semantic': False,
        'params': ['username', 'password（Basic Auth 或 form）'],
        'response': '{errcode:0, data:{token, expires_at}}',
    },
]


def _is_complete_item(item):
    return bool(
        (item or {}).get('summary')
        and (item or {}).get('path')
        and (item or {}).get('method')
        and (item or {}).get('response')
    )


@lru_cache(maxsize=64)
def _cached_docs_for_permission_key(permission_key):
    """按权限集合缓存可见接口清单（服务进程内缓存，发版重启后刷新）。"""
    permission_set = set(permission_key or ())
    docs = []
    for item in DOC_ITEMS:
        if not item.get('query_semantic'):
            continue
        required = (item.get('required_permission') or '').strip()
        if required and required not in permission_set:
            continue
        if not _is_complete_item(item):
            continue
        docs.append(dict(item))
    return tuple(docs)


def list_readonly_docs(permission_set):
    """返回可展示的只读接口目录。"""
    key = tuple(sorted(set(permission_set or ())))
    return [dict(item) for item in _cached_docs_for_permission_key(key)]
