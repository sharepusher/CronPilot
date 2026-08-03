# Release Notes · CronPilot

> HTML 版：[RELEASE_NOTES.html](RELEASE_NOTES.html) · [文档索引](index.html) · [索引 Markdown](index.md)

# CronPilot Release Notes

v2.7.0 2026-08-03 · Admin scope + audit scope + search + indexing + doc reorganization
 | 
v2.6.0 2026-07-31 · Color consolidation + API access\_token hardening + S6/API docs redesign
 | 
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

当前无草稿条目。

## [2.7.0] — 2026-08-03

### Admin scope differentiation (OPT-P2-15)

- **Seed admin vs. manager admin:** The built-in `admin` user (seed) now has global read-only scope. Non-seed admins ("manager admins") are scoped to explicitly assigned groups.
- **Virtual `__ALL__` group:** Manager admins can be assigned `__ALL__` to bypass group scoping.
- **User management scope:** Manager admins can only view/manage users within their group intersection. Seed admin is hidden from manager admin user lists.
- **Group management:** Only bypass-scope admins (seed or `__ALL__`) can create new resource groups.

### Audit log scope filtering (OPT-P2-16)

- **`actor_group_ids` column:** New column on `rbac_audit_logs` storing actor's group IDs in comma-wrapped format (`,1,3,`). `ensure_business_tables` handles idempotent DDL.
- **Scoped query:** Manager admins see only audit records with intersecting group IDs. Historical records without `actor_group_ids` are invisible to scoped admins.
- **Bypass users:** Seed admin and `__ALL__` manager admins retain full audit log visibility.

### Documentation quality audit and fixes

- README: added missing v2.2.0–v2.5.0 to version table; expanded CI workflows, directory structure, config keys.
- Delivery roadmap: added v2.3.0/v2.4.0 version rows; fixed OPT-P1-06 status; added OPT-P2-14/15/16 entries.
- Numbering conflict resolution: OPT-P2-12/ADMIN-SCOPE → **OPT-P2-15**; OPT-P2-13/AUDIT-SCOPE → **OPT-P2-16**.

### Version consistency CI

- `scripts/check_version_consistency.py`: verifies git tags ↔ README/roadmap/RELEASE\_NOTES consistency. `--check` mode for CI.
- `.github/workflows/version-consistency.yml`: CI workflow on version-related file changes.

### Time-column index enforcement (OPT-P2-17)

- **Model-level `index=True`:** All `create_time` / `update_time` / `created_at` / `updated_at` columns across 7 tables now carry `index=True`.
- **Runtime index backfill:** `_ensure_time_column_indexes()` idempotently creates `ix_<table>_<column>` indexes on startup.
- **Tables covered:** `rbac_audit_logs`, `rbac_users`, `resource_groups`, `cron_infos` (×2), `job_log`, `job_health`, plus pre-existing `operation_log`.

### User management & audit log search

- User management: username fuzzy search on the user list page.
- Audit log: multi-dimensional search (username, action, status, time range).
- API token auto-issuance: `ensure_existing_users_have_token()` for pre-S6 users.

### Documentation reorganization

- **Subdirectory structure:** `doc/` reorganized into 7 subdirectories (`arch/`, `design/`, `plan/`, `deps/`, `ops/`, `product/`, `qa/`). 80 files moved, 85 cross-references updated.
- **Orphan cleanup:** Removed 11 orphaned/legacy files.
- **`index.html` full refresh:** Updated to v2.7.0, added 4 missing design documents, all subdirectory links verified.
- **`check_doc_completeness.py`:** New CI script ensuring all `doc/*.html` files are registered in `doc/index.html`.

### Engineering norms

- Time-column index norm: new models missing `index=True` on time columns are review blockers.
- Query performance assessment: mandatory for all new query/search features during design phase.
- UI style consistency: prohibits inline styles for layout; standard toolbar dimensions.
- API path guard: `tests/test_api_path_guard.py` ensures all `/api/` paths in templates map to real routes.

### Tests

