# CronPilot · 技术文档索引

> HTTP 定时触发调度台 · 每份文档提供 **HTML**（浏览器）与 **Markdown**（GitHub / IDE）两种格式。  
> 本索引按 **项目管理 / 进度 / 架构 / 设计中 / 已交付 / 产品 / 依赖 / 运维 / 验收** 分维整理，避免扁平铺开。

**快捷入口：** [进度总览](交付状态与路线图.html) · [项目入门](arch/项目总览与技术文档.html) · [当前焦点 OPT-P2-13](design/规模化信息架构设计.html) · [Docker 部署](ops/Docker部署指南.html)

---

## ① 项目管理与进度

| 文档 | 说明 | HTML | Markdown |
|------|------|------|----------|
| **编辑与局部更新开发规范** | 意图/权限/并发/范围外保留/事务副作用；附官方依据与验收 | [HTML](arch/编辑与局部更新开发规范.html) | [MD](arch/编辑与局部更新开发规范.md) |
| **交付状态与路线图（权威）** | 已交付 vs 待确认 vs 未开始 · 发行版 **v2.7.0** | [HTML](交付状态与路线图.html) | [MD](交付状态与路线图.md) |
| **需求编号与缩写规范（权威）** | OPT / Tier / Phase / DEC 四轨读法 | [HTML](需求编号与缩写规范.html) | [MD](需求编号与缩写规范.md) |
| **Release Notes** | 版本变更日志（面向用户 / 运维） | [HTML](RELEASE_NOTES.html) | [doc MD](RELEASE_NOTES.md) · [仓库根](../RELEASE_NOTES.md) |
| 项目总览与技术文档 | 定位、架构图、模块导航（推荐首读） | [HTML](arch/项目总览与技术文档.html) | [MD](arch/项目总览与技术文档.md) |
| 仓库拆分与 Git 方案 | 独立仓库与发布说明 | [HTML](arch/新建项目与分支合并方案.html) | [MD](arch/新建项目与分支合并方案.md) |

## ② 架构与安全（已落地）

| 文档 | 说明 | HTML | Markdown |
|------|------|------|----------|
| 架构设计文档 | C4、数据架构、集群双锁 | [HTML](arch/架构设计文档.html) | [MD](arch/架构设计文档.md) |
| 详细技术方案 | 功能规格、API、运维安全 | [HTML](arch/详细技术方案.html) | [MD](arch/详细技术方案.md) |
| **RBAC 详设 v4**（已交付） | 三角色 / login / has_perm | [HTML](design/RBAC架构设计方案.html) | [MD](design/RBAC架构设计方案.md) |
| ↳ RBAC 落地路线 | 阶段实施记录 | [HTML](design/RBAC落地路线.html) | [MD](design/RBAC落地路线.md) |
| **Resource Scope OPT-P2-12**（v1.1.0） | 业务组隔离 · 防 IDOR | [HTML](design/资源隔离与Scope设计.html) | [MD](design/资源隔离与Scope设计.md) |
| ↳ 资源隔离落地路线 | 落地阶段记录 | [HTML](design/资源隔离落地路线.html) | [MD](design/资源隔离落地路线.md) |
| ↳ **RBAC 与群组权限管理评审报告**（评审稿 2026-07-29） | API 层 Scope 缺口再评级 · 登录限流/Cookie 安全等增补建议 | [HTML](design/RBAC与群组权限管理评审报告.html) | [MD](design/RBAC与群组权限管理评审报告.md) |
| **任务生命周期与无删除**（已交付） | 暂停≠下线 · LIFECYCLE-2 | [HTML](design/任务生命周期与无删除设计.html) | [MD](design/任务生命周期与无删除设计.md) |
| **OPT-P0-09/10 锁与密钥**（v2.1.1） | Redis SET NX EX · 生产 SECRET_KEY fail-fast | [HTML](arch/OPT-P0-09-10-锁与密钥设计.html) | [MD](arch/OPT-P0-09-10-锁与密钥设计.md) |
| **OPT-P0-11 管理端 CSRF**（v2.1.1） | 写操作 POST + Session Token | [HTML](arch/OPT-P0-11-管理端CSRF设计.html) | [MD](arch/OPT-P0-11-管理端CSRF设计.md) |

## ③ 设计中（待确认 · 实现前）

