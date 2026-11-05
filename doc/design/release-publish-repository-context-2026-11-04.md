# GitHub 自动发布修复与 v4.2.0 附件恢复设计

> HTML 版：[release-publish-repository-context-2026-11-04.html](release-publish-repository-context-2026-11-04.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# GitHub 自动发布修复与 v4.2.0 附件恢复设计

rev.2 · 2026-11-05 · 用户要求恢复 GitHub 自动打包上传；用户已明确确认 rev.2；本地实现与验证完成，远端部署/恢复尚未执行。[附件 Before/After（无截图）](#page-compare)

## 版本记录

rev.2：补已发布 v4.2.0 的安全恢复入口、默认分支新工作流与旧标签源提交分离、已存在附件保护及远端验收。rev.1 的一行 GH\_REPO 修复只解决新工作流的仓库定位，不能单独补齐当前已发布 Release。

rev.1（2026-11-04，历史）：定位仓库上下文缺失；当时用户选择手动发布并延期。本轮“赶紧修复”已表明希望恢复自动化，替代继续依赖本地打包的交付方向；实施仍遵守仓库设计确认门禁。

## 交付契约

对象：GitHub 标签→只读构建/验证→Release 三个安装附件。调用者：正常标签推送；一次性恢复通过默认分支 workflow\_dispatch。认证：现有 GITHUB\_TOKEN，构建 contents:read，publish contents:write，release 环境审批保留。标签选择仅允许已存在的严格 vX.Y.Z，不从附件正文决定仓库或版本；输入经 env 传递并校验，不直接拼进 shell 源码。版本、源 SHA、构建报告与远端 tag 绑定；401/403/网络错误拒绝，不假装 Release 不存在。远端验收以公开 Release 资产及下载字节为准，不以本地文件或 Actions artifact 上传成功代替。

## 1. 问题与目标

公开运行 41952060019：build-validate 成功，publish 在 Create or refresh draft Release and upload assets 失败。v4.2.0 Release 已发布，公开 API 观测 assets=[]、immutable=false；本地相同源 SHA 的生产包为 0.71 MiB，而平台 Source code 是完整审计快照。目标是 GitHub 自行构建、校验、附加安装包，不让用户安装 gh、在本地打包或搬运文件。

目标产物仅 cronpilot-4.2.0.tar.gz、同名 .sha256 和 .build.json；平台自动 Source code 保留完整仓库。不改图片保留策略、打包白名单、已修复的运行时原字节保护或既有 v4.2.0 标签。

## 2. 根因与两项恢复障碍

1. publish 在新 runner 不 checkout，gh 步骤只有 GH\_TOKEN，没有 GH\_REPO/--repo。令牌提供认证而非仓库定位。061f73f 拆 job 后遗漏仓库上下文；现有测试只检查发布顺序字符串。
2. 已发布 Release 被现有代码无条件拒绝，单加 GH\_REPO 后仍不会给当前 v4.2.0 补附件；且默认分支修复后直接重跑旧 run 仍使用原事件的 SHA/ref，不能假定自动采用新 workflow。
3. 手动恢复从默认分支启动时，GITHUB\_SHA 是工作流所在提交，不再等于所构建旧标签的提交；必须把预期产物源 SHA 与工作流提交分开。

## 3. 推荐方案

1. **仓库上下文：**给实际调用 gh 的 publish 步骤添加 GH\_REPO: ${{ github.repository }}；令牌权限及 release 环境保持。publish 不 checkout、不执行从构建包带来的脚本。
2. **未来版本：**保留 push semver 标签触发；GitHub 上执行现有双构建、图片排除、安装验证、产物检查；默认仍先草稿、验证远端三个附件及说明后再发布。
3. **当前 v4.2.0 恢复：**增加 workflow\_dispatch，输入 release\_tag 及默认 false 的 repair\_published。工作流从默认分支采用修复后的编排，构建内容明确 checkout 已存在目标标签。只读构建阶段解析并输出实际标签源 SHA；publish 验证报告 source\_commit 和上传边界再次解析的远端标签都等于该源 SHA，不再误用默认分支 GITHUB\_SHA。
4. **已发布附件保护：**仅 workflow\_dispatch 且显式 repair\_published=true 才进入补传。保留既有标题、正文、发布日期和标签；只补缺失的三个固定命名附件。上传前检查已有同名附件：字节相同则保留，冲突则拒绝，禁止 --clobber 已发布资产。重复执行全部相同时返回成功；缺失恢复后再次下载比对、校验和与 source\_commit 检查。immutable 或权限不允许时明确阻断，不删除/重建 Release、不重打标签、不降低保护。
5. **失败与并发：**同仓库同目标标签的发布串行化，不取消进行中的写操作。Release 不存在与查询失败分开：可用成功的完整 API 列表/查询结果判定存在性；认证、限流或网络失败停止，不能把任意 view 非零当 404 后创建。正常模式继续拒绝改动已发布版本。

备选：仅添加 GH\_REPO 适合未来新标签，但不足以恢复当前 Release；在 publish 重新 checkout 会引入不必要的源码执行面；修改/重打 v4.2.0 标签违反产物来源约束；继续本地打包上传违背本轮自动化目标。因此采用上述受控恢复方案。

### 附件对比（无截图）

#### BEFORE · v4.2.0 Release

- Source code (zip)
- Source code (tar.gz)

精简安装附件缺失；用户误下载约 40 MB 完整源码。

#### AFTER · v4.2.0 Release

- cronpilot-4.2.0.tar.gz（约 0.71 MiB）
- cronpilot-4.2.0.tar.gz.sha256
- cronpilot-4.2.0.tar.gz.build.json
- Source code (zip)
- Source code (tar.gz)

GitHub 自动生成并附加三项安装资产；保留原 Release 元信息。

## 4. 范围与授权边界

.github/workflows/release-asset.yml、tests/test\_release\_asset.py 的 workflow 契约/提取 shell 执行测试，必要时独立 tests/test\_release\_publish\_workflow.py，以及设计、复盘、验收和 Release Notes。无产品页面、数据库、API 或运行时依赖变更。不改包内容边界，不重建已有标签。保留所有 pin、只读构建、最小写权限、环境审批及下载比对。所有 gh 只在 GitHub runner 运行，用户本机不需要 gh。

确认设计后先完成代码、模拟测试与提交。推送默认分支、触发恢复、修改公开 Release 属于远端发布动作，在提供实际 diff/目标 Release 后按会话授权执行；不把设计稿本身当成已修复或远端已成功。若现有审批需要人工，保留该要求，不绕过。

## 5. 分批

1. R0：确认 rev.2，冻结目标 tag 源提交；保留工作区并行架构文档改动。
2. R1：GH\_REPO 与作用域测试先红后绿；加入受控 dispatch 和标签源 SHA 传递；测试旧式 GITHUB\_SHA 用法会被拒绝。
3. R2：对提取出的真实 publish shell 用假 gh/API 响应执行，不写真实 Release；覆盖创建/草稿/已发布拒绝/显式恢复/重复/冲突/网络失败及标签漂移。
4. R3：YAML 与 shell 语法、发布专项/版本测试、Ruff 与文档门禁、七项复盘、定向提交。无需重跑与 CI 编排无关的数据库、浏览器或全量业务套件。
5. R4：经远端操作授权部署到默认分支，在 GitHub 对原 v4.2.0 标签执行恢复；实际构建/安装/上传成功后，独立读取 Release API、下载校验三个资产，记录链接和体积。验收不依赖用户本地打包。

## 6. 验收

- 作用域否定：移除 GH\_REPO、仅在注释/其他 job 配置、硬编码仓库都应失败；保留只读构建和无 checkout 的写 job。
- 流程：标签 push 自动打包；dispatch 无效标签在执行仓库脚本前拒绝；构建源 SHA 与工作流 SHA 不同时仍正确验证目标 tag 源；标签漂移、报告版本/SHA 错误一律拒绝。
- 真实 shell 假 gh：无 Release→草稿→上传/下载/发布；已发布且修复 flag 关闭→零写入；开启且缺三个文件→仅补传三个附件、不 edit 正文或草稿状态；已有相同文件→保留；冲突、API 失败、immutability→不覆盖；重复运行无重复有效变更。
- .venv-py311/bin/python -m unittest tests.test\_release\_asset tests.test\_version\_consistency -v，加新增 workflow 测试；对 YAML 结构和提取 shell 执行 bash -n。文档 HTML/MD、登记、链接、术语、diff 门禁通过。
- 远端：build-validate、publish 均成功，公开 API 出现固定三个附件；真实 tag 源提交仍 dd4a9a2，build.json.source\_commit 相同；tar 中无历史截图，运行时字节完整；远端下载与该次 GitHub 构建产物一致。以同一次 ref 两次构建比较，不要求 SHA 引用与 tag 引用的文档 URL 导致的整包哈希相同。

## 7. 风险与回滚

主要风险是手动恢复误用默认分支源码、将 GITHUB\_SHA 当标签源、允许覆盖已发布资产或错误查询被当作不存在。以显式模式、已存在严格标签、源 SHA 双校验、只补缺、冲突拒绝及失败注入覆盖。工作流逻辑改动限于发布编排，运行时代码不变。若恢复失败，保留失败记录与已有资产，不自动回滚发布或移动标签；可修复后再次受控恢复。

## 实施与七项复盘 · 2026-11-05

1. **Bug 定位：**构建成功但 publish 无仓库上下文；公开 v4.2.0 无三个安装附件。实际 runner 原始日志未下载，不把静态定位伪称日志结论。
2. **根因：**拆分最小权限 job 时保留了认证、遗漏仓库定位；恢复路径仍假定 Release 未发布、事件 SHA 就是目标源码 SHA，未对已发布旧标签建模。
3. **测试漏洞：**原测试只查找创建/发布字符串顺序，没有执行特权 shell，也没有覆盖无 checkout 的仓库上下文、dispatch 源提交差异、查询失败与已发布资产冲突。
4. **修复：**实际 gh 步骤显式 GH\_REPO；严格标签在 checkout 前验证，构建绑定目标标签并输出源 SHA；publish 通过 API 解引用普通/附注标签并在写入前及验收时复查。新增默认关闭的手动恢复；仅补缺失资产，已有相同字节跳过，冲突先拒绝；保留 Release 元信息、Action SHA pin、只读构建和 release 环境。API 查询失败停止，同标签写入串行化。
5. **防护测试：**新 tests/test\_release\_publish\_workflow.py 提取真实发布 shell，以有状态假 gh 执行创建草稿、刷新草稿、显式恢复、幂等、部分存在、冲突、API 查询失败、不可变版本、源/版本错误、附注标签、写边界标签漂移和下载损坏路径。普通事件不得修复已发布版本；GITHUB\_SHA 故意与目标源不同。额外验证缺 GH\_REPO、注释伪配置、其他 job 配置、硬编码仓库及注入型输入。旧包测试继续覆盖字节保护。
6. **同类排查：**rg 检查 .github/workflows 下所有 gh release / GH\_REPO / GITHUB\_SHA；发布命令集中在此步骤，未发现另一条遗漏上下文的发布路径。新写 job 无 checkout/仓库脚本执行；所有原 Action pin 与权限边界保持。
7. **预防方案：**新增可执行发布边界测试，随现有 Unit tests 的 tests/test\_\*.py discover 自动运行；第三方可执行 `python -m unittest tests.test_release_publish_workflow -v`（需 bash、jq、sha256sum；macOS 可由 shasum 适配）。用实际 shell 的有状态执行代替仅验证字符串存在；不需要网络、令牌或写公开 Release。

## 本地验收记录

- `PATH=/private/tmp/cronpilot-release-bin:$PATH .venv-py311/bin/python -m unittest tests.test_release_publish_workflow tests.test_release_asset tests.test_version_consistency -v`：36 tests，0 failures，0 skipped，17.860 秒；临时 PATH 仅提供官方 jq 1.7.1 和 macOS shasum 适配，不进入产品依赖。
- `/private/tmp/cronpilot-actionlint/actionlint -shellcheck= .github/workflows/release-asset.yml`：通过；Actionlint 1.7.7 验证工作流结构与表达式，未声称执行 ShellCheck。独立 PyYAML 解析通过；全部 11 个 inline run 块经 `bash -n` 通过。
- `.venv-py311/bin/ruff check app/ tests/test_release_publish_workflow.py tests/test_release_asset.py`：0 违规。
- 文档同步、登记、链接、版本、术语门禁通过。复盘完整性脚本 exit 0，仍报告 53 条历史引用警告；本次复盘已有 Release Notes 引用。开发数据库表清单完整；本轮测试不导入 manage、不连接业务库。

## 远端恢复待执行

本地测试不等于公开 Release 已修复。待提供实际提交/diff并获得远端执行授权后，推送默认分支，以 release\_tag=v4.2.0、repair\_published=true 触发新工作流。正常的新 tag 仍自动构建发布，不依赖本地 gh 或本地包。原标签源必须仍为 dd4a9a2bcfc63cfa87686d006b97e00c77618bae；等待 GitHub 安装验证及上传成功，独立核验公开附件与校验和。若遇环境审批保留人工审批。禁止重打标签、覆盖已发布资产或修改原正文。

## 依据

[GitHub CLI GH\_TOKEN/GH\_REPO 职责](https://cli.github.com/manual/gh_help_environment) · [重跑保留原 SHA/ref](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs) · [默认分支 workflow\_dispatch](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow) · [实际附件与运行记录](../qa/evidence/release-runtime-template-fix-2026-11-04/github-assets-2026-11-05.json)

[Markdown](release-publish-repository-context-2026-11-04.md) · [文档索引](../index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
