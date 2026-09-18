#!/usr/bin/python3
# -*- coding:utf-8 -*-
import datetime
import json
import re
import time
import traceback
import uuid
from urllib.parse import parse_qsl, urlsplit

import requests
from flask import current_app
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app import db, scheduler
from app.common.functions import get_cronpilot_sign, single_task, wechat_info_err
from app.logging_config import _ctx_cron_id, _ctx_duration_ms, _ctx_status, _ctx_task_name, _ctx_trace_id
from app.metrics import (
    GHOST_TASKS,
    JOB_DURATION,
    JOB_LOG_WRITE_BYTES,
    JOB_TOTAL,
    JOBS_ACTIVE,
    ORPHAN_JOB_DETECTED,
    ORPHAN_TASKS,
    TRIGGER_DELAY,
    _ctx_enqueue_time,
    _ctx_scheduled_run_time,
)
from app.services.execution_tracer import ExecutionTracer
from app.services.job_log_outcome import (
    STATUS_ERROR,
    STATUS_FAIL,
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
    evaluate_http_response,
    exception_fail_reason,
    exception_failure_info,
    is_timeout_exception,
    pre_request_outcome,
    should_alert,
)
from app.services.scheduler_db import fetch_apscheduler_job_ids
from app.services.url_security import make_pinned_session, validate_and_resolve_url
from configs import configs
from datas.model.cron_infos import CronInfos
from datas.model.job_log import JobLog
from datas.utils.times import utc_now_hms

# ── Orphan task cache (populated by cron_check, read by Dashboard) ──
_orphan_cache = {
    'orphan_ids': set(),
    'orphan_count': 0,
    'total_scanned': 0,
    'updated_at': 0.0,
}


def get_orphan_cache():
    """Return a snapshot of the latest cron_check reconciliation result."""
    return dict(_orphan_cache)


def _notify_job_outcome(task_name, content, status):
    if not should_alert(status):
        return
    if status == STATUS_ERROR:
        wechat_info_err(
            '定时任务【%s】执行异常' % task_name,
            '返回信息:%s' % content,
        )
    else:
        wechat_info_err(
            '定时任务【%s】发生错误' % task_name,
            '返回信息:%s' % content,
        )


def _build_trigger_signature_params(req_url, trace_id):
    """Return the query parameters that participate in trigger signing.

    ``urlsplit`` excludes a URL fragment, which browsers and requests never
    send to the target server.  Duplicate query keys retain the historical
    last-value-wins behaviour because the signing API accepts a dict.
    """
    params = dict(parse_qsl(urlsplit(req_url).query, keep_blank_values=True))
    params['cronpilot_trace_id'] = trace_id
    return params


def _build_get_actual_url(req_url, inject_params):
    """Build the same normalized GET URL that requests prepares for dispatch."""
    return requests.Request('GET', req_url, params=inject_params).prepare().url


def _mask_cronpilot_sign(url):
    """Mask the sign value without consuming a following URL fragment."""
    return re.sub(r'(cronpilot_sign=)[^&#]+', r'\1***', url) if url else None


def _redact_event_text(value):
    """Remove known trigger credentials before persisting diagnostic text."""
    if not value:
        return ''
    return re.sub(r'(cronpilot_sign=)[^&#\s]+', r'\1***', str(value))


def _ssrf_block_detail(message):
    """Convert a validator message into stable, queryable event fields."""
    text_value = _redact_event_text(message)
    lowered = text_value.lower()
    if '私有' in text_value or '内网' in text_value or 'private' in lowered:
        block_type = 'private_ip'
    elif 'dns' in lowered or '解析' in text_value:
        block_type = 'dns_resolution'
    elif '协议' in text_value or 'scheme' in lowered:
        block_type = 'invalid_scheme'
    else:
        block_type = 'policy'
    return {'block_type': block_type, 'block_detail': text_value}


