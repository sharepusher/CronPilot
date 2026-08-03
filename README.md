# CronPilot

中心化 **HTTP 定时回调调度台**：到点向业务 `req_url` 发起 GET/POST（POST 支持 JSON Body），支持 Web 管理、REST API 动态改任务、秒级 Cron、集群双锁与执行日志。

当前版本 **v2.6.0**（颜色收编 · API access_token 加固 · S6 用户级 Token · 查询式 API 文档；运行时 Flask 2.3 + SQLAlchemy 2.0）；详见 [Release Notes](RELEASE_NOTES.md)。产品与工程进度总览：[doc/交付状态与路线图.html](doc/交付状态与路线图.html)（面向维护者）。

## 主要能力

| 版本 | 能力 |
|------|------|
| **v2.6.0** | 前端颜色收编（191 处→CSS 变量）；API access_token 加固；用户级 Token（S6）；只读 API 文档重设计；颜色审计 CI 门禁 |
| **v2.5.0** | 执行状态机 B1（4 终态 success/fail/timeout/error）；单任务超时配置 B2；表单实时校验（Vue 3） |
| **v2.4.0** | 前端现代化 Vite + Vue 3（状态单元格、筛选栏、Toast 抽象）；管理端 UX 优化；死静态资源清理 |
| **v2.3.0** | API 契约规范化（OpenAPI 3.0 + Swagger UI）；`/api/swagger` 交互文档 |
| **v2.2.0** | 可观测性（结构化日志 + Prometheus 指标）；CSRF AJAX 表单修复；集成测试 |
| **v2.1.1** | 集群 Redis 锁原子化；生产 `SECRET_KEY` fail-fast；管理端写操作 CSRF（POST + token） |
| **v2.1.0** | 升级至 Flask **2.3.3** + SQLAlchemy **2.0.36**；移除 `records`；列表查询与模型适配 2.x |
| **v2.0.0** | 任务中心五列 + `job_health`；列表立即执行；强制首次改密/触发重置；用户启停缘由；**触发请求 GET/POST + JSON Body** |
| **v1.2.0** | 管理端顶栏身份（系统/业务管理员）；种子 `admin` 仅建用户+只读；启停用语统一；下线入口提示 |
| **v1.1.0** | 业务组资源隔离；自助改密（成功后强制重新登录）；任务编辑页精简 |
| **v1.0.0** | 三角色权限、用户管理 / 审计；操作记录；无人工删除 + 下线；回调 `log_id`；404 友好页 |
| **v0.2.0** | 执行状态与失败判定；执行记录与导航体验；依赖与 Docker（Python 3.10）加固 |
| **v0.1.1** | 文档 `/docs/`、Python 3.8–3.11 自动匹配、CI |
| **v0.1.0** | ORM 化访问、密码哈希、SSRF 防护、统一 JSON 契约、校验与服务层抽取 |

后续路线图见 [doc/交付状态与路线图.html](doc/交付状态与路线图.html)（推荐）或 [doc/产品优化需求-借鉴Plombery.html](doc/产品优化需求-借鉴Plombery.html)。

## 快速开始

### 1. 配置

```bash
cp conf.ini.example conf.ini
# 编辑数据库、login_pwd（仅空库种子 admin 的初始密码）、redis、block_private_ip 等
```

生成初始密码哈希（推荐在**首次启动、空库种子之前**写入 `login_pwd`）：

```bash
python scripts/hash_login_password.py '你的强密码'
```

### 2. 依赖（Python 3.8 / 3.9 / 3.10 / 3.11）

支持 **3.8～3.11**（勿用 3.12+）。**无需手动指定 Python 版本**，脚本会自动：

1. 若已有 `.venv-py*` → 优先复用  
2. 否则按 `python3.11` → `3.10` → `3.9` → `3.8` → `python3` 探测（跳过 3.12+）

```bash
bash scripts/cronpilot.sh check      # 查看本机可用版本
bash scripts/cronpilot.sh install    # 自动建 venv + 安装核心依赖
bash scripts/cronpilot.sh test       # 自动 venv 下跑单测
```

| 依赖文件 | 用途 |
|----------|------|
| `requirements-core.txt` | 本地开发、单元测试（无 gevent） |
| `requirements.txt` | 生产 Gunicorn + gevent 全量依赖 |

生产环境在自动创建的 venv 中：`source .venv-py*/bin/activate` → `pip install -r requirements.txt`

### 2.1 前端开发环境（可选 — 仅修改 Vue 组件时需要）

