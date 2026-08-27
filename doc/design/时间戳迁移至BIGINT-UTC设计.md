# 时间戳全量迁移至 BIGINT (UTC) 设计方案

> HTML 版：[时间戳迁移至BIGINT-UTC设计.html](时间戳迁移至BIGINT-UTC设计.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 时间戳全量迁移至 BIGINT (UTC) 设计方案 待确认

**文档编号**：OPT-PERF-TIMESTAMP-BIGINT  
**前置文档**：`doc/design/时间戳存储格式优化评估.html`（三方案对比）  
**创建**：2026-08-26  
**状态**：待确认  
**已确认决策**：时区策略 = **方案 T-A（真正转 UTC）**；展示层时区 = **方案 C（全局配置 + 预留 tz 参数）**

---

## 1. 问题

当前所有时间字段使用 `VARCHAR(25)` 存储 `'YYYY-MM-DD HH:MM:SS'` 格式字符串，存在以下问题：

1. **存储膨胀**：19 字节 + VARCHAR 开销 vs BIGINT 的 8 字节（~2.6x 浪费）
2. **查询效率**：字符串比较慢于整数比较，`LIKE 'date%'` 模式不够确定
3. **无时区语义**：隐式依赖服务器本地时区，多机/多时区部署时有歧义
4. **应用层解析开销**：每次比较需 `strptime()` 解析字符串
5. **空值语义混乱**：`''` 和 `NULL` 混用

## 2. 根因

项目早期为快速实现，所有时间字段统一使用 `VARCHAR` 存储格式化字符串。
随着执行日志量增长和逾期检测等实时计算功能引入，字符串格式的性能与语义局限性逐渐暴露。

## 3. 方案

### 3.1 目标格式

| 属性 | 规格 |
| --- | --- |
| 存储类型 | `BIGINT`（SQLAlchemy: `db.BigInteger`） |
| 时区 | **UTC**（写入时统一转 UTC，展示时按需转本地） |
| 精度 | **百毫秒**（hectomillisecond，10 ticks/sec） |
| 单位 | 自 1970-01-01 00:00:00 UTC 起的百毫秒计数 |
| 示例值 | `2026-08-26 09:55:00.000 UTC` → `17878605000` |
| 范围 | `0` ~ `2^63-1`（远超 Y2038，可用至 ~29 亿年） |

#### 3.1.1 百毫秒精度决策分析

| 精度选项 | 单位 | 数值位数 | 适用场景 | CronPilot 适配度 |
| --- | --- | --- | --- | --- |
| 秒 (s) | 1 tick/s | 10 位（当前年代） | 传统 Unix timestamp | 不足 — 任务执行耗时需亚秒精度 |
| **百毫秒 (100ms)** | 10 ticks/s | 11 位（当前年代） | 调度系统、日志记录 | **最佳** — 满足调度精度，数值紧凑 |
| 毫秒 (ms) | 1000 ticks/s | 13 位（当前年代） | Java/JS 生态标准 | 超需 — cron 最小粒度为秒，100ms 已足够 |
| 微秒 (μs) | 10⁶ ticks/s | 16 位 | 数据库内部、高频交易 | 远超需求 |

**百毫秒 vs 毫秒权衡**：  
• 百毫秒值（11 位）比毫秒值（13 位）短 2 位，日志肉眼更易阅读  
• CronPilot 最高频场景是 cron 执行（最快 `*/1 * * * *` = 每分钟），百毫秒精度远超调度需求  
• `take_time`（执行耗时）当前精度为 0.001s，转换后 `int(float_seconds * 10)` → 个位数精度已够用（如 3.18s → 32 百毫秒）  
• **注意**：若未来需要与 Java/JS 生态集成（如 Kafka、Elasticsearch），毫秒是更通用的约定。该迁移成本极低（全局 `×10` / `÷10`）。

### 3.2 核心工具函数设计

```
# datas/utils/times.py — 重构后

import time
from datetime import datetime, timedelta, timezone

UTC = timezone.utc

# ═══ 写入 ═══

def utc_now_hms():
    """当前 UTC 时间，百毫秒精度 BIGINT。"""
    return int(time.time() * 10)

def utc_today_start_hms():
    """今日 UTC 00:00:00 对应的百毫秒 BIGINT。"""
    now = datetime.now(UTC)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(midnight.timestamp() * 10)

def utc_tomorrow_start_hms():
    """明日 UTC 00:00:00 对应的百毫秒 BIGINT。"""
    now = datetime.now(UTC)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(tomorrow.timestamp() * 10)

# ═══ 展示（BIGINT → 可读字符串）═══

def hms_to_display(hms_value, fmt='%Y-%m-%d %H:%M:%S', tz=None):
    """百毫秒 BIGINT → 本地可读字符串。
    tz=None 时使用服务器本地时区（向下兼容现有展示行为）。
    """
    if not hms_value:
        return ''
    try:
        ts = int(hms_value) / 10.0
        dt = datetime.fromtimestamp(ts, tz=tz)
        return dt.strftime(fmt)
    except (ValueError, TypeError, OSError):
        return ''

def hms_to_datetime(hms_value):
    """百毫秒 BIGINT → datetime (UTC)。"""
    if not hms_value:
        return None
    return datetime.fromtimestamp(int(hms_value) / 10.0, tz=UTC)

def datetime_to_hms(dt):
    """datetime → 百毫秒 BIGINT。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp() * 10)

# ═══ 兼容（旧格式字符串 ↔ BIGINT 互转）═══

def str_to_hms(time_str):
    """'YYYY-MM-DD HH:MM:SS' → 百毫秒 BIGINT（假定为 UTC）。
    用于数据迁移和旧测试数据。
    """
    if not time_str or time_str.strip() == '':
        return None
    try:
        dt = datetime.strptime(str(time_str)[:19], '%Y-%m-%d %H:%M:%S')
        dt = dt.replace(tzinfo=UTC)
        return int(dt.timestamp() * 10)
    except (ValueError, TypeError):
        return None

def hms_to_str(hms_value, fmt='%Y-%m-%d %H:%M:%S'):
    """百毫秒 BIGINT → 'YYYY-MM-DD HH:MM:SS' 字符串。
    用于 API 响应和展示层兼容。
    """
    return hms_to_display(hms_value, fmt=fmt)

# ═══ 向下兼容（过渡期保留，标记 Deprecated）═══

def get_now_time(format='%Y-%m-%d %H:%M:%S'):
    """[DEPRECATED] 旧接口兼容，返回本地时间字符串。
    新代码应使用 utc_now_hms()。
    """
    return time.strftime(format, time.localtime(time.time()))

def get_today(format='%Y-%m-%d'):
    """[DEPRECATED] 旧接口兼容。
    新代码应使用 utc_today_start_hms()。
    """
    return time.strftime(format, time.localtime(time.time()))
```

### 3.3 Model 变更示例

```
# 迁移前（VARCHAR）
class JobLog(db.Model):
    create_time: Mapped[str] = mapped_column(db.String(25), nullable=False, default='', index=True)
    started_at: Mapped[Optional[str]] = mapped_column(db.String(25), nullable=True)
    finished_at: Mapped[Optional[str]] = mapped_column(db.String(25), nullable=True)

# 迁移后（BIGINT）
class JobLog(db.Model):
    create_time: Mapped[int] = mapped_column(db.BigInteger, nullable=False, default=0, index=True)
    started_at: Mapped[Optional[int]] = mapped_column(db.BigInteger, nullable=True)
    finished_at: Mapped[Optional[int]] = mapped_column(db.BigInteger, nullable=True)
```

### 3.4 查询模式迁移

| 场景 | 迁移前 | 迁移后 |
| --- | --- | --- |
| 当日过滤 | `create_time.like(today + '%')` | `create_time >= utc_today_start_hms(), create_time < utc_tomorrow_start_hms()` |
| 时间区间 | `create_time.between(beg_str, end_str)` | `create_time >= str_to_hms(beg_str), create_time <= str_to_hms(end_str)` |
| 最近执行 | `func.max(create_time)` → `strptime` | `func.max(create_time)` → `hms_to_datetime(v)` |
| 耗时比较 | `datetime.strptime(ct) - datetime.strptime(st)` | `(create_time - started_at) / 10.0`（直接得秒数） |
| 过期判断 | `strptime(expires_at) > now()` | `expires_at > utc_now_hms()` |
| 写入 | `create_time=get_now_time()` | `create_time=utc_now_hms()` |
| 展示 | 直接使用字符串 | 模板 filter `{{ val|hms_display }}` 或 view 层 `hms_to_display(v)` |

### 3.5 API 响应兼容策略

**⚠️ API Breaking Change**：外部 API（`/api/cron/*`）目前返回时间字符串（如 `"create_time": "2026-08-26 09:55:00"`）。
迁移后若直接返回 BIGINT，所有 API 消费者将失败。

**推荐策略**：API 响应层增加序列化适配，**对外仍返回 ISO 8601 字符串**：

```
# app/api/views.py — 序列化示例
from datas.utils.times import hms_to_str

result = {
    'create_time': hms_to_str(row.create_time),  # "2026-08-26 09:55:00"
    'started_at': hms_to_str(row.started_at),
    'finished_at': hms_to_str(row.finished_at),
}
```

API 消费者无感知。未来若需返回 BIGINT，可新增 `?format=epoch` 参数或 v2 API。

### 3.6 模板展示适配

```
# app/__init__.py — 注册 Jinja2 filter
from datas.utils.times import hms_to_display

app.jinja_env.filters['hms_display'] = hms_to_display
app.jinja_env.filters['hms_date'] = lambda v: hms_to_display(v, '%Y-%m-%d')
app.jinja_env.filters['hms_time'] = lambda v: hms_to_display(v, '%H:%M:%S')
app.jinja_env.filters['hms_short'] = lambda v: hms_to_display(v, '%m-%d %H:%M')
```

```
{# 模板中使用 #}
<td>{{ item.create_time|hms_display }}</td>
<td>{{ item.updated_at|hms_short }}</td>
```

## 4. 影响范围

### 4.1 变更统计

| 分类 | 文件/位置 | 变更类型 | 行数估计 |
| --- | --- | --- | --- |
| **Model 定义** (9 个 Model) | `datas/model/job_log.py` | String→BigInteger (3 字段) | ~6 |
| `datas/model/cron_infos.py` | String→BigInteger (4 字段) | ~8 |
| `datas/model/job_health.py` | String→BigInteger (4 字段) | ~8 |
| `datas/model/operation_log.py` | String→BigInteger (1 字段) | ~2 |
| `datas/model/rbac_audit_log.py` | String→BigInteger (1 字段) | ~2 |
| `datas/model/rbac_user.py` / `rbac_registration_request.py` / `tag.py` / `resource_group.py` | String→BigInteger (7 字段) | ~14 |
| **工具 / 服务层** | `datas/utils/times.py` | 重构核心 | ~80 |
| `app/services/*.py` (cron\_service, operation\_log\_service, tag\_service, cron\_validator, job\_health\_service, rbac/services) | `get_now_time()` → `utc_now_hms()` | ~30 |
| `app/crons.py` | 写入路径迁移 | ~10 |
| **Repository 层** | `app/repositories/cron_repository.py` | LIKE → 范围比较 + strptime 去除 | ~15 |
| `app/repositories/rbac_audit_log_repository.py` / `operation_log_repository.py` | 字符串比较 → 整数比较 | ~8 |
| **View 层** | `app/main/views.py` | 查询迁移 + 展示适配 | ~30 |
| `app/api/views.py` | 序列化适配 `hms_to_str()` | ~20 |
| **模板层** | ~20 个 HTML 模板 | 直接引用 → `|hms_display` filter | ~35 |
| **迁移脚本** | `scripts/ensure_business_tables.py` | 新增列类型迁移函数 | ~120 |
| **测试** | ~12 个测试文件 | 时间数据从字符串 → BIGINT | ~100 |
| 合计 | |  | ~490 行 |

### 4.2 明确不做

- 不变更 `take_time` 字段格式（已为 VARCHAR 存储秒数字符串，独立处理）
- 不变更 `log_id`（UUID 字符串，非时间戳）
- 不变更 `cron_infos` 的调度字段（`run_date`、`minute`、`hour` 等 — 这些是 cron 表达式，非时间戳）
- 不在本轮引入 MySQL 分区表
- 不修改外部 API 的 JSON 响应格式（仍返回 ISO 8601 字符串）

## 5. 分批实施计划

Phase T1：基础设施 + 工具层

| 任务 | 文件 | 验收 |
| --- | --- | --- |
| 重构 `datas/utils/times.py` | `datas/utils/times.py` | 新旧函数单测通过：`utc_now_hms` / `str_to_hms` / `hms_to_display` 互转精度验证 |
| 注册 Jinja2 filter | `app/__init__.py` | `hms_display` filter 在模板中可用 |
| 新增 `tests/test_timestamp_utils.py` | `tests/test_timestamp_utils.py` | 覆盖：UTC 转换、百毫秒精度、空值处理、字符串互转、跨日/跨月/跨年边界 |

**独立验收**：此阶段不修改任何 Model 或数据库，纯代码层新增，`cronpilot.sh test` 全通过。

Phase T2：Model 层迁移 + 数据迁移脚本

| 任务 | 文件 | 验收 |
| --- | --- | --- |
| 所有 Model 的时间字段 `String(25)` → `BigInteger` | 9 个 `datas/model/*.py` | Model 定义与 DB schema 对齐 |
| 数据迁移脚本 `_migrate_time_columns_to_bigint()` | `scripts/ensure_business_tables.py` | 幂等执行，支持 SQLite / MySQL 双后端 |
| 迁移脚本测试 | `tests/test_ensure_business_tables.py` | 空库 → 新建 BIGINT 列；旧库 → 数据正确迁移 |

**独立验收**：迁移脚本在 SQLite 测试库上执行，数据正确转换，`.tables` + 抽样验证。

Phase T3：写入路径迁移（服务层 + 调度器）

| 任务 | 文件 | 验收 |
| --- | --- | --- |
| 所有 `get_now_time()` → `utc_now_hms()` | `app/services/*.py`, `app/crons.py`, `app/rbac/services.py` | 新写入的记录 `create_time` 为 BIGINT |
| 写入路径测试 | 相关测试文件 | 创建任务/用户/日志后查 DB 值为整数 |

**独立验收**：手动触发一次 cron 执行 → `job_log.create_time` 为 BIGINT 值。

Phase T4：读取路径迁移（Repository + View + API）

| 任务 | 文件 | 验收 |
| --- | --- | --- |
| Repository 查询迁移 | `app/repositories/*.py` | LIKE → 整数范围；strptime → 整数比较 |
| View 层展示适配 | `app/main/views.py` | 逾期检测、耗时计算等直接用整数 |
| API 序列化 | `app/api/views.py` | API 响应仍为 ISO 8601 字符串 |

**独立验收**：Dashboard + 执行记录 + 任务详情页面数据正确展示。

Phase T5：模板层适配 + 全量回归

| 任务 | 文件 | 验收 |
| --- | --- | --- |
| 所有模板中直接引用 → `|hms_display` | ~20 个 `app/templates/redesign/*.html` | 所有页面时间展示正确 |
| 全量测试回归 | — | `cronpilot.sh test` + `verify_golden_path.sh` + 浏览器 4 角色验证 |
| 清理废弃函数 | `datas/utils/times.py` | 移除 `get_now_time()`、`get_today()`、`get_next_time()` |

**独立验收**：全站所有页面时间展示正确 + 全量测试通过 + API 响应格式不变。

## 6. 数据迁移策略

### 6.1 SQLite 迁移（需要建新表）

SQLite 不支持 `ALTER COLUMN`，需要：

```
-- 1. 创建新表（BIGINT 类型）
CREATE TABLE job_log_new (
    id INTEGER PRIMARY KEY,
    log_id VARCHAR(65) NOT NULL DEFAULT '',
    cron_info_id INTEGER NOT NULL DEFAULT 0,
    content TEXT NOT NULL DEFAULT '',
    http_status INTEGER,
    status VARCHAR(16),
    fail_reason VARCHAR(128),
    create_time BIGINT NOT NULL DEFAULT 0,      -- 原 VARCHAR(25)
    take_time VARCHAR(25) DEFAULT '',
    started_at BIGINT,                           -- 原 VARCHAR(25)
    finished_at BIGINT,                          -- 原 VARCHAR(25)
    timeout_sec INTEGER
);

-- 2. 迁移数据（VARCHAR → BIGINT，本地时间 → UTC）
--    'utc' 修饰符：告诉 SQLite "输入是本地时间，请输出 UTC epoch"
INSERT INTO job_log_new
SELECT id, log_id, cron_info_id, content, http_status, status, fail_reason,
       CASE WHEN create_time = '' OR create_time IS NULL THEN 0
            ELSE CAST(strftime('%s', create_time, 'utc') AS INTEGER) * 10
       END,
       take_time,
       CASE WHEN started_at = '' OR started_at IS NULL THEN NULL
            ELSE CAST(strftime('%s', started_at, 'utc') AS INTEGER) * 10
       END,
       CASE WHEN finished_at = '' OR finished_at IS NULL THEN NULL
            ELSE CAST(strftime('%s', finished_at, 'utc') AS INTEGER) * 10
       END,
       timeout_sec
FROM job_log;

-- 3. 替换旧表
DROP TABLE job_log;
ALTER TABLE job_log_new RENAME TO job_log;

-- 4. 重建索引
CREATE INDEX ix_job_log_log_id ON job_log (log_id);
CREATE INDEX ix_job_log_cron_info_id ON job_log (cron_info_id);
CREATE INDEX ix_job_log_create_time ON job_log (create_time);
CREATE INDEX ix_job_log_cron_id_create_time ON job_log (cron_info_id, create_time);
```

### 6.2 MySQL 迁移（原地 ALTER）

```
-- 0. 确保 session 时区与旧数据一致（方案 T-A 关键步骤）
SET time_zone = '+08:00';  -- 根据实际服务器时区调整

-- 1. 新增临时列
ALTER TABLE job_log ADD COLUMN create_time_new BIGINT DEFAULT 0;

-- 2. 填充数据（本地时间 → UTC epoch × 10）
UPDATE job_log SET create_time_new =
    CASE WHEN create_time = '' OR create_time IS NULL THEN 0
         ELSE UNIX_TIMESTAMP(create_time) * 10
    END;

-- 3. 重命名（MySQL 8.0+）
ALTER TABLE job_log DROP COLUMN create_time;
ALTER TABLE job_log CHANGE create_time_new create_time BIGINT NOT NULL DEFAULT 0;

-- 4. 重建索引
CREATE INDEX ix_job_log_create_time ON job_log (create_time);
```

**MySQL 大表注意**：`job_log` 若超过 100 万行，`UPDATE` 和 `ALTER TABLE`
需使用在线 DDL 或 pt-online-schema-change 避免锁表。建议在低峰期执行。

### 6.3 迁移安全措施

| 措施 | 说明 |
| --- | --- |
| 备份验证 | 迁移前 `cp datas/job_log.sqlite datas/job_log.sqlite.bak` |
| 幂等设计 | 检测列类型后再执行迁移，已迁移的跳过 |
| 抽样验证 | 迁移后随机取 10 条记录，`hms_to_str(new_value) == old_value` |
| 回滚能力 | 保留 `.bak` 文件 7 天；MySQL 保留旧列为 `_old` 后缀 |

## 7. 验收

| # | 验收项 | 命令 / 方法 |
| --- | --- | --- |
| 1 | 所有 Model 时间字段为 BIGINT | `grep -rn "db.String(25)" datas/model/ | grep -i "time\|_at"` → 0 结果 |
| 2 | 无残留 `get_now_time()` 调用（测试除外） | `grep -rn "get_now_time\|get_today" app/` → 0 结果 |
| 3 | 无残留 `LIKE` 日期过滤 | `grep -rn "\.like(today" app/` → 0 结果 |
| 4 | API 响应格式不变 | `curl /api/cron/job_log_list` → `create_time` 仍为 `"YYYY-MM-DD HH:MM:SS"` |
| 5 | 全量测试通过 | `bash scripts/cronpilot.sh test` |
| 6 | 黄金路径验证 | `bash scripts/verify_golden_path.sh` |
| 7 | 数据库值为整数 | `sqlite3 datas/job_log.sqlite "SELECT typeof(create_time), create_time FROM job_log LIMIT 3"` → `integer` |
| 8 | Dashboard 今日统计正确 | 浏览器登录 → Dashboard 数据正确 |
| 9 | 4 角色浏览器验证 | Seed Admin / Biz Admin / Operator / Viewer 各页面时间展示正确 |
| 10 | 逾期检测功能正常 | Dashboard 逾期统计与迁移前一致 |

## 8. 风险

| 风险 | 概率 | 影响 | 缓解 |
| --- | --- | --- | --- |
| **SQLite strftime 时区**：SQLite `strftime('%s', ...)` 假定输入为 UTC | 中 | 高（旧数据实为本地时间，转换后偏移） | 迁移脚本中对本地时区旧数据做偏移补偿：`CAST(strftime('%s', ct, 'utc') AS INTEGER) * 10` |
| **大表迁移性能**：`job_log` 百万行级建新表+复制 | 低~中 | 中（迁移期间服务不可用） | 提供停机迁移 + 在线迁移两种路径，默认停机（安全） |
| **跨时区数据歧义**：旧数据为本地时间，新数据为 UTC | 中 | 中（展示时偏移） | 迁移脚本统一转 UTC；展示层 `hms_to_display()` 按服务器本地时区还原 |
| **API 消费者断裂** | 低 | 高 | API 序列化层确保对外仍返回 ISO 8601 字符串 |
| **测试全面性**：12 个测试文件需同步改 | 中 | 中（遗漏导致假绿） | 分 Phase 逐步迁移；每 Phase 独立验收 |
| **百毫秒精度非标准**：未来集成时需适配 | 低 | 低 | 集成时 `×10`/`÷10` 转毫秒；或届时全局切换精度（改 `*10` 为 `*1000`） |

## 9. 时区迁移策略 已确认：方案 T-A

**决策**：采用 **方案 T-A — 真正转 UTC**。旧数据（服务器本地时间）在迁移时转换为 UTC epoch，
新写入代码一律使用 `time.time()`（天然 UTC）。

### 9.1 迁移转换公式

#### SQLite 转换

**SQLite `strftime` 时区行为解析**：  
• `strftime('%s', '2026-08-26 09:55:00')` → 将输入视为 **UTC**，返回 UTC epoch  
• `strftime('%s', '2026-08-26 09:55:00', 'utc')` → 将输入视为**本地时间**，返回 UTC epoch ← **这才是正确的**  
• 注意：SQLite 的 `'utc'` 修饰符含义是"请把输入理解为本地时间，然后输出 UTC"（反直觉但正确）

```
-- SQLite：旧数据为本地时间 → 使用 'utc' 修饰符将本地时间转为 UTC epoch
-- 然后 × 10 得到百毫秒
CASE WHEN create_time = '' OR create_time IS NULL THEN 0
     ELSE CAST(strftime('%s', create_time, 'utc') AS INTEGER) * 10
END

-- 验证示例（假设服务器 UTC+8）：
-- 输入: '2026-08-26 09:55:00'（本地 UTC+8 = UTC 01:55:00）
-- strftime('%s', '2026-08-26 09:55:00', 'utc')
--   → 先按本地解析 → 减去 8h → 输出 UTC epoch of 01:55:00
--   → 1787831700
-- × 10 → 17878317000 ← 正确的 UTC 百毫秒
```

#### MySQL 转换

```
-- MySQL：UNIX_TIMESTAMP() 自动按 @@session.time_zone 解释输入
-- 需确保 session time_zone 与旧数据写入时的服务器时区一致

-- 迁移脚本开头设置 session 时区
SET time_zone = '+08:00';  -- 根据实际服务器时区调整

-- 转换
CASE WHEN create_time = '' OR create_time IS NULL THEN 0
     ELSE UNIX_TIMESTAMP(create_time) * 10
END

-- 验证：
-- UNIX_TIMESTAMP('2026-08-26 09:55:00') with time_zone='+08:00'
-- → 1787831700 (= 2026-08-26 01:55:00 UTC)
-- × 10 → 17878317000 ← 与 SQLite 结果一致 ✓
```

#### Python 迁移脚本中的时区检测

```
import time

def _detect_tz_offset():
    """检测服务器当前时区偏移量（秒），用于迁移验证。
    UTC+8 → 返回 28800
    """
    return -time.timezone if time.daylight == 0 else -time.altzone

def _verify_migration_sample(old_str, new_bigint):
    """验证单条迁移数据的正确性。
    old_str: '2026-08-26 09:55:00'（本地时间）
    new_bigint: 17878317000（UTC 百毫秒）
    """
    from datetime import datetime, timezone, timedelta
    local_dt = datetime.strptime(old_str, '%Y-%m-%d %H:%M:%S')
    tz_offset = _detect_tz_offset()
    local_tz = timezone(timedelta(seconds=tz_offset))
    local_dt = local_dt.replace(tzinfo=local_tz)
    expected_hms = int(local_dt.timestamp() * 10)
    assert new_bigint == expected_hms, \
        f"Migration mismatch: {old_str} → expected {expected_hms}, got {new_bigint}"
```

### 9.2 新代码写入方式（迁移后）

```
# 写入：time.time() 天然返回 UTC epoch（float 秒）
def utc_now_hms():
    return int(time.time() * 10)

# 展示：fromtimestamp 默认按服务器本地时区还原
def hms_to_display(hms_value, fmt='%Y-%m-%d %H:%M:%S', tz=None):
    if not hms_value:
        return ''
    ts = int(hms_value) / 10.0
    dt = datetime.fromtimestamp(ts, tz=tz)  # tz=None → 本地时区
    return dt.strftime(fmt)
```

用户看到的时间与迁移前完全一致（本地时间展示），但数据库中存储的是 UTC epoch。

### 9.3 迁移验证清单

| # | 验证项 | 方法 |
| --- | --- | --- |
| 1 | 时区偏移量探测 | 迁移脚本开头打印 `_detect_tz_offset()`，人工确认与服务器时区一致 |
| 2 | SQLite 转换公式验证 | `SELECT strftime('%s', '2026-08-26 09:55:00', 'utc')` → 比对 Python 计算结果 |
| 3 | 迁移后抽样 10 条 | `_verify_migration_sample(old, new)` 全部通过 |
| 4 | 展示不变验证 | 迁移前截图 vs 迁移后截图，所有页面时间展示一致 |
| 5 | 跨日边界验证 | `utc_today_start_hms()` 在 UTC+8 00:00 和 08:00 各执行一次，确认"今日"范围正确 |

### 9.4 方案 T-B 备选说明（未采用）

方案 T-B（保持原值含义）迁移更简单但数据语义不纯正，不支持多时区部署。
若未来发现 T-A 迁移导致时区偏移问题，可回退到 T-B 作为降级方案。

## 10. 附录：全量字段迁移清单

| # | 表 | 字段 | 当前类型 | 目标类型 | NULL 策略 | 默认值 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `job_log` | `create_time` | VARCHAR(25) | BIGINT | NOT NULL | 0 |
| 2 | `job_log` | `started_at` | VARCHAR(25) | BIGINT | NULL | NULL |
| 3 | `job_log` | `finished_at` | VARCHAR(25) | BIGINT | NULL | NULL |
| 4 | `cron_infos` | `created_at` | VARCHAR(25) | BIGINT | NULL | NULL |
| 5 | `cron_infos` | `updated_at` | VARCHAR(25) | BIGINT | NULL | NULL |
| 6 | `cron_infos` | `retired_at` | VARCHAR(25) | BIGINT | NULL | NULL |
| 7 | `cron_infos` | `last_operated_at` | VARCHAR(25) | BIGINT | NOT NULL | 0 |
| 8 | `job_health` | `last_run_at` | VARCHAR(25) | BIGINT | NOT NULL | 0 |
| 9 | `job_health` | `last_success_at` | VARCHAR(25) | BIGINT | NOT NULL | 0 |
| 10 | `job_health` | `last_fail_at` | VARCHAR(25) | BIGINT | NOT NULL | 0 |
| 11 | `job_health` | `updated_at` | VARCHAR(25) | BIGINT | NOT NULL | 0 |
| 12 | `operation_log` | `create_time` | VARCHAR(25) | BIGINT | NOT NULL | 0 |
| 13 | `rbac_audit_logs` | `create_time` | VARCHAR(25) | BIGINT | NOT NULL | 0 |
| 14 | `rbac_users` | `create_time` | VARCHAR(25) | BIGINT | NOT NULL | 0 |
| 15 | `rbac_users` | `last_login_at` | VARCHAR(25) | BIGINT | NULL | NULL |
| 16 | `rbac_users` | `api_token_expires_at` | VARCHAR(25) | BIGINT | NULL | NULL |
| 17 | `rbac_registration_requests` | `create_time` | VARCHAR(25) | BIGINT | NOT NULL | 0 |
| 18 | `rbac_registration_requests` | `update_time` | VARCHAR(25) | BIGINT | NULL | NULL |
| 19 | `tags` | `create_time` | VARCHAR(25) | BIGINT | NOT NULL | 0 |
| 20 | `tags` | `update_time` | VARCHAR(25) | BIGINT | NOT NULL | 0 |

---

文档版本 1.0 | 2026-08-26 | CronPilot 时间戳全量迁移至 BIGINT (UTC) 设计方案

· [Markdown](时间戳迁移至BIGINT-UTC设计.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
