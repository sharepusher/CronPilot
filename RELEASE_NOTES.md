# CronPilot Release Notes

本文档记录 **CronPilot** 版本变更。  
HTML 版：[doc/RELEASE_NOTES.html](doc/RELEASE_NOTES.html)

---

## [Unreleased]

### 增强 — 集成测试自动探测

- `test_csrf_integration.py` 和 `test_cron_ops_integration.py` 新增本地服务自动探测（:5001/:5860）
- 无需手动设置 `CRONPILOT_BASE_URL` 环境变量，服务运行时集成测试自动执行
- 新增 `SKIP_INTEGRATION=1` 环境变量支持强制跳过
- skipped 测试从 11 个减少到 6 个（剩余 6 个因无测试任务数据跳过，非连接问题）
- 详见 [集成测试自动探测优化](doc/design/集成测试自动探测优化-2026-08.html)

### 清理 — 死代码移除（P2-4）

- 移除 5 项确认死代码：
  - `isCreate` 变量（`app/__init__.py`）— 上游遗留，从未被读取
  - `_create_pending_log` / `_update_log_running` 桩函数（`app/crons.py`）— Plan-B 弃用后仅 `raise NotImplementedError`，无调用者
  - `CRONPILOT_FORCE_NEW_UI` 配置（`config.py`）— V1 下线后运行时无消费者；同步清理 3 个测试文件中的无效设置
  - `redis_host` 模块级变量（`config.py`）— 冗余的配置读取，实际通过 `configs()` 字典传递
  - `login_required` 装饰器（`app/decorated.py`）— 已被 RBAC `@require_permission` 完全替代，无使用点
- 同步更新 `pyproject.toml` 移除 `app/__init__.py` 的 F841 per-file-ignore
- 详见 [代码质量优化方案](doc/design/代码质量优化方案-2026-08.html) P2-4 · [全面 CodeReview 复盘](doc/postmortem/2026-08-全面CodeReview复盘.html) P2-4 实施复盘

### 修复 — CWD 相对路径消除（P1-5）

- `configs.py` 的 `conf.ini` 读取从 CWD 相对路径改为基于 `__file__` 的绝对路径（`os.path.join(_proj_root, 'conf.ini')`）
- 消除"启动脚本未 `cd` 到项目根目录时配置静默失效"的潜在故障模式
- 详见 [CWD 路径修复](doc/design/CWD路径修复-P1-5-2026-08.html)

### 重构 — 状态切换逻辑统一（P1-2）

- Web 端 `POST /update_status` 和 API 端 `POST /api/cron/status` 的暂停/恢复逻辑统一到 `cron_service.toggle_status()`
- 消除双写：调度器操作（`resume_job`/`pause_job`）、持久化、审计日志由 service 层统一处理
- **审计日志行为修正**：Web 端从"无条件记录"改为"状态实际变化时才记录"（与 API 端对齐），消除重复点击产生的冗余审计记录
- 副效果：`main/views.py` 和 `api/views.py` 不再直接 import `scheduler`
- 详见 [状态切换统一方案](doc/design/状态切换统一方案-P1-2-2026-08.html)

### 工程质量 — 测试门禁统一（P0-1）

- CI workflow 从显式列举 5 个测试模块改为 `unittest discover`，覆盖全部 51 个模块（634 用例）
- `cronpilot.sh test` 同步改为 `discover`，消除 CI 和本地测试的覆盖差异
- 原 CI 仅门禁 5/51 模块（~28 用例），安全修复防护测试（`test_safe_redirect` · `test_logout_csrf` · `test_tag_scope`）完全不在 CI 中执行
- 改为 discover 后，新增测试文件自动纳入 CI，无需手动维护模块列表
- 详见 [测试门禁统一方案](doc/design/测试门禁统一方案-2026-08.html) · [全面 CodeReview 复盘](doc/postmortem/2026-08-全面CodeReview复盘.html) P0-1 实施复盘

### 工程质量 — Ruff Lint 工具链引入 + 代码清理（Batch 0）

- 新增 `pyproject.toml` 配置 ruff（target Python 3.8，select E/W/F/I 四组规则）
- 自动修复 66 处（import 排序 49、行尾空白 7、文件末尾缺换行 7、冗余 f-prefix 1、未使用 `as exc` 绑定 2）
- 手动修复 21 处（详见根因分析）：
  - 删除 `crons.py` `_update_log_running()` 中 `raise` 后 22 行不可达死代码（F821 ×5）
  - `type(x)==T` → `isinstance(x, T)`：`decorated.py`（5 处）+ `crons.py`（1 处）（E721 ×6）
  - 移除 `main/views.py` 和 `rbac/views.py` 中从未使用的 Flask `g` 导入（F811 ×8）
  - 删除 4 处未使用变量赋值（F841）：`role`、`recent_ok_tasks`（**消除 Dashboard 无用 SQL 查询**）、`repo`、`CRON_CONFIG`
- per-file-ignores 从 7 条精简为 3 条（仅保留 `isCreate` F841 + 长行 E501）
- 新增 CI workflow `.github/workflows/ruff-lint.yml`（阻断模式，push/PR 触发）
- 详见 [全面 CodeReview 复盘](doc/postmortem/2026-08-全面CodeReview复盘.html) B0-8/B0-9

### 可观测性 — 静默异常加日志 Batch L1+L2

- **Batch L1（Service 层）**：`app/rbac/services.py` 中 16 处 `except Exception: rollback + return error` 新增 `logger.exception(...)`，覆盖用户/组/Token/注册等全部 CRUD 操作。日志包含操作名称和关键标识（user_id/username/group_id），帮助区分约束冲突、连接超时、SQL 错误等不同根因。
- **Batch L2（基础设施/Fire-and-forget）**：
  - C-1 `main/views.py` 分组下拉查询失败 → `logger.warning`
  - C-5 `rbac/context.py` 用户组列表 DB 查询失败 → `logger.warning`
  - C-6 `rbac/__init__.py` 待审注册计数查询失败 → `logger.warning`
  - C-2/C-4 `main/views.py` bypass scope 刷新失败 → `logger.debug`
  - D-2 `rbac/services.py` scope 缓存失效失败 → `logger.debug`
  - F-3 `CuBackgroundScheduler.py` 一次性任务标记下线失败 → `self._logger.warning`
  - C-8/D-1 `api/__init__.py` — 已在 Batch S1 中完成
- 详见 [静默异常审计与优化方案](doc/design/静默异常审计与优化方案-2026-08.html)

### 安全修复 — 静默异常审计 Batch S1+S2

- **⚠️ API Breaking Change**: `api/__init__.py` `_api_token_guard()` 中 `configs()` 读取失败时，原行为为赋予 admin 权限并放行；现改为返回 HTTP 500 + 记录错误日志。正常配置环境下无影响。
- 删除死代码文件 `app/api/auth.py`（文件头已注明"未启用"，从未被路由引用）
- 裸 `except:` → `except Exception:`（`CuBackgroundScheduler.py`、`CuGeventScheduler.py` 各 1 处），防止捕获 `KeyboardInterrupt`/`SystemExit`
- 补充 `_resolve_user_token` 和 `_write_api_deny_audit` 的 `logger.warning` 日志
- 详见 [静默异常审计与优化方案](doc/design/静默异常审计与优化方案-2026-08.html)

### 重大变更 — V1 UI 下线 Batch 1–3（完全移除 V1）

V2 Redesign UI 现在是唯一界面。V1 全部模板、JS、CSS 及第三方插件已物理删除。

**Batch 1（默认切换）**:
- `app/ui_mode.py`: Cookie 默认值 `v1` → `v2`
- `app/__init__.py`: `before_request` 中默认值 `v1` → `v2`，移除 `CRONPILOT_FORCE_NEW_UI` 覆盖逻辑
- `scripts/start_local_full.sh`: 移除冗余的 `CRONPILOT_FORCE_NEW_UI=true`

**Batch 2（分支清理）**:
- `app/main/views.py`: 移除 15 处 `ui_version` 条件分支，净减约 205 行
- `app/rbac/views.py`: 移除 20 处 `ui_version` 条件分支，净减约 207 行
- `app/__init__.py`: 移除 `_set_ui_version()` before_request 钩子
- `app/ui_mode.py`: 移除 `_VALID_UI_VERSIONS` 及 `ui_version` 相关代码
- 19 个测试更新为 V2 断言（dashboard rows、retire、run-now、topbar、audit logs、registration review）

**Batch 3（物理删除）**:
- 删除 V1 模板 36 个（`app/templates/*.html` + `rbac/*.html` + `errors/error.html`）
- 删除 V1 JS 8 个（`common.js`、`wind.js`、`ajaxForm.js`、`bootstrap.min.js`、`requests.js`、`signs.js`、`tag-input.js`、`md5.js`）
- 删除 V1 CSS 2 个（`bootstrap.min.css`、`console-mode.css`）
- 删除 V1 第三方插件目录 5 个（`artDialog/`、`datePicker/`、`jquery.validate/`、`noty/`、`simpleboot/`）
- 新建 `redesign/error.html`（V2 独立错误页，覆盖 404/403/500）
- `errors.py`、`decorators.py` 错误处理指向 V2 error 模板
- 移除 `_users_form_response()` 中的 V1→V2 template_map
- 移除 topbar "切换到经典界面" 链接
- 12 个 V1 专属测试移除（V2 sidebar 已由 `test_redesign_sidebar` 12 条覆盖）

**⚠️ 不可回退**：Batch 3 后不再支持 V1 回退。如需回退需从 git 历史恢复 V1 资产。

**设计文档**: `doc/design/V1下线方案设计.html`、`doc/design/V1下线Pre-check报告-2026-08.html`、`doc/design/Redesign代码质量全面评估报告-R6-2026-08.html`

**Batch 4（注释 + Dead CSS 清理）**:
- `console-theme.css`: 移除 6 处过时的 V1 引用注释（admin_base、simpleboot）；删除 18 行 Dead CSS（`.rbac-topbar` 选择器 + `--cp-topbar-*` token，V2 无消费者）
- `common-redesign.js`: 更新文件头注释，移除 V1 引用
- `execution_logs.html`: 更新过时的 datePicker 注释

**Batch 5（Legacy Shim 删除）**:
- 删除 `/check_pass` 路由 shim（8 行）和 `/logout` GET shim（3 行）
- 删除对应测试 7 个（test_rbac_phase.py 5 个 + test_logout_csrf.py 2 个）

**设计文档**: `doc/design/V1下线Batch4-5方案设计.html`、`doc/design/V1下线完成报告-Batch1-3-2026-08.html`

---

### 改进 — 全站图标迁移至 Heroicons

全站 Redesign 模板中的 Feather 图标（stroke-width: 2）统一迁移至 Heroicons Outline（stroke-width: 1.5），共替换 **53 个 SVG** 跨 11 个模板文件。

**B1-B3（语义修正）**：
- 密码可见性 Eye/Eye-Slash：3 个页面 7 组图标 → Heroicons 更精致的 stroke:1.5 版本
- 查看详情：Eye → Document-Text（消除与密码切换的语义冲突）
- API Token 导航：Key → Command-Line（消除与重置密码的语义混淆）
- Token 重置：Refresh → Arrow-Path

**B4-B9（全站统一）**：
- 侧边栏导航（14 个）：squares-2x2、document-text、user-group、tag、user、user-plus、shield-check、clock、lock-closed、code-bracket、chevron-right/left
- 顶栏工具与用户菜单（9 个）：bars-3、magnifying-glass、sun、moon、bell、chevron-down、lock-closed、arrow-path、arrow-right-start-on-rectangle
- 用户管理操作列（3 个）：lock-closed、key、no-symbol
- Dashboard（2 个）：calendar-days、document-text
- 详情页与面包屑（7 个）：chevron-right、clipboard-document、pause、pencil-square
- 业务组成员（1 个）：users

**验收**：`rg 'stroke-width="2"' app/templates/redesign/` → 0 结果（全站清零）

**设计文档**：`doc/design/图标规范化与替换设计.html`、`doc/design/全站图标迁移至Heroicons设计.html`

### 改进 — 任务列表业务组列条件展示

Dashboard 任务列表「业务组」列和组筛选下拉改为按用户可见组数动态展示：
- 多组用户 / Admin（可见 ≥ 2 组）：展示业务组列（7 列）+ 组筛选下拉
- **单组用户**（仅 1 个可见组）：**隐藏**业务组列（6 列）和组筛选下拉，减少信息冗余
- 逻辑 `show_group_column = len(scope_groups) > 1`，AJAX 分页/筛选上下文同步传入

**设计文档**：`doc/design/任务列表业务组列条件展示设计.html`

### 改进 — 执行记录结果列细分展示

执行记录「结果」列从统一的「失败」细分为四种状态 + fail_reason 子标签：
- **失败**（`fail`）：HTTP 4xx · 5xx · 关键词
- **异常**（`error`）：连接 · URL拦截（橙色 `--cp-warn`）
- **超时**（`timeout`）
- **成功**（`success`）

新增 CSS class：`.el-log-error`、`.el-log-timeout`、`.el-log-sub`

**设计文档**：`doc/design/执行记录结果列细分展示设计.html`

### 改进 — 系统管理菜单文案优化

侧边栏「操作记录」→「变更记录」、「审计」→「访问审计」，更清晰地区分任务配置变更日志与安全访问事件日志。
- v1 / v2 导航、页面标题、交叉引用、空态提示、角色提示文案同步更新
- 路由 URL、权限字符串、数据库字段不变

