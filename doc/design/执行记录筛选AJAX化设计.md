# 执行记录筛选AJAX化设计 — OPT-P1-18

> HTML 版：[执行记录筛选AJAX化设计.html](执行记录筛选AJAX化设计.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 执行记录筛选 AJAX 化设计（OPT-P1-18）

**状态**：设计待确认  
**关联**：OPT-P1-17（任务中心筛选 AJAX 化已完成）  
**日期**：2026-08-26

## 1. 问题

执行记录页面（`redesign/execution_logs.html`）在用户排障时需要频繁切换筛选条件（非成功/全部/仅失败/仅异常/仅成功），每次点击按钮触发 `<form method="get">` 提交 → 整页重载 → 滚动位置回到顶部。

在排障场景中，用户可能在数百条记录中反复切换筛选条件对比问题模式，整页刷新严重影响工作效率和连贯性。

## 2. 根因

执行记录页面的 5 个结果筛选按钮使用 `<button type="submit" name="outcome" value="xxx">`，搜索和翻页使用标准 HTML 表单/链接。这是浏览器的原生导航行为：每次触发都是一个新的 HTTP GET 请求，浏览器必然重置 scroll position。

v2 redesign 时只重构了视觉样式，未引入 AJAX 局部刷新机制。

## 3. 方案

复用 OPT-P1-17 的 AJAX partial 模式：

1. 将表格 tbody 和分页区域拆为独立 Jinja2 partial 模板
2. 后端在 `partial=1` 时返回 JSON（含 rows HTML + pagination HTML + total）
3. 前端 IIFE 拦截所有筛选事件，通过 `fetch` 获取 JSON 并更新 DOM
4. `history.replaceState` 保持 URL 同步
5. JS 未加载时降级为整页刷新（按钮保留原 type="submit"）

### 3.1 前端改动

| 控件 | 现状 | AJAX 后 |
| --- | --- | --- |
| 5 个结果按钮 | `type="submit"` 触发表单提交 | JS 拦截 click → `doFetch()`；`type` 改为 `"button"`，降级时由隐藏 submit 兜底 |
| 任务名称/内容搜索 | 表单提交 | 300ms debounce input + form submit 拦截 |
| 日期范围 | 表单提交 | change 事件触发 doFetch() |
| 搜索按钮 | `type="submit"` | form onsubmit 拦截 |
| 重置链接 | `<a href="...">` 整页导航 | JS 拦截 → 清空 state → doFetch() |
| 翻页链接 | `<a href="?page=N">` | JS 事件委托 → 提取 page → doFetch() |

### 3.2 后端改动

在 `job_log_list()` 和 `job_log_all_list()` 的 v2 分支中，`partial=1` 时返回：

```
{
  "rows": "<渲染后的 tbody HTML>",
  "pagination": "<渲染后的分页 HTML>",
  "total": 125
}
```

### 3.3 新增 partial 模板

- `app/templates/redesign/_exec_logs_rows.html` — tbody 循环（从 execution\_logs.html 第 81-140 行提取）
- `app/templates/redesign/_exec_logs_pagination.html` — 分页区域（从第 144-170 行提取）

## 4. 范围

| 改动 | 文件 |
| --- | --- |
| 后端 partial 分支 | `app/main/views.py`（job\_log\_list + job\_log\_all\_list） |
| Partial 模板拆分 | `app/templates/redesign/_exec_logs_rows.html`（新增） `app/templates/redesign/_exec_logs_pagination.html`（新增） |
| 主模板 AJAX JS | `app/templates/redesign/execution_logs.html` |
| 回归测试 | `tests/test_exec_logs_partial.py`（新增） |

**明确不做**：

- 不修改 v1 模板（`job_log_list.html` / `job_log_all_list.html`）
- 不改变列数、列头文案、CSS class
- 不添加新功能（如实时刷新、WebSocket）

## 5. 分批

1. **Batch 1**：拆 partial 模板 + 后端 `partial=1` JSON 响应 → 单测验证
2. **Batch 2**：前端 AJAX JS（筛选按钮 + 搜索 + 翻页）→ 浏览器验证

## 6. 验收

1. `.venv-py311/bin/python -m unittest tests.test_exec_logs_partial -v` — 全部通过
2. `bash scripts/cronpilot.sh restart --daemon` → 浏览器访问执行记录页
3. 点击「仅失败」→ 页面不滚动、表格内容更新、URL 含 `outcome=fail`
4. 输入任务名称 → 300ms 后表格自动更新
5. 点击翻页 → 页面不滚动
6. JS 禁用时 → 各按钮/链接仍可整页刷新正常使用

## 7. 风险

- **日期选择器兼容**：现有 `.js-datetime` 可能依赖第三方库（如 WindUI），AJAX 刷新后需重新绑定 → 在 `doFetch` 回调中处理
- **content-code 展开状态丢失**：AJAX 更新 innerHTML 后，展开的 `.expanded` 状态会丢失 → 可接受（用户正在切换筛选，旧展开状态无意义）
- **两个入口共用模板**：`job_log_list`（单任务）和 `job_log_all_list`（全局）使用同一模板，partial JS 需根据 `cron_info` 存在与否确定 base URL

[文档索引](index.html) · [Markdown](执行记录筛选AJAX化设计.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