def _save_job_log(
    cron_id,
    content,
    nows,
    take_time,
    task_name=None,
    trace_id='',
    http_status=None,
    status=None,
    fail_reason=None,
    started_at=None,
    timeout_sec=None,
    trigger_source=None,
    actual_url=None,
    resolved_ip=None,
    trigger_delay_ms=None,
    failure_stage=None,
    transport_state=None,
    response_received=None,
):
    if status is None:
        status, fail_reason = pre_request_outcome(content)
    if failure_stage is None:
        failure_stage = 'remote_response' if http_status is not None else 'pre_request'
    if response_received is None:
        response_received = http_status is not None
    if transport_state is None:
        transport_state = 'response_received' if response_received else 'not_started'
    if not trace_id:
        trace_id = str(uuid.uuid1())
    jl = db.session.scalars(select(JobLog).where(JobLog.trace_id == trace_id)).first()
    if jl is None:
        jl = JobLog(cron_info_id=cron_id, trace_id=trace_id, create_time=nows)
        db.session.add(jl)
    elif jl.status not in ('pending', 'running'):
        # A terminal record is immutable.  A retrying or late code path must
        # not rewrite the evidence that was already committed for this trace.
        return jl
    jl.content = content
    jl.take_time = take_time
    jl.http_status = http_status
    jl.status = status
    jl.fail_reason = fail_reason
    jl.started_at = started_at
    jl.finished_at = utc_now_hms()
    jl.timeout_sec = timeout_sec
    jl.trigger_source = trigger_source
    jl.actual_url = actual_url
    jl.resolved_ip = resolved_ip
    jl.trigger_delay_ms = trigger_delay_ms
    jl.failure_stage = failure_stage
    jl.transport_state = transport_state
    jl.response_received = response_received
    db.session.commit()
    try:
        from app.services.job_health_service import update_job_health
        update_job_health(
            cron_id,
            status,
            nows,
            trace_id=trace_id,
            cron_config=current_app.config.get('CRON_CONFIG'),
        )
    except Exception:
        current_app.logger.exception(
            'health update failed',
            extra={"event": "health.update_failed"},
        )
        try:
            db.session.rollback()
        except Exception:
            pass
    if task_name:
        _notify_job_outcome(task_name, content, status)
    return jl


def _create_pending_job_log(cron_id, trace_id, nows, trigger_source, trigger_delay_ms):
    """Commit the parent before any remote HTTP call so add_log can attach safely."""
    record = JobLog(
        cron_info_id=cron_id,
        trace_id=trace_id,
        content='',
        create_time=nows,
        status='pending',
        trigger_source=trigger_source,
        trigger_delay_ms=trigger_delay_ms,
    )
    db.session.add(record)
    db.session.commit()
    return record


@single_task()
def cron_check_db_sleep():
    with scheduler.app.app_context():
        try:
            db.session.execute(text("SELECT 1"))
            db.session.commit()
        except Exception as e:
            wechat_info_err('定时任务发生严重错误', '检查数据库出错:%s' % str(e))
            db.session.rollback()

