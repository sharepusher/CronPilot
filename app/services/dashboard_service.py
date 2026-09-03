# -*- coding: utf-8 -*-
"""Dashboard 统计指标计算服务。

职责：
- 基于 scope_filters 计算全局统计（不含 UI 展示过滤）
- 计算当前页任务的运行详情（last_run, next_run, overdue_map）
- 管理逾期缓存生命周期

设计文档：doc/design/DashboardService提取重构设计.html
"""
import time as _time
from collections import namedtuple
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import load_only

from datas.model.cron_infos import CronInfos
from datas.model.job_health import JobHealth

_overdue_cache = {}
_OVERDUE_CACHE_TTL = 30


def _format_relative_time(total_seconds):
    """格式化秒数为相对时间字符串。"""
    if total_seconds < 60:
        return 'in <1 min'
    elif total_seconds < 3600:
        return 'in {} min'.format(total_seconds // 60)
    elif total_seconds < 86400:
        return 'in {}h'.format(total_seconds // 3600)
    else:
        return 'in {}d'.format(total_seconds // 86400)


class DashboardService:
    """Dashboard 统计指标计算服务。

    Usage:
        svc = DashboardService(cron_repository)
        stats = svc.compute_stats(scope_filters, cron_config)
        page_ctx = svc.compute_page_context(page_items)
    """

    def __init__(self, repo):
        self.repo = repo

    def compute_stats(self, scope_filters, cron_config=None):
        """返回 Dashboard 统计卡片数据。

        Args:
            scope_filters: 权限 + 组过滤条件（不含 UI 展示条件）
            cron_config: CRON_CONFIG 字典

        Returns:
            dict: {metrics, consecutive_failing, status_counts,
                   today_success_rate, overdue_count}
        """
        metrics = self.repo.metrics(list(scope_filters), cron_config=cron_config)
        from app.crons import get_orphan_cache
        orphan = get_orphan_cache()
        return {
            'metrics': metrics,
            'consecutive_failing': self.repo.count_consecutive_failing(scope_filters),
            'status_counts': self.repo.status_counts(
                scope_filters, running_count=metrics['running'],
            ),
            'today_success_rate': metrics['today_success_rate'],
            'overdue_count': self.cached_overdue_count(scope_filters),
            'orphan_count': orphan['orphan_count'],
            'orphan_ids': orphan['orphan_ids'],
            'orphan_updated_at': orphan['updated_at'],
        }

    def compute_page_context(self, page_items):
        """返回当前页任务的运行详情。

        Args:
            page_items: 当前页 CronInfos 对象列表

        Returns:
            dict: {last_run_map, next_run_map, overdue_map}
        """
        task_ids = [item.id for item in page_items]
        page_last_exec = self.repo.last_exec_time_by_ids(task_ids)
        return {
            'last_run_map': self.repo.last_run_details_by_ids(task_ids),
            'next_run_map': self.compute_next_runs(page_items),
            'overdue_map': self.compute_overdue_map(page_items, page_last_exec),
        }

    def cached_overdue_count(self, scope_filters):
        """统计卡片用：仅返回逾期计数，缓存 key 基于 scope。"""
        cache_key = ('__stats__',) + tuple(str(f) for f in scope_filters)
        count, _ = self._cached_overdue_stats(cache_key, scope_filters)
        return count

    def overdue_ids_for_list(self, cache_key, filter_arr):
        """列表过滤 health='overdue' 时获取逾期 ID 集合。"""
        _, ids = self._cached_overdue_stats(cache_key, filter_arr)
        return ids

    # ─── 迁移自 views.py 的域逻辑 ─────────────────────────────

    def _cached_overdue_stats(self, cache_key, filter_arr):
        """进程内 TTL 缓存 overdue_count 和 overdue_ids（30s）。

        P2 优化 (B+C)：
        - B: LEFT JOIN job_health 取 last_run_at，消除 last_exec_time_by_ids() 查询
        - C: 仅加载逾期计算所需列（id/run_date/minute/hour/day/day_of_week），
              不实例化完整 ORM 对象
        合并后：2 条 SQL → 1 条 SQL + Python 循环
        """
        now = _time.time()
        if cache_key in _overdue_cache:
            cached_time, cached_result = _overdue_cache[cache_key]
            if now - cached_time < _OVERDUE_CACHE_TTL:
                return cached_result

        _OverdueRow = namedtuple(
            '_OverdueRow', 'id status run_date minute hour day day_of_week last_run_at',
        )
        stmt = (
            select(
                CronInfos.id, CronInfos.status, CronInfos.run_date,
                CronInfos.minute, CronInfos.hour, CronInfos.day,
                CronInfos.day_of_week, JobHealth.last_run_at,
            )
            .outerjoin(JobHealth, JobHealth.cron_info_id == CronInfos.id)
            .where(CronInfos.status == 1)
        )
        if filter_arr:
            stmt = stmt.where(*filter_arr)
        rows = [_OverdueRow(*r) for r in self.repo.execute_all(stmt)]
        last_exec_map = {}
        for r in rows:
            val = r.last_run_at
            if val and val != '0' and val != 0:
                last_exec_map[r.id] = val
        overdue_map_all = self.compute_overdue_map(rows, last_exec_map)
        result = (len(overdue_map_all), set(overdue_map_all.keys()))
        _overdue_cache[cache_key] = (now, result)
        stale = [k for k, (t, _) in _overdue_cache.items() if now - t > _OVERDUE_CACHE_TTL * 3]
        for k in stale:
            del _overdue_cache[k]
        return result

    def compute_next_runs(self, cron_items):
        """用 croniter 计算每个任务的下次执行时间。

        返回 {cron_id: '相对时间字符串'} 如 'in 3 min', 'in 2h'。
        status != 1 的任务返回对应状态文案。
        """
        try:
            from croniter import croniter
        except ImportError:
            return {}
        result = {}
        now = datetime.now()
        for item in cron_items:
            if item.status == 0:
                result[item.id] = '已暂停'
            elif item.status == -1:
                result[item.id] = '已下线'
            else:
                run_date = getattr(item, 'run_date', '') or ''
                if run_date.strip():
                    try:
                        target = datetime.strptime(run_date.strip(), '%Y-%m-%d %H:%M:%S')
                        if target <= now:
                            result[item.id] = '已执行'
                        else:
                            delta = target - now
                            total_seconds = int(delta.total_seconds())
                            result[item.id] = _format_relative_time(total_seconds)
                    except (ValueError, TypeError):
                        result[item.id] = '—'
                    continue
                minute = getattr(item, 'minute', '') or '*'
                hour = getattr(item, 'hour', '') or '*'
                day = getattr(item, 'day', '') or '*'
                day_of_week = getattr(item, 'day_of_week', '') or '*'
                cron_expr = '{} {} {} * {}'.format(
                    minute.strip() or '*',
                    hour.strip() or '*',
                    day.strip() or '*',
                    day_of_week.strip() or '*',
                )
                if cron_expr == '* * * * *':
                    result[item.id] = '—'
                    continue
                try:
                    cron = croniter(cron_expr, now)
                    next_dt = cron.get_next(datetime)
                    delta = next_dt - now
                    total_seconds = int(delta.total_seconds())
                    result[item.id] = _format_relative_time(total_seconds)
                except (ValueError, KeyError):
                    result[item.id] = '—'
        return result

    def compute_overdue_map(self, cron_items, last_exec_map):
        """计算逾期任务。返回 {cron_id: '逾期 Xh'} 字典（仅含逾期任务）。

        逾期 = (now - last_exec) > max(interval * 2, 600s)
        排除：已暂停(0)、已下线(-1)、一次性任务(run_date非空)、无调度表达式
        """
        try:
            from croniter import croniter
        except ImportError:
            return {}
        result = {}
        now = datetime.now()
        for item in cron_items:
            if item.status != 1:
                continue
            run_date = getattr(item, 'run_date', '') or ''
            if run_date.strip():
                continue
            minute = (getattr(item, 'minute', '') or '*').strip() or '*'
            hour = (getattr(item, 'hour', '') or '*').strip() or '*'
            day = (getattr(item, 'day', '') or '*').strip() or '*'
            day_of_week = (getattr(item, 'day_of_week', '') or '*').strip() or '*'
            cron_expr = '{} {} {} * {}'.format(minute, hour, day, day_of_week)
            if cron_expr == '* * * * *':
                continue
            try:
                ci = croniter(cron_expr, now)
                next1 = ci.get_next(datetime)
                next2 = ci.get_next(datetime)
                interval_sec = (next2 - next1).total_seconds()
            except (ValueError, KeyError):
                continue
            threshold = max(interval_sec * 2, 600)
            last_exec_val = last_exec_map.get(item.id)
            if not last_exec_val:
                continue
            try:
                from datas.utils.times import hms_to_datetime, str_to_hms
                if isinstance(last_exec_val, str):
                    last_exec = hms_to_datetime(str_to_hms(last_exec_val))
                elif isinstance(last_exec_val, (int, float)):
                    last_exec = hms_to_datetime(last_exec_val)
                else:
                    last_exec = last_exec_val
                if last_exec is None:
                    continue
                if getattr(last_exec, 'tzinfo', None) is not None:
                    last_exec = last_exec.astimezone().replace(tzinfo=None)
                gap = (now - last_exec).total_seconds()
            except (ValueError, TypeError):
                continue
            if gap > threshold:
                if gap < 3600:
                    label = '逾期 {}min'.format(int(gap // 60))
                elif gap < 86400:
                    label = '逾期 {}h'.format(int(gap // 3600))
                else:
                    label = '逾期 {}d'.format(int(gap // 86400))
                result[item.id] = label
        return result