334 tests pass, covering admin scope differentiation, audit log scope filtering, time-column indexes, API path guard, and all prior features.

## [2.6.0] — 2026-07-31

### Release scope (all commits after v2.5.0)

- Includes all commits in `v2.5.0..v2.6.0`: `8f683ce` and `8979424`.
- Covers: frontend color consolidation, API access\_token hardening, S6 user-level token UX completion, and query-only API documentation redesign.

### Frontend color consolidation and maintainability

191 hardcoded hex colors across 21 files (57 distinct values) consolidated into CSS Custom Properties (`var(--cp-*)`). Visual output is pixel-identical.

- **`app/static/css/console-theme.css` (new):** 60 semantic CSS variables covering text, background, border, accent, success/danger/warning palettes, execution status, role badges, topbar, etc. `--cp-*` prefix avoids collisions with simpleboot.
- **20 Jinja2 templates consolidated:** `admin_base.html` (15), `cron_list.html` (68), `cron_add/edit.html` (29), and 16 additional templates.
- **Vue component consolidation:** `CronFormValidator.vue` — 10 hardcoded colors replaced with CSS variables; built assets updated.
- **Semantic class extraction:** Role badges (`.topbar-role-*`) and execution status labels (`.label-timeout/running/pending/danger`) moved to `console-theme.css`.
- **Dead file cleanup:** Removed zero-reference `_admin_nav.html`.

### Audit tooling and CI gate

- **`scripts/audit_hardcoded_colors.py` (new):** Full scan for hardcoded colors. `--check` (CI mode), `--mapping` (value→token map), `--csv` (export).
- **`.github/workflows/color-audit.yml` (new):** CI gate blocking PRs with hardcoded colors.
- **`tests/test_form_name_guard.py` (new):** 3 guard tests preventing accidental form `name` attribute changes.

### API access\_token hardening (minimal Scope mitigation)

- New opt-in setting `api_access_token_required` (default `0`, no behavior change). When set to `1`, production startup fails fast if `api_access_token` is empty.
- Failed API token checks write an audit trail (`rbac_audit_logs`, `action='api:deny'`).
- See [RBAC review report](design/RBAC与群组权限管理评审报告.html).

### RBAC / API Token UX completion (S6)

- Added standalone token page `GET /rbac/api_token`, placed before "API Docs" in top nav.
- Added self-service reset `POST /rbac/api_token/reset` (`require_login` + CSRF) with 30-day expiry refresh.
- Admin-side reset in user list unchanged.
- `tests/test_api_scope_s6.py` covers issuance, expiry, scope isolation, cache invalidation, and auto-reset on password/group mutation.

### API documentation redesign: query-only + permission-aware

- Rebuilt `/api_doc` as a native console-style page; removed embedded Swagger interaction.
- Switched from HTTP-method filtering to query-semantic + permission-aware filtering; auto-hides incomplete entries.
- Exposed read APIs: `GET /api/cron/query`, `GET /api/cron/logs`, `GET /api/cron/detail`, `GET /api/cron/log/detail`.
- Query APIs include `total`/`has_more`; logs API supports `status`/`http_status`/time-range filters and `content_preview`.
- Catalog cached in-process by permission set; refreshes on service restart.

### Deployment docs

- Non-Docker deployment guide added frontend development environment section (Node.js/nvm). README added corresponding section.

322 tests pass (covering color audit gate, RBAC/S6, query-only API docs, and scope query endpoints).

## [2.5.0] — 2026-07-29

### 单任务超时配置 — Phase B2（OPT-P1-01）