| 文档 | 说明 | HTML | Markdown |
|------|------|------|----------|
| **v4.2.0 版本归档与最终候选验收方案**（待确认） | 冻结提交、验收及手动发布 | [HTML](design/v4.2.0-release-finalization-2026-11-04.html) | [MD](design/v4.2.0-release-finalization-2026-11-04.md) |
| **用户授权编辑提交后读取故障分析与修复设计**（待确认） | 稳定 ID、缓存与故障验收 | [HTML](design/rbac-user-edit-postcommit-2026-11-04.html) | [MD](design/rbac-user-edit-postcommit-2026-11-04.md) |
| **发布 job 仓库上下文缺失分析与修复设计**（待确认） | GH_REPO 作用域及发布防护 | [HTML](design/release-publish-repository-context-2026-11-04.html) | [MD](design/release-publish-repository-context-2026-11-04.md) |
| **术语门禁与任务编辑基线工具修复设计（2026-11-03）**（待确认） | 术语分层、历史证据保持、当前契约六场景与命令级防护 | [HTML](design/terminology-baseline-repair-2026-11-03.html) | [MD](design/terminology-baseline-repair-2026-11-03.md) |
| **SQLite 任务编辑保存边界原子保护设计与评估（2026-11-02）**（待确认） | 锁外DNS与受保护重算、有限预算、调度/日志边界和三维评估 | [HTML](design/SQLite任务编辑保存边界原子保护设计-2026-11-02.html) | [MD](design/SQLite任务编辑保存边界原子保护设计-2026-11-02.md) |
| **SQLite 用户编辑保存边界原子保护设计（2026-11-02）**（专项通过） | 局部即时事务、串行规则、独立竞争验收与集成隔离例外 | [HTML](design/SQLite用户编辑保存边界原子保护设计-2026-11-02.html) | [MD](design/SQLite用户编辑保存边界原子保护设计-2026-11-02.md) |
| **RBAC 用户编辑七状态浏览器验收与锁成本文案校准设计**（已验证） | F2实际登录与七状态证据、提交前后故障对照；F3锁成本表述校准 | [HTML](design/RBAC用户编辑七状态浏览器验收与锁成本文案校准设计-2026-10-29.html) | [MD](design/RBAC用户编辑七状态浏览器验收与锁成本文案校准设计-2026-10-29.md) |
| **编辑契约检查单与行为回归门禁设计**（待确认） | 责任检查单、分层触发、真实环境和稳定汇总阻断 | [HTML](design/编辑契约检查单与行为回归门禁设计-2026-10-29.html) | [MD](design/编辑契约检查单与行为回归门禁设计-2026-10-29.md) |
| **RBAC 用户编辑锁释放验收增强设计（2026-10-29）**（已验证） | F1关闭；同上下文探针与省略回滚负向校准；实施结果见源设计 | [HTML](design/RBAC用户编辑锁释放验收增强设计-2026-10-29.html) | [MD](design/RBAC用户编辑锁释放验收增强设计-2026-10-29.md) |
| **R5 用户编辑字段意图与范围外组保留设计（2026-10-29）**（已验证） | 只改花名只写花名；可信表单投影与外组保留 | [HTML](design/R5用户编辑字段意图与范围外组保留设计-2026-10-29.html) | [MD](design/R5用户编辑字段意图与范围外组保留设计-2026-10-29.md) |
| **RBAC 用户编辑两项 P2 评估与修复设计（2026-10-29）**（rev.1.1，已验证） | 正确组读取与不可比较状态；审计 v1 整条回退，含页面对比与验收 | [HTML](design/RBAC用户编辑两项P2评估与修复设计-2026-10-29.html) | [MD](design/RBAC用户编辑两项P2评估与修复设计-2026-10-29.md) |
| **RBAC 用户编辑两项 P1 根因与修复设计（2026-10-29）**（rev.1.1，P1 已验证） | 回显快照连续性、非破坏性专用空库；含根因、备选评估、页面对比与验收矩阵 | [HTML](design/RBAC用户编辑两项P1根因与修复设计-2026-10-29.html) | [MD](design/RBAC用户编辑两项P1根因与修复设计-2026-10-29.md) |
| **规模化信息架构 OPT-P2-13**（权威总稿） | L1/L2/L3 · job_health · 角色调制 · **当前焦点** | [HTML](design/规模化信息架构设计.html) | [MD](design/规模化信息架构设计.md) |
| **发布资产与源码归档边界规范（2026-10）**（待确认） | 自定义安装包唯一入口 · Source code 审计快照边界 · Release 文案与资产发布后门禁 | [HTML](design/发布资产与源码归档边界规范-2026-10.html) | [MD](design/发布资产与源码归档边界规范-2026-10.md) |
| **任务中心需要关注项目排除下线任务设计**（已交付） | 下线任务不再进入异常提醒面板 | [HTML](design/任务中心需要关注项目排除下线任务设计.html) | [MD](design/任务中心需要关注项目排除下线任务设计.md) |
| **下次执行相对时间误显示修复设计（2026-09）**（已实施） | 空 minute 展示与 APScheduler 默认 0 对齐 · CronTrigger 同源 | [HTML](design/下次执行相对时间误显示修复设计-2026-09.html) · [复盘](postmortem/2026-09-下次执行相对时间误显示.html) | [MD](design/下次执行相对时间误显示修复设计-2026-09.md) |
| **任务中心顶栏运行中/已暂停分列统计（2026-09）**（已实施 · rev.5 · 方案 E） | 保留「N 个任务」后追加「运行中 X · 已暂停 Y」；不改 chip「全部」、不改默认列表 | [HTML](design/任务中心排除已下线任务统计与默认列表设计-2026-09.html) | [MD](design/任务中心排除已下线任务统计与默认列表设计-2026-09.md) |
| **任务中心标题统计收敛（2026-09）**（已实施） | 移除标题中的总任务数与今日失败；保留运行中、已暂停、持续异常、逾期；今日失败仅留统计卡 | [HTML](design/任务中心标题统计收敛设计-2026-09.html) | [MD](design/任务中心标题统计收敛设计-2026-09.md) |
| **4.1.0 发布前变更梳理与文档收敛（2026-09-18）**（发布前） | 4.0.0 后提交分层、过期文档排除、R1/R2 已关闭与后续验收顺序 | [HTML](design/4.1.0发布前变更梳理与文档收敛-2026-09-18.html) | [MD](design/4.1.0发布前变更梳理与文档收敛-2026-09-18.md) |
| **历史图片资产去重与发布包瘦身设计（2026-10）**（v1.4，已实施） | 71 个内容寻址资产；图片门禁；从最终 tag 按白名单构建 4.1.0 公开发布包；不发布证据包 | [HTML](design/历史图片资产去重与发布包瘦身设计-2026-10.html) | [MD](design/历史图片资产去重与发布包瘦身设计-2026-10.md) |
| **历史图片资产去重与发布包瘦身设计专业 Review（2026-10）** | v1.4 修订后通过；用户确认后已实施 | [HTML](qa/历史图片资产去重与发布包瘦身设计-专业Review-2026-10.html) | [MD](qa/历史图片资产去重与发布包瘦身设计-专业Review-2026-10.md) |
| **历史图片治理瘦身后项目体积评估（2026-10）** | 实施后 71 个唯一资产；5 张凭据截图已删除 | [HTML](qa/历史图片治理瘦身后项目体积评估-2026-10.html) | [MD](qa/历史图片治理瘦身后项目体积评估-2026-10.md) |
| **历史截图凭据脱敏与迁移原子性复盘（2026-10）** | 5 张凭据截图最终删除；可恢复迁移；CI/发布门禁 | [HTML](postmortem/2026-10-历史截图凭据脱敏与迁移原子性复盘.html) | [MD](postmortem/2026-10-历史截图凭据脱敏与迁移原子性复盘.md) |
| **发布包隔离安装闭环修复（2026-10）** | pytz 锁冲突；运行时文档闭包；0.60 MiB 严格双构建；黄金路径通过 | [HTML](postmortem/2026-10-发布包隔离安装闭环修复.html) | [MD](postmortem/2026-10-发布包隔离安装闭环修复.md) |
| **健康度未满阈值误标「健康」修复（2026-09）**（已实施 · 方案 A） | 连续失败 1～N−1 显示「有失败」，禁止标「健康」；≥N 仍为异常 | [HTML](design/健康度未满阈值误标健康修复设计-2026-09.html) | [MD](design/健康度未满阈值误标健康修复设计-2026-09.md) |
| **用户管理「添加用户」入口布局优化设计**（已交付） | 标题区减负 · 主操作移入列表工具区左首位 · 桌面/窄屏前后对比 | [HTML](design/用户管理添加用户入口布局优化设计.html) · [页面对比 Demo](design/用户管理添加用户入口-页面对比Demo.html) | [MD](design/用户管理添加用户入口布局优化设计.md) |
| **全仓术语治理设计（2026-09）**（已完成） | 业务旧术语 → 触发语义 · 技术 API 保留 · 活跃文档与语境化门禁 | [HTML](design/全仓术语治理设计-2026-09.html) | [MD](design/全仓术语治理设计-2026-09.md) |
| **全量测试全绿修复设计（2026-09）**（待确认） | 90 项失败/错误分簇：Session fixture、离线 DNS、旧 schema 与 ORM 门禁 | [HTML](design/全量测试全绿修复设计-2026-09.html) | [MD](design/全量测试全绿修复设计-2026-09.md) |
| **统一人工操作错误处理设计（2026-09）**（历史草案） | 已拆分为 P0-A2、P0-S、P0-B 与 P0-C 子方案，仅作决策溯源 | [HTML](design/统一人工操作错误处理设计-2026-09.html) | [MD](design/统一人工操作错误处理设计-2026-09.md) |
| **统一错误处理治理路线图（2026-09）**（待确认） | 权威层级、P0/P1 优先级、依赖、确认边界与拆分导航 | [HTML](design/统一错误处理P0实施计划-2026-09.html) | [MD](design/统一错误处理P0实施计划-2026-09.md) |
| **P0-A-lite Request ID 协议设计（2026-10）**（待确认） | UUID v4 Header、端点登记、双 ID、缓存与原子发布 | [HTML](design/P0-A-lite-Request-ID协议设计-2026-10.html) | [MD](design/P0-A-lite-Request-ID协议设计-2026-10.md) |
| **P1-A2 JSON 错误信封设计（2026-10）**（待确认） | P1：输出兼容快照、入口适配与稳定错误码（保留旧路径） | [HTML](design/P0-A2-JSON错误信封设计-2026-10.html) | [MD](design/P0-A2-JSON错误信封设计-2026-10.md) |
| **P0-S 异常脱敏与输出 Sink 设计（2026-10）**（待确认） | P0 安全前置：sink 台账、统一 sanitizer 与 HTTP/日志/通知输出面 | [HTML](design/P0-S-异常脱敏与输出Sink设计-2026-10.html) | [MD](design/P0-S-异常脱敏与输出Sink设计-2026-10.md) |
| **P1-B 错误交互与表单回显设计（2026-10）**（待确认） | P1：页面级字段错误、表单回显、无障碍与真实页面对比 | [HTML](design/P0-B-错误交互与表单回显设计-2026-10.html) | [MD](design/P0-B-错误交互与表单回显设计-2026-10.md) |
| **P0-C（C-0）任务调度最终一致性设计（2026-10）**（待确认） | 先冻结 generation、迁移、锁与对账证据，再评审实施切片 | [HTML](design/P0-C-任务调度最终一致性设计-2026-10.html) | [MD](design/P0-C-任务调度最终一致性设计-2026-10.md) |
| **管理平台渐进式 REST API 化后续方案（2026-09）**（待确认） | SSR 保留、管理端 JSON 层、Session/CSRF/RBAC 边界与垂直迁移计划 | [HTML](design/管理平台REST_API化后续方案-2026-09.html) | [MD](design/管理平台REST_API化后续方案-2026-09.md) |
| **统一错误处理 P0 设计契约修订复盘（2026-09）** | 首期兼容决议、scheduler 最终一致性与可验证入口覆盖 | [HTML](postmortem/2026-09-统一错误处理P0设计契约修订.html) | [MD](postmortem/2026-09-统一错误处理P0设计契约修订.md) |
| **统一错误处理方案文档交付失误深度复盘（2026-09）** | request_id 语义、SSR/REST 边界、版本记录、URL 交付与浏览器验证的系统复盘 | [HTML](postmortem/2026-09-统一错误处理方案文档交付失误深度复盘.html) | [MD](postmortem/2026-09-统一错误处理方案文档交付失误深度复盘.md) |
| **统一错误处理现状评估（2026-09-21）**（评估） | 当前未满足统一契约；2 个 P0、3 个 P1 和 1 个 P2 缺口 | [HTML](qa/统一错误处理现状评估-2026-09-21.html) | [MD](qa/统一错误处理现状评估-2026-09-21.md) |
| **统一错误处理 P0 方案专业 Review（2026-09-21）**（评估） | B+：方向正确但需补齐接口覆盖、trace_id 复用、API 兼容和事务状态机 | [HTML](qa/统一错误处理P0方案专业Review-2026-09-21.html) | [MD](qa/统一错误处理P0方案专业Review-2026-09-21.md) |
| **统一错误处理后续优化步骤评估（2026-10-15）**（评估） | 代码完成度、确认状态漂移、P0/P1 实施顺序与逐批停止条件 | [HTML](qa/统一错误处理后续优化步骤评估-2026-10-15.html) | [MD](qa/统一错误处理后续优化步骤评估-2026-10-15.md) |
| **RBAC 用户编辑差异写入与事务闭环方案专业 Review（2026-10-15）**（条件通过） | B+：方向正确；实施前须关闭 __ALL__ 授权、回显、停用策略与 UI/审计契约 | [HTML](qa/RBAC用户编辑差异写入与事务闭环方案专业Review-2026-10-15.html) | [MD](qa/RBAC用户编辑差异写入与事务闭环方案专业Review-2026-10-15.md) |
| **RBAC 用户编辑差异写入与单事务收口独立设计（2026-10）**（rev.2.6，四项 Review 已关闭） | 签名意图、数据库当前授权、行锁三方比较、同事务审计、前端预检与安全审计展示均已完成 | [HTML](design/RBAC用户编辑差异写入与单事务收口独立设计-2026-10.html) | [MD](design/RBAC用户编辑差异写入与单事务收口独立设计-2026-10.md) |
| **任务编辑无变更保存零副作用独立设计（2026-10）**（问题①，已验证） | 前端零 POST、后端零写入/日志/调度；专项、双后端、浏览器及原生回退已验证 | [HTML](design/任务编辑无变更保存零副作用独立设计-2026-10.html) | [MD](design/任务编辑无变更保存零副作用独立设计-2026-10.md) |
| **任务 API 超时参数类型兼容修复设计（2026-11-02）**（rev.2，验收通过） | 兼容 Schema 整数与表单字符串；专项、双后端及浏览器验收通过 | [HTML](design/任务API超时参数类型兼容修复设计-2026-11-02.html) | [MD](design/任务API超时参数类型兼容修复设计-2026-11-02.md) |
| **任务启停结果判定与冲突报错 D2 设计（2026-11-02）**（rev.4，本批验收通过） | 明确目标签名重试，双后端 Web/API 验证 | [HTML](design/任务启停结果判定与冲突报错D2设计-2026-11-02.html) | [MD](design/任务启停结果判定与冲突报错D2设计-2026-11-02.md) |
| **任务调度写入协调与恢复 W2 独立设计（2026-10-30）**（历史候选） | 后续可选协调/恢复路线及 C-0 证据；本批改为冲突检测与明确报错 | [HTML](design/任务调度写入协调与恢复W2独立设计-2026-10-30.html) | [MD](design/任务调度写入协调与恢复W2独立设计-2026-10-30.md) |
| **任务调度冲突检测与明确报错 W2 设计（2026-10-30）**（rev.4，D1 验收通过） | 正常返回信任同步契约；版本冲突单独报错，仅不确定异常查询 | [HTML](design/任务调度冲突检测与明确报错W2设计-2026-10-30.html) | [MD](design/任务调度冲突检测与明确报错W2设计-2026-10-30.md) |
| **暂停任务编辑注册窗口独立设计（2026-10-30）**（问题⑤，待 Review） | 按有效变化决定调度副作用；暂停规则修改方案待真实 JobStore 验证 | [HTML](design/暂停任务编辑注册窗口独立设计-2026-10-30.html) | [MD](design/暂停任务编辑注册窗口独立设计-2026-10-30.md) |
| **任务编辑陈旧页面并发覆盖独立设计（2026-10）**（问题②，待 Review） | 可信基线、三方比较与原子版本；未编辑值保留、完整写者协议和冲突页面对比 | [HTML](design/任务编辑陈旧页面并发覆盖独立设计-2026-10.html) | [MD](design/任务编辑陈旧页面并发覆盖独立设计-2026-10.md) |
| **任务编辑无变更保存副作用修复复盘（2026-10-29）** | 只读比较、零 DML/日志/调度；按钮/回车/原生回退及双后端验证 | [HTML](postmortem/2026-10-任务编辑无变更保存副作用.html) | [MD](postmortem/2026-10-任务编辑无变更保存副作用.md) |
| **任务编辑差异写入与调度一致性 M1 设计（2026-10）**（综合背景） | 当前按用户要求逐项独立设计，先评审问题① | [HTML](design/任务编辑差异写入与调度一致性M1设计-2026-10.html) | [MD](design/任务编辑差异写入与调度一致性M1设计-2026-10.md) |
| **RBAC 用户编辑差异写入与单事务收口方案专业 Review（2026-10-28）**（A 校准通过） | 准确性 A、专业性 A、合理性 A；G1–G4 已关闭，凭据操作必须审计但凭据值永不记录 | [HTML](qa/RBAC用户编辑差异写入与单事务收口方案专业Review-2026-10-28.html) | [MD](qa/RBAC用户编辑差异写入与单事务收口方案专业Review-2026-10-28.md) |
| **RBAC 全局权限授予边界 S0–S5 全过程专业 Review（2026-10-16）**（最终复核） | A-（9.3/10），正式通过：写入安全、批量反馈、列表 Scope 与持久化证据均已闭环，S5 关闭 | [HTML](qa/RBAC全局权限授予边界S0-S5全过程专业Review-2026-10-16.html) | [MD](qa/RBAC全局权限授予边界S0-S5全过程专业Review-2026-10-16.md) |
| **当前项目全面专业性 Bugbot 评估（2026-10-27）**（评估） | 无待审 diff；版本结构已闭环，工程治理与安全回归成熟，依赖扫描与运行态集成验证仍需收口 | [HTML](qa/当前项目全面专业性Bugbot评估-2026-10-27.html) | [MD](qa/当前项目全面专业性Bugbot评估-2026-10-27.md) |
| **发布治理语义门禁与 Release Notes 收口设计（2026-10）**（已实施） | 文案已收口；tag 门禁与已发布章节语义检查已接入；远端 Release 状态待实际工作流核验 | [HTML](design/发布治理语义门禁与Release-Notes收口设计-2026-10.html) | [MD](design/发布治理语义门禁与Release-Notes收口设计-2026-10.md) |
| **发布治理 Security Review 发现专业性与准确性评估（2026-10-27）** | 4 项发现总体成立；High/Medium 分级基本合理，优先处理凭据隔离、tag 输入和上传后资产完整性 | [HTML](qa/发布治理Security-Review发现专业性准确性评估-2026-10-27.html) | [MD](qa/发布治理Security-Review发现专业性准确性评估-2026-10-27.md) |
| **发布工作流安全加固 S1–S4 设计（2026-10）**（已实施） | 凭据/权限隔离、严格 tag 输入、上传后资产校验、结构化发布状态已接入 | [HTML](design/发布工作流安全加固S1-S4设计-2026-10.html) | [MD](design/发布工作流安全加固S1-S4设计-2026-10.md) |
| **发布工作流 S4 自引用修正设计（2026-10）**（已实施） | 移除源码 manifest 的自身 commit SHA；由构建产物绑定 tag 来源，已消除发布阻断 | [HTML](design/发布工作流S4自引用修正设计-2026-10.html) | [MD](design/发布工作流S4自引用修正设计-2026-10.md) |
| **发布工作流安全加固未提交变更专业评估（2026-10-27）**（历史阻断，已修正） | 曾发现 S4 源码清单 `source_commit` 自引用；现已由 S4 修正设计消除，保留作决策溯源 | [HTML](qa/发布工作流安全加固未提交变更专业评估-2026-10-27.html) | [MD](qa/发布工作流安全加固未提交变更专业评估-2026-10-27.md) |
| **当前提交基线后续优化步骤评估（2026-10-27）**（历史下一步评估） | 当时建议先核验远端信任根；所有者后续已接受单维护者残余风险，当前转入 RBAC U0 | [HTML](qa/当前提交基线后续优化步骤评估-2026-10-27.html) | [MD](qa/当前提交基线后续优化步骤评估-2026-10-27.md) |
| **GitHub 发布信任根核验（2026-10-27）**（所有者已接受风险） | main 未保护、ruleset 为空的事实保留；单人执行 commit/tag/Release，不再阻断当前产品优化 | [HTML](qa/GitHub发布信任根核验-2026-10-27.html) | [MD](qa/GitHub发布信任根核验-2026-10-27.md) |
| **发布治理评估时态误判复盘（2026-10）** | 历史发布阻断被误写为当前状态；已以 tag 与版本一致性门禁复核并校正 | [HTML](postmortem/2026-10-发布治理评估时态误判.html) | [MD](postmortem/2026-10-发布治理评估时态误判.md) |
| **发布工作流安全加固复盘（2026-10）** | 凭据隔离、tag 输入、资产回读、结构化 readiness 已实施并完成专项验收 | [HTML](postmortem/2026-10-发布工作流安全加固复盘.html) | [MD](postmortem/2026-10-发布工作流安全加固复盘.md) |
| **CronPilot 4.1.1 发布就绪度评估（2026-10-27）**（发布阻断） | 候选变更可提交；版本归档与真实 MySQL 迁移演练未闭环，暂不可发版 | [HTML](qa/4.1.1发布就绪度评估-2026-10-27.html) | [MD](qa/4.1.1发布就绪度评估-2026-10-27.md) |
| **当前未提交代码与方案 Bugbot 专业评估（2026-10-26）**（历史基线） | 修复前发现的 2 个 P1 权限缺陷、2 个 P2 真值/交互缺陷 | [HTML](qa/当前未提交代码与方案Bugbot专业评估-2026-10-26.html) | [MD](qa/当前未提交代码与方案Bugbot专业评估-2026-10-26.md) |
| **RBAC 四项 Review 问题闭环优化方案（2026-10）**（待确认） | 服务边界授权、DB-current actor、Session 撤销、全局 Scope 双向映射与最终状态真值契约 | [HTML](design/RBAC四项Review问题闭环优化方案-2026-10.html) | [MD](design/RBAC四项Review问题闭环优化方案-2026-10.md) |
| **RBAC 注册审批拒绝 Scope 授权闭环方案（2026-10）**（已实施） | P1：服务边界对象授权、DB-current actor、异常申请全局治理出口 | [HTML](design/RBAC注册审批拒绝Scope授权闭环方案-2026-10.html) | [MD](design/RBAC注册审批拒绝Scope授权闭环方案-2026-10.md) |
| **RBAC 注册审批拒绝 Scope 授权方案专业评估（2026-10-27）**（方案评估） | 专业通过；待确认审阅授权矩阵后实施 | [HTML](qa/RBAC注册审批拒绝Scope授权方案专业评估-2026-10-27.html) | [MD](qa/RBAC注册审批拒绝Scope授权方案专业评估-2026-10-27.md) |
| **RBAC 用户管理数据库当前授权与 Session 撤销方案（2026-10）**（已实施） | P1：用户管理 7 个入口的数据库当前 Scope 与授权变更原子撤销 | [HTML](design/RBAC用户管理数据库当前授权与Session撤销方案-2026-10.html) | [MD](design/RBAC用户管理数据库当前授权与Session撤销方案-2026-10.md) |
| **RBAC 全局管理员表单 Scope 回显优化方案（2026-10）**（已实施） | 无关联行 global Scope → 表单 `__ALL__` 回显 | [HTML](design/RBAC全局管理员表单Scope回显优化方案-2026-10.html) | [MD](design/RBAC全局管理员表单Scope回显优化方案-2026-10.md) |
| **RBAC 全局管理员表单 Scope 回显方案专业评估（2026-10-27）**（方案评估） | A：展示层映射，不改变授权或持久化语义 | [HTML](qa/RBAC全局管理员表单Scope回显方案专业评估-2026-10-27.html) | [MD](qa/RBAC全局管理员表单Scope回显方案专业评估-2026-10-27.md) |
| **RBAC 批量审批失败项最终状态真值优化方案（2026-10）**（待确认） | 请求动作结果与最终持久化状态分离，消除“失败项保持原状态”误导 | [HTML](design/RBAC批量审批失败项最终状态真值优化方案-2026-10.html) | [MD](design/RBAC批量审批失败项最终状态真值优化方案-2026-10.md) |
| **RBAC 批量审批失败项最终状态方案专业评估（2026-10-27）**（方案评估） | A：结构化 disposition 与 final_status，异常默认未知 | [HTML](qa/RBAC批量审批失败项最终状态方案专业评估-2026-10-27.html) | [MD](qa/RBAC批量审批失败项最终状态方案专业评估-2026-10-27.md) |
| **RBAC 用户管理陈旧 Session 方案专业评估（2026-10-27）**（方案评估） | A- 条件通过；B1 数据库当前授权与 B2 原子撤销须同轮闭环 | [HTML](qa/RBAC用户管理陈旧Session方案专业评估-2026-10-27.html) | [MD](qa/RBAC用户管理陈旧Session方案专业评估-2026-10-27.md) |
| **RBAC 注册审批拒绝 Scope 绕过修复复盘（2026-10-27）**（已修复） | 数据库当前 actor、对象 Scope 与异常申请全局治理闭环 | [HTML](postmortem/2026-10-RBAC注册审批拒绝Scope绕过修复.html) | [MD](postmortem/2026-10-RBAC注册审批拒绝Scope绕过修复.md) |
| **RBAC 批量审批反馈误报成功复盘（2026-10-16）**（已修复） | 三态真值契约、原始异常服务端留存与 trace_id 安全关联 | [HTML](postmortem/2026-10-RBAC批量审批反馈误报成功.html) | [MD](postmortem/2026-10-RBAC批量审批反馈误报成功.md) |
| **RBAC 全局权限授予边界加固方案专业评估（2026-10-15）**（评估） | A-：专业、准确且合理；rev.2 可进入用户确认，确认后按 S0–S5 实施 | [HTML](qa/RBAC全局权限授予边界加固方案专业评估-2026-10-15.html) | [MD](qa/RBAC全局权限授予边界加固方案专业评估-2026-10-15.md) |
| **统一错误处理 P0 与管理平台 REST 方案全面专业 Review（2026-09）**（评估） | 专业性、准确性、合理性与实施阻塞项：request_id、SSR/REST、ContextVar、兼容性 | [HTML](qa/统一错误处理P0与管理平台REST方案全面专业Review-2026-09.html) | [MD](qa/统一错误处理P0与管理平台REST方案全面专业Review-2026-09.md) |
| **B1 认证夹具复盘与修复计划（2026-09）**（Review 未通过） | 30 失败 + 5 错误；统一真实用户、auth_version 与模型注册 | [HTML](postmortem/2026-09-B1认证夹具复盘与修复计划.html) | [MD](postmortem/2026-09-B1认证夹具复盘与修复计划.md) |
| **数据库自增 ID 生成器下线复盘（2026-09）**（已实施） | 根因、写入路径修复、SQLite 结构切换、25 项专项测试与 86 路由冒烟 | [HTML](postmortem/2026-09-数据库自增ID生成器下线.html) | [MD](postmortem/2026-09-数据库自增ID生成器下线.md) |
| **SSRF 内外网区域校验修复（2026-09）**（已实施） | 部署 DNS 控制私网/ULA 可达性、危险地址硬拒绝、单次解析 pinning、重定向防护 | [HTML](postmortem/2026-09-SSRF内外网区域校验修复.html) | [MD](postmortem/2026-09-SSRF内外网区域校验修复.md) |
| **MySQL 任务 ID 关联列类型修复（2026-09）**（已实施） | 任务 ID 关联列统一 BIGINT；高位 ID 写入与迁移 fail-closed | [HTML](postmortem/2026-09-MySQL任务ID关联列类型修复.html) | [MD](postmortem/2026-09-MySQL任务ID关联列类型修复.md) |
| **v4.0.0 之后提交深度 Review（2026-09-20）**（历史审查） | 当时记录的 3 个 P1；当前状态以 2026-10-12 全面复核为准 | [HTML](qa/4.0之后提交深度Review-2026-09-20.html) | [MD](qa/4.0之后提交深度Review-2026-09-20.md) |
| **三份 Review 报告专业性与合理性评估（2026-09-20）** | 技术结论总体成立；校准基线/闭环/观察项的状态治理 | [HTML](qa/三份Review报告专业性与合理性评估-2026-09-20.html) | [MD](qa/三份Review报告专业性与合理性评估-2026-09-20.md) |
| **近期代码变更影响与质量评估（2026-09-20）** | 7063ff7 ID 自增切换：B+ / 条件通过；P1 含 D–F 未闭环与 SQLite ID 复用 | [HTML](qa/近期代码变更影响与质量评估-2026-09-20.html) | [MD](qa/近期代码变更影响与质量评估-2026-09-20.md) |
| **全面代码 Bugbot 评估（2026-09-21）**（不建议发布） | 2 个 P0 SSRF 绕过、4 个 P1：SQLite 迁移中断、IPv6、MySQL 关联列与 DDL fail-open | [HTML](qa/全面代码Bugbot评估-2026-09-21.html) | [MD](qa/全面代码Bugbot评估-2026-09-21.md) |
| **全量测试与 Bugbot 复核（2026-09）**（未通过） | 754 项：4 failures、1 error、11 skipped；last-admin 保护覆盖回归 | [HTML](design/全量测试与Bugbot复核-2026-09.html) | [MD](design/全量测试与Bugbot复核-2026-09.md) |
| **Codex 沙盒服务启停与验收脚本设计（2026-09）**（待确认） | 受限进程/端口/网络环境下的安全启停与 offline 验收 | [HTML](design/Codex沙盒服务启停与验收脚本设计-2026-09.html) | [MD](design/Codex沙盒服务启停与验收脚本设计-2026-09.md) |
| **质量门禁与测试稳定性最小修复方案（2026-09）** | 4 项阻断修复：单测隔离、golden path、CSS reachability、postmortem completeness | [HTML](design/质量门禁与测试稳定性最小修复方案-2026-09.html) | [MD](design/质量门禁与测试稳定性最小修复方案-2026-09.md) |
| **OPT-P0-21 50-bit 任务 ID 生成器最终优化设计**（待确认） | 仅任务 ID 使用 · 32/12/6 位布局 · IP+PORT+PID worker · 引用列 BIGINT | [HTML](design/OPT-P0-21-ID生成策略优化设计.html) | [MD](design/OPT-P0-21-ID生成策略优化设计.md) |
| **OPT-P0-21 数据库自增 ID 写入机制切换设计（2026-09-20）**（待确认） | 下线 next_id · 仅调整自增属性与起点 · 历史数据原样保留 | [HTML](design/OPT-P0-21-数据库自增ID迁移设计-2026-09-20.html) | [MD](design/OPT-P0-21-数据库自增ID迁移设计-2026-09-20.md) |
| ↳ **OPT-P0-21 数据库自增 ID 迁移设计专业 Review（2026-09-20）**（有条件通过） | P0：SQLite 类型契约、Core INSERT 省略主键；P1：引用范围检查与停写边界 | [HTML](design/OPT-P0-21-数据库自增ID迁移设计-专业Review-2026-09-20.html) | [MD](design/OPT-P0-21-数据库自增ID迁移设计-专业Review-2026-09-20.md) |
| **任务执行链路可观测性设计方案（收敛版）**（待确认） | 同步 HTTP 触发执行事件与执行中记录 · 不引入工作流编排 · rev.5 确认页面、线程池与保留边界 | [HTML](design/任务执行链路可观测性设计方案-收敛版.html) | [MD](design/任务执行链路可观测性设计方案-收敛版.md) |
| ↳ **执行详情 URL 字段角色化脱敏修复设计**（已实施） | Bugbot High：全角色 URL 凭据脱敏 · 完整 Presenter DTO · 展示面修复 | [HTML](design/执行详情URL字段角色化脱敏修复设计-2026-09.html) | [MD](design/执行详情URL字段角色化脱敏修复设计-2026-09.md) |
| ↳ 页面对比 Demo | Before/After · 详情主变更 + 列表/任务详情轻量 · 明确不改页 | [HTML](design/任务执行链路可观测性-页面对比Demo.html) | [MD](design/任务执行链路可观测性-页面对比Demo.md) |
| ↳ Run Inspector 目标态场景 Demo | 状态呈现 / 时间线 / 三角色信息边界 | [HTML](design/任务执行链路可观测性-RunInspector-Demo.html) | [MD](design/任务执行链路可观测性-RunInspector-Demo.md) |
| ↳ 收敛版专业 Review | 有条件通过 · 3 Blocker · 7 Major | [HTML](design/任务执行链路可观测性设计方案-收敛版-专业Review.html) | [MD](design/任务执行链路可观测性设计方案-收敛版-专业Review.md) |
| ↳ 专业 Review 评估 | rev.3 对照 · 采纳/修订/拒绝结论 | [HTML](design/任务执行链路可观测性设计方案-收敛版-专业Review评估.html) | [MD](design/任务执行链路可观测性设计方案-收敛版-专业Review评估.md) |
| ↳ 文档与实现功能评估 | 有条件可用 · B4/B5 未闭环 | [HTML](design/任务执行链路可观测性-文档与实现功能评估.html) | [MD](design/任务执行链路可观测性-文档与实现功能评估.md) |
| ↳ 当前实现评估（2026-09-17） | 有条件可用 · 执行观测闭环，调度注册观测未闭环 | [HTML](design/任务执行链路可观测性-当前实现评估-2026-09-17.html) | [MD](design/任务执行链路可观测性-当前实现评估-2026-09-17.md) |
| ↳ 执行侧观测专项评估（2026-09-17） | 约 75% · 单次运行诊断可用，事件上下文与降级提示待补 | [HTML](design/任务执行链路可观测性-执行侧观测专项评估-2026-09-17.html) | [MD](design/任务执行链路可观测性-执行侧观测专项评估-2026-09-17.md) |
| ↳ 执行侧观测近期提交专业 Review 评估（2026-09-18） | 有条件通过 · c30353b/0a303ed/4d8f2ac · 2 Medium / 2 Low / 2 Info | [HTML](design/执行侧观测近期提交专业Review评估-2026-09-18.html) | [MD](design/执行侧观测近期提交专业Review评估-2026-09-18.md) |
| ↳ 执行侧观测优化完成后全面 Review（2026-09-18） | 有条件通过 · R1/R2/R5/R8 已关闭 · R3/R4/R6/R7 待后续 | [HTML](design/执行侧观测优化完成后全面Review-2026-09-18.html) | [MD](design/执行侧观测优化完成后全面Review-2026-09-18.md) |
| ↳ 执行侧观测 R1 状态兜底修复（2026-09-18） | 已实施 · client_failed/not_started/unknown_failure/未知值 · 三角色真实路由矩阵 | [HTML](postmortem/2026-09-执行侧观测R1状态兜底修复.html) | [MD](postmortem/2026-09-执行侧观测R1状态兜底修复.md) |
| ↳ 执行侧观测 R2 异常矩阵修复（2026-09-18） | 已实施 · 异常子类/response 证据分流 · 保守传输状态 | [HTML](postmortem/2026-09-执行侧观测R2异常矩阵修复.html) | [MD](postmortem/2026-09-执行侧观测R2异常矩阵修复.md) |
| ↳ 传输状态机收口设计（2026-09-18） | 部分实施 · R1/R2 已完成 · Run Inspector 页面对比 | [HTML](design/执行侧观测-传输状态机收口设计-2026-09-18.html) | [MD](design/执行侧观测-传输状态机收口设计-2026-09-18.md) |
| ↳ 执行侧观测优化设计（2026-09） | 待确认 · run_id 强关联、事件上下文、降级可见、统一时间线 | [HTML](design/执行侧观测优化设计-2026-09.html) | [MD](design/执行侧观测优化设计-2026-09.md) |
| ↳ run_id 强关联决策说明（2026-09） | 待确认 · 数据一致性、迁移兼容、查询与回滚边界 | [HTML](design/执行侧观测-run_id强关联决策说明-2026-09.html) | [MD](design/执行侧观测-run_id强关联决策说明-2026-09.md) |
| ↳ **失败分类与 HTTP 响应语义优化设计（2026-09）**（已实施） | 统一失败分类、请求生命周期、无响应语义与 Before/After Demo | [HTML](design/执行侧观测-失败分类与HTTP响应语义优化设计-2026-09.html) | [MD](design/执行侧观测-失败分类与HTTP响应语义优化设计-2026-09.md) |
| ↳ **R1 执行记录列表 pending/running 显示收口**（已实施） | 已入队徽章 +「进行中」筛选 · 不改默认非成功 | [HTML](design/R1-执行记录列表pending-running显示收口设计-2026-09.html) | [MD](design/R1-执行记录列表pending-running显示收口设计-2026-09.md) |
| ↳ **R2 Run Inspector Presenter/详情契约收口**（已实施） | 时间线上移 · 禁 raw detail JSON · Viewer/Operator/Admin | [HTML](design/R2-RunInspector-Presenter详情契约收口设计-2026-09.html) | [MD](design/R2-RunInspector-Presenter详情契约收口设计-2026-09.md) |
| ↳ **R2-D Run Inspector 对齐 Demo §C**（待确认） | 页面对比=Demo §C 原文 · 纠偏 R2 | [HTML](design/R2-D-RunInspector对齐页面对比Demo-C设计-2026-09.html) | [MD](design/R2-D-RunInspector对齐页面对比Demo-C设计-2026-09.md) |
| ↳ **R3 执行可观测性契约门禁**（已实施） | B0 合同测试 · Tracer↔Presenter · 无 UI；R3-C 另评 | [HTML](design/R3-执行可观测性契约门禁设计-2026-09.html) | [MD](design/R3-执行可观测性契约门禁设计-2026-09.md) |
| ↳ **R3-C 任务详情最近执行状态语义**（暂停） | 非本轮所指；页面对比=Demo §B | [HTML](design/R3-C-任务详情最近执行状态语义收口设计-2026-09.html) | [MD](design/R3-C-任务详情最近执行状态语义收口设计-2026-09.md) |
| ↳ Scope 过滤（L2 专章） | admin / 1～2 Scope Demo | [HTML](design/规模化Scope过滤与角色差异化设计.html) | [MD](design/规模化Scope过滤与角色差异化设计.md) |
| ↳ L1/L2/L3 评审归档 | 讨论隐阱；结论已收束至总稿 | [HTML](design/规模化双层IA与任务健康模型评审.html) | [MD](design/规模化双层IA与任务健康模型评审.md) |
| P1 可观测小步 OPT-P1-01b/c | 失败筛选 · 展示统一 | [HTML](plan/P1可观测小步优化设计.html) | [MD](plan/P1可观测小步优化设计.md) |
| P1 执行详情与立即执行 OPT-P1-03/04 | 独立详情 URL · 立即执行 | [HTML](plan/P1执行详情与立即执行设计.html) | [MD](plan/P1执行详情与立即执行设计.md) |
| Tier 3 前置收束 | 去 `records` 裸 SQL | [HTML](deps/Tier3前置收束设计.html) | [MD](deps/Tier3前置收束设计.md) |

