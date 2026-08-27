# 任务中心筛选 AJAX 化设计

> HTML 版：[任务中心筛选AJAX化设计.html](任务中心筛选AJAX化设计.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 任务中心筛选 AJAX 化设计

编号：OPT-P1-17 · 状态：设计中 · 日期：2026-08-26

## 1. 问题

Redesign (v2) 任务中心（`redesign/dashboard.html`）每次过滤操作（异常/状态/组/标签/搜索/翻页）均触发整页 GET 刷新，浏览器滚动位置重置到顶部。用户在查看下方表格时，每次点击筛选按钮都会导致页面跳回顶部，需要重新滚动定位，体验很差。

## 2. 根因

- 异常/状态筛选按钮使用 `<a href="...">` 整页跳转
- 组/标签下拉使用 `onchange="location.href=this.value"` 整页跳转
- 任务名搜索使用 `<form method="get">` 原生表单提交
- 分页使用 `<a href="...">` 整页跳转
- Legacy v1 已通过 `partial=1` AJAX 模式解决此问题，但 v2 未沿用该模式

## 3. 方案

### 推荐方案：AJAX 局部刷新

将筛选/翻页操作改为 AJAX 请求，仅更新表格区域（table body + pagination），不刷新整页，页面滚动位置自然保持稳定。

#### 3.1 后端改动

在 `cron_list()` 视图函数的 v2 分支中，增加 `partial=1` 支持。返回 JSON 包含：

- `rows`：表格 tbody 内容（新建局部模板 `redesign/_dashboard_rows.html`）
- `pagination`：分页 HTML（新建局部模板 `redesign/_dashboard_pagination.html`）
- `stats`：统计数字（异常/逾期/今日失败等），用于更新顶部 Stats Cards
- `total`：总数（用于分页信息）

#### 3.2 前端改动（`dashboard.html` 内 JS）

1. 拦截所有筛选按钮的 click 事件（`.f-btn` 链接），阻止默认跳转，改用 `fetch` 请求
2. 拦截下拉框 change 事件，阻止 `location.href` 赋值
3. 拦截搜索表单 submit 事件，改用 AJAX
4. 拦截分页链接 click 事件
5. AJAX 成功后：更新 table tbody innerHTML、pagination innerHTML、Stats Cards 数字
6. 用 `history.replaceState` 更新 URL（不触发导航）
7. 更新筛选按钮的 active 状态 class

#### 3.3 备选方案（不推荐）：滚动锚点

在所有筛选链接 href 后加 `#filters`，页面加载后浏览器自动滚动到锚点位置。缺点：仍有整页刷新闪烁，体验不如 AJAX 方案。

## 4. 范围

### 改动文件

| 文件 | 变更 |
| --- | --- |
| `app/main/views.py` | v2 分支增加 `partial=1` JSON 响应 |
| `app/templates/redesign/_dashboard_rows.html` | 新建：抽取 table tbody 渲染逻辑 |
| `app/templates/redesign/_dashboard_pagination.html` | 新建：抽取 pagination 渲染逻辑 |
| `app/templates/redesign/dashboard.html` | ① include 新局部模板 ② 筛选元素改为 JS 拦截 ③ 新增 AJAX 筛选 JS 逻辑 |

### 明确不做

- 不改动 Exception Panel（异常面板）的 AJAX 更新（保持首次加载时数据即可，筛选后不更新异常面板）
- 不改动 v1 legacy 的现有 AJAX 逻辑
- 不引入任何新依赖
- 不改动数据模型或 API

## 5. 分批

| 批次 | 内容 | 验收标准 |
| --- | --- | --- |
| Batch 1 | 后端 partial 支持 + 局部模板抽取 | `curl '/cron_list?partial=1'` 返回 JSON 且 rows 非空 |
| Batch 2 | 前端 AJAX 筛选 JS + URL 更新 + active 状态同步 | 浏览器中点击筛选按钮，页面不刷新，表格内容更新，URL 变化，滚动位置不变 |

## 6. 验收

1. `bash scripts/cronpilot.sh test` 全量通过
2. 浏览器验证：登录后进入任务中心 → 滚动到表格区域 → 点击"持续异常"筛选按钮 → 页面不刷新、滚动位置不变、表格内容更新
3. 浏览器验证：切换组下拉 → 页面不刷新、表格更新
4. 浏览器验证：输入任务名搜索 → 回车或自动触发 → 页面不刷新、表格更新
5. 浏览器验证：点击分页 → 页面不刷新、表格更新
6. 浏览器验证：筛选后浏览器地址栏 URL 正确反映当前筛选条件
7. 浏览器验证：刷新页面后筛选状态保持（因 URL 已更新）

## 7. 风险

- **Stats Cards 数据一致性**：AJAX 刷新时同步更新 stats 数字，确保与筛选条件一致
- **Exception Panel**：首次加载时渲染，筛选后不更新（面板展示的是全局异常概览，与当前筛选无关）
- **回归风险**：筛选逻辑纯前端拦截，后端不变，回归面小
- **降级**：JS 加载失败时筛选链接仍为原始 href，降级为整页刷新（可用）

## 8. 交互契约

| 元素 | 原行为 | 新行为 |
| --- | --- | --- |
| `.f-btn` 筛选按钮 | `<a href>` 整页跳转 | JS click → AJAX fetch → 更新表格 |
| `.f-select` 下拉框 | `onchange="location.href=..."` | JS change → AJAX fetch → 更新表格 |
| 任务名搜索 form | `<form method=get>` 提交 | JS submit → AJAX fetch → 更新表格（增加 300ms 防抖） |
| 分页链接 | `<a href>` 整页跳转 | JS click → AJAX fetch → 更新表格 + 滚动到表格顶部 |

**CSS class 变更**：无新增可见 DOM 行；仅 JS 行为变更。

**降级策略**：所有筛选元素保留原始 href/action 属性，JS 未加载时降级为整页跳转。

[文档索引](index.html) · [Markdown](任务中心筛选AJAX化设计.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
