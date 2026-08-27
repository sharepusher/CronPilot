# 孤儿 Job 监控告警设计

> HTML 版：[孤儿Job监控告警设计.html](孤儿Job监控告警设计.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 孤儿 Job 监控告警设计

OPT-P1 监控 APScheduler

## 1. 问题

APScheduler 的持久化 jobstore（`datas/cron.sqlite`）中存在 7 个"孤儿 job"——对应的 `cron_infos` 记录已不存在。每次触发时，`cron_do()` 检测到任务不存在，写入一条 error 日志到 `job_log`，但**无告警通知运维**。

**影响**：

- 17,770 条无意义的"定时任务不存在" job\_log 记录（其中 `cron_16` 每分钟 1 条）
- 运维无法从外部监控系统感知此异常
- "今日失败次数"指标被无意义 error 拉高（虽然 JOIN cron\_infos 后不计入，但历史记录累积）
- scheduler 线程资源被无意义回调消耗

## 2. 根因

### 2.1 历史路径（已封死）

旧版 `cron_del` / `cron_batch_del`（commit `1f73cb0` 之前）：

```
db.session.delete(cif)
db.session.commit()
try:
    scheduler.remove_job('cron_%s' % cron_id)
except:
    pass  # ← 吞掉所有异常，job 残留在 cron.sqlite
```

该路径已于 `1f73cb0`（feat: lifecycle replace delete with retire）封死，返回 HTTP 410。**当前代码不存在能产生新孤儿的路径。**

### 2.2 数据来源

| 孤儿 cron\_id | 触发频率 | 产生原因 | 证据 |
| --- | --- | --- | --- |
| 9, 10 | 5min / 10min | 旧版 cron\_del 删除后 remove\_job 失败 | 操作日志有 create\_cron 记录（b4-test-task, b4-browser-test） |
| 12, 14, 16, 19, 20 | 2min / 5min / 1min / 30min / 30min | cron.sqlite 继承自更早开发环境，对应的 cron\_infos 从未在当前库中创建 | job\_log 第 1 条即为 "定时任务不存在"；无创建操作日志 |

### 2.3 为何未被发现

- `cron_do()` 只写 `warning` 级别日志，无 Prometheus 指标
- `cron_check()` 只做正向对账（cron\_infos → APScheduler），不做反向
- Dashboard "今日失败" JOIN cron\_infos 过滤掉了这些 orphan 日志，从 UI 看不到异常

## 3. 方案

### 3.1 核心原则

- **只告警不自愈**：异常状态应由人工介入处理，不静默消除
- **执行记录如实记录**：APScheduler 触发了 cron\_do = 一次执行事件，job\_log 保持写入
- **升级可见性**：日志从 warning → error + Prometheus counter

### 3.2 改动

| 文件 | 改动 |
| --- | --- |
| `app/metrics.py` | 新增 `ORPHAN_JOB_DETECTED = Counter('cronpilot_orphan_job_detected_total', ..., ['cron_id'])` |
| `app/crons.py` | `cron_do()` 中 `if not cif:` 分支：① 日志 warning → error ② 递增 Prometheus counter |
| `datas/cron.sqlite` | 一次性清理当前 7 个已知孤儿 job |

### 3.3 代码变更详情

#### app/metrics.py

```
# 新增（在 JOBS_ACTIVE 之后）
ORPHAN_JOB_DETECTED = Counter(
    'cronpilot_orphan_job_detected_total',
    'Scheduler job fired but cron_infos record missing (should not happen)',
    ['cron_id'],
)
```

#### app/crons.py — cron\_do() 分支

```
if not cif:
    # Prometheus: 递增孤儿检测计数
    ORPHAN_JOB_DETECTED.labels(cron_id=str(cron_id)).inc()
    
    saved_jl = _save_job_log(
        cron_id, "定时任务不存在", nows, 0, log_id=cronpilot_log_id,
    )
    current_app.logger.error(
        "ORPHAN_JOB: scheduler has cron_%s but cron_infos record missing. "
        "Root cause: likely legacy cron_del without remove_job. "
        "Action: manually remove from cron.sqlite.",
        cron_id,
        extra={"event": "cron.orphan_detected", "cron_id": cron_id},
    )
    ...
```

#### 一次性清理

```
sqlite3 datas/cron.sqlite \
  "DELETE FROM apscheduler_jobs WHERE id IN ('cron_9','cron_10','cron_12','cron_14','cron_16','cron_19','cron_20')"
```

### 3.4 告警规则（Alertmanager / Grafana）

```
- alert: CronPilotOrphanJobFiring
  expr: increase(cronpilot_orphan_job_detected_total[10m]) > 0
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "检测到孤儿 scheduler job (cron_{{ $labels.cron_id }})"
    description: |
      APScheduler 中的 cron_{{ $labels.cron_id }} 在 cron_infos 表中无对应记录。
      可能原因：旧版删除残留、手动 DB 操作、数据迁移不完整。
      处理：sqlite3 datas/cron.sqlite "DELETE FROM apscheduler_jobs WHERE id='cron_{{ $labels.cron_id }}'"
```

## 4. 范围

### 4.1 改动范围

- `app/metrics.py` — 新增 1 个 Counter
- `app/crons.py` — `cron_do()` 中 2 行变更（日志级别 + counter）
- `datas/cron.sqlite` — 一次性 DELETE 7 条记录

### 4.2 不做

- 不做自愈（不调用 `scheduler.remove_job()`）
- 不做反向对账（`cron_check` 不改动）
- 不改 job\_log 写入逻辑（执行记录保持如实记录）
- 不修改 Dashboard 统计逻辑（已有 JOIN 过滤孤儿）

## 5. 分批

改动量极小（3 个文件、约 10 行代码），**单批交付**。

| 步骤 | 内容 | 可独立验收 |
| --- | --- | --- |
| 1 | app/metrics.py + app/crons.py 代码变更 | ✅ 单测 + 重启验证 |
| 2 | 清理当前 7 个孤儿 | ✅ 重启后无 "定时任务不存在" 日志 |

## 6. 验收

| # | 验收项 | 命令/方法 |
| --- | --- | --- |
| 1 | Prometheus counter 可见 | `curl http://127.0.0.1:5001/metrics 2>/dev/null | grep orphan`（如 Prometheus 启用） |
| 2 | 孤儿清理后无新 error 日志 | 重启后 `tail -f datas/logs/local-server.log | grep ORPHAN_JOB` 无输出 |
| 3 | 清理生效 | `sqlite3 datas/cron.sqlite "SELECT count(*) FROM apscheduler_jobs WHERE id IN ('cron_9','cron_10','cron_12','cron_14','cron_16','cron_19','cron_20')"` → 0 |
| 4 | 正常任务不受影响 | 触发已有任务（id 1-8）仍正常写入 job\_log |

## 7. 风险

- **低**：改动量极小（2 行代码 + 1 行 metrics 定义），不影响正常执行路径
- **残余风险**：如果未来出现新孤儿（手动 DB 操作等），由于不自愈，会持续消耗 scheduler 线程和产生 ERROR 日志，直到人工清理。这是有意设计（可见性优先于静默修复）
- **Prometheus 依赖**：如果 prometheus\_client 未安装，counter 降级为 NoOp（现有 metrics.py 已有此降级机制），告警依赖日志而非指标

---

*创建时间：2026-08-26 | 关联：迁移脚本清零有效时间戳复盘（`doc/postmortem/2026-08-迁移脚本清零有效时间戳.html`）*

[文档索引](index.html) · [Markdown](孤儿Job监控告警设计.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
