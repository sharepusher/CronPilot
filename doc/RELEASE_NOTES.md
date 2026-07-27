# Release Notes · CronPilot

> HTML 版：[RELEASE_NOTES.html](RELEASE_NOTES.html) · [文档索引](index.html) · [索引 Markdown](index.md)

# CronPilot Release Notes

v2.1.1 2026-07-21 · Security hardening (lock / SECRET\_KEY / CSRF)
 | 
v2.1.0 2026-07-20 · Runtime stack (Flask 2.3 + SQLAlchemy 2.0)
 | 
v2.0.0 2026-07-17 · 任务中心 / POST 触发 / 账户生命周期
 | 
v1.2.0 2026-07-15 · 顶栏身份 / 种子权限 / 启停用语
 | 
v1.1.0 2026-07-14 · 业务组隔离 / 自助改密
 | 
v1.0.0 2026-07-14 · 多用户权限 / 生命周期 / 操作审计
 | 
v0.2.0 2026-06-10 · 执行可观测 / 依赖与部署加固
 | 
v0.1.1 2026-06-01 · 文档 / 部署 / 多版本 Python
 | 
v0.1.0 2026-05-29 · 首发

[← 文档索引](index.html) ·
[Markdown 版（仓库根）](../RELEASE_NOTES.md) ·
[Markdown 版（doc）](RELEASE_NOTES.md)

## [Unreleased]

维护说明：未完成项请记在 [交付状态与路线图](交付状态与路线图.html)；本节不要写成内部进度板。

### Internal: dead static asset cleanup (F0-a)

- Removed `app/static/vue.js` (280 KB): a Vue 2.x library committed but never referenced by any template or Python file; its presence previously created a misleading impression that Vue was already integrated.
- Removed additional unused static files confirmed to have zero template or CSS references: `images/mini_code.png`, `js/qrcode.min.js`, `js/artDialog/skins/blue.css` and the entire `blue/` skin directory (artDialog loads only the `default` skin), the entire `js/simpleboot/font-awesome/4.2.0/` directory (superseded by 4.4.0), and the entire `js/simpleboot/themes/bluesky/` directory (only the `flat` theme is in use).
- No behavior change. All 219 existing tests pass.
- F0-b (IE 8/9 `html5shiv` shim in `admin_base.html`) removed: confirmed no active IE 8/9 users; eliminates an external CDN dependency (`oss.maxcdn.com`) from the base template.

### Frontend modernization: Vite + Vue 3 component pilot (OPT-P2-14 · F1)

- **Vite build chain introduced (`frontend/`):** A minimal `frontend/` directory contains `package.json` (Node ≥ 18, Vite 6 + `@vitejs/plugin-vue` 5 + Vue 3.5), `vite.config.js` (IIFE lib mode, output to `app/static/dist/`), and the `CronStatusCell` Single File Component. `frontend/node_modules/` is gitignored; `app/static/dist/` is committed so deployment requires no Node.js.
- **`CronStatusCell` Vue 3 component (F1-b):** The cron list "Status & Operations" column is now rendered by a Vue 3 component mounted via `data-*` attributes on `<div id="cron-ops-{id}">`. The component provides: reactive status badge (enabled / paused / retired), "运行记录" link, "立即执行" button (CSRF-protected POST, `csrfFetch`), a "更多" dropdown with "启动/暂停", "编辑", and "下线" actions — all gated by `data-can-write` / `data-can-retire` props rendered server-side. No page reload for status toggle (badge updates in place).
- **Test coverage:** Added `test_vue_mount_point_data_attrs_present` asserting all 10 `data-*` props and the Vue bundle script tag are server-rendered in the cron list HTML. Existing permission tests updated to check `data-can-write` / `data-can-retire` attributes instead of jQuery-rendered button text.
- **CI gate (F1-c):** New `.github/workflows/frontend-build.yml` runs `npm ci && npm run build` on changes to `frontend/**` or `app/static/dist/**`, then fails if the committed dist file diverges from the freshly-built output.

