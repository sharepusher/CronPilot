# CronPilot 50-bit 时间戳 ID 生成器技术文档

> HTML 版：[CronPilot-50bit-ID生成器技术文档.html](CronPilot-50bit-ID生成器技术文档.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# CronPilot 50-bit 时间戳 ID 生成器技术文档

**版本**：v1.0   **引入版本**：v4.0.0（OPT-P0-21）   **最后更新**：2026-09-07

**源码位置**：`datas/utils/id_generator.py`

**关联设计**：[OPT-P0-21 设计文档](新任务继承旧健康记录Bug设计.html)

**目录**

1. [背景与动机](#background)
2. [ID 结构](#structure)
3. [参数规格](#parameters)
4. [API 参考](#api)
5. [集成方式](#integration)
6. [线程安全与并发](#thread-safety)
7. [数据库兼容性](#db-compat)
8. [JavaScript 精度安全](#js-safety)
9. [迁移与共存](#migration)
10. [测试覆盖](#testing)
11. [FAQ](#faq)
12. [方案对比（选型依据）](#comparison)

## 1. 背景与动机

CronPilot 原始模型使用 SQLite 的 `INTEGER PRIMARY KEY` 作为 `cron_infos` 和 `job_log` 的主键。SQLite 在不使用 `AUTOINCREMENT` 的情况下允许 ID 复用——当记录被删除并且有新插入时，已释放的小数字 ID 可能被重新分配。

由于 `job_health` 和 `job_log` 表通过 `cron_info_id` 关联 `cron_infos`，但**没有外键约束**，当 ID 被新任务复用时，新任务会继承旧任务的健康记录和执行日志，导致：

- 新任务创建后立即显示"健康异常"（实际是旧任务的失败记录）
- 执行记录混杂，无法区分新旧任务的日志

为了从根源消除 ID 复用，我们引入 50-bit 时间戳 ID 生成器，确保每个 ID 全局唯一且单调递增。

## 2. ID 结构

50-bit ID 结构（共 50 位）  
  ┌──────────────────────────────────────┬──────────────┐  
  │ 38-bit 秒时间戳（相对 Epoch） │ 12-bit 序列号 │  
  │ bit 49 ─────────────── bit 12 │ bit 11 ── bit 0 │  
  └──────────────────────────────────────┴──────────────┘  
   
  计算公式: **id = (seconds\_since\_epoch << 12) | sequence**

### 2.1 时间戳部分（高 38 位）

- **Epoch**：`2024-09-01 00:00:00 UTC`（Unix 时间戳 `1725148800`）
- **精度**：秒级
- **容量**：238 秒 ≈ 8,694 年（至公元 10718 年）

### 2.2 序列号部分（低 12 位）

- **范围**：0 ~ 4095
- **含义**：同一秒内的递增计数器
- **溢出策略**：等待下一秒（spin-wait，10ms 轮询间隔）

## 3. 参数规格

| 参数 | 值 | 说明 |
| --- | --- | --- |
| 总位数 | 50 bit | 最大值 1,125,899,906,842,623 |
| 十进制位数 | 12 ~ 15 位 | 当前生成约 12 位数字 |
| 时间戳位数 | 38 bit | 覆盖 ~8,700 年 |
| 序列号位数 | 12 bit | 每秒最多 4,096 个 ID |
| Epoch | 2024-09-01 00:00:00 UTC | Unix 1725148800 |
| JS 安全性 | ✅ 安全 | < 253 - 1 = 9,007,199,254,740,991 |
| 时间排序 | ✅ 支持 | ID 按生成时间自然排序 |
| 单调递增 | ✅ 保证 | 同进程内严格单调 |

**设计要点**：50-bit 上限 1.13×1015 远小于 JavaScript 的 `Number.MAX_SAFE_INTEGER`（9.0×1015），
确保前端 JSON 解析不会丢失精度，无需字符串化传输。

## 4. API 参考

### 4.1 `next_id()`

```
from datas.utils.id_generator import next_id

new_id = next_id()
# 返回: 260504313856 (示例，12 位十进制)
```

| 参数 | 说明 |
| --- | --- |
| （无参数） | — |
| 返回值 | 说明 |
| `int` | 全局唯一、单调递增的 50-bit 正整数 |
| 异常 | 说明 |
| `RuntimeError` | 系统时钟早于 Epoch（2024-09-01） |
| `OverflowError` | 生成的 ID 超过 JS MAX\_SAFE\_INTEGER（理论上不会发生） |

### 4.2 ID 结构解析（调试用）

```
def decompose_id(id_val):
    """将 50-bit ID 拆解为时间戳和序列号。"""
    seq = id_val & 0xFFF          # 低 12 位
    ts = id_val >> 12             # 高 38 位（秒偏移）
    epoch = 1725148800             # 2024-09-01 UTC
    unix_ts = ts + epoch
    return {
        'id': id_val,
        'timestamp_offset': ts,
        'sequence': seq,
        'unix_timestamp': unix_ts,
        'utc_time': datetime.utcfromtimestamp(unix_ts).isoformat() + 'Z',
    }

# 示例：
# decompose_id(260504313856)
# → {'timestamp_offset': 63600076, 'sequence': 0, 'unix_timestamp': 1788748876,
#    'utc_time': '2026-09-07T02:34:36Z'}
```

## 5. 集成方式

### 5.1 SQLAlchemy 模型集成

在模型定义中，将主键类型改为 `BigInteger` 并设置 `default=next_id`：

```
from datas.utils.id_generator import next_id
from app import db

class CronInfos(db.Model):
    __tablename__ = 'cron_infos'
    id: Mapped[int] = mapped_column(
        db.BigInteger, primary_key=True, default=next_id
    )
    # ...
```

### 5.2 当前已集成的模型

| 模型 | 表名 | 字段 | 说明 |
| --- | --- | --- | --- |
| `CronInfos` | cron\_infos | id | 任务主表，每条任务的唯一标识 |
| `JobLog` | job\_log | id | 执行日志，每条日志的唯一标识 |

**注意**：`job_health` 表的 `cron_info_id` 是外键引用 `cron_infos.id`，
无需修改，因为它存储的是 `cron_infos` 生成的 ID 值。

### 5.3 APScheduler 兼容

APScheduler 的 `job_id` 格式为 `cron_{cron_info_id}`（字符串），
50-bit ID 只是让数字部分变长（如 `cron_260504313856`），
APScheduler 对 job\_id 长度无限制，完全兼容。

## 6. 线程安全与并发

### 6.1 锁机制

使用 `threading.Lock()` 保护全局状态（`_last_ts` 和 `_seq`），
确保同进程内所有线程生成的 ID 严格单调递增且不重复。

### 6.2 同秒处理

```
同一秒内的多次调用：
  call 1 → (ts=63600076, seq=0) → id = 63600076 << 12 | 0
  call 2 → (ts=63600076, seq=1) → id = 63600076 << 12 | 1
  call 3 → (ts=63600076, seq=2) → id = 63600076 << 12 | 2
  ...
  call 4097 → seq 溢出 → spin-wait 至下一秒
```

### 6.3 多进程 / 分布式

**当前限制**：生成器为单进程内的全局单例，不含 worker\_id 字段。
对于 CronPilot 的典型部署（单进程 + gevent），这完全足够。
  
  
若未来需要多进程写入同一数据库，可扩展低位加入 worker\_id，或切换为数据库原生序列。

## 7. 数据库兼容性

| 数据库 | 列类型 | DDL 操作 | 说明 |
| --- | --- | --- | --- |
| SQLite | `INTEGER PRIMARY KEY` | 无需改动 | SQLite 的 INTEGER 底层已支持 8 字节存储，BigInteger 映射透明 |
| MySQL | `BIGINT NOT NULL AUTO_INCREMENT` | ALTER TABLE 升级 | `ensure_business_tables.py` 中 `_ensure_id_columns_bigint()` 自动迁移 |

**MySQL 迁移逻辑**（`scripts/ensure_business_tables.py`）：
启动时自动检测 `cron_infos.id` 和 `job_log.id` 列类型，
若不是 BIGINT 则执行 `ALTER TABLE ... MODIFY COLUMN ... BIGINT NOT NULL AUTO_INCREMENT`。
幂等操作，多次执行安全。

## 8. JavaScript 精度安全

JavaScript 的 `Number` 类型为 IEEE 754 双精度浮点数，安全整数范围为：

| 边界 | 值 | 十进制位数 |
| --- | --- | --- |
| `Number.MAX_SAFE_INTEGER` | 9,007,199,254,740,991 | 16 位 |
| 50-bit ID 最大值 | 1,125,899,906,842,623 | 16 位 |
| 当前生成的 ID | ~260,000,000,000 | 12 位 |

**结论**：50-bit ID 最大值仅为 JS 安全上限的 12.5%，
前端无需任何特殊处理（无需 BigInt、无需字符串化传输）。
`JSON.parse()` 直接解析的 ID 数值完全精确。

### 8.1 对比标准 Snowflake（64-bit）

| 方案 | 最大值 | JS 安全 | 前端处理 |
| --- | --- | --- | --- |
| 标准 Snowflake（64-bit） | ~1.8×1019 | ❌ 超限 | 须字符串化或 BigInt |
| CronPilot 50-bit | ~1.1×1015 | ✅ 安全 | 无需处理 |

## 9. 迁移与共存

### 9.1 新旧 ID 共存

升级后的行为：

- **新创建的任务/日志**：使用 50-bit ID（12+ 位数字，如 `260504313856`）
- **已存在的任务/日志**：保留原始小数字 ID（如 `1`、`14`）
- 两种 ID **互不冲突**——50-bit ID 的最小值远大于任何原始自增 ID

### 9.2 启动时清理

`ensure_business_tables.py` 在应用启动时自动执行：

1. **孤儿 job\_health 清理**：删除 `cron_info_id` 在 `cron_infos` 中不存在的记录
2. **MySQL BIGINT 迁移**：将 `cron_infos.id` 和 `job_log.id` 升级为 BIGINT（SQLite 无需操作）

### 9.3 回滚策略

若需要回滚到旧版本：

1. SQLite：无 DDL 变更，直接回退代码即可（新 ID 记录仍可读取）
2. MySQL：BIGINT 向下兼容 INT 范围的值，回退代码后旧版可读取所有记录（但不能创建新的大 ID 记录）
3. 如需完全回退：手动 `ALTER TABLE ... MODIFY COLUMN ... INT`（仅当无大 ID 记录时安全）

## 10. 测试覆盖

### 10.1 ID 生成器单元测试（`tests/test_id_generator.py`）

| # | 测试用例 | 验证内容 |
| --- | --- | --- |
| T1 | test\_returns\_positive\_integer | 返回正整数 |
| T2 | test\_ids\_are\_unique | 连续 1000 个 ID 无重复 |
| T3 | test\_ids\_are\_monotonically\_increasing | 严格单调递增 |
| T4 | test\_id\_below\_js\_max\_safe\_integer | < 9007199254740991 |
| T5 | test\_id\_is\_12\_or\_more\_digits | ≥ 12 位十进制 |
| T6 | test\_thread\_safety | 10 线程各生成 100 个 ID，无重复 |
| T7 | test\_sequence\_overflow\_waits | 同秒内超过 4096 个时等待下一秒 |
| T8 | test\_clock\_before\_epoch\_raises | 时钟回拨至 Epoch 前抛 RuntimeError |
| T9 | test\_overflow\_raises | 极端时间戳溢出抛 OverflowError |
| T10 | test\_decompose\_structure | ID 可正确拆解为时间戳 + 序列号 |

### 10.2 模型集成测试（`tests/test_job_health.py::TestNewIdStrategy`）

| # | 测试用例 | 验证内容 |
| --- | --- | --- |
| I1 | test\_cron\_infos\_gets\_50bit\_id | CronInfos 获得大数字 ID 且 JS 安全 |
| I2 | test\_job\_log\_gets\_50bit\_id | JobLog 获得大数字 ID |
| I3 | test\_new\_task\_no\_inherited\_health | 新任务无继承的 health 记录 |
| I4 | test\_two\_tasks\_get\_different\_ids | 两个任务获得不同且递增的 ID |

### 10.3 运行命令

```
# 仅运行 ID 生成器测试
python -m unittest tests.test_id_generator -v

# 仅运行 ID 策略集成测试
python -m unittest tests.test_job_health.TestNewIdStrategy -v

# 全量回归
bash scripts/cronpilot.sh test
```

## 11. FAQ

### Q1：为什么不用 UUID？

UUID（128-bit / 36 字符字符串）作为主键会显著增加索引体积和 JOIN 开销。
CronPilot 的数据规模不需要分布式唯一性，50-bit 整数在保证唯一的同时保持了整数主键的性能优势。

### Q2：为什么不用标准 64-bit Snowflake？

标准 Snowflake 最大值 ~1.8×1019 超过 JavaScript `MAX_SAFE_INTEGER`（9.0×1015），
前端 JSON 解析会丢失末尾精度，需要字符串化传输或引入 BigInt polyfill。
50-bit 方案完全避免了这个问题。

### Q3：4096 IDs/秒够用吗？

CronPilot 是定时任务调度系统，典型场景：

- 任务创建：手动操作，频率极低（<1/秒）
- 日志写入：与活跃任务数成正比，百级并发已是极端场景

4096/秒对于 CronPilot 绰绰有余。溢出时生成器自动等待下一秒，不会报错。

### Q4：系统时钟回拨怎么办？

生成器通过 `_last_ts` 追踪上次生成时的时间戳。如果当前时间 ≤ `_last_ts`（即时钟回拨），
序列号继续递增直到溢出，溢出后 spin-wait 直到时钟追上。
这保证了 ID 的单调性，但时钟长时间回拨（超过 1 秒）会导致短暂阻塞。

### Q5：Epoch 为什么选 2024-09-01？

选择一个接近项目启用时间的日期作为 Epoch，可以让时间戳部分的初始值较小（约 6 千万），
ID 以较短的数字（12 位）开始，随时间自然增长。比使用 Unix Epoch（1970-01-01）产生的
17 亿级初始值更紧凑。

### Q6：如何从 ID 中提取创建时间？

```
import datetime

def id_to_utc(id_val):
    ts_offset = id_val >> 12
    unix_ts = ts_offset + 1725148800  # Epoch
    return datetime.datetime.utcfromtimestamp(unix_ts)

# id_to_utc(260504313856)
# → datetime(2026, 9, 7, 2, 34, 36)
```

### Q7：新旧 ID 如何区分？

通过数值大小即可区分：旧自增 ID 通常 < 1000，而 50-bit ID 的最小值约为 260,000,000,000（12 位）。
业务逻辑无需区分——两种 ID 在数据库中以相同的整数类型存储，完全透明共存。

## 12. 方案对比（选型依据）

| 方案 | 位数 | 十进制长度 | JS 安全 | 每秒容量 | 时间跨度 | 适合场景 |
| --- | --- | --- | --- | --- | --- | --- |
| SQLite AUTOINCREMENT | 63 bit | 1~19 | ⚠️ 后期超限 | 无限制 | — | 单节点、ID 不会被复用 |
| 标准 Snowflake (64-bit) | 64 bit | 18~19 | ❌ | 4096/worker | ~69 年 | 分布式系统 |
| **CronPilot 50-bit（选定）** | 50 bit | 12~15 | ✅ | 4096 | ~8700 年 | 单进程、JS 友好 |
| 缩短版 53-bit | 53 bit | 13~16 | ✅（临界） | 4096 | ~8700 年 | 需更多位扩展 |
| UUID v4 | 128 bit | 36 char | ✅（字符串） | 无限制 | — | 分布式、索引代价可接受 |

**选型结论**：50-bit 方案在 JS 精度安全、ID 紧凑性、实现简洁性之间取得最佳平衡，
完全满足 CronPilot 单进程部署的需求，且无需前端任何适配。

## 附录：常量定义

```
# datas/utils/id_generator.py

_EPOCH      = 1725148800    # 2024-09-01 00:00:00 UTC
_SEQ_BITS   = 12            # 序列号位数
_SEQ_MASK   = 0xFFF         # (1 << 12) - 1 = 4095
_JS_MAX_SAFE = 9007199254740991  # 2^53 - 1
```

[文档索引](index.html) · [Markdown](CronPilot-50bit-ID生成器技术文档.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
