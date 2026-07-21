# CronPilot Release Notes

本文档记录 **CronPilot** 版本变更。  
HTML 版：[doc/RELEASE_NOTES.html](doc/RELEASE_NOTES.html)

---

## [Unreleased]

Changes in development for a future release will appear here when ready.

Maintainer note: track unfinished work in [交付状态与路线图](doc/交付状态与路线图.html); do not use this section as a project status board.

---

## [2.1.0] — 2026-07-20 · Runtime stack (Flask 2.3 + SQLAlchemy 2.0)

This release upgrades CronPilot’s application and ORM runtime. **Task scheduling behavior, management UI, and the HTTP callback / progress-log API stay compatible** for deployments that already follow the documented install path. Supported Python remains **3.8–3.11**.

### What’s new

- **Web stack:** Flask **2.3.3**, Werkzeug **2.3.8**, Jinja2 **3.1.6**, and related dependencies aligned to that line.
- **Database layer:** SQLAlchemy **2.0.36** and Flask-SQLAlchemy **3.1.1**, with models and list queries updated for the 2.x style.
- **Scheduler persistence:** removed the `records` package; JobStore checks and retire updates go through SQLAlchemy / the application ORM. Dual-database layout (`cron_db_url` / `cron_job_log_db_url`) is unchanged.
- **Schema tooling:** business tables and additive columns continue to be applied with `scripts/ensure_business_tables` (SQLite / MySQL). There is still **no** required Alembic `migrations/` tree for day-to-day upgrades.
- **Quality gates:** additional automated checks for ORM usage and pinned framework versions in verification scripts.

### Upgrade

1. Update the virtualenv: `pip install -r requirements.txt` (or rebuild from your install docs).
2. Run `bash scripts/ensure_business_tables.sh`.
3. **Restart** the CronPilot process (template and Python changes are not picked up by a browser refresh alone).

This release does **not** introduce breaking table drops or mandatory data migrations.

### Notes

- Flask 3.x and a default Python 3.12+ support window are **not** part of this release.
- End-to-end Docker Compose pin verification may still need to be run in environments where Docker is available; local / bare-metal installs are covered by the usual test and golden-path scripts.

---

## [2.0.0] — 2026-07-17 · 任务中心、触发 GET/POST、账户生命周期

任务中心布局与健康筛选、触发请求支持 POST JSON Body、强制首次改密与用户启停缘由等。升级须跑 `ensure_business_tables`（**SQLite / MySQL** 补列）并**重启**。

### Schema（SQLite / MySQL）

| 对象 | 变更 | 说明 |
|------|------|------|
| `job_health` | 新表 | 连续失败 / 最近结果等健康快照 |
| `cron_infos` | `last_operator_name` / `last_operated_at` | 最近发布人与时间 |
| `cron_infos` | `req_method` / `req_body` | 触发方法 GET/POST；POST JSON Body（MySQL 补列 `req_body` 无 DEFAULT） |
| `rbac_users` | `must_reset_password` / `status_reason` | 强制改密标记；启停缘由 |
| 配置 | `health_failing_threshold`（默认 3） | 连续失败≥N 视为「连续失败」 |

其它方言打印 `SKIP`，需自行维护 schema。

### 触发请求：GET / POST（JSON Body）

- 任务可配置 `req_method=GET|POST`（默认 GET，兼容既有任务）。
- **GET**：query 附加 `cronpilot_log_id` / `cronpilot_sign`。
- **POST**：`Content-Type: application/json`；以配置的 `req_body` 为基，再注入签名字段（不覆盖用户已写同名字段）；可空 body。
- Web 添加/编辑与 API `/api/cron` 均可配置方法与 Body。

### 任务中心

