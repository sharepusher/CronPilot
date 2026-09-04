# CronPilot UI重设计 — 第五轮 Mockup 对比评估

> HTML 版：[UI重设计-第五轮Mockup对比评估.html](UI重设计-第五轮Mockup对比评估.html) · [文档索引](../../index.html) · [索引 Markdown](../../index.md)

# CronPilot UI重设计 — 第五轮 Mockup 对比评估

评估日期：2026-08-20 · 对标：`CronPilot-2026-full-mockup.html`

## 综合评分

已对齐页面

6

Task Center / Users / Groups / Tags / API Doc / Profile

待优化页面

2

Operation Log (Z1) · Audit Log (Z2)

本轮已修复

2

cron\_add 错误重定向 · registration\_review Bootstrap 弹窗

全局模态系统

✓

CpModal 全局化，Bootstrap 0 残留

## ✅ 本轮已修复 Bug

**BUG-1 修复cron\_add 任务新建错误时立即跳转**

修复前

后端异常时返回 `web_api_return(code=1, ..., url='/cron_list')`  
js-ajax-form 无条件读取 url → 立即跳转 /cron\_list  
用户表单数据全部丢失，无法得知错误原因

修复后

异常返回 `web_api_return(code=1, msg=str(e))`（无 url）  
js-ajax-form 的 tips\_success span 显示错误消息  
用户留在表单页，可查看错误并修改后重试

**BUG-2 修复registration\_review Bootstrap modal 透明显示**

修复前

点击"通过"/"拒绝"触发 Bootstrap `modal('show')`  
redesign CSS 改变了 stacking context → 弹窗透明或不可见  
同时导入了 `bootstrap.min.css/js`（样式污染）

修复后

迁移至 `CpModal()`（现已全局可用）  
"通过"：CpModal HTML body 显示 username + 停用警告  
"拒绝"：CpModal 含 textarea 输入  
Bootstrap 完全移除，redesign templates 0 残留

**架构改进CpModal 全局化**  
`CpModal()` 从 tags.html 内联定义 → `redesign-confirm.js` 全局注册（`window.CpModal`），所有 redesign 页面无需重复定义。tags.html 同步更新（移除本地复制，更新按钮选择器）。

## 页面对比分析

### 任务中心 (view-dashboard)

Mockup 规格

- 4 stat cards：任务总数 · 运行中 · 今日失败 · 24h成功率
- 简单 chip 筛选：全部 · 运行中 · 异常 · 已下线
- 表格 4 列：任务(名称+meta+tags) · 调度策略 · 运行状态 · 操作(2个icon按钮)
- 页头右侧"新建任务"按钮

当前实现

- 差异 4 stat cards：异常任务 · 连续失败 · 运行中 · 今日失败次数（名称与mockup不同）
- 一致 chip 筛选：异常 · 连续失败 · 今日失败 · 状态筛选 · 全部
- 扩展 表格 7 列（含健康度/下次执行/业务组），比 mockup 更详细
- 差异 有 Exception Panel（mockup 无，但为功能增强）
- 缺失 页头无"新建任务"快捷按钮（有权限者通过侧边栏导航）

📝 评估：当前实现为有意义的功能增强（Exception Panel、健康度、下次执行均是业务价值），统计指标名称差异可接受。新建任务按钮已通过侧边栏导航覆盖。整体对齐度：**基本符合 + 合理扩展**

### 执行记录 (view-logs)

Mockup 规格

- 筛选：搜索框 + chip（全部 · 失败 · 超时）
- 表格 5 列：任务 · 触发时间 · 耗时 · 响应码 · 状态

当前实现

- 一致 chip 筛选：非成功 · 全部 · 仅失败 · 仅异常 · 仅成功 + 任务名/时间范围
- 一致 表格结构与 mockup 基本对齐（任务/触发时间/耗时/响应码/状态）

📝 评估：**高度一致**，无需修改

### 操作记录 (view-optlog) Z1 待修复

Mockup 规格（5 列）

- 操作人
- 操作（彩色 badge：修改/下线/新建）
- 对象（仅显示任务名）
- 时间
- 来源 IP

**无 ID 列，无内容详情**

当前实现（7 列）

- 多余 ID 列
- 用户（操作人）
- 类型（= 操作 badge）
- 过多 内容（显示完整 diff/参数，信息量过大）
- IP
- 时间

**Z1 计划修复**：移除 ID 列；"内容"列改为只显示任务名（缩短为"对象"列）；表格从 7 列简化为 5 列。*文件：*`app/templates/redesign/operation_log.html`

### 用户管理 (view-users)

Mockup 规格（5 列）

- 用户（avatar + 姓名 + email 副标题）
- 角色（badge）
- 状态（pin dot）
- 最近登录
- 操作（单个 edit icon button）

当前实现（8 列）

- 一致 用户名（avatar 首字母 + 用户名）
- 花名 · 岗位（mockup 无）
- 一致 角色（badge）
- 一致 状态
- 密码状态（mockup 无）
- 业务组（mockup 无）
- 创建时间（vs mockup 的"最近登录"）
- 差异 操作：文字链接（编辑/重置密码/重置Token/停用）vs mockup 单 icon 按钮

