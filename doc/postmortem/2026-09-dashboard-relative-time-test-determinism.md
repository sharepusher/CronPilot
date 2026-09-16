# Dashboard 相对时间测试确定性修复复盘

> HTML 版：[2026-09-dashboard-relative-time-test-determinism.html](2026-09-dashboard-relative-time-test-determinism.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# Dashboard 相对时间测试确定性修复复盘

日期：2026-09-16 · 状态：已修复并验证

## 1. Bug 定位

`test_hour_only_next_not_under_one_minute` 使用固定时间编写断言，但被测方法内部使用真实当前时间，导致测试结果受执行日期影响。

## 2. 根因

相对时间计算依赖系统时钟，服务方法没有提供测试可注入的时间基准；测试又同时假设了固定时间和生产默认行为。

## 3. 测试漏洞

测试只在单一环境运行，未检查固定输入时间是否真正传入计算路径，因此时间依赖问题长期未被识别。

## 4. 修复

`DashboardService.compute_next_runs()` 增加可选 `now` 参数。生产调用不传参，仍使用当前时间；测试显式传入固定时间，未改变生产语义。

## 5. 防护测试

Dashboard 下次执行相关 6 项测试全部通过；同时完成 Ruff 和差异空白检查。

## 6. 同类排查

检查了下次执行、逾期计算和调度表达式测试。只有该测试将固定时间与真实时钟混用，其他路径已显式传入或合理使用当前时间。

## 7. 预防方案

所有依赖当前时间的可测试服务方法必须允许注入时间基准；新增时间相关测试必须固定输入时间并验证结果，不得只依赖执行时钟。验证命令：`.venv-py311/bin/python -m unittest tests.test_dashboard_next_run -v`。

[文档索引](index.html) · [Markdown](2026-09-dashboard-relative-time-test-determinism.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
