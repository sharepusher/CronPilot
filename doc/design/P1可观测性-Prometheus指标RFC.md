# CronPilot · Prometheus 指标 RFC（P1 可观测性）

> HTML 版：[P1可观测性-Prometheus指标RFC.html](P1可观测性-Prometheus指标RFC.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

[← 文档索引](../index.html)
P1已交付 v2.2.0

# Prometheus 指标 RFC（P1 可观测性 · OPT-P2-05）

调度延迟 · 执行耗时 · 成功率 · 锁竞争 · 写入字节分布 · 多进程聚合方案

状态：已交付 v2.2.0 · 2026-07-23

**前置条件：**结构化日志（`app/logging_config.py`、`trace_id`/`cron_id` ContextVar）已在 commit `656a31c` 交付。本 RFC 在其基础上增加 Prometheus 指标埋点，复用同一批上下文变量，无需重复改造 `cron_do` 调用链。

## §1 指标清单（含类型、标签、Bucket 配置）

| 指标名 | 类型 | 标签 | 含义 | 评级 |
| --- | --- | --- | --- | --- |
| `cronpilot_job_trigger_delay_seconds` | Histogram | `task_name` | 计划触发时间 vs 实际开始执行的差值；排查"调度器堵塞/锁竞争导致延迟执行"的核心指标 | 需补实现路径 |
| `cronpilot_job_duration_seconds` | Histogram | `task_name`, `status` | HTTP 回调耗时分布；直接复用 `t0 = time.time()` | 正确 |
| `cronpilot_job_total` | Counter | `task_name`, `status` | 执行总数；成功率 = `status="success" / all` | 正确 |
| `cronpilot_lock_contention_total` | Counter | `lock_type`, `result` | Redis/文件双层锁竞争频次；`result`: `acquired`/`skipped` | 低优先级 |
| `cronpilot_jobs_active` | Gauge | `state` | 当前各状态任务数（`running`/`paused`/`retired`）；由 `cron_check` 每 30 分钟更新 | 命名已修正 |
| `cronpilot_job_log_write_bytes` | Histogram | — | 每次写入 `job_log.content` 的字节数；用于校准大响应体分离阈值（§4 决策依据） | 正确 |
| `cronpilot_api_request_duration_seconds` | Histogram | `endpoint`, `method`, `http_status` | API/管理端请求耗时；由 `prometheus-flask-exporter` 自动埋点，路由分组避免高基数 | 正确 |

### 必配 Histogram Buckets

**⚠ 必改项：**默认 Bucket 上限 10s，而 `cron_do` HTTP timeout 是 120s。不自定义 Bucket 则超时任务全部落进 `+Inf`，P95/P99 曲线完全失真。

```
JOB_DURATION = Histogram(
    'cronpilot_job_duration_seconds', 'HTTP callback duration',
    ['task_name', 'status'],
    buckets=[0.1, 0.5, 1, 5, 10, 30, 60, 120, float('inf')]
)

TRIGGER_DELAY = Histogram(
    'cronpilot_job_trigger_delay_seconds', 'Scheduling delay',
    ['task_name'],
    buckets=[0.05, 0.1, 0.5, 1, 5, 15, 30, 60, float('inf')]
)

JOB_LOG_WRITE_BYTES = Histogram(
    'cronpilot_job_log_write_bytes', 'Content bytes per job log write',
    buckets=[1024, 4096, 16384, 32768, 65536, 131072, 524288, 2097152, float('inf')]
)  # 1KB → 2MB，用于校准分离存储阈值
```

## §2 trigger\_delay 实现路径（补全缺口 A）

**原设计缺口：**`cron_do(cron_id)` 当前签名不含 `scheduled_run_time`，文档中的 `datetime.now() - scheduled_run_time` 无法直接实现。

### 推荐方案：APScheduler EVENT 携带 fire\_time → ContextVar

在 `CuBackgroundScheduler._process_jobs` 触发时，APScheduler 内部已有 `run_time`（即计划执行时间）。通过监听 `EVENT_JOB_EXECUTED`/`EVENT_JOB_SUBMITTED`，或在调度循环中读取 `job._trigger.get_next_fire_time()`，将其写入 ContextVar，再在 `cron_do` 入口读取。

更简洁的备选方案（侵入性更小）：

```
# app/crons.py cron_do 入口 — 在获取 APScheduler job 之前读 next_run_time
# 注意：调度器触发时 next_run_time 已更新为"下一次"，不能在此读
# 因此在 APScheduler 触发前（before_execute hook）记录，更准确

# 最简可用方案：不强求精确 fire_time，改为记录"排队等待时间"
# 在 single_task 装饰器里记录 enqueue_time，cron_do 入口读差值
_ctx_enqueue_time: ContextVar[float] = ContextVar('enqueue_time', default=0.0)

# single_task 装饰器 wrapper 入口：
_ctx_enqueue_time.set(time.time())

# cron_do 入口：
enqueue_t = _ctx_enqueue_time.get()
if enqueue_t > 0:
    TRIGGER_DELAY.labels(task_name=task_name or 'unknown').observe(t0 - enqueue_t)
```

**设计决策点（需用户确认）：**采用"排队等待时间"（`single_task` 入队 → 实际执行开始）作为 trigger delay 的近似值，精度在毫秒级，已足够"调度器是否堵塞"的判断需求。若需要精确到"APScheduler 计划时间 vs 实际时间"，则需修改 APScheduler 内部代码，成本较高。

## §3 Gunicorn 多进程聚合方案（补全缺口 C）

**⚠ 不配置则多 worker 下数据丢失：**Gunicorn workers=2 时，每个 OS worker 进程有独立的内存注册表，`/metrics` 只能看到当前处理请求的 worker 的数据，另一个 worker 的指标完全不可见。

### 初始化顺序（关键）

```
# gun.py — 必须在所有 import 最前面，进程 fork 前设好
import os
os.environ.setdefault(
    'PROMETHEUS_MULTIPROC_DIR',
    os.path.join(os.path.dirname(__file__), 'datas', 'prometheus_tmp')
)
os.makedirs(os.environ['PROMETHEUS_MULTIPROC_DIR'], exist_ok=True)
```

### /metrics 端点（必须用 MultiProcessCollector）

```
# app/main/views.py 或独立蓝图
from prometheus_client import CollectorRegistry, multiprocess, generate_latest, CONTENT_TYPE_LATEST
from flask import Response

@main.route('/metrics')
def prometheus_metrics():
    # 必须在请求处理时动态创建 registry，不能复用全局实例
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    return Response(generate_latest(registry), mimetype=CONTENT_TYPE_LATEST)
```

### 访问控制（必须限制）

```
# 方案 A：Nginx upstream 配置（推荐生产）
# location /metrics { allow 10.0.0.0/8; deny all; proxy_pass ...; }

# 方案 B：Flask 中间件（适合无反向代理的场景）
@main.before_request
def _guard_metrics():
    if request.path == '/metrics':
        remote = request.remote_addr or ''
        allowed = current_app.config.get('METRICS_ALLOWED_IPS', ['127.0.0.1'])
        if remote not in allowed:
            return '', 403
```

### gevent worker 兼容性说明

每个 Gunicorn gevent worker 是一个独立 OS 进程（内含多条 greenlet），`prometheus_client.multiprocess` 在 OS 进程级别聚合，greenlet 内共享进程内存——这与 gevent 兼容，无需额外 monkey-patch。

## §4 依赖引入 Tier 审查（补全缺口 D）

| 包 | 版本（pin） | 许可证 | Python 3.8–3.11 | 合规 |
| --- | --- | --- | --- | --- |
| `prometheus_client` | `==0.20.0` | Apache-2.0 | ✅ | ✅ 可合规分发 |
| `prometheus-flask-exporter` | `==0.23.1` | MIT | ✅ | ✅ 可合规分发 |

**OPT-P2-11 Tier 归属：**属于监控基础设施依赖，归 Tier 3b（应用层可观测）。引入前须在 `doc/依赖升级RFC.html` 登记，并通过 `assert_framework_pins.sh` 验证。

## §5 埋点位置（对照现有代码）

### app/crons.py — cron\_do

```
from app.metrics import JOB_DURATION, JOB_TOTAL, TRIGGER_DELAY, JOB_LOG_WRITE_BYTES

# cron_do 入口（已有 t0 = time.time()）
enqueue_t = _ctx_enqueue_time.get()
if enqueue_t > 0 and task_name:
    TRIGGER_DELAY.labels(task_name=task_name).observe(t0 - enqueue_t)

# _save_job_log 写入前
JOB_LOG_WRITE_BYTES.observe(len((content or '').encode('utf-8')))

# cron_do finally 块（已有 duration_ms 计算）
JOB_DURATION.labels(task_name=task_name or 'unknown', status=final_status).observe(duration_ms / 1000)
JOB_TOTAL.labels(task_name=task_name or 'unknown', status=final_status).inc()
```

### app/metrics.py（新增，集中声明）

```
"""Prometheus metric declarations for CronPilot.

Import from here to avoid duplicate registration errors across modules.
All metrics use lazy registration (only active when prometheus_client is available).
"""
try:
    from prometheus_client import Counter, Histogram, Gauge

    JOB_TOTAL = Counter('cronpilot_job_total', 'Total job executions', ['task_name', 'status'])

    JOB_DURATION = Histogram(
        'cronpilot_job_duration_seconds', 'HTTP callback duration per execution',
        ['task_name', 'status'],
        buckets=[0.1, 0.5, 1, 5, 10, 30, 60, 120, float('inf')]
    )

    TRIGGER_DELAY = Histogram(
        'cronpilot_job_trigger_delay_seconds', 'Enqueue-to-start latency',
        ['task_name'],
        buckets=[0.05, 0.1, 0.5, 1, 5, 15, 30, 60, float('inf')]
    )

    JOB_LOG_WRITE_BYTES = Histogram(
        'cronpilot_job_log_write_bytes', 'Bytes written per job_log.content',
        buckets=[1024, 4096, 16384, 32768, 65536, 131072, 524288, 2097152, float('inf')]
    )

    JOBS_ACTIVE = Gauge('cronpilot_jobs_active', 'Active job count by state', ['state'])

    _PROMETHEUS_AVAILABLE = True

except ImportError:  # prometheus_client not installed (dev/test without metrics)
    _PROMETHEUS_AVAILABLE = False

    class _NoOp:
        def labels(self, **_): return self
        def observe(self, _): pass
        def inc(self): pass
        def set(self, _): pass

    JOB_TOTAL = JOB_DURATION = TRIGGER_DELAY = JOB_LOG_WRITE_BYTES = JOBS_ACTIVE = _NoOp()
```

## §6 Grafana / Alertmanager 告警规则

| 告警名 | PromQL 表达式 | 意义 |
| --- | --- | --- |
| 触发延迟异常 | `histogram_quantile(0.95, rate(cronpilot_job_trigger_delay_seconds_bucket[5m])) > 30` | 调度器堵塞或锁竞争，P95 延迟超 30s |
| 执行成功率骤降 | `rate(cronpilot_job_total{status!="success"}[5m]) / rate(cronpilot_job_total[5m]) > 0.2` | 过去 5 分钟失败率超 20% |
| 执行耗时 P99 异常 | `histogram_quantile(0.99, rate(cronpilot_job_duration_seconds_bucket[10m])) > 60` | P99 超 60s，接近 timeout 边界 |
| 锁竞争异常升高 | `rate(cronpilot_lock_contention_total{result="skipped"}[5m]) > 5` | 分钟内 5+ 次锁竞争失败，多节点问题 |

## §7 分批实施与验收

| Batch | 内容 | 文件 | 验收 |
| --- | --- | --- | --- |
| **Tier-Dep** | 引入 `prometheus_client==0.20.0` + `prometheus-flask-exporter==0.23.1`；更新 `doc/依赖升级RFC.html` | `requirements.txt` | `bash scripts/assert_framework_pins.sh` 通过 |
| **P-1** | 新建 `app/metrics.py`（含 NoOp 降级）；`gun.py` 增加 `PROMETHEUS_MULTIPROC_DIR` 初始化；`/metrics` 端点 | `app/metrics.py`、`gun.py`、`app/main/views.py` | `curl /metrics` 返回 200 + Prometheus 文本格式 |
| **P-2** | `cron_do` 埋点：`JOB_DURATION`、`JOB_TOTAL`、`JOB_LOG_WRITE_BYTES` | `app/crons.py` | 触发一次任务后 `curl /metrics | grep cronpilot_job` 出现数值 |
| **P-3** | `single_task` 装饰器写入 `_ctx_enqueue_time`；`cron_do` 入口计算 `TRIGGER_DELAY` | `app/common/functions.py`、`app/crons.py` | `cronpilot_job_trigger_delay_seconds_bucket` 有非零桶 |
| **P-4** | `cron_check` 更新 `JOBS_ACTIVE` Gauge；`lock_contention` 埋点（低优先级，可推迟） | `app/crons.py`、`app/common/functions.py` | `cronpilot_jobs_active` 有标签数值 |

## §8 风险与注意事项

| 风险 | 评估 | 缓解 |
| --- | --- | --- |
| `PROMETHEUS_MULTIPROC_DIR` 磁盘空间 | 低：每个指标约 4KB/进程/重启 | 进程重启时清空该目录（Gunicorn worker 退出会自动清理 `*.db` 文件） |
| `task_name` 高基数 | 低：任务数有界（用户主动创建，通常 <1000） | 若超过 10000 条任务，考虑截断 task\_name 或改用 cron\_id 分桶 |
| `/metrics` 未加鉴权被公网扫描 | 高：会泄露任务名、执行频次等内部信息 | 生产必须通过 Nginx allow/deny 或 Flask IP 中间件限制；部署文档须明确写明 |
| prometheus\_client 与 gevent 兼容性 | 低：已验证 prometheus\_client 0.20 + gevent 23.9.1 无冲突 | monkey\_patch\_all() 在 gun.py 最顶部已有，早于 prometheus\_client import |

## §9 原设计文档命名修正

| 原名（原设计文档） | 修正后 | 原因 |
| --- | --- | --- |
| `cronpilot_scheduler_jobs_gauge` | `cronpilot_jobs_active` | Prometheus 规范不在指标名里写 metric type；`_gauge` 后缀为反模式 |

[← P1 可观测优化设计](../plan/P1可观测优化设计.html) ·
[Markdown 版](P1可观测性-Prometheus指标RFC.md) ·
[文档索引](../index.html)

CronPilot · Apache-2.0 · [GitHub](https://github.com/sharepusher/CronPilot)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
