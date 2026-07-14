# CronPilot Release Notes

本文档记录 **CronPilot** 版本变更。  
HTML 版：[doc/RELEASE_NOTES.html](doc/RELEASE_NOTES.html)

---

## [Unreleased]

下一版计划见 **[交付状态与路线图](doc/交付状态与路线图.html)**。建议下一优化：**OPT-P1-09** 管理操作审计 `operation_log`（与 `/rbac/audit-logs` 分表）。

**维护约定**：未交付项进入开发时，在本节起草条目；发布时下沉到对应版本节，并同步更新交付状态总览页。

---

## [0.3.0] — 2026-07-14 · RBAC v4、任务生命周期、可追溯执行记录

交付 **OPT-P2-10 RBAC v4**（含用户管理/审计）、**LIFECYCLE-1/2 无删除与元数据**、**执行记录 log_id 必填**、**404 友好页**。打 tag 前请再跑全量验收。

### OPT-P2-10 · RBAC v4

| 阶段 | 状态 | 交付摘要 |
|------|------|----------|
| 1 数据层 | ✅ | `rbac_users` / `rbac_audit_logs`；`rbac_enable`；`ensure_sqlite_tables` 建表 + 种子 |
| 2 RBAC 核心 | ✅ | `app/rbac/`：policy、services、`make_has_perm`、`require_permission` |
| 2.5 登录身份 | ✅ | `/rbac/login`；用户名+密码必填；空表种子 `admin`（密码=`login_pwd`）；**无** `legacy_admin` |
| 3 导航迁移 | ✅ | `rbac/_nav.html` + `has_perm` 菜单裁剪 |
| 4+5 权限 | ✅ | `@require_permission`；**无删除**；`cron:retire` |
| 6a 用户管理 | ✅ | `/rbac/users*`；最后一名 admin / 禁停用自己；Ajax 表单门禁 |
| 6b 审计列表 | ✅ | `/rbac/audit-logs`；中文动作/用户 ID 列 |
| 7 验收 | ✅ | 三角色真实登录矩阵单测 `TestRbacTriangularAcceptance` |

设计说明：[doc/RBAC架构设计方案.html](doc/RBAC架构设计方案.html) · [doc/RBAC落地路线.html](doc/RBAC落地路线.html)

| 变更 | 说明 |
|------|------|
| 默认行为 | `rbac_enable=0`：权限旁路；登录仍须 `rbac_users`；空表种子 `admin` |
| 登录入口 | `/rbac/login`；`/check_pass` 仅转发；冒烟 `username=admin&password=…` |
| 未登录跳转 | 仅受保护路由；`/docs/*`、`/api/*` 独立 |
| `cron:write` / `cron:retire` / `log:read` | 写=启停编辑；下线仅 admin；**废弃** delete |
| 测试 | `tests/test_rbac_phase.py`、`tests/test_ajax_form_guard.py` 并入 `cronpilot.sh test` |

### RBAC 6a · `/rbac/users`

| 变更 | 说明 |
|------|------|
| 路由 | 列表 / 添加 / 编辑；`user:manage` |
| 安全 | 无物理删除；禁停用自己与最后一名启用中 admin |
| 表单 | `js-ajax-submit`；非 Ajax 成功 302 |
| 防再发 | `test_ajax_form_guard`；去掉空壳 `js-ajax-form` |

### RBAC 6b · `/rbac/audit-logs`

| 变更 | 说明 |
|------|------|
| 路由 | 只读分页；`audit:read` |
| 展示 | 用户 ID 独立列；动作/结果中文；说明列可读文案 |
| 分工 | ≠ OPT-P1-09 `operation_log` |

### 任务生命周期 · 无删除

| 变更 | 说明 |
|------|------|
| 暂停 vs 下线 | `status=0` 可恢复；`status=-1` 不可逆终点 |
| 无人工删除 | 旧删除路由 410；同类需求新建 |
| 设计 | [任务生命周期与无删除](doc/任务生命周期与无删除设计.html) |

### LIFECYCLE-2 · 元数据与下线可追溯

