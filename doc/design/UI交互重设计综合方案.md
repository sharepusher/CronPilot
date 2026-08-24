# CronPilot 2026 — UI/交互重设计综合评估与方案

> HTML 版：[UI交互重设计综合方案.html](UI交互重设计综合方案.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# CronPilot 2026 — UI/交互重设计综合评估与方案

文档编号：OPT-P1-16 · 创建：2026-08-11 · 状态：**设计草案**  
输入源：① Mockup (`CronPilot-2026-full-mockup.html`) ② 产品评审分析 ③ 现有工程架构 ④ 已交付 IA/RBAC/任务生命周期/执行记录设计文档  
目标：从"漂亮的 Admin Console"升级为"专业的 Scheduler Operations Console"

## 一、评估总结

### 1.1 Mockup 评分

| 维度 | 当前 Mockup | 目标 | 关键差距 |
| --- | --- | --- | --- |
| Visual Design | 8.5/10 | 9 | 色系已自洽、Typography/Radius 克制 |
| Design System | 8.5/10 | 9 | Token 完整（canvas/surface/signal/...），Light/Dark 对称 |
| Information Architecture | 7.0/10 | 9 | "任务编辑"不应为 L1 nav；缺 Health 层 |
| Task Management | 7.0/10 | 9 | 仍是 CRUD List；缺 Task Detail |
| Observability | 6.5/10 | 9 | 无 Health/Exception 首屏；指标选取非运营视角 |
| Execution Debug | 6.0/10 | 9 | 缺 Run Inspector / 失败原因 / Duration anomaly |
| RBAC/Scope UX | 7.0/10 | 9 | Group 停留在 Card；未体现 Scope Console |
| Scalability 100+ Tasks | 6.5/10 | 9 | 表格无健康上下文，信息密度不足 |
| Enterprise UX | 7.0/10 | 9 | 缺 Timezone、Run Now 确认流、Progressive Disclosure |
| 2026 风格 | 8.0/10 | 9 | 接近 Linear/Vercel 水准；卡片化略多 |
| **Overall** | **≈ 7.2/10** | **9/10** |  |

### 1.2 核心判断

**结论**：Mockup 的视觉层（Design Token + Shell + Component Library）可直接采用。产品层需要二次收敛：从"管理 128 条记录"的心智升级为"10s 发现问题 → 30s 定位任务 → 1min 定位 Run → 3min 完成处理"的运营心智。

## 二、Design Token 采纳决策

### 2.1 Mockup Token 与现有 CronPilot Token 对照

| Token 类别 | Mockup (新) | CronPilot 现有 | 决策 |
| --- | --- | --- | --- |
| Canvas/Surface | `--canvas/#F7F8F9` `--surface/#FFF` | `--cp-bg/#fafbfc` `--cp-surface/#fff` | ✅ 采用 Mockup 值（差异 <1%） |
| Border | `--border/#E4E6E9` | `--cp-border/#e2e8f0` | ✅ 采用 Mockup 值（对比度更好） |
| Ink/Muted | `--ink/#14171A` `--muted/#5B6169` | `--cp-ink/#0f172a` `--cp-muted/#64748b` | ✅ Mockup 的 muted 对比度 6.2:1 > 现有 4.76 |
| Signal (Primary) | `--signal/#3D6FE0` (H=222° S=73% L=56%) | `--cp-accent-blue/#2563eb` (H=221° S=83% L=53%) | ✅ 采用 Mockup（饱和度更收敛） |
| Success/Warning/Danger | 各有 base + bg 两级 | 各有 5–7 级变体（过细） | ⚠️ 精简至 Mockup 的 2–3 级 |
| Typography | Inter + JetBrains Mono | 系统字体 + 无 mono 指定 | ✅ 采用（Mono 对 Cron/URL 展示至关重要） |
| Dark Mode | `canvas:#0D0F12` 独立设计 | `--cp-bg:#16161e` Tailwind 映射 | ✅ 采用 Mockup 暗色系统（独立设计 > 机械映射） |

**决策**：以 Mockup 的 Token 系统为目标态（~20 变量 × 2 主题 = 40 值），替代现有 65 × 2 = 130 值的过细系统。迁移过程中两套并存，逐页替换。

## 三、信息架构重设计

### 3.1 现有 IA vs 目标 IA

| 现有 Mockup IA | 问题 | 目标 IA |
| --- | --- | --- |
| 任务中心 (Task List) | 无 Health 层 | **OPERATIONS**: 任务中心 (Health + Tasks) |
| 任务编辑 (L1 nav) | Edit 是 Action 不是节点 | 移除（Edit 从 Task Detail 进入） |
| 执行记录 | 仅列表无 Detail | **OPERATIONS**: 执行记录 (+ Run Inspector) |
| 操作记录 | — | **ADMINISTRATION**: 操作记录 |
| 用户管理 | — | **ADMINISTRATION**: 用户管理 |
| 业务组 (Card) | 未体现 Scope | **CONFIGURATION**: 业务组 (Scope Console) |
| 审计 | — | **ADMINISTRATION**: 审计 |
| 标签管理 | 无 Namespace | **CONFIGURATION**: 标签 (+ Namespace) |
| API 文档 (在"个人"下) | API 非个人资源 | **DEVELOPER**: API 文档 |

### 3.2 目标导航结构

OPERATIONS
├── 任务中心 ← Health + Exception + Task List
├── 执行记录 ← Run History + Run Inspector
│
CONFIGURATION
├── 业务组 ← Scope Console
├── 标签 ← Tag Namespace
│
ADMINISTRATION
├── 用户管理
├── 审计
├── 操作记录
│
DEVELOPER
├── API 文档
├── API Token ← 从 User Dropdown 中也可访问

### 3.3 新增核心页面：Task Detail

**当前最大缺页**：Mockup 中点击任务直接进入 Edit Form。专业 Scheduler 需要一个**Task Detail / Task Overview**页面——它是运维人员 90% 时间停留的页面。

```
← 返回任务列表

┌─────────────────────────────────────────────────────┐
│  同步订单履约状态                                      │
│  order-fulfillment-sync                              │
│  [Active] [交易] [P0]    [▶ 立即执行] [⏸ 暂停] [✎ 编辑]│
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌─ Health ────────────────────────────────────────┐ │
│  │ ● Healthy                                       │ │
│  │ 连续失败: 0  │  24h 成功率: 100%  │  P95 延迟: 192ms │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  ┌─ Schedule ──────────────────────────────────────┐ │
│  │ */5 * * * *     每 5 分钟执行一次                  │ │
│  │ Next: 15:05     Timezone: Asia/Shanghai (UTC+8)  │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  ┌─ Recent Runs ───────────────────────────────────┐ │
│  │ 15:00  ● 200  184ms                             │ │
│  │ 14:55  ● 200  192ms                             │ │
│  │ 14:50  ● 200  181ms                             │ │
│  │ [查看全部执行记录]                                 │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  ┌─ Configuration ─────────────────────────────────┐ │
│  │ Endpoint: POST https://api.order.io/sync         │ │
│  │ Timeout: 30s │ Group: 交易平台组                   │ │
│  └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

## 四、任务中心重设计：Health-First

### 4.1 当前 → 目标

| 元素 | Mockup 当前 | 目标 |
| --- | --- | --- |
| 顶部指标 | 任务总数 / 运行中 / 今日失败 / 24h成功率 | **异常任务 / 连续失败 / 运行中 / 今日失败 Run**（128 Tasks 降为副文本） |
| 首屏内容 | 直接进入 Task Table | Exception Panel（连续失败 top 3）→ Task Table |
| 表格字段 | 任务 / 调度策略 / 运行状态 / 操作 | 任务 / Schedule / **Health** / Last Run / Next Run / Scope / 操作 |
| Status | 单维度（运行中/成功/失败/已下线） | 三维度拆分（Lifecycle + Execution + Health） |

### 4.2 三层状态模型

| 维度 | 可能值 | 展示方式 |
| --- | --- | --- |
| **Lifecycle** (任务配置态) | Active / Paused / Retired | Badge（出现在 Task Name 旁） |
| **Execution** (当前执行态) | Running / Idle | 动画 pin（仅 Running 时脉冲） |
| **Health** (健康聚合态) | Healthy (●) / Warning (●) / Failing (×N) | Health 列独立展示 |

```
Task Table Row 示例：

│ 同步订单履约状态       │ */5 * * * * │ ● Healthy │ 2m ago 184ms │ in 3m │ 交易组 │ ▶ … │
│ order-fulfillment-sync │             │           │              │        │        │     │
│ [Active] [交易] [P0]  │             │           │              │        │        │     │
│                        │             │           │              │        │        │     │
│ 清理过期缓存           │ 0 * * * *   │ ×5 Failing│ 1m ago  —    │ in 59m │ 基础设施│ ▶ … │
│ cache-eviction-hourly  │             │           │              │        │        │     │
│ [Active] [基础设施]    │             │           │              │        │        │     │
```

## 五、关键交互升级

### 5.1 Run Now 确认流

```
用户点击 ▶ 立即执行
        ↓
┌─ 确认对话框 ──────────────────────┐
│  确认立即执行？                     │
│                                    │
│  任务: sync-order                  │
│  当前计划: 每 5 分钟                │
│  上次执行: 2 分钟前 · Success       │
│  Concurrency: 不允许并发            │
│                                    │
│  [取消]          [确认执行]         │
└────────────────────────────────────┘
```

### 5.2 Run Inspector（执行详情页）

```
Execution #ab8148aa

┌─ 状态 ─────────────────────────────┐
│ ● SUCCESS  HTTP 200  Duration 184ms │
│ Started 15:00:00.000                │
│ Finished 15:00:00.184               │
└─────────────────────────────────────┘

┌─ Request ──────────────────────────┐
│ POST https://api.order.io/sync      │
│ Headers: Content-Type: application/json │
│ Body: {"cronpilot_log_id":"ab8148aa"} │
└─────────────────────────────────────┘

┌─ Response ─────────────────────────┐
│ HTTP 200                            │
│ {"status":"ok","processed":42}      │
└─────────────────────────────────────┘

┌─ Business Logs (3 entries) ────────┐
│ [15:00:00.034] Processing batch 1   │
│ [15:00:00.098] Processing batch 2   │
│ [15:00:00.156] All 42 orders synced │
└─────────────────────────────────────┘
```

### 5.3 Timezone 作为一等字段

**必须补充**：Cron expression 本身无法完整表达调度语义。跨时区部署时，`0 9 \* \* \*` 在 UTC+8 和 UTC+0 意味着完全不同的时刻。Timezone 必须在 Schedule 配置和 Task Detail 中显式展示。

### 5.4 ⌘K 升级为 Command Palette

```
⌘K 打开

┌─────────────────────────────────────┐
│ 🔍 输入命令或搜索…                   │
├─────────────────────────────────────┤
│ TASKS                               │
│   sync-order            ● Healthy   │
│   cache-eviction        ×5 Failing  │
│                                     │
│ ACTIONS                             │
│   ▶ Run task…                       │
│   + Create task                     │
│   ⏸ Pause task…                     │
│                                     │
│ NAVIGATION                          │
│   → 用户管理                         │
│   → 执行记录                         │
│   → 审计                             │
└─────────────────────────────────────┘
```

## 六、实施路径

### 6.1 分阶段计划

| 阶段 | 范围 | 交付物 | 工程依赖 |
| --- | --- | --- | --- |
| **Phase 0** Design Token 迁移 | 将 Mockup 的 20 变量 Token 系统导入 `console-theme.css`，建立新旧映射 | 新 `console-theme-v2.css`（两套并存） | 无后端依赖 |
| **Phase 1** IA 重构 + Task Center | ① 导航结构调整（去掉"任务编辑" L1） ② 任务中心 Health-First 改造 ③ 三层状态模型 | sidebar nav + 任务列表页重构 | 需要 `job_health` 模型（已有） |
| **Phase 2** Task Detail + Run Now | ① 新增 Task Detail 页 ② Run Now 确认流 ③ Timezone 字段 | `/cron_detail?id=X` 路由 + 模板 | 需新增路由和视图函数 |
| **Phase 3** Run Inspector | ① 执行详情页（Request/Response/Business Logs） ② Duration anomaly 标记 ③ 失败原因分类 | `/job_log_detail?id=X` 重构 | 现有 `job_log` + `job_log_items` |
| **Phase 4** Command Palette + Scope Console | ① ⌘K 升级为全局 Command Palette ② Group Detail → Scope Console ③ Tag Namespace | 前端 JS 组件 + Group 详情页 | 中等 |

### 6.2 不做/不动的部分

- ✅ **保留**：操作记录与审计分离（正确的信息模型）
- ✅ **保留**：Mockup 的视觉层（Token/Shell/Table/Form/Badge 全套复用）
- ✅ **保留**：登录页设计（未来加 SSO/OIDC 入口即可）
- ❌ **不做**：DAG、Calendar View、SLA、Latency Trend（P2 远期）
- ❌ **不做**：Bootstrap 3 全面退役（仅逐页替换，不一次性重写）

## 七、色系决策（综合此前色系 RFC）

**最终决策**：**直接采用 Mockup 的色系统**。它已经解决了我们之前诊断的所有问题：

- 单一蓝色：`--signal:#3D6FE0` (H=222°) — 统一的唯一蓝
- 饱和度收敛：signal S=73%, success S=76%, warning S=68%, danger S=65% — 跨度仅 11%
- 变量精简：~20 个语义变量（而非 65 个）
- 暗色独立设计：`canvas:#0D0F12`（深色带蓝相 2%），非机械映射
- WCAG 达标：`--muted:#5B6169` 对比度 6.2:1 > 4.5:1

不再需要之前的"Phase A 色相微调"方案——直接用 Mockup Token 体系替代。

## 八、与现有工程架构的对接

| Mockup 概念 | CronPilot 现有对应 | 差距/需要新增 |
| --- | --- | --- |
| Task Center Health指标 | `job_health` 表 (consecutive\_failures) | 需要一个聚合查询 API |
| 三层状态 | Lifecycle: `status` 字段; Execution: 运行时状态 | Health 聚合需从 `job_health` 动态计算 |
| Task Detail | 无对应路由 | 新增 `/cron_detail?id=X` |
| Run Inspector | `job_log_detail` 已有基础数据 | 前端重构为 Inspector 布局 |
| Timezone | `cron_infos` 无 timezone 字段 | 需加字段 + 迁移 |
| Run Now | 已有"立即执行"按钮 | 需加确认弹窗 + 并发检查 |
| Command Palette | 已有 ⌘K 搜索（sidebar filter） | 升级为全局 Command + Action |
| Tag Namespace | `tags` 表（group\_id 隔离） | 可选加 `namespace` 字段 |

## 九、产品心智定位

**CronPilot 的产品心智不是**：
> "我有 128 个任务，给我看 128 条记录。"

**CronPilot 的产品心智应该是**：
> "系统现在健康吗？→ 哪里不健康？→ 哪个任务？→ 这次 Run 为什么失败？→ 我要不要处理？"

**对标定位**：  
Linear 的信息密度 + Datadog 的可观测性 + GitHub Actions 的执行心智 + 企业级 RBAC 的治理能力

```
用户进入 CronPilot 的认知路径：

L1 Health     "系统怎么样？"        → 异常面板 + 指标卡
     ↓
L2 Task       "哪个任务有问题？"    → Task Table + Task Detail
     ↓
L3 Run        "这次为什么失败？"    → Run Inspector
     ↓
L4 Action     "我要怎么处理？"      → Run Now / Pause / Edit / Alert
```

## 十、决策点（需确认）

1. **是否同意目标 IA 结构**（OPERATIONS / CONFIGURATION / ADMINISTRATION / DEVELOPER 四区）？
2. **是否同意 Phase 0→4 分阶段推进**？优先级是否需要调整？
3. **Task Detail 页是否在 Phase 2 实现**？还是提前到 Phase 1 一起做？
4. **Timezone 字段**：是否现在就加入 DB schema（Phase 2），还是远期？
5. **卡片化 vs Flat Surface**：是否同意在非"独立实体"场景减少卡片包装？

[文档索引](../index.html) · [Markdown](UI交互重设计综合方案.md) · [索引](../index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
