#!/usr/bin/python3 
# -*- coding:utf-8 -*-
import datetime
import json
import time
import traceback
import uuid

import records
import requests
from flask import current_app
from sqlalchemy import func, select, text

from app import scheduler, db
from app.common.functions import wechat_info_err, single_task, get_cronpilot_sign
from app.services.job_log_outcome import (
    STATUS_ERROR,
    evaluate_http_response,
    exception_fail_reason,
    pre_request_outcome,
    should_alert,
)
from app.services.job_log_service import trim_job_logs_for_cron
from app.services.url_security import validate_callback_url
from configs import configs
from datas.model.cron_infos import CronInfos
from datas.model.job_log import JobLog
from datas.utils.times import get_now_time


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


def _save_job_log(
    cron_id,
    content,
    nows,
    take_time,
    task_name=None,
    log_id='',
    http_status=None,
    status=None,
    fail_reason=None,
):
    if status is None:
        status, fail_reason = pre_request_outcome(content)
    # 每条执行记录必有 log_id，便于与回调 / add_log / 文件日志相互印证
    if not log_id:
        log_id = str(uuid.uuid1())
    jl = JobLog(
        cron_info_id=cron_id,
        content=content,
        create_time=nows,
        take_time=take_time,
        log_id=log_id,
        http_status=http_status,
        status=status,
        fail_reason=fail_reason,
    )
    db.session.add(jl)
    db.session.commit()
    try:
        from app.services.job_health_service import update_job_health
        update_job_health(
            cron_id,
            status,
            nows,
            log_id=log_id,
            cron_config=current_app.config.get('CRON_CONFIG'),
        )
    except Exception:
        current_app.logger.exception(
            'update_job_health failed cron_id=%s log_id=%s',
            cron_id,
            log_id,
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
        # 一次触发一个 log_id：预检失败 / HTTP / 异常共用，保证可追溯
        cronpilot_log_id = str(uuid.uuid1())
        nows = get_now_time()
        t0 = time.time()
        task_name = None

        try:

            CRON_CONFIG = current_app.config.get('CRON_CONFIG')

            cif = db.session.get(CronInfos, cron_id)

            if not cif:
                saved_jl = _save_job_log(
                    cron_id,
                    "定时任务不存在",
                    nows,
                    0,
                    log_id=cronpilot_log_id,
                )
            else:
                req_url = cif.req_url
                task_name = cif.task_name
                if not req_url:
                    saved_jl = _save_job_log(
                        cron_id,
                        "请求链接不存在",
                        nows,
                        0,
                        task_name=task_name,
                        log_id=cronpilot_log_id,
                    )
                else:
                    if req_url.find('http') == -1:
                        saved_jl = _save_job_log(
                            cron_id,
                            "请求链接有误，请检查一下",
                            nows,
                            0,
                            task_name=task_name,
                            log_id=cronpilot_log_id,
                        )
                    else:
                        url_ok, url_msg = validate_callback_url(req_url, CRON_CONFIG)
                        if not url_ok:
                            saved_jl = _save_job_log(
                                cron_id,
                                '回调URL安全校验未通过: %s' % url_msg,
                                nows,
                                0,
                                task_name=task_name,
                                log_id=cronpilot_log_id,
                            )
                        else:
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

                                parmas['cronpilot_log_id'] = cronpilot_log_id
                                cronpilot_sign = get_cronpilot_sign(parmas, api_key=api_key)

                                req_method = (getattr(cif, 'req_method', None) or 'GET').upper()
                                if req_method == 'POST':
                                    # 从用户配置的 req_body 解析 JSON 作为基础 body
                                    if cif.req_body:
                                        import json as _json
                                        parsed_body = _json.loads(cif.req_body)
                                        post_body = parsed_body if isinstance(parsed_body, dict) else {}
                                    else:
                                        post_body = {}
                                    # 注入 cronpilot 参数（不覆盖用户已定义的字段）
                                    if 'cronpilot_log_id' not in post_body:
                                        post_body['cronpilot_log_id'] = cronpilot_log_id
                                    if 'cronpilot_sign' not in post_body:
                                        post_body['cronpilot_sign'] = cronpilot_sign
                                    req = requests.post(
                                        req_url,
                                        json=post_body,
                                        timeout=2 * 60,
                                        headers={'user-agent': 'CronPilot'},
                                    )
                                else:
                                    req = requests.get(
                                        req_url,
                                        params={
                                            'cronpilot_log_id': cronpilot_log_id,
                                            'cronpilot_sign': cronpilot_sign,
                                        },
                                        timeout=2 * 60,
                                        headers={'user-agent': 'CronPilot'},
                                    )

                                ret = req.text
                                try:
                                    ret = req.json()
                                except Exception:
                                    pass

                                if type(ret) == dict:
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
                                    log_id=cronpilot_log_id,
                                    http_status=req.status_code,
                                    status=run_status,
                                    fail_reason=fail_reason,
                                )
                            except Exception as e:
                                err_content = "发生严重错误:%s" % str(e)
                                saved_jl = _save_job_log(
                                    cron_id,
                                    err_content,
                                    nows,
                                    time.time() - t0,
                                    task_name=task_name,
                                    log_id=cronpilot_log_id,
                                    status=STATUS_ERROR,
                                    fail_reason=exception_fail_reason(e),
                                )

        except Exception as e:
            print(str(e))
            db.session.rollback()
            try:
                saved_jl = _save_job_log(
                    cron_id,
                    "发生严重错误:%s" % str(e),
                    nows,
                    time.time() - t0,
                    task_name=task_name,
                    log_id=cronpilot_log_id,
                    status=STATUS_ERROR,
                    fail_reason=exception_fail_reason(e),
                )
            except Exception:
                pass
            trace_info = traceback.format_exc()
            current_app.logger.error("==============")
            current_app.logger.error(
                "cron_do cron_id=%s log_id=%s err=%s",
                cron_id,
                cronpilot_log_id,
                str(e),
            )
            current_app.logger.error(trace_info)
            current_app.logger.error("==============")
            wechat_info_err(
                '定时任务发生严重错误',
                'log_id:%s 返回信息:%s' % (cronpilot_log_id, str(e)),
            )

    return saved_jl.id if saved_jl else None

@single_task()
def cron_check():
    with scheduler.app.app_context():
        try:
            def dbs():
                url = current_app.config.get('CRON_DB_URL')
                db = records.Database(url)
                db = db.get_connection()  # 新加
                return db

            job_db = dbs()
            job_arr = []
            jobs = job_db.query("select id from apscheduler_jobs").all()
            if jobs:
                for item in jobs:
                    job_arr.append(item.id)

            cifs = db.session.scalars(select(CronInfos)).all()

            if cifs:
                for item in cifs:
                    if "cron_%s" % item.id not in job_arr:
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
        except Exception as e:
            db.session.rollback()
            trace_info = traceback.format_exc()
            current_app.logger.error("==============")
            current_app.logger.error(str(e))
            current_app.logger.error(trace_info)
            current_app.logger.error("==============")
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
            trace_info = traceback.format_exc()
            current_app.logger.error("==============")
            current_app.logger.error(str(e))
            current_app.logger.error(trace_info)
            current_app.logger.error("==============")
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
            trace_info = traceback.format_exc()
            current_app.logger.error("==============")
            current_app.logger.error(str(e))
            current_app.logger.error(trace_info)
            current_app.logger.error("==============")
    return "ok"