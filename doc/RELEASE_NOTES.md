# Release Notes · CronPilot

> HTML 版：[RELEASE_NOTES.html](RELEASE_NOTES.html) · [文档索引](index.html) · [索引 Markdown](index.md)

# CronPilot Release Notes

v1.1.0 2026-07-14 · Scope 资源隔离 / 自助改密 / 编辑页精简
 | 
v1.0.0 2026-07-14 · RBAC / 生命周期 / operation\_log
 | 
v0.2.0 2026-06-10 · P1 可观测 / Tier 0–2 / UI
 | 
v0.1.1 2026-06-01 · 文档 / 部署 / 多版本 Python
 | 
v0.1.0 2026-05-29 · Phase A（P0）

[← 文档索引](index.html) ·
[Markdown 版（仓库根）](../RELEASE_NOTES.md) ·
[Markdown 版（doc）](RELEASE_NOTES.md)

## [Unreleased]

下一版计划见 [**交付状态与路线图**](交付状态与路线图.html)。

**维护约定：**未交付项进入开发时，在本节起草条目；发布时下沉到对应版本节。

## [1.1.0] — 2026-07-14 · Resource Scope、自助改密、编辑页精简

在 v1.0.0 RBAC 之上交付 **OPT-P2-12 资源隔离**，并完善账号自助与任务编辑体验。升级须**重启**。

| 库 | 升级动作 |
| --- | --- |
| **SQLite / MySQL** | 部署启动时 `ensure_sqlite_tables.py`（`run_production.sh` / `cronpilot.sh start`）：`create_all` 建缺失表（含业务组），并对已有 `cron_infos` / `job_log` 按需 `ALTER` 补列 |
| 其它方言 | 打印 `SKIP`；需自行维护 schema |

前提：MySQL 库与账号已存在且 `cron_db_url` 可连；脚本**不会**删表或改已有列类型。手写 DDL（设计 §十）仍作备用。`login_pwd` 仍仅空表种子。

### OPT-P2-12 · Resource Scope

| 变更 | 说明 |
| --- | --- |
| 数据 | `resource_groups` / `user_groups`；`cron_infos.scope_type`（默认 GLOBAL）/ `group_id`；SQLite/MySQL 均由 `ensure_sqlite_tables` 自动补齐 |
| 鉴权 | 列表 Scope 过滤 + 单资源 `authorize`；admin 绕过；越权 403 + `scope:deny` |
| 管理端 | `/rbac/groups*`（编码由名称自动生成）；用户绑组（非 admin 至少一组）；**任务添加**时可设作用域；日志继承可见性 |
| 非 admin 任务 | 强制 `GROUP`、仅可选本人所属组；不可设 GLOBAL |
| API | 首期未改（部署级 token 全库；S6 远期） |
| 测试 | `tests/test_rbac_scope.py` |

详设：[Scope 设计](资源隔离与Scope设计.html) · [落地路线](资源隔离落地路线.html)

### 自助修改密码

| 变更 | 说明 |
| --- | --- |
| 入口 | 导航「修改密码」→ `/rbac/password`（任意已登录角色；不需 `user:manage`） |
| 校验 | 当前密码；新密码 ≥6 位且不同于旧密码 |
| 会话 | 成功后清空会话，跳转登录页提示重新登录 |
| 审计 | `user:password` |
| 代改 | admin「用户管理 → 编辑」仍可改他人密码（不强制对方下线） |

### 任务编辑页精简

- 导航显示「任务编辑」（不再高亮「任务添加」）
- 不展示创建时间、上次编辑、作用域/可见范围；保存时作用域保持原值

## [1.0.0] — 2026-07-14 · 重大版本：多用户 RBAC、任务生命周期、操作审计

首个 **1.x** 里程碑：交付 **OPT-P2-10 RBAC v4**（三角色始终分权）、**OPT-P1-09 `operation_log`**、**LIFECYCLE-1/2**、**log\_id 必填**、**404 友好页**。升级须重启；登录为用户名+密码（空表种子 `admin`）。

### OPT-P2-10 · RBAC v4

| 阶段 | 状态 | 摘要 |
| --- | --- | --- |
| 1～5 | ✅ | 模型、核心、登录、导航、权限；无删除；`cron:retire` |
| 6a 用户管理 | ✅ | `/rbac/users*`；最后 admin 保护；Ajax 门禁 |
| 6b 审计 | ✅ | `/rbac/audit-logs`；中文动作 / 用户 ID 列 |
| 7 验收 | ✅ | 三角色真实登录矩阵 `TestRbacTriangularAcceptance` |

