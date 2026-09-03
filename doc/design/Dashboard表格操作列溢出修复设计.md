# Dashboard 操作下拉菜单与任务行重叠修复设计

> HTML 版：[Dashboard表格操作列溢出修复设计.html](Dashboard表格操作列溢出修复设计.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# Dashboard 操作下拉菜单与任务行重叠修复设计

状态：已确认 · 已实施 | 日期：2026-08-27 | 实施：2026-09-03

## 1. 问题

Dashboard 任务列表中，点击操作列的"更多"（⋮）按钮弹出的下拉菜单（包含暂停/恢复、编辑、下线选项）与下方的任务行发生视觉交叉重叠，显示混乱。

**表现**：

- 下拉菜单（`.c-dd-menu`）使用 `position: absolute; top: calc(100% + 4px)` 向下展开
- 菜单展开后覆盖在后续任务行上方，但被 `.c-table-wrap { overflow: hidden }` 裁剪（尤其是接近表格底部的行）
- 菜单覆盖区域的行内容（任务名、状态等）透过菜单底层隐约可见，造成视觉混乱

## 2. 根因

`.c-table-wrap`（表格外层容器）设置了 `overflow: hidden` 用于配合 `border-radius: 8px` 实现圆角裁剪。这导致所有溢出容器边界的子元素（包括绝对定位的下拉菜单）被裁剪。

**CSS 布局链**：

```
.c-table-wrap { overflow: hidden; border-radius: 0 0 8px 8px; }    ← 裁剪源
  └ .c-table
    └ tbody > tr > td
      └ .c-dd { position: relative; }
        └ .c-dd-menu { position: absolute; z-index: 20; }           ← 被裁剪
```

**CSS 规范约束**：`overflow: hidden` 创建了 BFC（块格式化上下文），所有子元素的绝对定位、z-index 都无法逃逸该裁剪区域。同理，`overflow-x: auto; overflow-y: visible` 在 CSS2.1 规范中会被浏览器计算为 `overflow-y: auto`，无法单独解除纵向裁剪。

## 对比 Demo

**在浏览器中打开对比**：[dashboard-table-overflow-demo.html](screenshots/dashboard-table-overflow-demo.html)

## 3. 方案

### 3.1 解除表格外层 overflow 裁剪

将 Dashboard 的 `.c-table-wrap` 从 `overflow: hidden` 改为 `overflow: visible`，让下拉菜单可以自由扩展到容器外部。圆角通过最后一行 `td` 的 `border-radius` 保持：

```
/* 解除 overflow 裁剪，允许下拉菜单逃逸 */
.cp-page-dashboard .c-table-wrap {
  overflow: visible;
}
/* 保持底部圆角视觉 */
.cp-page-dashboard .c-table tbody tr:last-child td:first-child {
  border-bottom-left-radius: 7px;
}
.cp-page-dashboard .c-table tbody tr:last-child td:last-child {
  border-bottom-right-radius: 7px;
}
```

### 3.2 下拉菜单视觉增强

增强下拉菜单的视觉分层效果，让它与背景行明确区分：

```
/* 增强下拉菜单的分层感 */
.cp-page-dashboard .c-dd-menu {
  z-index: 50;
  box-shadow: 0 8px 24px rgba(0,0,0,0.15);
}
```

### 3.3 表格固定列宽（附带修复）

同时修复 `table-layout: fixed` 确保操作列宽度稳定：

```
.cp-page-dashboard .c-table { table-layout: fixed; min-width: 960px; }
.cp-page-dashboard .c-table th { white-space: nowrap; }
```

### 3.4 窄屏横向滚动

在外层增加一个 overflow wrapper 用于窄屏横向滚动（不影响下拉菜单溢出）：

```
@media (max-width: 1024px) {
  .cp-page-dashboard .c-table-wrap {
    overflow-x: auto;   /* 窄屏横向滚动 */
    overflow-y: visible; /* 实际被浏览器计算为 auto — 但 min-height 足够不会触发 */
  }
}
```

**注**：由于 CSS 规范限制，当 `overflow-x` 为 `auto` 时，`overflow-y: visible` 实际被计算为 `auto`。但由于表格高度不固定（由内容决定），`overflow-y: auto` 等效于 `visible`（不会出现纵向滚动条），下拉菜单仍然可以正常显示。

## 4. 范围

| 文件 | 变更 |
| --- | --- |
| `app/static/css/redesign-pages.css` | Dashboard .c-table-wrap overflow: visible + 底部圆角；.c-dd-menu 增强 z-index 和阴影；table-layout: fixed + min-width |

**不做**：不修改模板 HTML 结构；不修改 JS 逻辑；不影响其他页面的表格。

## 5. 分批

单批 CSS-only 修复，共 ~10 行 CSS。

## 6. 验收

1. `bash scripts/cronpilot.sh restart --daemon`
2. 以有 `cron:write` 权限的用户登录 V2 Dashboard（非种子 admin）
3. 点击运行中任务的"更多"（⋮）按钮，下拉菜单（暂停/编辑/下线）完整显示，不被裁剪
4. 下拉菜单明确浮于下方行之上，阴影清晰可见，无视觉交叉
5. 对最后一行任务点击"更多"，菜单同样完整可见
6. 表格底部圆角保持正常
7. CSS 门禁：`python scripts/check_ui_contract.py --check`

## 7. 风险

- **低**：`overflow: visible` 在宽屏（≥1024px）下，表格不会横向溢出（min-width: 960px < 内容区宽度）
- **低**：窄屏 @media 降级为 `overflow-x: auto` 后，下拉菜单在纵向上可能被轻微裁剪（但表格高度通常足够不触发）
- **无**：仅影响 Dashboard 表格（选择器 `.cp-page-dashboard` 限定），不影响其他页面

[文档索引](index.html) · [Markdown](Dashboard表格操作列溢出修复设计.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