### 改进 — 执行记录术语规范化

- 执行记录详情中「追踪码」→「Trace ID」，更贴近技术用户习惯
- `error_keyword` 配置默认值从 `fail,error` 改为空（不启用响应体关键词检查），避免 HTTP 200 被误判为失败

### 改进 — Inline Style 清零（CI 全绿）

消除 Redesign 模板中残留的 10 处 inline style 违规，提取为语义化 CSS class：
- 新增 `.cp-modal-p`、`.cp-modal-p-lg`、`.cp-modal-err`、`.cp-modal-footnote`、`.cp-modal-textarea` 等模态框工具类
- 新增 `.lr-pin-ok/.lr-pin-fail/.lr-pin-unknown` 替代 status dot 动态 background
- 新增 `.tg-scope-cell/.tg-scope-global` 替代标签作用域列 inline style
- 新增 `.auth-group-all-label` 替代注册页 admin-only label 的 display:none
- CI 门禁 `check_ui_contract.py --check` 从 10 violations → **0 violations**

### 文档 — 代码质量评估报告 R4

新增 `doc/design/Redesign代码质量全面评估报告-R4-2026-08.html`：综合评分 B+ (80/100)，覆盖 CSS/JS/Template/Backend/CI/Test 六维度评估。

### 修复 — 文档链接 140 处 broken 归零

- 创建 `doc/design/index.html`、`doc/postmortem/index.html`、`doc/design/screenshots/eval6/index.html` 目录索引页
- 修正 `UI重设计-groups-tags-方案对比Demo.html` 中 Mockup 文件名引用错误
- `check_doc_links.py --check`：991 个引用扫描 → 0 broken

### 文档 — 代码质量评估报告 R3

新增 `doc/design/Redesign代码质量全面评估报告-R3-2026-08.html`：综合评分 B+（78/100），覆盖 CSS/JS/Template/Backend/CI/Test 六维度评估。

### ⚠️ API Breaking Change — 执行记录标识符与术语统一

**变更**：全量重命名 `log_id`（UUID 追踪码）为 `trace_id`，消除与数据库主键 `id` 的歧义。

**代码变更**：
- **模型层**：`JobLog.log_id` → `JobLog.trace_id`（`mapped_column('log_id', ...)`，数据库列名通过迁移脚本 `ALTER TABLE RENAME COLUMN` 同步更改）；`JobLogItems.log_id` → `JobLogItems.trace_id`；`JobHealth.last_run_log_id` → `JobHealth.last_run_trace_id`
- **外部 API 参数**：定时触发请求参数 `cronpilot_log_id` → `cronpilot_trace_id`（影响签名计算）；`POST /api/cron/add_log` 入参 `cronpilot_log_id` → `cronpilot_trace_id`；`GET /api/cron/log_detail` 查询参数 `log_id` → `trace_id`，响应字段 `log_id` → `trace_id`
- **UI 显示**：列表页列头 `log_id` → `追踪码`；详情页 `Log ID` → `追踪码`；标题 `执行 #<hash>` 保留（使用 `trace_id` 前 8 位）
- **术语**：用户可见文本中 `回调` → `定时触发`（内部安全校验字符串保留以兼容历史日志数据）

**迁移**：`scripts/ensure_business_tables.py` 自动执行 `ALTER TABLE RENAME COLUMN`（SQLite 3.25+ / MySQL 8.0+）

**设计文档**：`doc/design/执行记录标识符与术语统一设计.html`

### 新增 — 关键路由冒烟测试脚本

**工具**：`python scripts/smoke_routes.py --check`

**覆盖**：86 条路由（v1 + v2 双版本 × 43 条），包括：
- GET 页面渲染：任务中心、执行记录、详情页、用户管理、标签管理等全部核心页面
- POST 表单提交：登录（有效/无效）、注册、新增任务、创建标签、切换状态
- API 端点：健康检查、任务列表、执行记录、详情查询
- 错误路径：404、不存在的 ID、无权限
- 内容断言：关键文案存在性验证

**模式**：
- `--check`：内存 SQLite 全量冒烟（CI 门禁模式，含 seed 数据路由，86 条/4.3s）
- `--live`：对运行中的服务做 HTTP 冒烟
- `--ui v1/v2`：仅测指定 UI 版本

**目的**：弥补单元测试无法覆盖 view → repo → model → template 完整渲染链路的盲区。跨层重命名、Jinja2 filter 注册变更等改动后必须运行。

**教训来源**：2026-08 `log_id → trace_id` 重命名事故 — 650 单元测试全通过但详情页 500。

### Bugfix — Dashboard 统计指标受 UI 筛选条件影响

**影响**：Redesign Dashboard 顶部统计卡片（任务总数、持续异常、逾期、今日成功率）随列表筛选（状态/标签/搜索）变化，误导用户以为全局数据在波动。

**根因**：`cron_list()` 视图中 `filter_arr` 同时承载 Scope 过滤（权限+业务组）和 UI 展示过滤（状态/标签/搜索），统计函数直接使用 `filter_arr` 导致卡片数据被展示条件污染。

**修复**：
- 将 `filter_arr` 拆分为 `scope_filters`（仅权限+组）和 `filter_arr`（scope + UI 展示条件）
- 所有统计函数（`metrics` / `count_consecutive_failing` / `status_counts` / `today_success_rate` / `_cached_overdue_stats`）改用 `scope_filters`
- 分离缓存 key：`_stats_cache_key`（scope-only）和 `_list_cache_key`（scope + display filters）

**防护测试**：`tests/test_dashboard_stats_stability.py`（3 条用例）

**复盘**：`doc/design/Dashboard统计指标Scope隔离修复设计.html`

### Refactor — DashboardService 提取

从 `app/main/views.py` 的 `cron_list()` God Function（242 行）中提取域逻辑到独立 Service 层：

- **新增** `app/services/dashboard_service.py`（231 行）：croniter 调度计算、逾期检测、TTL 缓存
- **views.py** 从 1,420 行降至 1,258 行（−162 行）
- 统计计算通过 `DashboardService.compute_stats()` 和 `compute_page_context()` 独立可测试

**设计文档**：`doc/design/DashboardService提取重构设计.html`

### Improvement — 按钮系统统一 + A11y 补全

**按钮统一**：
- 消除 `.cp-btn` / `.btn-c` 双系统，全部统一为 `btn-c` + 修饰符（`btn-accent` / `btn-line` / `btn-danger-c`）
- 删除 `redesign-components.css` 中未使用的 `.cp-btn` 定义（−54 行）
- 迁移 4 处 `.cp-btn cp-btn--primary` → `btn-c btn-accent`（dashboard / task_detail / task_form）

**A11y 补全**：
- 5 个 `<select>` 添加 `aria-label`（task_form × 3、user_form、operation_log）
- 侧边栏 collapse 按钮添加 `aria-expanded` + `aria-label="切换侧栏"`（含 JS 动态更新）
- Dashboard 6 个 filter toggle 添加 `aria-pressed` 标记当前选中状态

### Improvement — 用户管理业务组列显示优化

- 业务组列从显示前 2 个 tag 改为只显示第 1 个 + `+N` 收缩标记
- `+N` 标记 hover 时通过 CSS tooltip 展示完整组名列表（用「、」连接）
- 列宽从 140px 收窄至 110px，行高一致性提升

**设计文档**：`doc/design/用户管理业务组列显示优化设计.html`

### Bugfix — 迁移脚本误清零有效时间戳

**影响**：Dashboard "今日失败"等时间维度统计全部归零。

**根因**：`scripts/ensure_business_tables.py` 的清理条件 `typeof(col) = 'text'` 覆盖了 SQLite VARCHAR 列中存储的有效 BIGINT 时间戳（纯数字文本 typeof 也是 'text'），每次服务重启时将其清零。

**修复**：
- `_column_needs_migration()` 仅对日期格式文本（`LIKE '____-__-__%'`）触发迁移
- `_convert_column_data()` 清理条件收窄：仅清零 `CAST(col AS INTEGER) = 0` 的非数字文本

**防护测试**：`tests/test_timestamp_utils.py::TestMigrationCleanupPreservesNumericText`（3 条用例）

**复盘**：`doc/postmortem/2026-08-迁移脚本清零有效时间戳.html`

### Enhancement — 孤儿 Job 监控告警

APScheduler 中存在的孤儿 job（对应 cron_infos 记录已不存在）现在会：
- 触发时递增 Prometheus counter `cronpilot_orphan_job_detected_total`
- 日志级别从 warning 升级为 error，包含处理指引

清理了 10 个历史孤儿 job（来自旧版 `cron_del` 的 `try/except:pass` 导致 `remove_job` 失败后残留）。

**设计文档**：`doc/design/孤儿Job监控告警设计.html`

### Enhancement — 任务中心筛选 AJAX 化（OPT-P1-17）

任务中心（Redesign v2）筛选操作改为 AJAX 局部刷新，不再整页重载。点击异常/状态筛选、切换组/标签、搜索任务名、翻页时页面滚动位置保持稳定，表格区域局部更新。

**交互优化**：
- 筛选按钮 click → AJAX fetch → 仅更新表格 + 分页 + 统计数字
- URL 通过 `history.replaceState` 同步更新，刷新页面后筛选状态保持
- JS 未加载时降级为整页刷新（可用）

**规范新增**：
- `.cursor/rules/cronpilot-project.mdc` 追加"Redesign 交互回归约束"：v1 已有 AJAX 交互的功能，v2 不得降级为整页刷新
- 复盘文档：`doc/postmortem/2026-08-Redesign筛选交互降级.html`

### Enhancement — 执行记录筛选 AJAX 化（OPT-P1-18）

执行记录页（Redesign v2）筛选操作改为 AJAX 局部刷新，复用 OPT-P1-17 相同的 partial 模式。覆盖两个入口：单任务执行记录（`/job_log_list`）和全局执行记录（`/job_log_all_list`）。

**交互优化**：
- 5 个结果按钮（非成功/全部/仅失败/仅异常/仅成功）→ AJAX fetch → 表格 + 分页局部更新
- 任务名/内容搜索 300ms debounce → 自动刷新
- 翻页链接拦截 → 局部更新
- URL 通过 `history.replaceState` 同步
- JS 未加载时降级为整页刷新

**新增文件**：
- `app/templates/redesign/_exec_logs_rows.html` — tbody partial
- `app/templates/redesign/_exec_logs_pagination.html` — 分页 partial
- `tests/test_exec_logs_partial.py` — 5 条回归测试

### Enhancement — 操作记录与审计日志筛选 AJAX 化（OPT-P1-19）

操作记录页（`/operation_log_list`）、审计日志页（`/rbac/audit-logs`）和用户管理页（`/rbac/users`）的 Redesign v2 筛选操作改为 AJAX 局部刷新，复用 OPT-P1-17/18 相同的 partial 模式。

**交互优化**：
- 操作记录：操作类型下拉 + 关键词搜索 → AJAX fetch → 表格 + 分页局部更新
- 审计日志：5 个 chip 按钮（全部/登录成功/登录失败/权限拒绝/用户管理）+ 用户名搜索 → AJAX fetch → 表格 + 分页局部更新
- 用户管理：3 个 chip 按钮（全部/启用/停用）+ 用户名搜索 → AJAX fetch → 表格 + 分页 + 状态计数局部更新
- 翻页链接拦截 → 局部更新
- URL 通过 `history.replaceState` 同步
- JS 未加载时降级为整页刷新

**新增文件**：
- `app/templates/redesign/_oplog_rows.html` — 操作记录 tbody partial
- `app/templates/redesign/_oplog_pagination.html` — 操作记录分页 partial
- `app/templates/redesign/_audit_logs_rows.html` — 审计日志 tbody partial
- `app/templates/redesign/_audit_logs_pagination.html` — 审计日志分页 partial
- `app/templates/redesign/_users_rows.html` — 用户管理 tbody partial
- `app/templates/redesign/_users_pagination.html` — 用户管理分页 partial
- `tests/test_oplog_audit_partial.py` — 10 条回归测试

### Bugfix — test_rbac_phase 测试维护债务修复（9F+1E）

**影响**：`test_rbac_phase.py` 中 9 failures + 1 error 长期潜伏未被日常 CI 发现。

**修复**：
- **Category A**：恢复 `/check_pass` 路由的 `next` 参数透传 + POST 307 语义（`app/main/views.py`）
- **Category B**：5 处测试 POST data 补充 `job_title: 'tech'`（OPT-P1-10 新增验证后测试未同步）
- **Category C**：3 个 TestCase setUp 补充 Tag/TaskTag/TaskGroup model imports（OPT-P1-11 新增表后旧测试未更新）

**预防措施**：创建 `tests/_all_models.py` 全模型导入辅助模块，避免未来新增模型时旧测试遗漏 import。

**复盘**：`doc/postmortem/2026-08-test-rbac-phase-maintenance-debt.html`

### Enhancement — 时间戳存储格式迁移至 BIGINT UTC（OPT-P2-14）

全量时间戳字段从 `VARCHAR(25)` 本地时间字符串迁移为 `BIGINT` 百毫秒 UTC epoch，提升查询性能和跨时区一致性。

**数据模型**：9 个 Model、22 个时间戳字段全部迁移至 `db.BigInteger`

