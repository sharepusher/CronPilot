# CronPilot · RBAC 架构设计方案 v2（真实代码版）

> HTML 版：[RBAC架构设计方案.html](RBAC架构设计方案.html) · [文档索引](index.html) · [索引 Markdown](index.md)

[← 文档索引](index.html)
安全RBACOPT-P2-10v2

# RBAC 架构设计方案

v2 · 基于 CronPilot 真实源码逆向 · Flask 装饰器 + Blueprint（非 Express 中间件）

**纠错：**v1.0/v1.1 方案误将本仓库当作 Node/Express 项目设计（`init_rbac`、`route_registry`、JWT、`audit_queue` 等**均已废弃**）。v2 全部结论标注真实代码出处，遵循 `.cursor/rules/cronpilot-project.mdc` 的**最小 diff**纪律。

## 变更记录

| 版本 | 日期 | 说明 |
| --- | --- | --- |
| v1.0–v1.1 | — | **废弃**：误判技术栈的中间件 / 四角色 / JWT 方案 |
| **v2** | 2026-06 | 基于 `app/main/views.py`、`app/decorated.py`、`configs.py` 等真实代码重设；三角色 + 装饰器替换 + `rbac_enable` |

## 〇、与误判方案对照

| 维度 | v1.1（废弃） | v2（本方案） |
| --- | --- | --- |
| 载体 | Express / Flask `before_request` 全局中间件 | Flask `@require_permission` 装饰器 + `app/rbac/` Blueprint |
| views 改动 | 声称零修改 | **仅替换装饰器与 import**，函数体不动 |
| 角色 | 4 角色 + `superadmin` | **3 角色**（viewer / operator / admin） |
| 用户模型 | `users` + `roles` + 多表 RBAC | 单表 `rbac_users`（username + role 字段） |
| 配置 | `auth_mode`、JWT、`.env` | `conf.ini` → `rbac_enable=0|1` |
| API | 与 Web 统一 JWT/RBAC | **保持 `access_token` 不变**（外部集成契约） |
| 审计 | `audit_queue` 异步写 `operation_log` | `rbac_audit_logs` 同步写 RBAC 事件；`operation_log` 仍由 P1 管业务变更 |
| 迁移 | 手写 DDL | Flask-Migrate + `flask db`（`manage.py` 已注册 Click 子命令；见 [依赖升级 RFC](依赖升级RFC.html) Tier 0） |

## 一、现状分析（代码出处）

### 1.1 技术栈

| 维度 | 真实值 | 出处 |
| --- | --- | --- |
| Web | Flask 1.1.2，Blueprint：`main` / `api` / `docs` | `app/__init__.py` |
| ORM | SQLAlchemy 1.3 + Flask-SQLAlchemy | `app/__init__.py` |
| 调度 | Flask-APScheduler + `CuBackgroundScheduler` | `app/CuBackgroundScheduler.py` |
| 部署 | gunicorn + gevent；Python **3.8–3.11** | 项目规则 / `requirements.txt` |
| 配置 | `conf.ini` + `configs()` 每次读盘无缓存 | `configs.py` |
| 前端 | Jinja2 SSR + jQuery + Vue（非 SPA） | `app/templates/` |
| JSON 契约 | `{errcode:int, errmsg, result, data, url}` | `datas/utils/json.py` |

### 1.2 现有鉴权（两套独立）

**Web：**单全局密码 `login_pwd` → `session['is_login']=True`；`@login_required` 仅检查 `is_login` 键（`app/decorated.py:37–45`）。

```
# app/main/views.py check_pass()
if not verify_login_password(password, login_pwd):
    return redirect("/check_pass?msg=密码有误")
session['is_login'] = True
```

**API：**各路由内重复 `api_access_token` 字符串比对（`app/api/views.py` 三处），无统一入口、无用户概念。

### 1.3 项目纪律约束

- Phase A（P0）已交付；RBAC 为**需用户明确确认**的新阶段（OPT-P2-10），非默认 scope。
- 最小 diff：不顺手重构；密码走 `verify_login_password` / `hash_password`（`app/auth/password.py`）。
- 测试沿用 `python -m unittest`，不引入 pytest。

## 二、设计原则

1. **解耦**：RBAC 代码集中在新增 Blueprint `app/rbac/`，复用 `app/auth/password.py`。
2. **最小 diff**：`main/views.py` 只替换 `@login_required` → `@require_permission(...)`；函数体逐行保留。
3. **单一校验路径**：权限逻辑仅在 `policy.py` + `decorators.py`，禁止像 `access_token` 那样复制粘贴。
4. **JSON 契约**：新增接口统一 `json_response()` / `web_api_return()`，`errcode` 为 int。
5. **配置体系**：`conf.ini` 的 `rbac_enable`，不用环境变量。
6. **向后兼容**：`rbac_enable=0`（默认）时行为与现网**逐字节一致**。

## 三、角色与权限

### 3.1 三内置角色

