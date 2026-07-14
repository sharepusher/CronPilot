# CronPilot · RBAC 落地路线 v4

> HTML 版：[RBAC落地路线.html](RBAC落地路线.html) · [文档索引](index.html) · [索引 Markdown](index.md)

[← 文档索引](index.html)
OPT-P2-10路线v4

# RBAC 落地路线

分阶段实施 · 验收门禁 · PR 切分 · 与 v4 详设对齐

目标版本：**v1.0.0** · 状态：代码与文档已齐 · 待打 tag（阶段 1～7、2.5、2.6、R2/R3 均已交付）

**权威详设：**[RBAC架构设计方案 v4](RBAC架构设计方案.html) ·
**交付总览：**[交付状态与路线图](交付状态与路线图.html) ·
**开发规范：**`.cursor/rules/rbac.mdc`、`cronpilot-format-guard.mdc`

## 一、前置条件（已满足）

| 项 | 状态 | 说明 |
| --- | --- | --- |
| Tier 0 · `flask db` | v0.2.0 已交付 | 迁移 CLI 可用 |
| Tier 1 · SA 1.4 | v0.2.0 已交付 | 新代码禁止 `Model.query` |
| 格式保留规则 | 已提交 | `cronpilot-format-guard.mdc` |
| v4 详设确认 | 已确认实施 | 2026-06 起按 v4 编码 |

## 二、里程碑总览

| 阶段 | 交付物 | 估时 | 可发布 |
| --- | --- | --- | --- |
| **0** 工程防护 | format-guard 规则（已完成可跳过） | 5 min | — |
| **1** 数据层 | 模型 + migrate | 0.5–1 d | 已交付 |
| **2** RBAC 核心 | `app/rbac/` policy/services/decorators/context（v4 性能） | 1–1.5 d | 已交付 |
| **2.5** 登录身份 | `/rbac/login`、`check_pass` 转发、logout | 0.5 d | 已交付 |
| **3** 导航迁移 | `_admin_nav` → `rbac/_nav.html` + `has_perm` 菜单 | 0.25 d | 已交付 |
| **2.6** 404 页 | 登录态/访客 `errors/404*.html` + `smoke_http_not_found` | 0.25 d | 已交付 |
| **4** 路由装饰器 | `main/views.py` 逐路由 `@require_permission` | 1 d | 已交付 |
| **5** 模板按钮 | 各页 `has_perm` 包裹（与阶段 4 同权限点配对） | 1 d | 已交付 |
| **6a** 用户管理 | `/rbac/users` CRUD、单测 | 0.5–1 d | 已交付 |
| **6b** 审计列表 | `/rbac/audit-logs`、单测 | 0.5 d | 已交付 |
| **7** 发布 | 三角色验收、文档、Release Notes v1.0.0 | 0.5 d | 文档/验收已齐 · 待 tag |

**合计：**约 5–7 个工作日（12–16 h 净编码 + 分批人工 `git diff` 约 30–40 min）。

## 三、阶段明细与验收门禁

### 阶段 0 — 格式风格保留（已完成可跳过）

确认 `.cursor/rules/cronpilot-format-guard.mdc` 存在且 `alwaysApply: true`。

**门禁：**规则文件在仓库中；后续模板 diff 无无关格式化行。

### 阶段 1 — 数据层与配置

- 新增 `datas/model/rbac_user.py`、`rbac_audit_log.py`
- `flask --app manage:app db migrate -m "add rbac tables"` + `upgrade`

**门禁：**`bash scripts/cronpilot.sh test`（含 `tests.test_rbac_phase`）；migrate / `ensure_sqlite_tables` 在 SQLite 可重复执行。

### 阶段 2 — RBAC 核心模块（v4 性能实现）

- `policy.py` — `ROLE_PERMISSIONS` + `has_permission`
- `services.py` — `get_role_permission_set`、`write_audit_log`
- `context.py` — `make_has_perm` 闭包外层预加载（v4 §8.1）
- `decorators.py` — `require_permission` + `full_path` next + Ajax/页面 403 分流
- `__init__.py` — Blueprint + `app_context_processor`
- `app/__init__.py` 注册 Blueprint（+2 行）

**门禁：**`tests/test_rbac_phase.py`（policy + 404）；已并入 `bash scripts/cronpilot.sh test`。

### 阶段 2.5 — 登录身份子阶段

- `views.py` — `/rbac/login` GET/POST、`/logout`
- `authenticate_user` — legacy 单密码 + `rbac_users`（`select` 查询）
- 模板 `rbac/login.html`、`forbidden.html`
- `check_pass` 仅改函数体：转发 + `next` 透传 + 307（v4 §8.2）

**门禁：**`username=admin&password=…` 可登录；空用户名被拒绝；带 query 的 `next` 登录后筛选条件不丢。

### 阶段 3 — 导航迁移（`_admin_nav` → `rbac/_nav`）

**前提：**v0.2.0 已交付 `_admin_nav.html`（OPT-P1-07），5 个主页面已 `include`，**非** 7 文件硬编码 Tab。本阶段只改 include 路径，再在 `rbac/_nav.html` 内加 `has_perm`。

| 批次 | 文件 | 改动 | 状态 |
| --- | --- | --- | --- |
| **3-A** | `cron_list.html`、`cron_add.html`、`cron_edit.html` | `_admin_nav` → `rbac/_nav.html` | 已实施 |
| **3-B** | `job_log_all_list.html`、`api_doc.html` | 同上 | 已实施 |

`job_log_list` / `job_log_item_list` 为详情子页单 Tab，不在本阶段范围。