- **`CronInfos.timeout_sec` 字段（可空 INT）：**NULL 表示使用系统默认 5 s；有效范围 1–120 s。`ensure_business_tables` 幂等 DDL 补列，存量数据库安全升级。
- **表单 UI：**新增/编辑任务表单新增"超时（秒）"输入框（留空使用默认 5 s，最大 120 s）。
- **校验门禁（`cron_validator.py`）：**非空时校验 1≤timeout\_sec≤120，非整数/越界均返回 `timeout_sec` 字段错误。
- **执行路径（`cron_do`）：**使用 `cif.timeout_sec or _DEFAULT_TIMEOUT_SEC` 动态读取 per-task 超时，默认值从 120 s 调整为 5 s。
- **API schema（`CronUpsertIn`）：**新增可选 `timeout_sec` 整数字段（1–120），通过 APIFlask 文档自动暴露。
- **详情页：**`job_log_detail.html` 新增"超时限制 Xs"展示，与耗时字段并排显示。
- **14 条新单元测试（`tests/test_b2_timeout_config.py`）：**合法值、边界值、非法值（0/-1/121/非整数/浮点）、NULL 传播、service 写入，274 条测试全部通过。

### 执行状态机 — Phase B1（OPT-P1-01）

- **4 终态 `job_log.status`（方案 B，单次写）：**`success | fail | timeout | error`。执行路径全程不写中间态 DB 记录，HTTP 完成后一次性落终态，保持与原方案相同的 DB 写放大系数（1 COMMIT/execution）。
- **`started_at` / `finished_at` 时间戳字段：**`started_at` 在 HTTP 派发前赋值（本地变量），随终态记录一同落库。`finished_at` = 终态落库时刻。`timeout_sec` 字段记录本次执行所用超时阈值。
- **`timeout` 状态区分：**`requests.Timeout`/`ConnectTimeout`/`ReadTimeout` 异常映射 `timeout`，其余映射 `error`；`fail_reason` 字段保留失败归因标签。
- **`ensure_business_tables` 补丁：**幂等 DDL 添加 `started_at`、`finished_at`、`timeout_sec`；存量数据库安全升级。
- **`job_log_outcome.py`：**新增 `STATUS_PENDING`、`STATUS_RUNNING`（供旧数据 badge 展示）、`STATUS_TIMEOUT` 常量；`is_timeout_exception()` 区分超时与连接异常。
- **Badge 渲染：**`_job_log_result_cell.html` 与 `job_log_detail.html` 通过 `job_log_status_badge_class` Jinja filter 渲染 `<span class="label label-*">`；详情页展示 `started_at`/`finished_at`。新增 `.label-timeout`（紫）、`.label-running`（蓝）、`.label-pending`（灰）全局样式。
- **高并发设计选型：**方案 B 单次终态写，DB 写次数不变，适合 90%+ 快响应业务场景。`pending`/`running` 常量及样式保留，便于历史记录展示或未来按需启用中间态。
- **38 条新单元测试**（`tests/test_b1_execution_status.py`）：状态常量、`evaluate_http_response`、超时路由、`should_alert`、badge 映射、模型列存在性。
- **260 条测试全部通过**，无回归。

### Frontend modernization: real-time form validator (OPT-P2-14 · F3-a)

- **`CronFormValidator` Vue 3 组件：**挂载在 `cron_add.html` 和 `cron_edit.html` 表单的 `<div id="cron-form-validator">`。通过原生 DOM `input`/`change` 事件监听现有表单字段，实时更新插入在调度字段与 URL 字段之间的预览区。
- **人性化调度预览：**将 `cron_schedule_display.py` 的 `humanize_schedule()` 逻辑移植至 JavaScript；以绿色 pill 显示可读描述（"每天 09:30"、"每 5 分钟"、"每周一 08:00" 等）及组合表达式（`dow day hour:minute[:second]`）。全客户端，无后端请求。
- **范围校验：**对 `minute`（0–59）、`hour`（0–23）、`day`（1–31）、`second`（0–59）及 `*/n` 步进语法做即时合法性检查，非法时以红色 strip 提示。不替代 `cron_validator.py` 的服务端校验。
- **URL 格式检查：**实时校验 `req_url`，若不以 `http://` 或 `https://` 开头则显示行内错误。
- **JSON Body 检查：**`req_method=POST` 时校验 `req_body` 是否为合法 JSON 对象，否则显示行内错误。
- **CSS 提取：**`cron-form-validator.css`（< 1 KB）提交至 `app/static/dist/`，通过 `<link>` 引入两个表单页；JS bundle（`cron-form-validator.js`，68 KB）为自包含 IIFE。
- **零布局变化：**挂载 `<div>` 插入在 `#cron_div` 和 URL 行之间；现有字段、标签、提交行为完全不变。组件为纯追加。
- **三 bundle 构建：**`npm run build` 依次运行三个 Vite config（`cron-status-cell.js`、`cron-filter-bar.js`、`cron-form-validator.js`）。CI 门禁已更新（含 `cron-form-validator.css`）。
- **222 单元测试全绿**，无回归。

