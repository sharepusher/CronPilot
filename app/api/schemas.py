# -*- coding:utf-8 -*-
"""
API 请求/响应 Schema（marshmallow）。

设计原则：
- req_body 保持 String 类型，与 cron_validator 的 json.loads() 路径对齐；
  Schema 层做类型存在性检查，语义校验（JSON 格式、dict 结构）由 cron_validator 承担。
- access_token 通过 HTTPTokenAuth 在 Batch 3 统一处理，不在 Schema 字段中重复。
- 所有可选字段显式 required=False，避免 marshmallow 4.x 行为差异导致歧义。
"""
from apiflask import Schema
from apiflask.fields import String, Integer
from apiflask.validators import Length, OneOf, Range


class CronUpsertIn(Schema):
    """POST /api/cron — 新增或更新定时任务。"""
    task_name = String(required=True, metadata={'description': '任务名称（唯一键）'})
    task_keyword = String(
        required=True,
        validate=Length(1, 500),
        metadata={'description': '任务说明（用途、需求链接等），1-500 字'},
    )
    req_url = String(
        required=True,
        validate=Length(1, 200),
        metadata={'description': '触发 URL，由调度器到点发起 GET/POST 请求'},
    )
    req_method = String(
        load_default='GET',
        validate=OneOf(['GET', 'POST']),
        metadata={'description': '请求方式：GET（默认）或 POST'},
    )
    req_body = String(
        required=False,
        load_default=None,
        metadata={'description': 'POST 时的 JSON 对象字符串（系统会注入 cronpilot_trace_id / cronpilot_sign）'},
    )
    run_date = String(
        required=False,
        load_default='',
        metadata={'description': '具体执行时刻（ds_ms=1 时必填），格式 YYYY-MM-DD HH:MM'},
    )
    ds_ms = String(
        required=False,
        load_default='',
        validate=OneOf(['', '1', '2']),
        metadata={'description': '定时方式：1=具体时间，2=定时模式（cron）'},
    )
    day = String(required=False, load_default='', metadata={'description': '日（1-31），支持 * */n a-b a,b'})
    day_of_week = String(required=False, load_default='', metadata={'description': '星期（0-6 或 mon-sun），支持组合'})
    hour = String(required=False, load_default='', metadata={'description': '小时（0-23），支持 * */n a-b a,b'})
    minute = String(required=False, load_default='', metadata={'description': '分钟（0-59），支持 * */n a-b a,b'})
    second = String(required=False, load_default='', metadata={'description': '秒（0-59），支持 * */n a-b a,b'})
    timeout_sec = Integer(
        required=False,
        load_default=None,
        validate=Range(min=1, max=120),
        metadata={'description': '单任务 HTTP 超时（秒），1-120；不传则使用系统默认 5s'},
    )


class CronStatusIn(Schema):
    """POST /api/cron/status — 切换或指定任务运行状态。"""
    task_name = String(required=True, metadata={'description': '任务名称'})
    status = Integer(
        required=False,
        load_default=None,
        validate=Range(min=0, max=1),
        metadata={'description': '目标状态：0=停止，1=运行中；不传则取反'},
    )


class CronRetireIn(Schema):
    """POST /api/cron/retire — 下线（永久停用）任务。"""
    task_name = String(required=True, metadata={'description': '任务名称'})
    reason = String(
        required=False,
        load_default=None,
        validate=Length(0, 500),
        metadata={'description': '下线原因（可选，最多 500 字）'},
    )


class AddLogIn(Schema):
    """POST /api/cron/add_log — 业务方回传执行进度。"""
    cronpilot_trace_id = String(
        required=True,
        metadata={'description': 'CronPilot 定时触发时生成的 Trace ID (UUID)'},
    )
    content = String(
        required=True,
        validate=Length(1, 10000),
        metadata={'description': '进度/日志内容，最多 10000 字'},
    )


class ApiSuccessOut(Schema):
    """通用成功响应（errcode=0）。"""
    errcode = Integer(metadata={'description': '0 表示成功'})
    errmsg = String(metadata={'description': '结果描述'})
    data = String(metadata={'description': '附加数据（字符串或空）'})
