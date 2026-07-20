# CronPilot · 依赖升级 RFC

> HTML 版：[依赖升级RFC.html](依赖升级RFC.html) · [文档索引](index.html) · [索引 Markdown](index.md)

[← 文档索引](index.html)
RFC依赖运维P2

# 依赖升级 RFC

分层路线 · 风险分级 · 验收标准 · 与 RBAC / Phase B 的排期约束

状态：Draft v1.1 · 2026-06 · 按「耦合从弱到强」重排 Tier；SA 1.4 渐进策略

**定位：**本文是**决策与排期**文档，归属需求编号 **OPT-P2-11**（依赖升级）。不替代 [详细技术方案](详细技术方案.html) 的功能规格，也不在本 RFC 合并时自动修改 `requirements.txt`。实施每一 Tier / Phase 须单独确认设计、`RELEASE_NOTES` 与回归清单。编号读法见 [需求编号与缩写规范](需求编号与缩写规范.html)。  
**已交付版本：**Tier 0–2 见 **v0.2.0**；**Tier 3 前置**（去 `records`）及 Phase D0–D2 见 [交付状态与路线图](交付状态与路线图.html) / [RELEASE\_NOTES [Unreleased]](../RELEASE_NOTES.md)。

**2026-07-17 架构与版本复审：**当前 **v2.0.0** 架构（HTTP 回调调度台 · 双库 · 三角色 RBAC · gevent/gunicorn）与稳定栈
**Flask 1.1 + SA 1.4 + gevent 23 + Python 3.8–3.11** 仍成立，**无需紧急跳级**升级 Flask 2 / SA 2 / Python 3.12+。
下一依赖动作：**Tier 3b-A 已交付** → **Phase D3 compose（暂缓）** → **Tier 3c** 生产校验。

**交付纪律（每一 Tier / 优化项）：**

1. 实现改动（最小 diff）
2. 验收通过：`cronpilot.sh test` + `verify_golden_path.sh`；触及 Docker/生产时加 `verify_all.sh --docker-only`
3. **再**更新 `RELEASE_NOTES`、本 RFC 状态、相关 `doc/*.html`
4. `python scripts/html_docs_to_markdown.py --check`

大批量改写建议单模块验收后再更文档。详 [P0 验收手册](P0测试用例与验收手册.html) §优化交付验收。

## 一、摘要

CronPilot 当前锁定 **Flask 1.1 + SQLAlchemy 1.4 + gevent 23 + Python 3.8–3.11**，这是项目规则与 Docker/CI 共同维护的**稳定栈**，而非遗漏升级。

- **版本偏旧**主要体现在 Flask 1.x 停止演进；HTTP 客户端 CVE 与 gevent 20 编译问题已由**侧车 RFC-S.1**与**Tier 2 RFC-2.1**解决；迁移 CLI 已由 **Tier 0** 改为 `flask db`。
- **大规模升级**（Flask 2、SQLAlchemy 2、Python 3.12+）会牵动调度器、多 worker 锁、全站 `Model.query`，属**独立里程碑**，不应与 RBAC（OPT-P2-10）并行。
- **推荐路径**（依赖耦合从弱到强）：**Tier 0** Flask 原生 CLI → **Tier 1** SQLAlchemy 1.4 过渡（渐进改写）→ **Tier 2** gevent / Python → **Tier 3/4** SA 2.0 / Flask 2。
- RBAC 在 **Tier 0 后**即可启动，可与 Tier 1 并行；**不必**等待 gevent。

## 二、现状基线

### 2.1 锁定版本（`requirements.txt`）

