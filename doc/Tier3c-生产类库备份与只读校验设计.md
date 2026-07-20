# CronPilot · Tier 3c · 生产类库备份与只读校验设计

> HTML 版：[Tier3c-生产类库备份与只读校验设计.html](Tier3c-生产类库备份与只读校验设计.html) · [文档索引](index.html) · [索引 Markdown](index.md)

[← 文档索引](index.html)
OPT-P2-11Tier 3c设计待确认

# Tier 3c · 生产类库备份与只读校验

双库（JobStore + 业务）在 SA 2.0 栈上经 ensure 后的可运维证明

状态：设计待确认 · 2026-07-20 · 前置 Tier 3b-A ✓ · 不依赖 Phase D3 compose

**请确认后再实现。**本页为架构轨 **OPT-P2-11 · Tier 3c**。
编号见 [需求编号与缩写规范](需求编号与缩写规范.html)。
确认前**不**写校验脚本、不改生产入口、不宣称 Tier 3c 已交付。

**定位：**RFC 原文「生产库备份 → upgrade/ensure → JobStore / job\_log 只读校验」。
结合 Tier 3b-A 契约：业务 schema 主路径是 `ensure_business_tables`，
**不是** `flask db upgrade`（仓库无强制 Alembic 树）。
**不做功能 OPT**；可与 Phase D3（Docker pin）并行排期。

## 一、问题 / 根因 / 方案

| 项 | 内容 |
| --- | --- |
| 问题 | Tier 3b 已证明**空库** ensure 可重放；尚未证明：带历史数据的**双库** （`cron_db_url` JobStore + `cron_job_log_db_url` 业务）在 SA 2.0 / Flask 2.3 栈上 跑 ensure 后，调度元数据与执行日志仍可读、schema 关键。 |
| 根因 | 空库测试不覆盖旧列/旧行；直连生产 DDL 风险高；双库边界易在「升级脚本」里被混为一谈； RFC 写的「upgrade」易被误读成 Alembic。 |
| 方案（推荐） | **3c-A · 夹具/类生产副本路径**：先备份 → 在**副本**上跑 ensure → JobStore / 业务表**只读断言** →（可选）短时进程冒烟。真实生产仅提供运维清单，默认不自动触达。 |

**双库事实：**
JobStore = `cron_db_url` → `apscheduler_jobs`（`scheduler_db.fetch_apscheduler_job_ids`）；
业务 = `cron_job_log_db_url` → `cron_infos` / `job_log` / RBAC 等（ensure 只动业务库）。
ensure **不**改 JobStore 表结构；3c 对 JobStore 仅做连通与只读 SELECT。

## 二、范围

| 做 | 不做 |
| --- | --- |
| - 备份清单（SQLite 文件拷贝 / MySQL `mysqldump` 要点） - 夹具目录约定（如 `datas/_tier3c_fixture/`，gitignore） - 脚本：指向副本 conf → `ensure_business_tables` → 只读校验 - 断言：业务关键表/列存在；`job_log` COUNT 可执行；JobStore `SELECT id` 可执行 - RELEASE / 路线图 / RFC 在**实现通过后**标 Tier 3c | - 默认对**线上生产**自动 DDL / 自动备份上传 - 引入 Alembic revision 树（属 3b-B） - Phase D3 compose / Flask 3 / 默认 Py 3.12+ - OPT-P1-\* 功能；改双库边界或合并库 - 破坏性写校验（删任务、改 job\_state） |

## 三、推荐方案 vs 备选

|  | 推荐 · 3c-A（夹具/副本） | 备选 · 3c-B（真实生产窗口） |
| --- | --- | --- |
| 做法 | 从本地/试用/脱敏 dump 复制双库 → 临时 conf → ensure → 只读脚本 | 运维窗口：备份 → 停服 → ensure → 只读核对 → 启服；脚本仅 checklist |
| 风险 | 低；可进 CI/本地重复跑 | 高；须人工确认目标 URI，禁止默认 conf 指向生产 |
| 与 3b 关系 | 3b=空库；3c=有数据副本 | 同左，但目标库是真生产 |
| 本窗建议 | **采用** | 文档附录即可；实现须另确认 |

## 四、分批与验收（确认后按批落地）

| 批 | 内容 | 验收 |
| --- | --- | --- |
| **3c-1** | 运维清单写入本设计附录 + 非 Docker 部署指南短节（备份命令、禁止事项）。 | 文档可读；无代码。 |
| **3c-2** | `scripts/verify_tier3c_fixture.sh`（或 py）：复制/挂载夹具双库、写临时 conf、跑 ensure。 | 对仓库内样例或 CI 生成夹具 exit 0；不碰用户真实 `datas/*.sqlite`（除非显式参数）。 |
| **3c-3** | 只读校验：inspect 业务列；`fetch_apscheduler_job_ids`；业务 `SELECT COUNT(*)` on `job_log`/`cron_infos`。 | 单测或脚本断言；故意缺列夹具应失败。 |
| **3c-4** | RELEASE / 交付状态 / RFC 标 Tier 3c（3c-A）已交付；`html_docs_to_markdown.py --check`。 | 与脚本同一轮；不把 D3/3b-B 偷标完成。 |

### 建议夹具最小内容

- 业务库：至少 1 行 `cron_infos`、若干 `job_log`（可从 golden path 或本地脱敏拷贝生成）。
- JobStore：允许空表；若有行则 id 集合可读即可。
- 故意缺列夹具（负例）：去掉 `req_method` 等，ensure 后应变齐。

## 五、验收标准（整窗）

| # | 标准 |
| --- | --- |
| 1 | 文档明确：3c 默认跑**副本**；生产须显式确认 + 备份 |
| 2 | ensure 只针对业务 URI；JobStore 只读 |
| 3 | 夹具路径可重复：ensure 幂等 + 只读断言绿 |
| 4 | `cronpilot.sh test` 仍绿；不引入对生产 URI 的硬编码 |

## 六、与 Tier 3b / Phase D3 的关系

```
Tier 3b-A ✓  空库 ensure 重放
Tier 3c（本页）有数据副本 + 双库只读
Phase D3      Docker pin（compose 暂缓，另轨）
```

## 七、附录 · 备份要点（实现时可落部署指南）

| 方言 | 建议 |
| --- | --- |
| SQLite | 停写或短停服后拷贝 `*.sqlite`；或 `sqlite3 file ".backup 'copy.sqlite'"`。 业务与 JobStore **两个文件分别**备份。 |
| MySQL | `mysqldump` 分库（scheduler / job\_log）；保留例程/触发器按需。 恢复到**非生产**实例再跑 ensure 验收。 |

**确认方式：**请回复「按 Tier 3c 设计（3c-A）执行」或「改用 3c-B 生产窗口」或列出修改点。
未确认前不实现脚本。

[Tier 3b](Tier3b-迁移重放与残余收束设计.html) ·
[依赖升级 RFC](依赖升级RFC.html) ·
[Phase D3](PhaseD3-Docker-pin矩阵设计.html) ·
[交付状态](交付状态与路线图.html) ·
[编号规范](需求编号与缩写规范.html)

CronPilot · Tier 3c 设计 · 待确认 2026-07-20 · [索引](index.html) · [Markdown](Tier3c-生产类库备份与只读校验设计.md)

---

[← 文档索引（HTML）](index.html) · [← 文档索引（Markdown）](index.md)
