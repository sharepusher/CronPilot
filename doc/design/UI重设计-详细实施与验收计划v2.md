# CronPilot UI Redesign — 前端重构详细实施与验收计划 v2

> HTML 版：[UI重设计-详细实施与验收计划v2.html](UI重设计-详细实施与验收计划v2.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# CronPilot UI Redesign — 前端重构详细实施与验收计划 v2

**⚠️ SUPERSEDED**：本文档已合入 [统一执行手册 (OPT-P1-16-MANUAL)](UI重设计-统一执行手册.html)。  
本文档保留供历史追溯，**不再维护**。执行以统一手册为准。

**文档编号**：OPT-P1-16-IMPL-v2  
**状态**：~~设计评审（待确认）~~ → 已合入统一手册  
**前置**：替换 `doc/design/UI重设计-实施架构与过渡方案.html` 中的粗粒度 Phase 描述  
**Mockup 源**：`doc/design/CronPilot-2026-redesign-mockup.html`（22 views + 3 standalone auth pages）  
**教训整合**：Phase 2 Mockup 偏离事故 → 每页强制 Design QA；Agent 复盘失效 → Hook 程序化强制

## 一、当前状态总览

| Phase | 范围 | 状态 | 完成度 |
| --- | --- | --- | --- |
| 1 | Shell（Layout + Sidebar + Topbar + Theme） | 已完成 | 90% |
| 2 | Dashboard + 执行记录 | 已完成 | 70%（结构对齐，数据待丰富） |
| 3 | 任务详情 + 执行详情 | 未开始 | 0% |
| 4 | 任务表单（新建/编辑） | 未开始 | 0% |
| 5 | 管理页面（6 个子页面） | 未开始 | 0% |
| 6 | Auth + 个人设置 | 未开始 | 0% |
| 7 | 全局组件（Toast/Modal/Palette/Empty/Skeleton） | 部分 | 30%（结构在 base，功能未完成） |
| 8 | 深色模式/响应式/全量验收 | 未开始 | 10%（theme toggle 已工作） |

**关键问题**：当前从 v2 sidebar 点击"用户管理""业务组"等未实现页面，会跳到经典 `admin_base.html` 布局，体验断裂。Phase 3-6 的目标是消除这一断裂。

## 二、总体架构策略

### 2.1 技术约束

- Python 3.8–3.11 + Flask 2.3 SSR（Jinja2 模板）
- jQuery 全局可用（`common.js`）；新增 JS 使用 IIFE/ES Module
- CSS 变量驱动（`--cp-*` 在 `console-theme.css`）
- 新模板继承 `redesign/_base.html`（独立于 Bootstrap `admin_base.html`）
- 新组件使用 `.cp-*` 前缀（避免 Bootstrap/Flat UI 冲突）
- 表单保留 `js-ajax-form` + `js-ajax-submit` 约定

### 2.2 文件组织

```
app/templates/redesign/
├── _base.html              # Shell（已完成）
├── _sidebar.html           # Nav（已完成）
├── _topbar.html            # Header（已完成）
├── _pagination.html        # 共享分页宏（Phase 3 提取）
├── _breadcrumb.html        # 面包屑宏
├── dashboard.html          # Phase 2 ✓
├── execution_logs.html     # Phase 2 ✓
├── task_detail.html        # Phase 3
├── run_inspector.html      # Phase 3
├── task_form.html          # Phase 4（新建+编辑共用）
├── users.html              # Phase 5a
├── user_form.html          # Phase 5a
├── groups.html             # Phase 5b
├── group_form.html         # Phase 5b
├── reg_review.html         # Phase 5c
├── audit_log.html          # Phase 5d
├── operation_log.html      # Phase 5d
├── tags.html               # Phase 5e
├── change_password.html    # Phase 6
├── api_token.html          # Phase 6
├── api_doc.html            # Phase 6
└── auth/
    ├── login.html          # Phase 6（独立，不继承 _base）
    ├── register.html       # Phase 6
    └── forgot.html         # Phase 6

app/static/css/
├── console-theme.css       # Design Tokens（已完成）
├── redesign-layout.css     # Shell Grid（已完成）
├── redesign-components.css # 组件库（已完成，Phase 3+ 扩展）
└── redesign-pages.css      # 各页面特定样式（Phase 3 新建，提取 inline CSS）

app/static/js/
├── redesign-shell.js       # Shell 交互（已完成）
├── redesign-theme.js       # Theme 切换（已完成）
├── redesign-cmd-palette.js # Command Palette（Phase 7）
├── redesign-toast.js       # Toast 全局 API（Phase 7）
└── redesign-confirm.js     # Confirm Modal 全局 API（Phase 7）
```

### 2.3 路由分支策略

每个页面在对应 view 函数中添加 `if getattr(g, 'ui_version', 'v1') == 'v2'` 分支，渲染 `redesign/*.html`。Flask 路由 URL 不变，前端通过 Cookie 切换。

## 三、逐 Phase 详细实施规格

### Phase 2 补完 — 数据丰富 + 细节对齐

范围：Dashboard + 执行记录现有页面的数据补充

#### 2.1 Dashboard 数据补完

| Mockup 要求 | 当前状态 | 需要实现 |
| --- | --- | --- |
| Stats #4 子文本：成功率 % | 仅显示任务数 | 计算 today\_success\_rate 传入模板 |
| 最近执行列：耗时 + 相对时间 | 仅时间戳 | 传入 `take_time` + 模板 humanize |
| 下次执行列：计算时间 | 静态文案 | `croniter` 计算 next\_run\_at |
| Exception Panel：P95 延迟警告 | 仅连续失败 | 可选（Phase 8 polish） |
| Action "更多" 下拉菜单 | 无 | ⋮ dropdown（编辑/查看详情/查看日志/下线） |

#### 2.2 执行记录数据补完

| Mockup 要求 | 当前状态 | 需要实现 |
| --- | --- | --- |
| Filter chip："超时" | "异常"（not\_success） | 拆分为 失败/超时 两个独立 chip |
| 业务组下拉过滤 | 无 | 添加 group dropdown filter |
| 详情链接 → Run Inspector | → 经典 job\_log\_detail | Phase 3 完成后改指向 v2 |

#### 2.3 验收标准

```
# 结构对齐
curl -sb 'cp_ui_version=v2' http://127.0.0.1:5001/cron_list | grep -c 'hf-stat'  # = 4
curl -sb 'cp_ui_version=v2' http://127.0.0.1:5001/cron_list | grep 'exc-panel'    # exists
curl -sb 'cp_ui_version=v2' http://127.0.0.1:5001/cron_list | grep 'act-btn'      # exists

# 数据
curl -sb 'cp_ui_version=v2' http://127.0.0.1:5001/cron_list | grep '成功率'         # exists
curl -sb 'cp_ui_version=v2' http://127.0.0.1:5001/job_log_all_list | grep '超时'    # chip exists

# 截图对照 Mockup view-dashboard / view-logs
```

### Phase 3 — 任务详情 + 执行详情 (Run Inspector)

Mockup views: view-detail, view-run-inspector, view-run-failed

#### 3.1 任务详情 (`task_detail.html`)

**路由**：`/cron_detail/<id>` 或 `/job_log_list?id=<cron_id>` 的详情链接

**Mockup 结构 (view-detail)：**  
├── .page-head: 面包屑 + H1 + task-id badge + lifecycle/tags/group badges  
├── .detail-header: actions (立即执行 / 暂停 / 编辑 — cp-btn 文字按钮)  
├── .detail-grid (2×2 CSS Grid):  
│ ├── Card 1: 健康度 (.health-big) + 连续失败 + 24h成功率 + P95延迟  
│ ├── Card 2: 调度 (.schedule-big) — cron + human + next + timezone  
│ ├── Card 3: 最近执行 (.recent-runs) — 最近5条 + "查看全部"链接  
│ └── Card 4: 配置信息 (.config-grid) — URL/超时/业务组/创建人/时间  
└── (无分页)

#### 数据需求

| 字段 | 来源 | 备注 |
| --- | --- | --- |
| cron\_info.\* | CronInfos model | task\_name, task\_keyword, req\_url, time\_out, status, cron\_str, run\_date |
| health.\* | JobHealth model | consecutive\_failures, health\_status, last\_fail\_at, last\_success\_at |
| recent\_runs (5条) | JobLog 最新5条 | http\_status, status, take\_time, create\_time |
| success\_rate\_24h | 计算 | 24h 内成功数/总数 |
| next\_run\_at | croniter 计算 | 基于 cron\_str + run\_date |
| group\_name | task\_groups 关联 | 业务组名称 |
| tags | task\_tag\_map | 标签列表 |

#### 3.2 执行详情 / Run Inspector (`run_inspector.html`)

**Mockup 结构 (view-run-inspector / view-run-failed)：**  
├── .page-head: 3级面包屑 (任务中心 → 任务名 → 执行 #ID)  
├── .run-header: run-id + .run-badge(.ok/.fail) + run-meta(HTTP/耗时/时间/触发方式)  
├── .run-section "请求": mono-block (URL + Headers)  
├── .run-section "响应": mono-block (HTTP response body)  
├── .run-section "业务日志": mono-block (进度回传内容)  
├── .run-section "元数据": key-value pairs  
└── [失败特有] .run-section.danger: 错误详情 + 连续失败 + 最后成功时间

#### 数据需求

| 字段 | 来源 | 备注 |
| --- | --- | --- |
| job\_log.\* | JobLog model | 所有字段 |
| cron\_info.task\_name | 关联查询 | 面包屑用 |
| progress\_logs | JobLogContent / add\_log 内容 | 业务日志 |

#### 3.3 验收标准

```
# task_detail.html
curl -sb 'cp_ui_version=v2' http://127.0.0.1:5001/cron_detail/1 | grep 'detail-grid'  # exists
curl -sb 'cp_ui_version=v2' http://127.0.0.1:5001/cron_detail/1 | grep 'health-big'   # exists
curl -sb 'cp_ui_version=v2' http://127.0.0.1:5001/cron_detail/1 | grep 'recent-runs'  # exists

# run_inspector.html
curl -sb 'cp_ui_version=v2' http://127.0.0.1:5001/job_log_detail/1 | grep 'run-header'  # exists
curl -sb 'cp_ui_version=v2' http://127.0.0.1:5001/job_log_detail/1 | grep 'run-badge'   # exists
curl -sb 'cp_ui_version=v2' http://127.0.0.1:5001/job_log_detail/1 | grep 'run-section' # ≥3

# Design QA: Read mockup view-detail → 对照 4 张 card、badges、actions
# Design QA: Read mockup view-run-inspector → 对照 4 个 section
# 截图：浅色 + 深色各一张
```

### Phase 4 — 任务表单（新建 + 编辑）

Mockup views: view-form, view-task-add

#### 4.1 表单结构 (`task_form.html`)

**Mockup 结构 (view-form / view-task-add)：**  
├── .page-head: 面包屑 (任务中心 → [任务名] → 编辑配置 / 新建任务)  
├── .form-section "基础信息":  
│ ├── 任务名称 (input, required)  
│ ├── 任务关键词 (input)  
│ └── 业务组 (select — 受 Scope 限制)  
├── .form-section "请求配置":  
│ ├── 回调 URL (input, required)  
│ ├── 请求方式 (select: GET/POST)  
│ └── 超时时长 (input, default=30s)  
├── .form-section "调度配置":  
│ ├── Cron 表达式 (input + 预设 chips: 每分钟/5分钟/小时/天/周一)  
│ └── 人类可读说明 (auto-generated from cron, 只读)  
├── .form-section "Lifecycle" (编辑模式独有):  
│ └── 状态切换 (toggle: 运行/暂停)  
└── .form-actions: 保存 (.cp-btn--primary) + 取消 (.cp-btn--ghost)

#### 交互要点

- 使用 `js-ajax-form` + `js-ajax-submit` 提交模式
- Cron 预设 chips 点击填入对应表达式
- 业务组选择受当前用户 Scope 限制（非 seed admin 只能选自己的组）
- 编辑模式：表单预填已有数据
- 新建模式：字段为空，无 Lifecycle section
- 标签输入：chip-style inline tag input（复用已有实现）

#### 4.2 验收标准

```
# 结构
curl -sb 'cp_ui_version=v2' http://127.0.0.1:5001/cron_add | grep 'form-section' | wc -l  # ≥3
curl -sb 'cp_ui_version=v2' http://127.0.0.1:5001/cron_edit/1 | grep 'form-section' | wc -l  # ≥4

# 功能
# POST 新建任务 → 201/JSON redirect
# POST 编辑任务 → 200/JSON redirect
# 非 seed admin 只能选自己组

# Design QA: Read mockup view-form → 对照 section 数、字段名、cron chips
```

### Phase 5 — 管理页面（6 个子页面）

Mockup views: view-users, view-groups, view-audit, view-optlog, view-reg-review, view-tags

#### 5a. 用户管理 (`users.html` + `user_form.html`)

**Mockup 结构 (view-users) — 9 列表格：**  
用户(avatar+username+email) | 花名 | 岗位 | 角色 | 业务组 | 状态 | 密码状态 | 创建时间 | 操作(180px)
  
  
**操作列**：文字按钮 (重置密码 / 停用) + icon 编辑按钮  
**已停用行**：opacity: 0.6，仅显示 "查看"  
**Footer**：说明文案 "账户一旦停用不可恢复..."

**Mockup 结构 (view-user-add / view-user-edit)：**  
├── .form-section "基本信息": 用户名/邮箱/花名/岗位/初始密码  
├── .form-section "权限配置": 角色(select) + 业务组(select)  
├── [编辑] .form-section "安全操作": 重置密码 + 重置 Token  
└── [编辑] .danger-zone: 停用账户（不可恢复）

#### 5b. 业务组 (`groups.html` + `group_form.html`)

**Mockup 结构 (view-groups) — 卡片网格：**  
├── Overview: 3-col card grid (组名 + 描述 + stats: 成员/任务/异常)  
├── 点击展开: detail panel  
│ ├── 左列：成员列表 (avatar + username + role)  
│ └── 右列：权限 Scope checklist + 任务列表 (health dots)  
└── Header: "新建业务组" 按钮

#### 5c. 注册审批 (`reg_review.html`)

**Mockup 结构 (view-reg-review) — 9 列：**  
邮箱 | 用户名 | 花名 | 岗位 | 申请角色 | 业务组 | 申请原因 | 申请时间 | 操作(✓批准/✗拒绝)
  
  
**Status chips**：待审核(.warning) / 已通过(.success) / 已拒绝(.danger) / 已过期(.neutral)

#### 5d. 审计日志 (`audit_log.html`) + 操作记录 (`operation_log.html`)

**审计日志 (view-audit) — 6 列：**  
时间 | 用户名 | 动作(badge) | 说明 | 来源 IP | 结果  
失败登录行高亮 danger-bg
  
  
**操作记录 (view-optlog) — 7 列：**  
操作人 | 操作类型 | 操作对象 | 变更详情 | 操作结果 | 时间 | 来源 IP  
Filters: search + 操作类型 select + 时间范围 select

#### 5e. 标签管理 (`tags.html`)

**Mockup 结构 (view-tags) — Namespace chip 布局：**  
├── 4 namespace groups: 业务域 / 优先级 / 生命周期 / 区域  
├── 每组: pill chips with count badges  
└── P0/P1 使用 danger/warning 颜色

#### 5.x 验收标准（统一）

```
# 每个子页面验收：
# 1. curl 列数验证
curl -sb 'cp_ui_version=v2' http://127.0.0.1:5001/rbac/users | grep -c '<th'  # = 9
curl -sb 'cp_ui_version=v2' http://127.0.0.1:5001/rbac/registration_review | grep -c '<th'  # = 9

# 2. Design QA: Read mockup → 逐列对照
# 3. 4 角色验证：seed admin / biz admin / operator / viewer
# 4. 截图：浅色 + 深色
# 5. v1 无回归：cp_ui_version=v1 经典页面正常
```

### Phase 6 — Auth + 个人设置

Mockup views: login-page, register-page, forgot-page, view-password, view-api-token, view-apidoc

#### 6.1 Auth 页面（独立布局，不继承 \_base.html）

- `auth/login.html` — 登录表单 + 忘记密码链接 + 注册链接
- `auth/register.html` — 注册表单 + 业务组勾选 + 角色申请
- `auth/forgot.html` — 管理员重置提示页

#### 6.2 个人设置（继承 \_base.html Shell）

- `change_password.html` — 3 密码字段 + 显示/隐藏 toggle + 强度指示器（max-width 480px）
- `api_token.html` — Token 显示 + 复制 + curl 示例 + 重置（max-width 640px）
- `api_doc.html` — Endpoint cards + 方法 badge + Parameters/Response（可折叠）

### Phase 7 — 全局组件 JS 完善

Toast / Modal / Command Palette / Empty State / Skeleton

| 组件 | 文件 | API | 依赖 Phase |
| --- | --- | --- | --- |
| Toast | `redesign-toast.js` | `CpToast.success(msg)` / `.error(msg)` / `.warning(msg)` | Phase 3+（当前 dashboard 有 inline 实现，需提取） |
| Confirm Modal | `redesign-confirm.js` | `CpConfirm.show({title, body, onOk})` | 同上 |
| Command Palette | `redesign-cmd-palette.js` | ⌘K 打开 → 搜索 sidebar items + quick actions | 可独立 |
| Empty State | Jinja2 macro | `{% call empty_state(icon, title, desc) %} CTA {% endcall %}` | Phase 3+ |
| Skeleton | CSS only | `.cp-skeleton` + `.cp-skeleton-line` | 已在 redesign-components.css |

### Phase 8 — 全量验收 + Polish

深色模式全审计 / 响应式 / 文档同步 / v1 回归

- 深色模式：逐页截图，确认无白色闪块、对比度符合 WCAG AA
- 响应式：1024px（sidebar auto-collapse）、768px（sidebar hidden + hamburger）
- Command Palette 全面测试
- 全量 v1 回归：切回 v1 后所有经典页面正常
- 文档同步：RELEASE\_NOTES + doc/design/ + README

## 四、逐页 Design QA 验收规格（强制门禁）

**强制规则**：每个页面实现完成后，必须执行以下 4 步 Design QA。这是 Phase 2 偏离事故后的强制门禁。  
① `Read` Mockup 对应 `view-*` 区块完整 HTML  
② 列出结构清单（列数、列名、CSS class、组件层级、按钮类型）  
③ `curl + grep` 验证关键 class 存在  
④ 截图逐区域对照

| 页面 | Mockup view | 关键 grep 验证 | 列数 |
| --- | --- | --- | --- |
| Dashboard | `view-dashboard` | `hf-stats`, `exc-panel`, `row-acts` | 7 |
| Execution Logs | `view-logs` | `el-table`, `row-fail` | 7 |
| Task Detail | `view-detail` | `detail-grid`, `health-big`, `recent-runs` | N/A (cards) |
| Run Inspector | `view-run-inspector` | `run-header`, `run-badge`, `run-section` | N/A (sections) |
| Task Form | `view-form` | `form-section` ×3+, cron presets `chip` | N/A (form) |
| Users | `view-users` | 9 个 `<th>` | 9 |
| Groups | `view-groups` | card grid, `stat` badges | N/A (cards) |
| Reg Review | `view-reg-review` | 9 个 `<th>`, status chips | 9 |
| Audit Log | `view-audit` | 6 个 `<th>`, action badges | 6 |
| Operation Log | `view-optlog` | 7 个 `<th>`, filter selects | 7 |
| Tags | `view-tags` | namespace groups, `chip` with count | N/A (chips) |
| Change Password | `view-password` | `input-with-toggle`, `password-strength` | N/A (form) |
| API Token | `view-api-token` | mono code block, copy button | N/A |
| API Doc | `view-apidoc` | method badges (GET/POST) | N/A |
| Login | `#login-page` | login form, register link | N/A |
| Register | `#register-page` | group checkboxes, role select | N/A |

## 五、执行顺序与依赖关系

```
Phase 2 补完 ──→ Phase 3 (Detail/Inspector) ──→ Phase 4 (Forms)
                                                     │
                                              Phase 5a-5e (Admin)
                                                     │
                                              Phase 6 (Auth/Personal)
                                                     │
                                              Phase 7 (Global Components)
                                                     │
                                              Phase 8 (Polish/Audit)
```

**关键依赖**：

- Phase 3 依赖 Phase 2 完成（Dashboard "查看详情" 链接指向 task\_detail）
- Phase 4 可与 Phase 3 并行（表单独立于列表/详情）
- Phase 5 的每个子页面可独立交付（5a/5b/5c/5d/5e 之间无强依赖）
- Phase 7 建议在 Phase 5 之前提取（避免 Toast/Modal 代码重复），但不阻塞
- Phase 6 Auth 独立于 Shell（不继承 \_base），可在任何时候实现

### 推荐交付节奏（每批可独立验收）

| 批次 | 包含 | 预估工作量 | 可独立验收 |
| --- | --- | --- | --- |
| B1 | Phase 2 补完 | 0.5 天 | ✓ |
| B2 | Phase 7 提取（Toast/Modal/Empty） | 0.5 天 | ✓ |
| B3 | Phase 3 (Detail + Inspector) | 1 天 | ✓ |
| B4 | Phase 4 (Forms) | 1 天 | ✓ |
| B5 | Phase 5a (Users) | 0.5 天 | ✓ |
| B6 | Phase 5b (Groups) | 0.5 天 | ✓ |
| B7 | Phase 5c (Reg Review) | 0.5 天 | ✓ |
| B8 | Phase 5d (Audit + OptLog) | 0.5 天 | ✓ |
| B9 | Phase 5e (Tags) | 0.5 天 | ✓ |
| B10 | Phase 6 (Auth + Personal + API Doc) | 1 天 | ✓ |
| B11 | Phase 7 完善 (Command Palette) | 0.5 天 | ✓ |
| B12 | Phase 8 (全量 Polish + 验收) | 1 天 | ✓ |

**总计**：~8 天（单人串行）；可压缩至 5 天（并行 Phase 4/5）

## 六、质量门禁体系

### 6.1 每批次交付必须通过

| # | 门禁 | 工具/命令 | 失败处理 |
| --- | --- | --- | --- |
| 1 | 单元测试通过 | `bash scripts/cronpilot.sh test` | 修复后重跑 |
| 2 | 颜色审计 | `python scripts/audit_hardcoded_colors.py --check` | 替换为 var(--cp-\*) |
| 3 | Ajax Form 守卫 | `python -m unittest tests.test_ajax_form_guard -v` | 补充 js-ajax-submit |
| 4 | HTML↔MD 同步 | `python scripts/html_docs_to_markdown.py --check` | regenerate |
| 5 | Restart + 浏览器 | `cronpilot.sh restart → 登录 → 目标页面` | 修复渲染错误 |
| 6 | v1 无回归 | 切回 `cp_ui_version=v1` 验证经典页面 | 隔离 CSS/JS 泄漏 |
| 7 | 深色模式 | 切换 dark → 无白色闪块 | 补 dark mode override |
| **8** | **Mockup Design QA** | Read mockup → 列结构 → grep classes → 截图对照 | **不通过不得提交** |
| 9 | 复盘文档化完整性 | `python scripts/check_postmortem_completeness.py --check` | 补充复盘/RELEASE\_NOTES |
| 10 | 4 角色权限验证 | seed admin / biz admin / operator / viewer 各登录验证 | 修复权限逻辑 |

### 6.2 程序化强制（Hook 系统）

| Hook | 事件 | 效果 |
| --- | --- | --- |
| L1 postmortem-reminder | postToolUse (Write/StrReplace) | 每次编辑后注入分类+复盘+文档同步清单 |
| L2 pre-commit-gate | beforeShellExecution (git commit) | 阻止不含 RELEASE\_NOTES 的代码提交 |
| L2b stop hook | stop | 结束前评估复盘完整性（安全网） |

## 七、风险评估

| 风险 | 概率 | 影响 | 缓解 |
| --- | --- | --- | --- |
| 实现再次偏离 Mockup | 低（已有 Design QA 强制门禁） | 高 | 每页 Read mockup + grep + 截图；L1 Hook 提醒 |
| 新旧 CSS 冲突 | 中 | 中 | `.cp-*` 前缀命名空间；页面 CSS 在 `.cp-shell` 下作用域 |
| jQuery common.js 事件不匹配 | 中 | 中 | 保留 `.js-ajax-form`/`.js-ajax-submit` 约定 |
| CSRF 遗漏 | 低 | 高 | `_base.html` 统一注入 `csrf_param`；集成测试覆盖 POST |
| 深色模式残留白色 | 中 | 中 | Phase 8 全量审计 + CI 扫描 |
| 性能退化（过多 inline CSS） | 低 | 低 | Phase 7 提取共享 `redesign-pages.css` |

## 八、最终验收标准

当所有 Phase 完成后，最终验收需通过：

1. 设置 `cp_ui_version=v2`，从登录页开始，遍历所有 sidebar 链接，每个页面均为新设计（无经典 admin\_base 混入）
2. 4 种角色各登录一次，验证权限正确（导航可见性 + 数据 Scope + 操作拦截）
3. 深色/浅色模式各截图一套（~16 页 × 2 = 32 张）
4. 768px 宽度下验证响应式布局
5. 设置 `cp_ui_version=v1`，验证经典 UI 零回归
6. 全量测试套件通过（目标 450+ tests）
7. `check_postmortem_completeness.py --check` 通过
8. RELEASE\_NOTES 包含所有 Phase 的变更条目

---

*文档版本：v2 · 创建日期：2026-08-11 · 基于 Phase 2 偏离事故后重新设计*

[文档索引](../index.html) · [Markdown](UI重设计-详细实施与验收计划v2.md) · [索引](../index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
