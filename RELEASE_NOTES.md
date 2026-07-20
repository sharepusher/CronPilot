# CronPilot Release Notes

本文档记录 **CronPilot** 版本变更。  
HTML 版：[doc/RELEASE_NOTES.html](doc/RELEASE_NOTES.html)

---

## [Unreleased]

下一版计划见 **[交付状态与路线图](doc/交付状态与路线图.html)**。

**维护约定**：未交付项进入开发时，在本节起草条目；发布时下沉到对应版本节，并同步更新交付状态总览页。

### Tier 3 前置 · 去 `records` 裸 SQL（OPT-P2-11）

- **架构/版本复审（2026-07-17）**：维持 Flask 1.1 + SA 1.4 + gevent 23 + Python 3.8–3.11 稳定栈；不跳级升 Flask 2 / SA 2 / Python 3.12+。
- `CuBackgroundScheduler` / `CuGeventScheduler`：`update_cron_info` 改为 `app_context` + ORM（`apply_retire`），去掉 `records`。
- `cron_check`：经 `app/services/scheduler_db.fetch_apscheduler_job_ids` 读 JobStore（`text()` + 绑定），双库边界不变。
- 从 `requirements.txt` / `requirements-core.txt` 移除 `records==0.5.3`；更新 `THIRD_PARTY_NOTICES.md`。
- 单测：`tests.test_scheduler_db`。
- **未纳入本项**：SQLAlchemy 2.0 / Flask-SQLAlchemy 3.x / Alembic 解锁（挂 Tier 3a pin，须 Flask 2）。

### Phase A · Query Contract / 分页硬门（OPT-P2-11）

- 新增 `app/services/pagination.py`：`PageQuery`、`PaginationResult`、`paginate_select`（与 FSA `Pagination` 解耦，模板 `admin_page.html` 零改动）。
- 管理端 7 处列表迁移：`rbac/users`、`rbac/audit-logs`、`job_log_list`、`job_log_all_list`、`operation_log_list`、`cron_list`（含 health 过滤、metrics、sidebar）。
- `app/main/views.py` 与 `app/rbac/views.py` 内无 `.paginate(`、无列表路径 `session.query`。
- 单测：`tests.test_pagination`（13 例）；全量 `cronpilot.sh test` + `verify_all.sh --local-only` 通过。
- **未纳入本项**：pin bump（SA 2 / FSA 3）、`BaseRepository`（Phase B）、AST Legacy 门禁（Phase C）。见 DEC-007。

### Phase C · ORM Legacy AST 门禁（OPT-P2-11）

- 新增 `tests/test_orm_legacy_guard.py`：AST 扫描 `app/**/*.py`，禁止 L1 `Model.query`、L2 `session.query`、L3 `.paginate`（允许 `paginate_select`）；Allowlist 空。
- 挂载：`scripts/cronpilot.sh test`；CI `unit-tests.yml` 追加本 guard 与 `tests.test_ajax_form_guard`（C-CI-A）。
- 设计稿：[Phase C · ORM Legacy AST 门禁](doc/PhaseC-ORM-Legacy-AST门禁设计.html)。
- **未纳入本项**：C-CI-B（CI 全量 `cronpilot.sh test`）、Phase B Repo、Phase D pin bump。

### Phase B · 薄 BaseRepository（OPT-P2-11）

- 新增 `app/repositories/`：`BaseRepository`（会话原语 + `paginate` 委托 `paginate_select`，默认不 commit）及具体 Repo：`CronRepository`、`JobLogRepository`、`OperationLogRepository`、`RbacUserRepository`、`RbacAuditLogRepository`。
- 管理端 7 处列表与 cron 指标/侧栏查询迁出 `main/views` / `rbac/views`；views 仅解析请求与 Scope，调用具名 Repo 方法。
- 门禁：`tests.test_repositories_phase_b`（views 不得直接 `paginate_select`）；AST L3 收窄为仅拦 `Query.paginate`（允许 `self.paginate` / Repo.paginate）。
- **未纳入本项**：写路径全面迁 Repo（`cron_service` / `rbac/services` 仍负责 commit）；pin bump（Phase D）。

---

## [2.0.0] — 2026-07-17 · 任务中心、触发 GET/POST、账户生命周期

任务中心规模化 IA、触发请求支持 POST JSON Body、强制改密与用户启停缘由等。升级须跑 `ensure_business_tables`（**SQLite / MySQL** 补列）并**重启**。

### Schema（SQLite / MySQL）

| 对象 | 变更 | 说明 |
|------|------|------|
| `job_health` | 新表（`create_all`） | 连续失败 / 最近结果等健康快照 |
| `cron_infos` | `last_operator_name` / `last_operated_at` | 最近发布人与时间 |
| `cron_infos` | `req_method` / `req_body` | 触发请求 GET/POST；POST JSON Body（MySQL 补列 `req_body` 无 DEFAULT） |
| `rbac_users` | `must_reset_password` / `status_reason` | 强制改密标记；启停缘由 |
| 配置 | `health_failing_threshold`（默认 3） | 连续失败≥N 视为「连续失败」 |