'''
定时操作
'''
@single_task()
def cron_do(cron_id, trigger_source='schedule'):
    """执行定时任务触发请求。

    Args:
        cron_id: 任务主键
        trigger_source: 触发来源 — 'schedule'(定时) / 'manual'(手动) / 'one_shot'(一次性)
    """
    saved_jl = None
    tracer = None
    with scheduler.app.app_context():
        trace_id = str(uuid.uuid1())
        nows = utc_now_hms()
        t0 = time.time()
        task_name = None
        _ctx_cron_id.set(str(cron_id))

        # GAP-2: 链路起点日志 — 标记 cron_do 开始执行
        current_app.logger.info(
            "cron_do start",
            extra={
                "event": "cron.start",
                "cron_id": cron_id,
                "trace_id": trace_id,
                "trigger_source": trigger_source,
            },
        )

        # Keep JobLog.trigger_delay_ms's legacy meaning: time from the
        # single_task wrapper entry to cron_do's body.  Scheduler queue delay
        # belongs only to task.enqueued.detail.scheduled_delay_ms.
        enqueue_time = _ctx_enqueue_time.get()
        _trigger_delay_ms = int((t0 - enqueue_time) * 1000) if enqueue_time else None

        # The custom threadpool executor passes the specific APScheduler
        # scheduled time through ContextVar.  Manual runs have no such value.
        scheduled_run_time = _ctx_scheduled_run_time.get()
        if scheduled_run_time is not None:
            _scheduled_delay_ms = int((t0 - scheduled_run_time.timestamp()) * 1000)
        else:
            _scheduled_delay_ms = None
        for _attempt in range(3):
            try:
                saved_jl = _create_pending_job_log(
                    cron_id, trace_id, nows, trigger_source, _trigger_delay_ms
                )
                break
            except IntegrityError:
                db.session.rollback()
                trace_id = str(uuid.uuid1())
        else:
            raise RuntimeError('unable to allocate unique cron trace_id')
        _ctx_trace_id.set(trace_id)
        try:
            tracer = ExecutionTracer(trace_id, cron_id, run_id=saved_jl.id)
            tracer.emit('task.enqueued', detail={
                'trigger_source': trigger_source,
                'scheduled_delay_ms': _scheduled_delay_ms,
                'scheduled_at': scheduled_run_time.isoformat() if scheduled_run_time else None,
            })
            saved_jl.status = 'running'
            db.session.commit()
            tracer.emit('task.start')

            # 默认超时（秒）；per-task 值在 cif 加载后覆盖
            _DEFAULT_TIMEOUT_SEC = 5

            CRON_CONFIG = current_app.config.get('CRON_CONFIG')

            cif = db.session.get(CronInfos, cron_id)
            tracer.emit('db.load_cif')

            if not cif:
                ORPHAN_JOB_DETECTED.labels(cron_id=str(cron_id)).inc()
                saved_jl = _save_job_log(
                    cron_id,
                    "定时任务不存在",
                    nows,
                    0,
                    trace_id=trace_id,
                    trigger_source=trigger_source,
                    trigger_delay_ms=_trigger_delay_ms,
                )
                current_app.logger.error(
                    "ORPHAN_JOB: scheduler has cron_%s but cron_infos record "
                    "missing. Likely legacy cron_del residue. "
                    "Action: remove from cron.sqlite.",
                    cron_id,
                    extra={"event": "cron.orphan_detected", "cron_id": cron_id},
                )
            else:
                req_url = cif.req_url
                task_name = cif.task_name
                _ctx_task_name.set(task_name or '')
                if not req_url:
                    saved_jl = _save_job_log(
                        cron_id,
                        "请求链接不存在",
                        nows,
                        0,
                        task_name=task_name,
                        trace_id=trace_id,
                        trigger_source=trigger_source,
                        trigger_delay_ms=_trigger_delay_ms,
                    )
                    current_app.logger.warning(
                        "cron url missing",
                        extra={"event": "cron.url_missing"},
                    )
                else:
                    if req_url.find('http') == -1:
                        saved_jl = _save_job_log(
                            cron_id,
                            "请求链接有误，请检查一下",
                            nows,
                            0,
                            task_name=task_name,
                            trace_id=trace_id,
                            trigger_source=trigger_source,
                            trigger_delay_ms=_trigger_delay_ms,
                        )
                        current_app.logger.warning(
                            "cron url invalid scheme",
                            extra={"event": "cron.url_invalid", "url": req_url},
                        )
                    else:
                        url_ok, url_msg, resolved_ip = validate_and_resolve_url(req_url, CRON_CONFIG)
                        ssrf_detail = {}
                        if not url_ok:
                            ssrf_detail = _ssrf_block_detail(url_msg)
                        tracer.emit(
                            'ssrf.check',
                            outcome='ok' if url_ok else 'blocked',
                            detail=ssrf_detail,
                        )
                        if not url_ok:
                            saved_jl = _save_job_log(
                                cron_id,
                                '触发URL安全校验未通过: %s' % url_msg,
                                nows,
                                0,
                                task_name=task_name,
                                trace_id=trace_id,
                                trigger_source=trigger_source,
                                trigger_delay_ms=_trigger_delay_ms,
                            )
                            current_app.logger.warning(
                                "cron ssrf validation failed",
                                extra={"event": "cron.ssrf_blocked", "url": req_url, "reason": url_msg},
                            )
                        else:
                            # 预检通过：记录 started_at，HTTP 结束后一次终态写入（方案 B：1-write）
                            timeout_sec = int(cif.timeout_sec) if cif.timeout_sec else _DEFAULT_TIMEOUT_SEC
                            started_at = utc_now_hms()
                            _actual_url = None  # 提前初始化：防止 try 内赋值前抛异常时 except 引用未定义变量
                            _request_call_started = False
                            try:
                                api_key = CRON_CONFIG.get('api_key') or ''
                                signing_params = _build_trigger_signature_params(
                                    req_url, trace_id
                                )
                                cronpilot_sign = get_cronpilot_sign(
                                    signing_params, api_key=api_key
                                )

                                req_method = (getattr(cif, 'req_method', None) or 'GET').upper()

                                # 构建实际请求 URL（含注入的 trace_id/sign）用于链路追踪
                                _inject_params = {'cronpilot_trace_id': trace_id, 'cronpilot_sign': cronpilot_sign}
                                if req_method == 'GET':
                                    _actual_url = _build_get_actual_url(req_url, _inject_params)
                                else:
                                    _actual_url = req_url  # POST: params in body

                                # OPT-P0-12: DNS pinning — 使用校验阶段解析的 IP 发起请求
                                # 防止 DNS Rebinding 攻击（TOCTOU 窗口消除）
                                from urllib.parse import urlparse as _urlparse
                                _parsed_scheme = _urlparse(req_url).scheme
                                if resolved_ip:
                                    _http = make_pinned_session(resolved_ip, _urlparse(req_url).hostname, _parsed_scheme)
                                else:
                                    _http = requests

                                # GAP-3: HTTP 发出前日志 — 记录实际请求参数
                                current_app.logger.info(
                                    "sending trigger request",
                                    extra={
                                        "event": "cron.http_sending",
                                        "url": req_url,
                                        "method": req_method,
                                        "resolved_ip": resolved_ip,
                                        "timeout_sec": timeout_sec,
                                    },
                                )
                                from app.services.execution_tracer import sanitize_event_url
                                tracer.emit('http.start', detail={
                                    'method': req_method,
                                    'display_url': sanitize_event_url(req_url),
                                    'timeout_sec': timeout_sec,
                                    'transport_state': 'prepared',
                                    'response_received': False,
                                })

                                if req_method == 'POST':
                                    if cif.req_body:
                                        import json as _json
                                        parsed_body = _json.loads(cif.req_body)
                                        post_body = parsed_body if isinstance(parsed_body, dict) else {}
                                    else:
                                        post_body = {}
                                    if 'cronpilot_trace_id' not in post_body:
                                        post_body['cronpilot_trace_id'] = trace_id
                                    if 'cronpilot_sign' not in post_body:
                                        post_body['cronpilot_sign'] = cronpilot_sign
                                    _request_call_started = True
                                    req = _http.post(
                                        req_url,
                                        json=post_body,
                                        timeout=timeout_sec,
                                        headers={'user-agent': 'CronPilot'},
                                    )
                                else:
                                    _request_call_started = True
                                    req = _http.get(
                                        req_url,
                                        params={
                                            'cronpilot_trace_id': trace_id,
                                            'cronpilot_sign': cronpilot_sign,
                                        },
                                        timeout=timeout_sec,
                                        headers={'user-agent': 'CronPilot'},
                                    )

                                ret = req.text
                                try:
                                    ret = req.json()
                                except Exception:
                                    pass

                                if isinstance(ret, dict):
                                    ret = json.dumps(ret, ensure_ascii=False)

                                run_status, fail_reason = evaluate_http_response(
                                    req.status_code,
                                    ret,
                                    CRON_CONFIG.get('error_keyword'),
                                    CRON_CONFIG.get('fail_on_http_4xx_5xx'),
                                )
                                saved_jl = _save_job_log(
                                    cron_id,
                                    ret,
                                    nows,
                                    time.time() - t0,
                                    task_name=task_name,
                                    trace_id=trace_id,
                                    http_status=req.status_code,
                                    status=run_status,
                                    fail_reason=fail_reason,
                                    started_at=started_at,
                                    timeout_sec=timeout_sec,
                                    trigger_source=trigger_source,
                                    actual_url=_mask_cronpilot_sign(_actual_url),
                                    resolved_ip=resolved_ip,
                                    trigger_delay_ms=_trigger_delay_ms,
                                    failure_stage='remote_response',
                                    transport_state='response_received',
                                    response_received=True,
                                )
                                tracer.emit(
                                    'http.complete',
                                    outcome='ok' if run_status == STATUS_SUCCESS else 'fail',
                                    detail={
                                        'http_status': req.status_code,
                                        'response_bytes': len(getattr(req, 'content', b'') or b''),
                                        'transport_state': 'response_received',
                                        'response_received': True,
                                    },
                                )
                                if run_status == STATUS_ERROR:
                                    current_app.logger.error(
                                        "cron http trigger failed",
                                        extra={
                                            "event": "cron.http_error",
                                            "http_status": req.status_code,
                                            "fail_reason": fail_reason,
                                        },
                                    )
                                else:
                                    current_app.logger.info(
                                        "cron http trigger ok",
                                        extra={"event": "cron.http_ok", "http_status": req.status_code},
                                    )
                            except Exception as e:
                                err_content = "发生严重错误:%s" % str(e)
                                fin_status = STATUS_TIMEOUT if is_timeout_exception(e) else STATUS_ERROR
                                failure_info = exception_failure_info(e)
                                saved_jl = _save_job_log(
                                    cron_id,
                                    err_content,
                                    nows,
                                    time.time() - t0,
                                    task_name=task_name,
                                    trace_id=trace_id,
                                    status=fin_status,
                                    fail_reason=failure_info['fail_reason'],
                                    started_at=started_at,
                                    timeout_sec=timeout_sec,
                                    trigger_source=trigger_source,
                                    actual_url=_mask_cronpilot_sign(_actual_url),
                                    resolved_ip=resolved_ip,
                                    trigger_delay_ms=_trigger_delay_ms,
                                    failure_stage=failure_info['failure_stage'],
                                    transport_state='failed_before_response' if _request_call_started else 'prepared',
                                    response_received=False,
                                )
                                tracer.emit(
                                    'http.timeout' if fin_status == STATUS_TIMEOUT else 'http.error',
                                    outcome='timeout' if fin_status == STATUS_TIMEOUT else 'fail',
                                    detail={
                                        'exc_type': type(e).__name__,
                                        'exc_detail': _redact_event_text(str(e)),
                                        'timeout_sec': timeout_sec,
                                        'failure_stage': failure_info['failure_stage'],
                                        'fail_reason': failure_info['fail_reason'],
                                        'transport_state': 'failed_before_response' if _request_call_started else 'prepared',
                                        'response_received': False,
                                    },
                                )
                                current_app.logger.error(
                                    "cron http request exception",
                                    extra={
                                        "event": "cron.exception",
                                        "error": str(e),
                                        "exc_type": type(e).__name__,
                                    },
                                )

        except Exception as e:
            db.session.rollback()
            try:
                saved_jl = _save_job_log(
                    cron_id,
                    "发生严重错误:%s" % str(e),
                    nows,
                    time.time() - t0,
                    task_name=task_name,
                    trace_id=trace_id,
                    status=STATUS_ERROR,
                    fail_reason=exception_fail_reason(e),
                    trigger_source=trigger_source,
                    trigger_delay_ms=_trigger_delay_ms,
                )
            except Exception:
                pass
            current_app.logger.error(
                "cron_do fatal exception",
                extra={
                    "event": "cron.fatal",
                    "error": str(e),
                    "exc_type": type(e).__name__,
                    "traceback": traceback.format_exc(),
                },
            )
            wechat_info_err(
                '定时任务发生严重错误',
                'trace_id:%s 返回信息:%s' % (trace_id, str(e)),
            )

        finally:
            if tracer is not None and saved_jl is not None and getattr(saved_jl, 'status', None) in (
                STATUS_SUCCESS, STATUS_FAIL, STATUS_TIMEOUT, STATUS_ERROR,
            ):
                tracer.emit(
                    'db.write_log',
                    outcome='ok',
                    detail={'status': saved_jl.status, 'fail_reason': saved_jl.fail_reason},
                )
            if tracer is not None and saved_jl is not None:
                try:
                    saved_jl.observability_state = 'degraded' if tracer.disabled_reason else 'healthy'
                    saved_jl.observability_drop_reason = tracer.disabled_reason
                    db.session.commit()
                except Exception:
                    db.session.rollback()
            elapsed = time.time() - t0
            _ctx_duration_ms.set(int(elapsed * 1000))
            prom_status = 'error' if getattr(saved_jl, 'status', None) in (STATUS_ERROR, STATUS_TIMEOUT, STATUS_FAIL) else 'ok'
            # Truncate task_name to prevent high-cardinality if dynamic names are used.
            prom_task = (task_name or 'unknown')[:50]
            if saved_jl is not None:
                _ctx_status.set(prom_status)
                JOB_DURATION.labels(task_name=prom_task, status=prom_status).observe(elapsed)
                JOB_TOTAL.labels(task_name=prom_task, status=prom_status).inc()
                content_bytes = len((saved_jl.content or '').encode('utf-8'))
                if content_bytes > 0:
                    JOB_LOG_WRITE_BYTES.observe(content_bytes)
            if scheduled_run_time is not None:
                delay = t0 - scheduled_run_time.timestamp()
                if delay >= 0:
                    TRIGGER_DELAY.labels(task_name=prom_task).observe(delay)

        # SA 2.0：离开 app_context 后实例可能 detach，须在块内取主键
        return saved_jl.id if saved_jl else None

