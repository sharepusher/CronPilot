# -*- coding:utf-8 -*-
from sqlalchemy import desc, distinct, select

from datas.model.rbac_user import RbacUser
from datas.model.user_group import UserGroup

from app.repositories.base import BaseRepository


class RbacUserRepository(BaseRepository):
    def paginate_all(self, page_query):
        stmt = select(RbacUser).order_by(desc(RbacUser.id))
        return self.paginate(stmt, page_query)

    def paginate_by_groups(self, page_query, group_ids):
        """按组管理员：仅返回与 group_ids 有交集的用户（不含种子 admin）。"""
        sub = select(distinct(UserGroup.user_id)).where(
            UserGroup.group_id.in_(group_ids)
        ).scalar_subquery()
        stmt = (
            select(RbacUser)
            .where(RbacUser.id.in_(sub))
            .order_by(desc(RbacUser.id))
        )
        return self.paginate(stmt, page_query)