### Docker image pin verification

- **Compose verify：**`bash scripts/verify_docker_compose.sh --rebuild` 断言镜像内 Framework 包版本与 `requirements.txt` 一致（Flask / Werkzeug / Jinja2 / SQLAlchemy / Flask-SQLAlchemy / alembic / Flask-Migrate / blinker）。
- **构建与运行：**镜像构建期健康检查注入强 `SECRET_KEY`；verify 写入容器 SQLite 路径，并放宽宿主机 `datas/` 对容器用户可写。
- **冒烟稳定性：**HTTP 冒烟在 UTF-8 locale 下匹配中文标记，并避免 `pipefail` 下对大 HTML 的假失败。

## [2.1.1] — 2026-07-21 · Security hardening (cluster lock, SECRET\_KEY, CSRF)

加固集群互斥锁、生产会话签名与管理端写操作 CSRF。**调度回调与 `/api/*` 契约不变**。支持的 Python 仍为 **3.8–3.11**。

### Security & reliability

- **集群互斥：**非单机模式下，任务执行锁改为原子 Redis `SET NX EX`，且仅持有者 token 可释放（避免双节点同跑，以及 TTL 过期后误删后继锁）。
- **会话签名：**生产（`FLASK_CONFIG=production`）拒绝缺失 / 默认 / 过短的 `SECRET_KEY`。请设置
  `export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"`，
  或通过 `scripts/run_production.sh` 首次写入 `datas/.flask_secret_key`。多节点须共用同一密钥。
- **管理端 CSRF：**写操作须 `POST` + Session Token（页面 meta / 表单字段）；对话框启停与立即执行已改为 POST。无 token 或仍用 GET 变更状态会失败。请硬刷新后再操作。

### Upgrade notes

1. 若生产直接启动 Gunicorn（不经 `run_production.sh`），升级前须在环境 / systemd 中配置强 `SECRET_KEY`，否则将 fail-fast。
2. 升级后**重启** CronPilot，并对管理端**硬刷新**（CSRF token 嵌入页面）。
3. 单机试用（`is_single=1`）的 Redis 锁路径行为不变。
4. 启停 / 立即执行勿再用 GET 书签；相关路由仅为 POST。

## [2.1.0] — 2026-07-20 · Runtime stack (Flask 2.3 + SQLAlchemy 2.0)

本版本升级 CronPilot 的应用与 ORM 运行时。**任务调度行为、管理端与 HTTP 回调 / 进度回传 API 保持兼容**（按文档安装与升级路径即可）。支持的 Python 仍为 **3.8–3.11**。

### What's new

- **Web 栈：**Flask **2.3.3**、Werkzeug **2.3.8**、Jinja2 **3.1.6** 及同线依赖。
- **数据库层：**SQLAlchemy **2.0.36**、Flask-SQLAlchemy **3.1.1**；模型与列表查询已按 2.x 方式调整。
- **调度持久化：**移除 `records`；JobStore 巡检与下线更新改走 SQLAlchemy / 应用 ORM。双库布局不变。
- **Schema 工具：**业务表与补列仍通过 `scripts/ensure_business_tables`（SQLite / MySQL）；日常升级**不要求** Alembic `migrations/` 树。
- **质量门禁：**加强 ORM 用法与框架版本 pin 的自动检查。

### Upgrade

1. 更新虚拟环境：`pip install -r requirements.txt`
2. 执行 `bash scripts/ensure_business_tables.sh`
3. **重启** CronPilot 进程

本版本**不含**破坏性删表或强制数据迁移。Flask 3.x 与默认 Python 3.12+ 不在本版本范围。

## [2.0.0] — 2026-07-17 · 任务中心、触发 GET/POST、账户生命周期

任务中心布局与健康筛选、触发请求支持 POST JSON Body、强制首次改密与用户启停缘由等。升级须跑 `ensure_business_tables` 并**重启**。

