# Run Inspector HTTP 状态标签未消费修复复盘

> HTML 版：[2026-09-RunInspector-http状态标签未消费修复.html](2026-09-RunInspector-http状态标签未消费修复.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# Run Inspector HTTP 状态标签未消费 · 复盘

日期：2026-09-18 · 状态：**已修复并验证（F3）**

关联评估：[执行侧观测近期提交专业 Review 评估](../design/执行侧观测近期提交专业Review评估-2026-09-18.html)

**问题：**Presenter 已计算 `http_status_label`，用于表达“未获得 HTTP 响应”，但模板 Meta 区仍渲染 `summary.http_status`。无响应执行因此只显示“—”，丢失了明确诊断信息。

**结果：**Meta 区统一消费 `http_status_label`；有 HTTP 状态时保持原数字，无响应时显示“未获得 HTTP 响应”。

## 1. Bug 定位

问题位于 `app/templates/redesign/run_inspector.html` Meta 区的 HTTP 字段。Presenter 的 `summary.http_status_label` 本身已正确计算。

## 2. 根因

Presenter DTO 同时保留原始 `http_status` 和面向展示的 `http_status_label`，模板沿用了旧字段名，缺少 DTO 字段消费门禁。行为层根因是展示层没有把“原始值”和“语义标签”区分为不同用途。

## 3. 测试漏洞

既有 Presenter 测试只断言 DTO 中的 `http_status_label`，没有读取模板并断言 Meta 区消费该字段。因此计算逻辑正确但页面未使用时，测试仍会通过。

## 4. 修复

将模板从 `run.summary.http_status` 改为 `run.summary.http_status_label`；新增契约测试，禁止 Meta 区回退到原始字段。没有改变 API、数据库字段或业务结果判定。

## 5. 防护测试

- `tests/test_execution_observability_contract.py::test_run_inspector_meta_uses_http_status_label`：断言模板使用语义标签且不使用旧字段。
- `.venv-py311/bin/python -m unittest tests.test_execution_observability_contract tests.test_run_inspector_presenter tests.test_job_log_detail_integration -q`（35 条通过）
- `.venv-py311/bin/python scripts/check_ui_contract.py --check`、`.venv-py311/bin/ruff check app/`、`.venv-py311/bin/python scripts/smoke_routes.py --check`（86/86）

## 6. 同类排查

已检索 Run Inspector 模板中所有 `summary.http_status`、`http_status_label` 引用；Meta 区已切换到语义标签，响应区仍按原始 HTTP 数值渲染，职责边界清晰。F6 外层 fatal 阶段映射与 F4/F5 迁移观察项仍保持独立。

## 7. 预防方案

对 Presenter DTO 中所有“原始值/展示标签”成对字段增加模板消费断言；新增展示字段时必须同时补“计算存在 + 模板消费”的测试。门禁位置：`tests/test_execution_observability_contract.py`，第三方可用 §5 命令复现。

[Markdown](2026-09-RunInspector-http状态标签未消费修复.md) · [复盘索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
