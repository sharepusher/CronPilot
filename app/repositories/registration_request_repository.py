# -*- coding:utf-8 -*-
from sqlalchemy import desc, select

from datas.model.rbac_registration_request import RbacRegistrationRequest

from app.repositories.base import BaseRepository


class RegistrationRequestRepository(BaseRepository):
    def find_pending_by_username(self, username):
        """查找指定用户名的最新 pending 申请。"""
        stmt = (
            select(RbacRegistrationRequest)
            .where(RbacRegistrationRequest.username == username)
            .where(RbacRegistrationRequest.status == 'pending')
            .order_by(desc(RbacRegistrationRequest.id))
        )
        return self.scalars_first(stmt)

    def find_latest_by_username(self, username):
        """查找指定用户名的最新申请（不限状态，用于登录时状态提示）。"""
        stmt = (
            select(RbacRegistrationRequest)
            .where(RbacRegistrationRequest.username == username)
            .where(RbacRegistrationRequest.status.in_(['pending', 'rejected']))
            .order_by(desc(RbacRegistrationRequest.id))
        )
        return self.scalars_first(stmt)

    def paginate_all(self, page_query, status=None):
        """全量分页（种子/全局 admin）。"""
        stmt = select(RbacRegistrationRequest).order_by(
            desc(RbacRegistrationRequest.id)
        )
        if status:
            stmt = stmt.where(RbacRegistrationRequest.status == status)
        return self.paginate(stmt, page_query)

    def paginate_by_groups(self, page_query, group_ids, status=None):
        """按组管理员：仅返回 group_ids 有交集的申请。"""
        stmt = select(RbacRegistrationRequest).order_by(
            desc(RbacRegistrationRequest.id)
        )
        if status:
            stmt = stmt.where(RbacRegistrationRequest.status == status)
        # group_ids 存储为逗号分隔，用 LIKE 匹配交集
        conditions = []
        for gid in group_ids:
            conditions.append(
                RbacRegistrationRequest.group_ids.like('%%%s%%' % str(gid))
            )
        if conditions:
            from sqlalchemy import or_
            stmt = stmt.where(or_(*conditions))
        else:
            # 无组 → 看不到任何申请
            stmt = stmt.where(RbacRegistrationRequest.id < 0)
        return self.paginate(stmt, page_query)

    def get_pending_count_all(self):
        """全局待审批数量。"""
        from sqlalchemy import func
        stmt = select(func.count()).select_from(RbacRegistrationRequest).where(
            RbacRegistrationRequest.status == 'pending'
        )
        return self.session.scalar(stmt) or 0

    def get_pending_count_by_groups(self, group_ids):
        """按组交集的待审批数量。"""
        from sqlalchemy import func, or_
        stmt = select(func.count()).select_from(RbacRegistrationRequest).where(
            RbacRegistrationRequest.status == 'pending'
        )
        conditions = []
        for gid in group_ids:
            conditions.append(
                RbacRegistrationRequest.group_ids.like('%%%s%%' % str(gid))
            )
        if conditions:
            stmt = stmt.where(or_(*conditions))
        else:
            return 0
        return self.session.scalar(stmt) or 0
