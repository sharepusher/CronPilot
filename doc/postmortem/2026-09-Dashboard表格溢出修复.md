# 复盘：Dashboard 表格操作列溢出与下拉菜单裁剪

> HTML 版：[2026-09-Dashboard表格溢出修复.html](2026-09-Dashboard表格溢出修复.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 复盘：Dashboard 表格操作列溢出与下拉菜单裁剪

日期：2026-09-03

## 1. Bug 定位

两个 CSS 文件共同导致下拉菜单被后续行覆盖：

1. `app/static/css/redesign-mockup-shared.css:58-61`：`.c-table-wrap { overflow: hidden }` — 裁剪溢出
2. `app/static/css/redesign-pages.css:1326`：`.cp-page-dashboard .c-table tbody tr { opacity: 0; animation: rowSlideIn 0.25s ease-out forwards; }` — 每行创建独立层叠上下文

表现：点击"更多"按钮的下拉菜单被后续任务行覆盖（即使 `overflow` 修复后仍然存在）。同时缺少 `table-layout: fixed` 导致操作列可被挤压。

## 2. 根因（双层问题）

### 第一层：overflow: hidden 裁剪

- `.c-table-wrap { overflow: hidden }` 配合 `border-radius: 8px` 实现圆角，但会创建 BFC 裁剪所有溢出的后代元素
- 修复：改为 `overflow: visible`，圆角迁移到 `tr:last-child td`

### 第二层：animation: forwards 创建层叠上下文（真正根因）

- CSS 规范规定：`animation: ... forwards` 使动画"仍在生效"（filling forwards），每个 `<tr>` 都成为**独立的 stacking context**
- DOM 中后续行的层叠顺序更高 → 无论 `.c-dd-menu` 的 `z-index` 多大，它只在父行的 stacking context 内生效，**无法逃逸到其他行之上**
- 仅修复 `overflow` 不够——即使菜单不被裁剪，后续行仍然绘制在菜单之上
- 修复：给每行 `z-index: 0` 作为基准，打开下拉时提升该行 `z-index: 10`（CSS `:has()` + JS fallback `c-dd-elevated` class）

### 第三层：table-layout: auto 列宽不稳定

- 默认 `table-layout: auto` 下列宽由内容决定，长任务名可挤压操作列
- Users 表格已在 2026-08 修复此问题，Dashboard 未同步对齐

## 3. 测试漏洞

现有测试体系中无 CSS 布局验证能力：

- 单元测试和路由冒烟测试（86 路由）仅验证 HTTP 状态码和关键 HTML 元素存在性，不验证视觉布局
- `check_ui_contract.py` 检查 inline style 和 legacy class，不覆盖 `overflow` 裁剪或 `table-layout` 属性
- 无 E2E 浏览器测试来验证下拉菜单的可见性和元素重叠

## 4. 修复

### CSS 修复（`app/static/css/redesign-pages.css`）

- `.c-table-wrap { overflow: visible; }` — 解除裁剪（第一层）
- `tr:last-child td { border-bottom-*-radius: 7px; }` — 保持底部圆角
- `tr { position: relative; z-index: 0; }` — 行基准层叠（第二层）
- `tr:has(.c-dd.open) { z-index: 10; }` — CSS-only 打开行提升（第二层，现代浏览器）
- `tr.c-dd-elevated { z-index: 10; }` — JS fallback 打开行提升（第二层，旧浏览器）
- `.c-dd-menu { z-index: 50; box-shadow: 0 8px 24px rgba(0,0,0,0.15); }` — 增强视觉分层
- `.c-table { table-layout: fixed; min-width: 960px; }` — 固定列宽（第三层）
- `@media (max-width: 1024px) { .c-table-wrap { overflow-x: auto; } }` — 窄屏降级

### JS 修复

- `_dashboard_rows.html`：toggle 按钮 onclick 中增加 `tr.classList.toggle('c-dd-elevated', dd.classList.contains('open'))`
- `dashboard.html`：outside-click close handler 中增加 `tr.classList.remove('c-dd-elevated')`

## 5. 防护测试

- 静态门禁 `python scripts/check_ui_contract.py --check` 通过（0 违规）
- 颜色审计 `python scripts/audit_hardcoded_colors.py --check` 通过
- 路由冒烟 `python scripts/smoke_routes.py --check` — 86 路由全通过
- 功能验证：以 `cron:write` 用户登录 v2 Dashboard，确认 `c-dd-menu`、`act-btn` 正常渲染

## 6. 同类排查

全项目搜索使用 `c-dd-menu`（绝对定位下拉菜单）的页面：

- Dashboard — 本次修复
- 其他 Redesign 页面（Users、Tags、Exec Logs）使用 `um-icon-btn` 扁平图标 + CpConfirm 模态确认，不使用 `c-dd` 下拉菜单，不受影响
- 如果未来有新页面引入 `c-dd` 下拉菜单，同样需要检查 `.c-table-wrap` 的 `overflow` 设置

## 7. 预防方案

1. **新页面引入 c-dd 下拉菜单时的检查清单**：凡在 `.c-table-wrap` 内使用 `c-dd` 组件，必须检查外层 `overflow` 属性，并在页面专属 CSS 中覆盖为 `overflow: visible`（如需要）。此规则记录在本复盘文档中，供后续开发参考。
     
   验证命令：`grep -rn "c-dd" app/templates/redesign/ | grep -v "c-dd-menu\|c-dd-toggle" | head -10`
2. **table-layout: fixed 对齐检查**：新增 Redesign 表格页面时，对照 Users 表格的 `table-layout: fixed + min-width` 模式。
     
   验证命令：`grep "table-layout" app/static/css/redesign-pages.css`（应为每个表格页面都有一条）

[文档索引](../index.html) · [Markdown](2026-09-Dashboard表格溢出修复.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
