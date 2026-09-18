# ORM legacy 门禁误报修复复盘

> HTML 版：[2026-09-ORM-legacy-urlsplit误报修复.html](2026-09-ORM-legacy-urlsplit误报修复.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# ORM legacy 门禁误报修复复盘

日期：2026-09-18 · 状态：已修复并验证

## 1. Bug 定位

全量回归在 `app/services/execution_tracer.py` 的 `parts.query` 处失败。该属性来自标准库 `urlsplit()` 的返回值，却被 ORM legacy AST 门禁当作 `Model.query`。

## 2. 根因

门禁仅识别了同一表达式中的 `urlsplit(...).query`，没有记录跨语句别名赋值，因此无法区分 URL 解析对象与 ORM 模型对象。

## 3. 测试漏洞

原有回归只覆盖了直接链式写法和 ORM 正例，没有覆盖 `parts = urlsplit(url)` 后再访问 `parts.query` 的常见写法。

## 4. 修复

AST Visitor 记录由 `urlsplit` 赋值产生的名称，并在 `.query` 检查时跳过这些名称；同时保留 `Model.query`、`session.query` 与 `paginate` 的拦截规则。

## 5. 防护测试

```
.venv-py311/bin/python -m unittest tests.test_orm_legacy_guard -v
python3 scripts/check_doc_links.py --check
```

结果：8 条门禁测试通过，文档链接扫描 2123 个引用、0 broken。

## 6. 同类排查

已扫描 `app/` 中所有 `.query` 属性访问；除 URL 解析对象外未发现新的非 ORM 误报，也未放宽真实 ORM legacy 规则。

## 7. 预防方案

将“第三方返回对象属性”列入 AST 门禁的最小语义夹具矩阵：每次新增规则或出现误报时，必须同时提交一个合法非 ORM 正例与一个 ORM 反例，并在 `tests/test_orm_legacy_guard.py` 中运行全量扫描。这样可在 CI 中重现验证，避免用路径白名单掩盖规则缺陷。

[文档索引](../index.html) · [Markdown](2026-09-ORM-legacy-urlsplit误报修复.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