## ④ 已交付设计（归档）

| 文档 | 说明 | HTML | Markdown |
|------|------|------|----------|
| **RBAC 缓存失效与提交后处理边界统一修复设计**（已实施） | 跨入口快照、事务及缓存防护 | [HTML](design/rbac-cache-postcommit-boundary-2026-11-04.html) | [MD](design/rbac-cache-postcommit-boundary-2026-11-04.md) |
| **4.2.0 发布前图片证据治理设计**（已实施） | 发布门禁、证据保留及安全审查 | [HTML](design/release-image-governance-2026-11-03.html) | [MD](design/release-image-governance-2026-11-03.md) |
| **发布前六项测试失败分类与修复设计**（已实施） | Scope、CSRF 与状态模块测试契约 | [HTML](design/release-six-test-baseline-2026-11-03.html) | [MD](design/release-six-test-baseline-2026-11-03.md) |
| **SQLite 调度索引完整性异常诊断与恢复设计**（已修复） | 隔离复演、备份、停写与定向恢复 | [HTML](design/sqlite-jobstore-index-recovery-2026-11-03.html) | [MD](design/sqlite-jobstore-index-recovery-2026-11-03.md) |
| **任务启停提交后读取异常修复设计**（已实施） | 摘要快照、兼容重试与失败分类 | [HTML](design/status-postcommit-snapshot-repair-2026-11-03.html) | [MD](design/status-postcommit-snapshot-repair-2026-11-03.md) |
| **任务链路日志完整性增强设计**（已交付） | 过程日志 · job_log 四列 · 详情页触发来源 | [HTML](design/任务链路日志完整性增强设计.html) | [MD](design/任务链路日志完整性增强设计.md) |
| **管理员 admin Scope 差异化** OPT-P2-15 | 种子只读 · 管理员按组 · `__ALL__` · **v2.7.0** | [HTML](design/管理员admin-Scope差异化设计.html) | [MD](design/管理员admin-Scope差异化设计.md) |
| **OPT-P0-22 停用用户同名申请恢复设计**（已交付） | 覆盖 OPT-P1-10 §3.1.7 · 保留原 user_id · 审批警示 · auth_version · 文案契约 | [HTML](design/停用用户同名恢复设计.html) · [页面对比 Demo](design/停用用户同名恢复-页面对比Demo.html) | [MD](design/停用用户同名恢复设计.md) |
| **测试 Session 补齐 auth_version 修复设计**（已交付） | HTTP Fixture 对齐 OPT-P0-22 fail-closed · 2026-09-11 定向回归 21 项通过 | [HTML](design/测试Session补齐auth-version修复设计.html) | [MD](design/测试Session补齐auth-version修复设计.md) |
| **近期提交 P1/P2 问题深度评估与修复设计（2026-09）**（待确认） | 认证 fixture 与 URL/签名一致性 · 已复现证据 · 分批修复与验收 | [HTML](design/近期提交P1-P2问题深度评估与修复设计-2026-09.html) | [MD](design/近期提交P1-P2问题深度评估与修复设计-2026-09.md) |
| **审计日志 Scope 过滤 RFC** OPT-P2-16 | `actor_group_ids` LIKE 过滤 · **v2.7.0** | [HTML](design/审计日志Scope过滤RFC.html) | [MD](design/审计日志Scope过滤RFC.md) |
| **Prometheus 指标 RFC** OPT-P1-06 | Prometheus 接入 · Grafana Dashboard · **v2.2.0** | [HTML](design/P1可观测性-Prometheus指标RFC.html) | [MD](design/P1可观测性-Prometheus指标RFC.md) |
| Phase D3 · Docker pin 矩阵 | requirements-docker.txt · **v2.1.0** | [HTML](deps/PhaseD3-Docker-pin矩阵设计.html) | [MD](deps/PhaseD3-Docker-pin矩阵设计.md) |
| Tier 3c · 生产类库备份与只读校验 OPT-P2-11 | **搁置**（无存量升级 · 不实现） | [HTML](deps/Tier3c-生产类库备份与只读校验设计.html) | [MD](deps/Tier3c-生产类库备份与只读校验设计.md) |
| Tier 3b · 迁移重放与残余收束 OPT-P2-11 | ensure 空库重放 · 3b-A · **v2.1.0** | [HTML](deps/Tier3b-迁移重放与残余收束设计.html) | [MD](deps/Tier3b-迁移重放与残余收束设计.md) |
| Phase D2 · Mapped 模型迁移 | datas/model 九表 Mapped[] · test_mapped_model_guard · **v2.1.0** | [HTML](deps/PhaseD2-Mapped模型迁移.html) | [MD](deps/PhaseD2-Mapped模型迁移.md) |
| Phase D0 · Framework Generation 决策 | DEC-008 · Py 3.8–3.11 · Flask 2.3 + SA2/FSA3 同窗 · **v2.1.0** | [HTML](deps/PhaseD0-Framework-Generation决策.html) | [MD](deps/PhaseD0-Framework-Generation决策.md) |
| Phase C · ORM Legacy AST 门禁 | AST 禁止 Legacy ORM 回潮 · CI · **v2.1.0** | [HTML](deps/PhaseC-ORM-Legacy-AST门禁设计.html) | [MD](deps/PhaseC-ORM-Legacy-AST门禁设计.md) |
| 管理端 UI 优化（A′+B1） | 执行记录交互 · v0.2.0 | [HTML](design/管理端UI优化设计.html) | [MD](design/管理端UI优化设计.md) |
| P1 可观测 OPT-P1-01/02 | status / 失败规则 · v0.2.0 | [HTML](plan/P1可观测优化设计.html) | [MD](plan/P1可观测优化设计.md) |
| 技术方案与前端设计 | 早期线框（参考） | [HTML](design/技术方案与前端设计.html) | [MD](design/技术方案与前端设计.md) |