📝 评估：当前实现信息量更丰富（花名/岗位/业务组是业务需要），多列可接受。操作按钮多于 mockup 但功能上正确。关键差异：mockup 只有"最近登录"而当前显示"创建时间"（可考虑替换）。整体对齐度：**信息层面合理扩展**

### 业务组 (view-groups)

Mockup 规格

- 卡片网格，每卡片：组名 · 描述 · avatar stack（张/李/+3）· 任务数 badge

当前实现

- 基本一致 卡片网格：组名 · 描述 · "N 名成员" · N 个任务
- 说明 avatar stack → "N 名成员"文字（用户明确指定，非偏离）

📝 评估：用户在此前明确要求用数字代替 avatar stack，属于经确认的设计决策，不视为偏离。整体对齐度：**用户确认变体**

### 审计日志 (view-audit) Z2 待修复

Mockup 规格（5 列 + chip 筛选）

- chip 筛选：全部 · 登录失败 · 权限变更
- 事件（操作类型）
- 用户
- 时间
- IP
- 结果（badge：成功/失败×5）

**无 ID，无目标类型，无详情**

当前实现（8 列 + 复杂搜索）

- 差异 搜索栏（用户名/动作选择/结果/日期范围）vs mockup 3 个 chip
- 多余 ID 列
- 操作人
- 操作（事件）
- 多余 目标类型
- 多余 目标名
- 多余 详情
- IP
- 时间

**Z2 计划修复**：移除 ID/目标类型/详情 3 列；简化为 5 列；搜索栏改为 mockup 的 3 chip 风格（全部 · 登录失败 · 权限变更）。*文件：*`app/templates/redesign/audit_logs.html`

### 标签管理 (view-tags)

Mockup 规格

- 新建标签搜索框（trigger）
- 标签云（大号 pill，显示 count + × 删除）
- 无管理表格

当前实现

- 一致 标签云 pill（count + × 删除）
- 扩展 额外管理表格（标签名/使用数/业务组/关联任务/操作）
- 扩展 新建标签 CpModal 系统（功能完整）

📝 评估：管理表格是功能增强，提供了 mockup 没有的标签详细管理能力，属合理扩展。整体对齐度：**满足 + 合理扩展**

## 行动计划（按优先级）

| 编号 | 优先级 | 描述 | 涉及文件 | 状态 |
| --- | --- | --- | --- | --- |
| BUG-1 | 高 | cron\_add 异常时 url 字段导致表单重定向 | `app/main/views.py` | ✓ 已修复 |
| BUG-2 | 高 | registration\_review Bootstrap modal 透明 | `registration_review.html` | ✓ 已修复 |
| Z1 | 高 | 操作记录：移除 ID 列，简化"内容"为任务名（"对象"） | `redesign/operation_log.html` | 待实现 |
| Z2 | 高 | 审计日志：移除 ID/目标类型/详情 3 列，改 chip 筛选 | `redesign/audit_logs.html` | 待实现 |
| CpModal 全局化 | 架构 | CpModal 提取为 window.CpModal，tags.html 使用全局版本 | `redesign-confirm.js`, `tags.html` | ✓ 已完成 |

## 确认弹窗系统统一验证（本轮新增）

| 页面 | 弹窗 | 方案 | 状态 |
| --- | --- | --- | --- |
| API Token | 重置 Token 确认 | `CpConfirm.show()` | ✓ |
| 用户管理 | 重置密码 / 重置 Token / 停用确认 | `CpConfirm.show()` | ✓ |
| 标签管理 | 新建/重命名/关联任务/删除 | `CpModal()` + `CpConfirm.show()` | ✓ |
| 注册审批 | 批准/拒绝 | `CpModal()` 全局版 | ✓ 本轮修复 |
| Bootstrap 残留检测 | `grep -r ".modal('show')\|bootstrap.min" app/templates/redesign/` | | 0 结果 ✓ |

## 本轮验收信息

| 步骤 | 命令/路径 | 期望结果 |
| --- | --- | --- |
| 服务状态 | `lsof -nP -iTCP:5001 -sTCP:LISTEN` | PID 62683 在监听 |
| 侧边栏回归 | `.venv-py311/bin/python -m unittest tests.test_redesign_sidebar -v` | 12 tests OK |
| 表单守卫 | `.venv-py311/bin/python -m unittest tests.test_ajax_form_guard -v` | 4 tests OK |
| Bootstrap 清零 | `grep -r ".modal('show')\|bootstrap.min" app/templates/redesign/` | exit 1（无匹配 = OK） |
| HTML/MD 同步 | `.venv-py311/bin/python scripts/html_docs_to_markdown.py --check` | OK: all matched |
| 任务中心 | `http://127.0.0.1:5001/` | 页面正常加载，Exception Panel 显示 |
| 标签管理 | 点击"+ 新建标签" | CpModal 正确弹出（已验证截图） |
| 注册审批 | 有待审批记录时点击"通过" | CpModal 弹出（Bootstrap 已移除） |

[文档索引](../../index.html) · [Markdown](UI重设计-第五轮Mockup对比评估.md) · [索引](../../index.html)

---

[← 文档索引（HTML）](../../index.html) · [← 文档索引（Markdown）](../../index.md)
