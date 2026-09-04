# 复盘：Release Notes Unreleased 残留清理

> HTML 版：[2026-09-release-notes-unreleased-cleanup.html](2026-09-release-notes-unreleased-cleanup.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 复盘：Release Notes Unreleased 残留清理

日期：2026-09-04

## 1. Bug 定位

- `RELEASE_NOTES.md` 的 `[Unreleased]` 节包含 2 个小节和 7 条实质条目，触发 `python3 scripts/check_version_consistency.py --check` 失败。
- `doc/index.html` 首页快捷入口与 Release Notes 卡片仍显示旧版本标识（v2.7.0 等），与当前 README/路线图中的 v4.0.0 不一致。

## 2. 根因

- 发布后未执行「Unreleased 清空」收尾动作，导致已完成内容滞留在草稿区。
- 文档入口页的版本文案依赖手工维护，缺少与根 `RELEASE_NOTES.md` 的自动对齐机制。

## 3. 测试漏洞

- 虽然有 `check_version_consistency.py`，但此前未在本地交付前完整执行到该脚本，导致残留未及时暴露。
- `doc/index.html` 的版本展示文案不在现有一致性脚本覆盖范围内。

## 4. 修复

- 将 `RELEASE_NOTES.md` 的 `[Unreleased]` 收敛为非列表占位说明，移除实质条目与子节。
- 修正 `doc/index.html` 的「进度总览」版本标识为 v4.0.0。
- 修正 `doc/index.html` 的 Release Notes 卡片文案，明确以仓库根 `RELEASE_NOTES.md` 为准。

## 5. 防护测试

- `python3 scripts/check_version_consistency.py --check` 应通过（验证 Unreleased 残留已清理）。
- `python3 scripts/check_doc_completeness.py --check` 应通过（新复盘文档在索引中可达）。
- `python3 scripts/check_doc_links.py --check` 应通过（新增链接无断链）。
- `python3 scripts/html_docs_to_markdown.py --check` 应通过（HTML/Markdown 同步）。

## 6. 同类排查

- 已复核 `doc/_pending_sync/` 守卫，结果为 OK。
- 已复核 OPT 编号一致性，`check_opt_consistency.py --check` 通过。
- 当前未发现新的 broken doc 链接或未注册 HTML 文档。

## 7. 预防方案

1. **交付前文档体检固定化：**每次文档变更后固定执行
   `python3 scripts/check_doc_completeness.py --check && python3 scripts/check_doc_links.py --check && python3 scripts/check_version_consistency.py --check && python3 scripts/check_opt_consistency.py --check && python3 scripts/html_docs_to_markdown.py --check`。
     
   落地位置：交付流程执行清单（本次复盘文档 + 日常交付步骤）。
2. **版本入口去硬编码：**`doc/index.html` 的 Release Notes 描述改为「以仓库根 RELEASE\_NOTES 为准」，避免重复维护一长串版本 badge。
     
   验证命令：`` rg "以仓库根 `RELEASE_NOTES.md` 为准|发行版 v4.0.0" doc/index.html ``。

[文档索引](../index.html) · [Markdown](2026-09-release-notes-unreleased-cleanup.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
