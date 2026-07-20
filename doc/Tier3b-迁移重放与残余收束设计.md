# CronPilot · Tier 3b · 迁移重放与残余收束设计

> HTML 版：[Tier3b-迁移重放与残余收束设计.html](Tier3b-迁移重放与残余收束设计.html) · [文档索引](index.html) · [索引 Markdown](index.md)

[← 文档索引](index.html)
OPT-P2-11Tier 3b设计待确认

# Tier 3b · 迁移重放与残余收束

SA 2.0 栈上的 schema 演进可复现性 + 残余 1.4 兼容写法清理

状态：设计待确认 · 2026-07-20 · 不依赖 Docker · 前置 Phase D1/D2 ✓ · Phase D3 部分

**请确认后再实现。**本页为架构轨选项 B。编号见
[需求编号与缩写规范](需求编号与缩写规范.html)。
确认前**不**改 migrations / ensure 脚本行为 / 宣称 Tier 3b 已交付。

**定位：**属 **OPT-P2-11** · **Tier 3b**
（见 [依赖升级 RFC](依赖升级RFC.html)：迁移脚本重放；残余 SA 1.4 兼容写法收束）。
**不做功能 OPT**；**不做** Tier 3c 生产库操作；**不依赖** Phase D3 compose（可与 D3 并行排期）。

## 一、问题 / 根因 / 方案

| 项 | 内容 |
| --- | --- |
| 问题 | 已 pin SA 2.0 + Alembic 1.14 + Flask-Migrate 4，但仓库**无** `migrations/` 目录； 生产/试用 schema 实际靠 `ensure_business_tables`（create\_all + 条件 ALTER）。 「迁移重放」若按经典 Alembic 理解会对空；若只靠 ensure，又缺少**可重复的空库→当前态**自动化证明与文档契约。 |
| 根因 | 历史选择「轻量补列脚本」而非 Alembic 基线；Tier 0 只交付了 `flask db` CLI，未强制落地 revision 树。 RFC 3b 原文写于 Alembic 路径假设之上，需按现状改写为可执行方案。 |
| 方案（推荐） | **双轨诚实建模**：① 将 `ensure_business_tables` 正式定为「当前业务 schema 演进主路径」，补**空库重放验收**； ② 可选后续再立 Alembic 基线（3b-opt，本窗可不做）。 同时扫并收束残余 SA 1.4 兼容写法（在现有 AST 门禁之外的语义层）。 |

**事实核对（2026-07-20）：**工作区无 `migrations/`；
`manage.py` 注册 Flask-Migrate；部署入口调用 `ensure_business_tables.sh`。
Tier 3b 不得假装「已有 Alembic 历史可 upgrade」。

## 二、范围

| 做 | 不做 |
| --- | --- |
| - 文档契约：schema 演进主路径 = ensure（直至另立项 Alembic） - 空库 / 临时 SQLite：跑 ensure → 断言关键表与关键列存在（可脚本化） - 幂等：ensure 连跑两次无报错、列不重复破坏 - 残余写法盘点：`session.execute` 字符串、`Query` 旧 API、已弃用引擎选项等（对照 AST 门禁缺口） - 必要的最小代码清理（仅盘点中确认的、有测试的项） - RELEASE / 路线图 / RFC 3b 状态 | - Tier 3c 碰真实生产库 - Phase D3 compose（另轨） - 强制本窗引入完整 Alembic revision 树（可作为 3b-opt 备选，须另确认） - OPT-P1-\* 功能、Flask 3、默认 Python 3.12+ - 改双库边界（cron DB / job\_log DB） |

## 三、推荐方案 vs 备选

|  | 推荐 · 3b-A（ensure 重放硬化） | 备选 · 3b-B（Alembic 基线） |
| --- | --- | --- |
| 做法 | 验收脚本 + 文档契约 + 残余收束 | `flask db init` + 初始 revision 对齐当前模型；upgrade 空库 |
| 工期 / 风险 | 低～中；贴合现状 | 高：与 ensure 双源、历史库 stamp、双库 URL |
| 与生产 | 继续 ensure；3c 再验 | 须定义 stamp / 废弃 ensure 的迁移策略 |

**本设计默认确认 3b-A。**若你要 3b-B，请在确认时明示；不可 silent 开干 Alembic 基线。

## 四、分批（3b-A）

| 批 | 内容 | 可独立验收 |
| --- | --- | --- |
| **3b-1** | 契约文档：RFC / 部署指南写清「schema 主路径 = ensure\_business\_tables」； 与 `flask db` 的关系（CLI 可用，非当前强制演进路径）。 | 文档表述一致；无「已有 migrations 树」假话 |
| **3b-2** | 新增重放验收：临时 SQLite（或测试夹具）执行 ensure → 断言 `cron_infos` / `job_log` / `rbac_users` / `job_health` 等表及关键列 （复用/扩展 `tests.test_ensure_business_tables`）。 | `cronpilot.sh test` 含新用例绿；幂等第二次调用 OK |
| **3b-3** | 残余 SA 写法盘点清单（文件+行类）→ 仅清理有把握且有测的项； 无法本窗清理的记入 backlog（不扩 scope）。 | 盘点表入库文档；清理项单测仍绿 |
| **3b-4** | RELEASE + 交付状态 + RFC 标 Tier 3b（3b-A）已交付； `html_docs_to_markdown.py --check`。 | 与代码同一轮；不把 3c/D3 偷标完成 |

## 五、验收门禁

| # | 门禁 |
| --- | --- |
| 1 | `bash scripts/cronpilot.sh test`（含 ensure 重放相关用例） |
| 2 | 文档明确 schema 主路径；无虚假 Alembic 历史表述 |
| 3 | 残余盘点表完整；已清理项有对应测试或 AST 覆盖说明 |
| 4 | `html_docs_to_markdown.py --check` |

## 六、与 Phase D3 / Tier 3c 的关系

```
Tier 3b（本页，可不依赖 Docker）
    ├─ 证明：空库→当前 schema 可复现（ensure）
    └─ 收束：残余 ORM 写法
Phase D3（Docker pin）——环境就绪后另做
Tier 3c —— 备份真实/类生产库 → upgrade/ensure → JobStore 只读校验（另设计）
```

**确认方式：**请回复「按 Tier 3b 设计（3b-A）执行」或「改用 3b-B Alembic 基线」或列出修改点。

[依赖升级 RFC](依赖升级RFC.html) ·
[Phase D3](PhaseD3-Docker-pin矩阵设计.html) ·
[交付状态](交付状态与路线图.html) ·
[编号规范](需求编号与缩写规范.html)

CronPilot · Tier 3b 设计 · 待确认 2026-07-20 · [索引](index.html)

---

[← 文档索引（HTML）](index.html) · [← 文档索引（Markdown）](index.md)
