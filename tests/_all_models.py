"""Import all SQLAlchemy models so that db.create_all() creates every table.

Usage in tests:
    import tests._all_models  # noqa: F401
    db.create_all()

This avoids the pitfall where individual test setUp methods only import
a subset of models, causing 'no such table' errors when views or services
query newly added tables.
"""
from datas.model.cron_infos import CronInfos  # noqa: F401
from datas.model.job_health import JobHealth  # noqa: F401
from datas.model.job_log import JobLog  # noqa: F401
from datas.model.job_log_items import JobLogItems  # noqa: F401
from datas.model.operation_log import OperationLog  # noqa: F401
from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
from datas.model.rbac_registration_request import RbacRegistrationRequest  # noqa: F401
from datas.model.rbac_user import RbacUser  # noqa: F401
from datas.model.resource_group import ResourceGroup  # noqa: F401
from datas.model.tag import Tag  # noqa: F401
from datas.model.task_group import TaskGroup  # noqa: F401
from datas.model.task_tag import TaskTag  # noqa: F401
from datas.model.user_group import UserGroup  # noqa: F401
