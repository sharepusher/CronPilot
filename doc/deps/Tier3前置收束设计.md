# CronPilot · Tier 3 前置收束设计（去 records 裸 SQL）

> HTML 版：[Tier3前置收束设计.html](Tier3前置收束设计.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

[← 文档索引](../index.html)
依赖升级Tier 3 前置已交付

# Tier 3 前置收束设计

移除 `records` 裸 SQL · 为 SQLAlchemy 2.0 铺路

状态：Confirmed · 已交付 · 2026-07-17（设计稿 2026-06-24）

**定位：**[依赖升级 RFC](依赖升级RFC.html) Tier 2 已签收；本设计是 **Tier 3（SA 2.0）** 的**前置清债**，**不升级** SQLAlchemy / Flask 主版本。完成后再开 Tier 3a（`SQLAlchemy==2.0.x` + FSA 3.x）。

## 一、背景与目标

| Tier 1 已完成 | 仍阻塞 Tier 3 |
| --- | --- |
| 全站 `Model.query` 已迁移；`execute(text(...))` 用于健康检查 | `records==0.5.3` + 字符串拼接 SQL（调度器热路径） |

**目标：**零行为变更地去掉 `records` 依赖；所有 SQL 走 SQLAlchemy `text()` + 绑定参数，或 Flask-SQLAlchemy `db.session`（带 `app.app_context()`）。

## 二、现状清单（须改文件）

| 文件 | 函数 | 现逻辑 | 库 URL |
| --- | --- | --- | --- |
| `app/CuBackgroundScheduler.py` | `update_cron_info` | `update cron_infos set status=-1 where id='%s'` | `cron_job_log_db_url` |
| `app/CuGeventScheduler.py` | `update_cron_info` | 同上（重复实现） | 同上 |
| `app/crons.py` | `cron_check` | `select id from apscheduler_jobs` 对账 | `CRON_DB_URL`（JobStore） |

生产使用：`app/__init__.py` 仅挂载 `CuBackgroundScheduler`；`CuGeventScheduler` 建议**同步改法**或标注废弃，避免双份漂移。

## 三、双库说明（改代码时必须尊重）

| 配置键 | 典型表 | 访问方 |
| --- | --- | --- |
| `cron_db_url` | `apscheduler_jobs` | APScheduler `SQLAlchemyJobStore`、`cron_check` |
| `cron_job_log_db_url` | `cron_infos`、`job_log` … | Flask-SQLAlchemy、`update_cron_info` |

试用 SQLite 常拆两个文件；MySQL 生产可能同实例不同 schema。**禁止**在 PR 中假设两库合并。

## 四、推荐方案（拆 3 个 PR）

### PR-T1 · `update_cron_info`（调度器线程写业务库）

**推荐方案 S1：**Flask app\_context + ORM（与 `cron_do` 一致）。

```
def update_cron_info(self, job_id):
    cron_id = job_id.split('_')[-1]
    try:
        cron_pk = int(cron_id)
    except (TypeError, ValueError):
        return
    app = self._get_flask_app()  # 见 §4.1
    with app.app_context():
        from datas.model.cron_infos import CronInfos
        cif = db.session.get(CronInfos, cron_pk)
        if cif and cif.status != -1:
            cif.status = -1
            db.session.commit()
    except Exception:
        db.session.rollback()
```

### 4.1 获取 Flask app 引用

`CuBackgroundScheduler` 由 `Flask-APScheduler` 挂载，`scheduler.app` 在 `create_app` 里已赋值。在 `update_cron_info` 内使用 `from app import scheduler` 或 `self._scheduler_ref` 取 `scheduler.app`，避免循环 import（实现时以最小 diff 为准）。

### 4.2 行为不变点

- 仅在 job 被 remove / executor 失败时把对应 `cron_infos.status` 置 `-1`（与现网一致）。
- 异常仍吞掉或打日志（现 `except: pass` 可改为 `logger.debug`，非必须）。
- 不触发微信告警（与现网一致）。

### PR-T2 · `cron_check` 对账（读 JobStore + 写业务库）

**推荐方案 S2：**调度库用独立 `create_engine(cron_db_url)` + `text()`；业务侧继续现有 `scalars(select(CronInfos))`。

```
from sqlalchemy import create_engine, text

def _fetch_apscheduler_job_ids(cron_db_url):
    engine = create_engine(cron_db_url, pool_pre_ping=True)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id FROM apscheduler_jobs")).fetchall()
    return {row[0] for row in rows}
```

将 `cron_check` 内 `records.Database` 整段替换；`job_arr` 改为 set 成员检测。业务库更新逻辑不变。

**备选 S2′：**从 APScheduler 已初始化的 JobStore engine 取连接（耦合更强，不推荐首期）。

### PR-T3 · 移除 `records` 依赖

- 删除 `requirements.txt`、`requirements-core.txt` 中 `records==0.5.3`
- 删除三处 `import records`
- 更新 `THIRD_PARTY_NOTICES.md`
- 全量 `pip install` + 测试 + Docker 构建

### （可选 PR-T4 · 为 Tier 3a 铺路，可并入 Tier 3a）

`main/views.py` 三处 `db.session.query(...).paginate()` 改为 `select` + 手动分页或 FSA 3 推荐写法——**非 Tier 3 前置硬性要求**，但升 SA 2 时必须改。

## 五、数据流（改后）

APScheduler \_process\_jobs (portalocker)
→ job 完成/失效 → update\_cron\_info
→ app.app\_context() → db.session.get(CronInfos) → status=-1
cron\_check (每 30min, @single\_task)
→ engine(cron\_db\_url) + text(SELECT id FROM apscheduler\_jobs)
→ 与 CronInfos 对账 → 缺失则 status=-1

## 六、风险与缓解

| 风险 | 缓解 |
| --- | --- |
| 调度线程内 `db.session` 未 commit/rollback | 严格 `try/commit` + `except/rollback`；不跨请求复用 session |
| gunicorn 多 worker 并发写同一行 | 现网已存在；`status=-1` 幂等，无恶化 |
| `cron_db_url` 与 JobStore 配置不一致 | PR-T2 统一读 `current_app.config['CRON_DB_URL']`（与现 `cron_check` 一致） |
| SQLite 文件锁 | 与现 `records` 行为同级；Docker 冒烟 + 单任务一次性 job 回归 |

## 七、验收清单

1. **一次性任务**：添加 `run_date` 任务 → 触发一次 → job 从 store 移除 → `cron_infos.status` 变为 `-1`。
2. **cron\_check**：手动删除 `apscheduler_jobs` 中某 `cron_{id}` 行 → 30 分钟内（或临时改 cron 触发间隔做测试）对应任务 `status=-1`。
3. **多 worker**：Docker `gun.py` workers>1 时调度仍正常，无 `scheduler.lock` 死锁回归。
4. **双库**：SQLite 分离文件配置下 T1/T2 均成功。
5. `rg records` 无业务引用；`pip install -r requirements.txt` 无 records。
6. `bash scripts/cronpilot.sh test` + `verify_docker_compose.sh`。

## 八、实现触点汇总

| PR | 文件 |
| --- | --- |
| T1 | `app/CuBackgroundScheduler.py`、`app/CuGeventScheduler.py` |
| T2 | `app/crons.py`；可抽 `app/services/scheduler_db.py`（可选，避免 crons 膨胀） |
| T3 | `requirements*.txt`、`THIRD_PARTY_NOTICES.md` |
| 测试 | 新 `tests/test_scheduler_db.py`：mock engine 返回 job id；`update_cron_info` 集成测（SQLite 内存双 bind 可选） |
| 文档 | `依赖升级RFC` 标 Tier 3 前置 ✓；`RELEASE_NOTES` 一节 |

## 九、与 RBAC / P1 排期

| 并行性 | 说明 |
| --- | --- |
| P1 小步 / P1-03/04 | **可并行**（不同目录） |
| RBAC 首期 | **可并行**；RBAC 新代码禁止再用 `records` |
| Tier 3a SA 2.0 | **必须**在本设计 T1～T3 完成并回归后 |

## 十、确认记录

**2026-07-17 已确认并落地：**

- ☑ `update_cron_info` 采用方案 **S1**（app\_context + ORM / `apply_retire`）
- ☑ `cron_check` 采用方案 **S2**（独立 engine + `text()`，经 `app/services/scheduler_db.py`）
- ☑ `CuGeventScheduler.py`：**同步改法**（与 Background 同口径，避免漂移）
- ☑ 实现顺序：T1 → T2 → T3（同里程碑交付）；抽 `scheduler_db` 公共模块

[依赖升级 RFC · Tier 3](依赖升级RFC.html) ·
[架构设计文档](../arch/架构设计文档.html) ·
[文档索引](../index.html)

CronPilot · Tier 3 前置收束 · 已交付 · [Markdown](Tier3前置收束设计.md) · [索引](../index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