每批人工检查：

```
git diff app/templates/cron_list.html app/templates/cron_add.html app/templates/cron_edit.html
git diff app/templates/job_log_all_list.html app/templates/api_doc.html
```

**门禁：**仅 include 路径变化 + `rbac/_nav.html` 内 `has_perm` 按角色裁剪菜单。**已验收。**

### 阶段 2.6 — 404 友好页（R2.5）

- `app/main/errors.py` — 按 `session['is_login']` 渲染 `errors/404.html` 或 `404_guest.html`
- `scripts/smoke_http.sh` — `smoke_http_not_found` 断言 HTTP 404 与页面文案；拒绝旧纯文本 handler

**门禁：**部署后须重启进程；`smoke_http_suite` 通过 `PASS not_found`。

### 阶段 4 + 5 — 权限点逐对落地（强关联）

每个权限点**同一 PR / 同一轮**同时改装饰器与模板，避免「后端拦了、按钮还在」或反之。

| 顺序 | permission | 视图 | 模板触点 |
| --- | --- | --- | --- |
| 1 | `cron:read` | `cron_list`、`api_doc` ✅ | —（基线） |
| 2 | `cron:write` | `cron_add`、`cron_edit`、`update_status` ✅ | 编辑、添加入口、启停 ✅ |
| 3 | `cron:retire` | `cron_retire` | 下线按钮（替代已废弃的 delete） |
| 4 | `log:read` | 三个 `job_log_*_list` + `job_log_detail` ✅ | — |
| 5 | ~~`log:delete`~~ | **废弃**：禁止人工删除流水（见 [生命周期设计](任务生命周期与无删除设计.html)） | |
| 6 | `user:manage` | `/rbac/users*` | 用户管理页（阶段 6）；仅 admin |
| 7 | `audit:read` | `/rbac/audit-logs` | RBAC 审计（阶段 6）；仅 admin |
| 8 | `operation:read` | `/operation_log_list` | 操作记录（OPT-P1-09）；operator+admin |

**废弃权限：**`cron:delete`、`log:delete`。任务终点为**下线**（`status=-1`），非物理删除。

**门禁：**每步 `unittest` + 手工：viewer / operator / admin 三角验证；Ajax 403 弹窗、页面 403 友好页。

### 阶段 6a — 用户管理（已交付）

- `/rbac/users`、`/users/add`、`/users/edit` + `create_user` / `update_user`
- 无物理删除；禁停用当前登录账号；保护最后一名启用中 admin
- 首次空表：种子 `admin`（密码=`login_pwd`）；\*\*无\*\* legacy\_admin
- `test_rbac_phase.TestRbacUsersManage` + 导航用例

**门禁：**`bash scripts/cronpilot.sh test`（含用户 CRUD / 403 / 最后 admin）；operator 不可进 `/rbac/users`。

### 阶段 6b — 审计列表（已交付）

- `/rbac/audit-logs` 只读分页；`@require_permission('audit:read')`（仅 admin）
- 导航「审计」：仅 `has_perm('audit:read')`（admin）；viewer/operator 不可见
- 与「操作记录」分工：业务变更走 `operation:read` / `/operation_log_list`（operator+admin）
- `test_rbac_phase.TestRbacAuditLogs`

**门禁：**operator/viewer 403；admin 可见登录等审计行；页面无 `js-ajax-form`。

### 阶段 7 — 发布（文档与验收已齐 · 待打 tag）

1. `bash scripts/cronpilot.sh test`（含 `TestRbacTriangularAcceptance`）
2. `RELEASE_NOTES` 已下沉 **v1.0.0** 节；`[Unreleased]` 清空为占位
3. [交付状态与路线图](交付状态与路线图.html)：OPT-P2-10 / LIFECYCLE → 已交付 v1.0.0（待 tag）
4. `python scripts/html_docs_to_markdown.py --check`
5. 运维：监控 `/check_pass` 307；登录须 `username=admin&password=…`
6. 确认后：`git tag v1.0.0` + GitHub Release（不自动执行）

## 四、建议 PR 切分

| PR | 阶段 | 说明 |
| --- | --- | --- |
| PR-R1 | 1 + 2 | 模型 + 核心模块 + 单测骨架；分权始终启用 |
| PR-R2 | 2.5 + 3 | 登录页 + `rbac/_nav` 迁移（3+2）；可独立灰度 |
| PR-R3 | 4 + 5 | 装饰器 + 模板（可按 permission 再拆 2–3 个 PR） |
| PR-R4 | 6 + 7 | 用户管理 + 文档 + Release |

## 五、与项目路线图关系

| 项 | 关系 |
| --- | --- |
| P1 小步 / P1-03/04 | 可并行排期；RBAC 独立里程碑不阻塞 |
| Tier 3 前置 | 无硬依赖；勿与 RBAC 首期同一 sprint 并行（减认知负担） |
| P1-09 `operation_log` | RBAC Session 字段为 P1 审计预留；可后接 |
| OAuth（P2-07） | 独立后续；v4 不展开 |

## 六、风险与运维

- **分权：**三角色矩阵始终生效；无 `rbac_enable` 配置项
- **体验：**`next` 与 `check_pass` 格式须与装饰器一致；改错误页/模板后**必须重启**长驻进程

CronPilot · RBAC 落地路线 v4 ·
[Markdown](RBAC落地路线.md) ·
[详设 v4](RBAC架构设计方案.html) ·
[索引](index.html)

---

[← 文档索引（HTML）](index.html) · [← 文档索引（Markdown）](index.md)
