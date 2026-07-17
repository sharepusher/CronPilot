# CronPilot · L1/L2/L3 与任务健康模型评审

> HTML 版：[规模化双层IA与任务健康模型评审.html](规模化双层IA与任务健康模型评审.html) · [文档索引](index.html) · [索引 Markdown](index.md)

[← 文档索引](index.html)
IA评审归档OPT-P2-13

# L1 / L2 / L3 与 Job Health Model 评审

运维 × 开发关注差异 · SimpleBoot 风格统一 · 优劣势与工程隐阱 · 角色调制 Demo

状态：**评审归档 · 结论已收束** · 权威实现规格见
[规模化信息架构设计（OPT-P2-13）](规模化信息架构设计.html) · 2026-07-15

**归档说明：**本页保留讨论期的专业评审、角色 Demo 与隐阱分析。
**实现以总设计为准**：<规模化信息架构设计.html>。
Scope 控件细则：[Scope UX](规模化Scope过滤与角色差异化设计.html)。

**原评审对象：**「双层 IA」实为 **L1 健康中心 · L2 任务管理 · L3 执行中心** 三层，并引入异步维护的 Job Health Model。
结论：**方向正确、须角色调制与风格收束、Health Model 值得做但命名/写路径要改、Facet/Saved View 后置**。

**目录**

