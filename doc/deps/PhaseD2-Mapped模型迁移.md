# CronPilot · Phase D2 · Mapped 模型迁移

> HTML 版：[PhaseD2-Mapped模型迁移.html](PhaseD2-Mapped模型迁移.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

[← 文档索引](../index.html)
依赖演进Phase D2已交付

# Phase D2 · Mapped[] 模型迁移

datas/model 经典 Column → Mapped / mapped\_column（SA 2.0 声明式）

状态：已交付 · v2.1.0 · 2026-07-20 · 前置 D1 pin ✓

**已交付（2026-07-20）：**
`datas/model/` 九表全部改为 `Mapped[...]` + `mapped_column`；
门禁 `tests/test_mapped_model_guard.py`；挂 `cronpilot.sh test` 与 CI `unit-tests.yml`。
验收：199 unittest + `verify_all.sh --local-only` 4/4。

**定位：**Framework Generation 子阶段 D2（见 [D0](PhaseD0-Framework-Generation决策.html)）。
**不改**表结构 / 业务 API / UI；仍继承 `db.Model`（Flask-SQLAlchemy 3.1）。

## 一、问题 / 根因 / 方案

| 项 | 内容 |
| --- | --- |
| 问题 | D1 已 pin SA 2.0，模型仍为 1.x 风格 `db.Column`，与官方 Declarative 2.0 不一致。 |
| 根因 | D1 同窗刻意排除大批量 Mapped，避免与 pin 回归面叠加。 |
| 方案 | 九表机械改写为 `Mapped` / `mapped_column`；保留 `default`/`server_default`/`doc` 语义；AST 门禁防回潮。 |

## 二、范围

| 文件 | 说明 |
| --- | --- |
| `cron_infos.py` | 任务主表 |
| `job_log.py` / `job_log_items.py` | 执行日志 |
| `job_health.py` | 健康快照 |
| `operation_log.py` | 操作审计 |
| `rbac_user.py` / `rbac_audit_log.py` | RBAC |
| `resource_group.py` / `user_group.py` | Scope |

**不做：**Flask 3、schema 迁移、views/Repo 重写、自建 DeclarativeBase。

## 三、验收

| # | 门禁 |
| --- | --- |
| 1 | `cronpilot.sh test`（含 `test_mapped_model_guard`） |
| 2 | `verify_all.sh --local-only` |
| 3 | 登录 / 任务中心 / 执行记录冒烟（本地 `:5001`） |

[依赖升级 RFC](依赖升级RFC.html) ·
[交付状态](../交付状态与路线图.html) ·
[D0](PhaseD0-Framework-Generation决策.html)

CronPilot · Phase D2 Mapped 模型迁移 · 已交付 v2.1.0 · [索引](../index.html) · [Markdown](PhaseD2-Mapped模型迁移.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