**核心工具库** `datas/utils/times.py`：
- `utc_now_hms()` — 当前 UTC 时间百毫秒 epoch
- `str_to_hms()` / `hms_to_str()` — 字符串 ↔ BIGINT 互转
- `hms_to_display()` — BIGINT → 本地时间显示字符串
- `datetime_to_hms()` / `hms_to_datetime()` — datetime ↔ BIGINT 互转
- `local_today_start_hms()` / `local_tomorrow_start_hms()` — 日期范围查询

**Jinja2 过滤器**：`|hms_display`、`|hms_date`、`|hms_time`、`|hms_short`

**数据迁移脚本**：`ensure_business_tables.py` 新增 `_migrate_time_columns_to_bigint()`，幂等执行，支持 SQLite / MySQL 双后端，T-A 策略（历史本地时间转真正 UTC）

**写入路径**：7 个服务文件的 20+ 调用点从 `get_now_time()` 迁移到 `utc_now_hms()`

**读取路径**：`JobLog.create_time.like(today + '%')` 等字符串查询改为 BIGINT 范围查询；API 返回保持 ISO 字符串兼容

**模板适配**：25 个模板（redesign + v1）全部使用 `|hms_display` 过滤器

**测试**：41 条新增时间工具单测 + 10 个测试文件数据适配 = 617 tests, 0 新增失败

**⚠️ API 兼容说明**：`/api/cron/logs` 的 `create_time` 字段仍返回 ISO 字符串（通过 `hms_to_str()` 转换），API 消费者无需修改

**设计文档**：`doc/design/时间戳迁移至BIGINT-UTC设计.html`

**Files changed:** `datas/utils/times.py`, `datas/model/*.py` (9 files), `app/__init__.py`, `app/services/*.py` (3 files), `app/rbac/services.py`, `app/rbac/views.py`, `app/crons.py`, `app/main/views.py`, `app/api/views.py`, `app/repositories/*.py` (3 files), `scripts/ensure_business_tables.py`, `app/templates/**/*.html` (25 files), `tests/*.py` (11 files)

### Enhancement — 任务中心「逾期未执行」提示功能

- 新增「逾期未执行」独立维度：当任务超过调度间隔 × 2（最小 10 分钟）仍未执行时标记为逾期
- Stats 卡片：新增「逾期未执行」琥珀色卡片，显示逾期任务数量
- Stat-line：新增「逾期」计数，使用琥珀色高亮
- 筛选按钮：新增「逾期未执行」独立筛选，支持按逾期状态过滤任务列表
- Exception Panel：逾期任务显示琥珀色图标 + 「逾期 Xh」标签
- 健康度列：逾期任务显示琥珀色「逾期」/「异常 · 逾期」badge
- 逾期判定逻辑：使用 `croniter` 计算调度间隔，与最近一次执行时间比较；暂停/停用/一次性任务排除
- 新增 12 条单元测试覆盖逾期判定逻辑
- **性能优化 L1（复合索引）**：`ensure_business_tables.py` 自动创建复合索引 `ix_job_log_cron_id_create_time (cron_info_id, create_time)`，启用 Covering Index Scan，`MAX(create_time) GROUP BY` 查询提速 ~5x（实测 1000 ID 查询从 26.8ms 降至 5.5ms）
- **性能优化 L2（进程内 TTL 缓存）**：`_cached_overdue_stats()` 对逾期统计结果进行 30s TTL 缓存（按用户 scope 隔离），Dashboard 重复加载耗时从 776ms 降至 73ms（10.6x 提速）
- 设计文档含详细性能分析（SQLite/MySQL 基准、并发场景、阶梯式优化路线图）：`doc/design/任务中心逾期未执行提示设计.html`

**Files changed:** `app/main/views.py`, `app/repositories/cron_repository.py`, `app/templates/redesign/dashboard.html`, `app/static/css/redesign-pages.css`, `tests/test_overdue_detection.py` (new), `scripts/ensure_business_tables.py`

### Enhancement — 任务中心筛选按钮视觉统一与文案优化

- 任务中心筛选按钮（`.f-btn`）选中态增加蓝色圆点指示，与执行记录页视觉一致
- 「连续失败」改名为「持续异常」（Stats 卡片、Stat-line、筛选按钮），更贴近运维用户的关注视角
- Exception Panel 中的事实性描述「连续失败 X 次」保持不变
- 设计文档：`doc/design/任务中心筛选按钮视觉统一与文案优化设计.html`

**Files changed:** `app/static/css/redesign-pages.css`, `app/templates/redesign/dashboard.html`

### Fix — 执行记录「仅异常」筛选按钮失效修复与语义优化

- **Bug 修复**：「仅异常」按钮发送 `outcome=timeout`，但后端白名单不包含该值，导致按钮完全失效（行为等同于「非成功」，且无法显示选中态高亮）
- **语义优化**：将「仅异常」的过滤逻辑从单一 `timeout` 改为 `error + timeout`（系统层异常），与「仅失败」（`fail`，应用层错误）形成清晰互补关系，满足 **非成功 = 仅失败 ∪ 仅异常** 的集合分割
- **视觉优化**：筛选按钮选中态的指示圆点从黑色（`currentColor`）改为系统主题色 `var(--cp-signal)`
- 新增 3 条 `job_log_outcome_clause` 单元测试覆盖 `exception` 输入
- 设计文档：`doc/design/执行记录筛选条件Bug修复与视觉优化设计.html`

**Files changed:** `app/main/views.py`, `app/services/job_log_filter.py`, `app/templates/redesign/execution_logs.html`, `app/static/css/redesign-pages.css`, `tests/test_job_log_outcome_filter.py`

### Enhancement — F5: common.js 精简（Redesign JS 载荷 -62%）

- 新建 `app/static/js/common-redesign.js`（142 行），使用 `$.ajax()` + `CpToast` 替代 Wind 插件链
- `_base.html` 移除 `wind.js`（27 KB）+ `common.js`（39 KB），替换为 `common-redesign.js`（6 KB）
- 消除 3 个 lazy-load 插件（ajaxForm 37 KB + artDialog 16 KB + validate 46 KB）的隐式加载
- Redesign 页面 JS 总载荷从 ~257 KB 降至 ~98 KB
- v1 页面完全不受影响（`admin_base.html` 引用链未改动）
- **修复**：移除 `jquery.js` 的 `defer` 属性（inline script 依赖 `$` 必须同步加载）
- **UX 增强**：errcode≠0 的资源守卫跳转延迟 800ms，让错误 Toast 有时间被用户阅读
- 设计文档：`doc/design/F5-common-js精简设计.html`
- 复盘文档：`doc/postmortem/2026-08-F5-jQuery-defer-inline-script.html`

**Files changed:** `app/static/js/common-redesign.js` (new), `app/templates/redesign/_base.html`

### Fix — P0 CSS/模板缺陷修复（3 项）

**F1-1: keyframe 名称修正**
- `redesign-pages.css:1193` 的 `animation: healthPulse` 修正为 `animation: cp-health-pulse`
- 修复仪表盘失败任务健康指示器脉冲动画无效的问题

**F1-2: 缺失 token 定义**
- 在 `console-theme.css` 的 `.cp-shell` 作用域定义 `--cp-hover`、`--cp-font-ui`、`--cp-signal-border`、`--cp-radius`
- 提供暗色主题对应值（`--cp-hover: rgba(255,255,255,0.06)`）
- 修复复制按钮 hover 背景、Run Inspector 字体、sidebar toggle 圆角降级问题

**F1-3: 操作记录 v2 业务组名显示**
- view 层向 v2 模板传递 `task_group_map`
- 模板从 `cron.group_id`（已迁移字段）改为 `task_group_map.get(cron.id)`
- 修复操作记录页永远不显示任务所属业务组名称的问题

**Files changed:** `redesign-pages.css`, `console-theme.css`, `app/main/views.py`, `operation_log.html`

### Enhancement — F2: CSS Token 可达性 CI 门禁

- 新增 `scripts/check_css_token_reachability.py`：
  - 扫描 `var(--cp-*)` 引用，交叉验证 `:root` / `.cp-shell` 中定义存在性
  - 扫描 `animation:` 属性值，验证对应 `@keyframes` 在加载链中存在
  - 正确处理 CSS 时间单位（`0.3s`）和 `!important` 避免误报
- CI 命令：`python scripts/check_css_token_reachability.py --check`
- 预防 P0-1/P0-2/P0-3 类 CSS silent failure 再次发生

**Files changed:** `scripts/check_css_token_reachability.py`, `AGENTS.md`

### Enhancement — F4a: CSS 作用域补全

- Task Detail (`.td-*` 48 selectors)、Run Inspector (`.ri-*` 23 selectors)、Task Form (`.tf-*` 63 selectors) 三个最大无作用域区段的选择器全部添加 `.cp-page-*` 前缀
- Scope 覆盖率从 32% (219/691) 提升至 51% (354/691)
- 零视觉变更——仅增加 CSS 特异性层级，隔离跨页面样式泄漏风险
- 所有 CI 门禁通过（token 可达性、颜色审计、sidebar 权限）

**Files changed:** `redesign-pages.css`

### Enhancement — D1+D3 A11y 属性补全 + CI Lint

**D1: aria-label 属性补全（11 项）**
- Command Palette 搜索框、API Token 输入框、操作记录搜索、用户搜索、标签编辑输入
- 任务表单标签输入、用户表单/注册页岗位输入
- 所有按钮和输入元素现在均有 accessible name

**D3: A11y CI Lint 规则**
- `check_ui_contract.py` 新增 `a11y-button`（按钮无 aria-label/title/可见文本）和 `a11y-input`（文本输入无 aria-label/label[for]）检查
- 当前 0 违规

**Files changed:** `check_ui_contract.py` + 9 template files

### Enhancement — R3 功能补全: Command Palette 搜索 + Mobile 侧边栏

**Command Palette 搜索实现**
- 动态从侧边栏 DOM 构建导航注册表（权限感知：只显示当前用户可见的页面）
- 实时模糊匹配（支持页面名称 + 所属区段关键词）
- 键盘导航：↑↓ 切换高亮 → Enter 跳转 → Escape 关闭
- 打开时自动展示前 10 项；无结果时显示"无匹配结果"

**Mobile 侧边栏连接**
- 新增 `.cp-mobile-toggle` 汉堡按钮（topbar 左侧，桌面端隐藏，≤768px 显示）
- `.mobile-open` 类控制侧边栏固定弹出 + 半透明遮罩
- 点击遮罩区域自动关闭侧边栏
- 公开 API：`CpShell.openMobileSidebar()` / `CpShell.closeMobileSidebar()`

**Files changed:** `redesign-shell.js`, `_topbar.html`, `redesign-layout.css`, `redesign-components.css`

### Enhancement — R2 Minimal: Accent 统一 + 3 页 Scope 补充

**Accent 统一**（26 处）
- `redesign-pages.css`：19 处 `--cp-accent` → `--cp-signal`、3 处 `--cp-accent-bg` → `--cp-signal-bg`、2 处 `--cp-accent-ring` → `--cp-signal-bg`
- `redesign-mockup-shared.css`：`.f-input:focus` box-shadow 从 `--cp-accent-ring` → `--cp-signal-bg`
- `run_inspector.html`：执行中 badge 从 `--cp-accent-bg`/`--cp-accent` → `--cp-signal-bg`/`--cp-signal`

**3 页 Scope 补充**
- `task_detail.html`：新增 `{% block main_class %} cp-page-task-detail{% endblock %}`
- `task_form.html`：新增 `{% block main_class %} cp-page-task-form{% endblock %}`
- `run_inspector.html`：新增 `{% block main_class %} cp-page-run-inspector{% endblock %}`

**效果**：Redesign 全部页面现在使用统一的 `--cp-signal` 色系，与 Design Token 语义对齐；全部页面均具备 `.cp-page-*` CSS scope class。

**设计文档**：`doc/design/Phase-R2-R3必要性分析与根因复盘.html`（§ 推荐的最小执行项）

**Files changed:** `redesign-pages.css`, `redesign-mockup-shared.css`, `task_detail.html`, `task_form.html`, `run_inspector.html`

### Enhancement — CSS 死代码清理与命名统一（OPT-CSS-CLEANUP-01）

**Batch A — 死代码删除**
- `redesign-components.css` 从 825 行精简至 396 行（-52%），删除 71 个从未被模板/JS 引用的选择器块（含 `.cp-table`、`.cp-pagination`、`.cp-form-*`、`.cp-badge-*`、`.cp-health-*`、`.cp-chip`、`.cp-search`、`.cp-skeleton`、`.cp-btn--danger/ghost/sm/lg/success` 等 Phase 0 遗留组件）

**Batch B — 命名冲突修复**
- 移除 `redesign-mockup-shared.css` 中从未使用的 `[data-tip]` tooltip 规则
- 将 `redesign-pages.css` 中全局 `[data-tooltip]` 覆盖规则加 `.cp-page-dashboard` scope，避免影响其他页面 tooltip 样式
- 修复 `console-theme.css` 中引用未定义 Token `--cp-active-bg` → 改用 `--cp-signal-bg`
- 修正 `prefers-reduced-motion` 中错误选择器：`.toast-item` → `.toast`、删除不存在的 `.cp-confirm-box`/`.cp-shimmer`

**Batch C — CI 门禁**
- 新增 `scripts/check_dead_css.py --check`：检测 components.css 中无引用的类名，阈值 0

**设计文档**：`doc/design/CSS死代码清理与命名统一设计.html`

**Files changed:** `redesign-components.css`, `redesign-mockup-shared.css`, `redesign-pages.css`, `console-theme.css`, `scripts/check_dead_css.py`