## ⑤ 产品需求与竞品对照

| 文档 | 说明 | HTML | Markdown |
|------|------|------|----------|
| 产品优化需求（PRD） | P0/P1/P2 · OPT 编号 | [HTML](product/产品优化需求-借鉴Plombery.html) | [MD](product/产品优化需求-借鉴Plombery.md) |
| Plombery 深度对比 | 全维度对照 | [HTML](product/Plombery深度对比分析.html) | [MD](product/Plombery深度对比分析.md) |

## ⑥ 依赖演进（RFC）

| 文档 | 说明 | HTML | Markdown |
|------|------|------|----------|
| **依赖升级 RFC** | Tier 0–2 · Phase A–D2 · Tier 3b-A ✓ · **v2.1.0** · D3 待收尾 · 3c 搁置 | [HTML](deps/依赖升级RFC.html) | [MD](deps/依赖升级RFC.md) |
| ↳ Phase C · AST 门禁 | 已交付 | [HTML](deps/PhaseC-ORM-Legacy-AST门禁设计.html) | [MD](deps/PhaseC-ORM-Legacy-AST门禁设计.md) |
| ↳ Phase D0 · 框架代际决策 | 已确认 DEC-008 | [HTML](deps/PhaseD0-Framework-Generation决策.html) | [MD](deps/PhaseD0-Framework-Generation决策.md) |
| ↳ Phase D2 · Mapped[] | 已交付 | [HTML](deps/PhaseD2-Mapped模型迁移.html) | [MD](deps/PhaseD2-Mapped模型迁移.md) |
| ↳ Tier 3b · ensure 重放（3b-A） | 已交付 | [HTML](deps/Tier3b-迁移重放与残余收束设计.html) | [MD](deps/Tier3b-迁移重放与残余收束设计.md) |

