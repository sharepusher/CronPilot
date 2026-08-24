# CronPilot UI Redesign — 逐页设计规格书 (Complete)

> HTML 版：[UI重设计-逐页设计规格书.html](UI重设计-逐页设计规格书.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# CronPilot UI Redesign — 逐页设计规格书

**📌 定位**：本文档为 [统一执行手册](UI重设计-统一执行手册.html) 的详细附录（Part 3 逐页规格的完整版 + Part 5/6 动画与无障碍）。执行入口以统一手册为准。

**文档编号**：OPT-P1-16-PAGE-SPEC v2  
**状态**：设计评审  
**Mockup 源**：`doc/design/CronPilot-2026-redesign-mockup.html`  
**全局 Token**：参见 `doc/design/UI重设计-视觉设计规格书.html`  
**范围**：每页 = 布局结构 · 响应式断点 · 交互状态 · 验收标准

### 目录 (16 pages + 4 overlay/state)

[01 Dashboard（任务中心）](#p01)  
[02 执行记录](#p02)  
[03 任务详情](#p03)  
[04 Run Inspector](#p04)  
[05 任务表单（编辑/新建）](#p05)  
[06 用户管理列表](#p06)  
[07 用户表单（添加/编辑）](#p07)  
[08 业务组](#p08)  
[09 注册审批](#p09)  
[10 审计日志](#p10)  
[11 操作记录](#p11)  
[12 标签管理](#p12)  
[13 修改密码](#p13)  
[14 API Token](#p14)  
[15 API 文档](#p15)  
[16 登录/注册/忘记密码](#p16)  
[OV Command Palette / Toast / Modal](#overlay)  
[ST Empty / Loading / Error](#state)  
[C 动画与过渡效果规格](#animation)  
[D 无障碍与 ARIA 规格](#accessibility)

## PAGE 01: Dashboard（任务中心）

View ID
:   `#view-dashboard`

路由
:   `GET /cron_list`

模板
:   `redesign/dashboard.html`

继承
:   `redesign/_base.html`

Content max-width
:   1200px

CSS Prefix
:   `.hf-*` / `.exc-*`

### 1.1 布局结构

┌─────────────────────────────────────────────────────────────────────┐
│ .page-head (flex; between; wrap; gap:12px; mb:20px) │
│ ┌────────────────────────────┐ ┌─────────────────────────────┐ │
│ │ h1 "任务中心" 18px/600 │ │ .btn.btn-primary 32px h │ │
│ │ .sub 12.5px muted mt:3px │ │ icon 14×14 + "新建任务" │ │
│ └────────────────────────────┘ └─────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│ .stats (grid:4×1fr; gap:1px; bg:border; border:1px; r:8px; mb:20px) │
│ ┌────────────┬────────────┬────────────┬────────────┐ │
│ │ .stat │ .stat │ .stat │ .stat │ │
│ │ pad:14 18 │ pad:14 18 │ pad:14 18 │ pad:14 18 │ │
│ │ bg:surface │ bg:surface │ bg:surface │ bg:surface │ │
│ │ │ │ │ │ │
│ │ .label: │ .label: │ .label: │ .label: │ │
│ │ 11px/500 │ 11px/500 │ 11px/500 │ 11px/500 │ │
│ │ upper faint│ upper faint│ upper faint│ upper faint│ │
│ │ ls:0.04em │ ls:0.04em │ ls:0.04em │ ls:0.04em │ │
│ │ mb:6px │ mb:6px │ mb:6px │ mb:6px │ │
│ │ │ │ │ │ │
│ │ .value: │ .value: │ .value: │ .value: │ │
│ │ 22px/600 │ 22px/600 │ 22px/600 │ 22px/600 │ │
│ │ mono │ mono │ mono │ mono │ │
│ │ ls:-0.02 │ ls:-0.02 │ ls:-0.02 │ ls:-0.02 │ │
│ │ .danger │ .warning │ .signal │ .danger │ │
│ │ │ │ │ │ │
│ │ .total: │ .total: │ .total: │ .total: │ │
│ │ 11px faint │ 11px faint │ 11px faint │ 11px faint │ │
│ │ mt:4px │ mt:4px │ mt:4px │ mt:4px │ │
│ └────────────┴────────────┴────────────┴────────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│ .exception-panel (border:1px danger; r:8px; bg:danger-bg; mb:20px) │
│ ┌───────────────────────────────────────────────────────────────┐ │
│ │ .exception-header (flex; gap:8px; pad:10 16; 12.5px/600) │ │
│ │ color:danger; svg 14×14 │ │
│ ├───────────────────────────────────────────────────────────────┤ │
│ │ .exception-list (bg:surface; border-top:1px border) │ │
│ │ ┌─ .exception-item (flex; gap:12px; pad:10 16; bb:1px) ────┐ │ │
│ │ │ .ex-icon .ex-name .ex-detail .ex-action │ │ │
│ │ │ 14px/700 12.5px/500 11.5px muted 12px/500 signal │ │ │
│ │ │ danger flex:1 cursor:pointer │ │ │
│ │ └──────────────────────────────────────────────────────────┘ │ │
│ └───────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│ .filters (flex; center; gap:8px; wrap; mb:14px) │
│ [.search 260×32 r:6] [.chip×5 28h r:6] [spacer] [.chip 业务组▾] │
│ [.chip 标签▾] │
├─────────────────────────────────────────────────────────────────────┤
│ .table-wrap (border:1px; r:8px; overflow:hidden) │
│ thead th: 10.5px/500 upper ls:0.05em faint pad:10 14 bg:surface │
│ 7 cols: 任务(auto) | 调度策略(~150) | 健康度(~80) | 最近执行(~130) │
│ | 下次执行(~100) | 业务组(~90) | 操作(90px) │
│ tbody td: pad:11 14; bb:1px border; hover:bg surface-2 │
│ .task-cell: name(13/500 hover→signal) + id(11 mono faint) │
│ + tags(flex gap:4 mt:4: .lifecycle + .tag×N) │
│ .cron-expr: mono 11.5px; bg:surface-2; pad:2 6; r:4; border:1px │
│ .schedule-human: 11px muted mt:3px │
│ .health: inline-flex gap:5; 12px/500; .dot 7×7 r:50% │
│ .run-cell: .run-status(pin 5×5 + code) + .run-duration(mono 11) │
│ + .run-time(11 muted) │
│ .next-run: 12px muted │
│ .scope-cell: 12px muted │
│ .row-actions: flex gap:3; .action-btn 26×26 r:5 │
│ retired row: opacity 0.6; actions only [恢复][更多] │
├─────────────────────────────────────────────────────────────────────┤
│ .pagination (flex; between; pad:12 0; 12px muted) │
│ .pg-info: "显示 1-5 / 共 128 个任务" │
│ .pg-nav: flex gap:2; .pg-btn 28×28 r:5 border 12px/500 │
│ .active: signal-bg border:signal color:signal-ink/600 │
│ .disabled: opacity:0.4 cursor:not-allowed │
└─────────────────────────────────────────────────────────────────────┘

### 1.2 响应式断点

| 断点 | Shell 变化 | 页面内容变化 |
| --- | --- | --- |
| `> 1200px` | Sidebar 220px 展开 | 全量 7 列 + Exception panel + 4 stat |
| `1024–1200px` | Sidebar 220px | .main padding→20 24; stat padding→12 14; "下次执行"列可 ellipsis |
| `768–1024px` | Sidebar collapse → 56px icon-only | Exception panel .ex-detail 隐藏; 表格列宽均匀压缩 |
| `< 768px` | Sidebar 隐藏 → hamburger overlay | stats→grid 2×2; filters wrap 多行; table overflow-x:auto; 隐藏"下次执行""业务组"列; pagination→prev/next only; .page-head flex-col |

### 1.3 交互状态

| 元素 | Default | Hover | Active/Focus | Disabled |
| --- | --- | --- | --- | --- |
| tbody tr | bg: transparent | bg: surface-2 | — | .retired: opacity 0.6 |
| .task-name | 13px/500; color: ink | color: signal; cursor: pointer | — | — |
| .chip | border: border; color: muted; 12px | — | .active: border: signal; bg: signal-bg; color: ink | — |
| .action-btn | 26×26; border: transparent; color: muted | bg: surface-2; border: border; color: ink | — | opacity 0.4; not-allowed |
| .action-btn.run | color: signal | bg: signal-bg; border: border | — | — |
| .btn-primary | bg: signal; border: signal; color: #fff | bg: signal-ink | — | opacity 0.6; not-allowed |
| .pg-btn | border: border; bg: surface; color: muted | bg: surface-2; color: ink | .active: bg: signal-bg; border: signal; color: signal-ink; 600 | .disabled: opacity 0.4 |
| .search input | border: border; color: muted | border: border-strong | border: signal; box-shadow: 0 0 0 3px signal-bg | — |
| .ex-action | color: signal; 12px/500 | underline (implied) | — | — |

#### 特殊页面状态

| 状态 | 视觉规格 |
| --- | --- |
| Empty（0 任务） | stats 全 0(faint); 隐藏 exception-panel; table-wrap 内显示 .empty-state: svg 48×48 faint opacity:0.6 → .empty-title 15px/600 → .empty-desc 12.5px muted max-w:300 → CTA btn-primary |
| Loading | stats .value 替换为 .skeleton 40×22px; table 内 5 行 skeleton flex 布局 |
| Error | 同 empty-state 结构; icon=error; title="加载失败"; CTA="重试" |

## PAGE 02: 执行记录

View ID
:   `#view-logs`

路由
:   `GET /job_log_all_list`

模板
:   `redesign/execution_logs.html`

Content max-width
:   1200px

CSS Prefix
:   `.el-*`

表头
:   任务 | 触发时间 | 耗时 | 响应码 | 状态 | 失败原因 | (detail icon)

### 2.1 布局关键尺寸

| 元素 | 规格 |
| --- | --- |
| .page-head h1 | "执行记录" 18px/600; .sub "全部任务的调度执行历史" 12.5px muted |
| .filters | flex; gap:8px; mb:14px; chips: [全部(active)] [失败] [超时]; spacer; [业务组▾] |
| table 列宽 | 任务(auto) | 触发时间(~140px mono 12px muted) | 耗时(~70px mono 12px) | 响应码(~60px mono 12px) | 状态(~70px) | 失败原因(~160px 11.5px) | 详情(60px) |
| 失败行 (row-fail) | tr: bg: danger-bg; .task-name color: danger; 耗时 color: danger; 响应码 color: faint(如—) 或 danger(如502); 失败原因 color: danger 11.5px |
| .task-cell | 只有 .task-name(13px/500)，无 id/tags（对比 Dashboard 更紧凑） |
| Detail btn | .action-btn 26×26; eye icon svg 13×13; 链接到 /job\_log\_detail/ID |

### 2.2 响应式断点

| 断点 | 变化 |
| --- | --- |
| > 1024px | 7 列全部可见 |
| 768–1024px | "失败原因"列 max-width: 100px; overflow: hidden; text-overflow: ellipsis |
| < 768px | table overflow-x: auto; 隐藏"响应码""失败原因"列 |

### 2.3 交互状态

| 元素 | Default | Hover | 特殊 |
| --- | --- | --- | --- |
| 成功行 tr | bg: transparent | bg: surface-2 | — |
| 失败行 tr | bg: danger-bg | bg: danger-bg (unchanged) | .task-name color: danger |
| Detail eye btn | color: muted | bg: surface-2; border: border; color: ink | navigate to run-inspector |
| .chip | 与 Dashboard 相同 | — | .active → signal style |

## PAGE 03: 任务详情

View ID
:   `#view-detail`

路由
:   `GET /cron_detail/<id>`

Content max-width
:   1200px

核心结构
:   Breadcrumb → Header → 2×2 Detail-Grid

### 3.1 布局关键尺寸

| 区域 | 规格 |
| --- | --- |
| .breadcrumb | flex gap:6px; 12px muted; mb:16px; links color:signal; separator svg 10×10 faint |
| .detail-header | flex; align:flex-start; between; mb:24px; gap:16px |
| .detail-title | 20px/600; mb:4px |
| .detail-id | mono 12px faint |
| .detail-badges | flex gap:6px; mt:8px; .lifecycle + .tag×N + group-tag |
| .detail-actions | flex gap:8px; flex-shrink:0; [立即执行 btn-primary] [暂停 btn] [编辑 btn-ghost] |
| .detail-grid | grid: 1fr 1fr; gap:16px; mb:20px |
| .detail-card | bg:surface; border:1px border; r:8px; pad:16 18; h3: 11px upper ls:0.06em faint/600 mb:12px |

#### Card 1: 健康度

|  |  |
| --- | --- |
| .health-big | flex gap:10; .dot 10×10 r:50%; .label 15px/600 color:success/warning/danger |
| .health-metrics | flex gap:24; 12px muted; strong: ink mono |

#### Card 2: 调度

|  |  |
| --- | --- |
| .schedule-big | flex gap:12; .expr: mono 14px bg:surface-2 pad:4 10 r:5 border:1px; .human: 13px muted |
| .schedule-next | 12px muted mt:8; strong ink |
| .schedule-tz | 11.5px faint mono mt:4 |

#### Card 3: 最近执行

|  |  |
| --- | --- |
| .recent-runs li | flex gap:12; pad:7 0; bb:1px border; 12px |
| .rr-time | muted w:50 mono 11px |
| .rr-status | 6×6 r:50%; .ok=success .fail=danger |
| .rr-code | mono 11px w:30 |
| .rr-duration | mono 11px muted |
| .view-all | center; pad:10; 12px signal; bt:1px border; mt:8; cursor:pointer |

#### Card 4: 配置信息

|  |  |
| --- | --- |
| .config-grid | grid: 100px 1fr; gap:8px; 12.5px |
| .cfg-label | 11px upper faint |
| .cfg-value | 12px mono ink; word-break:break-all |
| Fields | 请求地址 / 超时 / 业务组 / 创建人 / 创建时间 / 最后修改 |

### 3.2 响应式断点

| 断点 | 变化 |
| --- | --- |
| > 768px | detail-grid 2 列; header flex-row |
| < 768px | detail-grid 1 列 stack; .detail-header flex-col; .detail-actions 全宽; .detail-badges wrap |

### 3.3 交互状态

| 元素 | Default | Hover |
| --- | --- | --- |
| .breadcrumb a | color: signal | underline |
| .view-all | color: signal | underline |
| recent-runs li | bb: border | bg: surface-2 (subtle) |
| .btn-primary "立即执行" | bg: signal | bg: signal-ink |
| .btn "暂停" | border: border-strong; bg: surface | bg: surface-2 |
| .btn-ghost "编辑" | bg: transparent; border: transparent | bg: surface-2; color: ink |

## PAGE 04: Run Inspector（执行详情）

View ID
:   `#view-run-inspector` / `#view-run-failed`

路由
:   `GET /job_log_detail/<id>`

Content max-width
:   1200px

核心结构
:   Breadcrumb(3级) → run-header → run-meta → run-section×N

### 4.1 布局关键尺寸

| 元素 | 规格 |
| --- | --- |
| .run-header | flex gap:12; mb:20px; .run-id: mono 14px/600; .run-badge: 12px/600 pad:3 10 r:5 |
| .run-badge.ok | bg: success-bg; color: success |
| .run-badge.fail | bg: danger-bg; color: danger |
| .run-meta | flex gap:20; 12px muted; mb:20; strong: ink |
| .run-section | bg: surface; border: 1px border; r:8; mb:12; overflow:hidden |
| .run-section-head | flex gap:8; pad:10 16; 12px/600 faint upper ls:0.04em; bb:1px border; bg:surface-2 |
| .run-section-body | pad:14 16; mono 12px; line-height:1.7; color:muted; .key=signal-ink .str=success .num=warning |
| 失败特有 section | .run-section border-color:danger; .run-section-head color:danger bg:danger-bg; 内容含连续失败次数+最后成功时间 |

### 4.2 响应式断点

| 断点 | 变化 |
| --- | --- |
| > 768px | .run-meta 单行; sections 正常宽度 |
| < 768px | .run-meta flex-wrap; .run-section-body overflow-x: auto（长 JSON/URL） |

### 4.3 交互状态

| 状态 | 表现 |
| --- | --- |
| 成功执行 | .run-badge.ok; 正常 sections (请求/响应/业务日志/元数据) |
| 失败执行 | .run-badge.fail; 额外 .run-section(danger border) 在最上方; run-meta 显示 "错误" 字段(danger) |
| Loading | section body 区域 skeleton lines |

## PAGE 05: 任务表单（编辑/新建）

View ID
:   `#view-form` (编辑) / `#view-task-add` (新建)

路由
:   `GET /cron_edit/<id>` / `GET /cron_add`

Content max-width
:   **720px**（窄版表单）

核心结构
:   Breadcrumb → page-head → form-section×4 → actions

### 5.1 布局关键尺寸

| 区域 | 规格 |
| --- | --- |
| .form-section | bg:surface; border:1px border; r:10px; pad:20 22; mb:16px |
| .form-section-title | 12px/600 faint upper ls:0.05em; mb:16px |
| .form-group | mb:14px; label: 12.5px/500 mb:6px; .help: 11px muted mt:5px |
| input/select/textarea | w:100%; h:34px; pad:0 11; bg:surface; border:1px border-strong; r:6; 13px sans; textarea: h:auto min-h:70px pad:9 11 resize:vertical |
| .form-row | grid: 1fr 1fr; gap:14px |
| Cron 预设按钮组 | flex gap:6-8 mb:8 wrap; btn-ghost 11px pad:3 8 r:4; active: bg:signal-bg color:signal border:none |
| Cron 输入框 | mono 14px |
| Cron 提示行 | flex between mt:6; left: 11.5px muted "= 每 X 分钟"; right: 11px faint "下次: ..." |
| Lifecycle toggle | flex between; pad:12 14; bg:surface-2; r:8; toggle: 36×20 r:10 bg:signal; knob: 16×16 #fff r:50% absolute left:18px |
| Tags 输入 | flex gap:4 center; h:34; pad:0 8; border:1px border-strong r:6; .tag×N + "+ 添加" dashed signal |
| Form actions | flex gap:8; pt:4px; [保存修改/创建任务 btn-primary] [取消 btn-ghost] |

#### 新建 vs 编辑差异

| 差异点 | 新建 | 编辑 |
| --- | --- | --- |
| Breadcrumb | 任务中心 → 新建任务 | 任务中心 → 任务名 → 编辑配置 |
| h1 | "新建定时任务" | "编辑任务配置" |
| .sub | "配置触发 URL 和调度策略" | task-id (mono) |
| Lifecycle section | 无 | 有（含 toggle） |
| 业务组 | "仅显示你所属的业务组"（help 提示）; 当前用户组预选 | 可选所有组（admin 权限决定） |
| CTA | "创建任务" | "保存修改" |

### 5.2 响应式断点

| 断点 | 变化 |
| --- | --- |
| > 768px | .form-row 2 列; max-width 720px 居左 |
| < 768px | .form-row → 1 列 stack; breadcrumb wrap; Cron 预设按钮 wrap |

### 5.3 交互状态

| 元素 | Default | Focus | Error |
| --- | --- | --- | --- |
| input/select/textarea | border: border-strong | border: signal; box-shadow: 0 0 0 3px signal-bg | .has-error: border: danger; bg: danger-bg; .error-msg 11px danger |
| .toggle (Lifecycle) | bg: signal (on); knob left:18px | — | off: bg: border-strong; knob left:2px |
| Cron 预设 btn | btn-ghost style | — | selected: bg:signal-bg color:signal |
| "+ 添加" tag | dashed border; color: signal | bg: signal-bg | — |

## PAGE 06: 用户管理列表

View ID
:   `#view-users`

路由
:   `GET /rbac/users`

Content max-width
:   1200px

表头 (9列)
:   用户 | 花名 | 岗位 | 角色 | 业务组 | 状态 | 密码状态 | 创建时间 | 操作(180px)

### 6.1 布局关键尺寸

| 元素 | 规格 |
| --- | --- |
| page-head | h1 "用户管理"; .sub "6 名成员 · 3 个业务组"; CTA "添加用户" btn-primary |
| filters chips | [全部 6(active)] [启用 5] [停用 1] | spacer | [角色▾] [业务组▾] |
| 用户列 td | flex gap:10; .avatar 26×26 r:50% bg:signal-bg color:signal-ink 11px/600; name 13px/500; email mono 11px faint |
| 花名列 | 12px |
| 岗位列 | 12px muted |
| 角色 badge | .lifecycle; 管理员: signal-bg/signal; 运维: success-bg/success; 观察者: surface-2/muted |
| 业务组 | 12px muted; 多组逗号分隔 |
| 状态 | .health; 启用: healthy; 停用: faint dot + "停用" |
| 密码状态 | 正常: 11px success; 待重置: 11px/500 warning; 停用用户: "—" faint |
| 创建时间 | 11px faint |
| 操作列 (180px) | flex gap:4 wrap; [重置密码 btn-sm 11px h:24 pad:0 8] [停用 btn-sm] [编辑 action-btn icon]; 停用用户仅 [查看 eye icon] |
| 停用行 | tr: opacity 0.6; avatar bg:surface-2 color:faint |
| Footer hint | mt:10px; 11.5px faint; "💡 无物理删除；停用不可恢复..." |

### 6.2 响应式断点

| 断点 | 变化 |
| --- | --- |
| > 1200px | 9 列全显 |
| 1024–1200px | "密码状态""创建时间"列可隐藏或 ellipsis |
| < 768px | table overflow-x: auto; 隐藏"岗位""密码状态""创建时间"列 |

### 6.3 交互状态

| 元素 | Default | Hover |
| --- | --- | --- |
| "添加用户" CTA | btn-primary | bg: signal-ink |
| 操作 btn-sm | border: border-strong; bg: surface; 11px h:24 | bg: surface-2 |
| 编辑 action-btn | 标准 action-btn | bg: surface-2; border: border |

## PAGE 07: 用户表单（添加/编辑）

View ID
:   `#view-user-add` / `#view-user-edit`

Content max-width
:   **640px**

核心结构
:   Breadcrumb → page-head → form-section(基本信息) → form-section(权限配置) → [danger-zone(编辑)] → actions

### 7.1 添加用户规格

| Section | 字段 | 规格 |
| --- | --- | --- |
| 基本信息 | 用户名 \* | input; placeholder "如 zhangsan"; .form-row 左列 |
| 邮箱 | input type=email; .help "可选；留空则用户首次登录后补填"; .form-row 右列 |
| 花名 / 岗位类型 | .form-row; 岗位=select(未设置/后端/前端/运维/数据/产品/其他); .help "可选" |
| 初始密码 | 不可编辑；显示 `changeme` mono 14px/600 + 说明文案 11.5px muted |
| 权限配置 | 角色 \* | select: [观察者(default)] [运维] [管理员]; .help 说明 |
| 业务组 \* | select multiple size=4 min-h:70px; .help "Ctrl/Command 可多选"; 末尾选项"全部（全局权限）" |

### 7.2 编辑用户规格（增量）

| 差异 | 规格 |
| --- | --- |
| 用户名 disabled | opacity:0.6; cursor:not-allowed; .help "用户名创建后不可更改" |
| 安全操作 section | [重置密码 btn-sm] [重置 API Token btn-sm]; .help 说明 mt:8 |
| .danger-zone | bg: danger-bg; border: 1px rgba(214,69,69,0.25); r:10; pad:18 22; .dz-title 13px/600 danger; .dz-desc 12px muted line-height:1.6 mb:14; btn-danger btn-sm "停用此账户" |

### 7.3 响应式断点

| 断点 | 变化 |
| --- | --- |
| > 640px | .form-row 2 列 |
| < 640px | .form-row 1 列 stack; 所有 input 全宽 |

## PAGE 08: 业务组

View ID
:   `#view-groups` / `#view-group-add`

路由
:   `GET /rbac/groups`

Content max-width
:   1200px

核心结构
:   page-head → 3列 Card Overview → Group Detail (展开态)

### 8.1 布局关键尺寸

| 元素 | 规格 |
| --- | --- |
| page-head | h1 "业务组"; .sub "资源 Scope 管理 · 3 个活跃组"; CTA "新建业务组" |
| Card Grid | grid: repeat(3,1fr); gap:12px; mb:28px |
| Group Card | bg:surface; border:1px border; r:8; pad:16; cursor:pointer; 选中态: border-color:signal |
| Card title | 14px/600; mb:4px |
| Card desc | 12px muted; mb:12px |
| Card stats | flex gap:16; 12px muted; bt:1px border; pt:10px; strong ink; 异常 strong danger |
| Detail Panel | bg:surface; border:1px border; r:10; overflow:hidden |
| Panel Header | pad:16 20; bb:1px; flex between; title 16px/600; desc 12px muted mt:2; btn-sm "编辑" |
| Panel Content Grid | grid: 1fr 1fr; bb:1px border |
| Members section | pad:16 20; border-right; h: 11px upper faint/600 ls:0.05em mb:12; items: flex col gap:10; each: avatar + name(500) + role(11px faint) |
| Permissions section | pad:16 20; list: flex col gap:6 12px; green dot = allowed; faint dot = restricted |
| Tasks section | pad:16 20; h: "任务 (N) · M 异常"; items: flex gap:12 12.5px pad:6 0 bb; .view-all center 12px signal |

### 8.2 新建业务组表单

|  |  |
| --- | --- |
| max-width | 560px |
| Fields | 组名称(required) + 描述(textarea); .help "建议使用「团队名+组」..." |
| Actions | [创建业务组 btn-primary] [取消 btn-ghost] |

### 8.3 响应式断点

| 断点 | 变化 |
| --- | --- |
| > 768px | Card Grid 3 列; Detail Panel 2列 content grid |
| < 768px | Card Grid 1 列 stack; Detail Panel content grid 1列 stack (Members 在 Permissions 上方) |

## PAGE 09: 注册审批

View ID
:   `#view-reg-review`

路由
:   `GET /rbac/reg_review`

Content max-width
:   1200px

表头 (9列)
:   邮箱 | 用户名 | 花名 | 岗位 | 申请角色 | 业务组 | 申请原因 | 申请时间 | 操作(140px)

### 9.1 布局关键尺寸

| 元素 | 规格 |
| --- | --- |
| filters chips | [待审核 3(active)] [已通过] [已拒绝] [已过期]（无 search bar） |
| 邮箱列 | mono 11.5px muted |
| 用户名列 | 12px/500 |
| 花名列 | 12px |
| 岗位列 | 12px muted |
| 申请角色 | .lifecycle badge（管理员: signal; 运维: success; 观察者: surface-2/muted） |
| 业务组列 | 12px muted |
| 申请原因列 | 12px muted; max-w:160px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; title tooltip |
| 申请时间列 | mono 11px faint; white-space:nowrap |
| 操作列 | flex gap:6; [✓ 批准 btn-sm btn-primary 12px] [✗ 拒绝 btn-sm color:danger border:danger 12px] |

### 9.2 响应式断点

| 断点 | 变化 |
| --- | --- |
| > 1024px | 全列显示 |
| < 1024px | table overflow-x:auto; "申请原因"max-w 缩至 100px; "邮箱""岗位"列可隐藏 |

## PAGE 10: 审计日志

View ID
:   `#view-audit`

路由
:   `GET /rbac/audit`

Content max-width
:   1200px

表头 (6列)
:   时间 | 用户名 | 动作 | 说明 | 来源 IP | 结果

### 10.1 布局关键尺寸

| 元素 | 规格 |
| --- | --- |
| page-head .sub | "RBAC 身份与权限事件（登录/登出、用户管理、权限拒绝）" |
| filters chips | search + [全部(active)] [登录成功] [登录失败] [权限拒绝] [用户管理] |
| 时间列 | mono 11.5px muted; white-space:nowrap |
| 用户名列 | 12.5px/500; 失败行: color: danger |
| 动作 badge | .lifecycle; 角色变更/登录成功=signal/success; 登录失败=danger-bg+danger+border:danger; 权限拒绝=warning-bg/warning |
| 说明列 | 12px; 含  `标签(bg:surface-2 pad:1 4 r:2 11px); strong 用于人名` |
| 来源 IP | mono 11px faint; 失败行: danger |
| 结果列 | "允许": 11px success/500; "拒绝": 11px danger/500-600 |
| 失败行 tr | bg: danger-bg |
| Footer hint | "💡 任务配置变更（创建/编辑/启停/下线）请到「操作记录」页查看。" |

## PAGE 11: 操作记录

View ID
:   `#view-optlog`

路由
:   `GET /optlog`

Content max-width
:   1200px

表头 (7列)
:   操作人 | 操作类型 | 操作对象 | 变更详情 | 操作结果 | 时间 | 来源 IP

### 11.1 布局关键尺寸

| 元素 | 规格 |
| --- | --- |
| page-head .sub | "任务配置变更审计（创建 / 编辑 / 启动 / 暂停 / 下线）" |
| Filters（非 chip） | flex gap:8 wrap mb:16; input(200×32 12px) + select 操作类型(32h) + select 时间范围(32h) |
| 操作人列 | 12.5px/500 |
| 操作类型 badge | .lifecycle; 修改配置/立即执行/暂停=signal; 下线=danger; 新建/创建=success |
| 操作对象列 | task-id: mono 12px ink; desc: 11px faint ("任务 · 交易平台组") |
| 变更详情列 | 12px muted; Cron 变更: old  `→ new` |
| 操作结果 | "✓ 成功" success 12px |
| 时间列 | mono 11.5px muted; nowrap |
| 来源 IP | mono 11px faint |
| Pagination | flex between mt:14; 12px muted; btn-ghost 28×28 pagination btns; active: bg:signal color:#fff border:signal |

## PAGE 12: 标签管理

View ID
:   `#view-tags`

路由
:   `GET /tags`

Content max-width
:   1200px

核心结构
:   page-head → namespace groups × N（非表格布局）

### 12.1 布局关键尺寸

| 元素 | 规格 |
| --- | --- |
| page-head | h1 "标签管理"; .sub "按命名空间组织的任务标签"; CTA "新建标签" |
| Namespace block | mb:24px |
| Namespace title | 12px/600 faint upper ls:0.05em mb:10; flex gap:8; icon svg 13×13 |
| Tag pills container | flex; flex-wrap; gap:8px |
| Normal tag pill | inline-flex gap:8; pad:7 14; bg:surface; border:1px border; r:20px; 12.5px; count-badge: bg:surface-2 color:muted 10.5px pad:1 6 r:8 |
| Priority P0 pill | bg:danger-bg; border:rgba(214,69,69,0.2); color:danger/500; count bg:rgba(214,69,69,0.15) |
| Priority P1 pill | bg:warning-bg; border:rgba(183,121,31,0.2); color:warning/500; count bg:rgba(183,121,31,0.15) |
| Namespaces | 业务域 / 优先级 / 生命周期 / 区域 |

### 12.2 响应式断点

| 断点 | 变化 |
| --- | --- |
| > 768px | pill 正常 flex-wrap |
| < 768px | pills 可能 wrap 到 2-3 行; namespace title 全宽 |

## PAGE 13: 修改密码

View ID
:   `#view-password`

路由
:   `GET /rbac/change_pwd`

Content max-width
:   **480px**

核心结构
:   page-head → single card form → security tip

### 13.1 布局关键尺寸

| 元素 | 规格 |
| --- | --- |
| Card | bg:surface; border:1px border; r:10; pad:24px |
| Form groups | mb:18px; label 12.5px/500 mb:6; input h:36 pad:0 12; 13px sans |
| .input-with-toggle | position:relative; input padding-right:36px!important |
| .toggle-vis | absolute right:8; top:50% translateY(-50%); 24×24 r:4; bg:none; border:none; color:faint; hover: ink bg:surface-2; svg 14×14 |
| .password-strength | flex gap:3; mt:6; .bar: flex:1 h:3 r:2 bg:border; .weak=danger; .medium=warning; .strong=success |
| .password-strength-text | 10px mt:3 /500; color:warning (dynamic) |
| Password help | 11px muted mt:5 "密码要求：至少 6 位，且不能与当前密码相同" |
| Submit btn | btn-primary w:100% justify:center |
| Security tip box | mt:14; pad:12; bg:surface-2; r:6; 11.5px muted lh:1.6; strong ink |

### 13.2 交互状态

| 状态 | 表现 |
| --- | --- |
| Password toggle ON | input type=text; eye icon swap to eye-off |
| Strength: 弱 | 1/4 bar weak(danger); text "强度不足" danger |
| Strength: 中等 | 3/4 bars (2 weak + 1 medium); text "中等强度" warning |
| Strength: 强 | 4/4 bars strong(success); text "强度足够" success |
| Passwords mismatch | .has-error on confirm input; .error-msg "密码不一致" |

## PAGE 14: API Token

View ID
:   `#view-api-token`

路由
:   `GET /rbac/api_token`

Content max-width
:   **640px**

核心结构
:   page-head → current token card → usage card → reset action → rules card

### 14.1 布局关键尺寸

| 区域 | 规格 |
| --- | --- |
| Current Token Card | bg:surface; border:1px; r:10; pad:24; mb:16 |
| Token display | flex gap:10; mb:12; mono 13px pad:10 14 bg:surface-2 border r:6 ls:0.02em word-break:break-all; + [复制 btn-sm] |
| Token meta | flex gap:16; 12px muted; strong ink; "创建时间: / 权限:" |
| Usage Card | 同上结构; code block: mono 12px pad:14 bg:canvas border r:6 lh:1.7 muted; .faint=comments .success=strings .signal-ink=urls |
| Reset action | flex gap:8 mb:16; btn-danger(transparent bg, danger border/color); warning text 11.5px muted flex center |
| Rules Card | bg:surface; border; r:10; pad:20 24; ul: pad-left:16 12.5px muted lh:2 |

## PAGE 15: API 文档

View ID
:   `#view-apidoc`

路由
:   `GET /docs/api`

Content max-width
:   1200px

核心结构
:   page-head → Endpoint cards (accordion)

### 15.1 布局关键尺寸

| 元素 | 规格 |
| --- | --- |
| Endpoint container | flex col; gap:10px |
| Endpoint Card (collapsed) | bg:surface; border:1px border; r:8; overflow:hidden |
| Card header row | flex gap:10; pad:12 16; cursor:pointer |
| Method badge | mono 10.5px/600 pad:2 7 r:4; GET: success-bg/success; POST: signal-bg/signal-ink |
| Path | mono 12.5px/500 |
| Description | 12px muted (right side, spacer between) |
| Expanded Card | border-color: signal; header bg: signal-bg; bb:1px border |
| Expanded body | pad:16; Parameters section + Response Example section |
| Parameters | h: 11px upper faint/600 mb:8; mono 12px lh:2; param-name: ink/500; type: faint; desc: — separated |
| Response block | mono 11.5px pad:12 bg:canvas border r:6 lh:1.6 muted; key:signal-ink num:warning |

### 15.2 交互状态

| 状态 | 表现 |
| --- | --- |
| Collapsed card | 单行 header; border: border |
| Hover (collapsed) | bg: surface-2 (header row) |
| Expanded card | border: signal; header bg: signal-bg; body visible below |

## PAGE 16: 登录 / 注册 / 忘记密码

View ID
:   `#login-page` / `#register-page` / `#forgot-page`

路由
:   `GET /rbac/login` / `GET /rbac/register`

类型
:   Standalone 全屏（无 Shell/Sidebar）

布局
:   min-h:100vh; flex center center; bg: canvas; pad:20px

### 16.1 登录页

| 元素 | 规格 |
| --- | --- |
| Container | w:380px; bg:surface; border:1px border; r:12; pad:36 30 |
| Brand | flex gap:8; 15px/600; mb:28; .dot 9×9 r:2 bg:signal |
| Title | "欢迎回来" 17px/600 mb:4; subtitle 12.5px muted mb:24 |
| Username field | mb:16; label 12.5px/500 mb:6; input h:38 pad:0 12 r:6 13px; .help 11px faint mt:5 |
| Password field | mb:20; label: flex between(label + "忘记密码?" link signal 11.5px); .input-with-toggle h:38 |
| Submit btn | btn-primary w:100% h:38 center 14px |
| Register link | mt:20; center 12px muted; "申请注册" signal/500 |
| Reg status (hidden) | mt:14; pad:10 14; bg:warning-bg; border:rgba(183,121,31,0.2); r:6; 12px warning |

### 16.2 注册页

| 元素 | 规格 |
| --- | --- |
| Container | w:440px; bg:surface; border:1px border; r:12; pad:32 28 |
| Title | "申请注册" 17px/600; subtitle "提交注册申请后，管理员将进行审核" 12.5px muted mb:22 |
| Fields | 公司邮箱\* / grid(花名\*,岗位类型\*) / grid(密码\*,确认密码\*) / grid(申请角色\*,目标业务组\* checkbox list) / 申请原因\* textarea h:70 |
| 业务组选择器 | border:1px border-strong; r:6; pad:8 10; max-h:80 overflow-y:auto; 12.5px; checkbox + label items mb:4 |
| Submit | "提交申请" btn-primary w:100% center |
| Login link | mt:14; center 12px muted; "返回登录" signal/500 |

### 16.3 忘记密码页

| 元素 | 规格 |
| --- | --- |
| Container | w:380px; r:12; pad:36 30; text-align:center |
| Icon | svg 48×48 faint stroke-w:1.5; mb:16 |
| Title | "忘记密码？" 17px/600 mb:8 |
| Description | 13px muted lh:1.7 mb:24; 说明不支持自助重置 |
| Help box | bg:surface-2; border:1px border; r:8; pad:14; 12.5px muted lh:1.6; text-align:left; strong ink; 步骤列表 |
| Back link | mt:20; signal 13px/500 "← 返回登录" |

### 16.4 响应式断点

| 断点 | 变化 |
| --- | --- |
| > 480px | Container 固定宽度居中 |
| < 480px | Container w:100%; pad 缩减; 注册页 grid 变 1 列 |

## OVERLAY: Command Palette / Toast / Modal

### OV.1 Command Palette (⌘K)

| 元素 | 规格 |
| --- | --- |
| .cmd-overlay | fixed inset:0; bg:rgba(0,0,0,0.5); z:100; flex; pt:15vh; center |
| .cmd-box | w:520px; bg:surface; border:1px border; r:12; box-shadow:0 16px 48px rgba(0,0,0,0.3); overflow:hidden |
| .cmd-input | flex gap:10; pad:14 16; bb:1px border; svg 16×16 muted; input: no-border bg:transparent 14px ink; flex:1 |
| .cmd-results | max-h:360px; overflow-y:auto; pad:8px |
| .cmd-group | pad:6 8; 10px faint upper ls:0.06em /600 |
| .cmd-item | flex gap:10; pad:8 10; r:6; 13px; cursor:pointer; hover:bg surface-2 |
| .ci-icon | 20×20 flex center; color:muted; svg 14×14 |
| .ci-name | flex:1 |
| .ci-health | 11px/500; color: success/danger |
| .ci-meta | 11px faint |
| .cmd-footer | flex gap:12; pad:8 16; bt:1px border; 11px faint; kbd: mono 10px border r:3 pad:1 4 bg:surface-2 |

### OV.2 Toast Notifications

| 元素 | 规格 |
| --- | --- |
| .toast-container | fixed top:16 right:16 z:200; flex col gap:8 |
| .toast | flex gap:10; pad:12 16; bg:surface; border:1px border; r:8; box-shadow:0 4px 16px rgba(0,0,0,0.12); 13px; min-w:280px; animation:slideIn 0.2s ease-out |
| .toast.success | border-left: 3px solid success |
| .toast.error | border-left: 3px solid danger |
| .toast.warning | border-left: 3px solid warning |
| .toast-icon | 16×16 flex-shrink:0 |
| .toast-close | color:faint; cursor:pointer; 16px |

### OV.3 Modal (确认弹窗)

| 元素 | 规格 |
| --- | --- |
| .modal-overlay | fixed inset:0; bg:rgba(0,0,0,0.5); z:150; flex center center; pad:20 |
| .modal | bg:surface; border:1px border; r:12; w:100% max-w:480px; box-shadow:0 16px 48px rgba(0,0,0,0.2); overflow:hidden |
| .modal-header | flex between center; pad:18 22; bb:1px border; h2: 15px/600 m:0 |
| .modal-body | pad:22 |
| .modal-footer | flex end gap:8; pad:14 22; bt:1px border; bg:surface-2 |
| Actions (下线) | [取消 btn-ghost] [确认下线 btn-danger] |
| Actions (停用) | [取消 btn-ghost] [确认停用 btn-danger] |
| Warning box | bg:danger-bg; border:1px rgba(214,69,69,0.2); r:6; pad:12; 12px danger lh:1.6-1.7 |

## SPECIAL STATES: Empty / Loading / Error

### ST.1 Empty State

| 元素 | 规格 |
| --- | --- |
| .empty-state | flex col center center; pad:60 20; text-align:center |
| Icon | svg 48×48 color:faint; mb:16; opacity:0.6 |
| .empty-title | 15px/600 mb:6; color:ink |
| .empty-desc | 12.5px muted max-w:300 mb:16 |
| CTA | btn-primary; icon + text |
| Context | Dashboard empty: stats 全 0(faint); .total 改为 "一切正常"/"无活跃任务"/"—" |

### ST.2 Loading / Skeleton

| 元素 | 规格 |
| --- | --- |
| .skeleton | bg: linear-gradient(90deg, surface-2 25%, border 50%, surface-2 75%); bg-size:200% 100%; animation:shimmer 1.5s infinite; r:4 |
| .skeleton-line | h:12px mb:10px r:4; .short w:40%; .medium w:70% |
| Table skeleton | Header row: 5 skeleton bars(120/160/60/40/60 × 14px) flex gap:14; Body: 4 rows × 5 bars(varying widths × 12px + 1 badge 50×20 r:10) |

### ST.3 Error Page

| 元素 | 规格 |
| --- | --- |
| Layout | .empty-state pad:100 20 |
| Error code | mono 56px/700 faint; ls:-0.03em; mb:8 (如 "403") |
| .empty-title | "无权访问" / "页面不存在" / "服务异常" |
| .empty-desc | 具体说明 + 建议操作 |
| Actions | flex gap:8; [返回首页 btn-primary] [联系管理员 btn-ghost] |

---

## 附录：全局共享规格速查

| Token | Light | Dark |
| --- | --- | --- |
| --canvas | #F7F8F9 | #0D0F12 |
| --surface | #FFFFFF | #16191D |
| --surface-2 | #F1F2F4 | #1C2025 |
| --border | #E4E6E9 | #262B31 |
| --border-strong | #D3D6DA | #34393F |
| --ink | #14171A | #ECEEF0 |
| --muted | #5B6169 | #8B9198 |
| --faint | #9CA3AF | #565C64 |
| --signal | #3D6FE0 | #4C8DFF |
| --signal-ink | #2F5FCB | #7DAAFF |
| --signal-bg | rgba(61,111,224,0.09) | rgba(76,141,255,0.12) |
| --success | #0F9D66 | #34D399 |
| --warning | #B7791F | #F5A623 |
| --danger | #D64545 | #F16565 |
| --mono | 'JetBrains Mono','SFMono-Regular',Consolas,monospace | |
| --sans | 'Inter','Helvetica Neue',Arial,sans-serif | |
| --shadow | 0 1px 2px rgba(20,23,26,0.04) | none |

| 全局组件 | 高度 | 字号 | 圆角 |
| --- | --- | --- | --- |
| .btn (default) | 32px | 13px/500 | 6px |
| .btn-sm | 26px | 12px | 5px |
| .chip | 28px | 12px | 6px |
| .search | 32px | 12.5px | 6px |
| input/select (form) | 34px | 13px | 6px |
| input (login page) | 38px | 13px | 6px |
| .action-btn | 26×26px | — | 5px |
| .pg-btn | 28×28px | 12px/500 | 5px |
| .avatar | 26×26px | 11px/600 | 50% |
| .tag | auto | 10px | 3px |
| .lifecycle badge | auto | 10px/500 | 3px |

| Shell 规格 | 值 |
| --- | --- |
| Sidebar 宽度 | 220px (展开); 56px (collapsed) |
| Topbar 高度 | 52px; position:sticky top:0 z:20 |
| .main padding | 24px 32px 60px |
| .nav-item | pad:7 10; r:6; 13px; gap:10; border-left:2px transparent; .active: bg:signal-bg border-left:signal |
| .nav-badge | ml:auto; bg:danger-bg color:danger; 10px/600; pad:1 6; r:10 |
| .top-search | 260×30px; r:6; bg:surface; border:border; 12.5px muted; .kbd mono 10px faint border pad:1 5 |
| .icon-btn | 30×30; r:6; color:muted; hover: bg:surface-2 border:border color:ink |
| .theme-toggle | border:1px border; r:6; pad:2; gap:2; button 26×24 r:4; .on: bg:surface-2 color:ink |
| .user-chip | flex gap:8; pad:4 8 4 4; r:20; border:transparent; hover: bg:surface-2 border:border |

## 附录 C: 动画与过渡效果规格

### C.1 全局过渡 (Global Transitions)

| 触发场景 | 属性 | 持续时间 | 缓动函数 | 备注 |
| --- | --- | --- | --- | --- |
| .nav-item hover/active | background, color, border-left-color | 100ms | ease (CSS transition:all .1s) | 侧边栏导航项状态切换 |
| .btn hover | background-color | 150ms | ease | 所有按钮 hover 变色 |
| .action-btn hover | background, border-color, color | 100ms | ease | 图标按钮快速反馈 |
| tbody tr:hover | background-color | 100ms | ease | 表格行 hover 高亮 |
| .chip active toggle | border-color, background, color | 150ms | ease | 筛选 chip 激活/取消 |
| input:focus | border-color, box-shadow | 150ms | ease | 输入框聚焦环 |
| .user-chip:hover | background, border-color | 100ms | ease | 顶栏用户信息 hover |
| .icon-btn:hover | background, border-color, color | 100ms | ease | 顶栏图标按钮 |

### C.2 关键帧动画 (Keyframe Animations)

| 动画名 | 目标 | 关键帧 | 持续/循环 |
| --- | --- | --- | --- |
| `@keyframes slideIn` | .toast 出现 | from: translateX(100%) opacity:0 → to: translateX(0) opacity:1 | 200ms ease-out; 一次 |
| `@keyframes shimmer` | .skeleton 骨架屏 | from: background-position 200% 0 → to: -200% 0 | 1500ms infinite; linear |
| `@keyframes fadeIn` (建议) | .modal-overlay 出现 | from: opacity:0 → to: opacity:1 | 200ms ease-out; 一次 |
| `@keyframes scaleIn` (建议) | .modal / .cmd-box 出现 | from: transform scale(0.95) opacity:0 → to: scale(1) opacity:1 | 200ms cubic-bezier(0.16,1,0.3,1); 一次 |
| `@keyframes slideUp` (建议) | Toast 消失 | from: translateX(0) opacity:1 → to: translateX(100%) opacity:0 | 150ms ease-in; 一次 |

### C.3 页面视图切换

| 场景 | 动画 | 规格 |
| --- | --- | --- |
| SPA 视图切换（nav item click） | Crossfade | 旧 view: opacity 1→0 (100ms); 新 view: opacity 0→1 (150ms); 总感知 ~150ms |
| 侧边栏 collapse/expand (响应式) | Width transition | width: 220px ↔ 56px; transition: width 200ms ease; .nav-item text opacity: 0/1 transition 100ms |
| Exception panel expand/collapse (如筛选) | Height + opacity | max-height: 0→auto (200ms); opacity: 0→1 (150ms); overflow:hidden |
| Dropdown menu (user-chip) | Scale + fade | transform-origin: top right; scaleY 0.9→1 + opacity 0→1; 150ms ease-out |
| Command Palette open | Overlay fade + box scale | overlay: opacity 0→1 (150ms); .cmd-box: scaleY(0.97)→1 + opacity 0→1 (200ms cubic-bezier) |
| Command Palette close | Reverse | overlay: opacity 1→0 (100ms); .cmd-box: opacity 1→0 (100ms) |

### C.4 交互微动画

| 元素 | 动画 | 触发 | 规格 |
| --- | --- | --- | --- |
| Toggle switch (Lifecycle) | Knob slide | 点击 | knob left: 2px ↔ 18px; bg: border-strong ↔ signal; transition: all 200ms ease |
| Password strength bars | Width grow | 输入时 | 各 .bar width: 0→100%; stagger delay: 0/50/100/150ms; transition: all 300ms ease-out |
| .health .dot | Pulse (异常时) | 持续 | .failing .dot: animation: pulse 2s infinite; @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} } |
| Pagination .pg-btn.active | Background fill | 切换页码 | background + border-color transition 150ms ease |
| .tag "添加" hover | Background fill | hover | bg: transparent → signal-bg; transition 100ms |
| Toast auto-dismiss | Slide out + fade | 4s 后自动 | delay 4000ms → slideUp 150ms ease-in → remove from DOM |
| .tooltip appear | Opacity | hover (150ms delay) | opacity: 0→1; transition: opacity 150ms; 需 hover 150ms 后才显示 |

### C.5 Motion Design Principles

| 原则 | 说明 |
| --- | --- |
| 响应性（Responsive） | 所有 hover/focus 反馈 ≤ 100ms，用户感知为即时 |
| 自然性（Natural） | UI 元素出现使用 ease-out（减速进入）；消失使用 ease-in（加速退出） |
| 克制性（Restrained） | 仅对用户关注的元素做动画；表格数据、文本内容无装饰性动画 |
| 可预测性（Predictable） | 同类交互使用相同的动画曲线和时长；modal/cmd/toast 同族 |
| 性能优先（Performant） | 只 animate transform/opacity（GPU 加速）；避免 layout thrash（如 height/width 动画用 max-height 模拟或 FLIP） |
| Reduce motion | `@media (prefers-reduced-motion: reduce)`: 所有 animation: none; transition-duration: 0.01ms |

## 附录 D: 无障碍与 ARIA 规格

### D.1 颜色对比度要求 (WCAG 2.1 AA)

| 场景 | 前景 | 背景 | 对比度 | 最低要求 |
| --- | --- | --- | --- | --- |
| 正文文本 (--ink on --surface) | #14171A | #FFFFFF | 18.3:1 | 4.5:1 ✓ |
| 辅助文本 (--muted on --surface) | #5B6169 | #FFFFFF | 5.8:1 | 4.5:1 ✓ |
| 次要文本 (--faint on --surface) | #9CA3AF | #FFFFFF | 2.6:1 | 3:1 (大文本) ⚠️ 仅用于装饰性/非关键信息 |
| Signal on surface (link/CTA) | #3D6FE0 | #FFFFFF | 4.6:1 | 4.5:1 ✓ (勉强通过) |
| Success text | #0F9D66 | #FFFFFF | 3.4:1 | 3:1 (大文本/图标) ✓ |
| Danger text | #D64545 | #FFFFFF | 4.0:1 | 3:1 (需辅助图标) ⚠️ |
| Dark: ink on surface | #ECEEF0 | #16191D | 13.6:1 | 4.5:1 ✓ |
| Dark: muted on surface | #8B9198 | #16191D | 5.4:1 | 4.5:1 ✓ |

#### 颜色无障碍策略

- **不仅靠颜色传递信息**：所有状态色 (success/warning/danger) 须辅以图标（dot/✓/×/⚠）或文字标签
- Health 状态：dot + 文字 "健康"/"异常"/"×N"
- 表单校验：border-color 变化 + 错误文字 + icon
- Toast 通知：border-left + icon + 文字描述

### D.2 键盘导航 (Keyboard Navigation)

| 区域 | Tab 顺序 | 快捷键 | 说明 |
| --- | --- | --- | --- |
| 全局 | Skip link → Sidebar → Topbar → Main | `⌘K` / `Ctrl+K` | 任何位置打开 Command Palette |
| Sidebar nav | 顺序 Tab 所有 .nav-item | `↑↓` | 焦点在 sidebar 时可用箭头键移动; Enter 激活 |
| Table rows | Tab 到表格 → 箭头键行间移动 | `↑↓` rows; `Enter` 打开详情 | 焦点行应有 visible focus ring |
| Filters (.chip) | Tab 进入 chip 组 | `←→` 切换 chip; `Enter/Space` 激活 | radio group 语义 |
| Pagination | Tab 到 pg-nav | `←→` 切换页码; `Enter` 跳转 | aria-label="分页" |
| Command Palette | 自动 focus input | `↑↓` 项间导航; `Enter` 选中; `Esc` 关闭 | trap focus in overlay |
| Modal | 自动 focus 第一个 interactive | `Esc` 关闭; `Tab` trap in modal | 关闭时 focus 返回触发元素 |
| Forms | 正常 Tab 顺序 | `Enter` submit (单行 input) | 错误 focus 到第一个 invalid 字段 |

### D.3 ARIA 属性规格

| 组件 | Role / Attribute | 说明 |
| --- | --- | --- |
| #app-shell | `role="application"` | SPA 根容器 |
| .sidebar | `role="navigation" aria-label="主导航"` | 侧边栏导航区 |
| .nav-item.active | `aria-current="page"` | 标识当前页 |
| .nav-badge | `aria-label="3 个待处理"` | 数字 badge 可读标签 |
| .topbar | `role="banner"` | 顶栏 |
| .top-search / .cmd-trigger | `role="button" aria-haspopup="dialog" aria-label="搜索 ⌘K"` | Command Palette 触发器 |
| .cmd-overlay | `role="dialog" aria-modal="true" aria-label="命令面板"` | 模态对话框 |
| .cmd-input input | `role="combobox" aria-expanded="true" aria-controls="cmd-results" aria-activedescendant="..."` | 搜索 combobox 模式 |
| .cmd-results | `role="listbox" id="cmd-results"` | 搜索结果列表 |
| .cmd-item | `role="option" id="cmd-item-N"` | 搜索结果项 |
| .chip 组 | `role="radiogroup" aria-label="状态筛选"` | 互斥筛选 |
| .chip | `role="radio" aria-checked="true/false"` | 单个筛选项 |
| .table-wrap table | `role="table"` (原生语义) | 数据表格 |
| 排序列头 th (如将来添加) | `aria-sort="ascending/descending/none"` | 排序状态 |
| .action-btn | `aria-label="立即执行" / "暂停" / "更多操作"` | 无文字的图标按钮必须有 aria-label |
| .modal-overlay | `role="dialog" aria-modal="true" aria-labelledby="modal-title"` | 确认弹窗 |
| .toast | `role="alert" aria-live="assertive"` | 紧急通知（error）; `aria-live="polite"` for success |
| .toggle-vis (密码) | `aria-label="显示密码" / "隐藏密码" aria-pressed="true/false"` | toggle 按钮 |
| .password-strength | `role="meter" aria-valuemin="0" aria-valuemax="4" aria-valuenow="N" aria-label="密码强度"` | 密码强度指示器 |
| .pagination | `nav aria-label="分页导航"` | 分页容器 |
| .pg-btn.active | `aria-current="page"` | 当前页码 |
| .pg-btn.disabled | `aria-disabled="true"` | 不可点击 |
| .empty-state | `role="status" aria-label="暂无数据"` | 空状态区域 |
| .skeleton (loading) | `aria-busy="true" aria-label="加载中"` | 加载占位 |
| form .error-msg | `role="alert" aria-live="polite"` | 表单即时错误 |
| form input (error) | `aria-invalid="true" aria-describedby="error-msg-id"` | 关联错误信息 |
| form label + input | `<label for="input-id">` | 所有输入必须 label 关联 |
| required 字段 | `aria-required="true"` + visual `*` | 必填标记 |
| .breadcrumb | `nav aria-label="面包屑"`; last item: `aria-current="page"` | 面包屑导航 |
| Theme toggle | `role="radiogroup" aria-label="主题切换"`; button: `role="radio" aria-checked` | 浅色/深色切换 |

### D.4 Focus 可见性规格

| 元素类型 | Focus ring 样式 |
| --- | --- |
| 按钮 (.btn, .action-btn, .pg-btn) | `outline: 2px solid var(--signal); outline-offset: 2px;` |
| 输入框 (input, select, textarea) | `border-color: var(--signal); box-shadow: 0 0 0 3px var(--signal-bg);` (已在 CSS 中定义) |
| 链接 (.task-name, .breadcrumb a, .view-all) | `outline: 2px solid var(--signal); outline-offset: 1px; border-radius: 2px;` |
| Chip (.chip) | `outline: 2px solid var(--signal); outline-offset: 1px;` |
| Nav item (.nav-item) | `outline: 2px solid var(--signal); outline-offset: -2px;` (内缩适配 border-left) |
| Modal 内元素 | 同上对应类型 |

#### :focus-visible vs :focus

- 使用 `:focus-visible` 而非 `:focus`，仅键盘导航时显示 focus ring
- Fallback: `:focus:not(:focus-visible) { outline: none; }`
- 对 `.action-btn` 等纯鼠标操作元素，:focus-visible 可避免点击后残留 outline

### D.5 屏幕阅读器注意事项

| 场景 | 策略 |
| --- | --- |
| Stats 数字 | 每个 .stat 应 aria-label="异常任务 3 个, 需要立即关注"（合并 label+value+total） |
| Exception Panel | aria-live="polite" 当异常数变化时通知 |
| Table 排序 | 排序操作完成后 aria-live 区域播报 "按健康度降序排列" |
| 分页跳转 | 跳转后 focus 到 table 首行或 aria-live 播报 "显示第 21-40 条" |
| Toast 通知 | role="alert" 确保立即播报；4s 后 DOM 移除不影响已播报内容 |
| Modal 开关 | 打开时 focus trap + aria-modal; 关闭时 focus 返回触发元素（store ref before open） |
| Loading skeleton | aria-busy="true" on 容器; 加载完成后移除 + aria-live="polite" 播报 "数据已加载" |
| Icon-only buttons | 所有无文字按钮（.action-btn, .toggle-vis, .icon-btn）必须 aria-label |
| Health dots | .dot 本身 aria-hidden="true"; 文字标签（"健康"/"异常"）承载语义 |
| Retired rows | opacity 降低为视觉提示; 须辅以 .lifecycle badge 文字 "已下线" + aria-label |

### D.6 Landmark 结构

```
<body>
  <a class="skip-link" href="#main-content">跳转到主要内容</a>
  <div id="app-shell">
    <aside role="navigation" aria-label="主导航"> ... </aside>
    <div class="col-main">
      <header role="banner"> .topbar </header>
      <main id="main-content" role="main">
        <div class="view active"> ... page content ... </div>
      </main>
    </div>
  </div>
</body>
```

### D.7 Reduce Motion 支持

```
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
  .skeleton { animation: none; background: var(--surface-2); }
  .toast { animation: none; }
}
```

---

*文档版本：v3 COMPLETE · 2026-08-11 · 覆盖全部 16 页 + Overlay + States + 动画规格 + 无障碍规格*

[文档索引](../index.html) · [Markdown](UI重设计-逐页设计规格书.md) · [索引](../index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