| 变更 | 说明 |
|------|------|
| `task_keyword` | 新建/编辑必填，VARCHAR(500) |
| `created_at` / `updated_at` | 创建一次；仅配置编辑刷新 updated |
| `retire_reason` / `retired_at` | 人工必填；系统固定文案；无 `retired_by` |
| 设计 | [生命周期 §四](doc/任务生命周期与无删除设计.html#lifecycle-2) |

### 管理端 · 404 友好页（R2.5）

| 变更 | 说明 |
|------|------|
| `errors/404*.html` | 登录态/访客分流；HTTP 404 |
| `smoke_http_not_found` | 黄金路径断言；改错误页后须重启 |

### 执行记录 log_id 必填

| 变更 | 说明 |
|------|------|
| `cron_do` / `_save_job_log` | 每次执行必有 `job_log.log_id`（UUID） |

### 升级说明（自 v0.2.0）

1. 安装/重启：`bash scripts/cronpilot.sh restart`（模板与鉴权变更须重启）。
2. Web 登录改为 **用户名 + 密码**；空库自动种子 `admin`（密码=`login_pwd`）。
3. 可选：`rbac_enable=1` 启用三角色；`0` 仍须账号登录但权限旁路。
4. 验证：`bash scripts/cronpilot.sh test`；`bash scripts/verify_golden_path.sh`。

---

## [0.2.0] — 2026-06-10 · P1 可观测、依赖 Tier 0–2、管理端 UI

在 v0.1.1 基础上交付 **P1 可观测（OPT-P1-01/02）**、**管理端 UI（A′+B1、OPT-P1-07）**、**依赖升级 Tier 0 / Tier 1 / Tier 2（RFC-2.1～2.5）** 与侧车安全补丁。**无 API 协议变更**（仍为 `cronpilot_log_id` / `cronpilot_sign` / `add_log`）。

### 版本摘要

| 类别 | 已交付 |
|------|--------|
| **P1 可观测** | `job_log.status` / `fail_reason`；`fail_on_http_4xx_5xx`；列表状态徽章 |
| **管理端 UI** | 执行记录 A′（单列两行 + 查看详情）；Cron 分钟 B1 提示；`_admin_nav.html` 五 Tab 导航 |
| **依赖 Tier 0** | `flask db` 替代 Flask-Script |
| **依赖 Tier 1** | SQLAlchemy 1.4.52 + Flask-SQLAlchemy 2.5.1；`Model.query` 全站迁移 |
| **依赖 Tier 2** | gevent 23.9.1、gunicorn 22.0.0、APScheduler 3.10.4；Docker **Python 3.10**；install-full CI matrix 3.9–3.11 |
| **侧车** | requests/urllib3/certifi 安全线；PyMySQL 1.1.2 |
| **Docker 运维** | `verify_docker_compose.sh` 黄金路径；`check_conf_production.py` 拒绝 `:memory:`；SQLite conf 生成指引 |

### 升级说明（自 v0.1.1）

1. `bash scripts/cronpilot.sh install` 或 `pip install -r requirements.txt`（依赖版本见上表）。
2. **Docker**：`docker compose build --no-cache && docker compose up -d`（镜像 Python **3.9 → 3.10**）。
3. **conf.ini**：勿用 `conf.ci.ini` 挂载生产；试用请 `python3 scripts/write_sqlite_conf.py --out conf.ini --datas-dir datas --container-paths`。
4. SQLite 已有库：启动时 `ensure_sqlite_tables.py` 补 `http_status`、`status`、`fail_reason` 列。
5. 新配置项：`fail_on_http_4xx_5xx=1`（见 `conf.ini.example`）。
6. 验证：`bash scripts/cronpilot.sh test`；Docker 建议 `bash scripts/verify_docker_compose.sh`。


| 变更 | 说明 |
|------|------|
| 执行记录列表 | 「返回的内容」一格两行：① HTTP 状态/异常 ② 响应正文截断；**不加新列** |
| 查看详情 | 替代原「更详细的执行记录」；弹窗展示 `job_log` 完整 HTTP 响应/异常（非空白 add_log 表） |
| `job_log.http_status` | `cron_do` 成功时写入状态码；SQLite 已有库经 `ensure_sqlite_tables.py` ALTER 补列；**不新增索引** |
| Cron 分钟提示 B1 | 添加/编辑任务页分钟字段行尾灰字：`*/1` = 每分钟，`1` = 每小时第 1 分 |
| 测试 | `tests/test_job_log_display.py` 并入 `bash scripts/cronpilot.sh test` |

设计说明：[doc/管理端UI优化设计.html](doc/管理端UI优化设计.html)

### 管理端 UI · OPT-P1-07 导航栏 partial

| 变更 | 说明 |
|------|------|
| `_admin_nav.html` | 统一 5 项 Tab：任务列表 / 任务添加 / 任务执行记录 / API文档 / 退出 |
| 修复 | `cron_add`、`cron_edit` 此前仅 2 项导航，进入添加页后其余 Tab 消失 |
| 引用页 | `cron_list`、`cron_add`、`cron_edit`、`job_log_all_list`、`api_doc` |

设计说明：[doc/产品优化需求-借鉴Plombery.html#opt-p1-07](doc/产品优化需求-借鉴Plombery.html) · [doc/技术方案与前端设计.html](doc/技术方案与前端设计.html)

### P1 可观测 · OPT-P1-01/02（执行 status + HTTP 失败规则）

| 变更 | 说明 |
|------|------|
| `job_log.status` | `success` / `fail` / `error`；`cron_do` 综合判定后写入 |
| `job_log.fail_reason` | 短标签：`http_5xx`、`keyword`、`timeout` 等 |
| `fail_on_http_4xx_5xx` | `conf.ini` 默认 `1`；4xx/5xx 记 fail 并走统一告警 |
| UI | A′ 列表第一行增加状态徽章；详情页展示 `fail_reason` |
| 测试 | `tests/test_job_log_outcome.py` 并入 `bash scripts/cronpilot.sh test` |

设计说明：[doc/P1可观测优化设计.html](doc/P1可观测优化设计.html)

### 依赖升级 · Tier 0

| 变更 | 说明 |
|------|------|
| 退役 Flask-Script | `manage.py` 改用 Flask 内置 `flask db`（Click 注册 Migrate 子命令） |
| `requirements.txt` | 移除 `Flask-Script==2.0.6` |
| `requirements-core.txt` | 增加 `Flask-Migrate`、`alembic==1.4.3` 等迁移依赖 |

用法：

```bash
export FLASK_APP=manage:app
flask db migrate -m "描述"
flask db upgrade
```

试用配置可 `cp conf.ci.ini conf.ini`（SQLite 内存库，仅单测）；本地试用见 `conf.local.sqlite.example`。

### 依赖升级 · Tier 1

| 变更 | 说明 |
|------|------|
| SQLAlchemy 1.3.19 → **1.4.52** | 过渡版；全站 `Model.query` 已迁移为 SA 1.4 推荐写法 |
| Flask-SQLAlchemy 2.4.4 → **2.5.1** | SA 1.4 兼容（2.4.x 与 1.4 URL API 不兼容） |
| `config.py` | `SQLALCHEMY_ENGINE_OPTIONS = {'future': False}` |
| `app/crons.py` | `execute(text(...))`；`session.get` / `scalars(select(...))` |
| `app/services/job_log_service.py` 等 | `delete()` / `scalars()` 替代 `Model.query` |
| Docker 验收 | `write_sqlite_conf.py --container-paths`；`reset_datas_sqlite.sh` 仅清 `*.sqlite` |

**SA 1.4 查询改写 backlog：**

| 模块 | 模式 | 优先级 |
|------|------|--------|
| `app/crons.py` | 裸 `execute` 字符串 | ✅ Tier 1 已改 |
| `app/crons.py` | `Model.query`（`cron_check`/`cron_del_job_log` 等） | ✅ Tier 1 已改 |
| `app/services/job_log_service.py` | `Model.query` | ✅ Tier 1 已改 |
| `app/main/views.py` | `Model.query` / `paginate` | ✅ Tier 1 已改 |
| `app/services/cron_service.py` | `Model.query` | ✅ Tier 1 已改 |
| `app/api/views.py` | `Model.query` | ✅ Tier 1 已改 |
| `app/crons.py` / `CuBackgroundScheduler.py` | `records` 裸 SQL | Tier 3 与 SQL 整改一并 |

新代码（RBAC、operation_log）禁止新增裸字符串 `execute`。

### 依赖升级 · Tier 2（RFC-2.1 ✓ · RFC-2.2 ✓ · RFC-2.3 ✓ · RFC-2.4 ✓ · RFC-2.5 ✓）

**Tier 2 已全部交付**（gevent / gunicorn / APScheduler / Docker Py 3.10 / CI matrix）；Python **3.8–3.11** 规则经 RFC-2.5 签收仍有效，3.12+ 待 Tier 3+ 评估。

| 变更 | 说明 |
|------|------|
| `gevent` 20.9.0 → **23.9.1** | 支持 Python 3.8–3.11；Docker 金路径（Py 3.10 + gunicorn gevent worker）已验收 |
| `greenlet` 0.4.17 → **3.1.1** | 与 gevent 23 配套；修复 Py 3.11 `SystemError` 类问题 |
| `gunicorn` 20.0.4 → **22.0.0** | gevent worker 冒烟通过；Docker 金路径（`verify_cronpilot_docker_mac.sh` full）已验收；`gun.py` 无需改动 |
| `APScheduler` 3.6.3 → **3.10.4** | `SQLAlchemyJobStore` + SA 1.4 联调；`CuBackgroundScheduler` 无需改；Docker compose 冒烟通过 |
| `install_production_deps.sh` | 移除 gevent 20 分步安装特例，统一 `pip install -r requirements.txt` |
| **RFC-2.4** Docker **3.10** + `install-full` matrix **3.9 / 3.10 / 3.11** | CI 全量依赖安装 + gevent/gunicorn 导入冒烟 |

### 依赖升级 · 侧车 PyMySQL（RFC-S.2）

| 变更 | 说明 |
|------|------|
| `PyMySQL` 0.10.1 → **1.1.2** | 1.x 维护线末版，兼容 Python 3.8–3.11；SQLAlchemy `mysql+pymysql://` 无需改 URL |
| 验收 | `bash scripts/cronpilot.sh test`；Docker compose 构建与健康检查 |

### 依赖升级 · 侧车 HTTP 安全补丁

| 变更 | 说明 |
|------|------|
| `requests` 2.24.0 → **2.31.0** | 收敛已知 CVE；回归 `cron_do` 回调与 SSRF 校验 |
| `urllib3` 1.25.10 → **1.26.19** | 与 requests 2.31 配套（1.26 末代安全线） |
| `certifi` 2020.6.20 → **2024.8.30** | CA 根证书同步 |

验收：`bash scripts/cronpilot.sh test`、`bash scripts/verify_golden_path.sh`。

---

## [0.1.1] — 2026-06-01 · 文档、部署与多版本 Python

在 v0.1.0 基础上的工程化与运维增强，**无 API 协议变更**。

### 文档与在线访问

| 变更 | 说明 |
|------|------|
| `/docs/` 路由 | Flask 提供 `doc/` 静态 HTML，与管理端同端口远程访问 |
| HTML + Markdown | 各技术文档双格式；`doc/index.md` 索引表 |
| 同步脚本 | `scripts/html_docs_to_markdown.py`（`--check` 供 CI 校验） |
| 非 Docker 部署指南 | `doc/非Docker部署指南.html` / `.md`；README 部署章节 |
| Cursor 规范 | `.cursor/rules/`、`AGENTS.md` 固化协作与实现约定 |

在线示例：`http://<host>:5860/docs/`、`/docs/index.md`

### Python 3.8–3.11 自动匹配

| 变更 | 说明 |
|------|------|
| 自动探测 | `scripts/lib/python.sh`：优先复用 `.venv-py*`，否则按 3.11→3.8 选用 |
| 统一入口 | `scripts/cronpilot.sh`（`start` / `install` / `test` / `check` / `exec`） |
| 核心依赖 | `requirements-core.txt`（本地与单测，含 PyMySQL；无 gevent） |
| 兼容 macOS | 启动脚本兼容 bash 3.2，**默认无需** `export PY=` |

```bash
bash scripts/cronpilot.sh start    # 自动匹配 Python，无需指定版本
bash scripts/cronpilot.sh test
```

生产全量依赖仍用 `requirements.txt`（Gunicorn + gevent）。

### Linux 安装与运行（Ubuntu + CentOS 7/8）

| 脚本 / 文档 | 说明 |
| --- | --- |
| `scripts/install_linux.sh` | 统一入口，自动识别发行版 |
| `scripts/install_ubuntu.sh` / `install_centos.sh` | 分平台一键安装 |
| `scripts/bootstrap_venv.sh` | 自动 `.venv-py*` + 核心依赖 |
| `scripts/install_production_deps.sh` | 同一 venv 安装 Gunicorn + gevent |
| `scripts/run_production.sh` | 生产启动（无需手动 activate） |
| `scripts/docker/verify_all.sh` | Docker 验收 Ubuntu / Rocky8 / CentOS7 |
| [INSTALL.md](../INSTALL.md) | 安装速查（MySQL 生产 / SQLite 试用） |

```bash
sudo bash scripts/install_linux.sh --production
bash scripts/run_production.sh
```

### Docker 安装验收 CI

- 工作流：`.github/workflows/docker-install-verify.yml`
- 矩阵构建验证 venv + gunicorn + `/docs/`（SQLite 试用路径）

### CI（GitHub Actions）

| 工作流 | 说明 |
|--------|------|
| Docs HTML ↔ Markdown sync | PR 校验 `doc/*.md` 与 HTML 一致 |
| Unit tests | 矩阵 **3.8 / 3.9 / 3.10 / 3.11** + `requirements-core.txt` |
| install-full | 矩阵 **3.9 / 3.10 / 3.11** 安装完整 `requirements.txt` 并导入 gevent/gunicorn |
| Docker install verify | 矩阵 Ubuntu / Rocky8 / CentOS7 完整安装 + venv + gunicorn |

### 升级说明（自 v0.1.0）

- 拉取代码后：`bash scripts/cronpilot.sh install` 或 `bash scripts/install_core_deps.sh`
- 修改 `doc/*.html` 后执行：`python scripts/html_docs_to_markdown.py`
- 远程文档：重启 Gunicorn 后访问 `/docs/`

---

## [0.1.0] — 2026-05-29 · Phase A（P0）首发

首个版本：HTTP 定时回调调度、Web/API 管理、P0 安全与质量能力、技术文档与 Apache-2.0 许可。

### 项目定位

- **CronPilot** — 中心化 HTTP 定时回调调度台。
- Web 管理端：**CronPilot 定时调度平台**。
- 回调 HTTP `User-Agent`：`CronPilot`。
- 本地开发：`bash scripts/cronpilot.sh start`（v0.1.1+ 自动匹配 Python）；配置示例：`conf.ini.example`。

### 回调与 API 协议

| 参数 / 接口 | 说明 |
|-------------|------|
| `cronpilot_log_id` | 每次触发生成的执行 UUID（query） |
| `cronpilot_sign` | 回调签名字段（MD5，见 `get_cronpilot_sign`） |
| `POST /api/cron/add_log` | 长任务进度回传，必传 `cronpilot_log_id`、`content` |

**回调示例：**

```http
GET https://your-service/callback?cronpilot_log_id=<UUID>&cronpilot_sign=<MD5>
```

**进度回传：**

```http
POST /api/cron/add_log
cronpilot_log_id=<UUID>&content=...
```

验签：query 参数按 key ASCII 排序，拼接 `key=value&&...&&api_key=` 后 MD5。  
执行记录 UUID 存于 `job_log.log_id`。

---

### Phase A（P0）— 安全与基础质量

#### OPT-P0-01 · SQL 参数化

- 删除定时任务时清理 `job_log`：ORM `JobLog.query.filter(...).delete()`。
- 定时清理超限日志：`trim_job_logs_for_cron()`（ORM），消除 SQL 拼接。
- 新增：`app/services/job_log_service.py`。

#### OPT-P0-02 · 管理端密码哈希

- `app/auth/password.py`：支持明文（兼容）与 `pbkdf2` 哈希。
- `scripts/hash_login_password.py` 生成哈希写入 `login_pwd`。

#### OPT-P0-03 · 回调 URL SSRF 防护

- `app/services/url_security.py`。
- 配置：`block_private_ip`、`url_allow_hosts`、`url_ssrf_observe_only`。
- 保存任务与 `cron_do` 执行前校验。

#### OPT-P0-04 · 统一 JSON 契约

- `json_response()`，`errcode` 为 int。
- 修复 `requests.js` 中 `errcode === 0` 判断。

#### OPT-P0-05 · Cron 校验与任务写入统一

- `cron_validator.py` + `cron_service.py`，Web / API 单一路径。
- 消除 `main/views` 与 `api/views` 重复校验逻辑。

---

### 文档

| 文档 | 说明 |
|------|------|
| `doc/index.html` | 文档索引 |
| `doc/项目总览与技术文档.html` | 项目入口 |
| `doc/架构设计文档.html` | 架构与部署 |
| `doc/详细技术方案.html` | 功能与 API |
| `doc/产品优化需求-借鉴Plombery.html` | P0/P1/P2 PRD |
| `doc/P0测试用例与验收手册.html` | 测试与冒烟 |
| `doc/LICENSE-AUDIT.html` | 许可审计 |

---

### 许可与合规

- **Apache License 2.0**（`LICENSE`、`NOTICE`、`THIRD_PARTY_NOTICES.md`）。
- 详见 [doc/LICENSE-AUDIT.html](doc/LICENSE-AUDIT.html)。

---

### 测试

```bash
bash scripts/cronpilot.sh test
# 或: python -m unittest tests.test_p0_phase_a tests.test_cronpilot_sign -v
```

| 套件 | 说明 |
|------|------|
| `tests/test_p0_phase_a.py` | SSRF、密码、校验、JSON 等 |
| `tests/test_cronpilot_sign.py` | 签名函数 |

---

### 配置（新增项）

```ini
block_private_ip=1
url_allow_hosts=
url_ssrf_observe_only=0
```

示例库名：`cronpilot.sqlite` / 数据库名 `cronpilot`。

---

### 部署说明

- `docker-compose.yml`、`start.sh` 路径示例已按 CronPilot 调整。
- 修改 `conf.ini` 后需重启进程。

---

### 对接检查清单

- [ ] 业务回调读取 `cronpilot_log_id`、`cronpilot_sign` 并验签
- [ ] 进度回传使用 `POST /api/cron/add_log`
- [ ] 生产环境配置 SSRF（建议 `block_private_ip=1`）
- [ ] 管理端密码建议使用 `pbkdf2` 哈希

---

### 已知限制与后续

- **P1**：执行 status、失败规则、详情页、「立即执行」等（见 PRD）。
- **P2**：SSE、图表、OAuth 等。
- 推荐 Python **3.8–3.11**。
- `Dockerfile` 基础镜像待升级 LTS。

---

## 版本规划

| 版本 | 说明 |
|------|------|
| `0.1.0` | Phase A（P0）首发 |
| `0.1.1` | 文档 `/docs/`、Markdown 双格式、多版本 Python 自动匹配、CI |
| **`0.2.0`** | **P1 可观测、UI A′+B1+导航、Tier 0–2、Docker Py 3.10** |
| `0.2.x` / `0.3.x` | 计划：P1-03/04、操作审计、Tier 3 前置 |