### Frontend modernization: reactive filter bar + toast abstraction (OPT-P2-14 · F2)

- **CronFilterBar Vue 3 component (F2-a):** 任务列表筛选栏（原 `<form method="GET">`）改为 Vue 3 组件，挂载在 `<div id="cron-filter-bar">`。点击异常/状态 chip 或切换业务组，仅 fetch `GET /?partial=1&…` 更新 `<tbody>` 与分页，通过 `history.replaceState` 更新 URL，无整页刷新。搜索输入防抖 150 ms。
- **零视觉变化：**Vue 组件模板与原服务端渲染的 form 使用完全相同的 HTML 结构和 CSS class（chip 样式、布局、按钮文案逐一对照）。
- **后端 partial 端点：**`cron_list()` 在 `?partial=1` 时返回 `jsonify({'rows': …, 'pagination': …})`；行 HTML 提取为 `_cron_list_rows.html`，分页提取为 `_cron_pagination.html`；全页与局部路径共享同一查询/筛选逻辑。
- **CronStatusCell 重挂载：**`cron-status-cell.js` 暴露 `window.CronStatusCell.mountAll()`（跳过已标记 `.cron-ops-mounted` 的元素）；FilterBar 每次 tbody 更新后调用，确保操作按钮在筛选结果上仍可用。
- **`useCronToast` composable (F2-b · B1):** 将 `artConfirm` / `artAlert` 从 `CronStatusCell.vue` 提取为 `src/composables/useCronToast.js`；内部仍封装 `Wind.use('artDialog', …)` + 原生降级，零视觉变化，但 Vue 组件不再直接依赖全局 `Wind` 变量。
- **双 bundle 构建：**`npm run build` 依次运行两个 Vite config，输出 `cron-status-cell.js`（68 KB）和 `cron-filter-bar.js`（70 KB）两个自包含 IIFE，均提交至 `app/static/dist/`。CI 门禁已更新。

## [2.4.0] — 2026-07-27 · 前端现代化（Vite + Vue 3）+ 管理端 UX 优化

### Internal: dead static asset cleanup (F0-a)

- Removed `app/static/vue.js` (280 KB): a Vue 2.x library committed but never referenced by any template or Python file; its presence previously created a misleading impression that Vue was already integrated.
- Removed additional unused static files confirmed to have zero template or CSS references: `images/mini_code.png`, `js/qrcode.min.js`, `js/artDialog/skins/blue.css` and the entire `blue/` skin directory (artDialog loads only the `default` skin), the entire `js/simpleboot/font-awesome/4.2.0/` directory (superseded by 4.4.0), and the entire `js/simpleboot/themes/bluesky/` directory (only the `flat` theme is in use).
- No behavior change. All 219 existing tests pass.
- F0-b (IE 8/9 `html5shiv` shim in `admin_base.html`) removed: confirmed no active IE 8/9 users; eliminates an external CDN dependency (`oss.maxcdn.com`) from the base template.

### Frontend modernization: Vite + Vue 3 component pilot (OPT-P2-14 · F1)