## ⑦ 部署与运维

| 文档 | 说明 | HTML | Markdown |
|------|------|------|----------|
| Docker 部署指南 | compose · 验收 · 数据卷 | [HTML](ops/Docker部署指南.html) | [MD](ops/Docker部署指南.md) |
| 非 Docker 部署指南 | 裸机 · systemd · Nginx | [HTML](ops/非Docker部署指南.html) | [MD](ops/非Docker部署指南.md) |
| Linux 安装总览 | 一键安装 · venv | — | [MD](ops/linux安装与运行.md) |
| Ubuntu / CentOS | 分发行版说明 | — | [Ubuntu](ops/ubuntu安装与运行.md) · [CentOS](ops/centos安装与运行.md) |
| INSTALL 速查 | 仓库根 | — | [INSTALL.md](../INSTALL.md) |


## ⑧ 验收、工程与合规

| 文档 | 说明 | HTML | Markdown |
|------|------|------|----------|
| **发布包运行时模板字节保护修复设计** | 发布阻断，待确认 | [HTML](design/release-runtime-template-preservation-2026-11-04.html) | [MD](design/release-runtime-template-preservation-2026-11-04.md) |
| **v4.2.0 发布评估与手动命令** | 候选准备、无截图安装包验证 | [HTML](qa/v4.2.0-release-assessment-2026-11-04.html) | [MD](qa/v4.2.0-release-assessment-2026-11-04.md) |
| **v4.1.1 后全部提交 Bugbot 复审（HEAD 0e31f8f）** | 六个提交、当前复核与验证边界 | [HTML](qa/post-v4.1.1-bugbot-review-head-0e31f8f-2026-11-04.html) | [MD](qa/post-v4.1.1-bugbot-review-head-0e31f8f-2026-11-04.md) |
| **缓存失效与提交后读取同类排查** | 入口矩阵及故障探针 | [HTML](qa/cache-postcommit-audit-2026-11-04.html) | [MD](qa/cache-postcommit-audit-2026-11-04.md) |
| **v4.1.1 后全部提交复审（2026-11-04）** | 独立 HEAD 及发布阻断复核 | [HTML](qa/post-v4.1.1-commit-review-2026-11-04.html) | [MD](qa/post-v4.1.1-commit-review-2026-11-04.md) |
| **v4.2.0 发布前未提交代码与文档全面审查（2026-10-30）** | 暂缓发布：SQLite 独立连接竞态、门禁与升级边界；详源报告 | [HTML](qa/v4.2.0-release-review-2026-10-30.html) | [MD](qa/v4.2.0-release-review-2026-10-30.md) |
| **SQLite 用户编辑原子保护验收（2026-11-02）** | 专项通过；任务子项与全量基线失败保留 | [HTML](qa/SQLite用户编辑原子保护验收-2026-11-02.html) | [MD](qa/SQLite用户编辑原子保护验收-2026-11-02.md) |
| **SQLite 用户编辑保存边界原子保护复盘** | 七项复盘与真实竞争预防 | [HTML](postmortem/2026-11-SQLite用户编辑保存边界原子保护.html) | [MD](postmortem/2026-11-SQLite用户编辑保存边界原子保护.md) |
| **下一步方案合理性、专业性与准确性评估（2026-11-02）** | 条件通过；串行顺序、竞争测试、事务所有权和基线绑定 | [HTML](qa/下一步方案合理性专业性准确性评估-2026-11-02.html) | [MD](qa/下一步方案合理性专业性准确性评估-2026-11-02.md) |
| **验收后下一步与发布前优先级梳理（2026-11-02）** | SQLite保存边界优先；提交、发布与治理分批 | [HTML](qa/验收后下一步与发布前优先级梳理-2026-11-02.html) | [MD](qa/验收后下一步与发布前优先级梳理-2026-11-02.md) |
| **提交 c727146 后代码与文档复审（2026-11-03）** | 全量与发布门禁、SQLite任务/启停撤权及提交后读取实证；原有变更全部提交 | [HTML](qa/commit-review-2026-11-03.html) | [MD](qa/commit-review-2026-11-03.md) |
| **RBAC 用户编辑七状态浏览器验收（2026-10-30）** | 七状态、原生POST与提交真值对照；详源验收 | [HTML](qa/RBAC用户编辑七状态浏览器验收-2026-10-30.html) | [MD](qa/RBAC用户编辑七状态浏览器验收-2026-10-30.md) |
| **RBAC 七状态浏览器验收与锁成本校准复盘** | F2/F3关闭；七项复盘与可执行预防 | [HTML](postmortem/2026-10-RBAC七状态浏览器验收与锁成本校准.html) | [MD](postmortem/2026-10-RBAC七状态浏览器验收与锁成本校准.md) |
| **RBAC 锁释放验收观察边界修复复盘（2026-10-29）** | F1关闭；同上下文真实MySQL探针与负向校准；七项复盘 | [HTML](postmortem/2026-10-RBAC锁释放验收观察边界.html) | [MD](postmortem/2026-10-RBAC锁释放验收观察边界.md) |
| **数据库事务与锁使用规范及当前实现评估（2026-10-29）** | 事务所有权、Session、最小锁、统一写协议、索引/隔离与失败恢复 | [HTML](qa/数据库事务与锁使用规范及当前实现评估-2026-10-29.html) | [MD](qa/数据库事务与锁使用规范及当前实现评估-2026-10-29.md) |
| **未提交代码与方案补修后全面复核（2026-10-29）**（历史评估） | F1/F2/F3均已按专项关闭；原始发现与历史证据保留 | [HTML](qa/未提交代码与方案补修后全面复核-2026-10-29.html) | [MD](qa/未提交代码与方案补修后全面复核-2026-10-29.md) |
| **RBAC 用户编辑 U0 契约基线与缺口证据（2026-10-28）**（U0 已完成） | no-op 双 commit/审计/缓存副作用、邮箱清空意图丢失、写边界授权和审计原子性缺口；安全基线 18/18 | [HTML](qa/RBAC用户编辑U0契约基线与缺口证据-2026-10-28.html) | [MD](qa/RBAC用户编辑U0契约基线与缺口证据-2026-10-28.md) |
| **RBAC 用户编辑 U2 事务收口验收（2026-10-29）**（U2 通过） | 19 项专项、106 项相关、真实 MySQL 双连接、浏览器正反向；准确性/专业性/合理性 A | [HTML](qa/RBAC用户编辑U2事务收口验收-2026-10-29.html) | [MD](qa/RBAC用户编辑U2事务收口验收-2026-10-29.md) |
| **RBAC 两项 P1 快照回显与验收库隔离修复复盘（2026-10-29）** | 永久负向测试、隔离 MySQL 与目标角色浏览器证据；P2 保留 | [HTML](postmortem/2026-10-RBAC两项P1快照回显与验收库隔离.html) | [MD](postmortem/2026-10-RBAC两项P1快照回显与验收库隔离.md) |
| **RBAC 用户编辑范围外组误删修复复盘（2026-10-29）** | 同范围意图与外组保护，双后端/全量/浏览器已验证 | [HTML](postmortem/2026-10-RBAC用户编辑范围外组误删.html) | [MD](postmortem/2026-10-RBAC用户编辑范围外组误删.md) |
| **RBAC 两项 P2 组选择与审计契约回退修复复盘（2026-10-29）** | 228 项联合、18 组 preflight、16 项 live；初始四项已关闭，新增 R5 已另批修复 | [HTML](postmortem/2026-10-RBAC两项P2组选择与审计契约回退.html) | [MD](postmortem/2026-10-RBAC两项P2组选择与审计契约回退.md) |
| **未提交代码与文档专业评估（2026-10-29）**（初评历史） | 2 项 P1、2 项 P2；含运行复现与本轮门禁记录 | [HTML](qa/未提交代码与文档专业评估-2026-10-29.html) | [MD](qa/未提交代码与文档专业评估-2026-10-29.md) |
| **RBAC 用户编辑 U3 交互与审计展示验收（2026-10-29）**（U3 通过） | 24 项专项、111 项相关、81 项 Scope 回归、86 条路由及浏览器正反向验证；准确性/专业性/合理性 A | [HTML](qa/RBAC用户编辑U3交互与审计展示验收-2026-10-29.html) | [MD](qa/RBAC用户编辑U3交互与审计展示验收-2026-10-29.md) |
| **编辑与修改业务流程同类一致性风险审计（2026-10-28）** | 任务编辑 P0；个人资料/业务组/标签存在 no-op 与陈旧覆盖；凭据和审批存在成功审计二次提交 | [HTML](qa/编辑与修改业务流程同类一致性风险审计-2026-10-28.html) | [MD](qa/编辑与修改业务流程同类一致性风险审计-2026-10-28.md) |
| **xiaoniu_cron ↔ CronPilot 页面截图对照（2026-09）**（已交付） | 双系统实装截图 · 同构 5 页并排 + CronPilot 独有页 | [HTML](qa/xiaoniu_cron与CronPilot-页面截图对照-2026-09.html) | [MD](qa/xiaoniu_cron与CronPilot-页面截图对照-2026-09.md) |
| **工程代价与终局对比：xiaoniu_cron → CronPilot v4.0**（已交付） | 工程过程十条教训 · 双项目终局矩阵 · 赢/输/欠账裁决 | [HTML](qa/工程代价与终局对比-xiaoniu_cron与CronPilot-2026-09.html) | [MD](qa/工程代价与终局对比-xiaoniu_cron与CronPilot-2026-09.md) |
| **假完成工业：Cursor 重构十年级开源项目的工程病理学报告**（已交付） | 长篇尸检 · 时间经济学/认识论/安全先验/治理军备 · 四场手术级病例 · 双账本 | [HTML](qa/假完成工业-Cursor重构工程病理学-2026-09.html) | [MD](qa/假完成工业-Cursor重构工程病理学-2026-09.md) |
| **我用 10 天用 Cursor 重构了一个 10 年前的 GitHub 项目，没想到有这么多坑**（已交付） | 专栏 · v0.1→v4.0 变更账本 · 量化指标 · 七种假完成与深层机制 | [HTML](qa/我用Cursor重构十年GitHub项目的坑-专栏-2026-09.html) | [MD](qa/我用Cursor重构十年GitHub项目的坑-专栏-2026-09.md) |
| **当前项目架构与代码质量全面评估报告（2026-09）**（待确认） | 架构 · 代码质量 · Bugbot 缺陷；逐项说明根因、影响、方案选型、实施路径与验收标准；统一采用“定时 HTTP 触发请求”术语 | [HTML](qa/当前项目架构与代码质量全面评估报告-2026-09.html) | [MD](qa/当前项目架构与代码质量全面评估报告-2026-09.md) |
| **未提交变更与方案评估（2026-09-16）**（已交付） | HEAD Run Inspector 断链 · WIP 热修可提交 · B4/B5/B6 未交付 | [HTML](qa/未提交变更与方案评估-2026-09-16.html) | [MD](qa/未提交变更与方案评估-2026-09-16.md) |
| **v4.0.0 之后变更与功能健康评估（2026-09-11）**（已交付） | 11 提交梳理 · 定向 148 绿 · 全量夹具红 · 未提交 P1/P2 分离 | [HTML](qa/v4.0.0之后变更与功能健康评估-2026-09.html) | [MD](qa/v4.0.0之后变更与功能健康评估-2026-09.md) |
| P0 测试与验收手册 | 用例 · 冒烟 · 签字 | [HTML](qa/P0测试用例与验收手册.html) | [MD](qa/P0测试用例与验收手册.md) |
| License Audit | Apache-2.0 合规 | [HTML](qa/LICENSE-AUDIT.html) | [MD](qa/LICENSE-AUDIT.md) |
| 文档同步说明 | HTML↔MD · CI | — | [MD](qa/文档同步说明.md) |