### Schema（SQLite / MySQL）

| 对象 | 变更 | 说明 |
| --- | --- | --- |
| `job_health` | 新表 | 连续失败 / 最近结果等健康快照 |
| `cron_infos` | `last_operator_*` / `req_method` / `req_body` | 最近发布人；GET/POST 与 JSON Body |
| `rbac_users` | `must_reset_password` / `status_reason` | 强制改密；启停缘由 |
| 配置 | `health_failing_threshold` | 默认 3 |

### 触发请求与任务中心

- 任务可配置 GET/POST；POST 发送 JSON Body 并注入签名字段。
- 任务中心五列布局、健康快筛、列表「立即执行」、执行结果筛选。
- 新建用户强制首次改密；启停须填缘由；会话无闲置超时自动登出。

本版未包含：独立执行详情页、Metric/异常榜 UI、API 按组隔离、可配置会话超时。

## [1.2.0] — 2026-07-15 · 顶栏身份、种子权限、启停用语

- 全局顶栏展示用户名、角色与退出；种子 `admin` 为「系统管理员」。
- 种子账号不可写任务；任务写操作需其它 admin 用户。
- 界面统一「启动 / 暂停」；下线入口按权限拦截。

## [1.1.0] — 2026-07-14 · 业务组隔离、自助改密、编辑页精简

- 业务组可见性隔离；非 admin 任务须绑定所属组；admin 不受限。
- 自助「修改密码」；成功后需重新登录。
- 任务编辑页精简（作用域仅添加时设置）。

升级：`ensure_business_tables` + **重启**。

## [1.0.0] — 2026-07-14 · 多用户权限、任务生命周期、操作审计

- 三角色权限始终启用；用户名+密码登录；空库种子 `admin`。
- 任务下线替代删除；操作记录与权限审计分权。
- 每次执行必有 `job_log.log_id`；友好 404 页。

`login_pwd` 仅用于空表种子；有用户后改 conf 不会改登录密码。

## [0.2.0] — 2026-06-10 · 执行可观测、依赖与部署加固

- 执行 `status` / `fail_reason` / `http_status`；可配置 HTTP 失败判定。
- 统一导航与执行记录详情体验。
- SQLAlchemy 1.4.52、gevent 23、gunicorn 22、APScheduler 3.10；Docker Python 3.10；HTTP/PyMySQL 安全升级；`flask db` 替代 Flask-Script。

**回调协议不变。**

## [0.1.1] — 2026-06-01 · 文档、部署与多版本 Python

- 同端口 `/docs/`；HTML + Markdown 双格式。
- `cronpilot.sh` 自动匹配 Python 3.8–3.11。
- Linux 安装 / 生产启动脚本；CI 与 Docker 安装验收。

## [0.1.0] — 2026-05-29 · 首发

HTTP 定时回调调度、Web/API 管理、基础安全与质量、技术文档与 Apache-2.0。

| 参数 / 接口 | 说明 |
| --- | --- |
| `cronpilot_log_id` | 每次触发的执行 UUID |
| `cronpilot_sign` | 回调签名（MD5） |
| `POST /api/cron/add_log` | 进度回传 |

- ORM / 参数化访问、密码哈希、SSRF 防护、统一 JSON、校验与服务层。

## 版本一览

| 版本 | 说明 |
| --- | --- |
| **2.1.1** | 集群锁原子化、生产 SECRET\_KEY、管理端 CSRF |
| 2.1.0 | Flask 2.3 + SQLAlchemy 2.0 运行时 |
| 2.0.0 | 任务中心、POST 触发、账户生命周期 |
| 1.2.0 – 1.0.0 | 权限、业务组、生命周期、操作审计 |
| 0.2.0 – 0.1.0 | 可观测、工程化、首发 |

CronPilot · Release Notes · [Markdown](RELEASE_NOTES.md) · [索引](index.html)

---

[← 文档索引（HTML）](index.html) · [← 文档索引（Markdown）](index.md)