| 层级 | 包 | 版本 | 备注 |
| --- | --- | --- | --- |
| Web | Flask / Werkzeug / Jinja2 | 1.1.2 / 1.0.1 / 2.11.2 | Flask 1.x 已停止演进 |
| ORM | SQLAlchemy / Flask-SQLAlchemy | 1.4.52 / 2.5.1 | **Tier 1 已交付**；全站 `Model.query` 已迁移；**Tier 3 前置已去 records** |
| 迁移 | Flask-Migrate / alembic | 4.0.7 / 1.14.1 | **Tier 0** 交付 `flask db` CLI；业务 schema **当前主路径**为 `ensure_business_tables`（见 Tier 3b）；仓库无强制 Alembic revision 树 |
| 调度 | APScheduler / Flask-APScheduler | **3.10.4** / 1.11.0 | `SQLAlchemyJobStore` + SA 1.4 |
| WSGI | gunicorn / gevent | **22.0.0** / **23.9.1** | `gun.py` 启动即 monkey patch |
| HTTP | requests / urllib3 | **2.31.0** / **1.26.19** | 侧车 RFC-S.1 已交付 |
| 辅助 | redis / PyMySQL | 3.5.3 / **1.1.2** | `records` 已移除（Tier 3 前置） |

### 2.2 开发与 CI 分工

| 场景 | 依赖文件 | Python | 说明 |
| --- | --- | --- | --- |
| 单元测试 | `requirements-core.txt` | 3.8–3.11（matrix） | 无 gevent；`conf.ci.ini` SQLite |
| 本地冒烟 | `requirements-core.txt` | 3.8–3.11 自动探测 | `scripts/start_local.sh`，Flask 内置 server |
| 完整生产依赖 | `requirements.txt` | **3.9 / 3.10 / 3.11**（matrix） | `install-full.yml` + `libev-dev` |
| Docker 镜像 | `requirements.txt` | **3.10** | `Dockerfile` + gunicorn gevent 健康检查 |

### 2.3 已验证问题（2026-06 本地）

| 现象 | 根因 | 影响面 |
| --- | --- | --- |
| `pip install -r requirements.txt` 失败（macOS 3.11） | 旧版 `gevent==20.9.0` Cython 编译失败 | **RFC-2.1 已缓解**（gevent 23.9.1 + greenlet 3.1.1 有 wheel） |
| `python manage.py db` 导入失败（3.11） | Flask-Script 使用已移除的 `inspect.getargspec` | **已解决**（Tier 0：`flask db`） |
| 仅装 Flask-Migrate 后 alembic 升到 1.18 | 未锁 `alembic==1.4.3`，拉取 SQLAlchemy 2.x | 与项目 SA 1.3 冲突 |
| `create_app()` + 本机 MySQL 未启动 | 调度器启动时连 `cron_db_url` | manage.py 需可用 DB 或 CI 配置 |

## 三、设计原则与约束

| 原则 | 说明 |
| --- | --- |
| 最小 diff | 依赖升级 PR 不得夹带 RBAC、operation\_log 等业务功能；反之亦然。 |
| 行为不变优先 | 调度触发、集群互斥（portalocker + Redis）、回调验签契约不得因升级而改变默认行为。 |
| Python 3.8–3.11 | 在 **Tier 2** 完成前，项目规则仍禁止默认 3.12+。 |
| 双格式文档 | 本 RFC 行为变更落地后同步 `RELEASE_NOTES`、`非Docker部署指南`、`INSTALL.md` 相关节。 |
| 可回滚 | 每一 Tier 须能在同一版本线回退 `requirements*.txt` 并恢复 Docker 构建。 |
| **耦合从弱到强** | 严格按 Tier 0→1→2→3→4 顺序推进；**禁止跳级**（如未修 CLI 就升 gevent）。每一级合并后须全量回归再进入下一级。 |
| **SA 1.4 渐进式** | 升到 SQLAlchemy 1.4 后**不强制**一次性改掉 `Model.query`；新代码优先 `text()` / 2.0 风格，旧写法在 1.4 兼容层下分批替换。 |

## 四、依赖耦合强度与升级顺序

