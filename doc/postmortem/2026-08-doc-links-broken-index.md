# 复盘 — 文档链接 140 处 broken（index.html 缺失）

> HTML 版：[2026-08-doc-links-broken-index.html](2026-08-doc-links-broken-index.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 复盘 — 文档链接 140 处 broken（index.html 缺失 + Mockup 文件名错误）

**日期**：2026-08-26  |  **严重程度**：Low（仅影响文档导航，不影响功能）

## 1. Bug 定位

`python scripts/check_doc_links.py --check` 报告 140 个 broken 链接：

- 138 处：`doc/design/*.html` 和 `doc/postmortem/*.html` 中 footer 的 `<a href="index.html">` 指向不存在的目录级 `index.html`
- 2 处：`doc/design/UI重设计-groups-tags-方案对比Demo.html` 引用 `CronPilot-2026-full-mockup.html`（实际为 `CronPilot-2026-redesign-mockup.html`）

## 2. 根因

- **index.html 缺失**：`scripts/html_docs_to_markdown.py` 的 `inject_md_footer()` 函数无条件注入 `<a href="index.html">` 作为相对链接。设计假设每个子目录有 index 文件，但 `doc/design/` 和 `doc/postmortem/` 从未创建过。
- **Mockup 文件名错误**：早期设计文档使用外部版文件名 `CronPilot-2026-full-mockup.html`，后来内部规范改为 `CronPilot-2026-redesign-mockup.html`，引用未同步更新。

## 3. 测试漏洞

`check_doc_links.py` 能发现问题但未在 CI 中作为阻断性门禁执行。`html_docs_to_markdown.py` 注入 footer 后未验证链接可达性。

## 4. 修复

- 创建 `doc/design/index.html`、`doc/postmortem/index.html`、`doc/design/screenshots/eval6/index.html`
- 修正 3 处 `CronPilot-2026-full-mockup.html` → `CronPilot-2026-redesign-mockup.html`

## 5. 防护测试

```
python scripts/check_doc_links.py --check
# 期望输出：✓ 文档链接检查通过（扫描 991 个引用，0 broken）。
```

## 6. 同类排查

- `grep -r "full-mockup" doc/` — 确认仅此一个文件引用了错误文件名
- 所有 `doc/` 子目录（design/postmortem/screenshots/eval6）现在都有 `index.html`

## 7. 预防方案

| 措施 | 落地位置 | 验证命令 |
| --- | --- | --- |
| 将 `check_doc_links.py --check` 作为 CI 阻断性门禁 | CI workflow / 本地 `cronpilot.sh test` | `python scripts/check_doc_links.py --check` |
| 嵌套子目录中的 footer 链接使用 `../../index.html` 而非裸 `index.html`（2026-09 追加：`dashboard-table-overflow-demo.html` 同根因修复） |
| 未来新增 `doc/` 子目录时，同步创建 `index.html` | `.cursor/rules/cronpilot-documentation.mdc`（已有相关规范） | `ls doc/*/index.html` |

[文档索引](index.html) · [Markdown](2026-08-doc-links-broken-index.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
