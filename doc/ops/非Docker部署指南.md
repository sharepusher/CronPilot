# CronPilot · 非 Docker 部署指南

> HTML 版：[非Docker部署指南.html](非Docker部署指南.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

[← 文档索引](../index.html)
运维
裸机 / VM

# 非 Docker 部署指南

在 Linux 或 macOS 上安装 CronPilot、远程访问管理端与 HTML 技术文档（`/docs/`）

## 1. 部署拓扑

浏览器 ──► Nginx :443 (可选 HTTPS / 文档鉴权)
│
├── / ──proxy──► Gunicorn 127.0.0.1:5860 (Flask 管理端 + API)
└── /docs/ ──proxy──► 同上（静态 HTML，内置路由）
Gunicorn ──► MySQL（或 SQLite） + Redis（集群时）

不使用 Docker 时，推荐 **Gunicorn + gevent** 作为 WSGI 进程；文档与控制台**同一端口**，无需单独起静态服务。

## 2. 环境要求

| 组件 | 要求 | 说明 |
| --- | --- | --- |
| Python | **3.8～3.11** | 勿用 3.12+（gevent 23 栈；Tier 2 其余项见 [依赖升级 RFC](../deps/依赖升级RFC.html)） |
| 数据库 | MySQL 5.7+ / 8 | 生产推荐；试用可用 SQLite |
| Redis | 可选 | 多实例集群锁；单机设 `is_single=1` |
| 端口 | **5860** | `gun.py` 默认；本地脚本常用 5001 |

## 3. 前端开发环境（可选）

**生产环境不需要 Node.js**——Vue 构建产物（`app/static/js/*.js`）已提交到仓库，Flask 直接托管。仅在修改 `frontend/src/` 下 Vue 组件源码时，需要 Node.js 重新构建。

### 3.1 架构说明

CronPilot 采用 **Islands Architecture**（岛屿架构）：主体由 Flask + Jinja2 服务端渲染，少量交互组件（`CronFilterBar`、`CronFormValidator`、`CronStatusCell`）用 Vue 3 + Vite 构建后输出到 `app/static/js/`，由 Flask 同进程托管。

| 环境 | Python | Node.js |
| --- | --- | --- |
| 生产（裸机 / Docker） | 3.8～3.11 | **不需要** |
| 开发（修改 Vue 组件时） | 3.8～3.11 | 18+ LTS（推荐 20/22） |
| CI | 3.11 | 仅 `frontend-build.yml` 检查时 |

### 3.2 安装 Node.js（推荐 nvm）

使用 **nvm**（Node Version Manager）管理 Node.js 版本，与 Python 的 pyenv 理念一致，不污染系统环境。

```
# 安装 nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc   # 或 ~/.zshrc

# 安装 Node.js LTS
nvm install --lts

# 安装前端依赖 & 构建
cd frontend
npm install          # 依赖安装到 frontend/node_modules/（项目级隔离）
npm run build        # 构建产物输出到 app/static/js/
```

### 3.3 Node.js 与 Python 环境隔离对比

| 维度 | Python (venv) | Node.js (node\_modules) |
| --- | --- | --- |
| 隔离机制 | `python -m venv .venv` | 项目级 `node_modules/`，天然隔离 |
| 依赖清单 | `requirements.txt` | `package.json` + `package-lock.json` |
| 全局污染风险 | 高（不用 venv 装到系统） | 低（`npm install` 默认装到当前目录） |
| 版本管理器 | pyenv | nvm / fnm / volta |
| 需要"激活" | `source .venv/bin/activate` | 不需要（`npx` / `npm run` 自动解析） |

Node.js 不需要 Python 式的虚拟环境——`node_modules/` 等价于 `.venv`，已在 `.gitignore` 中。

## 4. 安装步骤

### 4.1 Linux 一键安装（Ubuntu / CentOS 7·8，推荐）

自动识别发行版、**自动创建虚拟环境**（`.venv-py*`）。生产用 MySQL；试用加 `--sqlite`。

| 场景 | 命令 |
| --- | --- |
| 生产 MySQL | `sudo bash scripts/install_linux.sh --production` → 编辑 conf.ini → `bash scripts/run_production.sh` |
| 试用 SQLite | `sudo bash scripts/install_linux.sh --production --sqlite` → `bash scripts/run_production.sh` |

速查：[INSTALL.md](../../INSTALL.md) · [linux](linux安装与运行.md) · [ubuntu](ubuntu安装与运行.md) · [centos](centos安装与运行.md)

```
git clone git@github.com:sharepusher/CronPilot.git
cd CronPilot
sudo bash scripts/install_linux.sh --production
bash scripts/run_production.sh
```

### 4.2 手动安装（macOS / 自定义）

```
bash scripts/cronpilot.sh install
bash scripts/install_production_deps.sh
cp conf.ini.example conf.ini
```

Python 3.8～3.11；`run_production.sh` 自动使用 venv。

### 4.3 配置 conf.ini

必改项：`login_pwd`（**仅**空库种子 `admin` 的初始密码）、`cron_db_url`、`cron_job_log_db_url`、Redis（若集群）。日常改密见下表「认证」说明，勿在有用户后指望改 `login_pwd`。

**会话密钥 `SECRET_KEY`（勿写入 conf.ini）：**生产必须设置强密钥（长度 ≥ 16，且非源码默认值）。推荐：

```
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
# 或直接 bash scripts/run_production.sh —— 首次自动写入 datas/.flask_secret_key
# 多节点必须共用同一 SECRET_KEY
```

生成**初始**密码哈希（写入 `login_pwd`，须在空库首次启动前）：

```
python scripts/hash_login_password.py '你的强密码'
# 将输出写入 conf.ini 的 login_pwd=
```

### 4.4 MySQL 示例

```
[default]
is_single=1
cron_db_url=mysql+pymysql://user:pass@127.0.0.1:3306/cron_scheduler
cron_job_log_db_url=mysql+pymysql://user:pass@127.0.0.1:3306/cron_job_log
login_pwd=pbkdf2:...
block_private_ip=1
url_allow_hosts=
url_ssrf_observe_only=0
```

升级 **OPT-P2-12**：`bash scripts/run_production.sh`（或单独 `bash scripts/ensure_business_tables.sh`）会对 **MySQL / SQLite** 自动建业务组表并补 `scope_type`/`group_id`。需库已存在且账号有 DDL 权限。手写 SQL 备用见 [资源隔离与 Scope 设计 §十](../design/资源隔离与Scope设计.html)。

### 4.5 SQLite 单机试用

```
cron_db_url=sqlite:////opt/cronpilot/datas/cron.sqlite
cron_job_log_db_url=sqlite:////opt/cronpilot/datas/job_log.sqlite
```

路径请使用**绝对路径**（四个斜杠 `sqlite:////`）。

## 5. 启动服务

### 5.1 生产（Gunicorn，监听外网）

```
cd /opt/cronpilot/CronPilot
bash scripts/run_production.sh
export FLASK_CONFIG=production

gunicorn -c gun.py manage:app
# gun.py 已配置 bind = '0.0.0.0:5860'
```

### 5.2 本地冒烟

```
bash scripts/start_local.sh
# 默认 127.0.0.1:5001；远程调试可改 host 为 0.0.0.0
```

### 5.3 访问地址

| 用途 | URL | 认证 |
| --- | --- | --- |
| Web 管理端 | `http://<IP>:5860/` | 用户名 + 密码（`rbac_users`）。空库种子 `admin`/`login_pwd`；日常改密：用户管理 → 编辑 → 新密码 |
| REST API | `http://<IP>:5860/api/...` | `api_access_token` 等 |
| HTML 技术文档 | `http://<IP>:5860/docs/` | **无登录** |

文档索引：`/docs/` → `doc/index.html`；子页如 `/docs/架构设计文档.html`。

## 6. 防火墙与健康检查

```
sudo ufw allow 5860/tcp

curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5860/docs/
# 期望 200

python -m unittest tests.test_p0_phase_a tests.test_cronpilot_sign -v
```

## 7. systemd（可选）

文件 `/etc/systemd/system/cronpilot.service`：

```
[Unit]
Description=CronPilot scheduler admin
After=network.target mysql.service redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/cronpilot/CronPilot
Environment=FLASK_CONFIG=production
# Environment=SECRET_KEY=请替换为 secrets.token_hex(32) 的输出（多节点须一致）
ExecStart=/opt/cronpilot/CronPilot/.venv-py311/bin/gunicorn -c gun.py manage:app
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```
sudo systemctl daemon-reload
sudo systemctl enable --now cronpilot
sudo systemctl status cronpilot
```

## 8. Nginx 反代 + HTTPS

```
server {
    listen 443 ssl;
    server_name cron.example.com;

    location / {
        proxy_pass http://127.0.0.1:5860;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /docs/ {
        proxy_pass http://127.0.0.1:5860/docs/;
        # 公网建议加鉴权，例如：
        # auth_basic "CronPilot Docs";
        # auth_basic_user_file /etc/nginx/.htpasswd-cronpilot-docs;
    }
}
```

对外仅暴露 443，Gunicorn 只监听 `127.0.0.1:5860` 更安全。

## 9. 安全建议

- 生产必须使用**强密码**或 `pbkdf2` 哈希，禁止默认口令。
- 生产必须配置强 `SECRET_KEY`（环境变量或 `run_production.sh` 生成的 `datas/.flask_secret_key`）；直接 gunicorn 且使用默认密钥会拒绝启动。
- 管理端写操作已启用 CSRF（OPT-P0-11）：升级后**硬刷新**；勿用 GET 书签触发启停/立即执行。
- `/docs/` **无需登录**，含架构与 API 细节；公网请用 Nginx 白名单 / Basic Auth / 仅内网。
- 保持 `block_private_ip=1`，按需配置 `url_allow_hosts`。
- 勿对 `0.0.0.0` 使用 `debug=True` 的 Flask 内置服务器。

## 10. 常见问题

| 现象 | 处理 |
| --- | --- |
| 启动报 SECRET\_KEY | 设置环境变量 `SECRET_KEY`，或用 `bash scripts/run_production.sh`（自动生成 `datas/.flask_secret_key`） |
| 启停/立即执行失败（CSRF） | 硬刷新管理端；确认页面有 `csrf-token` meta；勿用旧 GET 书签 |
| `pip install gevent` 失败 | 换 3.9/3.10；或本地用 `bash scripts/start_local.sh`（core 依赖）。长期方案：[依赖升级 RFC](../deps/依赖升级RFC.html) Tier 2 |
| 数据库 schema 演进 | **主路径**：`bash scripts/ensure_business_tables.sh`（启动/`run_production` 已调用；SQLite/MySQL 建表补列）。 `flask db migrate/upgrade` 可用（Tier 0 CLI），但仓库**当前无**强制 Alembic revision 树；勿假设已有 `migrations/`。见 [Tier 3b](../deps/Tier3b-迁移重放与残余收束设计.html) / [依赖升级 RFC](../deps/依赖升级RFC.html) |
| 外网无法访问 | 确认 Gunicorn `0.0.0.0`、防火墙、云安全组放行 5860 |
| `/docs/` 404 | 确认已部署含 `app/docs/` 的版本并重启进程 |
| 调度不触发 | 检查 `cron_db_url`、APScheduler 库表、`is_single` / Redis |

## 11. 相关文档

- [文档索引](../index.html)
- [依赖升级 RFC](../deps/依赖升级RFC.html)（Tier 0～4 分层路线、与 RBAC 排期）
- [架构设计文档](../arch/架构设计文档.html)（部署拓扑、集群）
- [详细技术方案](../arch/详细技术方案.html)（配置项、API）
- [P0 测试与验收](../qa/P0测试用例与验收手册.html)
- 仓库 `README.md` 快速开始章节

CronPilot · 非 Docker 部署 · v0.1.0 · [Markdown 版](非Docker部署指南.md) · [文档索引](../index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
