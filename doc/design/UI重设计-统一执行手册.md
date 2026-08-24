# CronPilot UI Redesign — 统一执行手册 (Unified Execution Manual)

> HTML 版：[UI重设计-统一执行手册.html](UI重设计-统一执行手册.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# CronPilot UI Redesign — 统一执行手册

**文档编号**：OPT-P1-16-MANUAL v2  
**性质**：前端重构的**架构索引**（不含精确数值）。所有视觉数值均引用源文档。  
**目标**：前端重构的唯一执行入口 —— 批次结构 + 架构决策 + 质量门禁 + 源文档定位  
**权威数值来源**：[Mockup HTML (CSS)](CronPilot-2026-redesign-mockup.html) · [视觉规格书](UI重设计-视觉设计规格书.html) · [逐页规格书](UI重设计-逐页设计规格书.html)  
**上次更新**：2026-08-11 v2 — 移除冗余数值，改为纯索引

### 目录

[Part 1: 架构与约束](#part1)  
[Part 2: 全局设计规格（引用索引 — 不含数值）](#part2)  
[Part 3: 逐批次执行计划（架构索引 — 不含逐页详情）](#part3)  
[Part 4: 质量门禁体系](#part4)  
[Part 5: 动画与过渡规格（引用索引）](#part5)  
[Part 6: 无障碍与 ARIA 规格（引用索引）](#part6)  
[Part 7: 风险与最终验收](#part7)

## Part 1: 架构与约束

### 1.1 技术栈

- Python 3.8–3.11 + Flask 2.3 SSR（Jinja2 模板）
- jQuery 全局可用（`common.js`）；新增 JS 使用 IIFE/ES Module
- CSS 变量驱动（`--cp-*` 在 `console-theme.css`，Redesign 使用 `--*` 短名 in page CSS）
- 新模板继承 `redesign/_base.html`（独立于 Bootstrap `admin_base.html`）
- 新组件使用 `.cp-*` 前缀（避免 Bootstrap/Flat UI 冲突）
- 表单保留 `js-ajax-form` + `js-ajax-submit` 约定
- 深色模式：`[data-theme="dark"]` 覆盖 CSS 变量

### 1.2 文件组织

```
app/templates/redesign/
├── _base.html              # Shell（已完成）
├── _sidebar.html           # Nav（已完成）
├── _topbar.html            # Header（已完成）
├── _pagination.html        # 共享分页宏（Phase 3 提取）
├── _breadcrumb.html        # 面包屑宏
├── dashboard.html          # B1 ✓
├── execution_logs.html     # B1 ✓
├── task_detail.html        # B3
├── run_inspector.html      # B3
├── task_form.html          # B4（新建+编辑共用）
├── users.html              # B5
├── user_form.html          # B5
├── groups.html             # B6
├── reg_review.html         # B7
├── audit_log.html          # B8
├── operation_log.html      # B8
├── tags.html               # B9
├── change_password.html    # B10
├── api_token.html          # B10
├── api_doc.html            # B10
└── auth/
    ├── login.html          # B10（独立，不继承 _base）
    ├── register.html       # B10
    └── forgot.html         # B10

app/static/css/
├── console-theme.css       # Design Tokens（已完成）
├── redesign-layout.css     # Shell Grid（已完成）
├── redesign-components.css # 组件库（已完成，后续批次扩展）
└── redesign-pages.css      # 各页面特定样式（B3 新建，提取 inline CSS）

app/static/js/
├── redesign-shell.js       # Shell 交互（已完成）
├── redesign-theme.js       # Theme 切换（已完成）
├── redesign-cmd-palette.js # Command Palette（B11）
├── redesign-toast.js       # Toast 全局 API（B2）
└── redesign-confirm.js     # Confirm Modal 全局 API（B2）
```

### 1.3 路由分支策略

每个页面在对应 view 函数中添加 `if getattr(g, 'ui_version', 'v1') == 'v2'` 分支，渲染 `redesign/*.html`。Flask 路由 URL 不变，前端通过 Cookie `cp_ui_version=v2` 切换。开发期间仅内部使用，不面向终端用户。

### 1.4 当前进度

| 批次 | 范围 | 状态 |
| --- | --- | --- |
| Shell (Phase 1) | Layout + Sidebar + Topbar + Theme toggle | 已完成 |
| B1 (Phase 2) | Dashboard + 执行记录 | 已完成（结构对齐，数据待丰富） |
| B2 | 全局组件提取（Toast/Modal/Empty） | 已完成 |
| B3 | 任务详情 + Run Inspector | 已完成 |
| B4 | 任务表单（新建/编辑） | 未开始 |
| B5 | 用户管理 | 未开始 |
| B6 | 业务组 | 未开始 |
| B7 | 注册审批 | 未开始 |
| B8 | 审计日志 + 操作记录 | 未开始 |
| B9 | 标签管理 | 未开始 |
| B10 | Auth + 个人设置 + API | 未开始 |
| B11 | Command Palette | 未开始 |
| B12 | 全量 Polish + 验收 | 未开始 |

## Part 2: 全局设计规格（引用索引）

**⚠️ 本节不包含精确数值。**  
所有视觉规格的**唯一权威来源**为以下两份文档。实现时必须直接 `Read` 对应源：  
  
**色彩 / 字体 / 间距 / 圆角 / 阴影 / 组件尺寸**：[视觉设计规格书](UI重设计-视觉设计规格书.html) (OPT-P1-16-SPEC)  
**Mockup CSS 源码（终极权威）**：[Mockup HTML](CronPilot-2026-redesign-mockup.html) 第 8–334 行 `<style>` 块

### 2.1 为什么不在此重复数值

**教训**（2026-08-11）：本手册 v1 在整合时凭记忆写入 15 处与源文档不一致的数值（字体族错误、色值偏差、尺寸虚构），导致整份文档不可信。  
**结论**：中间层整合文档 = 精度损失来源。因此本手册 **不再包含任何可从源文档查到的精确值**。

### 2.2 规格速查索引

| 需要查什么 | 去哪里查 | 在源文档的位置 |
| --- | --- | --- |
| 色彩 Token（Light + Dark 全量） | [视觉规格书 §1.1–1.2](UI重设计-视觉设计规格书.html) | 行 36–84 |
| 字体系统（sans/mono/各级字号） | [视觉规格书 §1.3](UI重设计-视觉设计规格书.html) | 行 86–110 |
| 间距系统（4px grid） | [视觉规格书 §1.4](UI重设计-视觉设计规格书.html) | 行 112–130 |
| 圆角 / 阴影 | [视觉规格书 §1.5–1.6](UI重设计-视觉设计规格书.html) | 行 132–200 |
| 按钮 / 表格 / 表单组件 | [视觉规格书 §2](UI重设计-视觉设计规格书.html) | 行 202–330 |
| Shell 布局（Sidebar/Topbar/Content） | [视觉规格书 §3](UI重设计-视觉设计规格书.html) | 行 332–400 |
| Token 到现有 `--cp-*` 的映射 | [视觉规格书 §4](UI重设计-视觉设计规格书.html) | 行 440–470 |
| 各页面详细布局 + 响应式 + 交互状态 | [逐页规格书](UI重设计-逐页设计规格书.html) | 全文 16 页 |
| 动画 / 过渡 / Motion 原则 | [逐页规格书 附录 C](UI重设计-逐页设计规格书.html) | 搜索 `#animation` |
| ARIA / 无障碍 / 键盘导航 | [逐页规格书 附录 D](UI重设计-逐页设计规格书.html) | 搜索 `#accessibility` |
| Mockup 原始 CSS（终极仲裁） | [Mockup HTML](CronPilot-2026-redesign-mockup.html) | 行 8–334 |

### 2.3 架构决策（非数值，保留在此）

#### Token 命名空间策略

- **Redesign 模板内**：使用 Mockup 原生无前缀 Token（`--canvas`, `--signal`, `--warning` 等），定义在各 redesign 页面 `<style>` 或 `redesign-layout.css` 中
- **现有 v1 模板**：继续使用 `--cp-*` 前缀（`console-theme.css`），不做修改
- **映射关系**：见视觉规格书 §4 "Token 映射对照表"
- **冲突隔离**：redesign 页面在 `.cp-shell` 作用域内；v1 页面不加载 redesign CSS

#### CSS 文件策略

- **从 B3 起**：各页面特定 CSS 直接写入 `redesign-pages.css`，不再使用 inline `<style>`
- **B2 提取**：Dashboard/执行记录的 inline CSS 迁移到 `redesign-pages.css`
- **组件 CSS**：共享组件在 `redesign-components.css`（已有基础）

#### JS 兼容策略

- **保留 `common.js`**：新模板继续加载，确保 CSRF 注入、Ajax 表单守卫生效
- **按钮 type 约定**：所有表单主提交按钮**必须保留 `type="submit"`**，否则 `common.js` 防重复提交守卫失效
- **新增 JS**：`redesign-toast.js` / `redesign-confirm.js` / `redesign-cmd-palette.js` 均为 IIFE 模式，不冲突

## Part 3: 逐批次执行计划（架构索引）

**⚠️ 本节不包含精确视觉数值。**  
每页的具体 CSS 数值、列结构、响应式断点等，必须在实现时 `Read` 以下权威源：  
• **Mockup HTML**：<CronPilot-2026-redesign-mockup.html> — 对应 `id="view-*"` 区块  
• **逐页规格书**：<UI重设计-逐页设计规格书.html> — 16 页详细布局 + 响应式 + 交互状态  
• **视觉规格书**：<UI重设计-视觉设计规格书.html> — 组件规格（按钮/表格/表单等）

### 3.1 批次总览与依赖

```
B1 (补完) ──→ B2 (组件) ──→ B3 (Detail/Inspector) ──→ B4 (Forms)
                                                            │
                                                     B5─B9 (Admin 5 pages)
                                                            │
                                                     B10 (Auth/Personal)
                                                            │
                                                     B11 (Cmd Palette)
                                                            │
                                                     B12 (Polish)
```

| 批次 | 页面范围 | Mockup view-id | 逐页规格书章节 | 预估 | 前置 |
| --- | --- | --- | --- | --- | --- |
| B1 | Dashboard + 执行记录数据补完 | `view-dashboard`, `view-logs` | §1–§2 | 0.5 天 | Shell |
| B2 | Toast / Modal / Empty / Skeleton 提取 | （全局组件） | 附录 C | 0.5 天 | B1 |
| B3 | 任务详情 + Run Inspector | `view-detail`, `view-run-inspector`, `view-run-failed` | §3–§4 | 1 天 | B2 |
| B4 | 任务表单（新建 + 编辑） | `view-form`, `view-task-add` | §5 | 1 天 | B2 (可与 B3 并行) |
| B5 | 用户管理 | `view-users`, `view-user-add`, `view-user-edit` | §6 | 0.5 天 | B2 |
| B6 | 业务组 | `view-groups` | §7 | 0.5 天 | B2 |
| B7 | 注册审批 | `view-reg-review` | §8 | 0.5 天 | B2 |
| B8 | 审计日志 + 操作记录 | `view-audit`, `view-optlog` | §9 | 0.5 天 | B2 |
| B9 | 标签管理 | `view-tags` | §10 | 0.5 天 | B2 |
| B10 | Auth + 修改密码 + API Token + API 文档 | `login-page`, `register-page`, `forgot-page`, `view-password`, `view-api-token`, `view-apidoc` | §11–§14 | 1 天 | B2 |
| B11 | Command Palette | （overlay 组件） | §15 | 0.5 天 | B3 |
| B12 | 全量 Polish + 最终验收 | 全部 | 全部 + 附录 C/D | 1 天 | B1–B11 |

**总计**：~8 天（单人串行）；可压缩至 5 天（B4/B5-B9 并行）

### 3.2 每批次执行规程（统一流程）

**实现任一页面时，强制执行以下步骤：**

1. **Read 源**：`Read` Mockup HTML 中对应 `view-*` 区块（用 Grep 定位 id）→ 获取精确 HTML 结构 + inline CSS
2. **Read 规格**：`Read` 逐页规格书中对应章节 → 获取响应式断点 + 交互状态表
3. **实现**：严格按步骤 1-2 获取的数值编码；**禁止凭记忆写数值**
4. **Design QA (门禁 #8)**：
   - 列出 Mockup 结构清单（列数、列名、CSS class、组件层级）
   - `curl + grep` 验证关键 class 存在于实现
   - 浏览器截图逐区域对照 Mockup
   - 差异 → 修复 → 重新验证
5. **通用门禁**：单测 + 颜色审计 + v1 无回归 + 深色模式 + 4 角色权限

### 3.3 批次交互要点备忘（非数值，仅架构决策）

| 批次 | 关键架构决策 |
| --- | --- |
| B1 | 补充后端计算字段（成功率、croniter next\_run、take\_time humanize）；拆分"异常"为"失败/超时"两个 chip |
| B2 | Toast/Modal/Empty 提取为独立 JS（IIFE 模式）+ Jinja2 宏；**此批次产出的组件供后续所有批次复用** |
| B3 | 任务详情使用 2×2 CSS Grid；Run Inspector 使用 max-width 900px 居中；失败 Run 特有 .danger section |
| B4 | 新建/编辑共用 `task_form.html`；使用 `js-ajax-form`；业务组 select 受 Scope 限制 |
| B5 | 9 列表格含"岗位"；已停用行 opacity: 0.6；编辑页有 .danger-zone |
| B6 | 卡片网格（非表格）；点击展开 detail panel 而非跳转 |
| B7 | 审批操作触发 Toast（非整页刷新）；4 种 status chips |
| B8 | 审计日志 6 列 + 操作记录 7 列；变更详情使用折叠 summary |
| B9 | Namespace 分区 + pill chips；hover 显示编辑/删除 icon |
| B10 | Auth 页面独立布局（不继承 \_base.html）；密码强度 4 bars 指示器；Token 遮蔽 + 复制 |
| B11 | ⌘K 触发；overlay + cmd-box；debounce 150ms；↑↓ 键盘导航 |
| B12 | 全量 inline style → CSS 文件提取；prefers-reduced-motion；ARIA + keyboard nav；逐页截图对照 |

### 3.4 B12 最终验收清单

1. 深色模式逐页截图 — 确认无白色闪块、对比度符合 WCAG AA
2. 响应式验证：1024px (sidebar auto-collapse)、768px (sidebar hidden + hamburger)
3. Command Palette 全面测试（搜索/导航/操作）
4. v1 无回归：`cp_ui_version=v1` 全站正常
5. 4 角色权限全链路：seed admin / biz admin / operator / viewer
6. 全量测试套件通过
7. 文档同步：RELEASE\_NOTES + doc/design/ + README
8. CSS 提取：inline style → `redesign-pages.css`
9. Animation：`prefers-reduced-motion` 支持
10. Accessibility：ARIA 属性、keyboard nav、focus rings

## Part 4: 质量门禁体系

### 4.1 每批次交付必须通过 (10 道门禁)

| # | 门禁 | 工具/命令 | 失败处理 |
| --- | --- | --- | --- |
| 1 | 单元测试 | `bash scripts/cronpilot.sh test` | 修复后重跑 |
| 2 | 颜色审计 | `python scripts/audit_hardcoded_colors.py --check` | 替换为 var(--cp-\*) |
| 3 | Ajax Form 守卫 | `python -m unittest tests.test_ajax_form_guard -v` | 补充 js-ajax-submit |
| 4 | HTML↔MD 同步 | `python scripts/html_docs_to_markdown.py --check` | regenerate |
| 5 | Restart + 浏览器 | `cronpilot.sh restart → 登录 → 目标页面` | 修复渲染错误 |
| 6 | v1 无回归 | 切回 `cp_ui_version=v1` 验证 | 隔离 CSS/JS 泄漏 |
| 7 | 深色模式 | 切换 dark → 无白色闪块 | 补 dark override |
| **8** | **Mockup Design QA** | `Read` mockup 源 → 列结构 → grep classes → 截图对照 | **不通过不得提交** |
| 9 | 复盘文档化 | `python scripts/check_postmortem_completeness.py --check` | 补充复盘/RELEASE\_NOTES |
| 10 | 4 角色权限 | seed admin / biz admin / operator / viewer 各登录 | 修复权限逻辑 |

### 4.2 Design QA 强制流程（门禁 #8 详解）

**来源**：Phase 2 Mockup 偏离事故后追加的强制门禁。每个页面实现完成后必须执行：  
  
**Step 1**：`Read` Mockup 对应 `view-*` 区块的完整 HTML 源码  
**Step 2**：列出结构清单（列数、列名、CSS class、组件层级、按钮类型、间距值）  
**Step 3**：`curl + grep` 验证关键 class 在实现中存在  
**Step 4**：浏览器截图逐区域对照 Mockup  
**Step 5**：如有差异 → 修复 → 回到 Step 3

### 4.3 程序化强制（Hook 系统）

| Layer | Hook | 事件 | 效果 |
| --- | --- | --- | --- |
| L1 | postmortem-reminder.sh | postToolUse (Write/StrReplace) | 每次编辑后注入复盘 checklist |
| L2a | pre-commit-gate.sh | beforeShellExecution (git commit) | 阻止不含 RELEASE\_NOTES 的代码提交 |
| L2b | stop prompt hook | stop | 结束前评估复盘完整性 |
| L3 | CI script | check\_postmortem\_completeness.py | CI 阻断不完整文档 |

## Part 5: 动画与过渡规格（引用索引）

**权威来源**：[逐页规格书 附录 C（搜索 `#animation`）](UI重设计-逐页设计规格书.html)  
本节仅保留设计原则，不重复具体 keyframe 参数。

### 5.1 Motion 设计原则（架构决策，保留）

| 原则 | 说明 |
| --- | --- |
| 响应性 | hover/focus 反馈 ≤ 100ms |
| 自然性 | 出现 ease-out；消失 ease-in |
| 克制性 | 仅对用户关注的元素做动画；数据无装饰性动画 |
| 可预测性 | 同类交互使用相同曲线和时长 |
| 性能优先 | 只 animate transform/opacity（GPU 加速） |
| Reduce motion | `@media (prefers-reduced-motion: reduce)`: all animation/transition → 0.01ms |

### 5.2 动画分类索引

| 类别 | 包含动画 | 详见 |
| --- | --- | --- |
| 全局过渡（hover/focus） | nav-item, btn, action-btn, tr:hover, chip, input:focus | 逐页规格书 附录 C §C.1 |
| 关键帧动画 | slideIn, shimmer, fadeIn, scaleIn, slideUp | 逐页规格书 附录 C §C.2 |

## Part 6: 无障碍与 ARIA 规格（引用索引）

**权威来源**：[逐页规格书 附录 D（搜索 `#accessibility`）](UI重设计-逐页设计规格书.html)  
本节仅保留合规要求总纲，不重复具体对比度数值和 ARIA 属性表。

### 6.1 合规目标

- **标准**：WCAG 2.1 Level AA
- **对比度**：正文 ≥ 4.5:1；大文本 ≥ 3:1；所有 Token 对比度计算结果见逐页规格书 附录 D §D.1
- **键盘导航**：所有交互元素 Tab 可达；visible focus ring；Esc 关闭 overlay
- **Screen Reader**：landmark 结构完备；动态内容使用 `aria-live`；表格有 `caption`

### 6.2 索引

| 需要查什么 | 去哪里查 |
| --- | --- |
| 色彩对比度计算表 | 逐页规格书 附录 D §D.1 |
| 键盘导航矩阵 | 逐页规格书 附录 D §D.2 |
| ARIA 属性逐页清单 | 逐页规格书 附录 D §D.3 |
| Focus 可见性规格 | 逐页规格书 附录 D §D.4 |
| Screen reader + Landmark 结构 | 逐页规格书 附录 D §D.5–D.6 |

## Part 7: 风险与最终验收

### 7.1 风险评估

| 风险 | 概率 | 影响 | 缓解 |
| --- | --- | --- | --- |
| 实现偏离 Mockup | 低（Design QA 门禁） | 高 | 每页 Read mockup + grep + 截图; L1 Hook |
| 新旧 CSS 冲突 | 中 | 中 | `.cp-*` 前缀; `.cp-shell` 作用域 |
| jQuery common.js 事件不匹配 | 中 | 中 | 保留 `.js-ajax-form` 约定 |
| CSRF 遗漏 | 低 | 高 | `_base.html` 统一注入; 集成测试 |
| 深色模式残留白色 | 中 | 中 | B12 全量审计 |
| 性能退化 | 低 | 低 | 提取共享 CSS; 只 animate transform/opacity |

### 7.2 最终验收标准

1. `cp_ui_version=v2` 从登录页遍历所有 sidebar 链接 → 全新设计（无经典混入）
2. 4 种角色各登录 → 权限正确（导航 + Scope + 操作拦截）
3. 深色/浅色各截图一套（16 页 × 2 = 32 张）
4. 768px 宽度 → 响应式布局正确
5. `cp_ui_version=v1` → 经典 UI 零回归
6. 全量测试套件通过（目标 450+ tests）
7. `check_postmortem_completeness.py --check` 通过
8. RELEASE\_NOTES 包含所有 Batch 的变更条目
9. `prefers-reduced-motion` 下无动画
10. ARIA landmark + keyboard nav 手工验证

---

### 参考文档索引

| 文档 | 内容 | 路径 |
| --- | --- | --- |
| 视觉设计规格书 | 完整 Design Tokens + 334 行 CSS 提取 | `doc/design/UI重设计-视觉设计规格书.html` |
| 逐页设计规格书 | 16 页布局+响应式+交互+动画+ARIA 完整规格 | `doc/design/UI重设计-逐页设计规格书.html` |
| Mockup 源文件 | HTML mockup（22 views + auth） | `doc/design/CronPilot-2026-redesign-mockup.html` |
| Phase 2 偏离复盘 | 事故原因与防护措施 | `doc/postmortem/2026-08-Phase2-Mockup偏离复盘.html` |
| 元复盘 | 复盘失效机制分析 | `doc/postmortem/2026-08-元复盘-复盘失效机制.html` |

---

*文档版本：v2 · 2026-08-11 · 策略：纯索引+架构，数值引用源文档（Mockup CSS / 视觉规格书 / 逐页规格书）*

[文档索引](../index.html) · [Markdown](UI重设计-统一执行手册.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