| role | 说明 | 典型用户 |
| --- | --- | --- |
| `viewer` | 只读任务与执行日志 | 监控、只读审计 |
| `operator` | 新增/编辑/启停任务；可删日志；**不可删任务、不可管用户** | 开发 / 运维 |
| `admin` | 全部 Web 权限 + 用户管理 + RBAC/业务审计查看 | 团队负责人 |

单密码模式天然等价于唯一 `admin`；`rbac_enable=1` 后由 `rbac_users` 表承载多账号。

### 3.2 权限点（对照真实路由）

| permission | 含义 | 路由（`app/main/views.py`） |
| --- | --- | --- |
| `cron:read` | 查看任务、API 文档 | `/`、`/cron_list`、`/api_doc` |
| `cron:write` | 新增/编辑/启停 | `/cron_add`、`/cron_edit`、`/update_status` |
| `cron:delete` | 删除任务 | `/cron_del`、`/cron_batch_del` |
| `log:read` | 查看执行日志 | `/job_log_list`、`/job_log_item_list`、`/job_log_all_list` |
| `log:delete` | 删除执行日志 | `/job_log_delete`、`/job_batch_delete` |
| `user:manage` | 用户与角色管理 | `/rbac/users*`（新增 Blueprint） |
| `audit:read` | 查看审计 | `/rbac/audit-logs`；`/operation_log_list`（P1，admin） |

### 3.3 角色 → 权限（`app/rbac/policy.py`）

```
ROLE_PERMISSIONS = {
    'viewer':   {'cron:read', 'log:read'},
    'operator': {'cron:read', 'cron:write', 'log:read', 'log:delete'},
    'admin':    {'cron:read', 'cron:write', 'cron:delete',
                 'log:read', 'log:delete', 'user:manage', 'audit:read'},
}

def has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())
```

### 3.4 路由 → 装饰器替换表

| 函数 | 原 | 新 |
| --- | --- | --- |
| `cron_list`、`api_doc` | `@login_required` | `@require_permission('cron:read')` |
| `cron_add`、`cron_edit`、`update_status` | `@login_required` | `@require_permission('cron:write')` |
| `cron_del`、`cron_batch_del` | `@login_required` | `@require_permission('cron:delete')` |
| `job_log_*`（三个 list） | `@login_required` | `@require_permission('log:read')` |
| `job_log_delete`、`job_batch_delete` | `@login_required` | `@require_permission('log:delete')` |
| `check_pass`、`logout` | 无 / 无 | **不改** |

## 四、数据模型

### 4.1 `rbac_users`（`datas/model/rbac_user.py`）

```
class RbacUser(db.Model):
    __tablename__ = 'rbac_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='viewer')
    is_active = db.Column(db.SMALLINT, nullable=False, default=1)
    create_time = db.Column(db.String(25), nullable=False, default='')

    def set_password(self, plain):
        self.password_hash = hash_password(plain)  # app/auth/password.py

    def check_password(self, plain):
        return verify_login_password(plain, self.password_hash)
```

单角色字段（非多表 RBAC），符合轻量自托管定位；零新增密码依赖。

### 4.2 `rbac_audit_logs`（`datas/model/rbac_audit_log.py`）

```
class RbacAuditLog(db.Model):
    __tablename__ = 'rbac_audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True, index=True)
    username = db.Column(db.String(64), default='')
    action = db.Column(db.String(50), nullable=False)   # user:create | permission:deny | ...
    resource = db.Column(db.String(100), default='')
    ip = db.Column(db.String(45), default='')
    status = db.Column(db.String(10), default='allow')  # allow | deny
    create_time = db.Column(db.String(25), nullable=False, default='')
```

### 4.3 与 P1 `operation_log` 分工

| 表 | 职责 | 写入时机 |
| --- | --- | --- |
| `operation_log` | 业务配置变更（增删改任务、启停） | P1：`cron_service` / views 成功后 |
| `rbac_audit_logs` | RBAC 管理、权限拒绝 | `app/rbac/services.write_audit_log` |

RBAC 启用后 Session 增加 `user_id`、`username`、`role`，供 P1 `operation_log` 填充 `operator_*` 快照（`operator_type=user`）。

### 4.4 迁移

```
flask --app manage:app db migrate -m "add rbac_users and rbac_audit_logs"
flask --app manage:app db upgrade
```

迁移 CLI：Flask 原生 `flask db`（`manage.py` 已注册 Click 子命令，Py3.11 可用；**Tier 0 已交付**）。排期见 [依赖升级 RFC](依赖升级RFC.html) §七；CLI 不可用时退化 `ensure_rbac_tables(app)`。

## 五、目录结构

```
app/rbac/                    ← 与 main/api/docs 平级 Blueprint
  ├── __init__.py            url_prefix='/rbac'
  ├── policy.py              ROLE_PERMISSIONS + has_permission
  ├── decorators.py          require_permission / require_role
  ├── services.py            用户 CRUD、write_audit_log、get_rbac_enabled
  └── views.py               /rbac/users、/rbac/audit-logs

datas/model/
  ├── rbac_user.py
  └── rbac_audit_log.py

app/templates/
  ├── rbac_users.html        ← 参照 cron_list 分页风格
  └── rbac_audit_logs.html
```