- **Vite build chain introduced (`frontend/`):** A minimal `frontend/` directory contains `package.json` (Node ≥ 18, Vite 6 + `@vitejs/plugin-vue` 5 + Vue 3.5), `vite.config.js` (IIFE lib mode, output to `app/static/dist/`), and the `CronStatusCell` Single File Component. `frontend/node_modules/` is gitignored; `app/static/dist/` is committed so deployment requires no Node.js.
- **`CronStatusCell` Vue 3 component (F1-b):** The cron list "Status & Operations" column is now rendered by a Vue 3 component mounted via `data-*` attributes on `<div id="cron-ops-{id}">`. The component provides: reactive status badge (enabled / paused / retired), "运行记录" link, "立即执行" button (CSRF-protected POST, `csrfFetch`), a "更多" dropdown with "启动/暂停", "编辑", and "下线" actions — all gated by `data-can-write` / `data-can-retire` props rendered server-side. No page reload for status toggle (badge updates in place).
- **Two-column layout preserved:** Status badge (`cron-life-cell`, Jinja-rendered with `id="status-badge-N"`) and operations (`cron-ops-cell`, Vue-mounted) remain two independent `<td>` columns, matching the original layout.
- **Defense-in-depth:** `data-update-url`, `data-run-url`, `data-edit-url` only emitted when user has `cron:write`; `data-retire-url` only when user has `cron:retire`.
- **Bug fix — URL double-append:** `onRunNow` / `onToggle` previously appended `?id=N` to a URL already containing `?id=N` from Jinja `url_for`, producing `endpoint?id=1?id=1` and a "任务不存在" error. Fixed by using `props.runUrl` / `props.updateUrl` directly. Guard test `test_run_url_already_contains_id_param` added.
- **UX fix — run-now no longer forces page navigation:** After a successful "立即执行", the result log detail now opens in `open_iframe_dialog` (same as the "运行记录" button), keeping the user on the task list. Fallback: inline link if unavailable.
- **Terminology fix:** `job_log_detail.html` label changed from "回调: <url>" to "触发 URL: <url>", and "由回调方…写入" to "由业务方上报".
- **Test coverage:** Added `test_vue_mount_point_data_attrs_present` asserting all 10 `data-*` props and the Vue bundle script tag are server-rendered in the cron list HTML. Existing permission tests updated to check `data-can-write` / `data-can-retire` attributes instead of jQuery-rendered button text. New integration test `test_cron_ops_integration.py` covers URL format, CSRF header validation, and RBAC permission enforcement via real HTTP session.
- **CI gate (F1-c):** New `.github/workflows/frontend-build.yml` runs `npm ci && npm run build` on changes to `frontend/**` or `app/static/dist/**`, then fails if the committed dist file diverges from the freshly-built output.
- **Process guard:** `.cursor/rules/cronpilot-format-guard.mdc` extended with explicit HTML visible-structure constraints (table headers, colspan, button text, CSS class additions) to prevent out-of-scope AI edits.

### UX: password visibility toggle on all password fields

- **Login page** and **change-password page** now show a Font Awesome eye icon absolutely-positioned inside each password input field.
- Default state: `fa-eye-slash` + `type="password"` (password hidden). Click to toggle to `fa-eye` + `type="text"` (password visible).
- **jQuery 1.8 compatibility:** uses native DOM `inp.type = …` instead of jQuery `.attr('type', …)` which silently fails in all major browsers.
- No new dependencies; uses Font Awesome 4.4.0 already loaded by the admin base template.

## [2.3.0] — 2026-07-24 · API 契约规范化（OpenAPI 3.0 + Swagger UI）

### API contract standardization (OPT-P1-CONTRACT)

- **OpenAPI 3.0 + Swagger UI:** API 层自动生成 OpenAPI 3.0 规范，通过 `/api/openapi.json` 提供；交互式 Swagger UI 可通过 `/api/swagger` 访问（也嵌入已有的 API 文档管理面板 tab）。
- **Schema-based request validation:** `POST /api/cron`、`POST /api/cron/status`、`POST /api/cron/retire` 和 `POST /api/cron/add_log` 现在通过 marshmallow schemas 在业务逻辑前校验必填字段。缺少或无效字段返回 HTTP 422 及字段级错误映射：`{"errcode": 1, "errmsg": "参数校验失败", "data": {"fields": {...}}}`。
- **Centralized access\_token auth:** Token 验证（`conf.ini` 中 `api_access_token`）现在集中在 Blueprint `before_request` 钩子中，而不是分散在各视图函数里。同时接受 `Authorization: Bearer <token>` 头和旧版 `access_token` 查询/表单参数。
- **Backward-compatible legacy path:** `GET /api/cron/add`（旧版双方法路由）继续正常工作。
- **新依赖：**`apiflask==2.4.0` 及其传递依赖（marshmallow、webargs、flask-httpauth、flask-marshmallow、apispec）。无数据库 schema 变更。