### Fix — Redesign 功能页质量审查 Batch 1+2 修复

**Critical Bug 修复**
- **C1** `dashboard.html` `cpRetire()` 缺少 `reason` 字段导致下线操作永远失败 — 改用 `CpModal` 带 textarea 输入下线原因后再 POST。
- **C2** `user_form.html` 编辑已停用用户时仍展示"启用"选项，与"停用不可恢复"策略矛盾 — 停用用户改为只读展示"已停用（不可恢复）"。

**Medium Bug 修复**
- **M1** `tags.html` 任务状态映射 `status === 2` 错误（不存在该值）— 修正为 `=== 0`（暂停），并增加 `-1`（已下线）分支。
- **M2** `execution_logs.html` Esc 快捷键在单任务视图下失效（选择器 `a[href$="job_log_all_list"]` 不匹配）— 改为定位 `.el-filters a[href]` 重置链接。
- **M3** `task_detail.html` + `run_inspector.html` 复制按钮 `onclick="cpCopy('{{ var }}')"` 存在 XSS 注入风险 — 改用 `data-copy-text` 属性 + 事件委托。

**复盘文档**：`doc/postmortem/2026-08-Redesign功能页质量缺陷结构性复盘.html`

**Files changed:** `dashboard.html`, `user_form.html`, `tags.html`, `execution_logs.html`, `task_detail.html`, `run_inspector.html`, `redesign-pages.css`

### Enhancement — Redesign 功能页 Batch 3 UX 改善

- **M4** `task_detail.html` / `registration_review.html` AJAX 操作添加 loading 状态（按钮 disabled + "提交中…"文案），防止重复提交。
- **M5** `user_form.html` / `register.html` / `complete_profile.html` "岗位类型"选中"其他"时动态设置 `required`，空提交触发浏览器原生校验。（`user_profile.html` 已有此逻辑无需改动）
- **M8** `api_token.html` 复制按钮优先使用 `navigator.clipboard.writeText()`，不支持时 fallback 到 `document.execCommand('copy')`。

**Files changed:** `task_detail.html`, `registration_review.html`, `user_form.html`, `register.html`, `complete_profile.html`, `api_token.html`

### Enhancement — Redesign 功能页 Batch 4 可访问性补全

- **M9** `dashboard.html` / `users.html` icon-only 按钮添加 `aria-label`（立即执行、更多操作、停用用户）。
- **M10** `user_form.html` / `group_form.html` / `cron_retire.html` 表单 `<label>` 添加 `for` 属性关联对应 `<input>`/`<select>`/`<textarea>` 的 `id`。
- **M11** `register.html` 确认模态框添加 `role="dialog"` + `aria-modal="true"` + `aria-labelledby` + Escape 键关闭 + 关闭后返回焦点到触发按钮。

**Files changed:** `dashboard.html`, `users.html`, `user_form.html`, `group_form.html`, `cron_retire.html`, `register.html`

### Fix — Tier 3-5: CSS 规范化 + 可访问性 + 后端日志 + JS 兼容性

**CSS 规范 (S2, S3)**
- `redesign-pages.css`、`redesign-mockup-shared.css`、`console-mode.css` 中 5 处 `rgba(8,145,178,…)` focus ring 硬编码颜色提取为 `--cp-accent-ring` CSS 变量（新增于 `console-theme.css` light/dark 两套）。
- `redesign-mockup-shared.css` `.btn-c` 重复定义合并为一处。
- S1（18 处重复选择器）经分析为按页面分区的有意拆分，不做合并。

**可访问性 (A1-A5)**
- `login.html` 密码字段 `<span>密码</span>` 改为 `<label for="login-pwd-input">`，屏幕阅读器可正确关联。
- `change_password.html` 三个密码 `<label>` 补全 `for=` 属性。
- `_topbar.html` 主题切换按钮增加 `aria-pressed` 状态。
- `_sidebar.html` `<nav>` 增加 `aria-label="主导航"`。
- `execution_logs.html` + `run_inspector.html` Escape 键守卫增加 `.cp-modal-overlay` 检查，防止弹窗打开时误触导航。

**后端异常日志 (B1-B3)**
- `rbac/views.py` `last_login_at` 更新失败和 profile commit 失败的 `except: rollback` 增加 `current_app.logger.warning` 日志。
- `cron_service.py` 调度器 `pause_job`/`remove_job` 的 3 处 `except: pass` 增加 `_log.warning` 日志。

**JS 兼容性 (B4)**
- `common.js` `setCookie()` 中已废弃的 `escape()` 替换为 `encodeURIComponent()`。

**不修改项**
- B5（CpModal keydown listener 未清理）：经核查，`close()` 函数已正确调用 `removeEventListener`，不存在泄漏。
- S1（18 处重复选择器）：按页面分区的分节式 CSS，合并反降可读性。
- A6（inline layout styles）：dashboard 等页面的 inline styles 属于 Mockup 直出样式，集中提取需全面回归。

**Files changed:** `console-theme.css`, `redesign-pages.css`, `redesign-mockup-shared.css`, `console-mode.css`, `login.html`, `change_password.html`, `_topbar.html`, `_sidebar.html`, `execution_logs.html`, `run_inspector.html`, `rbac/views.py`, `cron_service.py`, `common.js`

### Fix — D5+D6: 标签页 alert() 替换 + CSRF null check

- `tags.html` 中 4 处 `alert()` 替换为 `CpToast.error()`，与 redesign 其余页面体验一致。
- `tags.html` CSRF meta 标签取值增加 null 安全检查。

**Files changed:** `app/templates/redesign/tags.html`

### Fix — C1+X1+X2: Cookie SameSite 一致性 + XSS 防御深度

- Redesign JS 中 3 处 cookie 写入（`cp_theme`、`cp_sidebar_collapsed`、`cp_ui_version`）缺少 `samesite=lax`，与 `common.js` 不一致。
- `tags.html` 删除确认对话框中 `r.errmsg` 未经 `escHtml()` 转义直接拼入 HTML。
- `CpModal` 的 `confirmText`/`cancelText` 通过 `innerHTML` 拼接，改为 DOM API `textContent` 赋值。

**Files changed:** `app/static/js/redesign-theme.js`, `app/static/js/redesign-shell.js`, `app/templates/redesign/_topbar.html`, `app/templates/redesign/tags.html`, `app/static/js/redesign-confirm.js`

### Fix — F1+F2+F3: Dashboard AJAX 路径与 API 契约修复

- Dashboard 三个操作按钮（暂停/恢复、立即执行、下架）的 AJAX 请求使用 RESTful 路径 `/update_status/{id}` 而非 Flask 注册的 `/update_status`，导致 **404 全部失效**。
- 下架按钮错误地 POST 到 `/update_status`（toggle 行为），实际应走 `/cron_retire`（下架行为）。
- 修复：三处 `$.post()` URL 改为正确路径，`id` 通过 POST data 传递；下架改用 `/cron_retire` 端点。
- 同类排查：`task_detail.html` 已正确使用 `/update_status?id=` 格式，v1 `_cron_list_rows.html` 使用 `url_for()`。

**Files changed:** `app/templates/redesign/dashboard.html`

### Fix — S1+S2: 登出 CSRF 防护

- `/rbac/logout` 原先接受 GET 请求，攻击者可构造 `<img src="/rbac/logout">` 使已登录用户被强制登出。
- 修复：`/rbac/logout` 改为 **POST-only**（GET 返回 405），配合 CSRF token 校验。
- 前端同步：Redesign `_topbar.html` 登出链接改为隐藏 `<form method="POST">` + JS 提交；v1 Command Palette 搜索结果中 "退出登录" 改为动态创建 POST 表单。
- 遗留路由 `/logout` 和 `/check_pass`（`main.views`）不再清除 session，仅重定向到 `/rbac/login`。
- 4 条单元测试覆盖 (`tests/test_logout_csrf.py`)：GET→405、POST→302+session清除、遗留路由→302。
- 设计文档：`doc/design/安全问题修复设计-S1至S5.html` §4
- 复盘文档：`doc/postmortem/2026-08-security-S1-S5.html`

**Files changed:** `app/rbac/views.py`, `app/main/views.py`, `app/decorated.py`, `app/templates/redesign/_topbar.html`, `app/static/js/redesign-shell.js`, `app/static/js/common.js`, `tests/test_logout_csrf.py` (new)

### Fix — S3: 标签 CRUD scope 越权修复

- 标签的创建/修改/删除/查询路由仅检查 `@require_permission('user:manage')`，无 scope 层面校验。
- 按组管理员（Biz Admin）可通过修改 POST body 中的 `group_id` 越权操作其他组或全局标签。
- 修复：新增 `_check_tag_group_id_scope()` / `_check_tag_scope()` 辅助函数，5 个标签路由（create/update/rename/tasks/delete）全部加入 scope 校验。
- 9 条单元测试覆盖：自组操作允许 3 + 他组/全局拦截 6 (`tests/test_tag_scope.py`)。
- 设计文档：`doc/design/安全问题修复设计-S1至S5.html` §2
- 复盘文档：`doc/postmortem/2026-08-security-S1-S5.html`

**Files changed:** `app/rbac/views.py`, `tests/test_tag_scope.py` (new)

### Fix — S4: 存储型 XSS 修复（data-* → innerHTML 链路）

- `registration_review.html` 2 处、`tags.html` 4 处、`task_form.html` 1 处，`data-*` 属性取值后直接拼入 `innerHTML` / `bodyHtml`，未转义。
- 攻击链路：Jinja2 转义保护 HTML 解析阶段，但浏览器解码后 jQuery `.data()` 返回原始字符串 → 二次注入。
- 修复：添加 `escHtml()` 转义函数；`task_form.html` 的 `addTag()` 改用 `textContent` + DOM API。
- 设计文档：`doc/design/安全问题修复设计-S1至S5.html` §3
- 复盘文档：`doc/postmortem/2026-08-security-S1-S5.html`

**Files changed:** `app/templates/redesign/registration_review.html`, `app/templates/redesign/task_form.html`, `app/templates/redesign/tags.html`

### Fix — S5: API 装饰器 catch-all 异常文本泄露

- `app/decorated.py` 的 `api_deal_return` 装饰器在 `except Exception` 中返回 `str(e)`，影响 `/api/cron/add` 旧路径兼容层。
- 与 P0-3 同源：修复时搜索范围限于 `main/views.py` + `rbac/views.py`，未覆盖 API 装饰器。
- 修复：返回通用错误信息 `'服务器内部错误'`；异常详情写入 `logging.getLogger().error()`。
- 设计文档：`doc/design/安全问题修复设计-S1至S5.html` §4
- 复盘文档：`doc/postmortem/2026-08-security-S1-S5.html`

**Files changed:** `app/decorated.py`

### Fix — P0-1: CpConfirm.show() 参数名错误 + P0-4: Escape 键守卫选择器修复

- **P0-1**: `task_detail.html` 的 2 处 `CpConfirm.show()` 调用使用了 `message:` 属性，但 API 仅识别 `body:`。修复后确认对话框正文正常显示。
- **P0-4**: `task_detail.html` 和 `task_form.html` 的 Escape 键守卫使用了不存在的 `.cp-confirm-overlay` 选择器（实际为 `.cp-modal-overlay`），导致对话框打开时按 Escape 仍触发页面导航。同时移除了不可靠的 `[style*="flex"]` 属性选择器。
- 设计文档：`doc/design/P0问题修复设计.html`
- 复盘文档：`doc/postmortem/2026-08-P0-frontend-bugs.html`

**Files changed:** `app/templates/redesign/task_detail.html`, `app/templates/redesign/task_form.html`

### Fix — P0-2: 开放重定向修复 (Open Redirect)

- 登录页 `next` 参数未做校验，攻击者可构造 `?next=https://evil.com/steal` 实现钓鱼跳转。
- 修复：新增 `app/rbac/safe_redirect.py` → `safe_next_url()` 函数，拒绝绝对 URL / 协议相对 URL / `javascript:` 等 scheme，仅放行安全的相对路径。
- 3 处调用点全部包裹：`rbac/views.py` GET 渲染（L189）+ POST 登录（L194）、`main/views.py` 未登录重定向（L1203）。
- 11 条单元测试覆盖：正常路径 3 + 恶意路径 5 + 边界 3 (`tests/test_safe_redirect.py`)。
- 设计文档：`doc/design/P0问题修复设计.html` §3
- 复盘文档：`doc/postmortem/2026-08-P0-frontend-bugs.html`

**Files changed:** `app/rbac/safe_redirect.py` (new), `app/rbac/views.py`, `app/main/views.py`, `tests/test_safe_redirect.py` (new)

### Fix — P0-3: 异常文本泄露修复

- `cron_add` 的 `except Exception` 分支中 `web_api_return(code=1, msg=str(e))` 将 Python 异常原始文本（含数据库引擎/表名/内网IP/文件路径）返回给前端。
- 修复：返回通用错误信息「服务器内部错误，请稍后重试」；异常详情写入 `current_app.logger.error` + 微信告警保持不变。
- 设计文档：`doc/design/P0问题修复设计.html` §4
- 复盘文档：`doc/postmortem/2026-08-P0-frontend-bugs.html`

**Files changed:** `app/main/views.py`

### Feature — Brand Icon `[⏱]`

