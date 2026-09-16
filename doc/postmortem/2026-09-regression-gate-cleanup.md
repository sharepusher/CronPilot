# 全量回归门禁收口修复复盘

> HTML 版：[2026-09-regression-gate-cleanup.html](2026-09-regression-gate-cleanup.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 全量回归门禁收口修复复盘

日期：2026-09-16 · 状态：已修复并验证

## 1. Bug 定位

全量回归发现 Presenter 中的 URL 对象属性访问触发 ORM legacy 静态门禁；Redis 锁未获取分支在无 Flask 应用上下文的测试中访问 `current_app` 并抛出异常。

## 2. 根因

静态门禁采用了对 `.query` 的保守匹配，新增代码未避开该约束；锁竞争日志使用了请求上下文相关 logger，未遵循基础设施代码可脱离 Flask context 的边界。

## 3. 测试漏洞

首次专项测试未运行完整 ORM legacy 门禁，锁竞争测试也未覆盖无应用上下文场景。

## 4. 修复

URL 解析改用位置字段读取原始 query；锁竞争日志改用模块级 logger。两项修复均不改变业务逻辑或安全策略。

## 5. 防护测试

ORM legacy、锁、Presenter 相关 16 项测试全部通过；全量测试重新执行后仅保留既有测试环境噪声，无本次相关失败。

## 6. 同类排查

已检查 Presenter、执行观测服务、锁装饰器及相关静态门禁；未发现其他 `current_app` 越界或同类 `.query` 触发点。

## 7. 预防方案

涉及静态门禁的新增代码必须在专项测试之外执行对应门禁；基础设施和装饰器日志默认使用模块级 logger，只有确实需要请求上下文时才使用 `current_app`。验证命令：`.venv-py311/bin/python -m unittest tests.test_orm_legacy_guard tests.test_single_task_lock tests.test_run_inspector_presenter -v`。

[文档索引](index.html) · [Markdown](2026-09-regression-gate-cleanup.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
