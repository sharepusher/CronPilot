# -*- coding:utf-8 -*-
from sqlalchemy import desc, or_, select

from app.repositories.base import BaseRepository
from datas.model.rbac_audit_log import RbacAuditLog

# Pseudo-action 'user:manage' expands to all user-management action codes.
_USER_MANAGE_ACTIONS = [
    'user:create', 'user:update', 'user:disable', 'user:enable',
    'user:password', 'user:password_reset',
    'user:register_approve', 'user:register_reject', 'user:register_expire',
]


def _apply_search_filters(stmt, username=None, action=None, status=None,
                           time_from=None, time_to=None):
    """通用搜索过滤：用户名 / 动作 / 结果 / 时间范围。"""
    if username:
        stmt = stmt.where(RbacAuditLog.username.like('%{}%'.format(username)))
    if action == 'user:manage':
        stmt = stmt.where(RbacAuditLog.action.in_(_USER_MANAGE_ACTIONS))
    elif action:
        stmt = stmt.where(RbacAuditLog.action == action)
    if status:
        stmt = stmt.where(RbacAuditLog.status == status)
    if time_from:
        from datas.utils.times import str_to_hms
        stmt = stmt.where(RbacAuditLog.create_time >= str_to_hms(time_from + ' 00:00:00'))
    if time_to:
        from datas.utils.times import str_to_hms
        stmt = stmt.where(RbacAuditLog.create_time <= str_to_hms(time_to + ' 23:59:59'))
    return stmt


class RbacAuditLogRepository(BaseRepository):
    def paginate_all(self, page_query, **search):
        stmt = select(RbacAuditLog).order_by(desc(RbacAuditLog.id))
        stmt = _apply_search_filters(stmt, **search)
        return self.paginate(stmt, page_query)

    def paginate_by_scope(self, page_query, viewer_group_ids, **search):
        """按组管理员：仅展示 actor_group_ids 与 viewer_group_ids 有交集的审计记录。

        存储格式为逗号包围（如 ',1,3,'），使用 LIKE '%,1,%' 精确匹配。
        """
        if not viewer_group_ids:
            stmt = (
                select(RbacAuditLog)
                .where(RbacAuditLog.id < 0)
                .order_by(desc(RbacAuditLog.id))
            )
            return self.paginate(stmt, page_query)

        filters = [
            RbacAuditLog.actor_group_ids.like('%,{},%'.format(int(gid)))
            for gid in viewer_group_ids
        ]
        stmt = (
            select(RbacAuditLog)
            .where(or_(*filters))
            .order_by(desc(RbacAuditLog.id))
        )
        stmt = _apply_search_filters(stmt, **search)
        return self.paginate(stmt, page_query)