下列顺序按**与业务代码/运行时的耦合度**从低到高排列，是 RFC 的**权威执行序**（与安全补丁、RBAC 的并行关系见 §七）。

| 顺序 | 层级 | 动作 | 耦合度 | 为何在此顺位 |
| --- | --- | --- | --- | --- |
| 1 | **Tier 0** ✓ | Flask-Script → Flask 原生 CLI | 最弱 | **v0.2.0 已交付** |
| 2 | **Tier 1** ✓ | SQLAlchemy 1.3 → **1.4**（过渡版） | 弱–中 | **v0.2.0 已交付** |
| ∥ | *侧车* ✓ | HTTP 安全补丁（requests / urllib3） | 最弱 | **v0.2.0 已交付**（RFC-S.1 + RFC-S.2） |
| ∥ | *功能* | RBAC（OPT-P2-10） | 弱 | **已交付**（见 [交付状态](交付状态与路线图.html)） |
| 3 | **Tier 2** ✓ | gevent / gunicorn / APScheduler + Python 上限 | 强 | **v0.2.0 已交付**（RFC-2.1～2.5） |
| 3.5 | **Tier 3 前置** ✓ | 去 `records` 裸 SQL（S1 ORM / S2 `text()`） | 中 | **已交付**（2026-07-17；见 [前置设计](Tier3前置收束设计.html)） |
| 4 | **Tier 3** | SA 1.4 → SA 2.0 + FSA 3.x | 高 | Phase A 硬门 ✓；下一子阶段 **3a**（pin bump，须 Flask 2 前提） |
| 5 | **Tier 4** | Flask 1.1 → 2.x | 高 | Werkzeug/Jinja/click 连锁；宜在 SA 2.0 稳定后 |

### 4.1 代码触点与耦合（盘点表）

| 模式 | 出处示例 | 耦合 | Tier 0 | Tier 1 (SA 1.4) | Tier 2 | Tier 3+ |
| --- | --- | --- | --- | --- | --- | --- |
| Flask-Script `Manager` | `manage.py` | 最弱 | 替换 | — | — | — |
| `db.session.execute("裸 SQL")` | `app/crons.py` | 中 | — | 改为 `text()`（小 PR） | — | 必须完成 |
| `Model.query.filter / paginate` | `main/views.py` 等 | 中 | — | ✅ 已改 | — | — |
| `SQLAlchemyJobStore` | `config.py` | 中 | — | 验证 1.4 | 随 APS 升级 | — |
| `records` 裸 SQL | `CuBackgroundScheduler` / `cron_check` | 已清 | — | — | — | Tier 3 前置 ✓ |
| `db.session.query(...).paginate()` | `main/views.py`、`rbac/views.py` | 中 | — | SA 1.4 可用 | — | Phase A ✓（`paginate_select`） |
| `gevent.monkey.patch_all()` | `gun.py` | 强 | — | — | 升级 | — |
| Flask / Jinja SSR | `decorated.py`、模板 | 强 | — | — | — | Flask 2 |

## 五、分层升级路线（耦合从弱到强）

### Tier 0 — Flask-Script → Flask 原生 CLI（1–2 天，耦合最弱）· 已交付（v0.2.0）

**目标：**只动 `manage.py` 与依赖声明，**不**升 Flask / SQLAlchemy / gevent 主版本。

| 项 | 动作 | 风险 |
| --- | --- | --- |
| RFC-0.1 | 移除 Flask-Script；`manage.py` 改用 Flask 应用工厂 + `flask db`（或 Click 注册 `MigrateCommand`） | 低 |
| RFC-0.2 | `requirements-core.txt` 锁定 `alembic==1.4.3`、`Flask-Migrate==2.5.3`；从 `requirements.txt` 移除 `Flask-Script` | 低 |
| RFC-0.3 | 文档：`flask --app manage:app db migrate` 用法；Docker `docker_start.sh` 若有 migrate 步骤则同步 | 低 |

#### 验收标准

