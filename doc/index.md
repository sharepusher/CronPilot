# CronPilot · 技术文档索引

> HTTP 定时回调调度台 · 每份文档提供 **HTML**（浏览器）与 **Markdown**（GitHub / IDE）两种格式。  
> 本索引按 **项目管理 / 进度 / 架构 / 设计中 / 已交付 / 产品 / 依赖 / 运维 / 验收** 分维整理，避免扁平铺开。

**快捷入口：** [进度总览](交付状态与路线图.html) · [项目入门](arch/项目总览与技术文档.html) · [当前焦点 OPT-P2-13](design/规模化信息架构设计.html) · [Docker 部署](ops/Docker部署指南.html)

---

## ① 项目管理与进度

| 文档 | 说明 | HTML | Markdown |
|------|------|------|----------|
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
| **规模化信息架构 OPT-P2-13**（权威总稿） | L1/L2/L3 · job_health · 角色调制 · **当前焦点** | [HTML](design/规模化信息架构设计.html) | [MD](design/规模化信息架构设计.md) |
| **质量门禁与测试稳定性最小修复方案（2026-09）** | 4 项阻断修复：单测隔离、golden path、CSS reachability、postmortem completeness | [HTML](design/质量门禁与测试稳定性最小修复方案-2026-09.html) | [MD](design/质量门禁与测试稳定性最小修复方案-2026-09.md) |
| ↳ Scope 过滤（L2 专章） | admin / 1～2 Scope Demo | [HTML](design/规模化Scope过滤与角色差异化设计.html) | [MD](design/规模化Scope过滤与角色差异化设计.md) |
| ↳ L1/L2/L3 评审归档 | 讨论隐阱；结论已收束至总稿 | [HTML](design/规模化双层IA与任务健康模型评审.html) | [MD](design/规模化双层IA与任务健康模型评审.md) |
| P1 可观测小步 OPT-P1-01b/c | 失败筛选 · 展示统一 | [HTML](plan/P1可观测小步优化设计.html) | [MD](plan/P1可观测小步优化设计.md) |
| P1 执行详情与立即执行 OPT-P1-03/04 | 独立详情 URL · 立即执行 | [HTML](plan/P1执行详情与立即执行设计.html) | [MD](plan/P1执行详情与立即执行设计.md) |
| Tier 3 前置收束 | 去 `records` 裸 SQL | [HTML](deps/Tier3前置收束设计.html) | [MD](deps/Tier3前置收束设计.md) |

## ④ 已交付设计（归档）

| 文档 | 说明 | HTML | Markdown |
|------|------|------|----------|
| **管理员 admin Scope 差异化** OPT-P2-15 | 种子只读 · 管理员按组 · `__ALL__` · **v2.7.0** | [HTML](design/管理员admin-Scope差异化设计.html) | [MD](design/管理员admin-Scope差异化设计.md) |
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
| P0 测试与验收手册 | 用例 · 冒烟 · 签字 | [HTML](qa/P0测试用例与验收手册.html) | [MD](qa/P0测试用例与验收手册.md) |
| License Audit | Apache-2.0 合规 | [HTML](qa/LICENSE-AUDIT.html) | [MD](qa/LICENSE-AUDIT.md) |
| 文档同步说明 | HTML↔MD · CI | — | [MD](qa/文档同步说明.md) |

---

## 在线访问（服务启动后）

- HTML：`http://<主机>:5860/docs/` 或 `/docs/index.html`（本地默认亦可 `:5001`）
- Markdown：`/docs/index.md` 及各 `.md`

## 仓库根目录

- [README.md](../README.md) — 快速开始
- [INSTALL.md](../INSTALL.md) — 安装速查
- [RELEASE_NOTES.md](../RELEASE_NOTES.md) — 版本变更（与 HTML Release Notes 同步）

---

*CronPilot · 技术文档索引 · Release Notes（v1.2.0）*