- Replaced the old 8px blue dot brand icon with a new **`[ ]` bracket-clock** SVG brand mark.
- Design: two square brackets (`currentColor`, adapts to theme) + blue clock hands (`var(--cp-signal)`).
- Concept: code syntax `[scheduled]` + time — instantly communicates "scheduled tasks" to developers.
- Works clearly at all sizes: 20px (sidebar expanded), 18px (sidebar collapsed), favicon-ready.
- Design candidates (45 options across 3 rounds): `doc/design/brand-icon-candidates.html`

**Files changed:** `_sidebar.html`

### Feature — Sidebar Collapse Button (Edge Toggle)

- Added a visible collapse/expand button on the sidebar's right edge (divider line), positioned at `top: 20%` (1/5 of page height).
- The button is a 24px circle with a chevron icon: `‹` when expanded, `›` when collapsed.
- Always visible (`opacity: 1`) to ensure discoverability for first-time users.
- Hover highlight: signal-blue background with matching border.
- Sidebar transition: `grid-template-columns 0.2s ease` for smooth width animation (192px ↔ 56px).
- State persistence: via `cp_sidebar_collapsed` cookie (existing infrastructure), server-side rendered to avoid flash.
- Added `title` attributes to all nav items for native tooltip in collapsed (icon-only) mode.
- Design document: `doc/design/侧边栏折叠功能设计.html`

**Files changed:** `_sidebar.html`, `redesign-layout.css`

### Fix — Redesign CSS hardcoded colors, duplicate definitions, and print selector mismatch

- Replaced 15 hardcoded hex colors (`#fff`, `#ddd`, `#d97706`) across 3 redesign CSS files with CSS variable references (`var(--cp-on-filled)`, `var(--cp-border)`, `var(--cp-warn-accent)`).
- Fixed 2 references to non-existent CSS variables: `--cp-warning` → `--cp-warn-accent`, `--cp-white` → `--cp-on-filled`.
- Added 2 missing CSS variables to `console-theme.css`: `--cp-warn-text` and `--cp-danger-text` (both light and dark themes).
- Removed duplicate `.cp-breadcrumb` definition from `redesign-layout.css` (consolidated into `redesign-pages.css`).
- Fixed print `@media` selectors: `.redesign-sidebar`/`.redesign-topbar`/`.redesign-main` → `.cp-sidebar`/`.cp-topbar`/`.cp-main`.
- No visual changes — all modifications are code quality improvements.

**Files changed:** `console-theme.css`, `redesign-components.css`, `redesign-pages.css`, `redesign-mockup-shared.css`, `redesign-layout.css`

### Fix — Nested form in change_password.html (force_reset mode)

- Fixed an HTML spec violation where the logout `<form>` was nested inside the password change `<form>` when `force_reset=True`.
- Browsers ignore nested `<form>` tags, so clicking "退出登录" would incorrectly trigger the password change submission instead.
- Fix: replaced the nested form with a `<button type="button">` + JS-driven dynamic form submission.
- Also removed an inline `style="display:inline"` that violated the project's no-inline-style rule.

**Files changed:** `app/templates/redesign/change_password.html`

### Feature — R3: Inline Deactivation Modal (User Management)

- Replaced the full-page deactivation redirect with an inline modal dialog.
- Modal shows username + role badge, an irreversible-action warning, and a **required** reason textarea (1–500 characters, live character counter).
- Confirm button is disabled until at least 1 character is entered.
- Three close methods: ESC key, Cancel button, backdrop click.
- Backend: deactivation reason is now persisted to `RbacUser.status_reason` via `users_set_active` endpoint.
- Deactivated user view-only page (`/rbac/users/view?id=<id>`) already displays the reason; shows "—（未填写）" for legacy users deactivated before R3.

**Files changed:** `app/templates/redesign/users.html`

### Feature — R2: Business Group Auto-Lock for Single-Group Users

- When a non-global user (Biz Admin with exactly one business group) accesses the create-user or edit-user form, the business group field is rendered as a read-only text input with the group pre-filled, plus a hidden `<input>` that submits the group ID automatically.
- Seed Admin and users belonging to multiple groups continue to see the full multi-select dropdown.
- Backend enforce: if `locked_group` is set, the submitted `group_ids` is overridden server-side regardless of what the client sends.
- New helper `_get_locked_group(bypass, groups)` in `views.py`.

**Files changed:** `app/rbac/views.py`, `app/templates/redesign/user_form.html`

### Feature — B3: Last Login Column in User Management Table

- Added `last_login_at VARCHAR(25)` field to `RbacUser` model (nullable, default None).
- Migration: `scripts/ensure_business_tables.py` now adds the column to existing `rbac_users` tables.
- Login flow: on successful authentication, `last_login_at` is updated with current timestamp.
- User management table (`/rbac/users`): new "最近登录" column added between "状态" and "密码状态", showing `YYYY-MM-DD HH:MM` or `—` if never logged in since the field was introduced.
- **Bug fix (B3 regression)**: Adding the 10th column caused headers to wrap on 1440px viewport. Fixed by changing `.c-table` from `table-layout: fixed; width: 100%` to `table-layout: fixed; min-width: 1300px` and adding `white-space: nowrap` to `th` elements, ensuring proper horizontal scroll.
- **Prevention**: Added "表格列变更验收" rule in `cronpilot-format-guard.mdc` requiring 1440px viewport screenshot validation when adding/removing table columns.

**Files changed:** `datas/model/rbac_user.py`, `app/rbac/views.py`, `scripts/ensure_business_tables.py`, `app/templates/redesign/users.html`, `.cursor/rules/cronpilot-format-guard.mdc`

### Bug Fix — B1: Deactivated Users View-Only Page + Critical Route Decorator Fix

**B1 — Deactivated users: view-only info**
- Added `GET /rbac/users/view?id=<id>` route rendering all fields as disabled/read-only inputs.
- Updated `users.html`: inactive users now show a person-icon link (tooltip: 查看信息) pointing to the view page, replacing the static "已停用" label.
- Updated `user_form.html` to support `view_mode=True` context: all fields disabled, "保存" replaced by "← 返回用户管理", page title "查看用户信息".

**Critical Bug Fix — Missing `@rbac.route` decorator on `users_reset_password`**
- A successive StrReplace operation accidentally deleted the `@rbac.route('/users/reset_password', methods=['POST'])` decorator from `users_reset_password`, making the endpoint invisible to Flask routing.
- This caused `url_for('rbac.users_reset_password')` in `redesign/users.html` to raise `BuildError`, returning HTTP 500 for all visits to `/rbac/users`.
- **Fix**: Restored the missing `@rbac.route` decorator.
- **Prevention**: New `scripts/check_route_completeness.py` (AST scan, CI-ready). New rule in AGENTS.md: "Read back ±20 lines after consecutive StrReplace on same function area."
- **Postmortem**: `doc/postmortem/2026-08-missing-route-decorator.html`

**Files changed:** `app/rbac/views.py`, `app/templates/redesign/users.html`, `app/templates/redesign/user_form.html`



Added email address as a mono-font subtitle below the username in the users table, matching the `view-users` mockup spec.

**Files changed:** `app/templates/redesign/users.html`

### Bug Fix — User Management Page UX (3 Issues)

**Bugs fixed:**
- UX-1: Icon button tooltips showed with ~500ms–1s OS delay (native `title` attr) → replaced with instant CSS `[data-tooltip]::after` tooltips
- UX-2: Eye icon used for "view inactive user" action conflicted with password-visibility icon convention → removed action entirely for inactive users
- UX-3: Inactive user action link navigated to the edit page, which is incorrect → replaced with static `已停用` label, no link

**Files changed:** `app/templates/redesign/users.html`
**Postmortem:** `doc/postmortem/2026-08-users-ux-bugs.html`

### Redesign UI — Users Table Column Alignment + Status Chip Filters (A2)

- **Column order corrected**: 业务组 moved to position 5 (after 角色), 状态 moved to position 6.
- **Column renamed**: `密码` → `密码状态` to match internal mockup.
- **Chip filter bar added**: 全部 N / 启用 N / 停用 N with dynamic counts, applied via `?chip=active/inactive`.
- **Backend**: `is_active` filter added to `RbacUserRepository.paginate_all` / `paginate_by_groups`; new `count_by_status()` method for scope-aware counts.
- **Pagination** preserves chip and username filters across pages.

### Redesign UI — Audit Log Table Alignment + Chip Filters (Z2)

- **Table structure updated from 8 columns to 6 columns** to match internal redesign mockup.
- **New columns:** 时间 | 用户名 | 动作 | 说明 | 来源 IP | 结果 (removed ID, 目标类型, 目标名 columns).
- **Chip filter bar** replaces dropdown selects: 全部 / 登录成功 / 登录失败 / 权限拒绝 / 用户管理 presets.
- **Action badges** with semantic colors: green (login success), red (login fail/deny), amber (permission deny), blue (user management).
- **Row highlight** for denied events (`background: var(--cp-danger-bg)`).
- **Backend:** `user:manage` pseudo-action in `rbac_audit_log_repository.py` expands to all user-management action codes via `IN` query.

### Redesign UI — Operation Log Table Alignment (Z1)

- **Table structure updated from 6 columns to 7 columns** to match internal redesign mockup (`doc/design/CronPilot-2026-redesign-mockup.html`).
- **Removed:** `ID` column (was the first column).
- **Renamed:** `用户` → `操作人`, `类型` → `操作类型`, `IP` → `来源 IP`.
- **Split:** Former `内容` column split into two: `操作对象` (task name + "任务 · 组" subtitle) and `变更详情` (summary text from `format_detail_summary()`).
- **Added:** `操作结果` column (✓ 成功 / ✗ 失败 based on `item.result`).
- **View updated:** `operation_result_label`, `cron_by_id`, `group_name_by_id` now passed to redesign template.
- **Subtitle updated:** Page subtitle now reads "任务配置变更审计（创建 / 编辑 / 启动 / 暂停 / 下线）".
- **Modified:** `app/templates/redesign/operation_log.html`, `app/main/views.py`

### Bug Fix — Evaluation Against Wrong Mockup File (7+ Rounds)

- **Root cause:** Comprehensive UI evaluations (rounds 1–7) used `/Users/summer/Downloads/CronPilot-2026-full-mockup.html` (external simplified demo, 5 columns for operation log) as the reference instead of the authoritative internal spec `doc/design/CronPilot-2026-redesign-mockup.html` (7 columns including 变更详情).
- **Fix:** Confirmed authoritative reference is `doc/design/CronPilot-2026-redesign-mockup.html`. Added mandatory rule to `AGENTS.md` and postmortem to `doc/postmortem/2026-08-错误Mockup文件评估复盘.html`.

### Bug Fix — cron_add Exception Redirect (BUG-1)

- **Root cause:** `cron_add` exception handler returned `web_api_return(code=1, ..., url='/cron_list')`. The `js-ajax-form` handler in `common.js` unconditionally redirects to `data.url` regardless of `errcode`, causing users to lose their form data on any server-side exception.
- **Fix:** Removed `url='/cron_list'` from the exception handler return — errors now stay on the form page and show the message inline.
- **Modified:** `app/main/views.py` (line 901, exception handler in `cron_add`)

### Redesign UI — Registration Review Modal System Migration + Global CpModal

- **Bootstrap modal → CpModal migration:** `registration_review.html` still used 2 Bootstrap modals (批准/拒绝) which rendered as transparent overlays in the redesign shell. Migrated to global `CpModal()`.
- **Global `CpModal` extracted:** `CpModal` function moved from `tags.html` inline definition into `redesign-confirm.js` as `window.CpModal`, making it available to all redesign pages without duplication. `tags.html` updated to use the global version (removed local copy, updated button class refs from `tg-m-*` to `cp-modal-*-btn`).
- **Bootstrap fully removed from redesign templates:** `grep "\.modal('show')\|bootstrap.min" app/templates/redesign/` returns 0 results.
- **Modified:** `app/static/js/redesign-confirm.js` (+`window.CpModal`), `app/templates/redesign/registration_review.html` (Bootstrap → CpModal), `app/templates/redesign/tags.html` (use global CpModal)

### Redesign UI — Tag Management Modal System Migration (Z3 完整修复)

- **Bootstrap modal → cp-modal 系统完整迁移**：标签管理页（`/rbac/tags`）原有 4 个 Bootstrap modal（新建标签/重命名标签/查看关联任务/删除确认）在 redesign shell 中全部不可见（透明遮罩/无内容），现已全部迁移到统一的 `CpModal()` 工厂函数 + `CpConfirm.show()` 系统。
- **新建标签**：内嵌表单（标签名/业务组/说明），服务端错误即时反馈，创建中状态防重复提交。
- **重命名标签**：pre-filled 表单（名称/只读组名/说明），提交后刷新。
- **查看关联任务**：只读任务列表表格，单"关闭"按钮。
- **删除确认（普通）**：`CpConfirm.show()` danger 模式，ESC 关闭，覆盖表格删除按钮和 pill 内联 × 按钮。
- **删除确认（强制）**：标签有关联任务时，展示任务列表的 `CpModal` danger variant，用户确认后发起 force 删除请求。
- **移除 Bootstrap 依赖**：从 `tags.html` 删除所有 Bootstrap modal HTML + `bootstrap.min.css/js` 引用，消除样式污染。
- **Modified:** `app/templates/redesign/tags.html` (全量重构 JS/HTML modal 系统)

### Security hardening (OPT-P0-12, OPT-P0-13)

