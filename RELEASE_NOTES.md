# CronPilot Release Notes

本文档记录 **CronPilot** 版本变更。  
HTML 版：[doc/RELEASE_NOTES.html](doc/RELEASE_NOTES.html)

---

## [Unreleased]

Maintainer note: track unfinished work in [交付状态与路线图](doc/交付状态与路线图.html); do not use this section as a project status board.

### Time-column index enforcement (OPT-P2-17)

- **Model-level `index=True`:** All `create_time` / `update_time` / `created_at` / `updated_at` columns across 7 tables now carry `index=True` in their `mapped_column()` declaration.
- **Runtime index backfill:** `scripts/ensure_business_tables.py` → `_ensure_time_column_indexes()` idempotently creates `ix_<table>_<column>` indexes on service startup for existing databases.
- **Norm:** `.cursor/rules/cronpilot-backend.mdc` → "时间列索引规范" section: new models missing `index=True` on time columns are treated as review blockers.
- **Tables covered:** `rbac_audit_logs.create_time`, `rbac_users.create_time`, `resource_groups.create_time`, `cron_infos.created_at`, `cron_infos.updated_at`, `job_log.create_time`, `job_health.updated_at` (plus pre-existing `operation_log.create_time`).

### User management & audit log search (OPT-P2-17 prior items)

- **User management search:** Username fuzzy search on the user list page.
- **Audit log multi-dimensional search:** Filter by username (fuzzy), action, status, and time range.
- **UI style consistency:** Search toolbars refactored to use CSS classes; date inputs normalized; search buttons use `btn-info`.
- **Query performance norms:** `.cursor/rules/cronpilot-backend.mdc` → "查询性能评估" section mandates performance assessment for all new query features.
- **API token auto-issuance:** `ensure_existing_users_have_token()` auto-issues tokens for pre-S6 users on startup.

---

## [2.7.0] — 2026-08-03

### Admin scope differentiation (OPT-P2-15)

- **Seed admin vs. manager admin:** The built-in `admin` user (seed) now has **global read-only** scope — full visibility across all groups but no task write/retire. Non-seed admins ("manager admins") are scoped to explicitly assigned groups.
- **Virtual `__ALL__` group:** Manager admins can be assigned the virtual `__ALL__` marker to bypass group scoping, functioning as a global manager without seed privileges.
- **User management scope:** Manager admins can only view and manage users within their group intersection. The seed admin is **hidden** from manager admin user lists entirely (neither visible nor operable).
- **Group management:** Only bypass-scope admins (seed or `__ALL__` manager) can create new resource groups. Scoped manager admins see only their assigned groups.
- **Group selection UI:** Add/edit user forms enforce mutual exclusion between `__ALL__` and individual groups via client-side JavaScript.

### Audit log scope filtering (OPT-P2-16)

- **`actor_group_ids` column:** New `VARCHAR(255)` column on `rbac_audit_logs`, storing the acting user's group IDs in comma-wrapped format (e.g., `,1,3,`) at write time. `ensure_business_tables` handles idempotent DDL for existing databases.
- **Scoped query:** Manager admins see only audit records where the actor's groups intersect with their own, using `LIKE '%,<gid>,%'` filtering. Historical records without `actor_group_ids` are invisible to scoped admins.
- **Bypass users:** Seed admin and `__ALL__` manager admins retain full audit log visibility via `paginate_all()`.

### Documentation quality audit and fixes

- **README version table:** Added missing v2.2.0, v2.3.0, v2.4.0, v2.5.0 entries; expanded v2.6.0 description; updated current version indicator; added 4 missing CI workflows to GitHub Actions table; expanded directory structure; added `api_access_token` / `api_access_token_required` to config table.
- **Delivery roadmap (`doc/交付状态与路线图.html`):** Added missing v2.3.0 (API contract) and v2.4.0 (frontend modernization) version rows; fixed OPT-P1-06 status from "unstarted" to "delivered v2.3.0"; added OPT-P2-14/15/16 entries; added 10 delivery detail rows.
- **Numbering conflict resolution:** OPT-P2-12/ADMIN-SCOPE → **OPT-P2-15** (OPT-P2-12 was already used for Resource Scope v1.1.0); OPT-P2-13/AUDIT-SCOPE → **OPT-P2-16** (OPT-P2-13 was already used for 规模化信息架构 v2.0.0).

### Version consistency CI

