#!/usr/bin/python3
# -*- coding:utf-8 -*-
import datetime
import json
import time
import traceback
import uuid

import requests
from flask import current_app
from sqlalchemy import func, select, text

from app import db, scheduler
from app.common.functions import get_cronpilot_sign, single_task, wechat_info_err
from app.logging_config import _ctx_cron_id, _ctx_duration_ms, _ctx_status, _ctx_task_name, _ctx_trace_id
from app.metrics import (
    JOB_DURATION,
    JOB_LOG_WRITE_BYTES,
    JOB_TOTAL,
    JOBS_ACTIVE,
    ORPHAN_JOB_DETECTED,
    TRIGGER_DELAY,
    _ctx_enqueue_time,
)
from app.services.job_log_outcome import (
    STATUS_ERROR,
    STATUS_FAIL,
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
    evaluate_http_response,
    exception_fail_reason,
    is_timeout_exception,
    pre_request_outcome,
    should_alert,
)
from app.services.job_log_service import trim_job_logs_for_cron
from app.services.scheduler_db import fetch_apscheduler_job_ids
from app.services.url_security import make_pinned_session, validate_and_resolve_url, validate_callback_url
from configs import configs
from datas.model.cron_infos import CronInfos
from datas.model.job_log import JobLog
from datas.utils.times import utc_now_hms


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


def _create_pending_log(cron_id, nows, trace_id, timeout_sec=None):
    """[方案B已弃用] 保留签名供外部测试兼容，内部不再调用。"""
    raise NotImplementedError("_create_pending_log removed in Plan-B: use _save_job_log with terminal status directly")