- Python **3.11**：`flask db --help` 成功（无需 `inspect.getargspec` 补丁）。
- `bash scripts/cronpilot.sh test` 全 matrix 通过。
- RBAC / operation\_log 的 `db init | migrate | upgrade` 在 SQLite CI 配置下可跑通。

### Tier 1 — SQLAlchemy 1.4 过渡版（约 1 周，含渐进改写）· 已交付（v0.2.0）

**目标：**把 ORM 底座升到官方**过渡版本** 1.4.x，在 Flask 1.1 + Flask-SQLAlchemy 2.5 下运行；**全站 `Model.query` 已分批迁移**为 `session.get` / `scalars(select(...))` / `execute(delete(...))`。

| 项 | 动作 | 说明 |
| --- | --- | --- |
| RFC-1.1 | `SQLAlchemy==1.4.52` | `Flask-SQLAlchemy==2.5.1`（2.4.4 与 SA 1.4 不兼容，须 2.5+） |
| RFC-1.2 | 应用级 `SQLALCHEMY_ENGINE_OPTIONS` 或配置 `future=False`（1.4 默认） | 抑制 2.0 迁移警告至可控范围 |
| RFC-1.3 | **首批**必改：`app/crons.py` 中 `execute("SELECT 1")` → `execute(text("SELECT 1"))` | 改动面极小，验证 1.4 路径 |
| RFC-1.4 | 「查询改写 backlog」按模块完成（`job_log_service` → `main/views` → `cron_service` → `api/views` → `crons`） | RBAC 新代码继续用 `text()` / 推荐写法 |
| RFC-1.5 | alembic：评估 `1.4.3` 是否仍满足 1.4；若不足则升到 1.7.x（仍 < 2.0），**禁止**解析到 alembic 1.18+ 拉 SA 2 | 锁版本写入 requirements |

#### SA 1.4 渐进策略（核心）

- **已完成：**`Model.query` 全站迁移；管理端列表分页已迁 `select()` + `paginate_select`（Phase A / Query Contract）。
- **新代码要求：**RBAC 模型、operation\_log、任何新 PR 中避免新增裸字符串 `execute` 与 `Model.query`。
- **分批 PR：**已按模块（`crons` → `job_log_service` → `main/views` → `cron_service` → `api/views`）合并，每 PR 跑全量单测 + 冒烟。
- **不做什么：**本 Tier **不**升 SQLAlchemy 2.0、**不**升 Flask-SQLAlchemy 3.x。

#### 验收标准

- 单元测试 + 本地 `start_local.sh` 冒烟通过（SQLite / MySQL 各一轮）。
- APScheduler JobStore 正常：`apscheduler_jobs` 读写、任务触发无异常。
- 改写 backlog 已清零：`Model.query` 与裸 `execute` 字符串已改；`records` 裸 SQL 列入 Tier 3。

### 侧车 — HTTP 安全补丁（与 Tier 0/1 并行，2–3 天）· RFC-S.1 已交付（v0.2.0）

耦合最弱，**不改变 Tier 序号**；任意时刻可独立合并。

| 项 | 候选 | 注意 |
| --- | --- | --- |
| RFC-S.1 ✓ | `requests` **2.31.0**、`urllib3` **1.26.19**、`certifi` **2024.8.30** | 已回归 `cron_do`、SSRF 单测、黄金路径 |
| RFC-S.2 ✓ | `PyMySQL` **1.1.2** | 兼容 Py 3.8–3.11；MySQL 生产连接回归 |

### Tier 2 — gevent / gunicorn / APScheduler / Python 上限（1–2 周，耦合强）· 已全部交付（v0.2.0）

**前置条件：**Tier 0、Tier 1 已合并且回归通过。**本 Tier 在 SA 1.4 稳定之后、Flask 2 之前。**

