# UI 重设计 — 逐页对比核实计划

> HTML 版：[UI重设计-逐页对比核实计划.html](UI重设计-逐页对比核实计划.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# UI 重设计 — 逐页对比核实计划

本文档定义了逐页、逐项对比核实的系统方法论，确保实现与 Mockup（`doc/design/console-style-demo.html`）严格对齐。

**权威源**：`doc/design/console-style-demo.html`（以下简称 Mockup）

**实现目录**：`app/templates/redesign/`（26 个模板）

**执行原则**：

1. 逐页、逐区域、逐项对比，不跳过任何可视元素
2. 每项标记为 ✅ 一致 / ❌ 不一致 / 🟡 增强（已确认）/ ⬜ Mockup 无定义
3. 不一致项必须给出 Mockup 原始值 vs 实现值的具体差异
4. 所有修复在用户确认后分步执行

## 执行顺序

按 Mockup 中明确定义的 4 个页面优先，之后是扩展页面：

| 序号 | 页面 | Mockup 区域 | 实现模板 | 状态 |
| --- | --- | --- | --- | --- |
| P1 | 任务中心（Dashboard） | `#console-cron_list` | `dashboard.html` | 待核实 |
| P2 | 新建定时任务（Task Form） | `#console-cron_add` | `task_form.html` | 待核实 |
| P3 | 执行记录（Execution Logs） | `#console-job_log` | `execution_logs.html` | 待核实 |
| P4 | 用户管理（Users） | `#console-users` | `users.html` | 待核实 |
| P5-P26 | 扩展页面 | 无 Mockup（按已确认模式推演） | 其余 22 个模板 | 待核实 |

## P1：任务中心（Dashboard）对比维度

### 1.1 页面头部（Page Header）

| 检查项 | Mockup 值 | 实现值 | 状态 |
| --- | --- | --- | --- |
| 标题文案 | `任务中心` |  |  |
| 统计行格式 | `{N} 个任务 · {N} 连续失败 · {N} 今日告警` |  |  |
| 统计行位置 | 标题右侧（flex space-between） |  |  |
| 连续失败颜色 | `var(--danger-fill)` |  |  |
| 今日告警颜色 | `var(--warn)` |  |  |

### 1.2 过滤栏（Filters）

| 检查项 | Mockup 值 | 实现值 | 状态 |
| --- | --- | --- | --- |
| 布局 | 单行 flex，`gap` 间隔 |  |  |
| 异常分组标签 | `异常`（f-label） |  |  |
| 异常分组按钮 | 连续失败 / 今日失败 |  |  |
| 状态分组标签 | `状态`（f-label） |  |  |
| 状态分组按钮 | 运行中 / 已暂停 / 全部 |  |  |
| 分隔符 | `f-sep`（1px 竖线） |  |  |
| 业务组选择器 | `select.f-select`，含「全部（可见）」默认项 |  |  |
| 标签选择器 | `select.f-select`，含「全部标签」默认项 |  |  |
| 搜索框 | `input.f-input` placeholder=「任务名模糊匹配」 |  |  |
| 新建按钮 | `btn-c btn-accent` + ＋ SVG 图标 + 「新建任务」 |  |  |
| 新建按钮位置 | 最右侧（f-spacer 推到右端） |  |  |

### 1.3 表格结构（Table）

| 检查项 | Mockup 值 | 实现值 | 状态 |
| --- | --- | --- | --- |
| 表格容器 | `.c-table-wrap.no-top` |  |  |
| 表格 class | `c-table` |  |  |
| 列数 | 6 列 |  |  |
| 列头文案 | 任务 / 调度策略 / 运行与发布 / 健康 / 状态 / 操作 |  |  |
| 列宽比例 | 36% / 14% / 18% / 7% / 9% / 16% |  |  |

### 1.4 表格行内容格式

| 检查项 | Mockup 值 | 实现值 | 状态 |
| --- | --- | --- | --- |
| 任务列 — 健康点 | `c-dot` 圆点 + 颜色表示健康 |  |  |
| 任务列 — 作用域标签 | `c-scope`（GLOBAL / 组名） |  |  |
| 任务列 — 任务名 | `c-task-name`（font-weight:600） |  |  |
| 任务列 — 标签 | `c-tag` |  |  |
| 任务列 — URL | `c-task-url`（mono 字体显示完整 URL） |  |  |
| 调度策略列 — 人性化描述 | `c-sched-human`（如「每 5 分钟」） |  |  |
| 调度策略列 — cron 表达式 | `c-sched-expr`（mono 字体） |  |  |
| 运行与发布列 — RUN 时间 | `c-audit mono`：`RUN {time}` |  |  |
| 运行与发布列 — BY 创建者 | `c-audit`：`BY {name} · {date}` |  |  |
| 健康列 | `c-dot` 圆点（ok/fail/warn/none） |  |  |
| 状态列 | `c-status` + 圆点 + 文案（运行中/已暂停/已下线） |  |  |
| 操作列 — 按钮样式 | `btn-c btn-line btn-xs`（文字按钮） |  |  |
| 操作列 — 按钮列表 | 运行中：记录 / 执行 / ···（暂停/编辑/下线） |  |  |
| 操作列 — 已暂停 | 记录 / ···（启动/编辑/下线） |  |  |
| 操作列 — 已下线 | 仅「记录」 |  |  |
| 已下线行样式 | `opacity:.6` |  |  |

### 1.5 翻页（Pagination）

| 检查项 | Mockup 值 | 实现值 | 状态 |
| --- | --- | --- | --- |
| 容器 class | `c-foot` |  |  |
| 左侧计数格式 | `{N} total` |  |  |
| 翻页按钮 | ‹ / 数字 / … / 数字 / › |  |  |
| 当前页样式 | `.active` |  |  |

### 1.6 Mockup B 增强（已确认）

| 增强项 | 来源 | 状态 |
| --- | --- | --- |
| 4 格统计卡片 | 用户确认加入 |  |
| 异常面板 | 用户确认加入 |  |
| 7 列表格 | 用户确认表格结构调整 |  |
| 图标操作按钮 | 用户确认替代文字按钮 |  |

## P2：新建定时任务（Task Form）对比维度

### 2.1 页面头部

| 检查项 | Mockup 值 | 实现值 | 状态 |
| --- | --- | --- | --- |
| 标题 | `新建定时任务` |  |  |

### 2.2 表单字段

| 检查项 | Mockup 值 | 实现值 | 状态 |
| --- | --- | --- | --- |
| 字段 1 — 任务名称 | label=「任务名称 \*」, placeholder=「例如：订单状态同步」, hint=「必填，不可重复」 |  |  |
| 字段 2 — 任务说明 | label=「任务说明 \*」, placeholder=「简要描述任务的用途和目的」, hint=「必填，1～500 字；可写需求链接、用途等」 |  |  |
| 字段 3 — 可见范围 | label=「可见范围 \*」, inline 双 select（「指定业务组/全局共享」+「组列表」）, hint=「默认归属业务组；仅必要时选全局共享」 |  |  |
| 字段 4 — 任务标签 | label=「任务标签」, tag 容器样式（带 c-tag + input）, hint=「可选；建议输入国家/业务线/服务名等」 |  |  |
| 字段 5 — 定时方式 | label=「定时方式 \*」, select（定时模式/具体时间）, hint=「定时模式按周期触发，具体时间仅执行一次」 |  |  |
| 字段 6 — Cron 表达式 | label=「Cron 表达式」, 5 格网格（日/星期几/小时/分钟/秒）, 预览行 |  |  |
| 字段 7 — 触发 URL | label=「触发 URL \*」, inline（method select + url input）, hint 含协议说明 |  |  |
| 字段 8 — 超时（秒） | label=「超时（秒）」, type=number, placeholder=「5」, width=100px, hint=「留空使用默认 5s；有效范围 1–120」 |  |  |
| 操作按钮 | 「添加」(btn-accent) + 「返回」(btn-line) |  |  |

## P3：执行记录（Execution Logs）对比维度

### 3.1 页面头部

| 检查项 | Mockup 值 | 实现值 | 状态 |
| --- | --- | --- | --- |
| 标题 | `执行记录` |  |  |
| 副标题 | `默认展示「非成功」，避免秒级成功日志淹没异常` |  |  |

### 3.2 过滤栏

| 检查项 | Mockup 值 | 实现值 | 状态 |
| --- | --- | --- | --- |
| 结果分组标签 | `结果`（f-label） |  |  |
| 结果按钮 | 非成功(active) / 全部 / 仅失败 / 仅异常 / 仅成功 |  |  |
| 分隔符 | `f-sep` |  |  |
| 任务名称输入 | `f-input` placeholder=「任务名称」 |  |  |
| 时间范围 | 开始时间 — 结束时间（两个 f-input） |  |  |
| 搜索按钮 | `btn-c btn-accent btn-xs`「搜索」 |  |  |
| 重置按钮 | `btn-c btn-line btn-xs`「重置」 |  |  |

### 3.3 表格结构

| 检查项 | Mockup 值 | 实现值 | 状态 |
| --- | --- | --- | --- |
| 列数 | 7 列 |  |  |
| 列头文案 | LOG ID / 任务名称 / 返回内容 / 执行时间 / 耗时 / 结果 / 操作 |  |  |
| 列宽比例 | 8% / 20% / 30% / 16% / 10% / 8% / 8% |  |  |
| LOG ID 样式 | `mono font-size:11px` |  |  |
| 任务名称样式 | `font-weight:600` |  |  |
| 返回内容样式 | `<code> font-size:11px`，失败时 `color:var(--danger-fill)` |  |  |
| 结果 badge | `log-result log-fail/log-timeout/log-unknown` + c-dot + 文案 |  |  |
| 操作按钮 | 「详情」`btn-c btn-line btn-xs` |  |  |

### 3.4 翻页

| 检查项 | Mockup 值 | 实现值 | 状态 |
| --- | --- | --- | --- |
| 计数格式 | `{N} total (non-success)` |  |  |

## P4：用户管理（Users）对比维度

### 4.1 页面头部

| 检查项 | Mockup 值 | 实现值 | 状态 |
| --- | --- | --- | --- |
| 标题 | `用户管理` |  |  |

### 4.2 工具栏

| 检查项 | Mockup 值 | 实现值 | 状态 |
| --- | --- | --- | --- |
| 添加按钮 | `btn-c btn-accent btn-xs`「+ 添加用户」 |  |  |
| 搜索框 | `f-input` placeholder=「按用户名搜索…」width=160px |  |  |
| 搜索按钮 | `btn-c btn-line btn-xs`「搜索」 |  |  |
| 说明文案 | `color:var(--muted);font-size:12px`「无物理删除；停用/启用须填写缘由。新建用户默认密码 changeme。」 |  |  |

### 4.3 表格结构

| 检查项 | Mockup 值 | 实现值 | 状态 |
| --- | --- | --- | --- |
| 列数 | 10 列 |  |  |
| 列头文案 | ID / 用户名 / 花名 / 岗位 / 角色 / 状态 / 密码 / 业务组 / 创建时间 / 操作 |  |  |
| 操作列宽度 | `width:220px` |  |  |
| 当前用户标记 | `当前` badge（accent-dim + accent 颜色） |  |  |
| 角色 badge | `u-role u-role-admin/operator/viewer` |  |  |
| 状态 badge | `u-badge u-active/u-inactive` |  |  |
| 密码 badge | `u-badge`（正常/待重置） |  |  |
| 停用用户行样式 | `opacity:.6` |  |  |
| 停用用户操作 | 仅「查看」按钮 |  |  |
| 当前用户操作 | 「修改密码」+ 说明文案「账号/角色不可自改」 |  |  |
| 普通用户操作 | 重置密码 / 重置Token / 停用 / 编辑 |  |  |
| 停用按钮样式 | `btn-c btn-danger-c btn-xs` |  |  |

## 逐页核实方法（每页执行步骤）

1. **读 Mockup 源**：用 Read 工具读取 `console-style-demo.html` 中对应 page-view 区域的完整 HTML
2. **读实现源**：用 Read 工具读取 `app/templates/redesign/xxx.html` 完整内容
3. **逐项对比**：按上方表格逐项填写「实现值」和「状态」
4. **浏览器截图**：restart 后打开浏览器截图对比
5. **输出结果**：标记 ✅/❌/🟡/⬜ 并列出所有 ❌ 项的修复建议
6. **用户确认**：等用户确认后执行修复

## 核实进度跟踪

| 页面 | 检查项数 | ✅ 一致 | ❌ 不一致 | 🟡 已确认增强 | ⬜ 无定义 | 进度 |
| --- | --- | --- | --- | --- | --- | --- |
| P1 Dashboard | — | — | — | — | — | 待执行 |
| P2 Task Form | — | — | — | — | — | 待执行 |
| P3 Execution Logs | — | — | — | — | — | 待执行 |
| P4 Users | — | — | — | — | — | 待执行 |
| P5-P26 扩展页面 | — | — | — | — | — | 待执行 |

[文档索引](../index.html) · [Markdown](UI重设计-逐页对比核实计划.md) · [索引](../index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