- **`scripts/check_version_consistency.py`:** New CI script that verifies all `vX.Y.Z` git tags have corresponding entries in README version table, delivery roadmap, and RELEASE_NOTES. Checks README "current version" matches latest tag. Supports `--check` mode (exit 1 on mismatch).
- **`.github/workflows/version-consistency.yml`:** CI workflow triggered on push/PR when version-related files change; uses `fetch-depth: 0` for full tag access.

### Release process hardening

- **Release checklist** (`.cursor/rules/cronpilot-release-deploy.mdc`): Added explicit requirements for README version table update, roadmap version row, OPT/RFC status sync, and numbering collision pre-check.
- **Project rules** (`.cursor/rules/cronpilot-project.mdc`): Added "版本一致性" enforcement section with CI gate and numbering allocation procedure.

### Tests

- 341 tests pass, covering admin scope differentiation, audit log scope filtering (write + query + false-positive prevention + historical data invisibility), and all prior features.

---

## [2.6.0] — 2026-07-31

### Release scope (all commits after v2.5.0)

- Includes all commits in `v2.5.0..v2.6.0`: `8f683ce` and `8979424`.
- This release combines color-system hardening, API access-token hardening, user-level token UX completion, and query-only API documentation redesign.

### 前端颜色收编与可维护性加固

**核心改进：** 191 处硬编码十六进制颜色（分布在 21 个文件 / 57 个独立色值）全部收编为 CSS Custom Properties（`var(--cp-*)`）。替换前后视觉效果完全一致，颜色修改从"搜 21 个文件 191 处"简化为"改 `console-theme.css` 1 个变量"。

- **`app/static/css/console-theme.css`（新增）：** 60 个语义 CSS 变量，覆盖文字层级、背景/表面、边框、强调色、成功/危险/警告色系、执行状态机、角色徽标、Topbar、已下线 chip、链接色。`--cp-*` 前缀避免与 simpleboot/Bootstrap 冲突。
- **20 个 Jinja2 模板收编：** `admin_base.html`（15 处）、`cron_list.html`（68 处）、`cron_add.html`（15 处）、`cron_edit.html`（14 处）及其余 16 个模板文件，全部替换为 `var(--cp-*)` 引用。
- **Vue 组件收编：** `CronFormValidator.vue` 10 处硬编码颜色替换为 CSS 变量；构建产物 `cron-form-validator.css` 已更新。
- **语义类外迁：** `admin_base.html` 中的角色徽标（`.topbar-role-*`）与执行状态标签（`.label-timeout/running/pending/danger`）定义迁移到 `console-theme.css`，消除重复。
- **死文件清理：** 删除零引用的 `app/templates/_admin_nav.html`。

### 审计工具与 CI 门禁

- **`scripts/audit_hardcoded_colors.py`（新增）：** 全量扫描模板和 Vue 组件中的硬编码颜色。支持 `--check`（CI 模式，exit 1）、`--mapping`（色值→令牌映射表）、`--csv`（导出）。内置 57 色值 100% 映射。
- **`.github/workflows/color-audit.yml`（新增）：** CI 门禁，PR 中含硬编码颜色自动阻断。
- **`tests/test_form_name_guard.py`（新增）：** 3 个静态守护测试，防止表单迁移时意外修改 `CronFormValidator.vue` 依赖的 `name` 属性（`day_of_week`/`day`/`hour`/`minute`/`second`/`req_url`/`req_method`/`req_body`）。

### API access_token hardening (minimal Scope mitigation)

