# Release Notes · CronPilot

> HTML 版：[RELEASE_NOTES.html](RELEASE_NOTES.html) · [文档索引](index.html) · [索引 Markdown](index.md)

# CronPilot Release Notes

v0.1.1 2026-06-01 · 文档 / 部署 / 多版本 Python
 | 
v0.1.0 2026-05-29 · Phase A（P0）

[← 文档索引](index.html) ·
[Markdown 版（仓库根）](../RELEASE_NOTES.md) ·
[Markdown 版（doc）](RELEASE_NOTES.md)

## [Unreleased] · UI / 侧车 / Tier 2

**管理端 A′+B1（b105e47）：**执行记录单列两行 +「查看详情」；`job_log.http_status`；Cron 分钟 `*/1` 提示。  
**侧车 RFC-S.2：**`PyMySQL` 1.1.2。  
**Tier 2 RFC-2.1：**`gevent` 23.9.1 + `greenlet` 3.1.1（gunicorn 20 待 RFC-2.2）。  
**Tier 0/1 + RFC-S.1** 见下方；**无 API 协议变更。**

### 管理端 UI（A′ + B1）

| 变更 | 说明 |
| --- | --- |
| 执行记录列表 | 「返回的内容」一格两行：HTTP 状态 + 正文截断 |
| 查看详情 | 替代「更详细的执行记录」；展示 `job_log` 完整 HTTP 响应/异常 |
| `http_status` | `cron_do` 写入；SQLite `ensure_sqlite_tables.py` 补列 |
| Cron 分钟 B1 | 添加/编辑页：`*/1` = 每分钟 |

设计说明：[管理端 UI 优化设计](管理端UI优化设计.html)

### 侧车 PyMySQL（RFC-S.2）

| 变更 | 说明 |
| --- | --- |
| `PyMySQL` 1.1.2 | 0.10.1 → 1.1.2；`mysql+pymysql://` URL 不变 |

### Tier 2 · RFC-2.1（进行中）

| 变更 | 说明 |
| --- | --- |
| `gevent` 23.9.1 | 20.9.0 → 23.9.1；Py 3.8–3.11 |
| `greenlet` 3.1.1 | 与 gevent 23 配套 |
| 待续 | RFC-2.2 gunicorn、RFC-2.3 APScheduler |

### 依赖升级 Tier 0 / Tier 1 / 侧车 HTTP

**Tier 0：**退役 Flask-Script；迁移 CLI 改为 `flask db`（Python 3.11 可用）。  
**Tier 1：**SQLAlchemy 1.4.52 + Flask-SQLAlchemy 2.5.1；全站 `Model.query` 已迁移为 SA 1.4 推荐写法。  
**侧车 RFC-S.1：**`requests` 2.31.0、`urllib3` 1.26.19、`certifi` 2024.8.30。

### Tier 0

| 变更 | 说明 |
| --- | --- |
| Flask-Script 移除 | `manage.py` 注册 Click `db` 子命令 |
| `requirements-core.txt` | 锁定 `Flask-Migrate`、`alembic==1.4.3` |

### Tier 1

| 变更 | 说明 |
| --- | --- |
| SQLAlchemy 1.4.52 | 过渡版；全站 `Model.query` 已迁移 |
| Flask-SQLAlchemy 2.5.1 | SA 1.4 兼容（2.4.x URL API 不兼容） |
| `config.py` | `SQLALCHEMY_ENGINE_OPTIONS = {'future': False}` |
| 查询改写 | `job_log_service`、`main/views`、`cron_service`、`api/views`、`crons` |
| Docker 验收 | `write_sqlite_conf.py --container-paths`；`reset_datas_sqlite.sh` |
| 留 Tier 3 | `records` 裸 SQL（`CuBackgroundScheduler` 等） |

### 侧车 HTTP（RFC-S.1）

| 变更 | 说明 |
| --- | --- |
| `requests` 2.31.0 | 收敛已知 CVE；回归回调与 SSRF |
| `urllib3` 1.26.19 | 与 requests 2.31 配套 |
| `certifi` 2024.8.30 | CA 根证书同步 |

```
export FLASK_APP=manage:app
flask db migrate -m "描述"
flask db upgrade
```

详 [依赖升级 RFC](依赖升级RFC.html) Tier 0–1；本地试用 `conf.local.sqlite.example`。

---

## [0.1.1] — 2026-06-01

工程化与运维增强，**无 API 协议变更**。

### 文档与在线访问

| 变更 | 说明 |
| --- | --- |
| `/docs/` | 技术文档 HTML 与 `/docs/*.md` 同端口访问 |
| 双格式 | 各文档 HTML + Markdown；`doc/index.md` 索引 |
| 同步工具 | `scripts/html_docs_to_markdown.py --check` |
| 部署指南 | [非 Docker 部署指南](非Docker部署指南.html) |
| 协作规范 | `.cursor/rules/`、`AGENTS.md` |

### Python 3.8–3.11 自动匹配

- 自动探测并复用 `.venv-py*`，**无需**手动 `export PY=`
- 统一入口：`bash scripts/cronpilot.sh start|install|test|check`
- `requirements-core.txt` 用于本地与 CI 单测

```
bash scripts/cronpilot.sh start
bash scripts/cronpilot.sh test
```

### CI

- Docs HTML ↔ Markdown sync
- Unit tests 矩阵 3.8 / 3.9 / 3.10 / 3.11
- install-full（3.10 全量依赖）

### 升级（自 v0.1.0）

- `bash scripts/cronpilot.sh install`
- 改 HTML 后运行 `html_docs_to_markdown.py`
- 重启后访问 `/docs/`

---

## [0.1.0] — 2026-05-29 · Phase A（P0）首发

HTTP 定时回调调度、Web/API 管理、P0 安全与质量、技术文档与 Apache-2.0 许可。

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
bash scripts/cronpilot.sh test
```

## 后续版本

P1/P2 见 [PRD](产品优化需求-借鉴Plombery.html)；计划 `0.2.x` 对应 P1。

CronPilot · Release Notes · [Markdown](RELEASE_NOTES.md) · [索引](index.html)

---

[← 文档索引（HTML）](index.html) · [← 文档索引（Markdown）](index.md)
