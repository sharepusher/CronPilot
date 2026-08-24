# CronPilot 2026 — UI 重设计 Mockup 审查结论与分批实施方案

> HTML 版：[UI重设计-Mockup审查与实施方案.html](UI重设计-Mockup审查与实施方案.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# CronPilot 2026 — UI 重设计 Mockup 审查结论与分批实施方案

文档编号：OPT-P1-16-IMPL · 创建：2026-08-11 · 最后更新：2026-08-11 · 状态：**审查通过（二轮），待实施**  
关联文档：`UI交互重设计综合方案.html` · `色系统一设计方案.html` · `CronPilot-2026-redesign-mockup.html`  
目标：将 Mockup 设计落地为工程可交付的分批实施方案

## 一、Mockup 审查结论

### 1.1 审查范围

| 审查项 | 状态 | 说明 |
| --- | --- | --- |
| 浅色模式（默认） | ✅ 通过 | 所有 22 个 View 验证完毕 |
| 深色模式 | ✅ 通过 | 8 个关键页面逐一截图验证一致性（二轮追加） |
| 功能覆盖完整性 | ✅ 通过 | 当前系统所有功能均有对应 Mockup |
| 交互细节 | ✅ 通过 | 密码 Toggle、强度条、表单验证、空状态、骨架屏、Toast、Modal、分页均已覆盖 |
| 新旧对比合理性 | ✅ 通过 | 任务中心/用户管理/登录三大核心对比确认 |
| 文案与真实系统对齐 | ✅ 通过 | 全量审计：表单标签、默认值、占位符、帮助文案均与 cron\_add.html 等模板对齐 |
| 中文本地化（i18n） | ✅ 通过 | 二轮审查消除全部非技术英文标签（详见 §1.4） |

### 1.2 Mockup 覆盖的完整页面清单

| 模块 | 页面 | View ID | 核心改进 |
| --- | --- | --- | --- |
| Operations | 任务中心（Dashboard） | view-dashboard | Health-First + 异常置顶 + Cron可视 + 分页 |
| 任务详情/下钻 | view-detail | 三层状态模型 + 配置/历史/操作分区 |
| Run Inspector | view-run-inspector | 全链路执行轨迹 + HTTP 响应展示 |
| 失败记录分析 | view-run-failed | 异常分组 + 根因摘要 |
| 执行记录 | view-logs | 时间线样式 + 状态过滤 |
| Configuration | 业务组 | view-groups | 组成员/任务统计 + 创建表单 |
| 标签管理 | view-tags | 命名空间分层 + 色彩标签 |
| 任务编辑 | view-form | 分区表单（基础/Endpoint/Schedule/Lifecycle） |
| 新建任务 | view-task-add | 同编辑结构，空状态起始 |
| 新建业务组 | view-group-add | 简洁创建表单 |
| Administration | 用户管理 | view-users | Avatar分层 + 状态圆点 + Tab筛选 |
| 添加用户 | view-user-add | 密码强度 + 角色/组选择 |
| 编辑用户 | view-user-edit | 危险区域隔离 |
| 注册审批 | view-reg-review | Tab切换（待审/已通过/已拒绝） |
| 审计日志 | view-audit | 时间线 + 操作者/动作/目标分列 |
| Personal | 修改密码 | view-password | 密码Toggle + 强度指示器 + 安全提示 |
| API Token | view-api-token | Token展示 + curl示例 + 重新生成 |
| Developer | API 文档 | view-apidoc | Swagger嵌入 + 端点列表 |
| 操作记录 | 操作历史 | view-optlog | 时间线样式 |
| Auth（独立页） | 登录 | login-page | 居中卡片 + 密码Toggle |
| 注册 | register-page | 角色/组选择 + 申请理由 |
| 忘记密码 | forgot-page | 邮箱重置流程 |
| 错误页(403) | view-error-demo | 友好提示 + 返回操作 |

### 1.3 设计原则确认

**核心设计决策（用户确认）**

- **默认主题**：浅色（Light）为默认
- **品牌色**：#3D6FE0（蓝色主色调），延续 CronPilot 品牌
- **信息架构**：Health-First — 异常和需关注任务优先展示
- **导航分组**：运维操作 → 系统配置 → 系统管理 → 个人设置 → 开发者
- **用户管理操作语义**：使用"添加用户"而非"邀请"（无邮件通知机制）
- **色系**：暂保留现有 Flat UI 色值，色系统一推迟到专项重设计
- **交互规范**：密码字段均需 Toggle；表单均需验证反馈；列表均需分页
- **本地化原则**：界面全部中文化，仅保留技术名词（HTTP/URL/Cron/API/Token/JSON 等）使用英文

### 1.4 本地化（i18n）审查结论（二轮追加）

二轮审查中发现 Mockup 中仍有约 40 处英文 UI 标签，已全部修正为中文。以下为修正清单：

| 区域 | 修正前（英文） | 修正后（中文） |
| --- | --- | --- |
| 侧栏导航分类 | Operations / Configuration / Administration / Personal / Developer / Demo | 运维操作 / 系统配置 / 系统管理 / 个人设置 / 开发者 / 演示 |
| 任务详情卡片标题 | Health / Schedule / Recent Runs / Configuration | 健康度 / 调度 / 最近执行 / 配置信息 |
| 任务详情配置标签 | Endpoint / Timeout / Group / Owner / Created / Last Edit | 请求地址 / 超时 / 业务组 / 创建人 / 创建时间 / 最后修改 |
| 调度卡片内文案 | Next Run: / Timezone: | 下次执行: / 时区: |
| 执行详情页头 | Run #xxx / SUCCESS / FAILED | 执行 #xxx / 成功 / 失败 |
| 执行元信息 | Duration / Started / Finished / Triggered by / Error | 耗时 / 开始 / 结束 / 触发方式 / 错误 |
| 执行详情 Section | Request / Response / Business Logs / Metadata / Failure Reason | 请求 / 响应 / 业务日志 / 元数据 / 失败原因 |
| 元数据标签 | Task / Group / Triggered By / Worker / Timezone | 任务 / 业务组 / 触发方式 / 执行节点 / 时区 |
| 生命周期状态 Badge | Active / Retired | 运行中 / 已下线 |
| 健康状态标签 | Healthy / ×5 Failing / ×3 Failing | 健康 / ×5 异常 / ×3 异常 |
| 表单 Section 标题 | Endpoint / Schedule | 请求配置 / 调度配置 |
| Dashboard 统计 | 今日失败 Run / 128 Tasks | 今日失败次数 / 128 个任务 |
| Command Palette | Create task / ● Healthy | 新建任务 / ● 健康 |
| 失败详情 | Consecutive Failures / Last Success | 连续失败 / 最后成功 |

**保留英文的技术名词**：HTTP、URL、POST/GET、Cron、API、Token、JSON、N/A、Connection refused、HTTP 502 等运行时错误信息。这些是行业通用技术术语或真实系统日志输出，不做翻译。

## 二、新旧版本核心差异对比

### 2.1 任务中心

| 维度 | 当前版本 (v3.0) | 新设计 (v4.0 Target) |
| --- | --- | --- |
| 首屏焦点 | 任务平铺列表 | Health 指标汇总（异常/失败/运行中/今日成功率） |
| 异常提醒 | 无 | 「需要关注的任务」Alert 卡片，连续失败/超时/P95 异常置顶 |
| 调度展示 | "每小时第30分钟" 纯文字 | Cron 5 段可视化 `*/5 * * * *` + 中文人读 |
| 表格设计 | 6列密集文字表格 | 分层卡片行 — 任务名+URL/标签/状态独立层级 |
| 操作入口 | "运行记录"文字链接 + "更多"按钮 | Icon Action Bar（执行/暂停/更多菜单） |
| 分页 | 首页/上一页/1/下一页/尾页（文字） | 数字分页 + 条目统计（"显示 1-5 / 共 128 个任务"） |

### 2.2 用户管理

| 维度 | 当前版本 | 新设计 |
| --- | --- | --- |
| 列表样式 | ID起始 + 紧凑表格 | Avatar + 姓名/邮箱分层卡片 |
| 状态展示 | 彩色底色块「启用/停用」 | 语义圆点 `●` + 文案 |
| 筛选 | 单行文本搜索框 | Tab 快筛（全部/启用/停用）+ 角色/组下拉 |
| 操作 | 红/蓝色文字链接并排 | 统一 icon 操作按钮（齿轮/设置） |
| 信息摘要 | 无 | "6 名成员 · 3 个业务组" 头部概览 |

### 2.3 登录页

| 维度 | 当前版本 | 新设计 |
| --- | --- | --- |
| 布局 | 超大 Jumbotron 标题 + 单行内联表单 | 页面居中卡片，视觉聚焦 |
| 品牌 | "CronPilot 定时调度平台" 大标题 | Logo + "欢迎回来" 简洁问候 |
| 安全 | 无密码可视性切换 | 👁 密码显示/隐藏 Toggle |
| 辅助导航 | 同行排列 | 分层（忘记密码右对齐 + 注册在卡片底部） |

## 三、分批实施方案

**实施原则**：每批独立可交付、独立可验收、可回滚。批次间无强依赖，可灵活调整顺序。每批完成后服务可正常运行。

### 3.1 实施阶段总览

Phase 1 基础设施 — Design Token + Layout Shell（2-3天）

建立新 Layout（Sidebar + Topbar + Content Area），注入 Design Token 系统，所有后续 Phase 基于此骨架。

Phase 2 核心 Operations — 任务中心重构（3-4天）

Health-First Dashboard、Cron 可视化、新任务列表卡片行、分页组件。

Phase 3 Task Detail + Execution（2-3天）

任务详情下钻、Run Inspector、执行记录时间线。

Phase 4 表单系统 — 任务编辑/新建（2天）

分区表单（基础/Endpoint/Schedule/Lifecycle），Cron 实时预览。

Phase 5 Administration — 用户/组/审批/审计（3天）

用户管理列表+CRUD、业务组管理、注册审批Tab、审计时间线。

Phase 6 Auth 独立页 + Personal（1-2天）

登录/注册/忘记密码重设计、修改密码（含强度条）、API Token。

Phase 7 全局交互 + 辅助页（1-2天）

Toast 通知系统、Modal 确认框、空状态、错误页、Loading骨架屏。

Phase 8 深色模式 + 响应式 + 收尾（1-2天）

深色模式完整适配、移动端适配、性能优化、文档同步。

### 3.2 Phase 1 — 基础设施（Design Token + Layout Shell）

#### 交付物

| 文件 | 变更内容 |
| --- | --- |
| `app/static/css/redesign-tokens.css` | 全新 Design Token 文件：颜色/字体/间距/圆角/阴影变量（Light + Dark） |
| `app/static/css/redesign-layout.css` | 新 Layout 骨架：Sidebar（固定宽度）+ Topbar + Content Area |
| `app/templates/redesign_base.html` | 新 base 模板（继承或替代 admin\_base.html） |
| `app/templates/components/sidebar.html` | 侧边栏导航组件 |
| `app/templates/components/topbar.html` | 顶栏（搜索+通知+用户头像） |

#### 关键设计决策

- **渐进式迁移**：新模板 `redesign_base.html` 与现有 `admin_base.html` 并存，通过配置开关或路由级别逐步迁移
- **Token 命名**：采用语义化命名 `--cp-surface-*`、`--cp-text-*`、`--cp-signal-*`（参考色系统一设计方案.html）
- **兼容策略**：新 Layout 中保留 Bootstrap 网格 class 兼容，逐步替换

#### 验收标准

1. 新 base 模板渲染出 Sidebar + Topbar + 空白 Content Area
2. 浅色/深色 Toggle 切换正常
3. ⌘K 搜索功能仍可用
4. 所有 Design Token 变量在 DevTools 中可查看
5. 现有页面（旧 base）不受影响

### 3.3 Phase 2 — 任务中心重构

#### 交付物

| 文件 | 变更内容 |
| --- | --- |
| `app/templates/redesign/cron_list.html` | 全新任务中心模板（Health Summary + Alert + Task Table + Pagination） |
| `app/static/css/redesign-dashboard.css` | 任务中心专用样式 |
| `app/static/js/cron-visual.js` | Cron 表达式 5 段可视化组件 |
| `app/main/views.py` | 新增 Health 指标聚合 API 数据 |

#### 子任务拆解

1. **2a**：Health Summary 卡片（异常/失败/运行中/成功率 4 指标）
2. **2b**：Alert 需关注面板（连续失败/P95超时任务列表）
3. **2c**：新任务列表表格（卡片行、Cron可视、标签chip、操作栏）
4. **2d**：分页组件（数字分页 + 条目统计 + 每页条数选择）

#### 验收标准

1. 任务中心默认展示 Health 指标和需关注任务
2. Cron 表达式以 5 段可视化 + 中文人读展示
3. 分页可切换、筛选可用（全部/异常/暂停/运行中/已下线）
4. 深色模式下排版/对比度一致

### 3.4 Phase 3 — Task Detail + Execution

#### 交付物

| 文件 | 变更内容 |
| --- | --- |
| `app/templates/redesign/cron_detail.html` | 任务详情页（状态三层模型 + 配置/历史/操作分区） |
| `app/templates/redesign/run_inspector.html` | Run Inspector 全链路执行轨迹 |
| `app/templates/redesign/cron_log.html` | 执行记录时间线 |
| `app/static/css/redesign-detail.css` | 详情页/执行记录专用样式 |

### 3.5 Phase 4 — 表单系统

#### 交付物

| 文件 | 变更内容 |
| --- | --- |
| `app/templates/redesign/cron_form.html` | 统一任务编辑/新建表单（分区：基础信息/Endpoint/Schedule/Lifecycle） |
| `app/static/js/cron-preview.js` | Cron 表达式实时预览（下 N 次执行时间） |
| `app/static/css/redesign-form.css` | 表单分区样式 |

### 3.6 Phase 5 — Administration

#### 交付物

| 文件 | 变更内容 |
| --- | --- |
| `app/templates/redesign/rbac/users.html` | 用户管理列表（Avatar + Tab筛选 + 概览摘要） |
| `app/templates/redesign/rbac/user_form.html` | 添加/编辑用户表单 |
| `app/templates/redesign/rbac/groups.html` | 业务组管理 |
| `app/templates/redesign/rbac/reg_review.html` | 注册审批（Tab：待审核/已通过/已拒绝） |
| `app/templates/redesign/rbac/audit.html` | 审计日志时间线 |

### 3.7 Phase 6 — Auth + Personal

#### 交付物

| 文件 | 变更内容 |
| --- | --- |
| `app/templates/redesign/login.html` | 居中卡片登录页 + 密码Toggle |
| `app/templates/redesign/register.html` | 注册申请表单 |
| `app/templates/redesign/forgot_password.html` | 忘记密码流程 |
| `app/templates/redesign/password.html` | 修改密码（强度条） |
| `app/templates/redesign/api_token.html` | API Token 管理 |

### 3.8 Phase 7 — 全局交互组件

#### 交付物

| 文件 | 变更内容 |
| --- | --- |
| `app/static/js/toast.js` | Toast 通知系统（success/error/warning，自动消失） |
| `app/static/js/modal.js` | 确认弹窗组件（替代 JS confirm） |
| `app/templates/components/empty_state.html` | 空状态组件（可复用 include） |
| `app/templates/components/skeleton.html` | 骨架屏 Loading 组件 |
| `app/templates/redesign/error_403.html` | 403 错误页 |

### 3.9 Phase 8 — 深色模式 + 收尾

#### 交付物

| 文件 | 变更内容 |
| --- | --- |
| `app/static/css/redesign-tokens.css` | Dark Mode 完整 Token 补全 |
| `app/static/css/redesign-responsive.css` | 移动端/平板 Media Query |
| 各模板 | 暗色场景下的边界用例修复 |
| 文档 | RELEASE\_NOTES + 部署指南 + 设计文档归档 |

## 四、工程约束与风险

### 4.1 技术约束

| 约束 | 应对策略 |
| --- | --- |
| Python 3.8-3.11 + Flask 2.3 + Jinja2 | 纯服务端渲染，不引入 SPA 框架；JS 增强仅用原生 + jQuery |
| Bootstrap 3.3.7 + Flat UI 历史依赖 | 新 Layout 独立 CSS 文件，不覆盖旧样式；渐进式迁移 |
| 颜色规范 `var(--cp-*)` | 新 Token 系统兼容现有 `console-theme.css`，逐步替换 |
| 现有测试 (ajax\_form\_guard 等) | 新模板需通过现有静态门禁；分批验证 |

### 4.2 迁移策略

**渐进式双轨方案**

1. 新增 `redesign_base.html`，与 `admin_base.html` 并存
2. 按模块将路由指向新模板（通过 Jinja2 extends 切换）
3. 添加配置开关 `CRONPILOT_NEW_UI=true/false`，允许一键回滚
4. 全部迁移完成后，删除旧模板和对应 CSS

### 4.3 风险清单

| 风险 | 概率 | 影响 | 缓解措施 |
| --- | --- | --- | --- |
| Bootstrap 3 class 被新 Layout 覆盖 | 中 | 高 | 新 CSS 使用独立命名空间 `.cp-redesign *` |
| js-ajax-form 守卫在新模板中失效 | 低 | 高 | 每批完成后跑 `test_ajax_form_guard` |
| 深色模式变量遗漏 | 中 | 中 | Phase 8 集中审查 + 自动化截图对比 |
| 移动端适配工作量超预期 | 低 | 低 | Phase 8 作为独立可选阶段 |

## 五、工时估算

| Phase | 估算工时 | 前置依赖 | 优先级 |
| --- | --- | --- | --- |
| Phase 1 · 基础设施 | 2-3 天 | 无 | 🔴 必须最先 |
| Phase 2 · 任务中心 | 3-4 天 | Phase 1 | 🔴 核心价值 |
| Phase 3 · Task Detail | 2-3 天 | Phase 1 | 🟡 高价值 |
| Phase 4 · 表单系统 | 2 天 | Phase 1 | 🟡 中等 |
| Phase 5 · Administration | 3 天 | Phase 1 | 🟡 中等 |
| Phase 6 · Auth + Personal | 1-2 天 | Phase 1 | 🟢 可独立 |
| Phase 7 · 交互组件 | 1-2 天 | Phase 1 | 🟢 增强 |
| Phase 8 · 深色 + 收尾 | 1-2 天 | Phase 2-7 | 🟢 收尾 |
| **合计：15-21 个工作日** | | | |

## 六、验收与文档同步

### 6.1 每 Phase 验收清单

1. `bash scripts/cronpilot.sh test` — 全测试通过
2. `python scripts/audit_hardcoded_colors.py --check` — 无硬编码颜色
3. `bash scripts/cronpilot.sh restart --daemon` → 浏览器验收对应页面
4. 深色模式切换后页面渲染正常
5. `python scripts/html_docs_to_markdown.py --check` — 文档同步

### 6.2 最终交付时文档更新

- `RELEASE_NOTES.md` — v4.0 UI 重设计条目
- `doc/交付状态与路线图.html` — 标记 OPT-P1-16 已交付
- `README.md` — 更新截图和功能描述
- `AGENTS.md` — 更新模板路径约定（若结构变化）

[文档索引](../index.html) · [Markdown](UI重设计-Mockup审查与实施方案.md) · [索引](../index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