- New opt-in `conf.ini` setting `api_access_token_required` (default `0`, no behavior change). When set to `1`, production startup now fails fast if `api_access_token` is empty (`scripts/check_conf_production.py` + `config.ProductionConfig.init_app`), preventing unnoticed unauthenticated `/api/*` access.
- Failed API token checks now write an audit trail (`rbac_audit_logs`, `action='api:deny'`) for traceability.
- See [RBAC 与群组权限管理评审报告](doc/RBAC与群组权限管理评审报告.html) for the underlying review and [资源隔离与Scope设计 §七](doc/资源隔离与Scope设计.html#future) for scope/limitations (still a shared deployment-level token; per-group API tokens remain a future RFC).

### RBAC / API Token UX completion (S6)

- Added standalone token page `GET /rbac/api_token` and moved the entry before `API文档` in top nav.
- Added self-service reset `POST /rbac/api_token/reset` (`require_login` + CSRF) with 30-day expiry refresh, while keeping admin-side reset in user list.
- Added/expanded S6 tests (`tests/test_api_scope_s6.py`) to cover issuance, expiry, scope isolation, cache invalidation, and auto-reset on password/group mutation.

### API documentation redesign: query-only + permission-aware

- Rebuilt `GET /api_doc` as a native console-style page; removed embedded Swagger interaction from this admin view.
- Switched from HTTP-method filtering to query-semantic filtering and auto-hid incomplete entries.
- Added permission-aware catalog rendering with in-process cache keyed by permission set.
- Exposed read APIs for integrators: `GET /api/cron/query`, `GET /api/cron/logs`, `GET /api/cron/detail`, `GET /api/cron/log/detail`.
- Query APIs now include `total`/`has_more`; logs API supports `status`/`http_status`/time-range filters and `content_preview`.

### 部署文档

- **非 Docker 部署指南**新增 §3「前端开发环境」：Node.js 仅开发时需要、nvm 安装、Node.js 与 Python 环境隔离对比。
- **README.md** 新增 §2.1「前端开发环境（可选）」。

### 测试

- 322 个测试通过（覆盖颜色门禁、RBAC/S6、只读 API 文档目录与 Scope 查询接口）。

---

## [2.5.0] — 2026-07-29

### Per-task timeout configuration — Phase B2 (OPT-P1-01)

### 单任务超时配置 — Phase B2（OPT-P1-01）

- **`CronInfos.timeout_sec` 字段（可空 INT）：** NULL 表示使用系统默认 5 s；有效范围 1–120 s。`ensure_business_tables` 幂等 DDL 补列，存量数据库安全升级。
- **表单 UI：** 新增/编辑任务表单新增"超时（秒）"输入框（留空使用默认 5 s，最大 120 s）。
- **校验门禁（`cron_validator.py`）：** 非空时校验 1≤timeout_sec≤120，非整数/越界均返回 `timeout_sec` 字段错误。
- **执行路径（`cron_do`）：** 使用 `cif.timeout_sec or _DEFAULT_TIMEOUT_SEC` 动态读取 per-task 超时，默认值从 120 s 调整为 5 s。
- **API schema（`CronUpsertIn`）：** 新增可选 `timeout_sec` 整数字段（1–120），通过 APIFlask 文档自动暴露。
- **详情页：** `job_log_detail.html` 新增"超时限制 Xs"展示，与耗时字段并排显示。
- **测试（`test_b2_timeout_config.py`）：** 14 条新测试覆盖合法值、边界值、非法值（0/-1/121/非整数/浮点）、NULL 传播、service 写入。

### Execution state machine — Phase B1 (OPT-P1-01)

### 执行状态机 — Phase B1（OPT-P1-01）

- **4 终态 `job_log.status`（方案 B，单次写）：** `success | fail | timeout | error`。执行路径全程不写中间态 DB 记录，HTTP 完成后一次性落终态，保持与原方案相同的 DB 写放大系数（1 COMMIT/execution）。
- **`started_at` / `finished_at` 时间戳字段：** `started_at` 在 HTTP 派发前赋值（本地变量），随终态记录一同落库。`finished_at` = 终态落库时刻。`timeout_sec` 字段记录本次执行所用超时阈值。
- **`timeout` 状态区分：** `requests.Timeout`/`ConnectTimeout`/`ReadTimeout` 异常映射 `timeout`，其余映射 `error`；`fail_reason` 字段保留失败归因标签。
- **`ensure_business_tables` 补丁：** 幂等 DDL 添加 `started_at`、`finished_at`、`timeout_sec`；存量数据库安全升级。
- **`job_log_outcome.py`：** 新增 `STATUS_PENDING`、`STATUS_RUNNING`（供旧数据 badge 展示）、`STATUS_TIMEOUT` 常量；`is_timeout_exception()` 区分超时与连接异常。
- **Badge 渲染：** `_job_log_result_cell.html` 与 `job_log_detail.html` 通过 `job_log_status_badge_class` Jinja filter 渲染 `<span class="label label-*">`；详情页展示 `started_at`/`finished_at`。新增 `.label-timeout`（紫）、`.label-running`（蓝）、`.label-pending`（灰）全局样式。
- **高并发设计选型：** 方案 B 单次终态写，DB 写次数不变，适合 90%+ 快响应业务场景。`pending`/`running` 常量及样式保留，便于历史记录展示或未来按需启用中间态。
- **38 条新单元测试**（`tests/test_b1_execution_status.py`）：状态常量、`evaluate_http_response`、超时路由、`should_alert`、badge 映射、模型列存在性。
- **260 条测试全部通过**，无回归。

### Frontend modernization: real-time form validator (OPT-P2-14 · F3-a)

- **`CronFormValidator` Vue 3 component:** Mounts on `<div id="cron-form-validator">` in `cron_add.html` and `cron_edit.html`. Listens to form `input`/`change` events via the native DOM (no Jinja change needed) and reactively updates a preview strip placed between the cron scheduling fields and the URL field.
- **Humanized schedule preview:** Ports `humanize_schedule()` logic from `app/services/cron_schedule_display.py` to JavaScript. Displays a green pill with the humanized description ("每天 09:30", "每 5 分钟", "每周一 08:00", etc.) alongside the assembled cron expression (`dow day hour:minute[:second]`). Zero backend round-trips — all client-side.
- **Inline range validation:** Validates `minute` (0–59), `hour` (0–23), `day` (1–31), `second` (0–59) against their legal ranges and `*/n` step syntax. Shows a red error strip on invalid input. Does not duplicate or replace the existing server-side validation in `cron_validator.py`.
- **URL format check:** Validates `req_url` on the fly; shows an inline error if the value does not start with `http://` or `https://`.
- **JSON Body check:** When `req_method=POST`, validates `req_body` is a valid JSON object; shows inline error for malformed or non-object JSON.
- **CSS extracted:** `cron-form-validator.css` (< 1 KB) is committed to `app/static/dist/` and linked from both form pages; the JS bundle (`cron-form-validator.js`, 68 KB) is self-contained IIFE.
- **Zero layout change:** The mount `<div>` is inserted between `#cron_div` and the URL control-group; all existing form fields, labels, and submit behavior are untouched. The validator is purely additive.
- **Triple-bundle build:** `package.json` now runs three sequential `vite build` commands (`cron-status-cell.js`, `cron-filter-bar.js`, `cron-form-validator.js`). CI gate updated to mention all four output files (3 JS + 1 CSS).
- **222 unit tests pass** — no regressions.

### Frontend modernization: reactive filter bar + toast abstraction (OPT-P2-14 · F2)

- **CronFilterBar Vue 3 component (F2-a):** The cron list filter toolbar (`<form method="GET">`) is replaced by a Vue 3 component (`CronFilterBar.vue`) mounted on `<div id="cron-filter-bar">`. Clicking health/status chips or changing the scope select now fetches only the `<tbody>` rows and pagination via `GET /?partial=1&…`, updates the DOM in-place, and pushes the URL via `history.replaceState` — no full page reload. Search input is debounced 150 ms.
- **Zero visual change:** The Vue component renders the exact same HTML structure and CSS classes as the original server-rendered form. All chip styles (`cron-chip-fail`, `cron-chip-run`, etc.), layout, and button labels are preserved pixel-for-pixel.
- **Server-side partial endpoint:** `cron_list()` view returns `jsonify({'rows': …, 'pagination': …})` when `?partial=1` is present. Row HTML extracted to `_cron_list_rows.html`; pagination to `_cron_pagination.html`. Full-page and partial paths share the same query/filter logic.
- **CronStatusCell re-mount after DOM replace:** `cron-status-cell.js` now exposes `window.CronStatusCell.mountAll()` (skips elements already marked `.cron-ops-mounted`). `CronFilterBar` calls `mountAll()` after each `<tbody>` update so operation buttons remain functional on filtered results.
- **`useCronToast` composable (F2-b · B1):** Extracted `artConfirm` / `artAlert` from `CronStatusCell.vue` into `src/composables/useCronToast.js`. Internally still wraps `Wind.use('artDialog', …)` with a native `confirm()/alert()` fallback — zero visual change, but Vue components no longer depend on the global `Wind` variable being present at import time.
- **Dual-bundle build:** `package.json` build script now runs `vite build && vite build --config vite.config.filter-bar.js` producing two self-contained IIFEs: `cron-status-cell.js` (68 KB) and `cron-filter-bar.js` (70 KB). Both are committed to `app/static/dist/`. CI gate updated.

---

## [2.4.0] — 2026-07-27 · 前端现代化（Vite + Vue 3）+ 管理端 UX 优化

### Internal: dead static asset cleanup (F0-a)

- Removed `app/static/vue.js` (280 KB): a Vue 2.x library that was committed but never referenced by any template or Python file; its presence previously created a misleading impression that Vue was already integrated.
- Removed unused static files confirmed to have zero template or CSS references: `images/mini_code.png`, `js/qrcode.min.js`, `js/artDialog/skins/blue.css` and the entire `blue/` skin directory (artDialog loads only the `default` skin), the entire `js/simpleboot/font-awesome/4.2.0/` directory (superseded by 4.4.0 which is the only version referenced), and the entire `js/simpleboot/themes/bluesky/` directory (only the `flat` theme is in use).
- No behavior change. All 219 existing tests pass.
- F0-b (IE 8/9 `html5shiv` shim in `admin_base.html`) removed: confirmed no active IE 8/9 users; eliminates an external CDN dependency (`oss.maxcdn.com`) from the base template.

### Frontend modernization: Vite + Vue 3 component pilot (OPT-P2-14 · F1)

- **Vite build chain introduced (`frontend/`):** A minimal `frontend/` directory contains `package.json` (Node ≥ 18, Vite 6 + `@vitejs/plugin-vue` 5 + Vue 3.5), `vite.config.js` (IIFE lib mode, output to `app/static/dist/`), and the `CronStatusCell` Single File Component. `frontend/node_modules/` is gitignored; `app/static/dist/` is committed so deployment requires no Node.js.
- **`CronStatusCell` Vue 3 component (F1-b):** The cron list "Status & Operations" column is now rendered by a Vue 3 component mounted via `data-*` attributes on `<div id="cron-ops-{id}">`. The component provides: reactive status badge (enabled / paused / retired), "运行记录" link, "立即执行" button (CSRF-protected POST, `csrfFetch`), a "更多" dropdown with "启动/暂停", "编辑", and "下线" actions — all gated by `data-can-write` / `data-can-retire` props rendered server-side. No page reload for status toggle (badge updates in place).
- **Two-column layout preserved:** Status badge (`cron-life-cell`, Jinja-rendered with `id="status-badge-N"`) and operations (`cron-ops-cell`, Vue-mounted) remain two independent `<td>` columns, matching the original layout.
- **Defense-in-depth:** `data-update-url`, `data-run-url`, `data-edit-url` only emitted when user has `cron:write`; `data-retire-url` only when user has `cron:retire`.
- **Bug fix — URL double-append:** `onRunNow` / `onToggle` previously appended `?id=N` to a URL already containing `?id=N` from Jinja `url_for`, producing `endpoint?id=1?id=1` and a "任务不存在" error. Fixed by using `props.runUrl` / `props.updateUrl` directly. Guard test `test_run_url_already_contains_id_param` added.
- **UX fix — run-now no longer forces page navigation:** After a successful "立即执行", the result log detail now opens in an `open_iframe_dialog` (same as the "运行记录" button), keeping the user on the task list. Fallback: inline link if `open_iframe_dialog` is unavailable.
- **Terminology fix:** `job_log_detail.html` label changed from "回调: <url>" to "触发 URL: <url>", and "由回调方…写入" to "由业务方上报", eliminating confusing "callback" framing.
- **Test coverage:** Added `test_vue_mount_point_data_attrs_present` asserting all 10 `data-*` props and the Vue bundle script tag are server-rendered in the cron list HTML. Existing permission tests updated to check `data-can-write` / `data-can-retire` attributes instead of jQuery-rendered button text. New integration test `test_cron_ops_integration.py` covers URL format, CSRF header validation, and RBAC permission enforcement via real HTTP session.
- **CI gate (F1-c):** New `.github/workflows/frontend-build.yml` runs `npm ci && npm run build` on changes to `frontend/**` or `app/static/dist/**`, then fails if the committed dist file diverges from the freshly-built output.
- **Process guard:** `.cursor/rules/cronpilot-format-guard.mdc` extended with explicit HTML visible-structure constraints (table headers, colspan, button text, CSS class additions) to prevent out-of-scope AI edits.

### UX: password visibility toggle on all password fields

- **Login page (`/rbac/login`)** and **change-password page (`/rbac/change_password`)** now show a Font Awesome eye-slash icon (`fa-eye-slash` / `fa-eye`) absolutely-positioned inside the password input field.
- Default state: `fa-eye-slash` + `type="password"` (password hidden). Clicking toggles to `fa-eye` + `type="text"` (password visible), following standard UX convention.
- **jQuery 1.8 compatibility note:** jQuery 1.8's `.attr('type', …)` silently fails to change an input's `type` attribute in all major browsers. The toggle uses native DOM `inp.type = …` instead.
- No new dependencies; uses Font Awesome 4.4.0 already loaded via the admin base template.

---

## [2.3.0] — 2026-07-24 · API 契约规范化（OpenAPI 3.0 + Swagger UI）

### API contract standardization (OPT-P1-CONTRACT)

- **OpenAPI 3.0 + Swagger UI:** The API layer now auto-generates an OpenAPI 3.0 specification, served at `/api/openapi.json`. Interactive Swagger UI is accessible at `/api/swagger` (also embedded in the existing **API Documentation** management panel tab).
- **Schema-based request validation:** `POST /api/cron`, `POST /api/cron/status`, `POST /api/cron/retire`, and `POST /api/cron/add_log` now validate required fields via marshmallow schemas before reaching business logic. Missing or invalid fields return HTTP 422 with a field-level error map: `{"errcode": 1, "errmsg": "参数校验失败", "data": {"fields": {...}}}`. The existing `{errcode, errmsg, data}` envelope is preserved for callers.
- **Centralized access_token auth:** Token validation (`api_access_token` in `conf.ini`) is now enforced in a single Blueprint `before_request` hook instead of being scattered across each view function. Both `Authorization: Bearer <token>` header and legacy `access_token` query/form parameter are accepted.
- **Backward-compatible legacy path:** `GET /api/cron/add` (the old dual-method route) continues to work unchanged for existing callers.
- **Upgrade notes:** Added `apiflask==2.4.0` and its transitive dependencies (`marshmallow`, `webargs`, `flask-httpauth`, `flask-marshmallow`, `apispec`) to `requirements.txt`. No database schema changes. No configuration file changes required.

### API documentation panel UI improvements

- **Page header alignment:** The API documentation management panel (`/api_doc`) now includes the standard CronPilot jumbotron header ("CronPilot 定时调度平台 / 方便、统一、自由"), consistent with all other admin pages.
- **Swagger UI clean-up (embedded view):** The embedded Swagger UI iframe now hides three redundant/developer-facing elements: the `/api/openapi.json` title link, the Servers dropdown, and the "CronPilot 1.0.0 OAS 3.0" block (already present in the jumbotron). These elements remain visible in the standalone `/api/swagger` URL for developer use.
- **Empty Parameters section hidden:** When an API operation has no URL/query/header parameters (all input is in the request body), the "Parameters / No parameters" section is automatically hidden by a `MutationObserver`-based JavaScript injection, leaving only "Request body" and "Responses" visible. Implemented with DOM-verified selectors (`.parameters-container > .opblock-description-wrapper` + `textContent === "No parameters"`) and a 100 ms polling fallback for delayed React renders.
- **Seamless iframe embed:** The iframe border is removed; Swagger UI content flows directly into the admin panel layout.

### Engineering conventions

- Added **DOM-first browser testing protocol** to `.cursor/rules/cronpilot-project.mdc`: before writing CSS selectors or JavaScript targeting third-party UI library DOM, use CDP `Runtime.evaluate` to inspect actual element structure; verify logic via dry-run query; require CDP `display:none` evidence before reporting a browser-side fix as complete.

---

## [2.2.0] — 2026-07-24 · 可观测性（结构化日志 + Prometheus 指标）+ Bug 修复

### Bug fixes (post-release patch, included in 2.2.0)

- **CSRF token missing from AJAX form submissions (B-1):** `common.js` `js-ajax-form` handler called `$.ajaxSubmit()` without injecting the `csrf_token` in the `beforeSubmit` callback — every AJAX form submission (create group, add user, etc.) was rejected with "csrf校验失败". Fixed by adding CSRF token injection from `<meta name="csrf-token">` inside `beforeSubmit`. Added full-chain integration tests (`tests/test_csrf_integration.py`) using `requests.Session` to prevent regression.
  - *Root cause:* The `js-ajax-dialog-btn` code path already had CSRF injection; the `js-ajax-form` path did not. Python unit tests operate via `test_client.post(data={csrf_param: token})` and bypass the JavaScript layer entirely, so the bug was invisible to the test suite.
- **Timestamp `%f` literal in JSON logs (B-2):** `_CronPilotJsonFormatter` was initialised with `datefmt='%Y-%m-%dT%H:%M:%S.%f%z'`, but `logging.Formatter.formatTime()` calls `time.strftime()` internally — `%f` (microseconds) is a `datetime.strftime()` extension not supported by `time.strftime()`, causing the literal string `%f` to appear in every log timestamp. Fixed by overriding `formatTime()` in `_CronPilotJsonFormatter` to use `datetime.datetime.fromtimestamp()`. Added `tests/test_logging_format.py` asserting that the timestamp is free of `%f` literals and parseable via `datetime.fromisoformat()`.
- **Logout CSRF (forced-logout attack):** `/rbac/logout` accepted unauthenticated `GET` and `POST` with no CSRF check, allowing an attacker to embed a cross-origin request that logs out the victim silently. Fixed by adding `@csrf_protect` to `/rbac/logout` and changing the topbar and force-reset logout UI from `<a href>` GET links to inline `<form method="post">` with `csrf_token`.

### Post-release process note

The original v2.2.0 tag (`20dd148`) was released before the above bugs were discovered and fixed. The tag has been moved to the current HEAD to include the three fixes above; all 219 unit tests pass on the re-tagged commit.

### Structured JSON logging

- **JSON log format:** Both `datas/logs/info.log` and `datas/logs/error.log` now emit one JSON object per line, enabling direct ingestion by Filebeat / Promtail for ELK or Loki.
- **Structured fields:** Every record contains `timestamp` (ISO 8601), `level`, `logger`, `message`, `filename`, `lineno`, `thread`, and five context fields: `trace_id`, `cron_id`, `task_name`, `duration_ms`, `status` (null when not applicable).
- **HTTP trace ID:** Each web request automatically receives a `trace_id` UUID4 (sourced from the `X-Request-Id` request header, or auto-generated). The ID propagates to all log records emitted during that request.
- **Scheduler context:** `cron_do` injects `cron_id`, `task_name`, `duration_ms`, and execution `status` (`ok`/`error`) into every log record produced during the job run.
- **Unified handler:** All module loggers (`getLogger(__name__)`) and APScheduler's internal logger now write to the same JSON file handlers via root-logger propagation, closing a previous blind-spot where module-level log calls were silently dropped.
- **Configurable:** Add `log_level` (default `INFO`) and `log_json_enabled` (default `1`) to `conf.ini` `[default]` section to override at deploy time. Set `log_json_enabled=0` for plain-text output in local development.
- **Dependency:** `python-json-logger==2.0.7` added to `requirements.txt` (Apache-2.0, no transitive dependencies).

### Gunicorn JSON access log

- **`app/gunicorn_logger.CronPilotLogger`:** Custom Gunicorn logger class that writes one JSON record per HTTP request to `datas/logs/access.log` (daily rotation, 7-day retention). Fields: `timestamp`, `level`, `logger`, `remote_addr`, `method`, `path`, `status`, `response_bytes`, `duration_ms`, `user_agent`, `referrer`.
- **`gun.py`:** Activated via `logger_class = 'app.gunicorn_logger.CronPilotLogger'`. Applies to Gunicorn production mode (`:5860`) only; local Flask dev server (`:5001`) is unaffected.
- Access log is independent of `info.log`/`error.log` and does not interfere with the JSON formatter or root-logger configuration.

### Logging hygiene: print() removed

- Removed a redundant `print(str(e))` from `cron_do`'s outer exception handler (the error is already emitted via `logger.error()`).
- Removed a debug `print(request.values.to_dict())` from the `/api/test` endpoint.
- Replaced `print(req.json())` in the DingTalk webhook helper with `current_app.logger.info(...)` so DingTalk responses appear in the structured JSON log.

### Structured log events in scheduler jobs

- Introduced a `event` field (via Python `logging` `extra=` dict) on all scheduler log calls in `app/crons.py`, enabling exact-match alerting rules in ELK/Loki without fragile `message` substring matching.
- Event enum: `cron.not_found` / `cron.url_missing` / `cron.url_invalid` / `cron.ssrf_blocked` / `cron.http_ok` / `cron.http_error` / `cron.exception` / `cron.fatal` / `health.update_failed` / `cron_check.exception` / `cron_del_job_log.exception` / `cron_del_operation_log.exception`.
- Variable context (e.g. `error`, `exc_type`, `http_status`, `fail_reason`, `traceback`, `url`, `reason`) is carried as sibling JSON fields alongside `event`.
- Removed all `logger.error("==============")` separator lines — JSON records are self-contained and don't need visual delimiters.

### Docker image pin verification

- **Compose verify:** `bash scripts/verify_docker_compose.sh --rebuild` asserts that Framework packages inside the image match `requirements.txt` (Flask / Werkzeug / Jinja2 / SQLAlchemy / Flask-SQLAlchemy / alembic / Flask-Migrate / blinker).
- **Build & run fixes:** image build-time health check supplies a strong `SECRET_KEY`; compose verify writes container SQLite paths into `conf.ini` and tolerates host `datas/` ownership for the `cronpilot` user.
- **Smoke reliability:** HTTP smoke checks use UTF-8 locale and avoid `pipefail` false failures when grepping large HTML pages.

### Prometheus metrics (OPT-P1-can — RFC: doc/P1可观测性-Prometheus指标RFC.html)

- **`app/metrics.py`** — centralised metric declarations; five metrics:
  - `cronpilot_job_total` (Counter, labels `task_name`/`status`)
  - `cronpilot_job_duration_seconds` (Histogram, labels `task_name`/`status`)
  - `cronpilot_job_trigger_delay_seconds` (Histogram, label `task_name`)
  - `cronpilot_job_log_write_bytes` (Histogram — content-size distribution)
  - `cronpilot_jobs_active` (Gauge, label `state`: `active`/`retired`)
  - NoOp fallback silently absorbs all calls if `prometheus_client` is absent.
- **`app/crons.py`** — `cron_do` observes `JOB_DURATION`, `JOB_TOTAL`, `JOB_LOG_WRITE_BYTES`, and `TRIGGER_DELAY` (enqueue→start delay via `_ctx_enqueue_time`); `cron_check` updates `JOBS_ACTIVE` gauge after each reconciliation cycle.
- **`app/common/functions.py`** — `single_task` decorator records enqueue timestamp in `_ctx_enqueue_time` ContextVar before invoking the wrapped function.
- **`gun.py`** — sets `PROMETHEUS_MULTIPROC_DIR` (`datas/prometheus_tmp/`) so per-worker mmap files are aggregated correctly by `MultiProcessCollector` in Gunicorn multiprocess mode.
- **`/metrics` endpoint** — registered in `create_app`; requires authenticated login; uses `MultiProcessCollector` when `PROMETHEUS_MULTIPROC_DIR` is set, falls back to `generate_latest()` for single-process (local) mode.
- **Bearer Token auth** — `conf.ini` optional `metrics_token`; when set, Prometheus server can scrape `/metrics` via `Authorization: Bearer <token>` without a browser session. Falls back to session-based auth when token is empty.
- **`task_name` cardinality guard** — label value truncated to 50 characters in `cron_do` to prevent high-cardinality explosion if dynamic task names are introduced.
- **`doc/prometheus.yml.example`** — ready-to-use Prometheus scrape config with Bearer Token, relabeling, and example alerting rules (failure rate, P95 duration, trigger delay, zero-active-jobs).
- **Dependencies:** `prometheus_client==0.20.0`, `prometheus-flask-exporter==0.23.1` added to `requirements.txt` (Apache-2.0).

---

## [2.1.1] — 2026-07-21 · Security hardening (cluster lock, SECRET_KEY, CSRF)

Hardens cluster mutex, production session signing, and admin write CSRF. **Scheduling callbacks and `/api/*` contracts are unchanged.** Supported Python remains **3.8–3.11**.

### Security & reliability

- **Cluster mutex:** When `is_single` is not single-node mode, task execution locks use atomic Redis `SET NX EX` and release only the holder’s token (avoids a race that could run the same job on two nodes, and avoids deleting another node’s lock after TTL expiry).
- **Session signing:** Production (`FLASK_CONFIG=production`) refuses to start with a missing, default, or short `SECRET_KEY`. Set `export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"`, or start via `scripts/run_production.sh` (first run writes `datas/.flask_secret_key`). Multi-node deployments must share the same key.
- **Admin CSRF:** State-changing admin actions require `POST` plus a session CSRF token (page meta / form field). Dialog actions such as pause/resume and run-now use POST. Hard-refresh the admin UI after upgrade.

### Upgrade notes

1. Before upgrading a production host that starts Gunicorn **without** `run_production.sh`, set a strong `SECRET_KEY` in the environment (or systemd unit); otherwise the process will fail fast on purpose.
2. Restart CronPilot after upgrade; **hard-refresh** the admin UI (CSRF meta tokens are embedded in pages).
3. Single-node trial (`is_single=1`) behavior is unchanged for Redis locking.
4. Do not use bookmark/GET URLs for pause/resume or run-now; those routes are POST-only.

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
| **2.6.0** | 颜色系统收编 + API access_token 加固 + S6 用户级 Token + 查询式 API 文档 |
| 2.5.0 | 执行状态机（B1）+ 单任务超时（B2） |
| **2.1.1** | 集群锁原子化、生产 SECRET_KEY、管理端 CSRF |
| 2.1.0 | Flask 2.3 + SQLAlchemy 2.0 运行时 |
| 2.0.0 | 任务中心、POST 触发、账户生命周期 |
| 1.2.0 | 顶栏身份、种子权限、启停用语 |
| 1.1.0 | 业务组隔离、自助改密 |
| 1.0.0 | 多用户权限、生命周期、操作审计 |
| 0.2.0 | 执行可观测、依赖与部署加固 |
| 0.1.1 | 文档 `/docs/`、多版本 Python、CI |
| 0.1.0 | 首发 |
