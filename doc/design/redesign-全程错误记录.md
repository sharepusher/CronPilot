# Agent 对话全程错误记录与复盘

> HTML 版：[redesign-全程错误记录.html](redesign-全程错误记录.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# Agent 对话全程错误记录与复盘汇总

对话 ID: `a47e4f24-32f2-41f0-a42c-2fb11056a413`  
时间跨度: 2026-08（多轮）  
涉及范围: UI Redesign 全过程（色系设计 → Mockup → 分批实现 → 对比核实）

## 错误清单总览

| # | 严重度 | 事件 | 用户原话 | 已有复盘文档 |
| --- | --- | --- | --- | --- |
| 1 | Critical | Phase 2 首次实现严重偏离 Mockup（缺 Exception Panel、7列降5列、icon变文字） | 「做的乱七八糟，和 mockup 差别很大」 | ✅ `doc/postmortem/2026-08-Phase2-Mockup偏离复盘.html` |
| 2 | Critical | 修复后未主动复盘（反复违反，≥3次） | 「为什么出现这么大的纰漏却没有复盘！规范是用来吃的吗！」「为什么又没有主动复盘，这多第几次了」 | ✅ `doc/postmortem/2026-08-元复盘-复盘失效机制.html` |
| 3 | Critical | 统一执行手册从记忆写入数值，导致 15 处偏差 | 「为什么总是凭记忆，你规范做的形同虚设，可以继续相信你吗」 | ✅ `doc/postmortem/2026-08-统一手册数值重复偏离.html` |
| 4 | Critical | 最终对比仍引用错误 Mockup 文件（console-style-demo.html 而非 CronPilot-2026-redesign-mockup.html） | 「你脑子是不是有问题，早就没有 console-style-demo.html，新的重构都是基于 redesign」 | ❌ **本文档新增** |
| 5 | High | 超时默认值被错误改为 10s（应为 5s），且未发现 | 「真是瞎搞，又把超时改成了 10s」 | ❌ **本文档新增** |
| 6 | High | Mockup 中「添加用户」被错误实现为「邀请用户」 | 「用户管理里添加用户不叫做邀请，邀请一般会发邮件」 | ❌ **本文档新增** |
| 7 | High | Dashboard 实现与 Mockup 存在 15 项结构性不一致 | 「还是有很多地方和 redesign mockup 文档不一致」 | ❌ **本文档新增** |
| 8 | Medium | 复盘文档化未执行（只在对话中写复盘，未落库） | 「复盘有写入文档吗，有遵守规范吗」 | ✅ 在元复盘中记录 |
| 9 | Medium | 用户管理列表缺少「岗位」列 | 「用户管理里少了岗位，请再次全面梳理确认」 | ❌ **本文档新增** |
| 10 | Medium | Mockup 对比后的修复引入未授权增强（如侧边栏底部用户信息） | 「redesign 的 mockup 哪里有什么底部用户信息，瞎搞」 | ❌ **本文档新增** |
| 11 | Medium | 多个页面缺少权限描述可读性问题（cron:read 等不可读） | 「页面有些地方描述权限使用 cron:read, cron:write 这种完全不可读的描述」 | ❌ 已在 Mockup 修正中处理 |

## 错误 #4 复盘：引用错误 Mockup 文件

### Bug 定位

在执行「逐页对比核实」时，Agent 读取了 `doc/design/console-style-demo.html`（早期 PoC），而正确的权威 Mockup 是 `doc/design/CronPilot-2026-redesign-mockup.html`。

### 根因

1. **仓库中存在两份类似文件**：早期 PoC (`console-style-demo.html`) 和正式 Mockup (`CronPilot-2026-redesign-mockup.html`) 同时存在于 `doc/design/`，且两者文件名都不含明确的「SUPERSEDED」或「AUTHORITATIVE」标记
2. **对话摘要中残留了旧文件引用**：conversation summary 中多处提及 `console-style-demo.html`，Agent 在恢复上下文时优先匹配了旧引用
3. **无程序化的权威源校验**：没有任何脚本或配置文件声明「redesign 的唯一 Mockup 源」，完全依赖 Agent 记忆判断

### 测试漏洞

无测试会验证 Agent 读取的 Mockup 文件路径是否正确。这是一个「操作流程」问题而非代码逻辑问题。

### 修复

已在 `doc/design/redesign-handover.md` 中明确标注唯一权威 Mockup 源，并标注 `console-style-demo.html` 为已废弃。

### 防护测试

建议在 `console-style-demo.html` 文件头部加入 SUPERSEDED 注释。

### 同类排查

还有 3 份实施方案文档被标注为 superseded：`UI重设计-详细实施与验收计划v2.html`、`UI重设计-视觉设计规格书.html`、`UI重设计-逐页设计规格书.html`。它们的首行已含 superseded 标记。

### 预防方案

| 措施 | 落地位置 |
| --- | --- |
| 在 `console-style-demo.html` 首行加入 `<!-- SUPERSEDED: 本文件已被 CronPilot-2026-redesign-mockup.html 取代 -->` | `doc/design/console-style-demo.html` L1 |
| 在每个 redesign 模板头部注释标注对应的 Mockup view ID 和行号 | `app/templates/redesign/*.html` |
| 交接文档 `redesign-handover.md` 中已明确标注唯一权威源 | `doc/design/redesign-handover.md` |

## 错误 #5 复盘：超时默认值被错误修改

### Bug 定位

Mockup 文案审核时，Agent 将超时默认值从 5s 改为 10s，违背了项目已有设定。

### 根因

Agent 在「全面对比所有文案」时，根据主观判断认为 10s 更合理，未 `grep` 代码确认 `_DEFAULT_TIMEOUT_SEC = 5` 是项目既定值。

### 测试漏洞

无测试验证 Mockup 文案中的数值与代码中的默认值一致。

### 修复

已回退为 5s。

### 防护测试

可在 `check_ui_contract.py` 中新增断言：Mockup 中超时相关文案引用的数值与 `crons.py` 中 `_DEFAULT_TIMEOUT_SEC` 一致。

### 同类排查

其他默认值（如 MAX\_FAILURES\_PER\_IP=5、密码最小长度等）未发现类似篡改。

### 预防方案

| 措施 | 落地位置 |
| --- | --- |
| Mockup 中所有引用后端默认值的文案，必须 `grep` 确认源码值后再写入 | `.cursor/rules/cronpilot-project.mdc` 「Redesign Mockup 逐节对照」 |
| 规范「禁止主观修改已有默认值，除非用户明确要求」已在项目规范中 | `AGENTS.md` |

## 错误 #6 复盘：「添加用户」错误实现为「邀请用户」

### Bug 定位

用户管理页面的「添加用户」按钮被 Agent 自行改为「邀请用户」。

### 根因

Agent 根据「行业惯例」自行判断应用「邀请」语义，未遵循 Mockup 原始文案 `+ 添加用户`。

### 修复

已回退为「+ 添加用户」。

### 预防方案

| 措施 | 落地位置 |
| --- | --- |
| 「禁止主观修改 Mockup 已定义的文案」已在规范中追加 | `.cursor/rules/cronpilot-project.mdc` |
| Mockup 中的按钮/标签文案属于产品决策，Agent 不得基于「行业惯例」自行更改 | 同上 |

## 错误 #7 复盘：Dashboard 15 项结构性不一致

### Bug 定位

`app/templates/redesign/dashboard.html` 与 Mockup `#view-dashboard` 在过滤栏（5项）、操作按钮（4项）、页面头部（2项）、翻页（2项）、表格（2项）存在结构性偏差。

### 根因

1. **实现时引用了错误的 Mockup 文件**（console-style-demo.html 而非 CronPilot-2026-redesign-mockup.html）
2. **多轮迭代中 Mockup 源发生迁移**但实现代码从未回溯对齐新 Mockup
3. **规范「逐节对照」虽已写入但缺乏程序化强制**，被绕过
4. **验收环节只验证功能正确性**（数据显示正确）而非结构对齐

### 修复

尚未执行。已在 `doc/design/redesign-handover.md` 中完整列出 15 项偏差的 Mockup 值 vs 实现值，供后续修复。

### 预防方案

| 措施 | 落地位置 |
| --- | --- |
| 每个模板文件头部注释标注 Mockup view ID + 行号范围 | `app/templates/redesign/*.html` |
| 新建 `scripts/check_mockup_alignment.py` 自动 curl 渲染页面并验证关键 class 存在性 | `scripts/check_mockup_alignment.py` |
| 规范已升级：在 `.cursor/rules/cronpilot-project.mdc` 中加入「Redesign Mockup 逐节对照」强制清单 | 已完成 |

## 错误 #9 复盘：用户管理列表缺少「岗位」列

### Bug 定位

Mockup 中用户管理表格有 10 列（含「岗位」），实现时遗漏了该列。

### 根因

实现时未逐列对照 Mockup 表格 `<thead>`，凭记忆判断列数。

### 修复

已补充「岗位」列。

### 预防方案

同错误 #7 的预防方案。

## 错误 #10 复盘：引入未授权增强（侧边栏底部用户信息）

### Bug 定位

Agent 在 Mockup 对比后自行添加了「侧边栏底部用户信息」组件，Mockup 中并无此元素。

### 根因

Agent 将「行业常见的侧边栏底部用户信息」视为「缺失项」而非「不需要的项」，主观添加了 Mockup 未定义的组件。

### 修复

已移除。

### 预防方案

| 措施 | 落地位置 |
| --- | --- |
| 规范追加：「Mockup 中未出现的元素视为不需要，不得自行添加。任何新增必须用户明确确认」 | `.cursor/rules/cronpilot-project.mdc` |

## 系统性根因分析

**核心失败模式**：Agent 在整个 Redesign 过程中反复出现「凭印象/记忆行事」而非「严格读取源文件后行事」的行为模式。具体表现为：

1. **Mockup 源不对**：引用旧 Mockup 而非新 Mockup
2. **数值不对**：从记忆写入数值而非 Read 源文件复制
3. **文案不对**：基于主观判断修改产品文案
4. **结构不对**：凭印象简化表格列数/按钮样式
5. **增删不对**：自行添加 Mockup 未定义的组件

**根本原因**：Agent 将 Mockup 视为「参考」而非「规格书」，允许自己在实现过程中做「优化判断」。正确认知应该是：**Mockup 是权威规格，实现必须逐像素对齐，任何偏离必须用户明确授权。**

**规范失效原因**：纯文字规范被证明无法防止行为偏离（至少 3 次违反后才升级为程序化 Hook）。Hook 能防止复盘缺失，但无法防止「用错 Mockup 文件」这类认知层错误。

## 已落地的预防措施清单

| # | 措施 | 落地位置 | 验证方式 |
| --- | --- | --- | --- |
| 1 | L1 postToolUse Hook（每次编辑后注入复盘提醒） | `.cursor/hooks.json` | 编辑后自动触发 |
| 2 | L2 stop prompt Hook（结束前评估复盘完整性） | `.cursor/hooks/stop-postmortem-gate.sh` | 自动触发 |
| 3 | L5 CI 复盘文档检查 | `scripts/check_postmortem_completeness.py` | `python scripts/check_postmortem_completeness.py --check` |
| 4 | Redesign Mockup 逐节对照规范 | `.cursor/rules/cronpilot-project.mdc` | 人工遵守（无程序化强制） |
| 5 | 禁止整合文档复制源文档数值 | `.cursor/rules/cronpilot-project.mdc` + `AGENTS.md` | 人工遵守 |
| 6 | 文档链接 CI 检查 | `scripts/check_doc_links.py --check` | CI 自动 |
| 7 | 颜色硬编码审计 | `scripts/audit_hardcoded_colors.py --check` | CI 自动 |
| 8 | 交接文档标注唯一权威 Mockup 源 | `doc/design/redesign-handover.md` | 文档内容 |

## 仍缺失的预防措施

| # | 措施 | 建议落地位置 | 状态 |
| --- | --- | --- | --- |
| 1 | 程序化 Mockup 结构对齐验证（curl + grep 关键 class） | `scripts/check_mockup_alignment.py` | 未创建 |
| 2 | 每个模板文件头部标注 Mockup view ID + 行号 | `app/templates/redesign/*.html` | 未执行 |
| 3 | `console-style-demo.html` 首行加 SUPERSEDED 标记 | `doc/design/console-style-demo.html` | 未执行 |
| 4 | Mockup 文案中引用的默认值自动与代码比对 | `scripts/check_ui_contract.py` | 未创建 |

[文档索引](../index.html) · [Markdown](redesign-全程错误记录.md) · [索引](../index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
