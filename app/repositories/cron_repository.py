# -*- coding:utf-8 -*-
"""CronInfos 列表 / 指标 / 侧栏查询（业务 SQL 在此，不进 BaseRepository）。"""
from sqlalchemy import desc, func, select

from app.repositories.base import BaseRepository
from app.services.job_health_service import HEALTH_FAILING, get_failing_threshold
from app.services.job_log_outcome import STATUS_ERROR, STATUS_FAIL, STATUS_SUCCESS, STATUS_TIMEOUT
from datas.model.cron_infos import CronInfos
from datas.model.job_health import JobHealth
from datas.model.job_log import JobLog
from datas.utils.times import local_today_start_hms, local_tomorrow_start_hms


class CronRepository(BaseRepository):
    def paginate_list(
        self,
        page_query,
        filters=None,
        health=None,
        overdue_ids=None,
    ):
        """任务中心主列表。filters 为已组装的 where 子句列表（含 Scope）。
        overdue_ids: 预计算的逾期任务 ID 集合，当 health='overdue' 时使用。
        """
        filters = list(filters or [])
        stmt = select(CronInfos)
        health = (health or '').strip().lower()
        if health == 'failing':
            stmt = (
                stmt.join(JobHealth, JobHealth.cron_info_id == CronInfos.id)
                .where(JobHealth.health_status == HEALTH_FAILING)
            )
        elif health == 'today_fail':
            today_fail_ids = (
                select(JobLog.cron_info_id)
                .where(JobLog.create_time >= local_today_start_hms(), JobLog.create_time < local_tomorrow_start_hms())
                .where(JobLog.status.in_([STATUS_FAIL, STATUS_ERROR, STATUS_TIMEOUT]))
                .distinct()
            )
            stmt = stmt.where(CronInfos.id.in_(today_fail_ids))
        elif health == 'overdue' and overdue_ids is not None:
            if overdue_ids:
                stmt = stmt.where(CronInfos.id.in_(list(overdue_ids)))
            else:
                stmt = stmt.where(CronInfos.id == -1)
        if filters:
            stmt = stmt.where(*filters)
        stmt = stmt.order_by(desc(CronInfos.status), desc(CronInfos.task_name))
        return self.paginate(stmt, page_query)

    def metrics(self, base_filters=None, cron_config=None):
        """一次性统计 Dashboard 全部指标（含今日成功率），减少冗余查询。"""
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
            .where(CronInfos.status != -1)
        )
        today_range = [
            JobLog.create_time >= local_today_start_hms(),
            JobLog.create_time < local_tomorrow_start_hms(),
        ]
        today_base = (
            select(func.count())
            .select_from(JobLog)
            .join(CronInfos, CronInfos.id == JobLog.cron_info_id)
            .where(*today_range)
            .where(CronInfos.status != -1)
        )
        today_total_stmt = today_base
        today_fail_stmt = today_base.where(
            JobLog.status.in_([STATUS_FAIL, STATUS_ERROR, STATUS_TIMEOUT])
        )
        today_success_stmt = today_base.where(JobLog.status == STATUS_SUCCESS)
        if base_filters:
            total_stmt = total_stmt.where(*base_filters)
            running_stmt = running_stmt.where(*base_filters)
            failing_stmt = failing_stmt.where(*base_filters)
            today_total_stmt = today_total_stmt.where(*base_filters)
            today_fail_stmt = today_fail_stmt.where(*base_filters)
            today_success_stmt = today_success_stmt.where(*base_filters)

        total = self.scalar(total_stmt) or 0
        running = self.scalar(running_stmt) or 0
        failing = self.scalar(failing_stmt) or 0
        today_total = int(self.scalar(today_total_stmt) or 0)
        today_fail = int(self.scalar(today_fail_stmt) or 0)
        today_success = int(self.scalar(today_success_stmt) or 0)
        today_success_rate = round(today_success / today_total * 100, 1) if today_total > 0 else None
        return {
            'total': int(total),
            'running': int(running),
            'failing': int(failing),
            'today_total_runs': today_total,
            'today_fail_runs': today_fail,
            'today_success_rate': today_success_rate,
            'failing_threshold': get_failing_threshold(cron_config),
        }

    def count_consecutive_failing(self, base_filters=None):
        """连续失败 ≥3 次的任务数（用于 Health-First stats），排除已下线任务。"""
        base_filters = list(base_filters or [])
        stmt = (
            select(func.count())
            .select_from(JobHealth)
            .join(CronInfos, CronInfos.id == JobHealth.cron_info_id)
            .where(JobHealth.consecutive_failures >= 3)
            .where(CronInfos.status != -1)
        )
        if base_filters:
            stmt = stmt.where(*base_filters)
        return int(self.scalar(stmt) or 0)

    def status_counts(self, base_filters=None, running_count=None):
        """每种 status 的任务数（用于 filter chip counts）。

        Args:
            running_count: 如果已从 metrics() 获取，传入以减少 1 条冗余查询。
        """
        base_filters = list(base_filters or [])
        result = {'running': 0, 'paused': 0, 'retired': 0}
        for status_val, key in [(1, 'running'), (0, 'paused'), (-1, 'retired')]:
            if key == 'running' and running_count is not None:
                result[key] = running_count
                continue
            stmt = (
                select(func.count()).select_from(CronInfos)
                .where(CronInfos.status == status_val)
            )
            if base_filters:
                stmt = stmt.where(*base_filters)
            result[key] = int(self.scalar(stmt) or 0)
        return result

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

    def today_success_rate(self, base_filters=None):
        """今日成功率 = 今日成功次数 / 今日总执行次数（排除已下线任务）。"""
        base_filters = list(base_filters or [])
        total_stmt = (
            select(func.count())
            .select_from(JobLog)
            .join(CronInfos, CronInfos.id == JobLog.cron_info_id)
            .where(JobLog.create_time >= local_today_start_hms(), JobLog.create_time < local_tomorrow_start_hms())
            .where(CronInfos.status != -1)
        )
        success_stmt = (
            select(func.count())
            .select_from(JobLog)
            .join(CronInfos, CronInfos.id == JobLog.cron_info_id)
            .where(JobLog.create_time >= local_today_start_hms(), JobLog.create_time < local_tomorrow_start_hms())
            .where(JobLog.status == STATUS_SUCCESS)
            .where(CronInfos.status != -1)
        )
        if base_filters:
            total_stmt = total_stmt.where(*base_filters)
            success_stmt = success_stmt.where(*base_filters)
        total = int(self.scalar(total_stmt) or 0)
        success = int(self.scalar(success_stmt) or 0)
        if total == 0:
            return None
        return round(success / total * 100, 1)

    def last_exec_time_by_ids(self, cron_ids):
        """每个任务最近一条 JobLog 的 create_time（不限 status）。
        返回 {cron_id: 'YYYY-MM-DD HH:MM:SS'}。
        """
        if not cron_ids:
            return {}
        stmt = (
            select(JobLog.cron_info_id, func.max(JobLog.create_time))
            .where(JobLog.cron_info_id.in_(cron_ids))
            .group_by(JobLog.cron_info_id)
        )
        result = {}
        for row in self.execute_all(stmt):
            result[row[0]] = row[1]
        return result

    def last_run_details_by_ids(self, cron_ids):
        """获取每个任务最后一条 JobLog 的 http_status/take_time/fail_reason/create_time。
        返回 {cron_id: {http_status, take_time, fail_reason, create_time, status}}。
        """
        if not cron_ids:
            return {}
        from sqlalchemy import and_
        subq = (
            select(
                JobLog.cron_info_id,
                func.max(JobLog.id).label('max_id'),
            )
            .where(JobLog.cron_info_id.in_(cron_ids))
            .group_by(JobLog.cron_info_id)
            .subquery()
        )
        stmt = (
            select(JobLog)
            .join(subq, and_(
                JobLog.cron_info_id == subq.c.cron_info_id,
                JobLog.id == subq.c.max_id,
            ))
        )
        result = {}
        from datetime import datetime as _dt
        now = _dt.now()
        for log in self.scalars_all(stmt):
            # Format take_time: raw is seconds (float), display as ms/s
            raw_time = getattr(log, 'take_time', None) or 0
            try:
                raw_time = float(raw_time)
            except (TypeError, ValueError):
                raw_time = 0
            if raw_time >= 1:
                take_display = '{:.1f}s'.format(raw_time)
            else:
                take_display = '{}ms'.format(int(raw_time * 1000))

            # Format create_time as relative "X ago"
            raw_ct = getattr(log, 'create_time', None) or ''
            time_ago = ''
            if raw_ct:
                try:
                    if isinstance(raw_ct, str):
                        ct = _dt.strptime(raw_ct, '%Y-%m-%d %H:%M:%S')
                    else:
                        ct = raw_ct
                    delta_sec = int((now - ct).total_seconds())
                    if delta_sec < 0:
                        time_ago = 'just now'
                    elif delta_sec < 60:
                        time_ago = 'just now'
                    elif delta_sec < 3600:
                        time_ago = '{} min ago'.format(delta_sec // 60)
                    elif delta_sec < 86400:
                        time_ago = '{}h ago'.format(delta_sec // 3600)
                    else:
                        time_ago = '{}d ago'.format(delta_sec // 86400)
                except (ValueError, TypeError):
                    time_ago = str(raw_ct)

            result[log.cron_info_id] = {
                'http_status': getattr(log, 'http_status', None) or '—',
                'take_time': take_display,
                'fail_reason': getattr(log, 'fail_reason', None) or '',
                'create_time': time_ago,
                'status': getattr(log, 'status', None) or '',
            }
        return result