---

## 复盘文档（本轮新增）

| 文档 | 说明 | HTML | Markdown |
|------|------|------|----------|
| **SQLite 任务在途撤权发布阻断评估** | 当前证据与修复顺序 | [HTML](qa/sqlite-revocation-next-assessment-2026-11-03.html) | [MD](qa/sqlite-revocation-next-assessment-2026-11-03.md) |
| **术语门禁分类与历史证据边界修复（2026-11-03）** | 工具契约、否定测试与历史证据 | [HTML](postmortem/2026-11-术语门禁分类与历史证据边界.html) | [MD](postmortem/2026-11-术语门禁分类与历史证据边界.md) |
| **任务编辑基线工具语义漂移修复（2026-11-03）** | 工具契约、否定测试与历史证据 | [HTML](postmortem/2026-11-任务编辑基线工具语义漂移.html) | [MD](postmortem/2026-11-任务编辑基线工具语义漂移.md) |
| **RBAC 全局管理员表单 Scope 回显缺失（2026-10-27）** | 零关联行 global Scope 的表单 marker 回显 | [HTML](postmortem/2026-10-RBAC全局管理员表单Scope回显缺失.html) | [MD](postmortem/2026-10-RBAC全局管理员表单Scope回显缺失.md) |
| **RBAC 用户编辑写前意图缺失 U1 修复（2026-10-28）** | 签名快照、纯规范化、no-op 写前短路、邮箱清空确认契约与状态只读 | [HTML](postmortem/2026-10-RBAC用户编辑写前意图缺失.html) | [MD](postmortem/2026-10-RBAC用户编辑写前意图缺失.md) |
| **RBAC 用户编辑并发覆盖与审计分裂 U2 修复（2026-10-29）** | 数据库当前授权、确定顺序行锁、三方比较、业务与审计同事务 | [HTML](postmortem/2026-10-RBAC用户编辑并发覆盖与审计分裂.html) | [MD](postmortem/2026-10-RBAC用户编辑并发覆盖与审计分裂.md) |
| **RBAC 用户编辑 U3 前端回退与审计展示修复（2026-10-29）** | 前端 no-op 预检、邮箱清空二次确认、稳定 outcome 与版本化审计安全展示 | [HTML](postmortem/2026-10-RBAC用户编辑U3前端回退与审计展示.html) | [MD](postmortem/2026-10-RBAC用户编辑U3前端回退与审计展示.md) |
| **RBAC 用户管理陈旧 Session 读取（2026-10-27）** | 7 个入口数据库当前 actor · 单事务版本撤销 | [HTML](postmortem/2026-10-RBAC用户管理陈旧Session读取.html) | [MD](postmortem/2026-10-RBAC用户管理陈旧Session读取.md) |
| **RBAC 全局权限授予边界缺失（2026-10）** | actor/target 授权混淆 · 数据库当前事实 · 写前拒绝 · 写入安全与 F-01/F-02 已闭环，S5 正式通过 | [HTML](postmortem/2026-10-RBAC全局权限授予边界缺失.html) | [MD](postmortem/2026-10-RBAC全局权限授予边界缺失.md) |
| **停用用户同名覆盖启用（OPT-P0-22）** | 删行重建 → 原行覆盖 · 申请人零提示 · auth_version fail-closed | [HTML](postmortem/2026-09-停用用户同名恢复.html) | [MD](postmortem/2026-09-停用用户同名恢复.md) |
| **auth_version Session 缺键 Fail-Open** | OPT-P0-22 B2 | [HTML](postmortem/2026-09-auth-version-session-failopen.html) | [MD](postmortem/2026-09-auth-version-session-failopen.md) |
| **全局管理员可停用种子账号** | Scope bypass 短路 · 双路径拦截 | [HTML](postmortem/2026-09-全局管理员可停用种子账号.html) | [MD](postmortem/2026-09-全局管理员可停用种子账号.md) |
| **文档索引结构损坏与登记丢失** | 剪贴断裂 · 登记删除 · 索引结构与复盘登记门禁 | [HTML](postmortem/2026-09-文档索引结构损坏与登记丢失.html) | [MD](postmortem/2026-09-文档索引结构损坏与登记丢失.md) |
| **任务链路日志 Bug 修复** | NameError · 签名脱敏 · to_json 死字段 | [HTML](postmortem/2026-09-任务链路日志Bug修复复盘.html) | [MD](postmortem/2026-09-任务链路日志Bug修复复盘.md) |
| **评估交付格式与测试状态漂移** | Canvas 误作交付 · 测试状态错误标记 · 双格式与索引防护 | [HTML](postmortem/2026-09-评估交付格式与测试状态漂移.html) | [MD](postmortem/2026-09-评估交付格式与测试状态漂移.md) |
| **P1 测试夹具认证契约漂移** | Session schema fixture · 模型注册顺序 · fail-closed 回归 | [HTML](postmortem/2026-09-P1测试夹具认证契约漂移.html) | [MD](postmortem/2026-09-P1测试夹具认证契约漂移.md) |
| **P2 触发 URL 签名与记录不一致** | fragment 解析 · PreparedRequest · 签名脱敏边界 | [HTML](postmortem/2026-09-P2触发URL签名与记录不一致.html) | [MD](postmortem/2026-09-P2触发URL签名与记录不一致.md) |
| **设计 Demo HTML 未入库丢失** | 未跟踪 Demo 被删无法 git 恢复 · 索引链接存在性门禁 | [HTML](postmortem/2026-09-设计Demo未入库丢失.html) | [MD](postmortem/2026-09-设计Demo未入库丢失.md) |
| **执行记录 pending 误标「未知」** | 已入队徽章 · in_progress 白名单 · KNOWN_OUTCOMES | [HTML](postmortem/2026-09-执行记录pending误标未知.html) | [MD](postmortem/2026-09-执行记录pending误标未知.md) |
| **健康度未满阈值误标「健康」** | 失败 1～2 次勿标健康 · 写 unknown + UI「有失败」 | [HTML](postmortem/2026-09-健康度未满阈值误标健康.html) | [MD](postmortem/2026-09-健康度未满阈值误标健康.md) |
| **UX 设计方案与页面对比拆分** | 单页 UX 误拆独立 Demo · 默认内嵌进设计稿 | [HTML](postmortem/2026-09-UX设计方案与页面对比拆分.html) | [MD](postmortem/2026-09-UX设计方案与页面对比拆分.md) |
| **R3-C 设计偏离原方案 Demo UI** | 子设计 AFTER 须锚定父 Demo §B · ●/◎+文案同构 | [HTML](postmortem/2026-09-R3-C设计偏离原方案DemoUI.html) | [MD](postmortem/2026-09-R3-C设计偏离原方案DemoUI.md) |
| **误把 Demo §C 当成 §B** | 多节 Demo 须写明节号 · Run Inspector 非任务详情 | [HTML](postmortem/2026-09-误把Demo-C当成-B.html) | [MD](postmortem/2026-09-误把Demo-C当成-B.md) |
| **执行详情 URL 脱敏缺失修复** | Presenter 边界 · 全参数值脱敏 · HTML 否定断言 | [HTML](postmortem/2026-09-execution-detail-url-redaction.html) | [MD](postmortem/2026-09-execution-detail-url-redaction.md) |
| **执行失败分类与 HTTP 响应语义** | TypeError 误归类 · 无响应语义缺失 · 参数准备与实际发送混淆 | [HTML](postmortem/2026-09-执行失败分类与HTTP响应语义.html) | [MD](postmortem/2026-09-执行失败分类与HTTP响应语义.md) |
| **执行侧观测传输状态误导修复** | 连接失败/已发送未响应分流 · F1 已修复 | [HTML](postmortem/2026-09-执行侧观测传输状态误导修复.html) | [MD](postmortem/2026-09-执行侧观测传输状态误导修复.md) |
| **执行侧观测 sent 状态判定修复** | Presenter/模板契约对齐 · F2 已修复 | [HTML](postmortem/2026-09-执行侧观测sent状态判定修复.html) | [MD](postmortem/2026-09-执行侧观测sent状态判定修复.md) |
| **Run Inspector HTTP 状态标签未消费修复** | Presenter/模板字段对齐 · F3 已修复 | [HTML](postmortem/2026-09-RunInspector-http状态标签未消费修复.html) | [MD](postmortem/2026-09-RunInspector-http状态标签未消费修复.md) |
| **执行侧观测外层 fatal 阶段映射修复** | outer fatal 三阶段映射 · F6 已修复 | [HTML](postmortem/2026-09-执行侧观测外层fatal阶段映射修复.html) | [MD](postmortem/2026-09-执行侧观测外层fatal阶段映射修复.md) |
| **执行侧观测 R2 异常矩阵修复** | 异常子类/response 证据分流 · 保守传输状态 | [HTML](postmortem/2026-09-执行侧观测R2异常矩阵修复.html) | [MD](postmortem/2026-09-执行侧观测R2异常矩阵修复.md) |
| **PinnedIPAdapter HTTP 协议参数错误** | HTTP 误传 TLS 参数 · HTTP/HTTPS 分支修复 | [HTML](postmortem/2026-09-PinnedIPAdapter-HTTP协议参数错误.html) | [MD](postmortem/2026-09-PinnedIPAdapter-HTTP协议参数错误.md) |
| **任务详情 seconds 展示丢失修复** | 调度表达式完整性 · 六字段展示 | [HTML](postmortem/2026-09-task-detail-seconds-display.html) | [MD](postmortem/2026-09-task-detail-seconds-display.md) |
| **Dashboard 相对时间测试确定性修复** | 可注入时间基准 · 消除时钟漂移 | [HTML](postmortem/2026-09-dashboard-relative-time-test-determinism.html) | [MD](postmortem/2026-09-dashboard-relative-time-test-determinism.md) |
| **全量回归门禁收口修复** | legacy 门禁 · 无上下文日志 | [HTML](postmortem/2026-09-regression-gate-cleanup.html) | [MD](postmortem/2026-09-regression-gate-cleanup.md) |
| **ORM legacy 门禁误报修复** | urlsplit 别名与 `.query` 误报 | [HTML](postmortem/2026-09-ORM-legacy-urlsplit误报修复.html) | [MD](postmortem/2026-09-ORM-legacy-urlsplit误报修复.md) |

