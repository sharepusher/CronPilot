# Release Notes · CronPilot

> HTML 版：[RELEASE_NOTES.html](RELEASE_NOTES.html) · [文档索引](index.html) · [索引 Markdown](index.md)

# CronPilot Release Notes

v2.0.0 2026-07-17 · 任务中心 / POST 触发 / 账户生命周期
 | 
v1.2.0 2026-07-15 · 顶栏身份 / 种子权限 / 启停用语
 | 
v1.1.0 2026-07-14 · Scope 资源隔离 / 自助改密 / 编辑页精简
 | 
v1.0.0 2026-07-14 · RBAC / 生命周期 / operation\_log
 | 
v0.2.0 2026-06-10 · P1 可观测 / Tier 0–2 / UI
 | 
v0.1.1 2026-06-01 · 文档 / 部署 / 多版本 Python
 | 
v0.1.0 2026-05-29 · Phase A（P0）

[← 文档索引](index.html) ·
[Markdown 版（仓库根）](../RELEASE_NOTES.md) ·
[Markdown 版（doc）](RELEASE_NOTES.md)

## [Unreleased]

下一版计划见 [**交付状态与路线图**](交付状态与路线图.html)。

**维护约定：**未交付项进入开发时，在本节起草条目；发布时下沉到对应版本节。

## [2.0.0] — 2026-07-17 · 任务中心、触发 GET/POST、账户生命周期

任务中心规模化 IA、触发请求支持 POST JSON Body、强制改密与用户启停缘由等。升级须跑 `ensure_business_tables`（**SQLite / MySQL** 补列）并**重启**。

### Schema（SQLite / MySQL）

| 对象 | 变更 | 说明 |
| --- | --- | --- |
| `job_health` | 新表（`create_all`） | 连续失败 / 最近结果等健康快照 |
| `cron_infos` | `last_operator_name` / `last_operated_at` | 最近发布人与时间 |
| `cron_infos` | `req_method` / `req_body` | 触发请求 GET/POST；POST JSON Body（MySQL 补列 `req_body` 无 DEFAULT） |
| `rbac_users` | `must_reset_password` / `status_reason` | 强制改密标记；启停缘由 |
| 配置 | `health_failing_threshold`（默认 3） | 连续失败≥N 视为「连续失败」 |

其它方言打印 `SKIP`，需自行维护 schema。

### 触发请求：GET / POST（JSON Body）

- 任务可配置 `req_method=GET|POST`（默认 GET，兼容既有任务）。
- **GET：**与既有行为一致，query 附加 `cronpilot_log_id` / `cronpilot_sign`。
- **POST：**`Content-Type: application/json`；以配置的 `req_body`（JSON 对象）为基，再注入 `cronpilot_log_id` / `cronpilot_sign`（**不覆盖**用户已写同名字段）；可空 body。
- Web 添加/编辑：触发 URL 旁选择方法；选 POST 时展示 Body 文本框。API `/api/cron` 亦可传 `req_method` / `req_body`。
- 升级：`ensure_business_tables` 对 SQLite/MySQL 补列；现有任务默认 GET。

### 任务中心与规模化 IA（OPT-P2-13）

- **导航：**「任务列表」→「任务中心」。
- **五列布局：**任务（健康圆点 + 名称/说明/URL）· 调度策略（人类可读 + Cron 原式）· 运行与发布（最近执行 / 最近发布）· 运行状态 · 操作。
- **工具栏：**连续失败 / 今日失败 / 运行中 / 已暂停 / 全部 + 业务组 Scope + 任务名搜索；Metric 四格与异常榜/最近成功**暂不展示**（过滤走工具栏）。
- **操作：**平铺「运行记录」「立即执行」（仅运行中 + `cron:write` + 有 URL）；启停 / 编辑 / 下线收入「更多 ▾」；无下线权灰色拦截（`js-retire-denied`）。
- **OPT-P1-04（列表侧）：**`/cron_run_now` + 列表确认后立即触发（独立详情页 OPT-P1-03 仍未交付）。
- **OPT-P1-01c：**执行记录 `outcome` 筛选；全局默认「非成功」。
- **表单：**默认定时模式；「触发 URL」；空调度不可发布；重名返回 `field=task_name` 并聚焦；编辑暂停任务默认保持暂停。
- **操作记录：**筛选/列「渠道」改为「业务组」（`scope_view` / `group_id`）。