| 项 | 动作 | 风险 |
| --- | --- | --- |
| RFC-2.1 ✓ | `gevent` **23.9.1** + `greenlet` **3.1.1** | Docker 构建 + gunicorn gevent worker 健康检查通过 |
| RFC-2.2 ✓ | `gunicorn` **22.0.0** | Docker 构建 + gevent worker + `SMOKE_LEVEL=full` 扩展冒烟 |
| RFC-2.3 ✓ | `APScheduler` **3.10.4** | `SQLAlchemyJobStore` + SA 1.4；Docker compose 冒烟通过 |
| RFC-2.4 ✓ | Python：Docker 金路径 **3.10**；`install-full.yml` matrix **3.9 / 3.10 / 3.11** | Docker 构建 + compose 冒烟通过 |
| RFC-2.5 ✓ | 项目规则「勿 3.12+」经 Tier 2 全量验收仍维持（3.8–3.11 稳定栈） | Tier 2 签收 |

#### 验收标准

- `pip install -r requirements.txt` 在目标 Python（3.10、3.11）成功。
- Docker 构建 + gunicorn 健康检查通过；多 worker 调度与 Redis 互斥正常。
- 不在此 Tier 改 Flask / SA 主版本（除 1.4 补丁）。

### Tier 3 前置 — 去 `records`（代码清债，不升主版本）· 已交付（2026-07-17）

设计确认：S1（`update_cron_info` → `app_context` + ORM）、S2（`cron_check` → 独立 engine + `text()`）；
`CuGeventScheduler` 同步改法；抽 `app/services/scheduler_db.py`。详 [Tier 3 前置收束设计](Tier3前置收束设计.html)。

### Tier 3 — SQLAlchemy 2.0 + 查询写法收束（数周，耦合高）

**前置条件：**Tier 1 的 `Model.query` 已清零；**Tier 3 前置已去 `records`**。本阶段才允许 bump SA / FSA / Alembic。

| 子阶段 | 内容 | 状态 |
| --- | --- | --- |
| 前置 | `records` → ORM / `text()`（调度热路径） | ✓ 已交付 |
| **3a 前置 · Phase A** | **Query Contract**（`app/services/pagination.py`）：`PageQuery` / `PaginationResult` / `paginate_select`。 改写全部管理端列表 `db.session.query(...).paginate()` 与列表路径 `session.query`：  - `app/main/views.py`：任务中心、job\_log、operation\_log（7 处） - `app/rbac/views.py`：用户列表、审计日志（2 处）  模板 `admin_page.html` 零改动；**不 bump pin**。 | ✓ 已交付（2026-07-20） |
| **3a · pin bump** | 已落地（2026-07-20 / Phase D1）：`SQLAlchemy==2.0.36` + `Flask-SQLAlchemy==3.1.1` + `alembic==1.14.1` + `Flask-Migrate==4.0.7`， 与 **Flask 2.3.3** 链同窗（DEC-008 B1）。 | ✓ 已交付 |
| **D2 · Mapped[]** | 已落地（2026-07-20）：`datas/model` 九表 `Mapped`/`mapped_column`； `test_mapped_model_guard`。见 [D2](PhaseD2-Mapped模型迁移.html)。 | ✓ 已交付 |
| **3b · ensure 重放 + 残余收束（3b-A）** | 业务 schema 主路径正式定为 `ensure_business_tables`；空库重放验收； 残余 SA 1.4 写法以 Phase A/B/C AST 门禁为准盘点。见 [Tier 3b 设计](Tier3b-迁移重放与残余收束设计.html)。 | ✓ 已交付（2026-07-20） |
| 3c | 生产库备份 → upgrade/ensure → JobStore / `job_log` 只读校验 | 未开始 |

#### 验收标准

- Phase A 单测 + P0 手册 + Docker 全绿；分页列表与 RBAC 列表回归。
- `THIRD_PARTY_NOTICES.md` 与 pin 同步。

### Tier 4 — Flask 2.x（独立里程碑，与 Tier 3 同窗或紧随）