## 在线访问（服务启动后）

- HTML：`http://<主机>:5860/docs/` 或 `/docs/index.html`（本地默认亦可 `:5001`）
- Markdown：`/docs/index.md` 及各 `.md`

## 仓库根目录

- [README.md](../README.md) — 快速开始
- [INSTALL.md](../INSTALL.md) — 安装速查
- [RELEASE_NOTES.md](../RELEASE_NOTES.md) — 版本变更（与 HTML Release Notes 同步）

---

*CronPilot · 技术文档索引 · 当前正式版本 v4.0.0 · 4.1.0 候选版整理中*
# 专项评审入口

- RBAC 注册审批关联表 R2-2E1 一致性加固实施验收（审批集合核验、切读后 verify-only，2026-10-22）：[HTML](qa/RBAC注册审批关联表R2-2E1一致性加固实施验收-2026-10-22.html) · [Markdown](qa/RBAC注册审批关联表R2-2E1一致性加固实施验收-2026-10-22.md)

- RBAC 注册审批关联表 R2-2E2 数据库性能验收阻断报告（100k SQLite 真值/索引通过；10 组 2.219×超阈值；MySQL 证实父表 ALL 扫描，2026-10-22）：[HTML](qa/RBAC注册审批关联表R2-2E2数据库性能验收阻断报告-2026-10-22.html) · [Markdown](qa/RBAC注册审批关联表R2-2E2数据库性能验收阻断报告-2026-10-22.md)
- RBAC 注册审批关联表 R2-2E2 校准性能验收（Fix B 集合聚合；MySQL 10k/30k、并发 5 与 SQLite 四档绝对 SLO 全部通过，2026-10-23）：[HTML](qa/RBAC注册审批关联表R2-2E2校准性能验收-2026-10-23.html) · [Markdown](qa/RBAC注册审批关联表R2-2E2校准性能验收-2026-10-23.md)
- RBAC 注册审批关联表 R2-2E3 集成验收（专项、全量、86 路由、黄金路径与浏览器角色矩阵通过，2026-10-23）：[HTML](qa/RBAC注册审批关联表R2-2E3集成验收-2026-10-23.html) · [Markdown](qa/RBAC注册审批关联表R2-2E3集成验收-2026-10-23.md)
- RBAC 注册审批关联表 R2-2E4 交付收口验收（R2-2 完成；运行态、文档和质量门禁收口，2026-10-23）：[HTML](qa/RBAC注册审批关联表R2-2E4交付收口验收-2026-10-23.html) · [Markdown](qa/RBAC注册审批关联表R2-2E4交付收口验收-2026-10-23.md)

