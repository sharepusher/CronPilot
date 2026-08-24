# Redesign Mockup 对比核实 — 交接文档

## 权威 Mockup 源

**唯一权威文件**：`doc/design/CronPilot-2026-redesign-mockup.html`（2525 行）

**⚠️ 已废弃文件**：`doc/design/console-style-demo.html` — 早期 PoC，不再作为实施依据。

## Mockup 页面索引

| # | view ID | 行号范围 | 对应模板 |
|---|---|---|---|
| 1 | `view-dashboard` | L481–L652 | `app/templates/redesign/dashboard.html` |
| 2 | `view-detail` | L657–L740 | `app/templates/redesign/task_detail.html` |
| 3 | `view-run-inspector` | L741–L820 | `app/templates/redesign/run_inspector.html` |
| 4 | `view-run-failed` | L821–L877 | 无独立模板（可能合并到 run_inspector） |
| 5 | `view-logs` | L878–L937 | `app/templates/redesign/execution_logs.html` |
| 6 | `view-users` | L938–L1010 | `app/templates/redesign/users.html` |
| 7 | `view-groups` | L1011–L1124 | `app/templates/redesign/groups.html` |
| 8 | `view-audit` | L1125–L1181 | `app/templates/redesign/audit_logs.html` |
| 9 | `view-tags` | L1182–L1269 | `app/templates/redesign/tags.html` |
| 10 | `view-form` | L1270–L1380 | `app/templates/redesign/task_form.html`（编辑模式） |
| 11 | `view-optlog` | L1381–L1473 | `app/templates/redesign/operation_log.html` |
| 12 | `view-password` | L1474–L1517 | `app/templates/redesign/change_password.html` |
| 13 | `view-api-token` | L1518–L1564 | `app/templates/redesign/api_token.html` |
| 14 | `view-apidoc` | L1565–L1664 | `app/templates/redesign/api_doc.html` |
| 15 | `view-reg-review` | L1665–L1734 | `app/templates/redesign/registration_review.html` |
| 16 | `view-user-add` | L1735–L1819 | `app/templates/redesign/user_form.html`（新建模式） |
| 17 | `view-user-edit` | L1820–L1893 | `app/templates/redesign/user_form.html`（编辑模式） |
| 18 | `view-group-add` | L1894–L1924 | `app/templates/redesign/group_form.html` |
| 19 | `view-task-add` | L1925–L2014 | `app/templates/redesign/task_form.html`（新建模式） |
| 20 | standalone login | L2196–L2226 | `app/templates/redesign/login.html` |
| 21 | standalone register | L2227–L2525 | `app/templates/redesign/register.html` |
| 22 | standalone forgot_password | L2175–L2195 | `app/templates/redesign/forgot_password.html` |

## P1 Dashboard 已识别偏差（15 项）

### 页面头部（2 项）
| # | Mockup | 实现 |
|---|---|---|
| 1 | 副标题 `系统运行状态总览与任务运营` | 改为动态 stat-line |
| 2 | 新建按钮在 page-head 右侧 | 放在过滤栏最右 |

### 过滤栏（5 项）
| # | Mockup | 实现 |
|---|---|---|
| 3 | 搜索框最左侧 | 中间位置 |
| 4 | chip 按钮带计数（全部128/异常3/运行中6/暂停12/已下线4） | 分组式 f-label + f-btn，无计数 |
| 5 | 无分组标签 | 有「异常」「状态」分组标签 + 分隔符 |
| 6 | 业务组/标签为 chip 形式（`业务组 ▾`） | select 下拉框 |
| 7 | 搜索 placeholder=`搜索任务名称…` | `任务名模糊匹配` |

### 表格（2 项）
| # | Mockup | 实现 |
|---|---|---|
| 8 | 操作列 `width:90px` | `width:12%` |
| 9 | 调度策略列: cron表达式在上 + 人性化在下 | 人性化在上 + 表达式在下 |

### 操作按钮（4 项）
| # | Mockup | 实现 |
|---|---|---|
| 10 | 暂停按钮直接暴露为独立 icon | 在 dropdown 中 |
| 11 | 无「记录」独立 icon 按钮 | 有记录按钮 |
| 12 | 运行中: 立即执行 + 暂停 + 更多 | 立即执行 + 记录 + 更多(暂停/编辑/下线) |
| 13 | 已下线: 恢复 + 更多 | 仅记录 |

### 翻页（2 项）
| # | Mockup | 实现 |
|---|---|---|
| 14 | `显示 1-5 / 共 128 个任务` | `{N} total` |
| 15 | 表格外独立 pagination div | 表格内 hf-pagination |

## P2-P22 状态

尚未执行逐项对比。基于 P1 的偏差程度，预计其他页面也存在类似问题。

## 执行方法论（供下一轮使用）

对每个页面：
1. `Read` Mockup 文件对应行号范围的完整 HTML
2. `Read` 实现模板完整内容
3. 逐区域对比：页面头部 → 工具栏/过滤栏 → 表格/表单结构 → 行内容 → 操作按钮 → 翻页 → 空状态
4. 每项标记 ✅/❌ 并记录 Mockup 原值 vs 实现值
5. 输出偏差表后等用户确认再修改

## 当前服务状态

- 本地服务运行在 `http://127.0.0.1:5001/`（PID 48200）
- v2 入口: `CRONPILOT_FORCE_NEW_UI=true` 已配置
- 登录: admin / changeme

## 相关规范文件

- `.cursor/rules/cronpilot-project.mdc` — 「Redesign Mockup 逐节对照」规范
- `AGENTS.md` — 所有强制规范汇总
- `doc/design/UI重设计-逐页对比核实计划.html` — 本轮创建的核实计划文档
- `doc/design/redesign-全程错误记录.html` — **本 Agent 对话全程 11 项错误的完整复盘记录**