**生产环境不需要 Node.js**。Vue 构建产物（`app/static/js/*.js`）已提交到仓库，Flask 直接托管。

仅在修改 `frontend/src/` 下 Vue 组件源码后，需要 Node.js 重新构建：

```bash
# 推荐用 nvm 管理 Node.js 版本（类似 pyenv）
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
nvm install --lts

cd frontend
npm install        # 依赖装到 frontend/node_modules/（项目级隔离，不污染系统）
npm run build      # 产物输出到 app/static/js/
```

| 环境 | Python | Node.js |
|------|--------|---------|
| 生产 | 3.8～3.11 | **不需要** |
| 开发（改 Vue 时） | 3.8～3.11 | 18+ LTS |

### 3. 启动

```bash
bash scripts/cronpilot.sh start
# 等价于 bash scripts/start_local.sh
```

仅当自动检测不符合预期时，可临时覆盖：`PY=python3.9 bash scripts/cronpilot.sh start`

浏览器打开：`http://127.0.0.1:5001/`。Web 登录为 **用户名 + 密码**：

| 项 | 说明 |
|----|------|
| 空库首次 | 自动种子用户名 `admin`；初始密码 = `conf.ini` → `login_pwd`（示例多为 `changeme`） |
| 日常改密 | 登录后导航 **修改密码**（任意角色，自助）；或 admin **用户管理** → 编辑 →「新密码」（`user:manage`） |
| `login_pwd` | **仅种子用**；表已有用户后改此项并重启**不会**改库内密码 |
| 不提供 | 登录页「忘记密码」 |

### 4. 测试

```bash
bash scripts/cronpilot.sh test
# 或：python -m unittest tests.test_p0_phase_a tests.test_cronpilot_sign -v
```

手工冒烟与用例表见：**[doc/P0测试用例与验收手册.html](doc/P0测试用例与验收手册.html)**

## Docker 部署（快速试用）

无需在宿主机安装 Python；适合本地验证，或宿主机 apt/dpkg（如 PostgreSQL）异常时。

```bash
git clone https://github.com/sharepusher/CronPilot.git
cd CronPilot
cp conf.ini.example conf.ini
docker compose up --build -d
```

| 项 | 值 |
|----|-----|
| 管理端 | `http://<宿主机IP>:5860/` |
| 文档 | `http://<宿主机IP>:5860/docs/` |
| 默认登录 | 用户名 `admin` · 初始密码见 `login_pwd`（常为 `changeme`）；**仅空库种子**。日常改密走导航「修改密码」或「用户管理」，勿指望改 `login_pwd` 重启生效 |

- 数据目录：宿主机 `./datas` 挂载进容器
- 改配置：`nano conf.ini` → `docker compose restart`
- 停止：`docker compose down`
- 镜像：Ubuntu 22.04 + Python 3.10，容器内自动 SQLite 试用配置

裸机 / pyenv / MySQL 生产路径见 **[INSTALL.md](INSTALL.md)**（路径 A/B/C/D）。

**开发者 CI 验收**（验证裸机安装脚本，非运行镜像）：

```bash
bash scripts/docker/verify_all.sh all
```

## 非 Docker 部署（生产 / 远程访问）

适用于 Linux 或 macOS 裸机、虚拟机，**不使用 Docker**。

### 环境

| 组件 | 要求 |
|------|------|
| Python | **3.8～3.11**（勿用 3.12+；gevent 23 栈见 [doc/依赖升级RFC.html](doc/依赖升级RFC.html)） |
| 数据库 | **MySQL**（推荐）或 SQLite（试用） |
| Redis | 多节点集群时必需；单机可 `is_single=1` |
| 端口 | 管理端默认 **5860**（`gun.py`）；本地脚本常用 **5001** |

### 安装

**Linux 一键安装（Ubuntu / CentOS 7·8）：** 详见 [INSTALL.md](INSTALL.md)

```bash
git clone https://github.com/sharepusher/CronPilot.git
cd CronPilot
# 生产（MySQL）：sudo bash scripts/install_linux.sh --production
# 试用（SQLite）：sudo bash scripts/install_linux.sh --production --sqlite
sudo bash scripts/install_linux.sh --production
# 编辑 conf.ini 中 cron_db_url（MySQL）后：
bash scripts/run_production.sh
# （内含 ensure_business_tables：MySQL/SQLite 自动建表补列）
```

脚本自动创建 `.venv-py*` 虚拟环境，**一般无需** `source activate`。

**手动安装（macOS 或自定义）：**

