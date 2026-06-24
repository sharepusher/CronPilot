# CronPilot

中心化 **HTTP 定时回调调度台**：到点向业务 `req_url` 发起 GET，支持 Web 管理、REST API 动态改任务、秒级 Cron、集群双锁与执行日志。

当前版本 **v0.1.1**（Phase A P0 + 文档 `/docs/`、多版本 Python 自动匹配）；详见 [Release Notes](RELEASE_NOTES.md)。

## 主要能力（v0.1.0）

| 能力 | 说明 |
|------|------|
| SQL 安全 | 删除任务/清理日志改为 SQLAlchemy ORM，消除拼接 SQL |
| 登录安全 | 支持 `login_pwd` 明文（兼容）与 `pbkdf2` 哈希 |
| SSRF 防护 | `block_private_ip`、`url_allow_hosts`、执行前二次校验 |
| API 契约 | 统一 `errcode` 数字类型；修复前端 `requests.js` 判断 |
| 校验统一 | `cron_validator` + `cron_service`，Web/API 单一路径 |

后续路线图见 `doc/产品优化需求-借鉴Plombery.html`（P1 可观测、P2 体验）；依赖分层升级见 [doc/依赖升级RFC.html](doc/依赖升级RFC.html)（OPT-P2-11：Tier 0 `flask db` → SA 1.4 → gevent → Flask 2）。

## 快速开始

### 1. 配置

```bash
cp conf.ini.example conf.ini
# 编辑数据库、login_pwd、redis、block_private_ip 等
```

生成密码哈希（推荐生产）：

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

### 3. 启动

```bash
bash scripts/cronpilot.sh start
# 等价于 bash scripts/start_local.sh
```

仅当自动检测不符合预期时，可临时覆盖：`PY=python3.9 bash scripts/cronpilot.sh start`

浏览器打开：`http://127.0.0.1:5001/`，密码为 `conf.ini` 中的 `login_pwd`。

### 4. 测试

```bash
python -m unittest tests.test_p0_phase_a -v
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
| 默认密码 | `changeme`（改 `conf.ini` → `login_pwd`） |

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
| Web 管理端 | `http://<服务器IP>:5860/` | `conf.ini` → `login_pwd` |
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

1. 生产务必使用 **强密码** 或 `pbkdf2` 哈希，勿暴露默认 `login_pwd`。
2. `/docs/` **无需登录**，含架构与 API 说明；公网部署时建议 Nginx **IP 白名单** 或 **Basic Auth**，或仅内网/VPN 访问。
3. 保持 `block_private_ip=1`，按需配置 `url_allow_hosts`。
4. 勿对 `0.0.0.0` 使用 `debug=True` 的开发服务器。

### 健康检查

```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5860/docs/
# 期望 200

python -m unittest tests.test_p0_phase_a tests.test_cronpilot_sign -v
```

## Release Notes

**[RELEASE_NOTES.md](RELEASE_NOTES.md)** · [doc/RELEASE_NOTES.html](doc/RELEASE_NOTES.html) — **v0.1.0**（2026-05-29）Phase A 变更说明。

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
| **Docs HTML ↔ Markdown sync** | PR 中校验 `doc/*.md` 与 HTML 一致（`doc/index.md` 手写，不参与自动生成） |
| **Unit tests** | 矩阵 **3.8 / 3.9 / 3.10 / 3.11** + `requirements-core.txt`；另 **install-full** 矩阵 **3.9 / 3.10 / 3.11** 验证全量依赖 |

文档含：**[INSTALL.md](INSTALL.md)**、**[依赖升级 RFC](doc/依赖升级RFC.html)**、架构设计、详细技术方案、**[非 Docker 部署指南](doc/非Docker部署指南.html)**、Plombery 对比、详版 PRD、P0 测试手册、Release Notes 等。

## AI / 协作规范（Cursor）

项目规范见 [`.cursor/rules/`](.cursor/rules/) 与 [`AGENTS.md`](AGENTS.md)，涵盖仓库边界、Phase A 安全、文档双格式、CI 与发布流程，减少重复沟通。

## 目录结构

```
.cursor/rules/       # Cursor 项目规范（.mdc）
app/
  services/          # cron_validator、cron_service、url_security、job_log_service
  auth/              # 密码哈希校验
  main/              # Web 管理端
  docs/              # /docs/ 静态 HTML 文档路由
  api/               # REST API
doc/                 # 技术文档源文件（HTML）
tests/               # P0 单元测试
scripts/             # 本地启动、密码哈希工具
```

## 回调与 API 约定

触发业务 URL 时，平台会追加 query 参数：

| 参数 | 说明 |
|------|------|
| `cronpilot_log_id` | 本次执行唯一 ID（UUID） |
| `cronpilot_sign` | 对现有 query + log_id 按 ASCII 排序拼接后 MD5（见 `get_cronpilot_sign`） |

长任务进度回传：`POST /api/cron/add_log`，必传 `cronpilot_log_id`、`content`。

## 配置项（P0 新增）

| 键 | 默认 | 说明 |
|----|------|------|
| `block_private_ip` | `1` | 禁止回调内网/本机/元数据地址 |
| `url_allow_hosts` | 空 | 非空时仅允许列出的主机（逗号分隔） |
| `url_ssrf_observe_only` | `0` | `1` 时仅记录不拦截（灰度） |

## 许可证

本项目采用 [Apache License 2.0](LICENSE)。第三方组件见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)；合规说明见 [doc/LICENSE-AUDIT.html](doc/LICENSE-AUDIT.html)。
