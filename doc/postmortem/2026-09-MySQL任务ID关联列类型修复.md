# MySQL 任务 ID 关联列类型修复

> HTML 版：[2026-09-MySQL任务ID关联列类型修复.html](2026-09-MySQL任务ID关联列类型修复.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# MySQL 任务 ID 关联列类型修复复盘

日期：2026-09-21

## 1. Bug 定位

任务主键切换为 BIGINT 后，部分关联列仍为 INT，可能导致高位任务 ID 写入溢出。

## 2. 根因

主键迁移只覆盖了三个主键列，未建立任务 ID 引用列的完整清单，ORM 类型与启动迁移也未形成统一契约。

## 3. 测试漏洞

测试只验证主键自增，没有验证 MySQL 方言下所有关联列的类型。

## 4. 修复

将 job\_log、job\_health、job\_log\_events、task\_groups、task\_tags、operation\_log 中的任务 ID 引用统一为 BIGINT；启动迁移补齐旧库列类型并对关键 DDL 失败 fail-closed。

## 5. 防护测试

新增所有引用列编译为 MySQL BIGINT 的专项测试；数据库自增与迁移专项 14 项通过，Ruff 通过。

## 6. 同类排查

全仓搜索 task\_id、cron\_info\_id、cron\_id、target\_id，确认模型和迁移目标一致。

## 7. 预防方案

新增任务主键时必须同步更新“引用列清单”和 MySQL 方言测试；迁移脚本对关键类型变更不得仅告警。验证：`.venv-py311/bin/python -m unittest tests.test_id_autoincrement tests.test_ensure_business_tables -v`。

[文档索引](index.html) · [Markdown](2026-09-MySQL任务ID关联列类型修复.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