1. [总评与打分](#v)
2. [人设：运维 vs 开发，三角色如何对准](#p)
3. [L1/L2/L3 合理性与修正](#ia)
4. [Job Health Model：值得做 vs 隐阱](#hm)
5. [页面风格统一约束](#style)
6. [角色调制 Demo](#demo)
7. [落地分期（对 CronPilot 现实）](#phase)
8. [确认项](#confirm)

## 一、总评与打分

总体采纳 · 有条件
信息解耦（配置 / 健康 / 执行实例）与「异常优先」专业且对症；原文对行锁、租户穿透的警告正确。
主要修正：**① 角色调制 L1，勿强迫开发者只看异常首页；② L3 对齐现有 JobLog，勿另造 Instance 实体；③ 风格锁在 SimpleBoot；④ Facet/Saved View / 完整 health\_score 后置；⑤ 表名勿叫 rbac\_\***。

| 模块 | 专业性 | 与 CronPilot 契合 | 首期是否落地 |
| --- | --- | --- | --- |
| L1 Exception First | 高 | 中高（须按角色裁剪模块） | 指标条 + 异常榜，非独立大屏 |
| L2 Scope / 快筛 | 高 | 高（已有 Scope UX 设计） | 是（与 Scope 设计合并） |
| Facet / Saved View | 中 | 偏低（SSR 成本高） | 否，P2+ |
| L3 Run 中心（非日志一级） | 高 | 高（JobLog≈Run 已存在） | 心智升级 + UI 文案，少新建表 |
| Job Health Model | 高 | 中高（写放大需控） | 窄表同步失败路径；成功率批写 |

## 二、人设：运维 vs 开发，能否「各看所需」

CronPilot 现网三角色（非独立「开发者」角色）：

| 角色 | 典型真人 | 核心心理 | 若 L1 仅「异常优先」会怎样 |
| --- | --- | --- | --- |
| `admin` | 平台/运维负责人 | 「全站有没有火、谁的锅」 | 契合；L1 应做默认首页 |
| `operator` | 业务开发 + 值班兼维护 | 「我组任务稳不稳；我刚改的那个成没成；要编辑/启停」 | **半契合**：需要异常区，也需要「我的任务 / 最近更新」入口，否则天天点进空异常榜再绕去 L2 |
| `viewer` | 只读开发 / 协作方 | 「某任务上次跑没跑、失败原因」 | 异常榜有用但只读；更常要**按任务名直达 L3** |

**结论：**「不同角色关注不同」必须做成 **同一壳层下的模块可见性差异**，而不是三套产品。
不建议为此新增第四角色「developer」——用 `operator`/`viewer` + Scope 已覆盖多数开发协作；若未来要「我创建的任务」，用 `created_by` 字段比再裂角色更经济。

### 2.1 推荐：角色调制的 L1 模块矩阵

| L1 模块 | admin | operator | viewer |
| --- | --- | --- | --- |
| 全局/可见域 Metric（失败任务数、连续失败） | 必显 · 默认焦点 | 必显（Scope 内） | 必显（只读） |
| 异常任务榜 Top-N | 必显 | 必显 | 必显 |
| Scope 健康矩阵 | 必显 | G≥2 时显；G=1 折叠为上下文 | 同 operator |
| 「快速进入任务管理」主按钮 | 次要 | **主 CTA** | 主 CTA（只读列表） |
| 最近成功 / 我组运行中摘要 | 可选 | **推荐显**（安抚开发「没坏」） | 推荐 |
| SLA / 熔断配置入口 | 后期 | 无 | 无 |
| 用户/组管理快捷 | 可链到现有 RBAC 页 | 无 | 无 |

落地默认路由建议（可配置）：

- `admin` → L1 健康摘要（可与 `/cron_list` 顶栏合体，见分期）
- `operator` / `viewer` → 仍可进 L1，但**首屏一半给「任务管理快捷 + 最近执行」**，异常区不独占全部 fold
- 任何人可在顶栏 Tab 固定进入 L2；偏好可后来再做（Saved View 之后）

## 三、L1 / L2 / L3 合理性与修正

#### L1 Health Center

采纳

异常优先对运维正确。修正：不是「看不见健康任务」，而是「默认折叠健康噪声」；开发角色保留「安抚性」成功摘要。

#### L2 Task Management

采纳

Scope + 状态快筛与既有设计一致。Facet / Saved View 概念对，**首期砍掉**以免 SSR 复杂化与风格漂移。

#### L3 Execution Center

采纳心智

**不要新建 Execution 表**：现有 `job_log` 一行即一次 Run；`log_id` 即 run 关联键；详情已挂 add\_log。将导航文案从「日志」改为「执行记录 / 运行实例」即可。

### 3.1 与「日志不再一级入口」

| 原文主张 | 评审 |
| --- | --- |
| 去掉一级「任务执行记录」Tab | 慎重：运维仍需「全站失败流」监察页。建议保留 Tab，但默认 `status=fail`，并改名「执行记录」；从 L2 行进入带 `cron_info_id` 的任务内 Run 列表更优先。 |
| Stdout/Stderr 属 Instance 附属 | 正确：对齐现 `job_log_detail` 的 content / add\_log 折叠。 |
| Timeline / Retry | CronPilot 当前无多步 DAG、无内置 Retry 状态机；Timeline 可简化为「单次 Run 时间线（请求→响应→add\_log）」；Retry 待产品确认后再做，勿空画。 |

### 3.2 L1→L2→L3 穿透一致性

原文「看板聚合必须注入 Scope」完全正确。规则：

- 一切列表/聚合先 `build_scope_filter_clause`，再算 Health。
- L1 链接必须带可复现 query：`scope_view` / `group_id` / `health=failing` / `id=`。
- 禁止 L1 展示不可点击进 L2/L3 的资源（避免 403 体验漏洞）。

## 四、Job Health Model：值得做 vs 隐阱

### 4.1 优势（成立）

- 列表/首页 O(可见任务数) 读宽表，避免每次扫 `job_log` 算连续失败。
- `consecutive_failures` 是告警/熔断自然语言。
- 为 OPT-P2-02 / Prometheus 暴露提供稳定维度（任务级 gauge）。

### 4.2 必须修正的设计细节

| 原文点 | 修正 |
| --- | --- |
| 表名 `rbac_job_health` | **改为 `job_health` 或 `cron_job_health`**。健康态不属于 RBAC 子系统，避免概念污染。 |
| 字段一口气上齐 health\_score / avg\_duration / failure\_rate\_24h | 首期仅：`cron_info_id` PK、`last\_run\_\*`、`last\_success\_at`、`last\_fail\_at`、`consecutive\_failures`、`health\_status`（ok|failing|unknown）。比率与均耗时二期批算或物化。 |
| 每次 Run 都 UPDATE 健康表 | 采纳原文防线：**失败/状态翻转同步写**；纯 SUCCESS 可节流（每 N 秒或每 K 次）或「仅更新 last\_run\_at 的低频写」。秒级任务是行锁主因。 |
| Redis 必选 | CronPilot 默认无 Redis 依赖；首期用「进程内不合适（多 worker）」→ 优先 **DB 条件更新 + 失败同步**；确有多实例热点再引 Redis（需新依赖评审）。 |
| 与 trim 日志的一致性 | `job_log_counts` 裁剪旧日志后，连续失败计数**不得**靠重扫残缺日志重算；必须以健康表为准，或裁剪时保留「足够窗口」。 |

### 4.3 写路径建议（B0）

```
cron_do 完成 → 写 job_log（已有）
        → update_job_health(cron_id, outcome):
             if fail/error:
                 consecutive_failures += 1
                 last_fail_* = now; health_status = failing
                 同步 COMMIT（与 job_log 同事务更佳）
             if success:
                 if consecutive_failures > 0 or last_status != success:
                     # 翻转：同步写
                     consecutive_failures = 0; health_status = ok; last_success_*
                 else:
                     # 连续成功：可选跳过或节流写 last_run_at
                     pass
```

## 五、页面风格统一约束

**反模式：**L1 做成现代大屏（渐变卡、圆角阴影、独立 CSS），L2 仍是 SimpleBoot 表格——用户会感觉「两个产品」。

| 约束 | 要求 |
| --- | --- |
| 壳层 | 沿用 `admin_base` + 顶栏 + `rbac/_nav.html` Tab；L1/L2 都是 Tab 或同一页区块，不另起 Vue/React 壳 |
| 组件 | Metric 用 Bootstrap/SimpleBoot `well` / 边框数字格（见 Demo）；异常榜用现有 table；Scope 控件见 Scope UX 设计 |
| 色彩 | 失败红 / 运行蓝 / 成功绿 与现有 job\_log badge 宏一致；禁止 emoji 主视觉 |
| 对话框 | L3 继续 `open_iframe_dialog` + art.dialog；勿突然改成全屏 SPA |
| 文案 | 全局统一「执行记录」「运行实例」称谓，逐步弱化「日志地狱」式入口名 |

## 六、角色调制 Demo（风格：SimpleBoot 指标条）

同一视觉语言下，仅模块权重不同——请切换角色对比。

admin · 运维
operator · 开发兼维护
viewer · 只读开发

admin — Exception First 主导；Scope 矩阵暴露；CTA 弱化

admin管理员

健康概览任务列表执行记录用户管理

128

可见任务

96

运行中

3

连续失败

7

今日失败 Run

异常任务榜（跨 Scope）

| 任务 | Scope | 连续失败 | 操作 |
| --- | --- | --- | --- |
| 风控日终对账 | 金融风控 | 5 | 查看执行 · 打开任务 |
| 数仓分钟同步 | 数据控制 | 3 | 查看执行 · 打开任务 |

Scope 健康矩阵

风控

1 失败 · 45 任务

数据

0 失败 · 20 任务

GLOBAL

0 失败 · 12 任务

operator — 异常区仍在，但「进入任务管理」与「我组最近执行」并排，服务开发日常

aliceoperator数据控制组

健康概览任务列表执行记录

32

可见任务

1

本组连续失败

19

本组运行正常

→ 任务管理

主工作台（L2）

需要处理

| 任务 | 最近执行 | 操作 |
| --- | --- | --- |
| 质量校验（日批） | 失败 ×3 | 执行记录 | 编辑 |

我组最近执行（安抚 / 发布核对）

| 任务 | 结果 | 时间 |
| --- | --- | --- |
| 数仓分钟同步 | 成功 | 14:26:01 |
| 全局心跳探测 | 成功 | 14:26:00 |

viewer — 只读；强调搜索直达与执行下钻，无写操作

carolviewer金融风控组

健康概览任务列表执行记录

1

可见连续失败

—

无写权限

搜索

异常（只读）

| 任务 | 连续失败 | 操作 |
| --- | --- | --- |
| 风控日终对账 | 5 | 查看执行记录 |

## 七、落地分期（对 CronPilot 现实）

| 波次 | 内容 | 不做 |
| --- | --- | --- |
| **B0** | `job_health` 窄表 + cron\_do 失败/翻转同步； `cron_list` 顶栏 Metric + 异常入口（L1 合体）； Scope/状态快筛（接 Scope UX）； 行内 last\_run / consecutive\_failures； 「运行记录」心智标为 L3（仍 iframe） | 独立 `/dashboard`；Facet；Saved View；Redis；health\_score；拆掉执行记录 Tab |
| **B1** | 角色调制 L1 区块；执行记录默认失败；可选独立健康 Tab | 熔断配置大屏 |
| **B2** | failure\_rate\_24h / avg\_duration 批算；OPT-P2-02 趋势；/metrics 导出 | 为健康单独上 Elasticsearch |
| **B3** | Saved View / 丰富 Facet；真正独立 Dashboard（任务破千或明确需求） | — |

原文「第一期物理合并交付」与本仓库策略一致：优先合体到 `cron_list`，避免三套路由三套 CSS。
第二期再拆 `/dashboard`——附条件：RBAC/Scope 稳定 + 任务规模或运维明确要求。

## 八、确认项（已收束）

§八原勾选项已全部纳入 [总设计 §二已拍板结论](规模化信息架构设计.html#s2)。
启动实现请确认 [总设计 §十](规模化信息架构设计.html#s10)。

[文档索引](index.html) ·
[总设计 OPT-P2-13](规模化信息架构设计.html) ·
[Scope UX](规模化Scope过滤与角色差异化设计.html) ·
Markdown 版：<规模化双层IA与任务健康模型评审.md>
· [Markdown](规模化双层IA与任务健康模型评审.md) · [索引](index.html)

---

[← 文档索引（HTML）](index.html) · [← 文档索引（Markdown）](index.md)
