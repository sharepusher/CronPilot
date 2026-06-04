# CronPilot Release Notes

本文档记录 **CronPilot** 版本变更。  
HTML 版：[doc/RELEASE_NOTES.html](doc/RELEASE_NOTES.html)

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

### CI（GitHub Actions）

| 工作流 | 说明 |
|--------|------|
| Docs HTML ↔ Markdown sync | PR 校验 `doc/*.md` 与 HTML 一致 |
| Unit tests | 矩阵 **3.8 / 3.9 / 3.10 / 3.11** + `requirements-core.txt` |
| install-full | 在 3.10 安装完整 `requirements.txt` 验证 gevent 等 |

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
| `0.2.x` | 计划：P1 可观测与运维体验 |
