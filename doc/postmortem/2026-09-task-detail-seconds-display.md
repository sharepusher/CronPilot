# 任务详情 seconds 展示丢失修复复盘

> HTML 版：[2026-09-task-detail-seconds-display.html](2026-09-task-detail-seconds-display.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 任务详情 seconds 展示丢失修复复盘

日期：2026-09-16 · 状态：已修复并验证 · 对应设计：[任务执行链路可观测性设计方案（收敛版）](../design/任务执行链路可观测性设计方案-收敛版.html)

**影响：**任务详情页使用五字段有效 Cron 展示调度规则，导致配置了 seconds 的任务丢失秒级约束，页面展示可能与实际调度频率不一致。此次修复只调整展示，不改变任务实际调度。

## 1. Bug 定位

`app/main/views.py` 的任务详情视图调用 `effective_crontab_5()`，该函数按设计只返回五个字段，因此 `second=*/10` 没有进入页面的 `cron_expr`。

## 2. 根因

代码同时存在五字段辅助函数和包含可选 seconds 的完整格式化函数，调用方选择了较底层的五字段函数，未遵循统一展示契约。

## 3. 测试漏洞

既有测试覆盖分钟、小时和空调度，但没有覆盖任务详情调用方，也没有为 seconds 表达式建立断言。

## 4. 修复

任务详情改为调用 `format_cron_expression()`；seconds 为非默认值时输出六字段表达式。调度注册路径未改动。

## 5. 防护测试

- `tests/test_cron_schedule_display.py` 新增 `*/10` 和显式秒值测试。
- 调度展示、下次执行计算与执行详情集成回归共 23 项通过。
- Ruff 与 86 条路由冒烟测试通过。

## 6. 同类排查

已检查任务详情和执行详情的调度展示调用方。任务表单已包含 seconds 字段；本次未改变输入校验、调度注册、下一次触发计算或数据库结构。

## 7. 预防方案

页面展示调度规则统一调用 `format_cron_expression()`，禁止业务视图直接调用 `effective_crontab_5()`。固定保留 seconds 页面样本测试；验证命令为 `.venv-py311/bin/python -m unittest tests.test_cron_schedule_display tests.test_dashboard_next_run tests.test_job_log_detail_integration -v`。

[Markdown](2026-09-task-detail-seconds-display.md) · [复盘索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
