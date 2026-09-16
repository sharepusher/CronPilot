# 执行详情 URL 脱敏缺失修复复盘

> HTML 版：[2026-09-execution-detail-url-redaction.html](2026-09-execution-detail-url-redaction.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 执行详情 URL 脱敏缺失修复复盘

日期：2026-09-15 · 状态：已修复并验证 · 对应设计：[执行详情 URL 字段角色化脱敏修复设计](../design/执行详情URL字段角色化脱敏修复设计-2026-09.html)

**影响：**执行详情的 Redesign 模板直接输出任务配置 URL。拥有 `log:read` 权限的用户可能在 query 参数或 URL userinfo 中看到凭据。此次修复仅改变展示，不删除或改写已有任务和执行记录。

## 1. Bug 定位

`app/templates/redesign/run_inspector.html` 直接读取 `cif.req_url`，并在管理员分支读取 `jl.actual_url`。这两项均可能包含 token、API key、签名或 userinfo 密码，且绕过角色化 Presenter。实施回归还发现 DTO 最初把“实际请求已注入运行参数”的事实暴露给 Operator/Viewer，虽不含 URL 原值，仍违背既定角色矩阵。

## 2. 根因

执行详情先为时间线引入了 Presenter，却没有把请求、响应、元数据和业务日志纳入同一 DTO 边界。模板仍持有 ORM 对象，导致“路由完成 RBAC 鉴权”被误当成“字段可原样展示”。权限控制的是资源访问权，不自动证明资源内每个字段均无敏感性。

## 3. 测试漏洞

此前集成测试仅验证详情页返回 200 和 trace ID 渲染，没有使用含 URL 凭据的样本，也没有断言响应 HTML 不含秘密值；模板没有“禁止原始 ORM 访问”的静态边界测试。因此页面在功能可用时仍存在展示泄露。

## 4. 修复

新增 `sanitize_url_for_display()`：保留 scheme、host、port、path、query 参数名和顺序，将每个 query 值统一替换为 `***`，userinfo 替换为 `***:***@`，fragment 丢弃，解析异常 fail-closed。新增 `build_run_inspector_view()`，路由在资源鉴权后构建只含可渲染基础类型的 DTO；模板改为只接收 `run`，不再访问 `cif`、`jl`、`item`。DTO 的 `actual_request_sent` 仅在 Admin 下计算，Operator/Viewer 连该执行事实也不接收。

## 5. 防护测试

- `tests/test_run_inspector_presenter.py` 覆盖 userinfo、重复 query key、空值与非法 URL。
- `tests/test_job_log_detail_integration.py` 以 Admin、Operator、Viewer 三种真实角色登录，用带 `secret-value`、user/password、签名的样本断言执行详情 HTML 不含原值；仅 Admin 可见“实际请求已注入运行参数”。
- 同一测试静态断言模板中不存在 `cif.`、`jl.`、`item.`，阻止绕过 DTO 的回归。

## 6. 同类排查

本次确认了执行详情的请求 URL、实际 URL、DNS Pinning IP 和请求 Body 均不再进入模板；响应正文、业务日志和时间线 detail 仍依既有角色化 Presenter 规则输出。未修改任务编辑页，因为它属于具备写权限的配置面；未修改 API 和数据库原始字段。事件 detail、异常消息和 SSRF 原因的入库存储脱敏属于独立 Bugbot P0-2，仍须单独设计和修复。

## 7. 预防方案

将执行详情模板的 DTO 边界固化为可执行门禁：`tests/test_job_log_detail_integration.py::test_template_has_no_raw_orm_access` 禁止三类 ORM 前缀，且凭据样本的 HTML 否定断言必须持续通过。后续新增执行详情字段时，必须先在 `build_run_inspector_view()` 显式建模，再添加“HTML 不含敏感原值”的测试；验证命令为 `.venv-py311/bin/python -m unittest tests.test_run_inspector_presenter tests.test_job_log_detail_integration -v`。

[Markdown](2026-09-execution-detail-url-redaction.md) · [复盘索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