@single_task()
def cron_check():
    with scheduler.app.app_context():
        try:
            job_ids = fetch_apscheduler_job_ids(current_app.config.get('CRON_DB_URL'))
            cifs = db.session.scalars(select(CronInfos)).all()

            orphan_count = 0
            orphan_id_set = set()
            if cifs:
                for item in cifs:
                    if "cron_%s" % item.id not in job_ids:
                        if item.status == -1:
                            continue
                        orphan_count += 1
                        orphan_id_set.add(item.id)
                        current_app.logger.warning(
                            "orphan task detected: cron_%s (%s) — not in JobStore, manual action required",
                            item.id, item.task_name or '',
                            extra={
                                "event": "cron_check.orphan",
                                "cron_id": item.id,
                                "task_name": item.task_name or '',
                                "status": item.status,
                            },
                        )
            _orphan_cache['orphan_ids'] = orphan_id_set
            _orphan_cache['orphan_count'] = orphan_count
            _orphan_cache['total_scanned'] = len(cifs)
            _orphan_cache['updated_at'] = time.time()
            ORPHAN_TASKS.set(orphan_count)
            if orphan_count > 0:
                current_app.logger.warning(
                    "reconciliation complete: %d orphan task(s) detected, no auto-retire — manual action required",
                    orphan_count,
                    extra={"event": "cron_check.orphan_summary", "count": orphan_count},
                )

            # ── Reverse scan: detect ghost jobs (in scheduler but retired/absent in cron_infos) ──
            cif_map = {item.id: item for item in cifs} if cifs else {}
            ghost_count = 0
            for job_id in job_ids:
                if not job_id.startswith('cron_'):
                    continue
                try:
                    cron_pk = int(job_id.split('_', 1)[1])
                except (ValueError, IndexError):
                    continue
                cif = cif_map.get(cron_pk)
                if cif and cif.status == -1:
                    ghost_count += 1
                    current_app.logger.warning(
                        "ghost job detected: %s (task=%s, status=-1) — removing from scheduler",
                        job_id, cif.task_name or '',
                        extra={"event": "cron_check.ghost", "job_id": job_id, "task_name": cif.task_name or ''},
                    )
                    try:
                        scheduler.remove_job(job_id)
                    except Exception:
                        current_app.logger.error("failed to remove ghost job %s", job_id, exc_info=True)
                elif cif is None:
                    ghost_count += 1
                    current_app.logger.warning(
                        "stale scheduler entry: %s — no matching cron_infos record, manual action required",
                        job_id,
                        extra={"event": "cron_check.stale", "job_id": job_id},
                    )
            GHOST_TASKS.set(ghost_count)

            # Update active/retired gauge for Prometheus after reconciliation
            all_cifs = db.session.scalars(select(CronInfos)).all()
            active_count = sum(1 for c in all_cifs if c.status != -1)
            retired_count = len(all_cifs) - active_count
            JOBS_ACTIVE.labels(state='active').set(active_count)
            JOBS_ACTIVE.labels(state='retired').set(retired_count)
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                "cron_check exception",
                extra={
                    "event": "cron_check.exception",
                    "error": str(e),
                    "exc_type": type(e).__name__,
                    "traceback": traceback.format_exc(),
                },
            )
            wechat_info_err('定时任务发生严重错误', '返回信息:%s' % str(e))
    return "ok"

@single_task()
def cron_del_job_log():
    """兼容历史调度注册：执行日志永久保留，不再按数量自动裁剪。"""
    with scheduler.app.app_context():
        current_app.logger.info(
            'job log retention sweep skipped: automatic deletion is disabled',
            extra={'event': 'cron.job_log_retention.disabled'},
        )
    return "ok"


@single_task()
def cron_del_operation_log():
    with scheduler.app.app_context():
        try:
            from app.services.operation_log_service import trim_operation_logs

            keep = configs().get('operation_log_counts') or 0
            if int(keep) != 0:
                trim_operation_logs(int(keep))
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                "cron_del_operation_log exception",
                extra={
                    "event": "cron_del_operation_log.exception",
                    "error": str(e),
                    "exc_type": type(e).__name__,
                    "traceback": traceback.format_exc(),
                },
            )
    return "ok"
