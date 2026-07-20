# -*- coding:utf-8 -*-
"""CronInfos 列表 / 指标 / 侧栏查询（业务 SQL 在此，不进 BaseRepository）。"""
from sqlalchemy import desc, func, select

from datas.model.cron_infos import CronInfos
from datas.model.job_health import JobHealth
from datas.model.job_log import JobLog
from datas.utils.times import get_today

from app.repositories.base import BaseRepository
from app.services.job_health_service import HEALTH_FAILING, get_failing_threshold
from app.services.job_log_outcome import STATUS_ERROR, STATUS_FAIL, STATUS_SUCCESS


class CronRepository(BaseRepository):
    def paginate_list(
        self,
        page_query,
        filters=None,
        health=None,
    ):
        """任务中心主列表。filters 为已组装的 where 子句列表（含 Scope）。"""
        filters = list(filters or [])
        stmt = select(CronInfos)
        health = (health or '').strip().lower()
        if health == 'failing':
            stmt = (
                stmt.join(JobHealth, JobHealth.cron_info_id == CronInfos.id)
                .where(JobHealth.health_status == HEALTH_FAILING)
            )
        elif health == 'today_fail':
            today = get_today()
            today_fail_ids = (
                select(JobLog.cron_info_id)
                .where(JobLog.create_time.like(today + '%'))
                .where(JobLog.status.in_([STATUS_FAIL, STATUS_ERROR]))
                .distinct()
            )
            stmt = stmt.where(CronInfos.id.in_(today_fail_ids))
        if filters:
            stmt = stmt.where(*filters)
        stmt = stmt.order_by(desc(CronInfos.status), desc(CronInfos.task_name))
        return self.paginate(stmt, page_query)

    def metrics(self, base_filters=None, cron_config=None):
        """在已有权限+UI 过滤上统计 Metric。"""
        base_filters = list(base_filters or [])
        total_stmt = select(func.count()).select_from(CronInfos)
        running_stmt = (
            select(func.count())
            .select_from(CronInfos)
            .where(CronInfos.status == 1)
        )
        failing_stmt = (
            select(func.count())
            .select_from(JobHealth)
            .join(CronInfos, CronInfos.id == JobHealth.cron_info_id)
            .where(JobHealth.health_status == HEALTH_FAILING)
        )
        today = get_today()
        today_fail_stmt = (
            select(func.count())
            .select_from(JobLog)
            .join(CronInfos, CronInfos.id == JobLog.cron_info_id)
            .where(JobLog.create_time.like(today + '%'))
            .where(JobLog.status.in_([STATUS_FAIL, STATUS_ERROR]))
        )
        if base_filters:
            total_stmt = total_stmt.where(*base_filters)
            running_stmt = running_stmt.where(*base_filters)
            failing_stmt = failing_stmt.where(*base_filters)
            today_fail_stmt = today_fail_stmt.where(*base_filters)

        total = self.scalar(total_stmt) or 0
        running = self.scalar(running_stmt) or 0
        failing = self.scalar(failing_stmt) or 0
        today_fail = self.scalar(today_fail_stmt) or 0
        return {
            'total': int(total),
            'running': int(running),
            'failing': int(failing),
            'today_fail_runs': int(today_fail),
            'failing_threshold': get_failing_threshold(cron_config),
        }

    def health_by_cron_ids(self, ids):
        if not ids:
            return {}
        health_by_id = {}
        for h in self.scalars_all(
            select(JobHealth).where(JobHealth.cron_info_id.in_(ids))
        ):
            health_by_id[h.cron_info_id] = h
        return health_by_id

    def top_failing(self, filters=None, limit=5):
        filters = list(filters or [])
        stmt = (
            select(CronInfos, JobHealth)
            .join(JobHealth, JobHealth.cron_info_id == CronInfos.id)
            .where(JobHealth.health_status == HEALTH_FAILING)
        )
        if filters:
            stmt = stmt.where(*filters)
        stmt = stmt.order_by(
            desc(JobHealth.consecutive_failures),
            desc(JobHealth.last_fail_at),
        ).limit(limit)
        return self.execute_all(stmt)

    def top_recent_ok(self, filters=None, limit=5):
        filters = list(filters or [])
        stmt = (
            select(CronInfos, JobHealth)
            .join(JobHealth, JobHealth.cron_info_id == CronInfos.id)
            .where(JobHealth.last_run_status == STATUS_SUCCESS)
        )
        if filters:
            stmt = stmt.where(*filters)
        stmt = stmt.order_by(desc(JobHealth.last_run_at)).limit(limit)
        return self.execute_all(stmt)

    def map_by_ids(self, ids):
        if not ids:
            return {}
        by_id = {}
        for cif in self.scalars_all(
            select(CronInfos).where(CronInfos.id.in_(ids))
        ):
            by_id[cif.id] = cif
        return by_id