其它方言打印 `SKIP`，需自行维护 schema。

### 触发请求：GET / POST（JSON Body）

- 任务可配置 `req_method=GET|POST`（默认 GET，兼容既有任务）。
- **GET**：与既有行为一致，query 附加 `cronpilot_log_id` / `cronpilot_sign`。
- **POST**：`Content-Type: application/json`；以配置的 `req_body`（JSON 对象）为基，再注入 `cronpilot_log_id` / `cronpilot_sign`（**不覆盖**用户已写同名字段）；可空 body。
- Web 添加/编辑：触发 URL 旁选择方法；选 POST 时展示 Body 文本框。API `/api/cron` 亦可传 `req_method` / `req_body`（经同一校验）。
- 升级：`ensure_business_tables` 对 SQLite/MySQL 补列；现有任务默认 GET。

### 任务中心与规模化 IA（OPT-P2-13）

- **导航**：「任务列表」→「任务中心」。
- **五列布局**：任务（健康圆点 + 名称/说明/URL）· 调度策略（人类可读 + Cron 原式）· 运行与发布（最近执行 / 最近发布）· 运行状态 · 操作。
- **工具栏**：连续失败 / 今日失败 / 运行中 / 已暂停 / 全部 + 业务组 Scope + 任务名搜索；Metric 四格与异常榜/最近成功**暂不展示**（后端仍可算，过滤走工具栏）。
- **操作**：平铺「运行记录」「立即执行」（仅运行中 + `cron:write` + 有 URL）；启停 / 编辑 / 下线收入「更多 ▾」；无下线权项灰色且前端拦截（`js-retire-denied`）。
- **OPT-P1-04（列表侧）**：`/cron_run_now` + 列表确认后立即触发（独立详情页 OPT-P1-03 仍未交付）。
- **OPT-P1-01c**：执行记录 `outcome` 筛选；全局默认「非成功」。
- **表单**：默认定时模式；「触发 URL」；空调度不可发布；重名返回 `field=task_name` 并聚焦；编辑暂停任务默认保持暂停（勾选「保存后启动」才恢复）。
- **操作记录**：筛选/列「渠道」改为「业务组」（`scope_view` / `group_id`）。

### 账号与用户管理