def _update_log_running(jl, started_at):
    """[方案B已弃用] 保留签名供外部测试兼容，内部不再调用。"""
    raise NotImplementedError("_update_log_running removed in Plan-B: started_at passed directly to _save_job_log")


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
):
    if status is None:
        status, fail_reason = pre_request_outcome(content)
    if not trace_id:
        trace_id = str(uuid.uuid1())
    jl = JobLog(
        cron_info_id=cron_id,
        content=content,
        create_time=nows,
        take_time=take_time,
        trace_id=trace_id,
        http_status=http_status,
        status=status,
        fail_reason=fail_reason,
        started_at=started_at,
        finished_at=utc_now_hms(),
        timeout_sec=timeout_sec,
    )
    db.session.add(jl)
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
def cron_do(cron_id):
    saved_jl = None
    with scheduler.app.app_context():
        trace_id = str(uuid.uuid1())
        nows = utc_now_hms()
        t0 = time.time()
        task_name = None
        _ctx_trace_id.set(trace_id)
        _ctx_cron_id.set(str(cron_id))

        # 默认超时（秒）；per-task 值在 cif 加载后覆盖
        _DEFAULT_TIMEOUT_SEC = 5

        try:

            CRON_CONFIG = current_app.config.get('CRON_CONFIG')

            cif = db.session.get(CronInfos, cron_id)

            if not cif:
                ORPHAN_JOB_DETECTED.labels(cron_id=str(cron_id)).inc()
                saved_jl = _save_job_log(
                    cron_id,
                    "定时任务不存在",
                    nows,
                    0,
                    trace_id=trace_id,
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
                        )
                        current_app.logger.warning(
                            "cron url invalid scheme",
                            extra={"event": "cron.url_invalid", "url": req_url},
                        )
                    else:
                        url_ok, url_msg, resolved_ip = validate_and_resolve_url(req_url, CRON_CONFIG)
                        if not url_ok:
                            saved_jl = _save_job_log(
                                cron_id,
                                '回调URL安全校验未通过: %s' % url_msg,
                                nows,
                                0,
                                task_name=task_name,
                                trace_id=trace_id,
                            )
                            current_app.logger.warning(
                                "cron ssrf validation failed",
                                extra={"event": "cron.ssrf_blocked", "url": req_url, "reason": url_msg},
                            )
                        else:
                            # 预检通过：记录 started_at，HTTP 结束后一次终态写入（方案 B：1-write）
                            timeout_sec = int(cif.timeout_sec) if cif.timeout_sec else _DEFAULT_TIMEOUT_SEC
                            started_at = utc_now_hms()
                            try:
                                api_key = CRON_CONFIG.get('api_key') or ''
                                parmas = {}

                                if req_url.find('?') != -1:
                                    pp = req_url.split('?')[-1]
                                    if pp.find('&&') != -1:
                                        ps = pp.split('&&')
                                    else:
                                        ps = pp.split('&')
                                    parmas = {d.split('=')[0]: d.split('=')[1] for d in ps}

                                parmas['cronpilot_trace_id'] = trace_id
                                cronpilot_sign = get_cronpilot_sign(parmas, api_key=api_key)

                                req_method = (getattr(cif, 'req_method', None) or 'GET').upper()

                                # OPT-P0-12: DNS pinning — 使用校验阶段解析的 IP 发起请求
                                # 防止 DNS Rebinding 攻击（TOCTOU 窗口消除）
                                from urllib.parse import urlparse as _urlparse
                                _parsed_scheme = _urlparse(req_url).scheme
                                if resolved_ip:
                                    _http = make_pinned_session(resolved_ip, _urlparse(req_url).hostname, _parsed_scheme)
                                else:
                                    _http = requests

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
                                    req = _http.post(
                                        req_url,
                                        json=post_body,
                                        timeout=timeout_sec,
                                        headers={'user-agent': 'CronPilot'},
                                    )
                                else:
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
                                )
                                if run_status == STATUS_ERROR:
                                    current_app.logger.error(
                                        "cron http callback failed",
                                        extra={
                                            "event": "cron.http_error",
                                            "http_status": req.status_code,
                                            "fail_reason": fail_reason,
                                        },
                                    )
                                else:
                                    current_app.logger.info(
                                        "cron http callback ok",
                                        extra={"event": "cron.http_ok", "http_status": req.status_code},
                                    )
                            except Exception as e:
                                err_content = "发生严重错误:%s" % str(e)
                                fin_status = STATUS_TIMEOUT if is_timeout_exception(e) else STATUS_ERROR
                                saved_jl = _save_job_log(
                                    cron_id,
                                    err_content,
                                    nows,
                                    time.time() - t0,
                                    task_name=task_name,
                                    trace_id=trace_id,
                                    status=fin_status,
                                    fail_reason=exception_fail_reason(e),
                                    started_at=started_at,
                                    timeout_sec=timeout_sec,
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
                if saved_jl is None:
                    saved_jl = _save_job_log(
                        cron_id,
                        "发生严重错误:%s" % str(e),
                        nows,
                        time.time() - t0,
                        task_name=task_name,
                        trace_id=trace_id,
                        status=STATUS_ERROR,
                        fail_reason=exception_fail_reason(e),
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
            enqueue_t = _ctx_enqueue_time.get()
            if enqueue_t > 0:
                delay = t0 - enqueue_t
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

            if cifs:
                for item in cifs:
                    if "cron_%s" % item.id not in job_ids:
                        if item.status == -1:
                            continue
                        from app.services.cron_service import (
                            RETIRE_REASON_ORPHAN,
                            apply_retire,
                        )
                        from app.services.operation_log_service import (
                            OperatorContext,
                            record_operation,
                            snapshot_cron,
                        )
                        apply_retire(
                            item,
                            RETIRE_REASON_ORPHAN,
                            operator=OperatorContext(
                                operator_type='system',
                                operator_name='系统',
                                roles=['system'],
                                permissions=['*'],
                            ),
                        )
                        db.session.commit()
                        record_operation(
                            action='retire_cron',
                            channel='system',
                            operator=OperatorContext(
                                operator_type='system',
                                operator_name='系统',
                                roles=['system'],
                                permissions=['*'],
                            ),
                            target_id=item.id,
                            task_name=item.task_name or '',
                            detail={
                                'reason': item.retire_reason or '',
                                'retired_at': item.retired_at or '',
                                'snapshot': snapshot_cron(item),
                            },
                        )
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

'''
保留一千条数据
'''
@single_task()
def cron_del_job_log():
    with scheduler.app.app_context():
        try:
            job_log_counts = configs('job_log_counts') or 0
            if int(job_log_counts) !=0:
                crons = db.session.scalars(select(CronInfos)).all()
                for item in crons:
                    counts = db.session.scalar(
                        select(func.count())
                        .select_from(JobLog)
                        .where(JobLog.cron_info_id == item.id)
                    ) or 0
                    if counts > int(job_log_counts):
                        trim_job_logs_for_cron(item.id, int(job_log_counts))
                        db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                "cron_del_job_log exception",
                extra={
                    "event": "cron_del_job_log.exception",
                    "error": str(e),
                    "exc_type": type(e).__name__,
                    "traceback": traceback.format_exc(),
                },
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
