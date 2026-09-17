# 复盘：Run Inspector Admin 时间线 raw detail JSON 泄露与诊断顺序

> HTML 版：[2026-09-RunInspector-raw-detail与时间线顺序.html](2026-09-RunInspector-raw-detail与时间线顺序.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 复盘：Run Inspector Admin 时间线 raw detail JSON 泄露与诊断顺序

日期：2026-09-16 · 设计：[R2 短设计](../design/R2-RunInspector-Presenter详情契约收口设计-2026-09.html) · 父方案：收敛版 B4

## 1. Bug 定位

1. **敏感泄露**：`app/services/run_inspector_presenter.py` 的 `_detail_value(..., include_detail=True)` 对 Admin 将整段 `event.detail` `json.dumps`；模板 `run_inspector.html` 用 `<code class="ri-timeline-detail">{{ event.detail }}</code>` 渲染。
2. **诊断顺序**：同模板 DOM 顺序为 请求 → 响应 → 业务 → 元数据 → **执行时间线**，与「先看走到哪一步」相反。
3. **角色粒度**：视图仅 `role == 'admin'` 二元门，Viewer/Operator 同权，无法落地 Operator 有限正文摘要。

## 2. 根因

- **行为层（泄露）**：热修接线 Presenter 时把「Admin 可看更多」实现成「整段 detail JSON」，覆盖了收敛版「任何角色不得见 raw detail」硬约束；白名单摘要未实现。
- **行为层（顺序）**：时间线作为增量区块追加在模板末尾，未按信息架构重排。
- **行为层（角色）**：DTO 仍用 `is_admin` 布尔，未引入 `viewer_role` 三角色矩阵。

## 3. 测试漏洞

- `tests.test_run_inspector_presenter.test_admin_receives_structured_detail` **正向锁定了泄露行为**（断言 Admin 得到 JSON 字符串），把错误契约测成「正确」。
- 集成测试只否定 URL 凭据明文，未否定时间线 `exc_detail` / `ri-timeline-detail`，也未断言 DOM 中时间线先于请求。

## 4. 修复

- Presenter：删除 raw detail 输出；时间线仅 `summary`（白名单）；`viewer_role` 三角色（URL / 响应 / 业务日志）。
- 模板：Meta → 未完成提示条 → 时间线 → 请求/响应/业务/元数据；渲染 `event.summary`。
- 视图：`normalize_viewer_role(session['role'])` 传入 Presenter。

## 5. 防护测试

- `test_no_role_receives_raw_event_detail_json`：三角色 summary 不含 `exc_detail` / `{`
- `test_timeline_before_request_and_no_raw_detail_json`：HTML 时间线先于请求；无 `SENSITIVE_STACK_TRACE` / `ri-timeline-detail`
- `test_pending_shows_incomplete_banner` / `test_viewer_hides_business_logs_and_response_body` / Viewer URL 去 query

验证：`.venv-py311/bin/python -m unittest tests.test_run_inspector_presenter tests.test_job_log_detail_integration -v`

## 6. 同类排查

| 路径 | 结论 |
| --- | --- |
| 执行列表 / 任务详情近期执行 | 不渲染 event.detail；无同类 JSON dump |
| `execution_tracer._safe_detail` | 写库仍存白名单键（含 `exc_detail`）；展示层已禁止原文输出，写路径属 R3 尾巴不在本轮 |
| API 执行详情 | 无等价时间线 HTML；未发现同源模板渲染 |

## 7. 预防方案

**措施：**在 `tests/test_job_log_detail_integration.py::test_template_has_no_raw_orm_access` 增加禁止 `event.detail`；并新增集成否定断言「HTML 不得出现 `ri-timeline-detail` / `exc_detail`」。后续时间线字段只能经 `summary` 白名单进入模板。

**落地位置：**上述测试文件（已落地）+ 设计契约 R2 §3.2。

**第三方验证：**

```
grep -n 'event.detail\|ri-timeline-detail' app/templates/redesign/run_inspector.html && echo FAIL || echo OK
.venv-py311/bin/python -m unittest tests.test_job_log_detail_integration.TestJobLogDetailIntegration.test_timeline_before_request_and_no_raw_detail_json -v
```

相关：[R2 设计](../design/R2-RunInspector-Presenter详情契约收口设计-2026-09.html) ·
[URL 脱敏复盘](2026-09-execution-detail-url-redaction.html) ·
[复盘索引](index.html)
· [Markdown](2026-09-RunInspector-raw-detail与时间线顺序.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
