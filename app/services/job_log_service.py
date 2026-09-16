# -*- coding: utf-8 -*-
"""执行日志保留策略（兼容历史调用点）。"""


def delete_job_logs_for_cron(cron_id):
    """保留执行审计证据：任务下线或维护操作均不得物理删除日志。"""
    return 0


def trim_job_logs_for_cron(cron_info_id, keep_count):
    """兼容旧调用点；自动保留上限已取消，始终不删除生产执行日志。"""
    return 0
