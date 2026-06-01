# CronPilot Release Notes

本文档记录 **CronPilot** 版本变更。  
HTML 版：[doc/RELEASE_NOTES.html](doc/RELEASE_NOTES.html)

---

## [0.1.0] — 2026-05-29 · Phase A（P0）首发

首个版本：HTTP 定时回调调度、Web/API 管理、P0 安全与质量能力、技术文档与 Apache-2.0 许可。

### 项目定位

- **CronPilot** — 中心化 HTTP 定时回调调度台。
- Web 管理端：**CronPilot 定时调度平台**。
- 回调 HTTP `User-Agent`：`CronPilot`。
- 本地开发：`scripts/start_local.sh`；配置示例：`conf.ini.example`。

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
python -m unittest tests.test_p0_phase_a tests.test_cronpilot_sign -v
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
| `0.1.0` | Phase A（P0） |
| `0.2.x` | 计划：P1 可观测与运维体验 |
