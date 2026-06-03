# Release Notes · CronPilot

> HTML 版：[RELEASE_NOTES.html](RELEASE_NOTES.html) · [文档索引](index.html) · [索引 Markdown](index.md)

# CronPilot Release Notes

v0.1.0 2026-05-29 · Phase A（P0）首发

[← 文档索引](index.html) ·
[Markdown 版](../RELEASE_NOTES.md)

首个版本：HTTP 定时回调调度、Web/API 管理、P0 安全与质量、技术文档与 Apache-2.0 许可。

## 回调与 API 协议

| 参数 / 接口 | 说明 |
| --- | --- |
| `cronpilot_log_id` | 每次触发的执行 UUID |
| `cronpilot_sign` | 回调签名（MD5） |
| `POST /api/cron/add_log` | 进度回传 |

```
GET /your/callback?cronpilot_log_id=<UUID>&cronpilot_sign=<MD5>
POST /api/cron/add_log  cronpilot_log_id=<UUID>&content=...
```

## 项目

- **CronPilot** 定时调度平台
- 回调 User-Agent：CronPilot
- `scripts/start_local.sh`、`conf.ini.example`

## Phase A（P0）

| ID | 内容 |
| --- | --- |
| P0-01 | SQL ORM 化 · `job_log_service` |
| P0-02 | 密码 pbkdf2 哈希 |
| P0-03 | SSRF 防护配置项 |
| P0-04 | JSON `errcode` 数字类型 |
| P0-05 | `cron_validator` + `cron_service` |

## 文档与许可

见 [文档索引](index.html)；许可 [LICENSE-AUDIT](LICENSE-AUDIT.html)（Apache-2.0）。

## 测试

```
python -m unittest tests.test_p0_phase_a tests.test_cronpilot_sign -v
```

## 配置新增

```
block_private_ip=1
url_allow_hosts=
url_ssrf_observe_only=0
```

## 对接检查

- 回调使用 `cronpilot_log_id`、`cronpilot_sign`
- `add_log` 回传进度
- SSRF 与密码哈希配置

## 后续版本

P1/P2 见 [PRD](产品优化需求-借鉴Plombery.html)；计划 `0.2.x` 对应 P1。

CronPilot · Release Notes · [Markdown](RELEASE_NOTES.md) · [索引](index.html)

---

[← 文档索引（HTML）](index.html) · [← 文档索引（Markdown）](index.md)
