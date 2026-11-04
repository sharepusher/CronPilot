# 发布 job 仓库上下文缺失分析与修复设计

> HTML 版：[release-publish-repository-context-2026-11-04.html](release-publish-repository-context-2026-11-04.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

2026-11-04 用户决策：继续手动发布，自动发布仓库上下文问题暂不处理，不列为本次发布阻断；原技术发现保留为历史记录。

# 发布 job 仓库上下文缺失分析与修复设计

rev.1 · 2026-11-04 · 待用户 Review 确认。本轮仅评估，没有修改工作流或测试实现。

## 1. 问题及触发条件

工作流 `.github/workflows/release-asset.yml` 的 publish job 使用独立 ubuntu-latest runner，只下载经构建验证的 dist 产物。执行 Release 命令的步骤只配置 GH\_TOKEN，没有 GH\_REPO，也未传 --repo；publish 中没有 checkout。GitHub CLI 身份凭据只能提供认证，不能提供目标仓库。下载产物也不会恢复 .git 上下文。

当合法版本标签通过 build-validate 并进入 release 环境批准后的 publish 阶段时，命令需要定位仓库却无定位来源：首条 view 的错误被 if 分支当作“Release 不存在”，随后 create 同样缺少仓库上下文而失败。结果是发布 job 失败；前序已验证产物不因此丢失，不能据此认定曾发生错误仓库发布或凭据泄露。

这是当前工作流定义在常规 GitHub-hosted runner 上的静态确认；本机未安装 gh，也未运行 GitHub Actions 发布。已有其他门禁可能更早失败，因此不声称远端已经执行到该错误。

## 2. 根因与测试漏洞

提交 061f73f 将原单一构建发布 job 拆为只读 build-validate 与有写权限 publish。拆分前 gh 命令与 checkout 同属一个 job，可以发现本地 Git remote；拆分后仅传递产物，未显式传递仓库身份。认证上下文与仓库上下文是两项独立输入。

`tests/test_release_asset.py::test_workflow_creates_draft_before_publishing` 检查命令顺序、固定 Action、草稿及远端资产验证字符串，未检查执行 gh 命令的 job 是否能获得目标仓库，也未验证其环境变量作用域。构建器和产物单测通过不能验证这个发布编排条件。

## 3. 推荐方案与备选

在现有“Create or refresh draft Release and upload assets”步骤的 env 中添加一行，所有 gh release 命令在该步骤内共享该上下文：

```
env:
  GH_TOKEN: ${{ github.token }}
  GH_REPO: ${{ github.repository }}
```

从事件所属仓库派生 OWNER/REPO，适用于仓库迁移或 fork；不硬编码 sharepusher/CronPilot，不以发行包内容、用户输入或 Release 正文作为仓库选择依据。步骤级作用域足以覆盖当前所有 gh 命令；以后若拆到新步骤，新的命令步骤也必须明确获得仓库上下文。

- **每条命令添加 --repo：**语义成立，但当前多个命令需重复配置，容易漏掉下载、状态读取或最终 publish，优先采用步骤级 GH\_REPO。
- **publish 中重新 checkout：**可提供 remote，但为仓库定位重新引入源码没有必要，不作为本次方案。
- **放到 job 级 env：**也可行；当前只有一个步骤使用 gh，步骤级配置范围更明确。

本次不改造将 view 的所有错误视为“未找到”的分支。401、403 或网络错误后 create 仍会失败，但诊断可能不直观；如后续需要准确区分 404 与基础设施故障，应单独设计，不将其混入一行仓库上下文修复。

## 4. 范围与兼容性

预计改动工作流上述 env、发布契约防护测试及复盘文档。GitHub token 权限、release 环境审批、标签校验、草稿流程、资产下载比对、哈希/commit 检查均保持现有语义。无应用页面、数据库或 API 变化，无需页面 Before/After。添加 GH\_REPO 不赋予新增权限；它使已有授权明确指向当前事件仓库。

## 5. 实施分批

1. R0：确认工作流仍与本设计相符，记录 HEAD 和工作区现有差异，保留此前图片治理的未提交修改。
2. R1：添加步骤级 GH\_REPO，检查所有 gh 命令在同一作用域；增加针对 publish job 的契约测试，禁止仅在整个 YAML 中查找 GH\_REPO 字符串。
3. R2：验证、否定校准、复盘及文档同步，记录本地验证与远端发布的边界，形成可提交结果。

## 6. 验收及防护

- 精确定位 publish job 中执行 gh release 的步骤，确认 GH\_REPO 等于受信任的 github.repository 表达式，且没有被该步骤的 shell 覆盖；不能用其他 job 或注释中的同名字符串充数。
- 确认构建 job 保持只读，publish 保持 release 环境及 contents: write，且仍不 checkout 或执行仓库脚本；所有现有远端资产校验仍先于最终发布。
- 对“移除 GH\_REPO”“变量只出现在 build job/注释”“仓库硬编码”做否定校准，检查测试能拒绝这些状态。静态契约测试是防遗漏工具，不宣称替代真实 gh 或 GitHub-hosted 执行。
- 执行 `.venv-py311/bin/python -m unittest tests.test_release_asset tests.test_version_consistency -v` 及新增契约测试；对 YAML 和提取 shell 做语法核验，运行文档登记、链接、术语、HTML/Markdown 同步及 diff 检查。无需运行数据库或调度服务。
- 如实施时本地可获得 gh，可在无 .git 的临时目录用显式 GH\_REPO 做只读已发布版本查询，验证仓库定位；不得创建或更新真实 Release。凭据和网络不可用时记录未执行，不伪报实际 CLI 验证。
- 实际 tag 发布仍受所有既有门禁和环境批准约束。本次不为测试创建 tag 或发布 Release，也不把后续业务阻断标记为已关闭。

## 7. 风险及回滚

代码改动小，主要风险是 env 放错作用域、未来 gh 命令拆分后丢失上下文或测试只检查文本存在。以作用域测试和否定校准防止重现。回退该行会恢复原发布故障，需暂停发布并保留诊断；不能通过移除审批、放宽权限或跳过资产验证恢复发布。尚未排查的远端环境配置和权限错误仍可能使后续发布失败。

## 8. 本轮核验与实施后复盘要求

已读取当前工作流、现有发布测试及 061f73f 的父版本，确认旧 job 有 checkout、新 publish job 无仓库上下文；已核对官方 CLI 文档。本轮未修改实现，未执行远端命令。实施后应记录定位、job 拆分根因、测试漏洞、修复、防护测试、同类 gh 命令作用域排查，以及新增契约测试的路径和可复现命令，形成七项复盘。

## 依据

- [GitHub CLI environment：GH\_TOKEN 与 GH\_REPO 的独立职责](https://cli.github.com/manual/gh_help_environment)
- [GitHub CLI 官方仓库：GITHUB\_REPOSITORY 支持讨论及显式 GH\_REPO 用法](https://github.com/cli/cli/issues/3556)
- [本轮提交复审](../qa/post-v4.1.1-commit-review-2026-11-04.html)
[Markdown](release-publish-repository-context-2026-11-04.md) · [索引](../index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