**目标：**Werkzeug 2 + Jinja2 3 + click 升级。可与 Tier 3 末尾合并为「框架代际」大版本，但**仍晚于** Tier 0/1/2。

- Flask 2.3 LTS 线；全站 session、错误处理、`jsonify` 行为回归。
- 评估 Python 3.12+ 是否纳入支持范围（依赖 gevent 与本 Tier 结果）。

## 六、组件风险矩阵（对齐新 Tier 序）

| 组件 | 维持现状风险 | 建议 Tier | 说明 |
| --- | --- | --- | --- |
| Flask-Script | Py3.11 阻断 migrate | **Tier 0** 已移除 | 耦合最弱，**已完成** |
| SQLAlchemy 1.3 | 维护结束 | **Tier 1** 已升 1.4 | 过渡版；`Model.query` 已迁移 |
| requests/urllib3 | CVE | **侧车 RFC-S.1** | **已升** 2.31.0 / 1.26.19 |
| PyMySQL 0.10 | 旧驱动 | **侧车 RFC-S.2** | **已升** 1.1.2（Py 3.8+） |
| gevent 20 | Py3.11 编译失败 | **Tier 2 RFC-2.1** | **已升** gevent 23.9.1 + greenlet 3.1.1 |
| gunicorn 20 | 旧版维护线 | **Tier 2 RFC-2.2** | **已升** gunicorn 22.0.0 |
| APScheduler 3.6 | 旧 bug | **Tier 2 RFC-2.3** | **已升** APScheduler 3.10.4 |
| SQLAlchemy 2.0 | — | **Tier 3** | Phase A 分页硬门 ✓；下一动作为 Phase B/C 后 3a pin（须 Flask 2） |
| Flask 1.1 | 无新补丁 | **Tier 4** | 晚于 Tier 3 |
| records 0.5.3 | 裸 SQL | **Tier 3 前置** | 已移除 |

## 七、与 RBAC（OPT-P2-10）的关系

RBAC v2 详设见 [RBAC 架构设计方案](RBAC架构设计方案.html)。本节专门回答：**做 RBAC 前必须升哪些依赖？升级与 RBAC 如何排期？**

### 7.1 结论（审阅要点）

| 问题 | 答案 |
| --- | --- |
| RBAC 是否依赖 Flask 2 / SQLAlchemy 2？ | **否。**RBAC 在 Flask 1.1 + SA 1.3/1.4 + 装饰器下可交付；Tier 1 升 1.4 后新表宜用 `text()` 写法。 |
| RBAC 是否依赖 gevent 升级？ | **否。**RBAC 与 gunicorn worker 无关；gevent 属 **Tier 2**。 |
| RBAC 前是否必须完成 Tier 0？ | **强烈建议。**否则 Py3.11 无标准 `db migrate`；可退化 `ensure_rbac_tables`。 |
| RBAC 与 Tier 1（SA 1.4）关系？ | **可并行。**RBAC 合入前完成 Tier 0 即可；若 Tier 1 已合，RBAC 模型避免新增 `Model.query` 债。 |
| RBAC 与 Tier 2/3/4 能否并行？ | Tier 2 **谨慎**；Tier 3/4 **禁止**与 RBAC 首期并行。 |

### 7.2 RBAC 对当前栈的实际依赖

| RBAC 能力 | 依赖组件 | 当前栈是否满足 |
| --- | --- | --- |
| 装饰器 + Session | Flask 1.1、`session` | 是 |
| 密码哈希 | `app/auth/password.py`（现有） | 是 |
| JSON 契约 | `json_response` / `web_api_return` | 是 |
| 新表 `rbac_users`、`rbac_audit_logs` | Flask-SQLAlchemy 2.4 + SA 1.3/1.4 | 是（Tier 1 后更佳） |
| 库表迁移 | Flask-Migrate + alembic（锁版本） | 是（**Tier 0** 后） |
| 三角色分权（始终启用） | 无新依赖 | 是 |
| API `access_token` 不变 | 不升级 `app/api/views.py` | 是（设计约束） |