```bash
git clone https://github.com/sharepusher/CronPilot.git
cd CronPilot
bash scripts/cronpilot.sh install
bash scripts/install_production_deps.sh
cp conf.ini.example conf.ini
bash scripts/cronpilot.sh exec python scripts/hash_login_password.py '强密码'
```

**SQLite 单机示例**（路径改为本机绝对路径）：

```ini
is_single=1
cron_db_url=sqlite:////opt/cronpilot/datas/cron.sqlite
cron_job_log_db_url=sqlite:////opt/cronpilot/datas/job_log.sqlite
```

### 启动服务（监听外网）

```bash
cd /opt/cronpilot/CronPilot
bash scripts/run_production.sh
# 内部使用 .venv-py*/bin/gunicorn，监听 0.0.0.0:5860
```

| 入口 | URL | 认证 |
|------|-----|------|
| Web 管理端 | `http://<服务器IP>:5860/` | 用户名 + 密码（`rbac_users`）；种子见下节「密码」；三角色 RBAC |
| REST API | `http://<服务器IP>:5860/api/...` | `api_access_token` 等 |
| **HTML 技术文档** | `http://<服务器IP>:5860/docs/` | **无登录**（见下方安全说明） |

文档首页：`/docs/` → `doc/index.html`；子页面如 `/docs/架构设计文档.html`。

### 防火墙

**Ubuntu：** `sudo ufw allow 5860/tcp`

**CentOS / RHEL：** `sudo firewall-cmd --permanent --add-port=5860/tcp && sudo firewall-cmd --reload`

**Docker 验收（可选）：** `bash scripts/docker/verify_all.sh all`

### systemd 示例（可选）

`/etc/systemd/system/cronpilot.service`：

```ini
[Unit]
Description=CronPilot scheduler admin
After=network.target mysql.service redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/cronpilot/CronPilot
Environment=FLASK_CONFIG=production
ExecStart=/opt/cronpilot/CronPilot/.venv/bin/gunicorn -c gun.py manage:app
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now cronpilot
```

### Nginx 反代 + HTTPS（推荐）

```nginx
server {
    listen 443 ssl;
    server_name cron.example.com;

    # 管理端 + API
    location / {
        proxy_pass http://127.0.0.1:5860;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # 技术文档（可选：仅内网或加鉴权）
    location /docs/ {
        proxy_pass http://127.0.0.1:5860/docs/;
        # auth_basic "CronPilot Docs";
        # auth_basic_user_file /etc/nginx/.htpasswd-cronpilot-docs;
    }
}
```

### 安全建议

1. **初始密码**：空库前用强明文或 `pbkdf2` 写入 `login_pwd`；首次启动种子 `admin`。**已有用户后**改密请走导航「修改密码」或「用户管理 → 编辑 → 新密码」，勿再依赖改 `login_pwd`。
2. **会话密钥 `SECRET_KEY`**：生产必须设置（勿写入 `conf.ini`）。`export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"`，或使用 `scripts/run_production.sh`（首次写入 `datas/.flask_secret_key`）。多节点须共用同一密钥。
3. **管理端 CSRF**：升级后请硬刷新；启停 / 立即执行等写操作须为 POST 并携带页面 CSRF token（勿使用旧书签 GET）。
4. `/docs/` **无需登录**，含架构与 API 说明；公网部署时建议 Nginx **IP 白名单** 或 **Basic Auth**，或仅内网/VPN 访问。
5. 保持 `block_private_ip=1`，按需配置 `url_allow_hosts`。
6. 勿对 `0.0.0.0` 使用 `debug=True` 的开发服务器。

### 健康检查

```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5860/docs/
# 期望 200

bash scripts/cronpilot.sh test        # 全量单测（333+ 用例）
```

## Release Notes

**[RELEASE_NOTES.md](RELEASE_NOTES.md)** · [doc/RELEASE_NOTES.html](doc/RELEASE_NOTES.html) — 当前 **v2.6.0**；历史见文档内版本节。

## 技术文档（HTML + Markdown）

每份文档均提供 **HTML** 与 **Markdown** 两种格式：

| 入口 | 路径 |
|------|------|
| HTML 索引 | `doc/index.html` · 在线 `/docs/` |
| Markdown 索引 | **[doc/index.md](doc/index.md)** · 在线 `/docs/index.md` |

服务启动后（与管理端同端口）：

- HTML：`http://<服务器IP>:<端口>/docs/`
- Markdown：`http://<服务器IP>:<端口>/docs/架构设计文档.md` 等

从 HTML 更新 Markdown（修改 `.html` 后执行）：