| 变更 | 说明 |
| --- | --- |
| 登录 / 密码 | 用户名+密码；空表种子 `admin`（初始密码=`login_pwd`）。日常改密：用户管理 → 编辑 → 新密码；有用户后改 `login_pwd` 无效。无忘记密码。（自助改密见 v1.1.0） |
| 默认行为 | 三角色分权**始终启用**；登录须 `rbac_users`；空表种子 `admin` |
| 分权 | 三角色**始终启用**；已移除旁路开关 `rbac_enable` |
| 冒烟 | `username=admin&password=…` |

详设：[RBAC v4](RBAC架构设计方案.html) · [落地路线](RBAC落地路线.html)

### OPT-P1-09 · 操作记录 `operation_log`

| 变更 | 说明 |
| --- | --- |
| 写入 | `create_cron` / `update_cron` / `toggle_status` / `retire_cron`（Web+API）；系统对账下线 |
| 管理页 | `/operation_log_list`；权限 `operation:read`（operator+admin）；RBAC「审计」为 `audit:read`（仅 admin） |
| 保留 | `operation_log_counts`（默认 5000）；`cron_del_operation_log` |

### 任务生命周期 / LIFECYCLE-2 / 404 / log\_id

| 变更 | 说明 |
| --- | --- |
| 无删除 | 下线替代删除；旧删除路由 410 |
| LIFECYCLE-2 | 强制备注；下线原因/时间；`created_at`/`updated_at` |
| 404 | 登录态/访客友好页；须重启后冒烟 |
| log\_id | 每次执行必有 `job_log.log_id` |

## [0.2.0] — 2026-06-10 · P1 可观测、依赖 Tier 0–2、管理端 UI

在 v0.1.1 上交付 **P1 OPT-P1-01/02**、**UI A′+B1+OPT-P1-07**、**Tier 0/1/2（RFC-2.1～2.5）**、侧车 HTTP/PyMySQL。**无 API 协议变更。**

**升级要点：**Docker 镜像 Python **3.10**；`fail_on_http_4xx_5xx` 新配置；勿用 `conf.ci.ini` 作生产挂载。

### 管理端 UI（A′ + B1）

| 变更 | 说明 |
| --- | --- |
| 执行记录列表 | 「返回的内容」一格两行：HTTP 状态 + 正文截断 |
| 查看详情 | 替代「更详细的执行记录」；展示 `job_log` 完整 HTTP 响应/异常 |
| `http_status` | `cron_do` 写入；SQLite `ensure_sqlite_tables.py` 补列 |
| Cron 分钟 B1 | 添加/编辑页：`*/1` = 每分钟 |

设计说明：[管理端 UI 优化设计](管理端UI优化设计.html)

### 管理端 UI · OPT-P1-07 导航栏 partial

| 变更 | 说明 |
| --- | --- |
| `_admin_nav.html` | 统一 5 项 Tab：任务列表 / 任务添加 / 任务执行记录 / API文档 / 退出 |
| 修复 | `cron_add`、`cron_edit` 此前仅 2 项导航，进入添加页后其余 Tab 消失 |
| 引用页 | `cron_list`、`cron_add`、`cron_edit`、`job_log_all_list`、`api_doc` |

设计说明：[产品 PRD OPT-P1-07](产品优化需求-借鉴Plombery.html) · [技术方案与前端设计](技术方案与前端设计.html)

### P1 可观测（OPT-P1-01/02）

| 变更 | 说明 |
| --- | --- |
| `status` / `fail_reason` | `success` / `fail` / `error` + 短标签 |
| `fail_on_http_4xx_5xx` | 默认 `1`；4xx/5xx 记 fail 并告警 |
| UI | A′ 列表增加状态徽章；详情展示 `fail_reason` |

设计说明：[P1 可观测优化设计](P1可观测优化设计.html)

### 侧车 PyMySQL（RFC-S.2）

| 变更 | 说明 |
| --- | --- |
| `PyMySQL` 1.1.2 | 0.10.1 → 1.1.2；`mysql+pymysql://` URL 不变 |

### Tier 2 · RFC-2.1 / RFC-2.2 / RFC-2.3

| 变更 | 说明 |
| --- | --- |
| `gevent` 23.9.1 | 20.9.0 → 23.9.1；Py 3.8–3.11 |
| `greenlet` 3.1.1 | 与 gevent 23 配套 |
| `gunicorn` 22.0.0 | 20.0.4 → 22.0.0；gevent worker + Docker 金路径已验收 |
| `APScheduler` 3.10.4 | 3.6.3 → 3.10.4；`SQLAlchemyJobStore` + SA 1.4；Docker compose 冒烟通过 |
| **RFC-2.4** | Docker **3.10** + `install-full` matrix **3.9 / 3.10 / 3.11** |

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