### 7.3 推荐排期（耦合从弱到强 × RBAC）

```
权威顺序（升级线）:
  Tier 0  Flask CLI
    → Tier 1  SQLAlchemy 1.4（Model.query 已迁移）
    → Tier 2  gevent + Python 上限
    → Tier 3  SQLAlchemy 2.0
    → Tier 4  Flask 2.x

RBAC 插入点（推荐）:
  Tier 0 完成
    → RBAC 实现 + db migrate（可与 Tier 1 并行）
    → RBAC 验收（三角色矩阵始终启用）
    → Tier 2（gevent）/ 侧车安全补丁

侧车（任意时刻）:
  HTTP 安全补丁（requests 等）

禁止:
  RBAC 首期与 Tier 3/4 同迭代
  未做 Tier 0 即在 Py3.11 强依赖 Flask-Script migrate
```

### 7.4 RBAC 实施时各 Tier 的影响

| Tier | 对 RBAC 开发 | 对 RBAC 发布 | 建议 |
| --- | --- | --- | --- |
| Tier 0 | 解锁 `flask db migrate` | 标准 Alembic 建表 | RBAC 前置（强烈建议） |
| Tier 1 (SA 1.4) | 无冲突；新代码避免旧查询债 | 与 1.3 行为一致即可发布 | 可与 RBAC 并行 |
| 侧车 安全补丁 | 无 | 回调冒烟 | 任意时刻 |
| Tier 2 gevent | 无直接冲突 | 调度回归 | RBAC 稳定后 |
| Tier 3/4 | 可能改 RBAC 查询 | 全站迁移 | RBAC 发布后 |

### 7.5 RBAC 迁移验收（与 RFC 验收对齐）

在**不升级 Flask 主版本**前提下，RBAC 发布除 [RBAC 详设 §验收](RBAC架构设计方案.html) 外，还须满足：

- 三角色矩阵单测（`tests/test_rbac_phase.py`）通过；分权**始终启用**（无旁路）。
- 建表：目标环境执行 `db upgrade` 成功，或文档记录 `ensure_rbac_tables` 使用条件与限制（不替代 Alembic 历史时的局限须写清）。
- 无 `rbac_enable` 配置项。

### 7.6 不必因 RBAC 而升级的内容

- Flask 2.x / 3.x、Werkzeug 2+
- SQLAlchemy 2.0、Flask-SQLAlchemy 3.x
- gevent 22+、Python 3.12+
- JWT、OAuth、新 API 鉴权协议（RBAC v2 明确不做）

## 八、排期与功能交叉（总表）

| 工作项 | Tier / 位置 | 与 RBAC | 说明 |
| --- | --- | --- | --- |
| Flask CLI | Tier 0 | RBAC 前置 | 耦合最弱，最先做 |
| SQLAlchemy 1.4 | Tier 1 | 可并行 | 渐进改写，不挡 RBAC |
| RBAC | 功能线 | — | Tier 0 后启动；不等 gevent |
| HTTP 安全补丁 | 侧车 | 可并行 | 独立 PR |
| gevent / Python | Tier 2 | RBAC 稳定后 | 耦合强，靠后 |
| SA 2.0 / Flask 2 | Tier 3/4 | 禁止与 RBAC 首期并行 | 单独立项 |

## 九、推荐执行顺序（甘特）

```
时间 ─────────────────────────────────────────────────────────────►

[Tier 0 Flask CLI]────┐
                      ├──► [RBAC + db migrate] ──► [RBAC 发布]
[Tier 1 SA 1.4 起步]──┘         │                      │
  （渐进 PR：crons→views…）      │                      ▼
                                │              [Tier 2 gevent]
[侧车 requests 补丁]（任意）     │
                                ▼
                      [Tier 2 gevent + Py 上限]
                                │
                                ▼
                      [Phase A/B/C ✓] → [Phase D0 DEC-008 ✓] → [D1 Flask2.3+SA2+FSA3 同窗 ✓] → [D2 Mapped ✓] → [D3 矩阵]
```

