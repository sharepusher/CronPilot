# V1 下线 Pre-check 报告 — 2026-08

> HTML 版：[V1下线Pre-check报告-2026-08.html](V1下线Pre-check报告-2026-08.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# V1 下线 Pre-check 报告

执行时间: 2026-08-26  | 
关联设计文档: <V1下线方案设计.html>  | 
目的: 确认 Batch 1（默认切换到 V2）的执行条件已满足

## 1. 检查结果总览

| # | 检查项 | 结果 | 风险 |
| --- | --- | --- | --- |
| 1 | 测试对 V1 模板的硬依赖 | PASS | 仅 `test_ajax_form_guard.py` 用 `admin_base.html` 作检测条件（非功能依赖），V2 通过 `"extends" in html` 分支正确处理 |
| 2 | V2 模板引用 V1 独有资源 | PASS | 0 引用。`common.js` / `wind.js` / `artDialog` / `simpleboot` / `bootstrap` 均不在 V2 模板中 |
| 3 | `ui_mode.py` 切换逻辑 | PASS | 逻辑清晰: Cookie → FORCE\_NEW\_UI 覆盖 → 白名单校验。Batch 1 仅改默认值 |
| 4 | V1→V2 路由对等覆盖 | PASS | 35 个 `ui_version` 分支全有 V2 render 路径；API-only 路由无模板不受影响 |
| 5 | V1 独有 JS 业务逻辑 | PASS | V1 核心操作（暂停/恢复/立即执行/下线/筛选/分页）在 V2 中有完整等价实现 |
| 6 | 本地/Docker 环境状态 | PASS | 本地已实质运行 V2（`start_local_full.sh` 强制），风险在未设环境变量的生产部署 |

## 2. 关键发现

### 发现 1: 本地环境已默认 V2

`scripts/start_local_full.sh` 第 49 行：

```
export CRONPILOT_FORCE_NEW_UI=true
```

`cronpilot.sh start` 和 `cronpilot.sh restart` 均调用此脚本。**所有使用 `cronpilot.sh` 启动的本地开发环境已经运行在 V2 模式下**。

**影响**: Batch 1 对本地开发者是事实生效状态。真正受影响的是：未使用 `cronpilot.sh` 的环境 / Docker 部署 / 生产环境。

### 发现 2: config.py 默认值仍为 'false'

```
CRONPILOT_FORCE_NEW_UI = os.environ.get(
    'CRONPILOT_FORCE_NEW_UI', 'false'
).lower() in ('1', 'true', 'yes')
```

Batch 1 的核心改动是将 `ui_mode.py` 中 cookie 默认值从 `'v1'` 改为 `'v2'`，对**未设置环境变量**的部署环境生效。

### 发现 3: 3 个测试文件显式设置 FORCE\_NEW\_UI

- `tests/test_dashboard_partial.py`
- `tests/test_exec_logs_partial.py`
- `tests/test_oplog_audit_partial.py`

这些测试验证 V2 partial rendering 逻辑，不受 Batch 1 影响。无需修改。

## 3. V1 → V2 模板对照表

| V1 模板 | V2 对应模板 | 状态 |
| --- | --- | --- |
| `cron_list.html` | `redesign/dashboard.html` | 完整对等 + 增强 |
| `cron_add.html` | `redesign/task_form.html` | 完整对等 |
| `cron_edit.html` | `redesign/task_form.html` | 完整对等（复用） |
| `cron_retire.html` | `redesign/cron_retire.html` | 完整对等 |
| `job_log_list.html` | `redesign/execution_logs.html` | 完整对等 + 增强 |
| `job_log_all_list.html` | `redesign/execution_logs.html` | 完整对等（合并） |
| `job_log_detail.html` | `redesign/run_inspector.html` | 完整对等 + 增强 |
| `job_log_item_list.html` | (redirect → run\_inspector) | V2 自动跳转 |
| `operation_log_list.html` | `redesign/operation_log.html` | 完整对等 + 增强 |
| `tag_manage.html` | `redesign/tags.html` | 完整对等 + 增强 |
| `api_doc.html` | `redesign/api_doc.html` | 完整对等 |
| `rbac/login.html` | `redesign/login.html` | 完整对等 |
| `rbac/register.html` | `redesign/register.html` | 完整对等 + 增强 |
| `rbac/users.html` | `redesign/users.html` | 完整对等 + 增强 |
| `rbac/users_add.html` | `redesign/user_form.html` | 完整对等（复用） |
| `rbac/users_edit.html` | `redesign/user_form.html` | 完整对等（复用） |
| `rbac/users_set_active.html` | `redesign/users_set_active.html` | 完整对等 |
| `rbac/groups.html` | `redesign/groups.html` | 完整对等 |
| `rbac/groups_add.html` | `redesign/group_form.html` | 完整对等（复用） |
| `rbac/groups_edit.html` | `redesign/group_form.html` | 完整对等（复用） |
| `rbac/audit_logs.html` | `redesign/audit_logs.html` | 完整对等 + 增强 |
| `rbac/registration_review.html` | `redesign/registration_review.html` | 完整对等 |
| `rbac/api_token.html` | `redesign/api_token.html` | 完整对等 |
| `rbac/change_password.html` | `redesign/change_password.html` | 完整对等 |
| `rbac/complete_profile.html` | `redesign/complete_profile.html` | 完整对等 |
| `rbac/forgot_password.html` | `redesign/forgot_password.html` | 完整对等 |

**覆盖率: 26/26 个 V1 页面模板均有 V2 对应实现 (100%)**

## 4. Batch 1 实际改动分析

### 改动范围

仅需修改 `app/ui_mode.py` 第 29 行：

```
# Before (current)
ui_version = request.cookies.get('cp_ui_version', 'v1')

# After (Batch 1)
ui_version = request.cookies.get('cp_ui_version', 'v2')
```

### 影响范围

| 环境 | 当前状态 | Batch 1 后 |
| --- | --- | --- |
| 本地（`cronpilot.sh` 启动） | 已是 V2（env var 强制） | 无变化 |
| 本地（直接 `python manage.py`） | V1（无 env var） | **变为 V2** |
| Docker（有 `FORCE_NEW_UI=true`） | 已是 V2 | 无变化 |
| Docker（无 env var） | V1 | **变为 V2** |
| 生产（无 env var） | V1 | **变为 V2** |

### 回退方式

用户设置 Cookie `cp_ui_version=v1` 即可个人回退到 V1。全局回退：将代码改回 `'v1'` 或设置 `CRONPILOT_FORCE_NEW_UI=false`。

## 5. 结论

**V1 下线 Batch 1 执行条件已全部满足。**

- 6/6 检查项全部 PASS
- V2 模板 100% 覆盖 V1 功能（26/26 页面）
- 零跨版本依赖（V2 不引用任何 V1 资源）
- 本地环境已实质运行 V2 多日，无功能回退报告
- 测试套件 441 tests 全绿，无 V1 硬依赖
- 所有 7 个 CI 门禁全绿

**建议**: 可安全执行 Batch 1。改动量极小（1 行代码 + 文档更新），风险可控（Cookie 回退即时生效）。

---

本报告基于 2026-08-26 代码库快照生成，与 <V1下线方案设计.html> 配合阅读。

[文档索引](index.html) · [Markdown](V1下线Pre-check报告-2026-08.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