- **SSRF DNS Rebinding fix (OPT-P0-12):** Eliminated TOCTOU window between URL validation and HTTP request execution. `validate_and_resolve_url()` now returns the validated IP address; the scheduler's HTTP client pins the connection to that IP via a custom `_PinnedIPAdapter`, preventing DNS rebinding attacks where a domain resolves to a safe IP during validation but resolves to a private/metadata IP at request time. Fallback to standard `requests` behavior when DNS is unavailable.
- **Login brute-force protection (OPT-P0-13):** In-memory sliding-window rate limiter on login failures. Dual dimensions: per-IP (5 failures / 5 min → 15-min lockout) and per-username (10 failures / 10 min → 30-min lockout). Successful login clears failure counters. Lockout messages shown on login page. No new dependencies; counters are process-local (reset on restart; adequate for single-instance deployments; Redis-backed upgrade path documented).
- **New files:** `app/rbac/login_limiter.py`, `tests/test_login_limiter.py`
- **Modified:** `app/services/url_security.py` (+DNS pinning layer), `app/crons.py` (pinned session), `app/rbac/views.py` (rate limit integration), `tests/test_p0_phase_a.py` (+8 pinning tests)

### ⌘K Sidebar Search (OPT-P2-14-F6)

- **Client-side fuzzy search:** Typing in the Console Mode sidebar search box (`⌘K` to focus) now filters sidebar navigation items and quick actions in real-time. Results displayed in a styled dropdown with keyboard navigation (↑/↓ select, Enter navigate, Escape close).
- **Index sources:** All permission-visible sidebar nav links + hardcoded quick-action shortcuts (e.g. "新增任务", "修改密码"). Auto-deduplicates by `href`.
- **Dark theme support:** Dropdown fully styled for both light and dark Console Mode themes.
- **No dependencies:** Pure vanilla JS (`_cpSearch` IIFE in `common.js`); zero external libraries.
- **Modified:** `app/static/js/common.js` (+`_cpSearch` IIFE, ~90 lines), `app/static/css/console-mode.css` (+dropdown styles)

### Scheduler separation readiness (OPT-P1-12 Step 1-2)

- **Scheduler enable/disable switch:** Environment variable `CRONPILOT_SCHEDULER_ENABLED=false` disables the APScheduler tick loop, allowing the process to run as a Web-only instance. Default: `true` (backward compatible). Use case: horizontal Web scaling where only one instance should run the scheduler.
- **Tuning documentation:** Added scheduler performance tuning guide to `conf.ini.example` covering `max_workers` (default 30), `max_instances` (default 20), capacity planning for second-level tasks (200+ tasks supported at current defaults), and monitoring thresholds (`jobs_active > 0.8 × max_workers` → alert).
- **Modified:** `config.py` (+`CRONPILOT_SCHEDULER_ENABLED`), `app/__init__.py` (conditional `scheduler.start()`), `conf.ini.example` (+tuning guide)

### Confirm Dialog Fix (Redesign UI)

- **Root cause**: `redesign-confirm.js` used Bootstrap button classes (`btn btn-danger`, `btn btn-ghost`) absent from the redesign CSS, resulting in unstyled buttons. `api_token.html` and `users.html` (redesign) used legacy `js-ajax-dialog-btn` triggering `artDialog` (inline tooltip anchored to button), visually messy in the redesign layout.
- **Fix**: Updated `redesign-confirm.js` to use `btn-c btn-danger-c` / `btn-c btn-line`. Replaced `js-ajax-dialog-btn` in `redesign/api_token.html` and `redesign/users.html` with `CpConfirm.show()` (centered modal + dim overlay). Confirmation POST uses hidden form with CSRF token.
- **Postmortem**: `doc/postmortem/2026-08-确认对话框修复与个人资料页.html`
- **Modified**: `app/static/js/redesign-confirm.js`, `app/templates/redesign/api_token.html`, `app/templates/redesign/users.html`

### Personal Profile Editing (Y1)

- **New page `/rbac/profile`:** All logged-in users can now edit their own nickname (花名), email, and job title. Account and role fields are read-only.
- **Sidebar:** Added "个人资料" link in the "个人设置" section (always visible to all roles). Navigation counts updated: Admin 12, Operator 7, Viewer 6.
- **Service:** New `update_own_profile()` function in `app/rbac/services.py` with full validation (email format, nickname length, job title whitelist).
- **Template:** `app/templates/redesign/user_profile.html` — follows the same card style as `change_password.html`, uses `js-ajax-form` + `js-ajax-submit` guard.
- **Modified:** `app/rbac/services.py`, `app/rbac/views.py`, `app/templates/redesign/_sidebar.html`, `tests/test_redesign_sidebar.py` (+nav counts)

**Tests:** 490 pass (was 481) · **Validation:** 6 consecutive failed logins → lockout message; legitimate login succeeds post-restart; scheduler disabled mode verified (`running=False`, routes intact); ⌘K search returns correct results (CDP verified: "用户"→"用户管理", "审"→"注册审批/审计"); full test suite green; DB integrity confirmed.

### Design Token System (Phase 1 · Batch 1-3)

- **Typography tokens:** 5-level font-size scale (`--cp-font-xs` 11px / `--cp-font-sm` 12px / `--cp-font-base` 13px / `--cp-font-md` 14px / `--cp-font-lg` 18px). All 34 `font-size` declarations in `console-mode.css` replaced with token references; zero raw pixel values remain. Eliminates prior 10-value fragmentation including `11.5px` / `12.5px` half-pixel artifacts.
- **Spacing tokens:** 4px-grid system (`--cp-space-1` through `--cp-space-6`: 4/8/12/16/24/32px). All 41 spacing declarations (padding/margin/gap) tokenized; non-grid values (5px/6px/7px/10px) mapped to nearest grid point. Eliminates "adjacent pages feel subtly different" spacing inconsistency.
- **Border-radius tokens:** 3-level semantic scale (`--cp-radius-sm` 3px / `--cp-radius-md` 5px / `--cp-radius-lg` 8px). All 16 applicable `border-radius` declarations tokenized (excluding `50%` circles and compound values).
- **Net result:** 91 raw pixel declarations eliminated from `console-mode.css`; all layout values now flow from 14 centralized tokens in `console-theme.css`.
- **Visual impact:** 76% exact match (0px change), 91% ≤ 0.5px change; notable intentional improvements: nav items slightly more spacious (+2px vertical for better touch targets), collapsed sidebar icons larger (+2px for visibility).
- **Color palette unification (Batch 4):** *Reverted* — Tailwind unification of Flat UI role badge / topbar colors was applied then rolled back per user feedback; original Flat UI colors retained. Palette unification deferred to future phase with proper design review.
- **Button size convergence (Batch 5):** Deprecated `btn-mini` / `btn-small` (Flat UI remnants) replaced with `cp-btn-sm` across all 25 template occurrences. New 3-tier system (`cp-btn-sm` / `cp-btn-base` / `cp-btn-lg`) defined with Design Token values. CI gate: `scripts/audit_button_classes.py --check`.
- **Jumbotron compact (Batch 6):** Marketing-style `jumbotron` headings (120px+ height with tagline) collapsed to transparent inline title in Console Mode. `<p class="lead">` hidden. First-screen table rows increased from ~5–6 to 8+.
- **Modified:** `app/static/css/console-theme.css` (+14 token definitions, +9 color migrations), `app/static/css/console-mode.css` (91 declarations tokenized + button styles + jumbotron compact), 7 template files (btn-mini → cp-btn-sm)
- **New files:** `scripts/audit_button_classes.py` (CI gate)

### UI Redesign Phase 1 — Layout Shell & Dual-Track (OPT-P1-16)

- **Design Token extension:** 9 new semantic tokens (`--cp-canvas`, `--cp-signal`, `--cp-signal-hover`, `--cp-signal-bg`, `--cp-text-muted`, `--cp-text-faint`, `--cp-shadow-sm`, `--cp-font-sans`, `--cp-font-mono`) with light/dark mode overrides in `console-theme.css`.
- **Layout Shell:** CSS Grid-based 3-zone layout (sidebar 220px / topbar 56px / main content) in `redesign-layout.css`. Responsive collapse at 768px.
- **Component base library:** `redesign-components.css` — buttons, tables, cards, stats, badges, forms, pagination, empty states, toasts, modals, skeletons, command palette. All prefixed `cp-` to avoid conflicts.
- **Dual-track switching:** Cookie `cp_ui_version=v2` activates new UI; environment variable `CRONPILOT_FORCE_NEW_UI=true` forces all users. `before_request` sets `g.ui_version`; view functions branch to redesign templates when `v2`.
- **Permission-gated sidebar:** `redesign/_sidebar.html` uses `has_perm()` to show/hide navigation sections by role. Verified for all 4 role types.
- **Shell interactions:** `redesign-shell.js` (sidebar collapse, user dropdown, command palette) + `redesign-theme.js` (light/dark toggle with cookie persistence).
- **Regression test gate:** `tests/test_redesign_sidebar.py` — 12 tests covering sidebar visibility (4 roles × template render) + HTTP reverse-path 403 assertions.
- **New files:** `app/static/css/redesign-layout.css`, `app/static/css/redesign-components.css`, `app/static/js/redesign-shell.js`, `app/static/js/redesign-theme.js`, `app/templates/redesign/_base.html`, `app/templates/redesign/_sidebar.html`, `app/templates/redesign/_topbar.html`, `app/templates/redesign/_welcome.html`, `tests/test_redesign_sidebar.py`
- **Modified:** `app/ui_mode.py` (+`ui_version` injection), `config.py` (+`CRONPILOT_FORCE_NEW_UI`), `app/__init__.py` (+`_set_ui_version` before_request), `app/main/views.py` (+conditional render for v2)

### UI Redesign Phase 2 — Dashboard & Execution Logs (OPT-P1-16)

- **Health-First Dashboard:** 4 top-level stats (总任务/运行中/暂停/异常), Exception Panel (top 5 consecutive-failing tasks), 7-column task table (任务/状态/Cron/业务组/标签/最近执行/操作), icon-only action buttons, dynamic filter chips with counts. Strictly aligned with `doc/design/CronPilot-2026-redesign-mockup.html` via Design QA gate.
- **Execution Logs page:** 7-column layout (任务/执行时间/耗时/HTTP状态/结果/失败原因/操作), row highlighting for failed entries, task info card header, monospace fonts for IDs/times, status dots.
- **Backend enrichment:** `CronRepository.count_consecutive_failing()` (连续失败≥3任务数), `CronRepository.status_counts()` (各状态任务数), `job_log_all_list` v2 route conditional rendering.
- **Light + Dark mode:** Both pages fully themed via CSS variables; verified via screenshots.
- **New files:** `app/templates/redesign/dashboard.html`, `app/templates/redesign/execution_logs.html`
- **Modified:** `app/repositories/cron_repository.py` (+2 methods), `app/main/views.py` (+v2 conditional render for both views)

### Agent Quality: Postmortem Hook System (Process Improvement)

