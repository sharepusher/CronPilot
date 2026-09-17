# 复盘：执行记录 pending 误标「未知」与 outcome 白名单漏登

> HTML 版：[2026-09-执行记录pending误标未知.html](2026-09-执行记录pending误标未知.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 复盘：执行记录 pending 误标「未知」与 outcome 白名单漏登

日期：2026-09-16 · 设计：[R1 短设计](../design/R1-执行记录列表pending-running显示收口设计-2026-09.html) · 父方案：收敛版 B5 前半

## 1. Bug 定位

1. **徽章**：`app/templates/redesign/_exec_logs_rows.html` 结果列无 `pending` 分支，落入 `else → 「未知」`；`running` 误用 `el-log-unknown`。
2. **筛选**（实现中发现）：`job_log_filter.job_log_outcome_clause('in_progress')` 已支持，但 `app/main/views.py` 的 `_parse_log_outcome_param` / 单任务 outcome 白名单未含 `in_progress`，URL 参数被降级为默认 `not_success`。

## 2. 根因

- **行为层（徽章）**：B1 状态机写入 `pending/running` 后，列表模板仍按旧终态枚举手写分支；已有 `job_log_badge()` 未被列表复用，两套映射漂移。
- **行为层（白名单）**：outcome 校验在视图层硬编码元组，与 filter 模块分离；新增 SQL 子句不等于 URL 可解析，缺集成断言时假绿（只测 clause、不测视图解析）。

## 3. 测试漏洞

- 既有 `test_job_log_display` / `test_b1_execution_status` 覆盖 badge 映射，但**不渲染** `_exec_logs_rows.html`。
- `test_job_log_outcome_filter` 只测 clause；不经 `_parse_log_outcome_param`。
- `test_exec_logs_partial` 无 pending 夹具，发现不了「未知」误标与白名单丢弃。

## 4. 修复

- 结果列改为 `log.status|job_log_badge`；新增 `.el-log-pending` / `.el-log-running`。
- 筛选 chip「进行中」→ `outcome=in_progress`；filter 子句含 pending+running；默认 not\_success 不变。
- 视图白名单改为引用 `KNOWN_OUTCOMES`（`job_log_filter.py`），全局列表与单任务列表共用。

## 5. 防护测试

- `tests.test_job_log_outcome_filter`：`in_progress` 含 pending/running；not\_success 不含；`KNOWN_OUTCOMES` 含 in\_progress。
- `tests.test_exec_logs_partial.TestExecLogsPartial.test_pending_badge_and_in_progress_filter`：页面含「已入队」/「进行中」；partial in\_progress 共 2 条且无「未知」；not\_success 不含 pending id。

## 6. 同类排查

- v1 列表模板：本轮 redesign 为主路径；未发现第二套 pending→未知分支。
- 任务详情近期点：已有 pending/running class（热修），不在本 bug 范围。
- 其它硬编码 outcome 元组：已收敛到 `KNOWN_OUTCOMES`。

## 7. 预防方案

| 措施 | 落地 | 验证 |
| --- | --- | --- |
| 新增 outcome 值时**只改** `KNOWN_OUTCOMES` + `job_log_outcome_clause`；视图禁止再写死元组 | `app/services/job_log_filter.py` · `app/main/views.py` 引用 | `rg "_parse_log_outcome_param|KNOWN_OUTCOMES" app/main/views.py`；`python -m unittest tests.test_job_log_outcome_filter tests.test_exec_logs_partial -v` |
| 列表状态展示必须走 `job_log_badge`，禁止模板手写 status 分支 | R1 模板 + 设计/本复盘 | `rg "log.status ==" app/templates/redesign/_exec_logs_rows.html` 应无结果列分支 |

关联设计：[R1](../design/R1-执行记录列表pending-running显示收口设计-2026-09.html) ·
[复盘索引](index.html)
· [Markdown](2026-09-执行记录pending误标未知.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
