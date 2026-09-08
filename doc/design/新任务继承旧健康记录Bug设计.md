# OPT-P0-21：新任务继承旧健康记录 Bug 修复 + ID 策略升级设计

> HTML 版：[新任务继承旧健康记录Bug设计.html](新任务继承旧健康记录Bug设计.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# OPT-P0-21：新任务继承旧健康记录 Bug 修复 + ID 策略升级设计

**状态**：待确认   **创建**：2026-09-07   **更新**：2026-09-07   **优先级**：P0（数据准确性）

**目录**

1. [问题](#problem)
2. [根因](#root-cause)
3. [方案概览](#solution)
4. [核心修复：ID 策略升级](#layer2)
5. [范围](#scope)
6. [分批](#batches)
7. [验收](#acceptance)
8. [风险](#risk)
9. [明确不做](#excluded)

## 1. 问题

用户用 admintest 新建任务 `test123`（cron\_info\_id=14），创建后**立即**在任务中心显示健康度为"异常"（`health_status=failing`，`consecutive_failures=1969`），给用户造成新任务已经大量失败的错误印象。

**证据**：

- `test123` 创建时间：`2026-09-04 10:32:54 UTC`（created\_at=17885179746）
- cron\_info\_id=14 的第一条 job\_log：`2026-08-26 12:40:20 UTC` — **早于创建 9 天**
- 60 条 job\_log 中，**59 条属于旧任务**（创建前），仅 1 条属于 test123 本身
- job\_health 记录的 `consecutive_failures=1969` 几乎全部来自旧任务的累积

## 2. 根因

### 2.1 根因链

1. **SQLite ID 复用**：`INTEGER PRIMARY KEY`（无 `AUTOINCREMENT`）允许已删除行的 ID 被重新分配。历史 `db.drop_all()` 事件导致表重建后 ID 从 1 重新编号。
2. **无外键约束**：`job_health.cron_info_id` 和 `job_log.cron_info_id` 无 FK 关联 `cron_infos.id`，删除 cron\_infos 不会级联清理。
3. **APScheduler 独立存活**：`apscheduler_jobs` 使用独立 metadata，`db.drop_all()` 不影响它。存活的 APScheduler 任务持续执行并在重建的表中写入日志和健康数据。
4. **create\_cron() 无清理**：获取新 ID 后不检查该 ID 下是否存在残留数据。
5. **update\_job\_health() 继承旧记录**：`db.session.get(JobHealth, cron_info_id)` 命中旧记录，在旧 `consecutive_failures` 上 +1。

### 2.2 ID 复用机制详解

SQLite `INTEGER PRIMARY KEY` 的 ID 分配规则：取当前最大 ID + 1。当表被 `DROP` 再 `CREATE` 后，最大 ID 重置为 0，下一条记录从 1 开始。这意味着新任务可能获得与已不存在的旧任务相同的 ID，而旧任务的 `job_health` 和 `job_log` 数据仍然存在（因为这些表未被 DROP 或未级联删除）。

### 2.3 当前数据库受影响范围

| 类型 | 数量 | 说明 |
| --- | --- | --- |
| 孤儿 job\_health（cron\_infos 中无对应） | 3 条 | cron\_info\_id = 16, 19, 20 |
| failures 远超 logs 的 job\_health | 多数任务 | 如 id=12: 4688 failures vs 100 logs; id=14: 1969 failures vs 60 logs |
| 归属旧任务的 job\_log | 59 条（id=14） | 创建时间早于 test123 创建 9 天 |

## 3. 方案概览

采用**根因治理**策略：从 ID 生成机制上消除复用，而非在创建流程中补丁式清理。

| 措施 | 目的 | 手段 |
| --- | --- | --- |
| **核心修复** | 消除 ID 复用 | 业务表主键改为 50-bit 时间戳 ID |
| **存量修复** | 修复已受影响的数据 | 一次性脚本清理孤儿 health 记录 + test123 残留 |

**设计决策**：ID 复用是 Bug 的唯一根因。消除 ID 复用后，`create_cron()` 获取的 ID 保证是全新的、从未被任何 `job_health` 或 `job_log` 使用过的。因此**不需要**在创建流程中添加「清理残留数据」的逻辑——正常创建任务本来就不应该有残留数据需要清理。

## 4. 核心修复：ID 策略升级（50-bit 时间戳 ID）

### 4.1 选择理由

在评估了 7 种方案后，选择 **方案 B：50-bit 时间戳 ID** 作为统一 ID 策略：

| 属性 | 方案 B（选定） |
| --- | --- |
| 结构 | `38-bit 秒级时间戳` + `12-bit 序列号` = 50 bit |
| 自定义 Epoch | `2024-09-01 00:00:00 UTC`（Unix 1725148800） |
| ID 长度 | 12 位十进制（当前生成约 `260504313856`） |
| 可用年限 | ~8700 年（远超任何实际需求） |
| 吞吐量 | 4096 ID/秒（单实例绰绰有余） |
| JS 安全 | ✅ 完全安全（50-bit < 253 - 1） |
| 单调递增 | ✅ 同一秒内序列号递增，跨秒自然递增 |
| 实现复杂度 | 低 — 纯 Python，无外部依赖 |

### 4.2 ID 生成器实现

新增文件 `datas/utils/id_generator.py`：

```
"""50-bit 时间戳 ID 生成器（OPT-P0-21）。

结构：[38-bit 秒时间戳][12-bit 序列号]
- Epoch: 2024-09-01 00:00:00 UTC (Unix 1725148800)
- 38-bit 秒时间戳: 覆盖 ~8700 年
- 12-bit 序列号: 同秒最多 4096 个 ID
- 总 50 bit, 最大值 1125899906842623 (< JS MAX_SAFE_INTEGER 9007199254740991)
"""
import threading
import time

_EPOCH = 1725148800  # 2024-09-01 00:00:00 UTC
_SEQ_BITS = 12
_SEQ_MASK = (1 << _SEQ_BITS) - 1  # 4095

_lock = threading.Lock()
_last_ts = 0
_seq = 0

def next_id():
    """生成下一个全局唯一、单调递增的 50-bit ID。
    
    线程安全。同秒内序列号递增，序列号溢出时等待下一秒。
    
    Returns:
        int: 50-bit 整数，12 位十进制
    """
    global _last_ts, _seq
    with _lock:
        ts = int(time.time()) - _EPOCH
        if ts < 0:
            raise RuntimeError("System clock before ID epoch (2024-09-01)")
        if ts == _last_ts:
            _seq = (_seq + 1) & _SEQ_MASK
            if _seq == 0:
                # 同秒内 4096 个 ID 用尽，等待下一秒
                while int(time.time()) - _EPOCH <= _last_ts:
                    time.sleep(0.01)
                ts = int(time.time()) - _EPOCH
        else:
            _seq = 0
        _last_ts = ts
        return (ts << _SEQ_BITS) | _seq
```

### 4.3 模型层集成

修改需要新 ID 策略的模型，使用 `next_id` 作为 `default`：

```
# datas/model/cron_infos.py
from datas.utils.id_generator import next_id

class CronInfos(db.Model):
    __tablename__ = 'cron_infos'
    id: Mapped[int] = mapped_column(db.BigInteger, primary_key=True, default=next_id)
    ...
```

**受影响表清单（逐步迁移）**：

| 表 | 当前 PK 类型 | 迁移优先级 | 原因 |
| --- | --- | --- | --- |
| `cron_infos` | INTEGER | P0 — 本轮 | 直接触发 Bug 的表 |
| `job_log` | INTEGER | P0 — 本轮 | 高频写入表，受 ID 复用影响最大 |
| `job_health` | INTEGER (cron\_info\_id) | P0 — 本轮 | PK 为 cron\_info\_id，跟随 cron\_infos |
| `resource_group` | INTEGER | P1 — 随后 | 低频表，受影响风险低 |
| `tag` | INTEGER | P1 — 随后 | 同上 |
| `rbac_user` | INTEGER | P1 — 随后 | 同上 |
| `operation_log` | INTEGER | P2 — 可选 | 纯日志，ID 复用无业务影响 |
| `rbac_audit_log` | INTEGER | P2 — 可选 | 同上 |
| `task_tag` / `task_group` / `user_group` | INTEGER | P2 — 可选 | 关联表，业务逻辑不依赖 ID 值 |
| `rbac_registration_request` | INTEGER | P2 — 可选 | 临时数据 |

**本轮仅迁移 P0 表**（`cron_infos`、`job_log`），P1/P2 表可在后续版本逐步迁移。`job_health` 的 PK 是 `cron_info_id`（引用 `cron_infos.id`），跟随 `cron_infos` 自动适配。

### 4.4 数据库迁移策略

#### 4.4.1 SQLite 迁移

SQLite 的 `INTEGER PRIMARY KEY` 和 `BIGINT PRIMARY KEY` 在底层存储上完全等价（SQLite 使用动态类型，INTEGER 最大可存 8 字节）。因此 **SQLite 无需修改表结构**，仅需：

1. 修改 SQLAlchemy 模型的类型声明（`mapped_column(db.BigInteger, ...)`）
2. 添加 `default=next_id`
3. 现有数据的小 ID（1-14 等）继续有效，新创建的记录使用 50-bit ID

#### 4.4.2 MySQL 迁移（若使用）

MySQL 需要 `ALTER TABLE` 将 `INT` 列升级为 `BIGINT`：

```
-- ensure_business_tables.py 中添加
ALTER TABLE cron_infos MODIFY COLUMN id BIGINT NOT NULL AUTO_INCREMENT;
ALTER TABLE job_log MODIFY COLUMN id BIGINT NOT NULL AUTO_INCREMENT;
```

#### 4.4.3 新旧 ID 共存

旧记录保留原始小 ID，新记录使用 50-bit ID。二者在同一表中共存无任何冲突：

- 旧 ID: `1, 2, 3, ..., 14`
- 新 ID: `260504313856, 260504317952, ...`
- 50-bit ID 最小值远大于现有最大 ID，保证不冲突

### 4.5 前端影响

50-bit ID 在 JavaScript `Number` 范围内（`250 = 1125899906842624` < `253 - 1 = 9007199254740991`），因此：

- **无需**修改任何前端代码
- **无需**将 ID 作为字符串传输
- `JSON.parse()`、`$.data()`、`parseInt()` 均精确处理
- Jinja2 模板中的 `{{ cron.id }}` 无变化

### 4.6 APScheduler job\_id 兼容

APScheduler 的 `job_id` 为字符串格式 `"cron_14"`。改为 50-bit ID 后变为 `"cron_260504313856"`，仅长度增加，无功能影响：

- `scheduler.add_job(id=f"cron_{cif.id}", ...)` — 无需修改
- `scheduler.remove_job(f"cron_{cron_id}")` — 无需修改
- `cron_check()` 中的 `jid.startswith("cron_")` — 无需修改

### 4.7 ID 方案评估（决策记录）

以下是全部评估过的方案及其取舍，记录决策过程：

| 方案 | ID 长度 | JS 安全 | 可用年限 | 碰撞保证 | 结论 |
| --- | --- | --- | --- | --- | --- |
| A: 标准雪花 64-bit | 19 位 | ❌ | ~69 年 | ✅ 4M/秒 | ❌ 需改前端 |
| C: 53-bit 雪花 | 16 位 | ✅ | ~285 年 | ✅ 4096/秒 | ⚠️ 年限偏短 |
| **B: 50-bit 秒+序列（选定）** | **12 位** | **✅** | **~8700 年** | **✅ 4096/秒** | **✅ 最优平衡** |
| D: 纯秒时间戳 | 8 位 | ✅ | ~8.5 年 | ❌ 同秒冲突 | ❌ 不安全 |
| F: 毫秒时间戳 | 11 位 | ✅ | ~34 年 | ⚠️ 概率碰撞 | ❌ 不确定 |
| G: 秒+8bit 序列 | 11 位 | ✅ | ~8.5 年 | ✅ 256/秒 | ⚠️ 年限短 |
| H: 天数+日内序列 | 7 位 | ✅ | ~30 年 | ✅ 10000/天 | ⚠️ 实现复杂 |

**选择方案 B 的理由**：

1. 12 位十进制 ID 长度适中，日常使用无视觉负担
2. 8700 年可用期，永远不需要更换策略
3. 4096/秒吞吐远超 CronPilot 实际需求（任务创建 <1/分钟，日志 <100/秒）
4. 完全在 JS MAX\_SAFE\_INTEGER 范围内，零前端改动
5. 实现仅 40 行 Python，无外部依赖
6. SQLite 无需 DDL 迁移，MySQL 仅需 ALTER COLUMN

## 5. 范围

### 5.1 新增文件

| 文件 | 说明 |
| --- | --- |
| `datas/utils/id_generator.py` | 50-bit ID 生成器 |
| `tests/test_id_generator.py` | ID 生成器单元测试 |

### 5.2 修改文件

| 文件 | 变更 |
| --- | --- |
| `datas/model/cron_infos.py` | PK 类型 → `db.BigInteger` + `default=next_id` |
| `datas/model/job_log.py` | PK 类型 → `db.BigInteger` + `default=next_id` |
| `scripts/ensure_business_tables.py` | ① 孤儿 job\_health 清理 ② MySQL BIGINT 列迁移 |
| `tests/test_job_health.py` | 新增：新 ID 策略下创建任务不再继承旧数据 |
| `doc/design/新任务继承旧健康记录Bug设计.html` | 本文档 |
| `RELEASE_NOTES.md` | Bug 修复 + ID 策略升级条目 |

### 5.3 不改的文件

| 文件/领域 | 原因 |
| --- | --- |
| 前端 JS / 模板 | 50-bit ID 在 JS 安全范围内，无需改动 |
| APScheduler 相关代码 | job\_id 为字符串拼接，自动适配 |
| API 层（views.py） | ID 类型兼容，无需改动 |
| `job_health` 模型 | PK 为 `cron_info_id`（引用 cron\_infos.id），自动适配新 ID 值 |
| P1/P2 表模型 | 后续版本再迁移 |

## 6. 分批

| 批次 | 内容 | 验收 |
| --- | --- | --- |
| **B1: ID 生成器** | - 创建 `datas/utils/id_generator.py` - 创建 `tests/test_id_generator.py`（唯一性、单调性、线程安全、溢出等待） | `python -m unittest tests.test_id_generator -v` |
| **B2: 模型迁移** | - `cron_infos.py` / `job_log.py` PK 改 BigInteger + default=next\_id - `tests/test_job_health.py` 新增测试（新 ID 策略下不再继承旧数据） | `python -m unittest tests.test_job_health -v` + `cronpilot.sh test` |
| **B3: 存量数据修复 + ensure 脚本** | - `ensure_business_tables.py` 孤儿 health 清理 + MySQL BIGINT 迁移 - 修复 test123 残留数据 | SQL 查询验证 + 重启后 dashboard 正确 |
| **B4: 文档同步** | - `RELEASE_NOTES.md` 更新 - `html_docs_to_markdown.py --check` | 门禁通过 |

## 7. 验收

### 7.1 ID 生成器验收

1. `python -m unittest tests.test_id_generator -v` — 全部通过
2. 生成 1000 个 ID，验证：唯一、单调递增、≤ 12 位十进制、< 253

### 7.2 模型迁移验收

1. 创建新任务，确认 `cron_infos.id` 为 12 位数字（非自增小整数）
2. 确认新任务的 `job_health` 从零开始（`consecutive_failures=0`）
3. `python -m unittest tests.test_job_health -v` — 新增用例通过

### 7.3 存量数据验收

1. `SELECT * FROM job_health WHERE cron_info_id NOT IN (SELECT id FROM cron_infos)` → 0 行
2. `SELECT consecutive_failures, health_status FROM job_health WHERE cron_info_id = 14` → `0, unknown`（或无记录）
3. 重启后 dashboard 中 test123 显示 "N/A" 或正常健康度（非"异常"）

### 7.4 回归验收

1. `bash scripts/cronpilot.sh test` — 全部通过
2. `sqlite3 datas/job_log.sqlite ".tables"` — 确认表未被破坏
3. 重启后创建新任务 → 查看执行记录 → 筛选 → 无异常

## 8. 风险

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 旧代码通过 `int(cron_id)` 处理 ID | 低 | 50-bit ID 仍为 int，无兼容问题 |
| 新旧 ID 混在同一表中 | 极低 | 50-bit 最小值远大于现有最大 ID，不冲突 |
| ID 生成器时钟回拨 | 低 | 生成器内部用 `_last_ts` 保护，回拨时等待追上 |
| ensure\_business\_tables MySQL ALTER 锁表 | 中 | ALTER COLUMN 在现有数据量下（<20000 行）秒级完成 |
| test123 旧日志被删 | 无 | 这些日志本属于旧任务，删除是正确的 |

## 9. 明确不做

| 方案 | 不做原因 |
| --- | --- |
| 标准 64-bit 雪花 ID | 超出 JS MAX\_SAFE\_INTEGER，需改前端所有 ID 处理 |
| 添加 FK ON DELETE CASCADE | SQLite 需重建表（不支持 ALTER ADD CONSTRAINT），高风险 |
| 改用 AUTOINCREMENT | 同上；且 AUTOINCREMENT 只防止表最大 ID 后复用，不防表重建后重置 |
| UUID 字符串主键 | 需修改所有模型的 PK 类型、索引、关联查询，改动面过大 |
| 全表 P0-P2 一次性迁移 | 改动面大，应分步验证；P1/P2 表风险低可延后 |

[文档索引](index.html) · [Markdown](新任务继承旧健康记录Bug设计.md) · [BIGINT 迁移设计](时间戳迁移至BIGINT-UTC设计.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
