# 复盘：Redesign 筛选交互降级

> HTML 版：[2026-08-Redesign筛选交互降级.html](2026-08-Redesign筛选交互降级.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 复盘：Redesign 筛选交互降级

日期：2026-08-26 · 关联设计：`doc/design/任务中心筛选AJAX化设计.html`

## 1. Bug 定位

`app/templates/redesign/dashboard.html` 第 68-111 行：所有筛选控件（异常/状态 `.f-btn`、组/标签 `.f-select`、任务名搜索 form、分页链接）均使用整页 GET 导航，导致每次筛选浏览器重载并滚动回顶部。

对比：`app/templates/cron_list.html`（v1）使用 Vue `CronFilterBar` + `partial=1` AJAX 实现无刷新筛选，滚动位置稳定。

## 2. 根因

1. **重构范围界定不清**：Redesign Mockup 只定义了视觉结构（HTML/CSS），未显式标注"筛选交互方式"这一非视觉需求。设计文档中没有"交互模式"维度的约束。
2. **去 Vue 依赖的副作用**：v2 明确目标之一是减少前端构建依赖（不再使用 Vue 组件），导致 v1 的 `CronFilterBar.vue` AJAX 逻辑被整体丢弃，而非将 AJAX 行为用原生 JS 重写。
3. **"先跑通再优化"的隐性假设**：开发时优先确保数据正确渲染（7 列表格、Stats Cards、Exception Panel），筛选用最简单的 `<a href>` 先跑通，但"优化"步骤未被显式 track。
4. **缺少交互回归清单**：Redesign 验收标准聚焦于"视觉对齐 Mockup"和"数据正确"，没有"交互体验不得低于 v1"这一回归约束。

## 3. 测试漏洞

- 现有测试覆盖 RBAC 权限、Scope 过滤正确性、数据渲染，但没有**交互体验**层面的验收项。
- Redesign 验收清单（Mockup 逐节对照）只检查 DOM 结构和视觉，不检查用户操作的响应方式（整页刷新 vs AJAX）。
- v1 的 `partial=1` 响应路径有隐式覆盖（Vue 组件测试），但 v2 无对应测试。

## 4. 修复

按设计文档 `doc/design/任务中心筛选AJAX化设计.html` 实施方案 A（AJAX 局部刷新）：

- 后端 v2 分支增加 `partial=1` JSON 响应（rows + pagination + stats）
- 模板抽取表格行和分页为独立 partial 模板
- 前端 JS 拦截筛选事件 → fetch → DOM 更新 + `history.replaceState`

## 5. 防护测试

- 单测新增：验证 v2 `partial=1` 请求返回合法 JSON 且包含 `rows`/`pagination`/`stats` 字段
- 浏览器验证：筛选后 `window.scrollY` 不变（或差值 < 50px）

## 6. 同类排查

| 页面 | 模板 | 是否同类问题 | 处置 |
| --- | --- | --- | --- |
| 执行记录 | `redesign/execution_logs.html` | 是 | 后续 OPT 跟踪 |
| 操作日志 | `redesign/operation_log.html` | 是 | 后续 OPT 跟踪 |
| 审计日志 | `redesign/audit_logs.html` | 是 | 后续 OPT 跟踪 |
| 用户管理 | `redesign/users.html` | 是（影响较小） | 后续 OPT 跟踪 |

## 7. 预防方案

### 措施 1：Redesign 交互回归约束（规范新增）

**落地位置**：`.cursor/rules/cronpilot-project.mdc`「Redesign Mockup 逐节对照」章节追加

**内容**：凡 v1 已有 AJAX 交互的功能（筛选、翻页、搜索），v2 Redesign 必须保持等效或优化交互方式，不得降级为整页刷新。Redesign 设计文档须包含"交互模式对比"维度（v1 行为 vs v2 行为）。

**验证命令**：`grep -n "onchange.*location.href\|<a.*href.*url_for.*cron_list" app/templates/redesign/dashboard.html | wc -l`（修复后应为 0）

### 措施 2：Redesign 设计文档必备要素追加"交互模式"

**落地位置**：`.cursor/rules/cronpilot-project.mdc`「设计必备要素」表

**内容**：新增"交互模式"行 — 须对比 v1 已有交互方式，显式声明 v2 的交互选择（AJAX/SPA/整页刷新）及理由。

### 措施 3：AJAX 筛选模式标准化

**落地位置**：本次实现完成后，将 AJAX 筛选 JS 逻辑抽为可复用函数（`common-redesign.js` 中的 `CpAjaxFilter`），后续页面可直接调用，避免重复实现。

[文档索引](index.html) · [Markdown](2026-08-Redesign筛选交互降级.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
