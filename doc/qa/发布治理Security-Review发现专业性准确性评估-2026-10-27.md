# 发布治理 Security Review 发现专业性与准确性评估（2026-10-27）

> HTML 版：[发布治理Security-Review发现专业性准确性评估-2026-10-27.html](发布治理Security-Review发现专业性准确性评估-2026-10-27.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 发布治理 Security Review 发现专业性与准确性评估

日期：2026-10-27 · 对象：当前发布治理工作树变更 · 结论：4 项发现总体专业且可操作；High/Medium 分级基本成立，但第 2、3 项需要补充边界，第 3 项推荐的结构化元数据优于当前字符串门禁。

**总裁决：**Security Review 没有误报为“代码已被攻陷”；它识别的是供应链、tag 输入、发布说明语义和资产完整性边界。第 1 项是实际高风险；第 2、4 项是中等完整性风险；第 3 项准确指出当前门禁的 false-negative 边界，但其建议应从“扩大正则”升级为结构化发布状态。

## 1. 逐项准确性与方案评估

| 原发现 | 准确性 | 方案合理性 | 建议结论 |
| --- | --- | --- | --- |
| 工作流写权限 + checkout 持久化凭据 | **准确，High 合理。**Tagged commit 中的脚本可读取 checkout 写入的 Git 凭据；同一 job 还拥有 `contents: write`。 | **合理且应优先。**`persist-credentials: false`、构建/发布拆 job、发布 job 使用受保护环境和 SHA 固定 Action 能显著降低供应链爆炸半径。 | 保留 High；先做权限拆分和凭据隔离，再考虑 Action SHA 固定。 |
| 宽 tag 触发与 malformed SemVer | **基本准确，Medium 合理。**`v*.*.*` 会触发非数字 tag；版本检查器只收集数字 tag，`extract_release_notes` 允许回退到 `Unreleased`，形成异常版本发布路径。 | **合理但需覆盖完整链路。**应在最早步骤严格校验 `GITHUB_REF_NAME`，并在 tag 发布模式禁止 fallback；仅收紧 workflow glob 不足以形成安全边界。 | 保留 Medium；增加脚本函数级测试和 tag 工作流静态断言。 |
| 英文短语语义门禁可绕过 | **准确，但属于门禁能力边界，不是已证实绕过线上发布的漏洞。**当前正则只识别 `before publishing vX.Y.Z`，不能覆盖同义表述或中文。 | **结构化元数据方向正确。**用 `release_blockers`、`readiness` 等字段验证状态，比继续堆叠自然语言正则可靠；过渡期应限定为“检测已知模式”。 | Medium 可保留；避免对该正则过度声称全面语义安全。 |
| 上传后只校验名称和文案 | **准确，Medium 合理。**上传后未重新取回并校验归档、checksum、build report 与事件 commit 的绑定；名称存在不等于内容完整性。 | **合理且可直接落地。**上传后下载每个资产并校验本地 hash、checksum 文件、build report 的 `source_commit` 与 `GITHUB_SHA`，再解除 draft，是最小闭环。 | 保留 Medium；并为 draft 并发更新增加版本/状态检查。 |

## 2. 方案优先级

1. 先处理第 1 项：将构建 job 改为只读，发布 job 使用最小权限、受保护环境和显式 token。
2. 同时处理第 2 项：严格 SemVer、禁止 tag fallback，并拒绝未预期的 tag 名称进入 shell 路径。
3. 随后处理第 4 项：上传后内容 hash 与来源 commit 双向校验。
4. 最后将第 3 项从短语正则迁移到结构化 release manifest；不应通过无限增加自然语言关键词解决。

## 3. 不应过度解读

- 没有证据证明已有恶意 tag、token 泄露或 Release 被篡改；第 1 项是可利用设计风险。
- 第 2 项描述的是未来输入边界，不因当前 tag 都规范而消失。
- 第 3 项影响语义门禁覆盖范围，不能替代发布权限控制。
- 第 4 项主要补足发布完整性证据；攻击前提是已有仓库/Release 写权限。

## 4. 验证依据

```
nl -ba .github/workflows/release-asset.yml
nl -ba scripts/check_version_consistency.py
nl -ba scripts/extract_release_notes.py
.venv-py311/bin/python scripts/check_version_consistency.py --check
```

本评估只审查安全问题与方案，不修改实现。

[文档索引](../index.html) · [Markdown](发布治理Security-Review发现专业性准确性评估-2026-10-27.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
