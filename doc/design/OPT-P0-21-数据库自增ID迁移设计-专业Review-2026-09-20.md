# OPT-P0-21 数据库自增 ID 迁移设计专业 Review（2026-09-20）

> HTML 版：[OPT-P0-21-数据库自增ID迁移设计-专业Review-2026-09-20.html](OPT-P0-21-数据库自增ID迁移设计-专业Review-2026-09-20.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# OPT-P0-21：数据库自增 ID 迁移设计专业 Review

日期：2026-09-20 · 评估对象：[数据库自增 ID 写入机制切换设计](OPT-P0-21-数据库自增ID迁移设计-2026-09-20.html) · 结论：**方向合理，暂不具备直接实施条件**

## 1. 评估范围与方法

本次 Review 对照设计稿、当前 ORM 模型、ExecutionTracer 写入路径、SQLite 物理 schema 和迁移脚本，重点检查自增语义、历史 ID 容量、双后端 DDL、事务回滚、并发以及验收可证性。已核对 `cron_infos`、`job_log`、`job_log_events`，以及任务引用列的实际定义。

## 2. 总体结论

“不搬迁历史数据，只把后续新写入切换为数据库自增”是合理的产品和运维决策。当前 SQLite 物理 schema 中 `cron_infos.id` 与 `job_log.id` 已经是精确的 `INTEGER PRIMARY KEY`，它们原则上只需移除应用层默认值；但 `job_log_events.id` 仍是 `BIGINT PRIMARY KEY`，SQLite 无法仅靠 ALTER 将其变成 rowid 自增。若三类表都要求数据库自增，必须接受一次“值不变的 schema 重建”，否则只能把范围限定为任务主表。结论为**方向合理，但范围和 SQLite 物理约束必须先定稿**。

## 3. 阻断项（P0/P1）

1. **P0：SQLite 物理能力与目标范围存在冲突。** `cron_infos`/`job_log` 当前已具备 rowid 自增；`job_log_events` 的 `BIGINT PRIMARY KEY` 不具备该能力。设计必须二选一：只保证任务主键自增，或接受对事件表做一次不改值的 schema 重建。不能用“只改属性”掩盖 SQLite 的物理限制。
2. **P0：ExecutionTracer 仍会把 `id=None` 送进 Core INSERT。** 当前代码按模型所有列构造 `values`，再显式填入 `next_id()`。改造后若只删除赋值而保留 `id` 键，可能生成显式 NULL，无法触发自增。设计必须规定“主键键名不进入 values”，并验证写入后数据库确实分配 ID。
3. **P1：引用列策略仍需收敛。** 当前 SQLite 的多个任务引用列仍为 INTEGER。本轮不搬迁历史行，但必须明确目标自增值不会超出列范围；若结构确实不足，只做 DDL 扩容，不改写历史值。

## 4. 重要缺口（P1/P2）

- **主键范围边界不清。** 若目标只是“新任务自增”，只需改 `cron_infos`；若目标是彻底下线 `id_generator`，则必须覆盖 `job_log_events`，并接受一次值不变的 SQLite schema 重建。
- **SQLite 原子切换描述过于乐观。** 事件表重建会涉及外键、索引、唯一约束、触发器（如存在）和并发写入；必须先确定停写窗口或迁移锁策略，并在 `PRAGMA foreign_keys` 开启/关闭两种模式下验证。
- **MySQL 自增起点缺少精确契约。** 需要定义空表、最大值接近上限、手工插入高 ID、重复运行时 `AUTO_INCREMENT` 的行为；不能只写“设置为最大值以上”。
- **迁移“探针后回滚”不适合作为唯一验证。** 应使用独立事务/临时数据库做真实插入验收；生产迁移中插入再删除会污染审计、触发器或自增序列。
- **生成器测试与死代码策略缺失。** 下线生产调用后，现有 `tests/test_id_generator.py` 应删除、改为迁移回归，或明确其仅作为历史兼容测试；否则验收命令会继续允许生成器残留。

## 5. 建议修订后的实施契约

1. 先明确范围：若目标是“新任务自增”，只改 `cron_infos`；若目标是彻底下线 `id_generator`，则必须覆盖 `job_log_events`，并接受一次值不变的 SQLite schema 重建。
2. 为目标表定义 SQLite 与 MySQL 的 DDL 断言：SQLite 主键必须是精确 `INTEGER PRIMARY KEY`，MySQL 必须是 `BIGINT NOT NULL AUTO_INCREMENT`。
3. 为关键引用列建立最小检查清单：当前最大值、孤儿引用数量、目标范围；必要时只执行列类型 DDL 扩容，验证历史值集合完全不变。
4. ExecutionTracer 的 Core insert 明确构造白名单字段，绝不包含 `id`；如需拿到 ID，使用后端支持的 `RETURNING` 或 `lastrowid`，并分别验证 SQLite/MySQL。
5. 定义迁移锁/停写方案：迁移期间禁止任务创建、日志写入和事件写入，完成 schema 与探针后再恢复；否则“事务内切换”不能证明并发安全。
6. 把验收拆成结构断言、数据不变量、并发写入、重启恢复和失败回滚五类，每类都提供可执行命令与预期输出。

## 6. 推荐实施顺序

1. 先补设计契约和双后端 schema fixture，不改生产代码。
2. 再改模型和 tracer 写路径，先用 SQLite 内存库验证“不提供 id 时必得新 ID”。
3. 仅在选择覆盖 `job_log_events` 时实现 SQLite schema 重建；验证历史行值集合完全不变，不做 ID 重排。
4. 实现 MySQL DDL 与起点校正，再做两个进程并发插入。
5. 最后删除生成器生产代码和过时测试，运行完整门禁后再进入 4.1.0 发布评估。

## 7. 验收与风险判定

| 维度 | 当前设计 | Review 结论 |
| --- | --- | --- |
| 业务方向 | 下线应用层 ID，保留历史值 | 通过 |
| SQLite 自增 | 两张任务表已有 rowid；事件表仍为 BIGINT PK | 范围未定，需补充 |
| Core insert | 仅描述数据库回填 | 阻断，需明确省略 id |
| 引用兼容 | 不迁移历史行，仅需保证未来值不越界 | 可接受，需范围断言 |
| 回滚与并发 | 有快照和回滚原则 | 需增加停写/锁定边界 |
| 发布验收 | 有全量测试与文档门禁 | 需增加结构与双后端断言 |

**最终建议：**保留当前设计作为方向基线，补齐上述 P0/P1 后重新确认；在补齐前不得开始 Batch B，也不得删除 `id_generator.py`。本 Review 不构成代码实施授权。

[文档索引](../index.html) · [原设计](OPT-P0-21-数据库自增ID迁移设计-2026-09-20.html) · [Markdown](OPT-P0-21-数据库自增ID迁移设计-专业Review-2026-09-20.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
