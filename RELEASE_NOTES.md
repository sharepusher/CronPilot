# CronPilot Release Notes

本文档记录 **CronPilot** 相对上游 [aniu-lee/xiaoniu_cron](https://github.com/aniu-lee/xiaoniu_cron) 的独立演进变更。  
HTML 版：[doc/RELEASE_NOTES.html](doc/RELEASE_NOTES.html)

---

## [0.1.0] — 2026-05-29 · Phase A（P0）首发

首个可发布基线：品牌独立、安全与质量改造、统一 API 契约、完整技术文档与许可合规。**系统尚未正式上线**，本版本包含破坏性 API 更名，无需兼容旧参数。

### 项目定位与品牌

- 项目正式命名为 **CronPilot**（HTTP 定时回调调度中心）。
- 自上游 `xiaoniu_cron` 拆分为独立仓库演进，不向上游强推合并。
- Web 管理端标题：**CronPilot 定时调度平台**（原「小牛定时任务管理系统」）。
- HTTP 回调 `User-Agent`：`CronPilot`。
- 本地开发：`scripts/start_local.sh`；配置示例：`conf.ini.example`。

### 破坏性变更（API / 回调协议）

> 未上线环境，**不保留** `xiaoniu_cron_*` 旧参数名。

| 旧（xiaoniu_cron） | 新（CronPilot） | 说明 |
|--------------------|-----------------|------|
| `xiaoniu_cron_log_id` | `cronpilot_log_id` | 每次触发生成的执行 UUID |
| `xiaoniu_cron_sign` | `cronpilot_sign` | 回调 query 签名字段 |
| `get_xiaoniu_cron_sign()` | `get_cronpilot_sign()` | 平台侧签名函数 |

**回调示例：**

```http
GET https://your-service/callback?cronpilot_log_id=<UUID>&cronpilot_sign=<MD5>
```

**进度回传：**

```http
POST /api/cron/add_log
cronpilot_log_id=<UUID>&content=...
```

验签算法不变：参数按 key ASCII 排序，`key=value&&...&&api_key=` + MD5。

数据库列名仍为 `job_log.log_id`（存 UUID），仅 HTTP/API 参数名变更。

---

### Phase A（P0）— 安全与基础质量

#### OPT-P0-01 · SQL 参数化

- 删除定时任务时清理 `job_log`：由 `execute("delete ... '%s'")` 改为 ORM `JobLog.query.filter(...).delete()`。
- 定时清理超限日志：`cron_del_job_log` 使用 `trim_job_logs_for_cron()`（ORM 按 id 删除），消除 SQL 拼接。
- 新增模块：`app/services/job_log_service.py`。

#### OPT-P0-02 · 管理端密码哈希

- 新增 `app/auth/password.py`：支持 `conf.ini` 明文密码（兼容）与 `pbkdf2` 哈希。
- 工具：`scripts/hash_login_password.py` 将明文转为哈希写入 `login_pwd`。
- 登录页不再在 dev 模式下在 placeholder 暴露明文密码。

#### OPT-P0-03 · 回调 URL SSRF 防护

- 新增 `app/services/url_security.py`。
- 配置项（`configs.py` / `conf.ini.example`）：
  - `block_private_ip=1` — 默认拦截本机、内网、链路本地/元数据地址。
  - `url_allow_hosts` — 可选主机白名单（逗号分隔）。
  - `url_ssrf_observe_only=0` — `1` 时仅观察不拦截（灰度）。
- 保存任务与 `cron_do` 执行前双重校验。

#### OPT-P0-04 · 统一 JSON 契约

- 新增 `datas/utils/json.py` → `json_response()`，`errcode` 固定为 **int**。
- `web_api_return()` / `api_return()` 统一走同一契约。
- 修复 `app/static/js/requests.js`：`errcode === 0`（原错误使用字符串 `'0'` 导致 Ajax 成功回调不触发）。

#### OPT-P0-05 · Cron 校验与任务写入统一

- 新增 `app/services/cron_validator.py` — Web / API 共用校验（含 `mon,wed` 等星期写法）。
- 新增 `app/services/cron_service.py` — `add_cron_web`、`edit_cron_web`、`upsert_cron_by_task_name`、调度注册。
- `app/main/views.py` 的 `cron_add` / `cron_edit` 与 `app/api/views.py` 的 `/api/cron` 收敛为同一 service，消除双份 300+ 行校验逻辑。
- 修复 `cron_service` ↔ `crons` 循环依赖（日志清理迁至 `job_log_service`）。

---

### 文档

| 文档 | 说明 |
|------|------|
| `doc/index.html` | 文档索引 |
| `doc/项目总览与技术文档.html` | 项目入口、架构、模块导航 |
| `doc/架构设计文档.html` | C4、部署、调度、集群、Plombery 摘要 |
| `doc/详细技术方案.html` | 功能规格、API、配置、运维 |
| `doc/技术方案与前端设计.html` | 线框与 UI |
| `doc/Plombery深度对比分析.html` | 16 章深度对比 |
| `doc/产品优化需求-借鉴Plombery.html` | P0/P1/P2 详版 PRD |
| `doc/P0测试用例与验收手册.html` | 自动化 + 手工冒烟 + curl 脚本 |
| `doc/新建项目与分支合并方案.html` | 与上游仓库拆分说明 |
| `doc/LICENSE-AUDIT.html` | 许可证审计报告 |

---

### 许可与合规

- 本仓库采用 **Apache License 2.0**（`LICENSE`）。
- `NOTICE` — 上游来源与权责说明。
- `THIRD_PARTY_NOTICES.md` — Python 依赖与静态前端许可清单。
- 上游 `aniu-lee/xiaoniu_cron` 在 GitHub 未声明 SPDX 许可证；商业再分发前请法务确认或取得作者授权。

---

### 测试

| 套件 | 说明 |
|------|------|
| `tests/test_p0_phase_a.py` | 12 项：SSRF、密码、校验、JSON 契约等 |
| `tests/test_cronpilot_sign.py` | `get_cronpilot_sign` 稳定性 |
| `tests/README.md` | 运行说明（推荐 Python 3.8–3.11） |

```bash
python -m unittest tests.test_p0_phase_a tests.test_cronpilot_sign -v
```

---

### 配置变更摘要

**新增 `conf.ini` 项：**

```ini
block_private_ip=1
url_allow_hosts=
url_ssrf_observe_only=0
```

**示例库名（`conf.ini.example`）：** `cronpilot.sqlite` / 数据库名 `cronpilot`。

---

### 部署与运维

- `docker-compose.yml` 挂载路径示例更新为 `CronPilot`。
- `start.sh` 工作目录：`/home/www/cronpilot`。
- 修改 `conf.ini` 后需**重启进程**（`LOGIN_PWD` 等在启动时加载）。

---

### 自 xiaoniu_cron 迁移检查清单

若从上游代码或文档迁移，请逐项核对：

- [ ] 业务回调改为读取 `cronpilot_log_id`、`cronpilot_sign`
- [ ] 验签代码中的参数名同步修改（算法不变）
- [ ] `POST /api/cron/add_log` 使用 `cronpilot_log_id`
- [ ] 配置 SSRF 相关三项（生产建议 `block_private_ip=1`）
- [ ] 管理端密码建议改为 `pbkdf2` 哈希
- [ ] 前端 Ajax 依赖数字 `errcode`，确认列表操作有成功提示

---

### 已知限制与后续路线

- **P1（规划）**：`job_log.status` / `http_status`、失败规则、执行详情页、「立即执行」等（见 PRD）。
- **P2（规划）**：SSE 实时日志、图表、OAuth 等。
- Python **3.12+** 与 Flask 1.1 / Werkzeug 1.0 组合未充分验证，推荐 **3.8–3.11**。
- `Dockerfile` 仍基于 `ubuntu:16.04`（EOL），建议后续升级 LTS。
- 静态前端（jQuery/Bootstrap 等）尚未集中 `NOTICE-frontend.txt`。

---

## 版本号说明

| 版本 | 含义 |
|------|------|
| `0.1.0` | Phase A（P0）能力闭环，可对内/测试环境发布 |
| 后续 `0.2.x` | 计划对应 P1 可观测与运维体验 |

---

## 贡献者与致谢

- 演进基础：[aniu-lee/xiaoniu_cron](https://github.com/aniu-lee/xiaoniu_cron)
- 对标参考：[Plombery](https://github.com/lucafaggianelli/plombery)（MIT，文档对比用）