### 账号与用户管理

- **业务组保存修复：**`set_user_groups` 增量增删，避免同次 flush 触发 `(user_id, group_id)` 唯一约束冲突。
- **强制首次改密：**新建默认 `changeme` + `must_reset_password=1`；管理员不可代设密码，仅可触发重置；不可重置自己；现有用户补列默认不强制。
- **用户列表：**重置密码 / 停用·恢复（须填缘由）/ 编辑（末位 info）；当前用户不可经用户管理编辑自己，列表仅「修改密码」。
- **登录会话（现状）：**Flask signed cookie；**无**闲置/绝对超时自动登出；关闭浏览器后会话 Cookie 通常失效；退出与改密成功会 `session.clear()`。详 [RBAC §4.6](RBAC架构设计方案.html#account-session)。
- **账户体系可优化（未排期）：**可配置会话超时、「记住登录」、会话吊销、忘记密码、密码策略增强、系统/业务管理员用户管理边界（待产品确认）、MFA/OAuth（远期）。

### 本版明确不纳入

- 系统管理员 vs 业务管理员的用户管理权限拆分（需求理解偏差，**已终止**，policy 仍统一 `user:manage`）。
- 登录闲置超时自动退出（见上「可优化」；本版不实现）。
- OPT-P1-03 独立执行详情页；Metric 条 / 异常榜 UI；API Scope 隔离（S6）。

## [1.2.0] — 2026-07-15 · 顶栏身份、种子权限收窄、启停用语

管理端身份可见性与种子运维边界；任务启停文案统一。升级须**重启**（模板 / policy）。

### 管理端顶栏：登录用户信息

| 变更 | 说明 |
| --- | --- |
| 位置 | `admin_base.html` 全局 `{% block topbar %}`（`rbac/_topbar.html`）；与 `nav-tabs` 分层 |
| 展示 | 右侧聚焦：用户名、角色标签与退出同组；种子 `admin` →「系统管理员」，其它 admin →「业务管理员」，`operator` / `viewer` 顶栏直接显示英文角色码；非 admin 另示业务组或「未分配业务组」；角色标签用橙/蓝/青/绿语义色 |
| 数据 | `current_user_groups` 由 `session['group_ids']` 解析组名（与授权同源；组变更须重新登录） |
| 退出 | 顶栏统一 `/rbac/logout`（写审计）；导航 tab 移除重复「退出」；「修改密码」仍在导航 |

### 种子账号 `admin` 权限收窄

| 变更 | 说明 |
| --- | --- |
| 种子 | 用户名固定 `admin`：保留 `user:manage` + 只读（`cron:read` / `log:read` / `operation:read` / `audit:read`）与 Scope 绕过 |
| 禁止 | 种子无 `cron:write` / `cron:retire`（不可添加/编辑/启动暂停/下线任务） |
| 运维 | 任务操作须由种子创建的其它 **admin 角色**用户（业务管理员）执行（非第四角色） |

### 操作记录用语：启动 / 暂停

| 变更 | 说明 |
| --- | --- |
| 操作记录 | `toggle_status` 展示为 **启动任务** 或 **暂停任务**（依 `status` 新旧值）；详情如「启动：已暂停 → 运行中」 |
| 任务列表 | 操作链「运行」改为「启动」，与「暂停」对称 |
| 接口提示 | 成功「已启动」/「已暂停」；下线任务「不能启动或暂停」 |
| 筛选 | 筛选项「启动/暂停」（库内仍为 `action=toggle_status`） |

### 任务列表「下线」入口可见性

| 变更 | 说明 |
| --- | --- |
| 展示 | 未下线任务对所有登录角色显示「下线」 |
| 权限 | 仅具备 `cron:retire` 的账号可进入下线表单并执行（业务管理员；种子 `admin` 无此权限） |
| 无下线权限 | 点击弹出「权限不足：当前账号不可下线任务」，不发起下线请求；直达 `/cron_retire` 仍为 403 |

## [1.1.0] — 2026-07-14 · Resource Scope、自助改密、编辑页精简

在 v1.0.0 RBAC 之上交付 **OPT-P2-12 资源隔离**，并完善账号自助与任务编辑体验。升级须**重启**。

| 库 | 升级动作 |
| --- | --- |
| **SQLite / MySQL** | 部署启动时 `ensure_business_tables.py`（`run_production.sh` / `cronpilot.sh start`）：`create_all` 建缺失表（含业务组），并对已有 `cron_infos` / `job_log` 按需 `ALTER` 补列。旧名 `ensure_sqlite_tables.*` 仍转发 |
| 其它方言 | 打印 `SKIP`；需自行维护 schema |

前提：MySQL 库与账号已存在且 `cron_db_url` 可连；脚本**不会**删表或改已有列类型。手写 DDL（设计 §十）仍作备用。脚本已更名为 **`ensure_business_tables`**（旧名 `ensure_sqlite_tables` 仍转发）。`login_pwd` 仍仅空表种子。

### OPT-P2-12 · Resource Scope

| 变更 | 说明 |
| --- | --- |
| 数据 | `resource_groups` / `user_groups`；`cron_infos.scope_type`（默认 GLOBAL）/ `group_id`；SQLite/MySQL 均由 `ensure_business_tables` 自动补齐 |
| 鉴权 | 列表 Scope 过滤 + 单资源 `authorize`；admin 绕过；越权 403 + `scope:deny` |
| 管理端 | `/rbac/groups*`（编码由名称自动生成）；用户绑组（非 admin 至少一组）；**任务添加**时可设作用域；日志继承可见性 |
| 非 admin 任务 | 强制 `GROUP`、仅可选本人所属组；不可设 GLOBAL |
| API | 首期未改（部署级 token 全库；S6 远期） |
| 测试 | `tests/test_rbac_scope.py` |

详设：[Scope 设计](资源隔离与Scope设计.html) · [落地路线](资源隔离落地路线.html)

### 自助修改密码

| 变更 | 说明 |
| --- | --- |
| 入口 | 导航「修改密码」→ `/rbac/password`（任意已登录角色；不需 `user:manage`） |
| 校验 | 当前密码；新密码 ≥6 位且不同于旧密码 |
| 会话 | 成功后清空会话，跳转登录页提示重新登录 |
| 审计 | `user:password` |
| 代改 | v1.1.0：admin「用户管理 → 编辑」仍可改他人密码（不强制对方下线）。**v2.0.0 起**改为仅「触发密码重置」（见 [2.0.0](#200)），本节保留发版当时行为说明 |

### 任务编辑页精简

- 导航显示「任务编辑」（不再高亮「任务添加」）
- 不展示创建时间、上次编辑、作用域/可见范围；保存时作用域保持原值

## [1.0.0] — 2026-07-14 · 重大版本：多用户 RBAC、任务生命周期、操作审计

首个 **1.x** 里程碑：交付 **OPT-P2-10 RBAC v4**（三角色始终分权）、**OPT-P1-09 `operation_log`**、**LIFECYCLE-1/2**、**log\_id 必填**、**404 友好页**。升级须重启；登录为用户名+密码（空表种子 `admin`）。

### OPT-P2-10 · RBAC v4

| 阶段 | 状态 | 摘要 |
| --- | --- | --- |
| 1～5 | ✅ | 模型、核心、登录、导航、权限；无删除；`cron:retire` |
| 6a 用户管理 | ✅ | `/rbac/users*`；最后 admin 保护；Ajax 门禁 |
| 6b 审计 | ✅ | `/rbac/audit-logs`；中文动作 / 用户 ID 列 |
| 7 验收 | ✅ | 三角色真实登录矩阵 `TestRbacTriangularAcceptance` |

| 变更 | 说明 |
| --- | --- |
| 登录 / 密码 | 用户名+密码；空表种子 `admin`（初始密码=`login_pwd`）。日常改密：用户管理 → 编辑 → 新密码；有用户后改 `login_pwd` 无效。无忘记密码。（自助改密见 v1.1.0） |
| 默认行为 | 三角色分权**始终启用**；登录须 `rbac_users`；空表种子 `admin` |
| 分权 | 三角色**始终启用**；已移除旁路开关 `rbac_enable` |
| 冒烟 | `username=admin&password=…` |

详设：[RBAC v4](RBAC架构设计方案.html) · [落地路线](RBAC落地路线.html)

### OPT-P1-09 · 操作记录 `operation_log`

| 变更 | 说明 |
| --- | --- |
| 写入 | `create_cron` / `update_cron` / `toggle_status` / `retire_cron`（Web+API）；系统对账下线 |
| 管理页 | `/operation_log_list`；权限 `operation:read`（operator+admin）；RBAC「审计」为 `audit:read`（仅 admin） |
| 保留 | `operation_log_counts`（默认 5000）；`cron_del_operation_log` |

### 任务生命周期 / LIFECYCLE-2 / 404 / log\_id

| 变更 | 说明 |
| --- | --- |
| 无删除 | 下线替代删除；旧删除路由 410 |
| LIFECYCLE-2 | 强制备注；下线原因/时间；`created_at`/`updated_at` |
| 404 | 登录态/访客友好页；须重启后冒烟 |
| log\_id | 每次执行必有 `job_log.log_id` |

## [0.2.0] — 2026-06-10 · P1 可观测、依赖 Tier 0–2、管理端 UI

在 v0.1.1 上交付 **P1 OPT-P1-01/02**、**UI A′+B1+OPT-P1-07**、**Tier 0/1/2（RFC-2.1～2.5）**、侧车 HTTP/PyMySQL。**无 API 协议变更。**

**升级要点：**Docker 镜像 Python **3.10**；`fail_on_http_4xx_5xx` 新配置；勿用 `conf.ci.ini` 作生产挂载。

### 管理端 UI（A′ + B1）

| 变更 | 说明 |
| --- | --- |
| 执行记录列表 | 「返回的内容」一格两行：HTTP 状态 + 正文截断 |
| 查看详情 | 替代「更详细的执行记录」；展示 `job_log` 完整 HTTP 响应/异常 |
| `http_status` | `cron_do` 写入；已有库经 `ensure_business_tables.py` 补列（当时名 `ensure_sqlite_tables.py`） |
| Cron 分钟 B1 | 添加/编辑页：`*/1` = 每分钟 |

设计说明：[管理端 UI 优化设计](管理端UI优化设计.html)

### 管理端 UI · OPT-P1-07 导航栏 partial

| 变更 | 说明 |
| --- | --- |
| `_admin_nav.html` | 统一 5 项 Tab：任务列表 / 任务添加 / 任务执行记录 / API文档 / 退出 |
| 修复 | `cron_add`、`cron_edit` 此前仅 2 项导航，进入添加页后其余 Tab 消失 |
| 引用页 | `cron_list`、`cron_add`、`cron_edit`、`job_log_all_list`、`api_doc` |

设计说明：[产品 PRD OPT-P1-07](产品优化需求-借鉴Plombery.html) · [技术方案与前端设计](技术方案与前端设计.html)

### P1 可观测（OPT-P1-01/02）

| 变更 | 说明 |
| --- | --- |
| `status` / `fail_reason` | `success` / `fail` / `error` + 短标签 |
| `fail_on_http_4xx_5xx` | 默认 `1`；4xx/5xx 记 fail 并告警 |
| UI | A′ 列表增加状态徽章；详情展示 `fail_reason` |

设计说明：[P1 可观测优化设计](P1可观测优化设计.html)

### 侧车 PyMySQL（RFC-S.2）

| 变更 | 说明 |
| --- | --- |
| `PyMySQL` 1.1.2 | 0.10.1 → 1.1.2；`mysql+pymysql://` URL 不变 |

### Tier 2 · RFC-2.1 / RFC-2.2 / RFC-2.3

| 变更 | 说明 |
| --- | --- |
| `gevent` 23.9.1 | 20.9.0 → 23.9.1；Py 3.8–3.11 |
| `greenlet` 3.1.1 | 与 gevent 23 配套 |
| `gunicorn` 22.0.0 | 20.0.4 → 22.0.0；gevent worker + Docker 金路径已验收 |
| `APScheduler` 3.10.4 | 3.6.3 → 3.10.4；`SQLAlchemyJobStore` + SA 1.4；Docker compose 冒烟通过 |
| **RFC-2.4** | Docker **3.10** + `install-full` matrix **3.9 / 3.10 / 3.11** |

### 依赖升级 Tier 0 / Tier 1 / 侧车 HTTP

**Tier 0：**退役 Flask-Script；迁移 CLI 改为 `flask db`（Python 3.11 可用）。  
**Tier 1：**SQLAlchemy 1.4.52 + Flask-SQLAlchemy 2.5.1；全站 `Model.query` 已迁移为 SA 1.4 推荐写法。  
**侧车 RFC-S.1：**`requests` 2.31.0、`urllib3` 1.26.19、`certifi` 2024.8.30。

### Tier 0

| 变更 | 说明 |
| --- | --- |
| Flask-Script 移除 | `manage.py` 注册 Click `db` 子命令 |
| `requirements-core.txt` | 锁定 `Flask-Migrate`、`alembic==1.4.3` |

### Tier 1

| 变更 | 说明 |
| --- | --- |
| SQLAlchemy 1.4.52 | 过渡版；全站 `Model.query` 已迁移 |
| Flask-SQLAlchemy 2.5.1 | SA 1.4 兼容（2.4.x URL API 不兼容） |
| `config.py` | `SQLALCHEMY_ENGINE_OPTIONS = {'future': False}` |
| 查询改写 | `job_log_service`、`main/views`、`cron_service`、`api/views`、`crons` |
| Docker 验收 | `write_sqlite_conf.py --container-paths`；`reset_datas_sqlite.sh` |
| 留 Tier 3 | `records` 裸 SQL（`CuBackgroundScheduler` 等） |

### 侧车 HTTP（RFC-S.1）

| 变更 | 说明 |
| --- | --- |
| `requests` 2.31.0 | 收敛已知 CVE；回归回调与 SSRF |
| `urllib3` 1.26.19 | 与 requests 2.31 配套 |
| `certifi` 2024.8.30 | CA 根证书同步 |

```
export FLASK_APP=manage:app
flask db migrate -m "描述"
flask db upgrade
```

详 [依赖升级 RFC](依赖升级RFC.html) Tier 0–1；本地试用 `conf.local.sqlite.example`。

---

## [0.1.1] — 2026-06-01

工程化与运维增强，**无 API 协议变更**。

### 文档与在线访问

| 变更 | 说明 |
| --- | --- |
| `/docs/` | 技术文档 HTML 与 `/docs/*.md` 同端口访问 |
| 双格式 | 各文档 HTML + Markdown；`doc/index.md` 索引 |
| 同步工具 | `scripts/html_docs_to_markdown.py --check` |
| 部署指南 | [非 Docker 部署指南](非Docker部署指南.html) |
| 协作规范 | `.cursor/rules/`、`AGENTS.md` |

### Python 3.8–3.11 自动匹配

- 自动探测并复用 `.venv-py*`，**无需**手动 `export PY=`
- 统一入口：`bash scripts/cronpilot.sh start|install|test|check`
- `requirements-core.txt` 用于本地与 CI 单测

```
bash scripts/cronpilot.sh start
bash scripts/cronpilot.sh test
```

### CI

- Docs HTML ↔ Markdown sync
- Unit tests 矩阵 3.8 / 3.9 / 3.10 / 3.11
- install-full（3.10 全量依赖）

### 升级（自 v0.1.0）

- `bash scripts/cronpilot.sh install`
- 改 HTML 后运行 `html_docs_to_markdown.py`
- 重启后访问 `/docs/`

---

## [0.1.0] — 2026-05-29 · Phase A（P0）首发

HTTP 定时回调调度、Web/API 管理、P0 安全与质量、技术文档与 Apache-2.0 许可。

## 回调与 API 协议

| 参数 / 接口 | 说明 |
| --- | --- |
| `cronpilot_log_id` | 每次触发的执行 UUID |
| `cronpilot_sign` | 回调签名（MD5） |
| `POST /api/cron/add_log` | 进度回传 |

```
GET /your/callback?cronpilot_log_id=<UUID>&cronpilot_sign=<MD5>
POST /api/cron/add_log  cronpilot_log_id=<UUID>&content=...
```

## Phase A（P0）

| ID | 内容 |
| --- | --- |
| P0-01 | SQL ORM 化 · `job_log_service` |
| P0-02 | 密码 pbkdf2 哈希 |
| P0-03 | SSRF 防护配置项 |
| P0-04 | JSON `errcode` 数字类型 |
| P0-05 | `cron_validator` + `cron_service` |

## 文档与许可

见 [文档索引](index.html)；许可 [LICENSE-AUDIT](LICENSE-AUDIT.html)（Apache-2.0）。

## 测试

```
bash scripts/cronpilot.sh test
```

## 后续版本

P1/P2 见 [PRD](产品优化需求-借鉴Plombery.html)；计划 `0.2.x` 对应 P1。

CronPilot · Release Notes · [Markdown](RELEASE_NOTES.md) · [索引](index.html)

---

[← 文档索引（HTML）](index.html) · [← 文档索引（Markdown）](index.md)