- 导航「任务列表」更名为「任务中心」。
- 五列布局：任务（健康圆点 + 名称/说明/URL）· 调度策略 · 运行与发布 · 运行状态 · 操作。
- 工具栏：连续失败 / 今日失败 / 运行中 / 已暂停 / 全部，以及业务组与任务名搜索。
- 列表可「立即执行」（运行中且具备写权限、已配置 URL）；启停 / 编辑 / 下线收入「更多」。
- 执行记录支持按结果筛选（默认「非成功」）。
- 操作记录筛选/列「渠道」改为「业务组」。

### 账号与用户管理

- 新建用户默认密码 `changeme` 并强制首次改密；管理员可触发重置（不可重置自己），不可直接代设他人密码。
- 用户启停须填写缘由；列表对停用 / 待重置用户有区分展示。
- 登录为浏览器会话 Cookie：无闲置超时自动登出；退出与改密成功会清空会话。

### 升级

1. `bash scripts/ensure_business_tables.sh`
2. **重启**进程

### 本版未包含

独立执行详情页、任务中心 Metric / 异常榜 UI、REST API 按业务组隔离、可配置登录闲置超时。

---

## [1.2.0] — 2026-07-15 · 顶栏身份、种子权限、启停用语

管理端展示当前登录身份；收窄种子账号任务写权限；统一「启动 / 暂停」用语。升级须**重启**。

### 顶栏身份

- 全局顶栏展示用户名、角色标签与退出；种子 `admin` 显示为「系统管理员」，其它 admin 为「业务管理员」；`operator` / `viewer` 显示角色码；非 admin 可显示所属业务组。
- 退出统一走 `/rbac/logout`。

### 种子账号 `admin`

- 保留用户管理与只读权限，**不可**添加/编辑/启动暂停/下线任务。
- 任务写操作需由其它 admin 角色用户执行。

### 启停用语与下线入口

- 界面与操作记录统一为「启动」「暂停」。
- 未下线任务对所有登录角色可见「下线」入口；仅具备下线权限者可执行，否则前端提示且不发起请求。

---

## [1.1.0] — 2026-07-14 · 业务组隔离、自助改密、编辑页精简

在多用户权限之上增加业务组可见性隔离，并提供自助改密与更清晰的任务编辑页。升级须跑 `ensure_business_tables` 并**重启**。

### 业务组隔离

- 新增业务组与用户-组关系；任务可设全局或组内可见。
- 列表与单资源访问按所属组过滤；admin 不受限。
- 非 admin 新建任务须绑定本人所属组。
- 部署级 API Token 本版仍可访问全库（后续可收紧）。

### 自助修改密码

- 任意已登录用户可通过导航「修改密码」修改本人密码；成功后需重新登录。
- （发版当时）管理员仍可通过用户管理编辑他人密码；自 **v2.0.0** 起改为仅「触发密码重置」。

### 任务编辑页

- 导航正确高亮「任务编辑」；不展示创建时间、上次编辑与作用域字段（作用域仅在添加时设置）。

---

## [1.0.0] — 2026-07-14 · 多用户权限、任务生命周期、操作审计

首个 1.x：三角色权限与用户管理、任务下线替代删除、操作记录与执行 `log_id`、404 友好页。升级须**重启**；空库自动种子 `admin`（密码=`login_pwd`）。

### 多用户权限

- 登录：用户名 + 密码；三角色分权始终启用。
- 用户管理、权限审计与业务操作记录分权分表。
- 无人工删除任务；下线需相应权限。

### 操作记录

- 创建 / 更新 / 启停 / 下线等写入 `operation_log`；支持按保留条数裁剪。

### 任务生命周期

- 暂停可恢复；下线为不可逆终点，须填写原因。
- 任务说明必填；记录创建与更新时间。

### 其它

- 友好 404 页面；每次执行必有 `job_log.log_id`。

### 升级说明（自 v0.2.0）

1. 重启以加载鉴权与模板。
2. Web 登录改为用户名 + 密码；空库种子 `admin`。
3. `login_pwd` 仅用于空表种子；有用户后改 conf 不会改登录密码。
4. 可选配置 `operation_log_counts`（默认 5000）。

---

