# Redesign 代码全面 Review 修复方案 — 2026-08

> HTML 版：[Redesign代码全面Review修复方案-2026-08.html](Redesign代码全面Review修复方案-2026-08.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# Redesign 代码全面 Review 修复方案

**文档编号：**OPT-P0-19-REVIEW  
**创建日期：**2026-08-24  
**状态：**待确认  
**触发来源：**Redesign 前端重构后全面代码 Review  
**覆盖范围：**47 项发现，分 5 个 Tier、8 个 Batch

## §1 问题总述

对 CronPilot Redesign（V2 UI）前后端代码进行全面 Review 后，共发现 47 项问题，横跨安全、可访问性、架构、Mockup 对齐和代码质量 5 个维度。无 P0 安全漏洞（前轮已修复），但存在 6 项 P1 安全风险和 8 项 P1 可访问性缺陷需优先处理。

| Tier | 维度 | P0 | P1 | P2 | Low | 合计 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 安全 | 0 | 2 | 3 | 1 | 6 |
| 2 | 可访问性 | 0 | 5 | 3 | 0 | 8 |
| 3 | 架构 / CSS | 0 | 3 | 7 | 0 | 10 |
| 4 | Mockup 偏离 | 2 | 4 | 5 | 0 | 11 |
| 5 | 代码质量 | 0 | 0 | 0 | 12 | 12 |
| **合计** | | **2** | **14** | **18** | **13** | **47** |

## §2 根因分析

### 2.1 安全类根因

- **SEC-1/SEC-2**：`innerHTML` 使用场景未全部配套 `escHtml()`；command palette 的 `href` 属性和 `CpModal` 的 `bodyHtml` 选项虽当前来源受控，但缺乏防御性编码。
- **SEC-3/SEC-4**：异常处理中 `str(e)` 直接进入响应或外部通道，是 Phase A 安全加固遗漏的长尾。
- **SEC-5**：`trigger_password_reset` 将默认密码写入前端消息，信息泄露。
- **SEC-6**：DNS 解析失败时 SSRF 校验 fail-open（放行），留下 TOCTOU 攻击窗口。

### 2.2 可访问性根因

- Redesign 迁移时优先保证视觉还原和功能正确，`<label for>` 关联、ARIA 属性、键盘可达性被系统性遗漏。
- Auth 页面（`login`/`register`/`complete_profile`）独立于 `_base.html`，未引入 `common-redesign.js` 的防重复提交全局守卫。

### 2.3 架构根因

- `redesign-pages.css` 在多轮迭代中持续追加，未按页面拆分；Dashboard 规则未使用 `.cp-page-dashboard` 前缀。
- V1 遗留的 `.btn` 系统与 Mockup 的 `.btn-c` 系统并存，模板混用两者。
- 后端 `views.py` 文件超 1,100 行，合并了路由、表单处理、查询构建、模板上下文组装。

### 2.4 Mockup 偏离根因

- 业务组详情面板和标签命名空间属于 Mockup 中的高级交互模式，在首轮 Redesign 中按 MVP 优先级被简化实现。
- 执行记录、注册审批的列差异来自实际数据模型与 Mockup 设想的不一致，需设计层面决策。

## §3 修复方案

共分 8 个 Batch，按依赖关系和风险排序。每个 Batch 可独立验收。

**Batch 1：安全加固（SEC-1 ~ SEC-6）**

### 3.1.1 SEC-1：Command Palette href 未转义

| 项 | 内容 |
| --- | --- |
| 文件 | `app/static/js/redesign-shell.js` L95-110 |
| 现状 | `renderResults()` 中 `href` 直接拼入 `innerHTML` 字符串，虽当前 href 来自服务端导航、不含用户输入，但违背防御性原则 |
| 方案 | 改用 `document.createElement('a')` + `.setAttribute('href', item.href)` 构建 DOM；`textContent` 设置标签文本 |
| 不做 | 不改变 Command Palette 的功能和视觉 |

### 3.1.2 SEC-2：CpModal bodyHtml XSS 面

| 项 | 内容 |
| --- | --- |
| 文件 | `app/static/js/redesign-confirm.js` L121 |
| 现状 | `opts.bodyHtml` 直接赋值给 `innerHTML`，调用方若传入未转义的用户数据即可 XSS |
| 方案 | 新增 `bodyText` 选项（用 `textContent` 安全插入），当 `bodyHtml` 存在时在 JS 注释中标注「调用方须自行 escHtml」；在所有现有调用点 Review 确认均已转义 |
| 不做 | 不移除 `bodyHtml`（已有 `tags.html` 等合法用例） |

### 3.1.3 SEC-3：cron\_add 异常类名泄露

| 项 | 内容 |
| --- | --- |
| 文件 | `app/main/views.py` L861 |
| 现状 | `'服务器内部错误（%s）' % err_type` 将异常类名（如 `ConnectionError`）返回前端 |
| 方案 | 统一返回 `'服务器内部错误，请稍后重试'`，异常类型仅记录到 `logger.error` |

### 3.1.4 SEC-4：WeChat 原始异常发送

| 项 | 内容 |
| --- | --- |
| 文件 | `app/main/views.py` L852 |
| 现状 | `wechat_info_err(str(e), ...)` 将原始异常文本发至外部通道 |
| 方案 | 改为 `wechat_info_err('任务新增异常', ...)`，不传 `str(e)` |

### 3.1.5 SEC-5：密码重置消息泄露默认密码

| 项 | 内容 |
| --- | --- |
| 文件 | `app/rbac/services.py` |
| 现状 | `trigger_password_reset` 返回 `'默认密码为 changeme'` 写入前端提示 |
| 方案 | 改为 `'密码已重置，请通知该用户使用默认密码登录后立即修改'`，不在前端展示具体密码 |

### 3.1.6 SEC-6：DNS 不可达时 SSRF fail-open

| 项 | 内容 |
| --- | --- |
| 文件 | `app/services/url_security.py` L97-99 |
| 现状 | DNS 解析返回空列表时，`validate_and_resolve_url` 放行请求（fail-open），在执行阶段无 IP 仍可发起不受限连接 |
| 方案 | DNS 解析失败时返回 `(False, 'DNS 解析失败，拒绝执行')`（fail-closed）；配置项 `url_ssrf_dns_fail_open=false` 可选恢复旧行为 |
| 风险 | 部分内网 DNS 短暂不可用时会误拒合法任务；可通过 allowlist 白名单豁免 |

**Batch 1 验收：**  
`bash scripts/cronpilot.sh test` 全量通过 +  
`grep -n "str(e)" app/main/views.py` — 仅出现在 logger 行  
`grep -n "changeme" app/rbac/services.py` — 不出现在 return 值中  
`grep -rn "innerHTML.*href" app/static/js/redesign-shell.js` — 0 hits  
SSRF 测试：`python -m unittest tests.test_p0_phase_a -v`

**Batch 2：可访问性修复（A11Y-1 ~ A11Y-8）**

### 3.2.1 A11Y-1：task\_form.html 标签关联

| 项 | 内容 |
| --- | --- |
| 文件 | `app/templates/redesign/task_form.html` |
| 现状 | 15+ 个 `<label>` 无 `for=` 属性，对应 `<input>`/`<select>` 无 `id` |
| 方案 | 逐字段添加 `id="tf-xxx"` + `for="tf-xxx"` 配对。字段前缀统一为 `tf-` |
| 不做 | 不改变表单布局或视觉样式 |

### 3.2.2 A11Y-2：Dashboard 操作按钮语义

| 项 | 内容 |
| --- | --- |
| 文件 | `app/templates/redesign/_dashboard_rows.html` |
| 现状 | 操作下拉菜单中 `<a onclick="cpToggleStatus(...)">` 无 `href`，键盘不可达 |
| 方案 | 改为 `<button type="button" onclick="cpToggleStatus(...)">` |

### 3.2.3 A11Y-3：Auth 页面防重复提交

| 项 | 内容 |
| --- | --- |
| 文件 | `login.html`、`register.html`、`complete_profile.html` |
| 现状 | 独立页面未引入 `common-redesign.js`，依赖各自 inline 守卫，覆盖度参差 |
| 方案 A（推荐） | 在 3 个 Auth 页面底部引入 `common-redesign.js`（jQuery 已在页面加载），统一使用全局守卫 |
| 方案 B | 保持 inline 守卫，补齐缺失的「恢复」逻辑（3 秒超时恢复按钮可用） |

### 3.2.4 A11Y-4：users.html 停用模态框标签

| 项 | 内容 |
| --- | --- |
| 文件 | `app/templates/redesign/users.html` |
| 现状 | `<label class="dm-label">停用缘由</label>` 未关联 `#dm-reason` textarea |
| 方案 | 添加 `for="dm-reason"` |

### 3.2.5 A11Y-5：注册审批全选复选框

| 项 | 内容 |
| --- | --- |
| 文件 | `app/templates/redesign/registration_review.html` |
| 现状 | `#rr-select-all` 无可见标签或 `aria-label` |
| 方案 | 添加 `aria-label="全选/取消全选"` |

### 3.2.6 A11Y-6：模态框焦点陷阱

| 项 | 内容 |
| --- | --- |
| 文件 | `redesign-shell.js`（Command Palette）、`redesign-confirm.js`（CpConfirm/CpModal） |
| 现状 | 打开模态框后 Tab 键可逃离遮罩层 |
| 方案 | 添加简易焦点陷阱：open 时记录 `lastFocusedElement`，在 overlay 内 Tab 循环首末可聚焦元素，close 时恢复焦点 |

### 3.2.7 A11Y-7：Toast 关闭按钮键盘支持

| 项 | 内容 |
| --- | --- |
| 文件 | `app/static/js/redesign-toast.js` |
| 现状 | 关闭按钮为 `<span role="button">`，无 `tabindex` 和 Enter/Space 处理 |
| 方案 | 改为 `<button type="button" class="toast-close" aria-label="关闭">` |

### 3.2.8 A11Y-8：error.html javascript: href

| 项 | 内容 |
| --- | --- |
| 文件 | `app/templates/redesign/error.html` |
| 现状 | `href="javascript:history.back()"` |
| 方案 | 改为 `<button type="button" onclick="history.back()">返回</button>` |

**Batch 2 验收：**  
`bash scripts/cronpilot.sh test` 全量通过  
`grep -rn 'javascript:' app/templates/redesign/` — 仅 `tags.html`（Batch 5 处理）  
手动键盘 Tab 测试：task\_form → 所有字段可通过 label 点击聚焦  
Command Palette 打开后 Tab 不逃逸模态框

**Batch 3：CSS 架构优化（ARCH-1 ~ ARCH-8）**

### 3.3.1 ARCH-1/ARCH-2：pages.css 拆分 + Dashboard 规则命名空间化

| 项 | 内容 |
| --- | --- |
| 文件 | `app/static/css/redesign-pages.css` |
| 现状 | 2,067 行单文件；Dashboard 区域 ~105 条规则使用 `.tc-*`、`.hf-*`、`.act-btn` 等全局类名 |
| 方案 | 1. 提取 Dashboard 规则到 `redesign-page-dashboard.css`（~400 行），所有规则添加 `.cp-page-dashboard` 前缀 2. 剩余规则保留在 `redesign-pages.css`（~1,600 行），后续按需继续拆分 3. 在 `_base.html` 中新增 `<link>` 引入 dashboard CSS |
| 不做 | 不一次性拆分所有页面（控制变更范围）；不改变视觉效果 |

### 3.3.2 ARCH-3：按钮系统统一

| 项 | 内容 |
| --- | --- |
| 文件 | `redesign-components.css`（`.btn`）、`redesign-mockup-shared.css`（`.btn-c`）、多个模板 |
| 现状 | 两套按钮系统并存，高度/边框/hover 行为不一致；`task_detail.html` 同时使用两者 |
| 方案 | 1. 以 `.btn-c`（Mockup 系统）为主系统，保留 `.btn-c-accent`/`.btn-c-danger` 变体 2. 将 `.btn` 标记为 deprecated，逐步替换模板中的 `.btn` → `.btn-c` 3. 本批次仅处理 `task_detail.html`、`cron_retire.html`、`error.html` 中的混用 |

### 3.3.3 ARCH-4：页面标题系统统一

| 项 | 内容 |
| --- | --- |
| 现状 | `.cp-page-head`（layout.css）仅被 `_welcome.html` 使用；其余所有页面使用 `.page-head`（mockup-shared） |
| 方案 | 移除 `.cp-page-head`，统一使用 `.page-head`；`_welcome.html` 改用 `.page-head` 或标记为 dead code |

### 3.3.4 ARCH-5：文本令牌命名空间合并

| 项 | 内容 |
| --- | --- |
| 现状 | Legacy `--cp-muted` 与 Redesign `--cp-text-muted` 共存，模板混用 |
| 方案 | 在 `console-theme.css` 的 `.cp-shell` 作用域下，将 `--cp-muted` alias 为 `--cp-text-muted`：`--cp-muted: var(--cp-text-muted)`。长期迁移至统一命名 |
| 不做 | 不立即搜索替换所有引用（风险过大），只做别名桥接 |

### 3.3.5 ARCH-6：Tag-input 样式迁移

| 项 | 内容 |
| --- | --- |
| 现状 | `.tag-input-wrapper`、`#tag-suggest` 等 ~70 行组件样式定义在 `console-theme.css`（令牌文件） |
| 方案 | 移至 `redesign-components.css` 末尾，`console-theme.css` 仅保留令牌定义 |

### 3.3.6 ARCH-7：硬编码 rgba() 令牌化

| 项 | 内容 |
| --- | --- |
| 现状 | 20+ 处 `rgba()` 用于阴影和 focus ring（如 `rgba(239,68,68,0.5)`、`rgba(8,145,178,.12)`） |
| 方案 | 在 `console-theme.css` 新增 `--cp-shadow-md`、`--cp-ring-accent`、`--cp-ring-danger`、`--cp-overlay` 等语义令牌，逐步替换硬编码值 |
| 不做 | 不改变暗色主题下的颜色值（仅令牌化，不调色） |

### 3.3.7 ARCH-8：color-mix() 兜底

| 项 | 内容 |
| --- | --- |
| 现状 | Zebra striping 使用 `color-mix(in srgb, ...)`，Safari <16.2 无 fallback |
| 方案 | 在 `color-mix` 行前添加 fallback 声明：`background: var(--cp-canvas-alt, #f9fafb)`，不影响支持浏览器 |

**Batch 3 验收：**  
`python scripts/audit_hardcoded_colors.py --check` — 通过  
`wc -l app/static/css/redesign-pages.css` — ≤ 1,700 行  
`grep -c "\.cp-page-head" app/static/css/redesign-layout.css` — 0  
视觉回归：Dashboard / 任务详情 / 标签页 截图对比无差异

**Batch 4：后端架构改善（ARCH-9 ~ ARCH-10）**

**注：**后端大文件拆分为结构性重构，风险较高。本批次仅做**最小抽取**以降低文件复杂度，不做全面重构。

### 3.4.1 ARCH-9：views.py 最小拆分

| 项 | 内容 |
| --- | --- |
| 文件 | `app/main/views.py`（1,157 行）、`app/rbac/views.py`（1,434 行） |
| 方案（Phase 1 — 本批次） | 1. 从 `rbac/views.py` 提取 tag 管理路由到 `app/rbac/views_tags.py`（~200 行） 2. 从 `rbac/views.py` 提取注册审批路由到 `app/rbac/views_registration.py`（~200 行） 3. 在 `rbac/views.py` 中 import + register routes |
| 方案（Phase 2 — 后续） | 从 `main/views.py` 提取 API 路由到 `app/api/views.py` |
| 不做 | 不改变 URL 路由或 Blueprint 注册方式；不拆 `main/views.py`（风险较大，分阶段处理） |

### 3.4.2 ARCH-10：RBAC services 仓库化

| 项 | 内容 |
| --- | --- |
| 文件 | `app/rbac/services.py`（1,112 行） |
| 现状 | 直接使用 `db.session.query()` 和 `flask.session`/`flask.request` |
| 方案（Phase 1 — 本批次） | 将 `flask.session`/`flask.request` 依赖从 4 个核心函数中提取为参数：  ``` # Before def write_audit_log(action, detail):     username = session.get('username', 'system')  # After def write_audit_log(action, detail, username=None, client_ip=None):     username = username or 'system' ```  视图层调用时传入上下文值。 |
| 不做 | 不迁移所有 `db.session` 到 Repository（范围过大） |

**Batch 4 验收：**  
`bash scripts/cronpilot.sh test` 全量通过（含现有 RBAC 测试）  
`wc -l app/rbac/views.py` — ≤ 1,100 行  
`grep -c "from flask import session" app/rbac/services.py` — 减少至 ≤ 2 处  
`bash scripts/verify_golden_path.sh` — 冒烟通过  
`bash scripts/cronpilot.sh restart --daemon` + 浏览器登录验证

**Batch 5：代码质量清理（CQ-1 ~ CQ-12）**

| ID | 修复内容 | 文件 |
| --- | --- | --- |
| CQ-1 | 确认 `_welcome.html` 路由状态；若无路由引用则标记 deprecated 注释 | `_welcome.html` |
| CQ-2 | 提取 `cpCopy()` 到 `common-redesign.js` 为全局工具函数 | JS |
| CQ-3 | 将模态框 `style="display:none"` 替换为 CSS class `.hidden` | 6+ 模板 |
| CQ-4 | 将 `javascript:void(0)` 替换为 `<button type="button">` | `tags.html` 等 |
| CQ-5 | `CpModal` 添加单实例守卫（打开前关闭已有实例） | `redesign-confirm.js` |
| CQ-6 | Toast dismiss 添加 `setTimeout` 兜底（`animationend` 未触发时 500ms 后移除） | `redesign-toast.js` |
| CQ-7 | `sidebar` 变量添加 null 守卫 | `redesign-shell.js` |
| CQ-8 | 在 `login_limiter.py` 添加内存清理：过期条目每 60 秒裁剪一次 | Python |
| CQ-9 | `cron_check()` 异常改为 `logger.error` 而非静默 `pass` | `app/__init__.py` |
| CQ-10 | `cron_del_job_log` 改为单次 `GROUP BY cif_id HAVING COUNT(*) > max` 批量查询 | `app/crons.py` |
| CQ-11 | `print()` → `logger.info()` | `rbac/services.py` |
| CQ-12 | 移除 `groups.html` 中未使用的 `avatars` 变量 | 模板 |

**Batch 5 验收：**  
`bash scripts/cronpilot.sh test` 全量通过  
`grep -rn "javascript:void" app/templates/redesign/` — 0 hits  
`grep -rn "print(" app/rbac/services.py` — 0 hits  
`grep -rn "except Exception" app/__init__.py` — 有 `logger.error` 而非 `pass`

**Batch 6：Mockup 对齐 — 仅结构性补齐（MOCK-3 ~ MOCK-11）**

**注：**MOCK-1（业务组详情面板）和 MOCK-2（标签命名空间）为大型功能开发，需独立设计文档。本批次仅处理现有页面可快速对齐的结构差异。

| ID | 修复内容 | 涉及文件 |
| --- | --- | --- |
| MOCK-3 | 执行记录表：确认当前 7 列是否符合实际数据模型，或补充「响应码」「失败原因」列 | `execution_logs.html`、`_exec_logs_rows.html` |
| MOCK-4 | 失败执行详情页：在现有 `run_inspector.html` 中添加红色边框失败原因面板（条件渲染） | `run_inspector.html` |
| MOCK-5 | 注册审批表补充「邮箱」「花名」「申请原因」列（需后端传入这些字段） | `registration_review.html` |
| MOCK-6 | Dashboard Exception Panel 增加 P95 延迟/逾期未执行项（需后端 metrics 支持） | `dashboard.html`、`cron_repository.py` |
| MOCK-7 | 任务表单添加分区卡片布局（基础信息/请求配置/调度配置）+ 面包屑 | `task_form.html` |
| MOCK-8 | 用户列表页补充角色/业务组筛选 chip | `users.html` |
| MOCK-9 | 修改密码页添加密码强度指示条 | `change_password.html` |
| MOCK-10 | 操作记录页添加时间范围快捷选择（24h/7d/30d） | `operation_log.html` |
| MOCK-11 | 任务表单/用户表单/业务组表单添加面包屑导航 | 3 个模板 |

**风险：**MOCK-3/5/6 需后端配合（新增字段/查询），可能涉及 API 契约变更。建议先实现纯前端可完成的项（MOCK-4/7/8/9/10/11），后端依赖项单独排期。

**Batch 6 验收：**逐项对照 `doc/design/CronPilot-2026-redesign-mockup.html` 对应 `view-*` 区块，截图比对。

**Batch 7：Mockup 对齐 — 大型功能（MOCK-1、MOCK-2）**

以下两项为独立功能开发，本文档仅记录方向性方案，详细设计需独立文档。

### 3.7.1 MOCK-1：业务组详情面板

| 项 | 内容 |
| --- | --- |
| Mockup 规格 | 点击业务组卡片展开：成员列表 + 权限 Scope 可视化 + 组内任务列表（含健康度） |
| 方向 | 在 `groups.html` 中卡片点击展开 inline detail panel，复用 Dashboard 表格样式；后端需新增 `/rbac/group/<id>/detail` API 返回成员/任务/权限数据 |
| 规模估算 | ~300 行前端 + ~150 行后端 + 测试 |

### 3.7.2 MOCK-2：标签命名空间

| 项 | 内容 |
| --- | --- |
| Mockup 规格 | 标签按命名空间（业务域/优先级/生命周期/区域）分组显示 pill 卡片 |
| 方向 | 数据库 `CronTag` 表新增 `namespace` 字段；标签展示按 namespace 分组渲染；向后兼容：无 namespace 的标签归入「默认」分组 |
| 规模估算 | ~200 行前端 + ~100 行后端 + 迁移脚本 + 测试 |

**范围声明：**MOCK-1 和 MOCK-2 需独立设计文档（含数据库迁移方案、API 契约、回归测试计划），不在本方案批次中执行。

**Batch 8：文档同步**

| 文件 | 动作 |
| --- | --- |
| `RELEASE_NOTES.md` | 新增 `[Unreleased]` 条目，记录各 Batch 修复内容 |
| `doc/design/Redesign代码全面Review修复方案-2026-08.html` | 本文档；随进度更新各 Batch 状态 |
| `doc/index.html` | 注册本文档 |
| `AGENTS.md` / `.cursor/rules/` | 若修复涉及新增规范，同步更新 |
| `python scripts/html_docs_to_markdown.py --check` | HTML ↔ MD 同步 |

## §4 批次执行顺序与依赖关系

```
Batch 1 (安全)     ──┐
                     ├──→ Batch 5 (代码质量) ──→ Batch 6 (Mockup 快速对齐)
Batch 2 (可访问性) ──┘                              │
                                                     ├──→ Batch 8 (文档)
Batch 3 (CSS 架构) ──────────────────────────────────┘
                                                     
Batch 4 (后端架构) ──────→ 独立验收
                                                     
Batch 7 (大型功能) ──────→ 需独立设计文档
```

**推荐执行序**：Batch 1 → Batch 2 → Batch 3 → Batch 5 → Batch 4 → Batch 6 → Batch 8 → （Batch 7 另议）

## §5 风险评估

**风险 1：CSS 拆分后加载顺序变化**  
影响：Batch 3 提取 Dashboard CSS 后，`_base.html` 的 `<link>` 顺序可能影响级联覆盖。  
缓解：新文件在 `redesign-pages.css` 之后、`redesign-mockup-shared.css` 之前加载；视觉回归截图验证。

**风险 2：后端路由拆分可能丢失装饰器**  
影响：Batch 4 将路由函数移至子文件时，`@rbac.route` 和 `@require_permission` 装饰器可能遗漏。  
缓解：拆分后运行 `python scripts/check_route_completeness.py --check app/rbac/views.py` + 全量冒烟。

**风险 3：SSRF fail-closed 误拒合法任务**  
影响：SEC-6 改为 fail-closed 后，DNS 短暂不可用将拒绝所有任务执行。  
缓解：提供 `url_ssrf_dns_fail_open` 配置项恢复旧行为；allowlist 白名单不受影响。

**风险 4：Auth 页面引入 common-redesign.js 的兼容性**  
影响：A11Y-3 方案 A 在 Auth 页面引入 jQuery 依赖的 `common-redesign.js`，Auth 页面已加载 jQuery，理论兼容。  
缓解：引入后在登录/注册页面完成端到端提交测试。

## §6 不做清单

- 不做全面 Repository 迁移（只做最小参数化解耦）
- 不做 `main/views.py` 拆分（Batch 4 Phase 2）
- 不修改业务逻辑或 API 契约（安全加固除外）
- 不改变暗色主题视觉效果
- 不新增 Redis 依赖（CQ-8 仅做内存清理优化）
- 不实现 MOCK-1 业务组详情面板（需独立设计文档）
- 不实现 MOCK-2 标签命名空间（需独立设计文档和数据库迁移）

文档：`doc/design/Redesign代码全面Review修复方案-2026-08.html`  
关联：OPT-P0-19-REVIEW · CronPilot v4.x  
[← 文档索引](../index.html)

· [Markdown](Redesign代码全面Review修复方案-2026-08.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