## 十、决策记录

| ID | 决策 | 理由 | 日期 |
| --- | --- | --- | --- |
| DEC-001 | 升级顺序按**依赖耦合从弱到强**：Tier 0 CLI → Tier 1 SA 1.4 → Tier 2 gevent → Tier 3/4 代际 | 避免 gevent 与 ORM 大爆炸同窗；SA 1.4 作过渡 | 2026-06 |
| DEC-002 | SA 1.4 阶段**不强制**一次性移除 `Model.query` | 分批 PR；新功能（RBAC）不新增旧债 | 2026-06 |
| DEC-003 | RBAC 不依赖 Tier 2+；仅需 Tier 0（推荐）或与 Tier 1 并行 | 功能交付不等待 gevent | 2026-06 |
| DEC-004 | 迁移依赖须锁 alembic，禁止解析到 SA 2.x | 本地 venv 实测 | 2026-06 |
| DEC-005 | RBAC 允许 `ensure_rbac_tables` 作 Tier 0 未完成时的退化 | 与 RBAC v2 详设一致 | 2026-06 |
| DEC-006 | 2026-07-17 复审：维持 Flask 1.1 + SA 1.4 稳定栈；先落地 Tier 3 前置再开 3a；禁止跳级 Flask 2 / Python 3.12+ | 架构健康；Flask 1 无补丁属已知中风险，由侧车与 P0 契约缓解 | 2026-07-17 |
| DEC-007 | Phase A 与 Tier 3a **pin bump 解耦**：Query Contract + 分页硬门可在 SA 1.4 下交付；SA 2 / FSA 3 pin 须等 Flask 2 前提，并入 Framework Generation | FSA 3.x 硬依赖 Flask ≥ 2.2.5；避免无 Flask 2 的半升状态 | 2026-07-20 |
| DEC-008 | Phase D0 确认：Python **3.8–3.11**（A1；与安装脚本一致）；目标线 **Flask 2.3.x + SA 2.0.x + FSA 3.1.x + Alembic** **同窗 bump**（B1）。选 B1 因回归面可控且已满足 FSA3；**非**因「Flask 3 不支持 3.8」（Flask 3.0 仍支持 3.8；仅 3.1+ 丢 3.8）。不做 Flask 3 首跳、Login/WTF、默认 3.12+。修订：撤回曾记的「弃 3.8」。详见 [D0 决策](PhaseD0-Framework-Generation决策.html) | FSA3 须 Flask≥2.2.5；Flask 3 首跳叠加 Werkzeug 3 成本高；D1 pin 均 ≥3.8 | 2026-07-20 |

## 十一、参考

- [Tier 3 前置收束设计](Tier3前置收束设计.html) — 去 records（已交付）
- [RBAC 架构设计方案 v2](RBAC架构设计方案.html) — OPT-P2-10 权威详设
- [详细技术方案 §15 风险与演进路线](详细技术方案.html#t15)
- [技术方案与前端设计](技术方案与前端设计.html) — P0 依赖升级意向
- [非 Docker 部署指南](非Docker部署指南.html) — Python 3.8–3.11 与 gevent 故障
- [P0 测试用例与验收手册](P0测试用例与验收手册.html)
- [License Audit](LICENSE-AUDIT.html)
- 仓库：`requirements.txt`、`requirements-core.txt`、`.github/workflows/unit-tests.yml`、`install-full.yml`

[Markdown 版](依赖升级RFC.md) · [文档索引](index.html) · CronPilot RFC v1.1 Draft

---

[← 文档索引（HTML）](index.html) · [← 文档索引（Markdown）](index.md)