### API 文档面板 UI 改进

- 页面标题对齐、Swagger UI 内嵌精简（隐藏冗余 Servers/标题块）、无参数操作自动隐藏 "No parameters" 节。

## [2.2.0] — 2026-07-24 · 可观测性（结构化日志 + Prometheus 指标）+ Bug 修复

### Bug fixes

- **CSRF token missing from AJAX form submissions (B-1):** `common.js` `js-ajax-form` 处理器调用 `$.ajaxSubmit()` 时未在 `beforeSubmit` 回调中注入 `csrf_token`，导致所有 AJAX 表单提交被拒绝。修复：在 `beforeSubmit` 内从 `<meta name="csrf-token">` 注入。新增全链路集成测试 `tests/test_csrf_integration.py`。
- **Timestamp `%f` literal in JSON logs (B-2):** `_CronPilotJsonFormatter` 使用 `time.strftime()` 处理 `%f`（微秒），但该扩展仅 `datetime.strftime()` 支持，导致日志时间戳中出现字面量 `%f`。修复：覆写 `formatTime()`。
- **Logout CSRF:** `/rbac/logout` 接受无验证的 GET，允许跨域请求静默退出用户。修复：添加 `@csrf_protect`，顶栏和强制重置退出 UI 改为内联 `<form method="post">`。

### Structured JSON logging

- 两个日志文件均发出单行 JSON，包含 `timestamp`、`level`、`trace_id`、`cron_id`、`duration_ms` 等结构化字段。
- HTTP 追踪 ID（`X-Request-Id` 或自动生成 UUID4）在请求期间的所有日志中传播。
- 新依赖：`python-json-logger==2.0.7`。

### Prometheus metrics

- `/metrics` 端点（可配置 Bearer token 保护）暴露 `cronpilot_jobs_total`、`cronpilot_job_duration_seconds`、`cronpilot_active_jobs` 等指标，供 Prometheus 抓取。

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

## Version index

| Version | Highlights |
| --- | --- |
| **2.7.0** | Admin scope differentiation, audit log scope filtering, search, time-column indexing, doc reorganization |
| **2.6.0** | Color system consolidation, API access\_token hardening, S6 user-level token, query-only API docs |
| 2.5.0 | Execution state machine (B1) + per-task timeout (B2) + frontend form validator (F3-a) |
| 2.4.0 | Frontend modernization (Vite + Vue 3), reactive filter bar, password visibility toggle |
| 2.3.0 | API contract standardization (OpenAPI 3.0 + Swagger UI) |
| 2.2.0 | Structured JSON logging, Prometheus metrics, CSRF / timestamp bug fixes |
| **2.1.1** | Cluster mutex atomicity, production SECRET\_KEY, admin CSRF |
| 2.1.0 | Flask 2.3 + SQLAlchemy 2.0 runtime upgrade |
| 2.0.0 | Task center, GET/POST trigger, account lifecycle |
| 1.2.0 | Topbar identity, seed admin permissions, start/pause wording |
| 1.1.0 | Resource group isolation, self-service password change |
| 1.0.0 | Multi-user RBAC, task lifecycle, operation audit |
| 0.2.0 | Execution observability, dependency & deployment hardening |
| 0.1.1 | `/docs/` documentation portal, multi-version Python, CI |
| 0.1.0 | Initial release |

CronPilot · Release Notes · [Markdown](RELEASE_NOTES.md) · [索引](index.html)

---

[← 文档索引（HTML）](index.html) · [← 文档索引（Markdown）](index.md)
