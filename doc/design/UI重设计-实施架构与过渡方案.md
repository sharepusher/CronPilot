# CronPilot UI 重设计 — 实施架构与平稳过渡方案

> HTML 版：[UI重设计-实施架构与过渡方案.html](UI重设计-实施架构与过渡方案.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# CronPilot UI 重设计 — 实施架构与平稳过渡方案

**⚠️ SUPERSEDED**：本文档已合入 [统一执行手册 (OPT-P1-16-MANUAL)](UI重设计-统一执行手册.html)。  
本文档保留供历史追溯，**不再维护**。执行以统一手册为准。

文档编号：**OPT-P1-16-ARCH** ·
创建：2026-08-11 ·
最后更新：2026-08-11 ·
状态：**设计评审** ·
关联：[Mockup](CronPilot-2026-redesign-mockup.html) |
[审查与实施方案](UI重设计-Mockup审查与实施方案.html) |
[色系统一 RFC](色系统一设计方案.html)

**目标**：将 CronPilot 管理端从 Bootstrap 3 + Simpleboot 横向 Tab 架构，平稳过渡到 Mockup 定义的 Health-First Sidebar + 语义 Token 新架构。  
**约束**：① Python 3.8–3.11 + Flask 2.3 SSR（非 SPA）；② 过渡期新旧共存、渐进切换；③ 每步可回滚、可独立验收；④ 对现有 API、定时调度零影响。

## 一、架构决策与技术路线

### 1.1 核心架构决策

| # | 决策点 | 选择 | 理由 | 备选（弃用） |
| --- | --- | --- | --- | --- |
| D1 | 前端框架 | **保持 Jinja2 SSR + jQuery + Vue Islands** | 改造量最小、与现有 RBAC/CSRF/session 无缝兼容、无需引入 SPA Router | 全量 Vue SPA（重写成本过高、SSR SEO 不需要） |
| D2 | 新旧共存方式 | **双 Base 模板 + Cookie 开关** | 用户可随时回退经典模式；渐进迁移不影响未改造页面 | Feature Flag 环境变量（不支持用户级切换） |
| D3 | CSS Token 体系 | **统一为 `--cp-*` 命名空间**，新增语义层 | 与现有 `console-theme.css` 兼容，无需全量重命名 | Mockup 的裸 `--canvas/--signal`（与生产 token 冲突） |
| D4 | 布局方案 | **CSS Grid Shell (`.cp-shell`)**，与 Bootstrap Grid 独立 | 新布局不污染旧页面；旧页面通过 `admin_base.html` 保持原貌 | 在 Bootstrap container 内嵌套（选择器冲突严重） |
| D5 | JavaScript 模块化 | **新功能用 ES Module IIFE；全局保留 jQuery** | 渐进式；新组件（Command Palette、Toast）独立封装不依赖全局 | 引入 Webpack/Vite 打包全局 JS（风险大） |
| D6 | 路由策略 | **保持服务端路由，每个 View 对应独立 URL** | SEO 无关，但利于书签/分享、浏览器后退、RBAC 装饰器直接鉴权 | 前端 Hash Router（破坏已有收藏链接） |
| D7 | 深色模式实现 | **`html[data-theme="dark"]` + CSS Token 覆盖** | 与当前 console-mode 一致；JS 切换 + Cookie 持久化 | CSS prefers-color-scheme（不支持手动切换） |

### 1.2 目标架构图

┌─────────────────────────────────────────────────────────────────────┐
│ Browser │
│ │
│ ┌── 新架构 ──────────────────────┐ ┌── 旧架构（共存） ──────────┐ │
│ │ redesign\_base.html │ │ admin\_base.html │ │
│ │ ├ \_shell.html (Grid Shell) │ │ ├ \_topbar.html │ │
│ │ ├ \_sidebar.html │ │ ├ \_nav.html (tabs) │ │
│ │ ├ \_topbar\_new.html │ │ ├ \_sidebar\_console.html │ │
│ │ └ {% block content %} │ │ └ {% block content %} │ │
│ └────────────────────────────────┘ └────────────────────────────┘ │
│ │
│ 共享层： │
│ ├ console-theme.css (Design Tokens: --cp-\*) │
│ ├ redesign-layout.css (新布局专用) │
│ ├ redesign-components.css (新组件库) │
│ ├ common.js (Ajax form / anti-double-submit / 搜索 / 签名) │
│ ├ redesign-shell.js (Sidebar、Command Palette、Toast、Theme) │
│ └ Vue 3 Islands (filter-bar, status-cell, form-validator) │
└─────────────────────────────────────────────────────────────────────┘
│ │
▼ ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Flask Server (SSR) │
│ ├ Blueprints: main / rbac / api / docs │
│ ├ Views: render\_template('redesign/xxx.html') or ('xxx.html') │
│ ├ UI Mode: Cookie → context\_processor → template选择 │
│ ├ Services → Repositories → Models (不变) │
│ └ APScheduler / gevent (不变) │
└─────────────────────────────────────────────────────────────────────┘

### 1.3 文件结构规划

app/
├── templates/
│ ├── admin\_base.html # 旧 Base（保留，不删）
│ ├── redesign/ # ★ 新架构目录
│ │ ├── \_base.html # 新 Base 模板
│ │ ├── \_shell.html # Grid Shell partial
│ │ ├── \_sidebar.html # 侧边栏 partial
│ │ ├── \_topbar.html # 新顶栏 partial
│ │ ├── \_breadcrumb.html # 面包屑 macro
│ │ ├── \_pagination.html # 分页 macro
│ │ ├── \_toast.html # Toast 容器
│ │ ├── \_modal.html # Modal 通用 macro
│ │ ├── \_empty\_state.html # 空状态 macro
│ │ ├── dashboard.html # 任务中心
│ │ ├── task\_detail.html # 任务详情
│ │ ├── task\_edit.html # 任务编辑
│ │ ├── task\_add.html # 新建任务
│ │ ├── run\_inspector.html # 执行详情
│ │ ├── execution\_logs.html # 执行记录
│ │ ├── users.html # 用户管理
│ │ ├── user\_add.html # 添加用户
│ │ ├── user\_edit.html # 编辑用户
│ │ ├── groups.html # 业务组
│ │ ├── group\_add.html # 新建业务组
│ │ ├── tags.html # 标签管理
│ │ ├── audit\_log.html # 审计日志
│ │ ├── operation\_log.html # 操作记录
│ │ ├── reg\_review.html # 注册审批
│ │ ├── change\_password.html # 修改密码
│ │ ├── api\_token.html # API Token
│ │ └── api\_doc.html # API 文档
│ ├── redesign\_auth/ # 独立 Auth 页（不继承 Shell）
│ │ ├── login.html
│ │ ├── register.html
│ │ └── forgot\_password.html
│ └── ... (旧模板保留)
├── static/
│ ├── css/
│ │ ├── console-theme.css # ★ 扩展 Token（新增语义变量）
│ │ ├── console-mode.css # 旧 Console 样式（保留）
│ │ ├── redesign-layout.css # ★ 新布局 CSS
│ │ ├── redesign-components.css # ★ 新组件库 CSS
│ │ └── redesign-auth.css # ★ Auth 页专用
│ └── js/
│ ├── common.js # 保留（共享 Ajax/guard）
│ ├── redesign-shell.js # ★ Shell 交互
│ ├── redesign-cmd-palette.js # ★ Command Palette
│ ├── redesign-toast.js # ★ Toast 系统
│ └── redesign-theme.js # ★ 主题切换

## 二、Design Token 映射 — Mockup → 生产

### 2.1 Token 命名对照

Mockup 使用简短的裸变量名（`--canvas`、`--signal`），生产环境统一映射为 `--cp-` 前缀以避免第三方库冲突：

| Mockup Token | 生产 Token | Light 值 | Dark 值 | 用途 |
| --- | --- | --- | --- | --- |
| `--canvas` | `--cp-canvas` | #F7F8F9 | #0D0F12 | 页面背景 |
| `--surface` | `--cp-surface` | #FFFFFF | #16191D | 卡片/面板 |
| `--surface-2` | `--cp-surface-2` | #F1F2F4 | #1C2025 | Hover/次级 |
| `--border` | `--cp-border` | #E4E6E9 | #262B31 | 默认边框 |
| `--border-strong` | `--cp-border-strong` | #D3D6DA | #34393F | 输入框边框 |
| `--ink` | `--cp-ink` | #14171A | #ECEEF0 | 主文字 |
| `--muted` | `--cp-text-muted` | #5B6169 | #8B9198 | 次级文字 |
| `--faint` | `--cp-text-faint` | #9CA3AF | #565C64 | 占位/辅助 |
| `--signal` | `--cp-signal` | #3D6FE0 | #4C8DFF | 主操作色 |
| `--signal-ink` | `--cp-signal-hover` | #2F5FCB | #7DAAFF | 主操作 Hover |
| `--signal-bg` | `--cp-signal-bg` | rgba(61,111,224,0.09) | rgba(76,141,255,0.12) | 主操作背景 |
| `--success` | `--cp-success` | #0F9D66 | #34D399 | 成功 |
| `--warning` | `--cp-warning` | #B7791F | #F5A623 | 警告 |
| `--danger` | `--cp-danger` | #D64545 | #F16565 | 危险 |
| `--mono` | `--cp-font-mono` | "JetBrains Mono","Fira Code",monospace | | 等宽字体 |
| `--sans` | `--cp-font-sans` | "Inter",-apple-system,sans-serif | | UI 字体 |
| `--shadow` | `--cp-shadow-sm` | 0 1px 2px rgba(20,23,26,0.04) | none | 微投影 |

### 2.2 与现有 Token 的兼容策略

**原则**：现有 `--cp-*` Token（如 `--cp-role-admin`、`--cp-topbar-bg`、`--cp-font-sm`）**保留不删**。新 Token 在 `console-theme.css` 的 `:root` 中追加。旧模板通过旧 Token 继续工作，新模板引用新 Token。

```
/* console-theme.css — Phase 1 追加 */
:root {
  /* === 新语义 Token（2026 Redesign） === */
  --cp-canvas: #F7F8F9;
  --cp-surface: #FFFFFF;
  --cp-surface-2: #F1F2F4;
  --cp-border: #E4E6E9;
  --cp-border-strong: #D3D6DA;
  --cp-ink: #14171A;
  --cp-text-muted: #5B6169;
  --cp-text-faint: #9CA3AF;
  --cp-signal: #3D6FE0;
  --cp-signal-hover: #2F5FCB;
  --cp-signal-bg: rgba(61,111,224,0.09);
  --cp-shadow-sm: 0 1px 2px rgba(20,23,26,0.04);
  /* success/warning/danger 沿用现有 --cp-success 等 */
}

html[data-theme="dark"] {
  --cp-canvas: #0D0F12;
  --cp-surface: #16191D;
  --cp-surface-2: #1C2025;
  --cp-border: #262B31;
  --cp-border-strong: #34393F;
  --cp-ink: #ECEEF0;
  --cp-text-muted: #8B9198;
  --cp-text-faint: #565C64;
  --cp-signal: #4C8DFF;
  --cp-signal-hover: #7DAAFF;
  --cp-signal-bg: rgba(76,141,255,0.12);
  --cp-shadow-sm: none;
}
```

## 三、平稳过渡机制

### 3.1 双轨切换架构

**核心思路**：用户通过 Cookie（`cp_ui_version=v2`）选择新架构；未切换的用户继续使用旧界面零影响。管理员可通过配置强制全局启用。

#### 3.1.1 Context Processor 扩展

```
# app/ui_mode.py — 扩展现有 inject_ui_mode
def inject_ui_mode():
    # 现有逻辑：ui_mode, theme, sidebar_collapsed
    ...
    # 新增：UI 版本
    ui_version = request.cookies.get('cp_ui_version', 'v1')
    if current_app.config.get('CRONPILOT_FORCE_NEW_UI'):
        ui_version = 'v2'
    return dict(
        ui_mode=ui_mode,
        theme=theme,
        sidebar_collapsed=sidebar_collapsed,
        ui_version=ui_version,  # 'v1' or 'v2'
    )
```

#### 3.1.2 Views 中的模板选择

```
# app/main/views.py — 示例：任务列表
@main.route('/cron_list')
@require_login
def cron_list():
    # ... 业务逻辑不变 ...
    if g.ui_version == 'v2':
        return render_template('redesign/dashboard.html', **ctx)
    return render_template('cron_list.html', **ctx)
```

**决策 D2 实施细节**：不修改 URL 路由，只在 view 函数末尾分支模板。这保证：

- 收藏的链接 `/cron_list` 对新旧用户均有效
- RBAC 装饰器（`@require_permission`）无需改动
- API Blueprint 完全不受影响

#### 3.1.3 切换入口

在旧界面顶栏和新界面设置中放置「切换 UI 版本」入口：

```
# app/rbac/views.py
@rbac.route('/switch_ui_version', methods=['POST'])
@require_login
def switch_ui_version():
    version = request.form.get('version', 'v1')
    resp = redirect(request.referrer or url_for('main.cron_list'))
    resp.set_cookie('cp_ui_version', version, max_age=365*86400, httponly=True)
    return resp
```

### 3.2 迁移进度矩阵

每个路由页面独立迁移，标记状态：

| 路由 | 旧模板 | 新模板 | Phase | 状态 |
| --- | --- | --- | --- | --- |
| `/cron_list` (Dashboard) | cron\_list.html | redesign/dashboard.html | Phase 2 | 待开发 |
| `/cron_detail/<id>` | cron\_detail.html | redesign/task\_detail.html | Phase 3 | 待开发 |
| `/cron_edit/<id>` | cron\_edit.html | redesign/task\_edit.html | Phase 4 | 待开发 |
| `/cron_add` | cron\_add.html | redesign/task\_add.html | Phase 4 | 待开发 |
| `/job_log_list` | job\_log\_list.html | redesign/execution\_logs.html | Phase 2 | 待开发 |
| `/job_log_detail/<id>` | job\_log\_detail.html | redesign/run\_inspector.html | Phase 3 | 待开发 |
| `/rbac/users` | rbac/users.html | redesign/users.html | Phase 5 | 待开发 |
| `/rbac/groups` | rbac/groups.html | redesign/groups.html | Phase 5 | 待开发 |
| `/rbac/tags` | rbac/tags.html | redesign/tags.html | Phase 5 | 待开发 |
| `/rbac/audit-logs` | rbac/audit\_logs.html | redesign/audit\_log.html | Phase 5 | 待开发 |
| `/operation_log_list` | operation\_log\_list.html | redesign/operation\_log.html | Phase 5 | 待开发 |
| `/rbac/registration_review` | rbac/registration\_review.html | redesign/reg\_review.html | Phase 5 | 待开发 |
| `/rbac/login` | rbac/login.html | redesign\_auth/login.html | Phase 6 | 待开发 |
| `/rbac/register` | rbac/register.html | redesign\_auth/register.html | Phase 6 | 待开发 |
| `/rbac/change_password` | rbac/change\_password.html | redesign/change\_password.html | Phase 6 | 待开发 |

### 3.3 回滚机制

| 场景 | 操作 | 影响范围 |
| --- | --- | --- |
| 单用户回退 | 设置 Cookie `cp_ui_version=v1` | 仅该用户 |
| 全局回退 | 删除 `CRONPILOT_FORCE_NEW_UI` 配置 | 所有用户回退到 v1 |
| 代码回退 | `git revert` 特定 Phase 的 commits | 旧模板完整保留，不受影响 |

## 四、分批实施详案（深度技术方案）

### 4.1 Phase 1 — 基础设施（Design Token + Layout Shell）

**目标**：建立新架构的「地基」——Token 系统 + Shell 骨架 + 切换机制。完成后新旧模板可并行存在，后续 Phase 只需「填内容」。

#### 4.1.1 交付物清单

| 文件 | 动作 | 说明 |
| --- | --- | --- |
| `app/static/css/console-theme.css` | 扩展 | 追加 §2 Token；不删不改现有变量 |
| `app/static/css/redesign-layout.css` | 新建 | Grid Shell (.cp-shell) + Sidebar + Topbar 布局 |
| `app/static/css/redesign-components.css` | 新建 | 基础组件：btn、table、card、badge、form primitives |
| `app/templates/redesign/_base.html` | 新建 | 新 Base 模板（引入新 CSS/JS + Shell） |
| `app/templates/redesign/_shell.html` | 新建 | Sidebar + Topbar + Content slot |
| `app/templates/redesign/_sidebar.html` | 新建 | 权限感知的导航菜单 |
| `app/templates/redesign/_topbar.html` | 新建 | 搜索 + 主题 + 用户菜单 |
| `app/templates/redesign/_pagination.html` | 新建 | 分页 Macro（支持 url\_for） |
| `app/static/js/redesign-shell.js` | 新建 | Sidebar collapse、User dropdown、Mobile menu |
| `app/static/js/redesign-theme.js` | 新建 | Light/Dark 切换 + Cookie 持久化 |
| `app/ui_mode.py` | 修改 | 追加 `ui_version` 注入 |
| `config.py` | 修改 | 追加 `CRONPILOT_FORCE_NEW_UI` |

#### 4.1.2 新 Base 模板骨架

```
<!-- app/templates/redesign/_base.html -->
<!DOCTYPE html>
<html lang="zh-CN" data-theme="{{ theme }}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{% block title %}CronPilot{% endblock %}</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='css/console-theme.css') }}">
  <link rel="stylesheet" href="{{ url_for('static', filename='css/redesign-layout.css') }}">
  <link rel="stylesheet" href="{{ url_for('static', filename='css/redesign-components.css') }}">
  {% block css %}{% endblock %}
</head>
<body>
  <div class="cp-shell">
    {% include "redesign/_sidebar.html" %}
    <div class="cp-col-main">
      {% include "redesign/_topbar.html" %}
      <main class="cp-main">
        {% block breadcrumb %}{% endblock %}
        {% block content %}{% endblock %}
      </main>
    </div>
  </div>
  {% include "redesign/_toast.html" %}

  <!-- 共享 JS（保留 jQuery 生态 + 新模块） -->
  <script src="{{ url_for('static', filename='js/jquery.js') }}"></script>
  <script src="{{ url_for('static', filename='js/common.js') }}"></script>
  <script src="{{ url_for('static', filename='js/redesign-shell.js') }}"></script>
  <script src="{{ url_for('static', filename='js/redesign-theme.js') }}"></script>
  {% block js %}{% endblock %}
</body>
</html>
```

#### 4.1.3 Layout CSS 核心

```
/* redesign-layout.css */
.cp-shell {
  display: grid;
  grid-template-columns: 220px 1fr;
  min-height: 100vh;
  background: var(--cp-canvas);
  color: var(--cp-ink);
  font-family: var(--cp-font-sans);
}

.cp-sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
  background: var(--cp-surface);
  border-right: 1px solid var(--cp-border);
  padding: 16px 0;
}

.cp-col-main {
  display: flex;
  flex-direction: column;
  min-width: 0; /* prevent grid blowout */
}

.cp-topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  height: 52px;
  display: flex;
  align-items: center;
  padding: 0 24px;
  background: var(--cp-surface);
  border-bottom: 1px solid var(--cp-border);
}

.cp-main {
  flex: 1;
  padding: 24px;
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
}

/* Sidebar collapsed state */
.cp-shell.collapsed {
  grid-template-columns: 56px 1fr;
}
.cp-shell.collapsed .cp-sidebar .nav-label,
.cp-shell.collapsed .cp-sidebar .section-label { display: none; }

/* Mobile */
@media (max-width: 768px) {
  .cp-shell { grid-template-columns: 1fr; }
  .cp-sidebar { display: none; }
  .cp-sidebar.mobile-open { display: block; position: fixed; z-index: 100; width: 260px; }
}
```

#### 4.1.4 验收标准

1. `bash scripts/cronpilot.sh restart` → 访问 `/cron_list` 旧界面正常
2. 设置 Cookie `cp_ui_version=v2` → 看到新 Shell 骨架（空 content + sidebar + topbar）
3. `python scripts/audit_hardcoded_colors.py --check` 通过
4. Light/Dark 切换生效，Cookie 持久化
5. Sidebar 导航链接跳转到对应旧页面（降级正常）

### 4.2 Phase 2 — 任务中心（Health-First Dashboard）

**目标**：将 `/cron_list` 重构为 Health-First Dashboard，这是用户 80%+ 时间停留的首页。

#### 4.2.1 数据层准备

```
# app/services/dashboard_service.py — 新建
class DashboardService:
    """聚合任务健康数据，供 Dashboard 使用"""

    def get_health_summary(self, scope_group_ids=None):
        """返回 Health-First 统计面板数据"""
        return {
            'abnormal_count': ...,       # 异常任务数
            'consecutive_fail': ...,     # 连续失败任务数
            'running_count': ...,        # 运行中任务数
            'today_fail_count': ...,     # 今日失败次数
            'total_tasks': ...,
            'success_rate_24h': ...,
        }

    def get_exception_tasks(self, scope_group_ids=None, limit=5):
        """返回需要关注的异常任务列表"""
        return [
            {'task_name': ..., 'failure_count': ..., 'last_error': ...},
            ...
        ]
```

#### 4.2.2 后端变更（Views）

```
# app/main/views.py — cron_list 增强
@main.route('/cron_list')
@require_login
def cron_list():
    # ... 现有分页 + 筛选逻辑保持 ...
    ctx = {
        'tasks': paginated_tasks,
        'pagination': pagination,
        'groups': user_groups,
        'filters': current_filters,
    }

    if g.ui_version == 'v2':
        # 新 Dashboard 需要额外数据
        dashboard_svc = DashboardService()
        scope_ids = get_user_scope_group_ids()
        ctx['health_summary'] = dashboard_svc.get_health_summary(scope_ids)
        ctx['exceptions'] = dashboard_svc.get_exception_tasks(scope_ids)
        return render_template('redesign/dashboard.html', **ctx)

    return render_template('cron_list.html', **ctx)
```

#### 4.2.3 前端组件拆解

| 组件 | 实现方式 | 说明 |
| --- | --- | --- |
| Health Stats 面板 | Jinja2 模板 | 4 个统计卡片，纯服务端渲染 |
| Exception Panel | Jinja2 模板 | 异常任务列表，带链接跳转详情 |
| Filter Bar | Vue 3 Island 复用 | 复用现有 `cron-filter-bar.js` |
| Task Table | Jinja2 + Vue Cell | 表格 SSR，状态单元格用 Vue 组件 |
| Pagination | Jinja2 Macro | 新建 `_pagination.html` macro |

#### 4.2.4 验收标准

1. Health Summary 4 项指标与数据库实际一致
2. Exception Panel 展示连续失败 ≥ threshold 的任务
3. Filter/搜索/分页功能与旧版等效
4. Scope 隔离：非 admin 用户只看到自己组的数据
5. 切回 v1 旧界面完全正常

### 4.3 Phase 3 — 任务详情 + 执行详情

#### 4.3.1 关键技术点

| 特性 | 实现方案 |
| --- | --- |
| Detail 多 Card 布局 | CSS Grid 2-column（`grid-template-columns: 1fr 1fr`） |
| Recent Runs 列表 | Jinja2 渲染最近 10 条，链接到 Run Inspector |
| Run Inspector 代码块 | `<pre>` + `--cp-font-mono`；JSON 格式化用 Python `json.dumps(indent=2)` |
| 失败原因高亮 | `.run-badge.failed` + Danger Token 着色 |
| 业务日志时间线 | Jinja2 loop `job_log_items`，按时间排序 |

#### 4.3.2 新增路由

```
# 执行详情页目前是 /job_log_detail/
# v2 保持相同 URL，切换模板
@main.route('/job_log_detail/<int:log_id>')
@require_login
def job_log_detail(log_id):
    log = JobLogRepository.get_with_items(log_id)
    # ... 权限检查 ...
    ctx = {'log': log, 'task': log.cron_info, 'items': log.items}
    if g.ui_version == 'v2':
        return render_template('redesign/run_inspector.html', **ctx)
    return render_template('job_log_detail.html', **ctx)
```

### 4.4 Phase 4 — 表单系统（编辑/新建任务）

#### 4.4.1 设计原则

- **分段式表单**：基础信息 / 请求配置 / 调度配置 / 生命周期 — 每段独立 `.form-section`
- **Cron 预设**：Quick chips + 自定义输入 — 复用现有 `cron-form-validator.js` Vue 组件
- **业务组限选**：只显示用户所属组（已有 Scope 过滤逻辑）
- **保持 Ajax 提交**：使用 `js-ajax-form` + `js-ajax-submit` 模式

#### 4.4.2 关键变更

```
<!-- redesign/task_edit.html — 表单结构 -->
{% extends "redesign/_base.html" %}
{% block content %}
<form class="js-ajax-form" action="{{ url_for('main.cron_save') }}" method="post">
  {{ csrf_param | safe }}

  <div class="form-section">
    <div class="form-section-title">基础信息</div>
    <!-- 任务名称、说明、业务组、标签 -->
  </div>

  <div class="form-section">
    <div class="form-section-title">请求配置</div>
    <!-- 触发 URL、请求方式、超时、JSON Body -->
  </div>

  <div class="form-section">
    <div class="form-section-title">调度配置</div>
    <!-- 定时方式、Cron 表达式 + 预设 chips -->
    <div id="cron-form-validator-mount"></div>
  </div>

  <div class="form-actions">
    <button type="submit" class="btn btn-primary js-ajax-submit">保存</button>
    <a href="{{ url_for('main.cron_list') }}" class="btn">取消</a>
  </div>
</form>
{% endblock %}

{% block js %}
<script src="{{ url_for('static', filename='dist/cron-form-validator.js') }}"></script>
{% endblock %}
```

### 4.5 Phase 5 — 用户/组/审批/审计

#### 4.5.1 实施子步

| 子步 | 页面 | 复杂度 | 新增后端逻辑 |
| --- | --- | --- | --- |
| 5a | 用户管理 + 添加/编辑 | 中 | 无（现有 API 充分） |
| 5b | 业务组 | 中 | 追加 group detail 聚合查询 |
| 5c | 注册审批 | 低 | 无 |
| 5d | 审计日志 + 操作记录 | 低 | 无 |
| 5e | 标签管理 | 低 | 无 |

### 4.6 Phase 6 — Auth 独立页 + 个人设置

#### 4.6.1 Auth 页面特殊处理

Auth 页面不继承 Shell（无侧边栏），使用独立的 `redesign_auth/` base：

```
<!-- redesign_auth/_auth_base.html -->
<!DOCTYPE html>
<html lang="zh-CN" data-theme="{{ theme }}">
<head>
  <link rel="stylesheet" href="{{ url_for('static', filename='css/console-theme.css') }}">
  <link rel="stylesheet" href="{{ url_for('static', filename='css/redesign-components.css') }}">
  <link rel="stylesheet" href="{{ url_for('static', filename='css/redesign-auth.css') }}">
</head>
<body class="cp-auth-page">
  <div class="cp-auth-container">
    {% block auth_content %}{% endblock %}
  </div>
  <script src="{{ url_for('static', filename='js/common.js') }}"></script>
  {% block js %}{% endblock %}
</body>
</html>
```

#### 4.6.2 密码强度组件

```
// redesign-password-strength.js — IIFE
(function() {
  'use strict';
  document.querySelectorAll('.password-strength-wrap').forEach(function(wrap) {
    var input = wrap.querySelector('input[type="password"], input[type="text"]');
    var bars = wrap.querySelectorAll('.strength-bar');
    var label = wrap.querySelector('.strength-label');

    input.addEventListener('input', function() {
      var score = calcStrength(input.value);
      updateBars(bars, label, score);
    });
  });

  function calcStrength(pw) {
    if (!pw || pw.length < 6) return 0;
    var score = 1; // weak
    if (pw.length >= 8 && /[a-z]/.test(pw) && /\d/.test(pw)) score = 2; // medium
    if (pw.length >= 10 && /[A-Z]/.test(pw) && /[^a-zA-Z0-9]/.test(pw)) score = 3; // strong
    return score;
  }
})();
```

### 4.7 Phase 7 — 全局交互组件

| 组件 | 文件 | 触发方式 |
| --- | --- | --- |
| Toast 通知 | `redesign-toast.js` | `window.CpToast.success(msg)` / `.error(msg)` |
| 确认 Modal | `redesign-modal.js` | `window.CpModal.confirm({title, message, onOk})` |
| Command Palette | `redesign-cmd-palette.js` | ⌘K / Ctrl+K / 点击搜索框 |
| 空状态 | `_empty_state.html` Macro | Jinja2 条件渲染 |
| 骨架屏 | CSS `.skeleton` | 页面加载时显示，JS 填充后移除 |

#### 4.7.1 Toast 与现有 noty 的关系

**决策**：新界面使用自研 `CpToast`（轻量、Token 着色、无依赖）；旧界面继续用 noty。`common.js` 中的 Ajax 成功回调在 v2 下调用 `CpToast`。

```
// common.js — Ajax form success hook 增强
function showFeedback(msg, type) {
  if (window.CpToast) {
    window.CpToast[type === 'error' ? 'error' : 'success'](msg);
  } else {
    // 旧 noty fallback
    noty({text: msg, type: type === 'error' ? 'error' : 'success'});
  }
}
```

#### 4.7.2 Command Palette 数据源

```
// redesign-cmd-palette.js
// 数据源：服务端注入 + 前端静态
var PALETTE_DATA = {
  tasks: {{ tasks_for_palette | tojson }},  // 服务端注入（前 50 个活跃任务）
  actions: [
    { label: '新建任务', icon: '+', href: '{{ url_for("main.cron_add") }}' },
    { label: '执行记录', icon: '📋', href: '{{ url_for("main.job_log_list") }}' },
    { label: '用户管理', icon: '👥', href: '{{ url_for("rbac.users") }}' },
  ],
};
```

### 4.8 Phase 8 — 深色模式完善 + 响应式 + 收尾

#### 4.8.1 深色模式检查清单

- 所有 `redesign-*.css` 中不允许硬编码颜色，必须通过 Token
- 图片/Logo 需提供深色版本或使用 `filter: brightness()`
- 代码块/JSON 显示使用独立的深色方案（`--cp-code-bg`）
- 表单 `:focus` ring 在深色背景上可见度充分（4.5:1 对比度）

#### 4.8.2 响应式断点

| 断点 | 布局调整 |
| --- | --- |
| ≥ 1024px | 完整 Sidebar + 全部列可见 |
| 768–1023px | Sidebar 折叠为 icon-only；表格隐藏次要列 |
| < 768px | Sidebar 隐藏（汉堡菜单触发）；表格可横向滚动 |

## 五、实施时间线

W1**Phase 1** — Token + Shell + 切换机制 + 验收  
→ 里程碑：新旧 UI 可切换，Shell 骨架可见
W2**Phase 2** — Dashboard + Execution Logs  
→ 里程碑：核心首页可用（Health Stats + Task Table + Pagination）
W3**Phase 3 + 4** — 详情 + 表单系统  
→ 里程碑：核心 CRUD 闭环（列表→详情→编辑→新建）
W4**Phase 5** — Admin 全套（用户/组/审批/审计/标签）  
→ 里程碑：管理功能完整
W5**Phase 6 + 7** — Auth + 全局组件  
→ 里程碑：登录流程端到端新界面；Toast/Modal/Palette 完整
W5-6**Phase 8** — 深色模式、响应式、文档同步、全面验收  
→ 里程碑：全部页面深色/浅色一致，移动端可用

**总工期**：5–6 周（单人全职）或 3–4 周（前后端各一人）。  
**可并行**：Phase 3 & 4 可同时进行（分属不同模板文件）；Phase 5 的子步可并行。

## 六、质量保障与验收体系

### 6.1 每 Phase 必须通过的门禁

| # | 门禁 | 命令/工具 |
| --- | --- | --- |
| 1 | 单元测试通过 | `bash scripts/cronpilot.sh test` |
| 2 | 颜色审计通过 | `python scripts/audit_hardcoded_colors.py --check` |
| 3 | Ajax Form 守卫 | `python -m unittest tests.test_ajax_form_guard -v` |
| 4 | HTML↔MD 同步 | `python scripts/html_docs_to_markdown.py --check` |
| 5 | 重启后浏览器验证 | `cronpilot.sh restart → curl + browser` |
| 6 | 旧界面无回归 | 切回 v1 关键路径正常 |
| 7 | 深色模式无残留 | 切换 dark → 无白色闪块/对比度问题 |
| **8** | **Mockup 设计还原对照（Design QA）** | 逐节对照 Mockup 源码中对应 `view-*` 区块：  ① `Read` Mockup 对应区块完整 HTML（不可凭记忆）  ② 逐一核对：Stats 指标名与顺序、表格列数与列名、按钮类型(icon/text)、特殊面板、行样式  ③ `curl + grep` 验证关键 CSS class 存在于渲染 HTML  ④ 截图逐区域对照（Stats → Panel → Filters → Table → Pagination） |

### 6.2 新增测试

| 测试文件 | 覆盖内容 | Phase |
| --- | --- | --- |
| `tests/test_redesign_templates.py` | 新模板渲染不报错 + 关键元素存在 | Phase 1 |
| `tests/test_ui_version_switch.py` | Cookie 切换逻辑正确 | Phase 1 |
| `tests/test_dashboard_service.py` | Health 聚合数据正确性 | Phase 2 |
| `tests/test_redesign_auth.py` | 新 Auth 页 CSRF + 登录流程 | Phase 6 |

### 6.3 设计还原度验收（Design QA）— 强制

**强制**（2026-08 追加，Phase 2 偏离事故后升级为强制门禁）：  
每个 Phase 交付前，必须执行 **Mockup 逐节对照**，步骤：  
① `Read` Mockup 中对应 `view-*` 区块的完整 HTML 源码（禁止凭记忆）  
② 列出结构清单：Stats 指标名和顺序、表格列数和列名、按钮类型、面板组件、行样式  
③ `curl + grep` 验证关键 CSS class 存在于渲染输出  
④ 截图逐区域对照（Stats → Exception Panel → Filters → Table → Pagination → Actions）  
  
**失败教训**：Phase 2 首次实现因跳过此步骤，导致 Exception Panel 完全缺失、7 列降为 5 列、icon 按钮变文字按钮，触发全量重写。

### 6.4 视觉回归（Playwright）

**建议**（非强制，资源允许时引入）：使用 Playwright screenshot comparison 对关键页面做视觉快照对比。CI 中新增 `visual-regression.yml` workflow，在 PR 中展示 diff 图。

## 七、风险评估与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
| --- | --- | --- | --- |
| 新旧 CSS 选择器冲突（如 `.btn` 被覆盖） | 中 | 高 | 新组件使用 `.cp-btn` 前缀命名空间；`redesign-*.css` 全部在 `.cp-shell` 作用域下 |
| jQuery `common.js` 事件与新模板 DOM 结构不匹配 | 中 | 中 | 新模板保留 `.js-ajax-form`/`.js-ajax-submit` class 约定；全局守卫依赖 `[type="submit"]` 保持兼容 |
| CSRF Token 在新模板中遗漏 | 低 | 高 | 新 Base 模板统一引入 `{{ csrf_param|safe }}`；集成测试覆盖 POST |
| 深色模式遗漏变量导致白色闪块 | 中 | 中 | CI 脚本扫描 `redesign-*.css` 中是否有未使用 Token 的颜色 |
| Vue Islands 在新 Shell 中挂载时机错误 | 低 | 中 | 保持 `DOMContentLoaded` 后 mount；新模板确保 mount 点 ID 一致 |
| 迁移周期过长导致新旧不一致时间窗过大 | 低 | 低 | 每完成一个 Phase 即上线（Cookie 切换）；用户反馈驱动优先级调整 |

## 八、旧架构弃用路线

| 阶段 | 条件 | 操作 |
| --- | --- | --- |
| Phase 8 完成后 | 所有路由已支持 v2 | 将 `CRONPILOT_FORCE_NEW_UI` 默认值改为 `True` |
| v2 上线 4 周无投诉 | 运行稳定 | 移除 `ui_version` 分支逻辑；旧模板标记 deprecated |
| 下一大版本（v4.0） | 确认无用户使用 v1 | 删除旧模板 + Simpleboot 依赖 + noty/artDialog |

**绝对不做**：在过渡期删除旧模板或旧 CSS。旧文件保留为「安全网」，直到弃用条件全部满足。

## 九、附录

### A. 关键决策日志

| 日期 | 决策 | 理由 |
| --- | --- | --- |
| 2026-08-11 | 不引入 SPA Router | 22 个页面级 View 通过服务端路由管理更简单，RBAC 装饰器直接鉴权 |
| 2026-08-11 | 新 Token 使用 `--cp-` 前缀 | 与现有 Token 同命名空间，避免两套变量名共存增加认知负担 |
| 2026-08-11 | 分 8 Phase 渐进交付 | 单 Phase 不超过 1 周，降低合并冲突和回归风险 |
| 2026-08-11 | 保留 jQuery + common.js | Anti-double-submit、Ajax form、CSRF 等基础设施成熟稳定，无需重写 |

### B. 参考资源

- [完整交互 Mockup](CronPilot-2026-redesign-mockup.html)
- [色系统一设计方案 RFC](色系统一设计方案.html)
- [UI 交互重设计综合方案](UI交互重设计综合方案.html)
- [Mockup 审查与实施方案](UI重设计-Mockup审查与实施方案.html)

[文档索引](../index.html) · [Markdown](UI重设计-实施架构与过渡方案.md) · [索引](../index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