- RBAC 注册审批关联表 R2-2C 双存储实施验收（父子单事务、实时双写，2026-10-20）：[HTML](qa/RBAC注册审批关联表R2-2C双存储实施验收-2026-10-20.html) · [Markdown](qa/RBAC注册审批关联表R2-2C双存储实施验收-2026-10-20.md)

- RBAC 注册审批关联表 R2-2B 实施验收（15 条关联、0 孤儿，2026-10-20）：[HTML](qa/RBAC注册审批关联表R2-2B实施验收-2026-10-20.html) · [Markdown](qa/RBAC注册审批关联表R2-2B实施验收-2026-10-20.md)

- RBAC 注册审批关联表 R2-2A 数据审计（16 张申请全部可分类，零写入，2026-10-20）：[HTML](qa/RBAC注册审批关联表R2-2A数据审计-2026-10-20.html) · [Markdown](qa/RBAC注册审批关联表R2-2A数据审计-2026-10-20.md)

- RBAC 注册审批列表 R2-2 专业评估（A-，DEC 前置，2026-10-20）：[HTML](qa/RBAC注册审批列表R2-2专业评估-2026-10-20.html) · [Markdown](qa/RBAC注册审批列表R2-2专业评估-2026-10-20.md)

- RBAC 注册审批列表陈旧 Session 读取复盘（R2-1 已修复，2026-10-19）：[HTML](postmortem/2026-10-RBAC注册审批列表陈旧Session读取.html) · [Markdown](postmortem/2026-10-RBAC注册审批列表陈旧Session读取.md)

- RBAC 注册审批列表 R2-1 实施说明与专业评估（已实施并验收，2026-10-19）：[HTML](qa/RBAC注册审批列表R2-1实施说明与专业评估-2026-10-19.html) · [Markdown](qa/RBAC注册审批列表R2-1实施说明与专业评估-2026-10-19.md)

- RBAC 注册审批列表 Scope 精确化方案专业 Review（A-，修订后确认，2026-10-19）：[HTML](qa/RBAC注册审批列表Scope精确化方案专业Review-2026-10-19.html) · [Markdown](qa/RBAC注册审批列表Scope精确化方案专业Review-2026-10-19.md)

- 任务触发 URL 3xx 失败语义与 Pinning 修复设计（已实施，2026-10）：[HTML](design/任务触发URL-3xx失败语义与Pinning修复设计-2026-10.html) · [Markdown](design/任务触发URL-3xx失败语义与Pinning修复设计-2026-10.md)

- 任务触发 URL DNS 二次解析安全修复设计（已确认并实施，2026-10-12）：[HTML](design/任务触发URL-DNS二次解析安全修复设计-2026-10.html) · [Markdown](design/任务触发URL-DNS二次解析安全修复设计-2026-10.md)

- 代码全面 Review 与未提交变更评估（2026-10-12 v6：历史 P0/P2 已关闭；完整测试 839 项已运行，其中 838 通过、1 项风险演示跳过，11 项服务集成测试全部通过；发布仅待真实 MySQL 迁移演练）：[HTML](qa/2026-10-10-代码全面Review与未提交变更评估.html) · [Markdown](qa/2026-10-10-代码全面Review与未提交变更评估.md)

- 任务触发安全与测试契约漂移复盘（2026-10-10）：[HTML](postmortem/2026-10-10-任务触发安全与测试契约漂移复盘.html) · [Markdown](postmortem/2026-10-10-任务触发安全与测试契约漂移复盘.md)

- P0-D 数据库写入失败闭环设计（待确认）：[HTML](design/P0-D-数据库写入失败闭环设计-2026-10.html) · [MD](design/P0-D-数据库写入失败闭环设计-2026-10.md)

- RBAC 注册审批申请业务组关联表 R2-2 实施方案（R2-2 已完成；R2-3/R2-4 亦已验收，2026-10）：[HTML](design/RBAC注册审批申请业务组关联表R2-2实施方案-2026-10.html) · [MD](design/RBAC注册审批申请业务组关联表R2-2实施方案-2026-10.md)

- RBAC 注册审批列表 Scope 精确化优化方案（R2-0–R2-4 已完成；F-02 关闭，2026-10）：[HTML](design/RBAC注册审批列表Scope精确化优化方案-2026-10.html) · [MD](design/RBAC注册审批列表Scope精确化优化方案-2026-10.md)

- RBAC 注册审批 R2-3 集成与同类排查实施方案（已完成；无读取旁路，2026-10）：[HTML](design/RBAC注册审批R2-3集成同类排查实施方案-2026-10.html) · [MD](design/RBAC注册审批R2-3集成同类排查实施方案-2026-10.md)

- RBAC 注册审批 R2-4 浏览器最终验收与 F-02 关闭方案（已完成，2026-10）：[HTML](design/RBAC注册审批R2-4浏览器最终验收与F-02关闭方案-2026-10.html) · [MD](design/RBAC注册审批R2-4浏览器最终验收与F-02关闭方案-2026-10.md)

- RBAC 注册审批 R2-4 浏览器最终验收与 F-02 关闭（通过，2026-10-26）：[HTML](qa/RBAC注册审批R2-4浏览器最终验收与F-02关闭-2026-10-26.html) · [MD](qa/RBAC注册审批R2-4浏览器最终验收与F-02关闭-2026-10-26.md)

- RBAC 注册审批 R2-3 集成与同类排查验收（通过，2026-10-26）：[HTML](qa/RBAC注册审批R2-3集成同类排查验收-2026-10-26.html) · [MD](qa/RBAC注册审批R2-3集成同类排查验收-2026-10-26.md)

- RBAC 注册审批批量反馈真值闭环优化方案（B0–B3 已完成；F-01 已关闭，2026-10）：[HTML](design/RBAC注册审批批量反馈真值闭环优化方案-2026-10.html) · [MD](design/RBAC注册审批批量反馈真值闭环优化方案-2026-10.md)
- RBAC 批量审批请求 ID 规范化修复方案（已实施，2026-10）：重复或非法请求 ID 在写入前整体拒绝，专项测试与 86 条路由冒烟均通过。[HTML](design/RBAC批量审批请求ID规范化修复方案-2026-10.html) · [MD](design/RBAC批量审批请求ID规范化修复方案-2026-10.md)
- RBAC 批量审批请求 ID 规范化缺失复盘（2026-10）：输入集合缺少唯一性边界；共享解析器与三条 HTTP 红线测试防回归。[HTML](postmortem/2026-10-RBAC批量审批请求ID规范化缺失.html) · [MD](postmortem/2026-10-RBAC批量审批请求ID规范化缺失.md)

- RBAC 全局权限授予边界加固优化需求（S0–S5 与 F-01/F-02 均已关闭，2026-10）：[HTML](design/RBAC全局权限授予边界加固优化需求-2026-10.html) · [MD](design/RBAC全局权限授予边界加固优化需求-2026-10.md)

- RBAC 用户编辑差异写入与事务闭环优化方案（待确认，2026-10）：[HTML](design/RBAC用户编辑差异写入与事务闭环优化方案-2026-10.html) · [MD](design/RBAC用户编辑差异写入与事务闭环优化方案-2026-10.md)

- 统一错误处理拆分文档专业评审（2026-10-09）：[HTML](qa/error-handling-split-review-2026-10-09.html) · [Markdown](qa/error-handling-split-review-2026-10-09.md)

- 统一调度状态机制对现有实现的改动评估：[HTML](qa/统一调度状态机制对现有实现的改动评估-2026-11-03.html) · [Markdown](qa/统一调度状态机制对现有实现的改动评估-2026-11-03.md)
- 调度变更统一状态与恢复机制评估：[HTML](arch/调度变更统一状态与恢复机制评估-2026-11-02.html) · [Markdown](arch/调度变更统一状态与恢复机制评估-2026-11-02.md)
- D2 完成后下一步与 D3 下线风险评估：[HTML](qa/D2完成后下一步与D3下线风险评估-2026-11-02.html) · [Markdown](qa/D2完成后下一步与D3下线风险评估-2026-11-02.md)
- W1 预览 test1 未执行原因核查：[HTML](qa/W1-preview-test1未执行原因核查-2026-10-30.html) · [Markdown](qa/W1-preview-test1未执行原因核查-2026-10-30.md)
