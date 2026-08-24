# -*- coding:utf-8 -*-
from sqlalchemy import asc, desc, distinct, func, select

from datas.model.rbac_user import RbacUser
from datas.model.user_group import UserGroup

from app.repositories.base import BaseRepository


class RbacUserRepository(BaseRepository):
    def paginate_all(self, page_query, username=None, is_active=None):
        # Active users first (desc), then username A-Z
        stmt = select(RbacUser).order_by(desc(RbacUser.is_active), asc(RbacUser.username))
        if username:
            stmt = stmt.where(RbacUser.username.like('%{}%'.format(username)))
        if is_active is not None:
            stmt = stmt.where(RbacUser.is_active == int(is_active))
        return self.paginate(stmt, page_query)

    def paginate_by_groups(self, page_query, group_ids, username=None, is_active=None):
        """按组管理员：仅返回与 group_ids 有交集的用户（不含种子 admin）。"""
        sub = select(distinct(UserGroup.user_id)).where(
            UserGroup.group_id.in_(group_ids)
        ).scalar_subquery()
        stmt = (
            select(RbacUser)
            .where(RbacUser.id.in_(sub))
            .order_by(desc(RbacUser.is_active), asc(RbacUser.username))
        )
        if username:
            stmt = stmt.where(RbacUser.username.like('%{}%'.format(username)))
        if is_active is not None:
            stmt = stmt.where(RbacUser.is_active == int(is_active))
        return self.paginate(stmt, page_query)

    def count_by_status(self, group_ids=None):
        """Return (total, active, inactive) counts, optionally scoped to group_ids."""
        base = select(RbacUser)
        if group_ids is not None:
            sub = select(distinct(UserGroup.user_id)).where(
                UserGroup.group_id.in_(group_ids)
            ).scalar_subquery()
            base = base.where(RbacUser.id.in_(sub))
        total_stmt = select(func.count()).select_from(base.subquery())
        active_stmt = select(func.count()).select_from(
            base.where(RbacUser.is_active == 1).subquery()
        )
        total = self.session.scalar(total_stmt) or 0
        active = self.session.scalar(active_stmt) or 0
        return total, active, total - active
