# 操作记录与审计日志筛选AJAX化设计 — OPT-P1-19

> HTML 版：[操作记录与审计日志AJAX化设计.html](操作记录与审计日志AJAX化设计.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 操作记录与审计日志筛选 AJAX 化（OPT-P1-19）

**状态**：设计待确认  
**关联**：OPT-P1-17/18（同模式已交付）  
**日期**：2026-08-26

## 1. 问题

操作记录（`redesign/operation_log.html`）和审计日志（`redesign/audit_logs.html`）的筛选/搜索/翻页均使用 `<form method="GET">`，每次操作触发整页刷新并滚动到顶部。

## 2. 方案

复用 OPT-P1-17/18 相同的 AJAX partial 模式。

### 2.1 操作记录

| 筛选控件 | 行为 |
| --- | --- |
| 关键词输入 | 300ms debounce → doFetch() |
| 操作类型下拉 | change → doFetch() |
| 搜索按钮 | form submit 拦截 |
| 清除链接 | click 拦截 → 清空 state → doFetch() |
| 翻页链接 | 事件委托 → doFetch() |

### 2.2 审计日志

| 筛选控件 | 行为 |
| --- | --- |
| 用户名搜索 | form submit 拦截 + 300ms debounce |
| 类型 chip 链接 | click 拦截 → doFetch() |
| 清除链接 | click 拦截 → 清空 state → doFetch() |
| 翻页链接 | 事件委托 → doFetch() |

### 2.3 用户管理

| 筛选控件 | 行为 |
| --- | --- |
| 用户名搜索 | form submit 拦截 + 300ms debounce |
| 状态 chip（全部/启用/停用） | click 拦截 → doFetch() |
| 清除链接 | click 拦截 → 清空 state → doFetch() |
| 翻页链接 | 事件委托 → doFetch() |

**特殊点**：AJAX 响应额外返回 `counts`（total/active/inactive）用于更新顶部状态计数 chip 和成员数副标题。事件委托式 jQuery 监听（`$(document).on('click', '.um-deactivate-btn')`）确保 DOM 更新后模态框和确认操作仍可用。

## 3. 范围

| 改动 | 文件 |
| --- | --- |
| 操作记录 partial 模板 | `_oplog_rows.html` + `_oplog_pagination.html`（新增） |
| 审计日志 partial 模板 | `_audit_logs_rows.html` + `_audit_logs_pagination.html`（新增） |
| 用户管理 partial 模板 | `_users_rows.html` + `_users_pagination.html`（新增） |
| 后端 partial 分支 | `app/main/views.py`（operation\_log\_list） `app/rbac/views.py`（audit\_logs, users\_list） |
| 前端 AJAX JS | `operation_log.html` + `audit_logs.html` + `users.html` |
| 回归测试 | `tests/test_oplog_audit_partial.py`（新增，10 条） |

**明确不做**：不修改 v1 模板、不改列结构。

## 4. 验收

1. 单测通过：`.venv-py311/bin/python -m unittest tests.test_oplog_audit_partial -v`
2. `bash scripts/cronpilot.sh restart --daemon` → 浏览器验证筛选不刷新页面

[文档索引](index.html) · [Markdown](操作记录与审计日志AJAX化设计.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