## [0.2.0] — 2026-06-10 · 执行可观测、依赖与部署加固、管理端体验

执行结果状态与失败原因、管理端列表与导航体验，以及运行时依赖与 Docker / CI 加固。**回调协议不变**（`cronpilot_log_id` / `cronpilot_sign` / `add_log`）。

### 执行可观测

- `job_log` 写入 `status` / `fail_reason` / `http_status`。
- 配置 `fail_on_http_4xx_5xx`（默认开启）：HTTP 4xx/5xx 记为失败并可告警。
- 执行记录列表展示状态徽章与「查看详情」。

### 管理端体验

- 统一主导航 Tab；添加/编辑页导航不再残缺。
- Cron 分钟字段增加可读提示（如 `*/1` 表示每分钟）。

### 依赖与运行时

| 组件 | 版本（本版） |
|------|----------------|
| SQLAlchemy / Flask-SQLAlchemy | 1.4.52 / 2.5.1 |
| gevent / greenlet / gunicorn | 23.9.1 / 3.1.1 / 22.0.0 |
| APScheduler | 3.10.4 |
| requests / urllib3 / certifi | 2.31.0 / 1.26.19 / 2024.8.30 |
| PyMySQL | 1.1.2 |

- 迁移 CLI 改为 `flask db`（移除 Flask-Script）。
- Docker 镜像 Python **3.10**；安装与 CI 覆盖 3.8–3.11（全量依赖矩阵含 3.9–3.11）。

### 升级说明（自 v0.1.1）

1. 更新依赖并重启；Docker 建议重建镜像。
2. 已有库由 `ensure_business_tables` 补执行日志相关列。
3. 核对 `fail_on_http_4xx_5xx` 配置。

---

## [0.1.1] — 2026-06-01 · 文档、部署与多版本 Python

工程化与运维增强，**无 API 协议变更**。

- 同端口提供 `/docs/` 技术文档（HTML + Markdown）。
- `cronpilot.sh` 自动匹配 Python **3.8–3.11** 与 `.venv-py*`。
- Linux 一键安装 / 生产启动脚本；Docker 与 GitHub Actions 安装验收。

升级：拉取后执行 `bash scripts/cronpilot.sh install`，重启后访问 `/docs/`。

---

## [0.1.0] — 2026-05-29 · 首发

HTTP 定时回调调度、Web / API 管理、基础安全与质量能力、技术文档与 **Apache-2.0** 许可。

### 回调与 API

| 参数 / 接口 | 说明 |
|-------------|------|
| `cronpilot_log_id` | 每次触发的执行 UUID |
| `cronpilot_sign` | 回调签名（MD5） |
| `POST /api/cron/add_log` | 进度回传（必传 `cronpilot_log_id`、`content`） |

### 安全与质量

- 任务与日志访问走 ORM / 参数化路径；管理端密码支持哈希。
- 回调 URL SSRF 防护（`block_private_ip` 等）。
- 统一 JSON 响应（`errcode` 为数字）；Cron 校验与任务写入统一服务层。

### 对接检查清单

- [ ] 业务回调读取并验签 `cronpilot_log_id` / `cronpilot_sign`
- [ ] 长任务进度使用 `POST /api/cron/add_log`
- [ ] 生产建议开启 SSRF 防护
- [ ] 管理端密码建议使用哈希

推荐 Python **3.8–3.11**。

---

## 版本一览

| 版本 | 说明 |
|------|------|
| **2.1.0** | Flask 2.3 + SQLAlchemy 2.0 运行时 |
| 2.0.0 | 任务中心、POST 触发、账户生命周期 |
| 1.2.0 | 顶栏身份、种子权限、启停用语 |
| 1.1.0 | 业务组隔离、自助改密 |
| 1.0.0 | 多用户权限、生命周期、操作审计 |
| 0.2.0 | 执行可观测、依赖与部署加固 |
| 0.1.1 | 文档 `/docs/`、多版本 Python、CI |
| 0.1.0 | 首发 |
