# -*- coding:utf-8 -*-
from sqlalchemy import case, desc, false, func, select, union_all

from app.repositories.base import BaseRepository
from datas.model.rbac_registration_request import RbacRegistrationRequest
from datas.model.rbac_registration_request_group import RbacRegistrationRequestGroup


class RegistrationRequestRepository(BaseRepository):
    @staticmethod
    def _scoped_request_ids(group_ids, status=None, search_username=None):
        """构造 scoped actor 可见申请 ID 的角色互斥集合。"""
        request = RbacRegistrationRequest
        if not group_ids:
            return select(request.id.label('id')).where(false())

        relation = RbacRegistrationRequestGroup
        parent_filters = [request.group_ids != '__ALL__']
        if status:
            parent_filters.append(request.status == status)
        if search_username:
            parent_filters.append(
                request.username.ilike('%%%s%%' % search_username)
            )

        viewer_operator_ids = (
            select(relation.registration_request_id.label('id'))
            .select_from(relation)
            .join(request, request.id == relation.registration_request_id)
            .where(relation.group_id.in_(group_ids))
            .where(request.role.in_(['viewer', 'operator']))
            .where(*parent_filters)
            .distinct()
        )

        outside_count = func.sum(case(
            (relation.group_id.not_in(group_ids), 1),
            else_=0,
        ))
        admin_ids = (
            select(relation.registration_request_id.label('id'))
            .select_from(relation)
            .join(request, request.id == relation.registration_request_id)
            .where(request.role == 'admin')
            .where(*parent_filters)
            .group_by(relation.registration_request_id)
            .having(outside_count == 0)
        )
        return union_all(viewer_operator_ids, admin_ids)

    @classmethod
    def _scoped_visibility(cls, group_ids):
        """兼容只接受布尔谓词的审计/编译调用方。"""
        request = RbacRegistrationRequest
        return request.id.in_(cls._scoped_request_ids(group_ids))

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

    def paginate_all(self, page_query, status=None, search_username=None):
        """全量分页（种子/全局 admin）。"""
        stmt = select(RbacRegistrationRequest).order_by(
            desc(RbacRegistrationRequest.id)
        )
        if status:
            stmt = stmt.where(RbacRegistrationRequest.status == status)
        if search_username:
            stmt = stmt.where(
                RbacRegistrationRequest.username.ilike('%%%s%%' % search_username)
            )
        return self.paginate(stmt, page_query)

    def paginate_by_groups(self, page_query, group_ids, status=None, search_username=None):
        """普通申请精确交集、管理员申请非空完整子集。"""
        scoped_ids = self._scoped_request_ids(
            group_ids,
            status=status,
            search_username=search_username,
        ).subquery()
        stmt = select(RbacRegistrationRequest).join(
            scoped_ids,
            scoped_ids.c.id == RbacRegistrationRequest.id,
        ).order_by(
            desc(RbacRegistrationRequest.id)
        )
        if status:
            stmt = stmt.where(RbacRegistrationRequest.status == status)
        if search_username:
            stmt = stmt.where(
                RbacRegistrationRequest.username.ilike('%%%s%%' % search_username)
            )
        return self.paginate(stmt, page_query)

    def get_pending_count_all(self):
        """全局待审批数量。"""
        from sqlalchemy import func
        stmt = select(func.count()).select_from(RbacRegistrationRequest).where(
            RbacRegistrationRequest.status == 'pending'
        )
        return self.session.scalar(stmt) or 0

    def get_pending_count_by_groups(self, group_ids):
        """与列表使用同一授权集合的待审批数量。"""
        scoped_ids = self._scoped_request_ids(
            group_ids,
            status='pending',
        ).subquery()
        stmt = select(func.count()).select_from(RbacRegistrationRequest).join(
            scoped_ids,
            scoped_ids.c.id == RbacRegistrationRequest.id,
        ).where(
            RbacRegistrationRequest.status == 'pending'
        )
        return self.session.scalar(stmt) or 0
