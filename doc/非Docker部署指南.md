# CronPilot · 非 Docker 部署指南

> HTML 版：[非Docker部署指南.html](非Docker部署指南.html) · [文档索引](index.html) · [索引 Markdown](index.md)

[← 文档索引](index.html)
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
| Python | **3.8～3.11** | 勿用 3.12+（gevent 23 栈；Tier 2 其余项见 [依赖升级 RFC](依赖升级RFC.html)） |
| 数据库 | MySQL 5.7+ / 8 | 生产推荐；试用可用 SQLite |
| Redis | 可选 | 多实例集群锁；单机设 `is_single=1` |
| 端口 | **5860** | `gun.py` 默认；本地脚本常用 5001 |

## 3. 安装步骤

### 3.1 Linux 一键安装（Ubuntu / CentOS 7·8，推荐）

自动识别发行版、**自动创建虚拟环境**（`.venv-py*`）。生产用 MySQL；试用加 `--sqlite`。

| 场景 | 命令 |
| --- | --- |
| 生产 MySQL | `sudo bash scripts/install_linux.sh --production` → 编辑 conf.ini → `bash scripts/run_production.sh` |
| 试用 SQLite | `sudo bash scripts/install_linux.sh --production --sqlite` → `bash scripts/run_production.sh` |

速查：[INSTALL.md](../INSTALL.md) · [linux](linux安装与运行.md) · [ubuntu](ubuntu安装与运行.md) · [centos](centos安装与运行.md)

```
git clone git@github.com:sharepusher/CronPilot.git
cd CronPilot
sudo bash scripts/install_linux.sh --production
bash scripts/run_production.sh
```

### 3.2 手动安装（macOS / 自定义）

```
bash scripts/cronpilot.sh install
bash scripts/install_production_deps.sh
cp conf.ini.example conf.ini
```

Python 3.8～3.11；`run_production.sh` 自动使用 venv。

### 3.3 配置 conf.ini

必改项：`login_pwd`（**仅**空库种子 `admin` 的初始密码）、`cron_db_url`、`cron_job_log_db_url`、Redis（若集群）。日常改密见下表「认证」说明，勿在有用户后指望改 `login_pwd`。

生成**初始**密码哈希（写入 `login_pwd`，须在空库首次启动前）：

```
python scripts/hash_login_password.py '你的强密码'
# 将输出写入 conf.ini 的 login_pwd=
```

### 3.4 MySQL 示例

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

升级 **OPT-P2-12 Resource Scope** 时，须为业务库建 `resource_groups` / `user_groups` 并为 `cron_infos` 增加 `scope_type`/`group_id`（SQL 见 [资源隔离与 Scope 设计 §十](资源隔离与Scope设计.html)）。SQLite 由 `ensure_sqlite_tables.py` 自动补列。

### 3.5 SQLite 单机试用

```
cron_db_url=sqlite:////opt/cronpilot/datas/cron.sqlite
cron_job_log_db_url=sqlite:////opt/cronpilot/datas/job_log.sqlite
```

路径请使用**绝对路径**（四个斜杠 `sqlite:////`）。

## 4. 启动服务

### 4.1 生产（Gunicorn，监听外网）

```
cd /opt/cronpilot/CronPilot
bash scripts/run_production.sh
export FLASK_CONFIG=production

gunicorn -c gun.py manage:app
# gun.py 已配置 bind = '0.0.0.0:5860'
```

### 4.2 本地冒烟

```
bash scripts/start_local.sh
# 默认 127.0.0.1:5001；远程调试可改 host 为 0.0.0.0
```

### 4.3 访问地址

| 用途 | URL | 认证 |
| --- | --- | --- |
| Web 管理端 | `http://<IP>:5860/` | 用户名 + 密码（`rbac_users`）。空库种子 `admin`/`login_pwd`；日常改密：用户管理 → 编辑 → 新密码 |
| REST API | `http://<IP>:5860/api/...` | `api_access_token` 等 |
| HTML 技术文档 | `http://<IP>:5860/docs/` | **无登录** |

文档索引：`/docs/` → `doc/index.html`；子页如 `/docs/架构设计文档.html`。

## 5. 防火墙与健康检查

```
sudo ufw allow 5860/tcp

curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5860/docs/
# 期望 200

python -m unittest tests.test_p0_phase_a tests.test_cronpilot_sign -v
```

## 6. systemd（可选）

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

## 7. Nginx 反代 + HTTPS

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

## 8. 安全建议

- 生产必须使用**强密码**或 `pbkdf2` 哈希，禁止默认口令。
- `/docs/` **无需登录**，含架构与 API 细节；公网请用 Nginx 白名单 / Basic Auth / 仅内网。
- 保持 `block_private_ip=1`，按需配置 `url_allow_hosts`。
- 勿对 `0.0.0.0` 使用 `debug=True` 的 Flask 内置服务器。

## 9. 常见问题

| 现象 | 处理 |
| --- | --- |
| `pip install gevent` 失败 | 换 3.9/3.10；或本地用 `bash scripts/start_local.sh`（core 依赖）。长期方案：[依赖升级 RFC](依赖升级RFC.html) Tier 2 |
| 数据库迁移 CLI | `export FLASK_APP=manage:app` 后 `flask db migrate` / `flask db upgrade`（Py3.11 可用；见 [依赖升级 RFC](依赖升级RFC.html) Tier 0） |
| 外网无法访问 | 确认 Gunicorn `0.0.0.0`、防火墙、云安全组放行 5860 |
| `/docs/` 404 | 确认已部署含 `app/docs/` 的版本并重启进程 |
| 调度不触发 | 检查 `cron_db_url`、APScheduler 库表、`is_single` / Redis |

## 10. 相关文档

- [文档索引](index.html)
- [依赖升级 RFC](依赖升级RFC.html)（Tier 0～4 分层路线、与 RBAC 排期）
- [架构设计文档](架构设计文档.html)（部署拓扑、集群）
- [详细技术方案](详细技术方案.html)（配置项、API）
- [P0 测试与验收](P0测试用例与验收手册.html)
- 仓库 `README.md` 快速开始章节

CronPilot · 非 Docker 部署 · v0.1.0 · [Markdown 版](非Docker部署指南.md) · [文档索引](index.html)

---

[← 文档索引（HTML）](index.html) · [← 文档索引（Markdown）](index.md)