## 六、关键实现

### 6.1 Blueprint（`app/rbac/__init__.py`）

```
from flask import Blueprint
rbac = Blueprint('rbac', __name__, url_prefix='/rbac')
from . import views  # noqa
```

### 6.2 权限装饰器（`app/rbac/decorators.py`）

```
def require_permission(permission):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if 'is_login' not in session:
                return redirect('/check_pass?msg=需要验证密码')
            if not get_rbac_enabled():
                return func(*args, **kwargs)   # rbac_enable=0：与现网一致

            role = session.get('role', 'admin')
            if not has_permission(role, permission):
                write_audit_log(action='permission:deny', resource=permission, status='deny')
                # Ajax/POST 走 web_api_return；页面 GET 走 redirect
                if request.method == 'POST':
                    return web_api_return(code=1, msg='权限不足')
                return redirect('/cron_list?msg=权限不足')
            return func(*args, **kwargs)
        return wrapper
    return decorator
```

### 6.3 登录写入 Session（`check_pass` 微调）

```
session['is_login'] = True
session['role'] = resolve_role_for_legacy_login(password)
# resolve_role_for_legacy_login:
#   rbac_enable=0 → 'admin'
#   匹配 rbac_users 表 → 对应 role + user_id/username
#   否则仍用 login_pwd 验证通过 → 'admin'（兜底，不锁死旧管理员）
```

### 6.4 API 端（独立轨道，**本次不改**）

`/api/cron`、`/api/cron/status`、`/api/cron/add_log` 保持现有 `access_token` 校验，不并入 Web 角色体系，避免破坏第三方对接。可选远期：多 token 只读范围（非本次 scope）。

### 6.5 入口注册（`app/__init__.py` +2 行）

```
from .rbac import rbac as rbac_blueprint
app.register_blueprint(rbac_blueprint)
```

## 七、配置（`conf.ini`）

```
[default]
; ...现有项不变...
rbac_enable=0   ; 0=单密码全权限（默认） 1=启用三角色
```

`configs.py` 增加容错读取（沿用 `cp.has_option` 模式），写入 `pz['rbac_enable']`。修改后需**重启进程**（与现有配置行为一致）。

## 八、测试（`tests/test_rbac_phase.py`）

- `test_viewer_cannot_write` — `has_permission('viewer','cron:write')` 为 False
- `test_operator_cannot_delete` — 不可 `cron:delete`
- `test_admin_has_all` — admin 具备全部 permission
- `test_legacy_mode_bypasses_check` — `rbac_enable=0` 时不拦截已登录用户

命令：`python -m unittest tests.test_p0_phase_a tests.test_rbac_phase -v`

## 九、实施步骤

1. `flask db` CLI 已就绪（[依赖升级 RFC](依赖升级RFC.html) **Tier 0**）；可与 RBAC 代码并行实施
2. 新增 `rbac_user.py`、`rbac_audit_log.py` → `db migrate` / `upgrade`
3. 新增 `app/rbac/` Blueprint 全套
4. `app/__init__.py` 注册 Blueprint
5. `main/views.py` 按 §3.4 逐路由替换装饰器；每步跑 P0 单测
6. `check_pass` 写入 `session['role']`（及可选 `user_id`）
7. `configs.py` + `conf.ini.example` 增加 `rbac_enable`
8. 新增 `tests/test_rbac_phase.py`
9. `RELEASE_NOTES.md` 记录变更

## 十、验收标准

- `rbac_enable=0`：与现网行为一致；P0 单测全绿。
- `rbac_enable=1`：`viewer` POST `/cron_add` 被拒绝；`operator` 不可 `/cron_del`。
- 用户管理仅 `admin` 可访问 `/rbac/users`。
- 权限拒绝写入 `rbac_audit_logs`（`status=deny`）。
- API `access_token` 行为不变。
- 无新增 pip 依赖。

## 十一、风险与待确认

- 建表：目标环境验证 `flask --app manage:app db migrate` 或 `ensure_rbac_tables`；**不必**等待 gevent / Flask 2 升级（RFC §七）。
- 多用户登录 UX：首期可继续 `check_pass` 单页输入密码匹配 `rbac_users`；远期可加 `/rbac/login` 用户名+密码（非必须）。
- OAuth（OPT-P2-07）为独立后续项，v2 不展开。
- **实施前需用户明确确认**进入 OPT-P2-10 开发（项目路线图纪律）。

CronPilot · RBAC v2 ·
[Markdown](RBAC架构设计方案.md) ·
[架构 §15](架构设计文档.html#rbac-arch) ·
[OPT-P2-10](产品优化需求-借鉴Plombery.html#opt-p2-10) ·
[依赖升级 RFC](依赖升级RFC.html) ·
[索引](index.html)

---

[← 文档索引（HTML）](index.html) · [← 文档索引（Markdown）](index.md)