- **业务组保存修复**：`set_user_groups` 改为增量增删，避免同次 flush 触发 `(user_id, group_id)` 唯一约束冲突。
- **强制首次改密**：新建用户默认密码 `changeme` + `must_reset_password=1`；须改密成功后方可继续；管理员不可代设密码，仅可**触发重置**（恢复 `changeme` + 强制改密）；不可重置自己；现有用户补列默认不强制。
- **用户列表**：重置密码 / 停用·恢复（须填缘由 → `status_reason`）/ 编辑（末位 info）；停用与待重置行底色区分；当前用户不可经用户管理编辑自己，列表仅「修改密码」。
- **登录会话（现状）**：Flask signed cookie；**无**闲置/绝对超时自动登出；关闭浏览器后会话 Cookie 通常失效；退出与改密成功会 `session.clear()`。详 [RBAC §4.6](doc/RBAC架构设计方案.html#account-session)。
- **账户体系可优化（未排期）**：可配置会话超时、「记住登录」、会话吊销、忘记密码、密码策略增强、系统/业务管理员用户管理边界（待产品确认）、MFA/OAuth（远期）。

### 本版明确不纳入

- 系统管理员 vs 业务管理员的用户管理权限拆分（需求理解偏差，**已终止**，policy 仍统一 `user:manage`）。
- 登录闲置超时自动退出（见上「可优化」；本版不实现）。
- OPT-P1-03 独立执行详情页；Metric 条 / 异常榜 UI；API Scope 隔离（S6）。

---

## [1.2.0] — 2026-07-15 · 顶栏身份、种子权限收窄、启停用语

管理端身份可见性与种子运维边界；任务启停文案统一。升级须**重启**（模板 / policy）。

### 管理端顶栏：登录用户信息

| 变更 | 说明 |
|------|------|
| 位置 | `admin_base.html` 全局 `{% block topbar %}`（`rbac/_topbar.html`）；与 `nav-tabs` 分层 |
| 展示 | 右侧聚焦：用户名、角色标签与退出同组；种子 `admin` →「系统管理员」，其它 admin →「业务管理员」，`operator` / `viewer` 顶栏直接显示英文角色码；非 admin 另示业务组或「未分配业务组」；角色标签用橙/蓝/青/绿语义色 |
| 数据 | `current_user_groups` 由 `session['group_ids']` 解析组名（与授权同源；组变更须重新登录） |
| 退出 | 顶栏统一指向 `/rbac/logout`（写审计）；导航 tab 移除重复「退出」；「修改密码」仍在导航 |

### 种子账号 `admin` 权限收窄

| 变更 | 说明 |
|------|------|
| 种子 | 用户名固定 `admin`：保留 `user:manage` + 只读（`cron:read` / `log:read` / `operation:read` / `audit:read`）与 Scope 绕过 |
| 禁止 | 种子无 `cron:write` / `cron:retire`（不可添加/编辑/启动暂停/下线任务） |
| 运维 | 任务操作须由种子创建的其它 **admin 角色**用户（业务管理员）执行（非第四角色） |

### 操作记录用语：启动 / 暂停

| 变更 | 说明 |
|------|------|
| 操作记录 | `toggle_status` 展示为 **启动任务** 或 **暂停任务**（依 `status` 新旧值）；详情如「启动：已暂停 → 运行中」 |
| 任务列表 | 操作链文案「运行」改为「启动」，与「暂停」对称 |
| 接口提示 | 成功返回「已启动」/「已暂停」；下线任务提示「不能启动或暂停」 |
| 筛选 | 操作类型筛选项为「启动/暂停」（仍对应库内 `action=toggle_status`） |

### 任务列表「下线」入口可见性

| 变更 | 说明 |
|------|------|
| 展示 | 未下线任务对所有登录角色显示「下线」 |
| 权限 | 仅具备 `cron:retire` 的账号可进入下线表单并执行（业务管理员；种子 `admin` 无此权限） |
| 无下线权限 | 点击弹出提示「权限不足：当前账号不可下线任务」，**不发起**下线请求；直达 `/cron_retire` 仍为 403 |

---

## [1.1.0] — 2026-07-14 · Resource Scope、自助改密、编辑页精简

在 v1.0.0 RBAC 之上交付 **OPT-P2-12 资源隔离**，并完善账号自助与任务编辑体验。升级须**重启**。

| 库 | 升级动作 |
|----|----------|
| **SQLite / MySQL** | 部署启动时 `ensure_business_tables.py`（`run_production.sh` / `cronpilot.sh start` 会调用）：`create_all` 建缺失表（含 `resource_groups` / `user_groups`），并对已有 `cron_infos` / `job_log` 按需 `ALTER` 补列。旧名 `ensure_sqlite_tables.*` 仍转发到新脚本 |
| 其它方言 | 打印 `SKIP`；需自行维护 schema |

前提：MySQL 库与账号已存在且 `cron_db_url` 可连；脚本**不会**删表或改已有列类型。手写 DDL（设计 §十）仍作备用。

脚本已更名为 **`ensure_business_tables`**（旧名 `ensure_sqlite_tables` 仍转发）。

### OPT-P2-12 · Resource Scope 资源隔离

在 RBAC v4 Capability 之上增加 Visibility 层：业务组（`resource_groups` / `user_groups`）、任务 `scope_type`/`group_id`、列表过滤 + 单资源 `authorize` 防 IDOR；`admin` 绕过 Scope；组管理复用 `user:manage`。

| 变更 | 说明 |
|------|------|
| 数据 | `resource_groups`、`user_groups`；`cron_infos.scope_type`（默认 GLOBAL）/ `group_id`；SQLite/MySQL 均由 `ensure_business_tables` 自动建表补列（§十 DDL 备用） |
| 鉴权 | `app/rbac/scope.py`、`authorize.py`；登录写 `session['group_ids']`；越权 403 + `scope:deny` |
| 管理端 | `/rbac/groups*`（组编码由名称自动生成）；用户绑组（非 admin 至少一组）；**任务添加**时可设作用域；执行日志/操作记录继承可见性 |
| 非 admin 任务 | 强制 `GROUP`、仅可选本人所属组；不可设 GLOBAL |
| API | **未改**：部署级 `api_access_token` 仍全库（已知缺口，见设计 §七；S6 远期） |
| 测试 | `tests/test_rbac_scope.py` 并入 `cronpilot.sh test` |

设计：[doc/资源隔离与Scope设计.html](doc/资源隔离与Scope设计.html) · [doc/资源隔离落地路线.html](doc/资源隔离落地路线.html)

### 自助修改密码

| 变更 | 说明 |
|------|------|
| 入口 | 导航 **修改密码** → `/rbac/password`（任意已登录角色；不需 `user:manage`） |
| 校验 | 当前密码正确；新密码 ≥6 位且与旧密码不同；确认一致 |
| 会话 | 成功后 **清空会话**，跳转登录页提示「密码已修改，请重新登录」 |
| 审计 | `user:password` |
| 代改 | v1.1.0：admin 可通过「用户管理 → 编辑 → 新密码」改他人密码（**不**强制对方下线）。**v2.0.0 起**改为仅「触发密码重置」（见 [2.0.0](#200)），本节保留发版当时行为说明 |
| 种子 | `login_pwd` 仅空表种子；有用户后改 conf **无效** |

### 任务编辑页精简

| 变更 | 说明 |
|------|------|
| 导航 | 编辑页显示 **任务编辑**（不再误高亮「任务添加」） |
| 表单 | 不展示创建时间、上次编辑、作用域/可见范围 |
| 作用域 | 保存时保持原值；仅在「任务添加」时设置 |

---

## [1.0.0] — 2026-07-14 · 重大版本：多用户 RBAC、任务生命周期、操作审计

首个 **1.x** 里程碑：交付 **OPT-P2-10 RBAC v4**（三角色始终分权、用户管理/审计）、**OPT-P1-09 `operation_log`**、**LIFECYCLE-1/2**、**log_id 必填**、**404 友好页**。升级须重启；登录为用户名+密码（空表种子 `admin`）。

### OPT-P2-10 · RBAC v4

| 阶段 | 状态 | 交付摘要 |
|------|------|----------|
| 1 数据层 | ✅ | `rbac_users` / `rbac_audit_logs`；`ensure_business_tables`（当时名 `ensure_sqlite_tables`）建表 + 种子 |
| 2 RBAC 核心 | ✅ | `app/rbac/`：policy、services、`make_has_perm`、`require_permission` |
| 2.5 登录身份 | ✅ | `/rbac/login`；用户名+密码必填；空表种子 `admin`（密码=`login_pwd`）；**无** `legacy_admin` |
| 3 导航迁移 | ✅ | `rbac/_nav.html` + `has_perm` 菜单裁剪 |
| 4+5 权限 | ✅ | `@require_permission`；**无删除**；`cron:retire` |
| 6a 用户管理 | ✅ | `/rbac/users*`；最后一名 admin / 禁停用自己；Ajax 表单门禁 |
| 6b 审计列表 | ✅ | `/rbac/audit-logs`；中文动作/用户 ID 列 |
| 7 验收 | ✅ | 三角色真实登录矩阵单测 `TestRbacTriangularAcceptance` |

设计说明：[doc/RBAC架构设计方案.html](doc/RBAC架构设计方案.html) · [doc/RBAC落地路线.html](doc/RBAC落地路线.html)

| 变更 | 说明 |
|------|------|
| 登录 / 密码 | 用户名+密码必填；空表种子 `admin`（初始=`login_pwd`）；日常改密：**用户管理 → 编辑 → 新密码**；有用户后改 `login_pwd` **无效**；无忘记密码 / 无 `legacy_admin` |
| 默认行为 | 三角色分权**始终启用**；登录须 `rbac_users`；空表种子 `admin` |
| 分权 | 三角色**始终启用**；已移除旁路开关 `rbac_enable` |
| 登录入口 | `/rbac/login`；`/check_pass` 仅转发；冒烟 `username=admin&password=…` |
| 未登录跳转 | 仅受保护路由；`/docs/*`、`/api/*` 独立 |
| `cron:write` / `cron:retire` / `operation:read` / `audit:read` | 写=启动/暂停/编辑；下线仅 admin；操作记录 operator+admin；RBAC 审计仅 admin；**废弃** delete |
| 测试 | `tests/test_rbac_phase.py`、`tests/test_ajax_form_guard.py` 并入 `cronpilot.sh test` |

### RBAC 6a · `/rbac/users`

| 变更 | 说明 |
|------|------|
| 路由 | 列表 / 添加 / 编辑；`user:manage`；编辑页「新密码」留空不改 |
| 安全 | 无物理删除；禁停用自己与最后一名启用中 admin |
| 表单 | `js-ajax-submit`；非 Ajax 成功 302 |
| 防再发 | `test_ajax_form_guard`；去掉空壳 `js-ajax-form` |

### RBAC 6b · `/rbac/audit-logs`

| 变更 | 说明 |
|------|------|
| 路由 | 只读分页；`audit:read` |
| 展示 | 用户 ID 独立列；动作/结果中文；说明列可读文案 |
| 分工 | ≠ OPT-P1-09 `operation_log`（业务配置变更见「操作记录」） |

### OPT-P1-09 · 管理操作审计 `operation_log`

| 变更 | 说明 |
|------|------|
| 表 | `operation_log`（业务库）；`ensure_business_tables` 自动建表（当时脚本名 `ensure_sqlite_tables`） |
| 写入 | `create_cron` / `update_cron` / `toggle_status` / `retire_cron`（Web + API）；系统对账下线 |
| 操作人 | Web=`user`（Session）；API=`api_client`；无请求=`system`；角色/权限快照 JSON |
| 管理页 | `/operation_log_list`；权限 `operation:read`（operator+admin）；与 RBAC「审计」`audit:read`（仅 admin）分权分表 |
| 保留 | `operation_log_counts`（默认 5000）；`cron_del_operation_log` 每 8 小时裁剪 |
| 测试 | `tests/test_operation_log.py` 并入 `cronpilot.sh test` |

### 任务生命周期 · 无删除

| 变更 | 说明 |
|------|------|
| 暂停 vs 下线 | `status=0` 可恢复；`status=-1` 不可逆终点 |
| 无人工删除 | 旧删除路由 410；同类需求新建 |
| 设计 | [任务生命周期与无删除](doc/任务生命周期与无删除设计.html) |

### LIFECYCLE-2 · 元数据与下线可追溯

| 变更 | 说明 |
|------|------|
| `task_keyword` | 新建/编辑必填，VARCHAR(500) |
| `created_at` / `updated_at` | 创建一次；仅配置编辑刷新 updated |
| `retire_reason` / `retired_at` | 人工必填；系统固定文案；无 `retired_by` |
| 设计 | [生命周期 §四](doc/任务生命周期与无删除设计.html#lifecycle-2) |

### 管理端 · 404 友好页（R2.5）

| 变更 | 说明 |
|------|------|
| `errors/404*.html` | 登录态/访客分流；HTTP 404 |
| `smoke_http_not_found` | 黄金路径断言；改错误页后须重启 |

### 执行记录 log_id 必填

| 变更 | 说明 |
|------|------|
| `cron_do` / `_save_job_log` | 每次执行必有 `job_log.log_id`（UUID） |

### 升级说明（自 v0.2.0）

1. 安装/重启：`bash scripts/cronpilot.sh restart`（模板与鉴权变更须重启）。
2. Web 登录改为 **用户名 + 密码**；空库自动种子 `admin`（密码=`login_pwd`）。
3. **`login_pwd` 仅用于种子**：表已有用户后改 conf 并重启不会改登录密码；日常改密 → **用户管理 → 编辑 → 新密码**。
4. 三角色分权始终启用（已无 `rbac_enable` 旁路）。
5. 可选：`operation_log_counts=5000`（未配置时默认 5000）。
6. 验证：`bash scripts/cronpilot.sh test`；`bash scripts/verify_golden_path.sh`。

---

## [0.2.0] — 2026-06-10 · P1 可观测、依赖 Tier 0–2、管理端 UI

在 v0.1.1 基础上交付 **P1 可观测（OPT-P1-01/02）**、**管理端 UI（A′+B1、OPT-P1-07）**、**依赖升级 Tier 0 / Tier 1 / Tier 2（RFC-2.1～2.5）** 与侧车安全补丁。**无 API 协议变更**（仍为 `cronpilot_log_id` / `cronpilot_sign` / `add_log`）。

### 版本摘要

| 类别 | 已交付 |
|------|--------|
| **P1 可观测** | `job_log.status` / `fail_reason`；`fail_on_http_4xx_5xx`；列表状态徽章 |
| **管理端 UI** | 执行记录 A′（单列两行 + 查看详情）；Cron 分钟 B1 提示；`_admin_nav.html` 五 Tab 导航 |
| **依赖 Tier 0** | `flask db` 替代 Flask-Script |
| **依赖 Tier 1** | SQLAlchemy 1.4.52 + Flask-SQLAlchemy 2.5.1；`Model.query` 全站迁移 |
| **依赖 Tier 2** | gevent 23.9.1、gunicorn 22.0.0、APScheduler 3.10.4；Docker **Python 3.10**；install-full CI matrix 3.9–3.11 |
| **侧车** | requests/urllib3/certifi 安全线；PyMySQL 1.1.2 |
| **Docker 运维** | `verify_docker_compose.sh` 黄金路径；`check_conf_production.py` 拒绝 `:memory:`；SQLite conf 生成指引 |

### 升级说明（自 v0.1.1）

1. `bash scripts/cronpilot.sh install` 或 `pip install -r requirements.txt`（依赖版本见上表）。
2. **Docker**：`docker compose build --no-cache && docker compose up -d`（镜像 Python **3.9 → 3.10**）。
3. **conf.ini**：勿用 `conf.ci.ini` 挂载生产；试用请 `python3 scripts/write_sqlite_conf.py --out conf.ini --datas-dir datas --container-paths`。
4. 已有库：启动时 `ensure_business_tables.py`（当时名 `ensure_sqlite_tables.py`）补 `http_status`、`status`、`fail_reason` 列。
5. 新配置项：`fail_on_http_4xx_5xx=1`（见 `conf.ini.example`）。
6. 验证：`bash scripts/cronpilot.sh test`；Docker 建议 `bash scripts/verify_docker_compose.sh`。


| 变更 | 说明 |
|------|------|
| 执行记录列表 | 「返回的内容」一格两行：① HTTP 状态/异常 ② 响应正文截断；**不加新列** |
| 查看详情 | 替代原「更详细的执行记录」；弹窗展示 `job_log` 完整 HTTP 响应/异常（非空白 add_log 表） |
| `job_log.http_status` | `cron_do` 成功时写入状态码；已有库经 `ensure_business_tables.py` ALTER 补列（当时名 `ensure_sqlite_tables.py`）；**不新增索引** |
| Cron 分钟提示 B1 | 添加/编辑任务页分钟字段行尾灰字：`*/1` = 每分钟，`1` = 每小时第 1 分 |
| 测试 | `tests/test_job_log_display.py` 并入 `bash scripts/cronpilot.sh test` |

设计说明：[doc/管理端UI优化设计.html](doc/管理端UI优化设计.html)

### 管理端 UI · OPT-P1-07 导航栏 partial

| 变更 | 说明 |
|------|------|
| `_admin_nav.html` | 统一 5 项 Tab：任务列表 / 任务添加 / 任务执行记录 / API文档 / 退出 |
| 修复 | `cron_add`、`cron_edit` 此前仅 2 项导航，进入添加页后其余 Tab 消失 |
| 引用页 | `cron_list`、`cron_add`、`cron_edit`、`job_log_all_list`、`api_doc` |

设计说明：[doc/产品优化需求-借鉴Plombery.html#opt-p1-07](doc/产品优化需求-借鉴Plombery.html) · [doc/技术方案与前端设计.html](doc/技术方案与前端设计.html)

### P1 可观测 · OPT-P1-01/02（执行 status + HTTP 失败规则）

| 变更 | 说明 |
|------|------|
| `job_log.status` | `success` / `fail` / `error`；`cron_do` 综合判定后写入 |
| `job_log.fail_reason` | 短标签：`http_5xx`、`keyword`、`timeout` 等 |
| `fail_on_http_4xx_5xx` | `conf.ini` 默认 `1`；4xx/5xx 记 fail 并走统一告警 |
| UI | A′ 列表第一行增加状态徽章；详情页展示 `fail_reason` |
| 测试 | `tests/test_job_log_outcome.py` 并入 `bash scripts/cronpilot.sh test` |

设计说明：[doc/P1可观测优化设计.html](doc/P1可观测优化设计.html)

### 依赖升级 · Tier 0

| 变更 | 说明 |
|------|------|
| 退役 Flask-Script | `manage.py` 改用 Flask 内置 `flask db`（Click 注册 Migrate 子命令） |
| `requirements.txt` | 移除 `Flask-Script==2.0.6` |
| `requirements-core.txt` | 增加 `Flask-Migrate`、`alembic==1.4.3` 等迁移依赖 |

用法：

```bash
export FLASK_APP=manage:app
flask db migrate -m "描述"
flask db upgrade
```

试用配置可 `cp conf.ci.ini conf.ini`（SQLite 内存库，仅单测）；本地试用见 `conf.local.sqlite.example`。

### 依赖升级 · Tier 1

| 变更 | 说明 |
|------|------|
| SQLAlchemy 1.3.19 → **1.4.52** | 过渡版；全站 `Model.query` 已迁移为 SA 1.4 推荐写法 |
| Flask-SQLAlchemy 2.4.4 → **2.5.1** | SA 1.4 兼容（2.4.x 与 1.4 URL API 不兼容） |
| `config.py` | `SQLALCHEMY_ENGINE_OPTIONS = {'future': False}` |
| `app/crons.py` | `execute(text(...))`；`session.get` / `scalars(select(...))` |
| `app/services/job_log_service.py` 等 | `delete()` / `scalars()` 替代 `Model.query` |
| Docker 验收 | `write_sqlite_conf.py --container-paths`；`reset_datas_sqlite.sh` 仅清 `*.sqlite` |

**SA 1.4 查询改写 backlog：**

| 模块 | 模式 | 优先级 |
|------|------|--------|
| `app/crons.py` | 裸 `execute` 字符串 | ✅ Tier 1 已改 |
| `app/crons.py` | `Model.query`（`cron_check`/`cron_del_job_log` 等） | ✅ Tier 1 已改 |
| `app/services/job_log_service.py` | `Model.query` | ✅ Tier 1 已改 |
| `app/main/views.py` | `Model.query` / `paginate` | ✅ Tier 1 已改 |
| `app/services/cron_service.py` | `Model.query` | ✅ Tier 1 已改 |
| `app/api/views.py` | `Model.query` | ✅ Tier 1 已改 |
| `app/crons.py` / `CuBackgroundScheduler.py` | `records` 裸 SQL | Tier 3 与 SQL 整改一并 |

新代码（RBAC、operation_log）禁止新增裸字符串 `execute`。

### 依赖升级 · Tier 2（RFC-2.1 ✓ · RFC-2.2 ✓ · RFC-2.3 ✓ · RFC-2.4 ✓ · RFC-2.5 ✓）

**Tier 2 已全部交付**（gevent / gunicorn / APScheduler / Docker Py 3.10 / CI matrix）；Python **3.8–3.11** 规则经 RFC-2.5 签收仍有效，3.12+ 待 Tier 3+ 评估。

| 变更 | 说明 |
|------|------|
| `gevent` 20.9.0 → **23.9.1** | 支持 Python 3.8–3.11；Docker 金路径（Py 3.10 + gunicorn gevent worker）已验收 |
| `greenlet` 0.4.17 → **3.1.1** | 与 gevent 23 配套；修复 Py 3.11 `SystemError` 类问题 |
| `gunicorn` 20.0.4 → **22.0.0** | gevent worker 冒烟通过；Docker 金路径（`verify_cronpilot_docker_mac.sh` full）已验收；`gun.py` 无需改动 |
| `APScheduler` 3.6.3 → **3.10.4** | `SQLAlchemyJobStore` + SA 1.4 联调；`CuBackgroundScheduler` 无需改；Docker compose 冒烟通过 |
| `install_production_deps.sh` | 移除 gevent 20 分步安装特例，统一 `pip install -r requirements.txt` |
| **RFC-2.4** Docker **3.10** + `install-full` matrix **3.9 / 3.10 / 3.11** | CI 全量依赖安装 + gevent/gunicorn 导入冒烟 |

### 依赖升级 · 侧车 PyMySQL（RFC-S.2）

| 变更 | 说明 |
|------|------|
| `PyMySQL` 0.10.1 → **1.1.2** | 1.x 维护线末版，兼容 Python 3.8–3.11；SQLAlchemy `mysql+pymysql://` 无需改 URL |
| 验收 | `bash scripts/cronpilot.sh test`；Docker compose 构建与健康检查 |

### 依赖升级 · 侧车 HTTP 安全补丁

| 变更 | 说明 |
|------|------|
| `requests` 2.24.0 → **2.31.0** | 收敛已知 CVE；回归 `cron_do` 回调与 SSRF 校验 |
| `urllib3` 1.25.10 → **1.26.19** | 与 requests 2.31 配套（1.26 末代安全线） |
| `certifi` 2020.6.20 → **2024.8.30** | CA 根证书同步 |

验收：`bash scripts/cronpilot.sh test`、`bash scripts/verify_golden_path.sh`。

---

## [0.1.1] — 2026-06-01 · 文档、部署与多版本 Python

在 v0.1.0 基础上的工程化与运维增强，**无 API 协议变更**。

### 文档与在线访问

| 变更 | 说明 |
|------|------|
| `/docs/` 路由 | Flask 提供 `doc/` 静态 HTML，与管理端同端口远程访问 |
| HTML + Markdown | 各技术文档双格式；`doc/index.md` 索引表 |
| 同步脚本 | `scripts/html_docs_to_markdown.py`（`--check` 供 CI 校验） |
| 非 Docker 部署指南 | `doc/非Docker部署指南.html` / `.md`；README 部署章节 |
| Cursor 规范 | `.cursor/rules/`、`AGENTS.md` 固化协作与实现约定 |

在线示例：`http://<host>:5860/docs/`、`/docs/index.md`

### Python 3.8–3.11 自动匹配

| 变更 | 说明 |
|------|------|
| 自动探测 | `scripts/lib/python.sh`：优先复用 `.venv-py*`，否则按 3.11→3.8 选用 |
| 统一入口 | `scripts/cronpilot.sh`（`start` / `install` / `test` / `check` / `exec`） |
| 核心依赖 | `requirements-core.txt`（本地与单测，含 PyMySQL；无 gevent） |
| 兼容 macOS | 启动脚本兼容 bash 3.2，**默认无需** `export PY=` |

```bash
bash scripts/cronpilot.sh start    # 自动匹配 Python，无需指定版本
bash scripts/cronpilot.sh test
```

生产全量依赖仍用 `requirements.txt`（Gunicorn + gevent）。

### Linux 安装与运行（Ubuntu + CentOS 7/8）

| 脚本 / 文档 | 说明 |
| --- | --- |
| `scripts/install_linux.sh` | 统一入口，自动识别发行版 |
| `scripts/install_ubuntu.sh` / `install_centos.sh` | 分平台一键安装 |
| `scripts/bootstrap_venv.sh` | 自动 `.venv-py*` + 核心依赖 |
| `scripts/install_production_deps.sh` | 同一 venv 安装 Gunicorn + gevent |
| `scripts/run_production.sh` | 生产启动（无需手动 activate） |
| `scripts/docker/verify_all.sh` | Docker 验收 Ubuntu / Rocky8 / CentOS7 |
| [INSTALL.md](../INSTALL.md) | 安装速查（MySQL 生产 / SQLite 试用） |

```bash
sudo bash scripts/install_linux.sh --production
bash scripts/run_production.sh
```

### Docker 安装验收 CI

- 工作流：`.github/workflows/docker-install-verify.yml`
- 矩阵构建验证 venv + gunicorn + `/docs/`（SQLite 试用路径）

### CI（GitHub Actions）

| 工作流 | 说明 |
|--------|------|
| Docs HTML ↔ Markdown sync | PR 校验 `doc/*.md` 与 HTML 一致 |
| Unit tests | 矩阵 **3.8 / 3.9 / 3.10 / 3.11** + `requirements-core.txt` |
| install-full | 矩阵 **3.9 / 3.10 / 3.11** 安装完整 `requirements.txt` 并导入 gevent/gunicorn |
| Docker install verify | 矩阵 Ubuntu / Rocky8 / CentOS7 完整安装 + venv + gunicorn |

### 升级说明（自 v0.1.0）

- 拉取代码后：`bash scripts/cronpilot.sh install` 或 `bash scripts/install_core_deps.sh`
- 修改 `doc/*.html` 后执行：`python scripts/html_docs_to_markdown.py`
- 远程文档：重启 Gunicorn 后访问 `/docs/`

---

## [0.1.0] — 2026-05-29 · Phase A（P0）首发

首个版本：HTTP 定时回调调度、Web/API 管理、P0 安全与质量能力、技术文档与 Apache-2.0 许可。

### 项目定位

- **CronPilot** — 中心化 HTTP 定时回调调度台。
- Web 管理端：**CronPilot 定时调度平台**。
- 回调 HTTP `User-Agent`：`CronPilot`。
- 本地开发：`bash scripts/cronpilot.sh start`（v0.1.1+ 自动匹配 Python）；配置示例：`conf.ini.example`。

### 回调与 API 协议

| 参数 / 接口 | 说明 |
|-------------|------|
| `cronpilot_log_id` | 每次触发生成的执行 UUID（query） |
| `cronpilot_sign` | 回调签名字段（MD5，见 `get_cronpilot_sign`） |
| `POST /api/cron/add_log` | 长任务进度回传，必传 `cronpilot_log_id`、`content` |

**回调示例：**

```http
GET https://your-service/callback?cronpilot_log_id=<UUID>&cronpilot_sign=<MD5>
```

**进度回传：**

```http
POST /api/cron/add_log
cronpilot_log_id=<UUID>&content=...
```

验签：query 参数按 key ASCII 排序，拼接 `key=value&&...&&api_key=` 后 MD5。  
执行记录 UUID 存于 `job_log.log_id`。

---

### Phase A（P0）— 安全与基础质量

#### OPT-P0-01 · SQL 参数化

- 删除定时任务时清理 `job_log`：ORM `JobLog.query.filter(...).delete()`。
- 定时清理超限日志：`trim_job_logs_for_cron()`（ORM），消除 SQL 拼接。
- 新增：`app/services/job_log_service.py`。

#### OPT-P0-02 · 管理端密码哈希

- `app/auth/password.py`：支持明文（兼容）与 `pbkdf2` 哈希。
- `scripts/hash_login_password.py` 生成哈希写入 `login_pwd`。

#### OPT-P0-03 · 回调 URL SSRF 防护

- `app/services/url_security.py`。
- 配置：`block_private_ip`、`url_allow_hosts`、`url_ssrf_observe_only`。
- 保存任务与 `cron_do` 执行前校验。

#### OPT-P0-04 · 统一 JSON 契约

- `json_response()`，`errcode` 为 int。
- 修复 `requests.js` 中 `errcode === 0` 判断。

#### OPT-P0-05 · Cron 校验与任务写入统一

- `cron_validator.py` + `cron_service.py`，Web / API 单一路径。
- 消除 `main/views` 与 `api/views` 重复校验逻辑。

---

### 文档

| 文档 | 说明 |
|------|------|
| `doc/index.html` | 文档索引 |
| `doc/项目总览与技术文档.html` | 项目入口 |
| `doc/架构设计文档.html` | 架构与部署 |
| `doc/详细技术方案.html` | 功能与 API |
| `doc/产品优化需求-借鉴Plombery.html` | P0/P1/P2 PRD |
| `doc/P0测试用例与验收手册.html` | 测试与冒烟 |
| `doc/LICENSE-AUDIT.html` | 许可审计 |

---

### 许可与合规

- **Apache License 2.0**（`LICENSE`、`NOTICE`、`THIRD_PARTY_NOTICES.md`）。
- 详见 [doc/LICENSE-AUDIT.html](doc/LICENSE-AUDIT.html)。

---

### 测试

```bash
bash scripts/cronpilot.sh test
# 或: python -m unittest tests.test_p0_phase_a tests.test_cronpilot_sign -v
```

| 套件 | 说明 |
|------|------|
| `tests/test_p0_phase_a.py` | SSRF、密码、校验、JSON 等 |
| `tests/test_cronpilot_sign.py` | 签名函数 |

---

### 配置（新增项）

```ini
block_private_ip=1
url_allow_hosts=
url_ssrf_observe_only=0
```

示例库名：`cronpilot.sqlite` / 数据库名 `cronpilot`。

---

### 部署说明

- `docker-compose.yml`、`start.sh` 路径示例已按 CronPilot 调整。
- 修改 `conf.ini` 后需重启进程。

---

### 对接检查清单

- [ ] 业务回调读取 `cronpilot_log_id`、`cronpilot_sign` 并验签
- [ ] 进度回传使用 `POST /api/cron/add_log`
- [ ] 生产环境配置 SSRF（建议 `block_private_ip=1`）
- [ ] 管理端密码建议使用 `pbkdf2` 哈希

---

### 已知限制与后续

- **P1**：执行 status、失败规则、详情页、「立即执行」等（见 PRD）。
- **P2**：SSE、图表、OAuth 等。
- 推荐 Python **3.8–3.11**。
- `Dockerfile` 基础镜像待升级 LTS。

---

## 版本规划

| 版本 | 说明 |
|------|------|
| `0.1.0` | Phase A（P0）首发 |
| `0.1.1` | 文档 `/docs/`、Markdown 双格式、多版本 Python 自动匹配、CI |
| **`0.2.0`** | **P1 可观测、UI A′+B1+导航、Tier 0–2、Docker Py 3.10** |
| `1.x` / 后续 | 计划：P1-03/04、OpenAPI、Tier 3 前置等（见交付状态） |