- **Problem:** Agent repeatedly failed to provide proactive postmortems after fixes (3+ occurrences), proving text-only rules insufficient.
- **L1 Hook (postToolUse):** `.cursor/hooks/postmortem-reminder.sh` — injects mandatory classification + postmortem checklist after every `Write`/`StrReplace`/`EditNotebook`. Verified 100% trigger rate.
- **L2 Hook (stop prompt):** `.cursor/hooks.json` stop event — AI evaluates at turn-end whether fixes exist without postmortem; if so, generates `followup_message` (loop_limit=2).
- **Design QA Gate:** Added to implementation plan (`doc/design/UI重设计-实施架构与过渡方案.html` §6.1 #8 + §6.3) — each Phase delivery requires Mockup source comparison before declaring complete.
- **Postmortems:** `doc/postmortem/2026-08-Phase2-Mockup偏离复盘.html`, `doc/postmortem/2026-08-元复盘-复盘失效机制.html`
- **New files:** `.cursor/hooks.json`, `.cursor/hooks/postmortem-reminder.sh`, `.cursor/hooks/stop-postmortem-gate.sh`
- **Modified:** `AGENTS.md`, `.cursor/rules/cronpilot-project.mdc`, `doc/design/UI重设计-实施架构与过渡方案.html`

### UI Redesign: Unified Manual v2 — Index-Only Architecture (OPT-P1-16-MANUAL)

- **Problem:** Manual v1 duplicated numerical values from source documents (Mockup CSS, 视觉规格书, 逐页规格书), introducing 15 inaccuracies via agent memory-based synthesis during integration.
- **Solution:** Rewrote `doc/design/UI重设计-统一执行手册.html` as **pure architecture index** — all sections that previously contained CSS values, font sizes, spacing, color tokens etc. now contain only references/links to their authoritative source documents.
- **Document role (v2):** Batch structure + architecture decisions + quality gates + source document locator. **Zero duplicated numerical values.**
- **Authoritative value chain:** Mockup HTML (CSS lines 8–334) → 视觉規格書 (extracted analysis) → 逐页規格書 (per-page details). Implementation reads from these directly.
- **Modified:** `doc/design/UI重设计-统一执行手册.html` (v1→v2: ~400 lines removed, replaced with index tables + reference links)

### UI Redesign Phase 1 — Token Alignment & Static Guard (Phase 1A/1B/1C)

- **Phase 1A — Redesign token alignment:** Added `.cp-shell`-scoped CSS token overrides in `console-theme.css` to precisely match Mockup-exact values for both light and dark themes. Scoped to `.cp-shell` so v1 legacy pages are completely unaffected.
- **Phase 1B — Sidebar 216px:** Adjusted `redesign-layout.css` grid column width from 220px to 216px (Mockup exact), main content padding to `24px 32px 60px`, max-width to 1180px.
- **Phase 1C — Static guard `check_ui_contract.py`:** New script scans `app/templates/redesign/` for inline-style attributes, legacy Bootstrap/Simpleboot class usage, and hardcoded hex colors. Supports `--check` mode for CI gate. Initial scan: 68 violations identified for Phase 2 remediation.
- **Bug fix — false positive in legacy-class detection:** `check_legacy_classes()` previously used substring matching (`if legacy in class_val`), causing project-specific classes (`btn-danger-c`, `btn-primary-c`, `btn-success-c`, `btn-default-c`) to be falsely reported as Bootstrap violations. Fixed by switching to HTML token-based matching (`set(class_val.split())`). Violation count corrected from 72 → 68.
- **New files:** `scripts/check_ui_contract.py`, `tests/test_check_ui_contract.py` (25 tests: token boundary regression, allowlist exceptions, hex detection)
- **Modified:** `app/static/css/console-theme.css` (+`.cp-shell` scoped token overrides), `app/static/css/redesign-layout.css` (216px sidebar, exact padding/max-width)

**Tests:** 25 new `test_check_ui_contract` tests pass · **Phase 2 plan:** 68 violations → 0 across 6 batches (2A CSS utils → 2B simple files → 2C table colwidths → 2D typography → 2E modal forms → 2F task_detail)

### UI Redesign Phase 2 — Inline Style & Legacy Class Elimination (Batch 2A–2F)

Executed all 6 batches of Phase 2 component extraction. Final result: **68 → 0 violations**. `check_ui_contract.py --check` now clean.

- **Batch 2A — CSS utility layer:** Added micro-utility classes to `redesign-components.css`: `.cp-fw-600`, `.cp-text-xs`, `.cp-text-muted-sm`, `.cp-text-faint-sm`, `.cp-mt-8`, `.cp-mb-12`, `.cp-mt-40`, `.cp-opacity-60`, `.cp-btn--success`.
- **Batch 2B — Simple single-violation files:** Replaced inline styles in `_welcome.html`, `api_token.html`, `run_inspector.html`, `user_form.html`; replaced legacy `btn btn-primary` with `cp-btn cp-btn--primary` in `task_form.html`.
- **Batch 2C — Table column widths:** Extracted `<th style="width:...">` into page-scoped CSS classes in `dashboard.html`, `execution_logs.html`, `users.html`.
- **Batch 2D — Mixed typography files:** Replaced `style="font-weight:600"` and `style="font-size:11px"` with utility classes in `groups.html`, `audit_logs.html`, `operation_log.html`.
- **Batch 2F — task_detail.html:** Added `{% block css %}` with `.td-empty-logs`; replaced legacy button classes; extracted `style="padding:16px 0"`.
- **Batch 2E — Legacy modal form structures:** Converted `control-group`/`controls` → `cp-form-group` in `tags.html`; replaced all legacy Bootstrap button classes (`btn-primary`/`btn-danger`/`btn-default`/`btn-success`) with `cp-btn` variants; extracted remaining inline width/typography styles in `tags.html` and `registration_review.html`.
- **Modified:** `redesign-components.css`, `_welcome.html`, `api_token.html`, `run_inspector.html`, `user_form.html`, `task_form.html`, `dashboard.html`, `execution_logs.html`, `users.html`, `groups.html`, `audit_logs.html`, `operation_log.html`, `task_detail.html`, `tags.html`, `registration_review.html`

### UI Redesign Phase 3A — CI Gate Integration

- **GitHub Actions gate:** New workflow `.github/workflows/ui-contract.yml` runs `check_ui_contract.py --check` + `tests/test_check_ui_contract` on every PR/push that touches `app/templates/redesign/**`, `app/static/css/redesign-*.css`, or the guard script itself. Blocks merges that reintroduce inline styles, legacy Bootstrap classes, or hardcoded hex colors in redesign templates.
- **Trigger paths:** `app/templates/redesign/**`, `app/static/css/redesign-*.css`, `scripts/check_ui_contract.py`, `tests/test_check_ui_contract.py`
- **New files:** `.github/workflows/ui-contract.yml`

### UI Redesign Phase 3B — Visual Regression Baseline

- **Playwright baseline capture:** `scripts/capture_visual_baseline.py` logs in (v2 cookie + dark theme) and captures full-page screenshots of all 13 redesign pages to `tests/visual_regression/baseline/`.
- **Visual regression comparison:** `scripts/compare_visual_regression.py` re-captures current screenshots and computes pixel diff vs baseline using Pillow. Default threshold: 0.5% (CI uses 1% to absorb Linux/macOS font rendering difference). Reports per-page diff % and exits non-zero on failure.
- **Anti-aliasing tolerance:** Pixels with max RGB channel diff ≤ 5 are ignored to prevent false positives from sub-pixel rendering differences.
- **Failure artifacts:** CI uploads `tests/visual_regression/current/` as a downloadable artifact on failure for visual inspection.
- **GitHub Actions gate:** `.github/workflows/visual-regression.yml` triggers on redesign template/CSS changes; starts Flask server, runs comparison, uploads diff screenshots if any page exceeds 1%.
- **New files:** `scripts/capture_visual_baseline.py`, `scripts/compare_visual_regression.py`, `requirements-dev.txt`, `.github/workflows/visual-regression.yml`, `tests/visual_regression/baseline/*.png` (13 screenshots)
- **Baseline:** 13 pages captured, max diff 0.021% (dashboard anti-aliasing), all other pages 0.000%

### UI Redesign Phase 4 — Full Page Implementation (Batches B1–B7)

Complete Mockup-to-code implementation of all 26 v2 routes. Each batch strictly aligned with `doc/design/console-style-demo.html` Mockup.

- **Batch 1 (Dashboard + Execution Logs):** 7-column task table, 4 stats cards, exception panel (top 5 consecutive-failing), status filter chips, scope/tag dropdowns, text search. Execution logs with status dots, duration color-coding, click-to-copy LOG ID, content expand/collapse.
- **Batch 2 (Global Components):** Toast notifications (`redesign-toast.js`), Confirm Modal (`redesign-confirm.js`), Empty State with SVG icon, Skeleton loading states. All integrated into Dashboard and Execution Logs.
- **Batch 3 (Task Detail + Run Inspector):** Task detail page with config display, health badge, tag list. Run Inspector with full response content, HTTP status, timing, fail reason.
- **Batch 4 (Task Form):** Cron expression grid builder (day/weekday/hour/minute/second), human-readable schedule preview, tag chip input with group-scoped autocomplete, scope selector, timeout/method/body configuration.
- **Batch 5 (User Management + System Pages):** Users list (10 columns with role badges, group tags), Groups list, Tags management (CRUD with modals), Registration Review (status filter tabs), Audit Logs (multi-filter: user/action/result/date), Operation Logs, Change Password form, API Token display+reset.
- **Batch 6 (Form Pages):** User Add/Edit form, Group Add/Edit form. Consistent card-based layout with validation hints, disabled states, dark mode support.
- **Batch 7 (Standalone Auth + Utility):** Login, Register, Forgot Password, Complete Profile — fully standalone pages (no `_base.html` dependency) with inline dark mode detection via `cp_theme` cookie. API Doc page. `users_set_active` confirmation page. `cron_retire` confirmation page.

**Architecture decisions:**
- Shared CSS: `redesign-mockup-shared.css` centralizes common Mockup-derived classes (`c-table`, `btn-c`, `f-input`, `page-head`, `pg-*` utilities) for cross-page reuse.
- Color token compliance: All colors use `var(--cp-*)` variables; `--cp-on-filled` introduced for text on filled backgrounds. Zero hardcoded hex in templates (CI gate `audit_hardcoded_colors.py --check`).
- RBAC-aware rendering: All action buttons, navigation items, and page access controlled by `has_perm()` checks.
- Dual-track coexistence: v1 and v2 templates coexist; `CRONPILOT_FORCE_NEW_UI=true` in startup script forces v2 as default.

**New files (26 templates):** `app/templates/redesign/dashboard.html`, `execution_logs.html`, `task_detail.html`, `run_inspector.html`, `task_form.html`, `users.html`, `groups.html`, `tags.html`, `registration_review.html`, `audit_logs.html`, `operation_log.html`, `change_password.html`, `api_token.html`, `user_form.html`, `group_form.html`, `api_doc.html`, `login.html`, `register.html`, `forgot_password.html`, `complete_profile.html`, `users_set_active.html`, `cron_retire.html`, `_base.html`, `_sidebar.html`, `_topbar.html`, `_welcome.html`

**New CSS/JS:** `app/static/css/redesign-mockup-shared.css`, `app/static/css/redesign-pages.css`, `app/static/js/redesign-toast.js`, `app/static/js/redesign-confirm.js`

**Modified:** `app/rbac/views.py` (v2 conditional rendering for all RBAC routes + `active_nav` context), `app/main/views.py` (v2 conditional rendering for main routes + Jinja filters), `app/main/__init__.py` (+`humanize_schedule`, `format_cron_expression` filters), `app/static/css/console-theme.css` (+`--cp-on-filled`, `.cp-shell` scoped tokens), `app/static/css/redesign-layout.css` (192px sidebar, rounded nav items, left-border active indicator), `scripts/start_local_full.sh` (+`CRONPILOT_FORCE_NEW_UI=true`)

### UI Redesign — Layout Refinement & Consistency Fixes

- **Sidebar narrowing:** Grid column reduced from 220px → 192px (Mockup exact). Nav item padding/font-size refined, rounded corners (`border-radius: 6px`), active state uses `border-left: 2px solid var(--cp-signal)` + `background: var(--cp-surface-2)`.
- **Title separator unification:** All 22 v2 templates now use ` — ` (em-dash) consistently in `<title>` tags; corrected `dashboard.html` and `execution_logs.html` which used ` - ` (hyphen).
- **Sidebar `active_nav` completeness:** Fixed missing `active_nav` context for 3 views: `change_password` → `'password'`, `api_token_page` → `'api-token'`, `api_doc` → `'apidoc'`. Sidebar now highlights the correct item on all 12 navigable pages.
- **CSS token compliance:** Replaced 2 remaining `color: #fff` instances in `redesign-layout.css` (`.cp-nav-badge`, `.cp-topbar-avatar`) with `var(--cp-on-filled)`.

**Tests:** 438 pass · **Dark mode:** All 12 pages verified via browser screenshots · **Mockup alignment:** All differences confirmed as user-authorized changes or RBAC-correct behavior.

---

## [3.0.0] — 2026-08-10

### Console Mode UI & Dual Theme (OPT-P2-14)

- **Dual UI Mode (Classic/Console):** New "Console" mode with vertical sidebar navigation, collapsible to icon-only (56px). Switch via topbar button or ⌘B keyboard shortcut. Classic mode remains default and completely unchanged.
- **Dual Theme (Light/Dark):** Full dark theme with 60+ CSS variables redefined. Toggle via button or ⌘\ shortcut. Cookie-persisted, SSR-rendered (no FOUC).
- **Sidebar:** Fixed left panel (220px) with grouped navigation (任务/管理/个人 sections), search placeholder (⌘K), permission-gated items (`has_perm`), pending registration badge, mode/theme switches in footer.
- **Responsive:** Three breakpoints — >1024px (full sidebar), 768–1024px (auto icon-only), ≤768px (hidden + hamburger → overlay). Table horizontal scroll on mobile.
- **Animations:** Theme switch smooth transitions (0.25s), nav item hover translateX, button lift effect, table row highlight, badge pulse, pagination hover. All respect `prefers-reduced-motion`.
- **Tooltips:** Collapsed sidebar hover shows floating label tooltip (pure CSS). Active page left-edge indicator bar. "CP" brand abbreviation in collapsed header.
- **Keyboard shortcuts (Console mode only):** ⌘K (search focus), ⌘B (sidebar toggle), ⌘\ (theme switch), Escape (close/blur).
- **Zero regression:** All styles scoped under `[data-ui-mode="console"]` / `[data-theme="dark"]` selectors; Classic+Light users see zero change.
- **New files:** `app/ui_mode.py`, `app/static/css/console-mode.css` (~960 lines), `app/templates/rbac/_sidebar_console.html`, `tests/test_ui_mode.py`.
- **Modified:** `admin_base.html` (attributes + sidebar include), `_topbar.html` (hamburger), `common.js` (+80 lines), `console-theme.css` (+Dark block).

**Tests:** 428 pass (11 new UI mode tests) · **Design:** `doc/design/console-style-dual-mode-design.html`

---

## [2.9.0] — 2026-08-07

### Task group affiliation, tag system & error pages (OPT-P1-11)

- **Single-group affiliation:** Each task belongs to exactly one business group (GROUP) or is globally visible (GLOBAL). `cron_infos.group_id` column removed; replaced by `task_groups` association table (one-to-one per task). `scope_type` (GLOBAL/GROUP) retained for semantic distinction.
- **Business tags (group-isolated):** Free-text tag system for tasks (country, business line, service name, etc.). Tags are isolated per business group — same tag name can exist independently in different groups. Autocomplete scoped to the selected group.
- **Inline chip tag input:** Tags displayed as chips inside the input field (email-recipient style); Enter/comma to add, Backspace to remove, autocomplete dropdown on typing.
- **Tag filtering:** New "标签" dropdown on task list filter bar for filtering by tag.
- **Tag management:** Admin page (`/rbac/tags`) for renaming and deleting tags. Manager admins only see tags from their assigned groups.
- **Task create/edit:** Single-select dropdown for business group; tag input with inline chips and autocomplete.
- **Unified error pages:** 403 (no permission), 404 (not found), and 500 (server error) now share a consistent template with icon, friendly message, and "back" / "home" navigation links. Internal permission identifiers (e.g. `cron:write`) no longer exposed to users.
- **Removed `code` field:** `resource_groups.code` column and external translation API dependency (`api.mymemory.translated.net`) removed. Group creation is now instant (<50ms vs 1-3s). `name` column given UNIQUE constraint.
- **Migration:** `scripts/ensure_business_tables.py` auto-migrates existing `group_id` data to `task_groups`, migrates tags to group-isolated model, and drops `code` column (all idempotent).
- **API breaking change:** `cron_query` and `cron_detail` responses now return `group_id: int|null` (via `task_groups` lookup) instead of the removed `cron_infos.group_id` column.
- **New models:** `TaskGroup`, `Tag` (with `group_id` for isolation), `TaskTag` (with unique constraints and indexes).
- **Deleted:** `app/rbac/group_code.py`, `app/templates/rbac/forbidden.html`, `app/templates/errors/404.html`, `app/templates/errors/404_guest.html`.
- **New norms:** "数据库字段删除/迁移前置分析"、"验证自主性原则"、"新模板/新路由自检清单"、"双渲染路径上下文一致性"、"Import 可达性验证"、"复盘质量门禁"。

**Tests:** 428 pass · **Design:** `doc/design/任务创建页改进设计.html`

---

## [2.8.0] — 2026-08-05

### User registration & approval (OPT-P1-10)

- **Registration form** (`/rbac/register`): Email-based username extraction, job title (8 categories + custom "other"), nickname, password, role selection (operator/viewer; admin blocked with prompt), multi-group selection, reason field.
- **Forgot password** (`/rbac/forgot_password`): Static hint page directing users to contact their group admin.
- **Login page enhancements**: Registration/forgot-password links; automatic pending/rejected status display when a user with a matching application attempts to login.
- **Approval management** (`/rbac/registration_review`): Status filtering (pending/approved/rejected/expired), pagination, approve/reject modals (consistent Bootstrap modal style), pending count badge in navigation.
- **Security**: Concurrent registration prevention via `pending_username` UNIQUE index; lazy expiration on each new submission; admin role backend validation; CSRF protection on all forms.
- **Anti-double-click**: Submit button disabled + "提交中…" text on form submission with 3-second auto-recovery.
- **User list columns**: Added 花名 (nickname) and 岗位 (job title) columns to user management page.
- **Integration tests**: 12 new HTTP-layer tests covering template rendering, form submissions, approval/rejection flows, and pagination macro correctness.

**Tests:** 388 pass · **Design:** `doc/design/用户注册审批与忘记密码设计.html`

---

## [2.7.1] — 2026-08-03

### Documentation reorganization & CI automation

- **Subdirectory structure:** Reorganized 40+ `doc/` files into 7 semantic subdirectories (`arch/`, `deps/`, `design/`, `ops/`, `plan/`, `product/`, `qa/`). All internal cross-references updated across 80+ HTML/MD files.
- **Orphan cleanup:** Removed 8 legacy/orphan files (unused images, stale deployment docs, `supervisors.conf`).
- **Index rewrite:** `doc/index.html` rebuilt with version timeline and quick-entry navigation.
- **Broken link fixes:** Corrected 17 stale `doc/` paths in `README.md`, `INSTALL.md`, and `.cursor/rules/*.mdc` caused by subdirectory migration.
- **OPT numbering fixes:** Corrected OPT-P2-12→15 and OPT-P2-13→16 references in design docs; updated Prometheus RFC (OPT-P2-05) status to delivered.
- **RELEASE_NOTES consistency:** Merged `[Unreleased]` into v2.7.0, corrected test count (334), translated Chinese headers to English, completed 15-version summary table.

### New CI scripts (doc-completeness.yml)

| Script | Check |
|--------|-------|
| `check_doc_completeness.py` | `doc/index.html` registration for all `doc/**/*.html` files |
| `check_doc_links.py` | Full-repo `doc/` reference reachability (583 refs scanned) |
| `check_opt_consistency.py` | OPT numbering consistency + design doc status vs. roadmap alignment |
| `check_version_consistency.py` | Enhanced: `[Unreleased]` residual check + version summary table completeness |

### Process improvement

- **Strengthened post-mortem rule:** Trigger condition expanded from "user-reported bugs" to **all fixes** (including self-discovered issues during review/audit). Added mandatory pre-delivery self-check: "Did I fix something? → Is the post-mortem in my reply?"

**Tests:** 334 pass · **CI gates:** all 5 documentation checks pass

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

### Time-column index enforcement (OPT-P2-17)

- **Model-level `index=True`:** All `create_time` / `update_time` / `created_at` / `updated_at` columns across 7 tables now carry `index=True` in their `mapped_column()` declaration.
- **Runtime index backfill:** `scripts/ensure_business_tables.py` → `_ensure_time_column_indexes()` idempotently creates `ix_<table>_<column>` indexes on service startup for existing databases.
- **Tables covered:** `rbac_audit_logs`, `rbac_users`, `resource_groups`, `cron_infos` (×2), `job_log`, `job_health` (plus pre-existing `operation_log`).

### User management & audit log search

- **User management search:** Username fuzzy search on the user list page.
- **Audit log multi-dimensional search:** Filter by username (fuzzy), action, status, and time range.
- **API token auto-issuance:** `ensure_existing_users_have_token()` auto-issues tokens for pre-S6 users on startup.

### Documentation reorganization

- **Subdirectory structure:** `doc/` reorganized into 7 subdirectories: `arch/`, `design/`, `plan/`, `deps/`, `ops/`, `product/`, `qa/`. 80 files moved, 85 cross-references updated.
- **Orphan cleanup:** Removed 11 orphaned/legacy files (screenshots, deprecated configs, old platform docs).
- **`index.html` full refresh:** Updated to v2.7.0, added 4 missing design documents, all subdirectory links verified.
- **`check_doc_completeness.py`:** New CI script ensuring all `doc/*.html` files are registered in `doc/index.html`.

### Engineering norms

- **Time-column index norm:** New models missing `index=True` on time columns are review blockers.
- **Query performance assessment:** Mandatory for all new query/search features during design phase.
- **UI style consistency:** Prohibits inline styles for layout; defines standard dimensions for toolbar elements.
- **API path guard:** `tests/test_api_path_guard.py` ensures all `/api/` paths in templates map to real routes.

### Tests

- 334 tests pass, covering admin scope differentiation, audit log scope filtering, time-column indexes, API path guard, and all prior features.

---

## [2.6.0] — 2026-07-31

### Release scope (all commits after v2.5.0)

- Includes all commits in `v2.5.0..v2.6.0`: `8f683ce` and `8979424`.
- This release combines color-system hardening, API access-token hardening, user-level token UX completion, and query-only API documentation redesign.

### Frontend color consolidation and maintainability

191 hardcoded hex colors across 21 files (57 distinct values) consolidated into CSS Custom Properties (`var(--cp-*)`). Visual output is pixel-identical; color changes now require editing a single variable in `console-theme.css`.

- **`app/static/css/console-theme.css` (new):** 60 semantic CSS variables covering text hierarchy, background/surface, border, accent, success/danger/warning palettes, execution status, role badges, topbar, retired chip, and link colors. `--cp-*` prefix avoids collisions with simpleboot/Bootstrap.
- **20 Jinja2 templates consolidated:** `admin_base.html` (15), `cron_list.html` (68), `cron_add.html` (15), `cron_edit.html` (14), and 16 additional templates — all replaced with `var(--cp-*)` references.
- **Vue component consolidation:** `CronFormValidator.vue` — 10 hardcoded colors replaced with CSS variables; built assets updated.
- **Semantic class extraction:** Role badges (`.topbar-role-*`) and execution status labels (`.label-timeout/running/pending/danger`) moved from `admin_base.html` to `console-theme.css`, eliminating duplication.
- **Dead file cleanup:** Removed zero-reference `app/templates/_admin_nav.html`.

### Audit tooling and CI gate

- **`scripts/audit_hardcoded_colors.py` (new):** Full scan of templates and Vue components for hardcoded colors. Supports `--check` (CI mode, exit 1), `--mapping` (value→token map), `--csv` (export). Built-in 57-value 100% mapping.
- **`.github/workflows/color-audit.yml` (new):** CI gate blocking PRs containing hardcoded colors.
- **`tests/test_form_name_guard.py` (new):** 3 static guard tests preventing accidental modification of `CronFormValidator.vue` field `name` attributes (`day_of_week`/`day`/`hour`/`minute`/`second`/`req_url`/`req_method`/`req_body`).

### API access_token hardening (minimal Scope mitigation)

- New opt-in `conf.ini` setting `api_access_token_required` (default `0`, no behavior change). When set to `1`, production startup now fails fast if `api_access_token` is empty (`scripts/check_conf_production.py` + `config.ProductionConfig.init_app`), preventing unnoticed unauthenticated `/api/*` access.
- Failed API token checks now write an audit trail (`rbac_audit_logs`, `action='api:deny'`) for traceability.
- See [RBAC 与群组权限管理评审报告](doc/design/RBAC与群组权限管理评审报告.html) for the underlying review and [资源隔离与Scope设计 §七](doc/design/资源隔离与Scope设计.html#future) for scope/limitations (still a shared deployment-level token; per-group API tokens remain a future RFC).

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

### Deployment docs

- **Non-Docker deployment guide** added §3 "Frontend development environment": Node.js only required for development, nvm setup, Node.js vs Python environment isolation.
- **README.md** added §2.1 "Frontend development environment (optional)".

### Tests

- 322 tests pass (covering color audit gate, RBAC/S6, query-only API doc catalog, and scope query endpoints).

---

## [2.5.0] — 2026-07-29

### Per-task timeout configuration — Phase B2 (OPT-P1-01)

- **`CronInfos.timeout_sec` 字段（可空 INT）：** NULL 表示使用系统默认 5 s；有效范围 1–120 s。`ensure_business_tables` 幂等 DDL 补列，存量数据库安全升级。
- **表单 UI：** 新增/编辑任务表单新增"超时（秒）"输入框（留空使用默认 5 s，最大 120 s）。
- **校验门禁（`cron_validator.py`）：** 非空时校验 1≤timeout_sec≤120，非整数/越界均返回 `timeout_sec` 字段错误。
- **执行路径（`cron_do`）：** 使用 `cif.timeout_sec or _DEFAULT_TIMEOUT_SEC` 动态读取 per-task 超时，默认值从 120 s 调整为 5 s。
- **API schema（`CronUpsertIn`）：** 新增可选 `timeout_sec` 整数字段（1–120），通过 APIFlask 文档自动暴露。
- **详情页：** `job_log_detail.html` 新增"超时限制 Xs"展示，与耗时字段并排显示。
- **测试（`test_b2_timeout_config.py`）：** 14 条新测试覆盖合法值、边界值、非法值（0/-1/121/非整数/浮点）、NULL 传播、service 写入。

### Execution state machine — Phase B1 (OPT-P1-01)

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

## [2.4.0] — 2026-07-27 · Frontend modernization (Vite + Vue 3) + Admin UX improvements

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

## [2.3.0] — 2026-07-24 · API contract standardization (OpenAPI 3.0 + Swagger UI)

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

## [2.2.0] — 2026-07-24 · Observability (structured logging + Prometheus metrics) + bug fixes

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

### Prometheus metrics (OPT-P2-05 — RFC: doc/design/P1可观测性-Prometheus指标RFC.html)

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

## Version index

| Version | Highlights |
|---------|------------|
| **3.0.0** | Console Mode UI, dual-mode switch (Classic/Console), dark theme, responsive layout, keyboard shortcuts |
| **2.9.0** | Task group affiliation (single-group), tag system (group-isolated), unified error pages, `code` field removal, API breaking change |
| **2.8.0** | User registration & approval, forgot password hint, concurrent prevention, anti-double-click |
| **2.7.1** | Documentation reorganization (7 subdirs), 3 new CI scripts, broken link/OPT fixes, post-mortem rule strengthening |
| **2.7.0** | Admin scope differentiation, audit log scope filtering, search, time-column indexing, doc reorganization |
| **2.6.0** | Color system consolidation, API access_token hardening, S6 user-level token, query-only API docs |
| 2.5.0 | Execution state machine (B1) + per-task timeout (B2) + frontend form validator (F3-a) |
| 2.4.0 | Frontend modernization (Vite + Vue 3), reactive filter bar, password visibility toggle |
| 2.3.0 | API contract standardization (OpenAPI 3.0 + Swagger UI) |
| 2.2.0 | Structured JSON logging, Prometheus metrics, CSRF / timestamp bug fixes |
| **2.1.1** | Cluster mutex atomicity, production SECRET_KEY, admin CSRF |
| 2.1.0 | Flask 2.3 + SQLAlchemy 2.0 runtime upgrade |
| 2.0.0 | Task center, GET/POST trigger, account lifecycle |
| 1.2.0 | Topbar identity, seed admin permissions, start/pause wording |
| 1.1.0 | Resource group isolation, self-service password change |
| 1.0.0 | Multi-user RBAC, task lifecycle, operation audit |
| 0.2.0 | Execution observability, dependency & deployment hardening |
| 0.1.1 | `/docs/` documentation portal, multi-version Python, CI |
| 0.1.0 | Initial release |