```bash
pip install markdownify
python scripts/html_docs_to_markdown.py
python scripts/html_docs_to_markdown.py --check   # 仅校验是否同步（CI 同款）
```

GitHub Actions：

| 工作流 | 说明 |
|--------|------|
| **Unit tests** | 矩阵 **3.8 / 3.9 / 3.10 / 3.11** + `requirements-core.txt` |
| **Install full** | 矩阵 **3.9 / 3.10 / 3.11** 验证全量依赖（`requirements.txt`） |
| **Docs HTML ↔ Markdown sync** | PR 中校验 `doc/*.md` 与 HTML 一致（`doc/index.md` 手写，不参与自动生成） |
| **Hardcoded color audit** | 检查模板/Vue 中是否有硬编码十六进制颜色（`audit_hardcoded_colors.py --check`） |
| **Frontend dist freshness** | 校验 `app/static/dist/` 构建产物与 `frontend/src/` 源码一致 |
| **Docker install verify** | Docker 环境安装脚本验证 |

文档含：**[INSTALL.md](INSTALL.md)**、**[交付状态与路线图](doc/交付状态与路线图.html)**、**[RBAC 详设](doc/RBAC架构设计方案.html)**、**[依赖升级 RFC](doc/依赖升级RFC.html)**、架构设计、详细技术方案、**[非 Docker 部署指南](doc/非Docker部署指南.html)**、Plombery 对比、详版 PRD、P0 测试手册、Release Notes 等。

## AI / 协作规范（Cursor）

项目规范见 [`.cursor/rules/`](.cursor/rules/) 与 [`AGENTS.md`](AGENTS.md)，涵盖仓库边界、Phase A 安全、文档双格式、CI 与发布流程，减少重复沟通。

## 目录结构

```
.cursor/rules/       # Cursor 项目规范（.mdc）
app/
  services/          # cron_validator、cron_service、url_security、job_log_service、operation_log_service
  repositories/      # 薄 Repository 层（Phase B）：CronRepository、JobLogRepository、RbacUserRepository 等
  auth/              # 密码哈希校验
  rbac/              # 三角色策略、登录、has_perm、require_permission、Scope 过滤
  security/          # CSRF 防护
  main/              # Web 管理端
  docs/              # /docs/ 静态 HTML 文档路由
  api/               # REST API + 用户级 Token 鉴权
  static/css/        # console-theme.css（CSS 变量主题）
  static/dist/       # Vue 构建产物（JS + CSS）
frontend/            # Vue 3 组件源码（Vite 构建；生产无需 Node.js）
doc/                 # 技术文档源文件（HTML + 同步 MD）
tests/               # 单测（P0 / RBAC / S6 / form guard 等，333+ 用例）
scripts/             # 本地启动、验收、密码哈希、颜色审计工具
```

## 回调与 API 约定

触发业务 URL 时，平台会追加 query 参数：

| 参数 | 说明 |
|------|------|
| `cronpilot_log_id` | 本次执行唯一 ID（UUID） |
| `cronpilot_sign` | 对现有 query + log_id 按 ASCII 排序拼接后 MD5（见 `get_cronpilot_sign`） |

长任务进度回传：`POST /api/cron/add_log`，必传 `cronpilot_log_id`、`content`。

## 配置项（节选）

| 键 | 默认 | 说明 |
|----|------|------|
| `login_pwd` | （必填） | **仅**空表时种子 `admin` 的初始密码（明文或 `pbkdf2`）；有用户后改此项无效于登录 |
| `SECRET_KEY`（环境变量） | 开发有默认；生产必强 | 会话签名；勿写入 conf.ini。生产可用 `run_production.sh` 生成 `datas/.flask_secret_key` |
| `api_access_token` | 空 | 全局 API Token（Bearer）；空且 `api_access_token_required=0` 时 API 免鉴权 |
| `api_access_token_required` | `0` | `1` 时生产启动 fail-fast：`api_access_token` 为空则拒绝启动 |
| `block_private_ip` | `1` | 禁止回调内网/本机/元数据地址 |
| `url_allow_hosts` | 空 | 非空时仅允许列出的主机（逗号分隔） |
| `url_ssrf_observe_only` | `0` | `1` 时仅记录不拦截（灰度） |
| `operation_log_counts` | `5000` | 业务操作记录保留条数上限 |

## 许可证

本项目采用 [Apache License 2.0](LICENSE)。第三方组件见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)；合规说明见 [doc/LICENSE-AUDIT.html](doc/LICENSE-AUDIT.html)。
