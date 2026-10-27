# 发布治理语义门禁与 Release Notes 收口设计（2026-10）

> HTML 版：[发布治理语义门禁与Release-Notes收口设计-2026-10.html](发布治理语义门禁与Release-Notes收口设计-2026-10.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 发布治理语义门禁与 Release Notes 收口设计

编号：Release Governance 2026-10 · 状态：已确认并实施 · 适用版本：后续发布版本，不回写已发布 tag 的历史事实。

**推荐决策：**修正 4.1.1 Release Notes 中已过期的历史 blocker 文案；将版本一致性检查接入 tag 发布工作流；新增已发布版本的语义一致性门禁；在发布前增加远端 Release 资产与工作流结果核验。四项分批实施，每批可独立验证。

## 1. 问题

当前版本结构事实已闭环：`v4.1.0`、`v4.1.1` tag 存在，README、路线图、Release Notes 与版本一致性脚本对齐。但 4.1.1 节仍保留面向旧时点的“发布 4.1.0 前完成 MySQL 演练”表述。现有版本脚本主要检查版本是否存在，不检查已发布章节的状态语义；版本工作流也未在 tag 发布路径直接调用该脚本。

## 2. 根因

- 发布说明同时承担历史决策记录和当前部署指引，缺少“已完成事实/当前阻断/历史说明”的机器可判定边界。
- 版本一致性门禁触发于 main/PR 的文档变更路径，而 tag 发布工作流独立运行，存在门禁链路断开。
- 结构完整性（章节存在、tag 存在）与语义准确性（不能把旧 blocker 留在已发布版本）被视为同一层检查。

## 3. 方案

| 措施 | 设计决策 | 不做什么 |
| --- | --- | --- |
| A · 修正文案 | 将 4.1.1 的旧 blocker 改成已完成的 MySQL 演练事实，或移入 4.1.0 历史节；不改变 tag、代码和资产。 | 不重写历史版本日期和 tag 指向。 |
| B · Tag 工作流接入结构门禁 | 在 `.github/workflows/release-asset.yml` 的 tagged checkout 后执行 `check_version_consistency.py --check`；失败则不构建或发布资产。 | 不以本地工作树状态代替 tagged commit 验证。 |
| C · 增加语义门禁 | 在 `scripts/check_version_consistency.py` 增加已发布章节语义检查：禁止引用更早已发布版本的“before publishing” blocker；复杂自然语言不做全面 NLP，只做明确、可审计的模式与版本比较。 | 不把所有 Release Notes 文案交给脆弱的关键词扫描；不阻止正常的历史迁移说明。 |
| D · 远端发布核验 | 保留现有工作流的双构建、资产校验、启动验证和资产存在性断言；补充发布后核验记录，确认 workflow 成功、Release 非 draft、3 个资产存在且 Release notes 取自目标版本节。 | 不在本地伪造 GitHub 状态；无法访问远端时只标记为未核验。 |

## 4. 范围

**包含：**`RELEASE_NOTES.md`、对应 HTML/Markdown 同步、`scripts/check_version_consistency.py`、其测试、`.github/workflows/release-asset.yml`、必要的文档索引和验收记录。

**不包含：**业务代码、数据库迁移、tag 重建、删除 GitHub Release、修改已发布资产、依赖升级和发布流程之外的安全策略。

## 5. 分批实施

1. **批次 A：文案收口。**修正 4.1.1 说明，生成 HTML/Markdown，运行文档同步与链接门禁。
2. **批次 B：语义门禁。**先写失败测试，再实现旧 blocker 识别和版本比较；验证正常历史说明不误报。
3. **批次 C：Tag 工作流。**在 tagged checkout 上接入结构与语义门禁，验证失败时不会生成/上传资产。
4. **批次 D：发布验收。**执行版本检查、全量相关测试、发布包双构建/验包；若有远端权限，再核对 GitHub Actions 与 Release 状态并记录证据。

## 6. 验收标准

- `.venv-py311/bin/python scripts/check_version_consistency.py --check` 通过。
- 新增语义门禁测试覆盖：旧版本 blocker 被拒绝、已完成事实通过、正常历史说明通过、无版本号文案不误报。
- `.github/workflows/release-asset.yml` 在 tag checkout 后执行门禁；模拟失败时 job 在资产构建前退出。
- `.venv-py311/bin/python scripts/html_docs_to_markdown.py --check`、`check_doc_completeness.py --check`、`check_doc_links.py --check` 全部通过。
- 发布资产仍满足双构建字节一致、包内容校验、解压启动黄金路径和 Release 资产完整性。

## 7. 风险与回滚

- 自然语言门禁可能误报：只允许明确版本化 blocker 模式，并为历史说明提供反例测试。
- Tag 工作流新增门禁可能阻断已有发布：先在 pull request/main 门禁验证，再接入 tag；失败时只阻断新发布，不修改历史 tag。
- 远端状态需要 GitHub 权限：无权限时保留本地可复现证据，并明确“远端未核验”，不伪造通过。

## 8. 待确认事项

用户已确认按 A→B→C→D 四批实施。本轮已完成 A/B/C，并执行 D 批次本地验收；远端 GitHub Actions/Release 状态未在本地伪造为已核验。

## 9. 实施记录与结果

- A：根目录 `RELEASE_NOTES.md` 的 4.1.1 MySQL blocker 已改为完成事实。
- B：`check_published_release_note_semantics()` 已加入 `scripts/check_version_consistency.py`，并新增 4 项回归测试。
- C：`release-asset.yml` 在 tagged checkout 后、资产构建前执行版本一致性门禁。
- D：版本、文档、链接、语义测试、Ruff 与差异检查通过；远端发布结果需在实际 tag workflow 中确认。
[文档索引](../index.html) · [Markdown](发布治理语义门禁与Release-Notes收口设计-2026-10.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
