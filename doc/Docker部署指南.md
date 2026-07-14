# CronPilot · Docker 部署指南

> HTML 版：[Docker部署指南.html](Docker部署指南.html) · [文档索引](index.html) · [索引 Markdown](index.md)

[← 文档索引](index.html)
运维
Docker

# Docker 部署指南

Ubuntu 22.04 镜像 · Python 3.10 · 默认 SQLite 试用 · 端口 `5860`

适用：**快速试用**、**不在宿主机装 Python**、或宿主机 **apt/dpkg 异常**（如 PostgreSQL 卡住）时。
镜像基于 Ubuntu 22.04 + Python 3.10，容器内自动执行 `install_ubuntu.sh --production --sqlite`。
裸机生产路径见 [非 Docker 部署指南](非Docker部署指南.html)。

## 1. 部署拓扑

宿主机 Docker
└── 容器 cronpilot (:5860)
├── Gunicorn + gevent → Flask 管理端 + API
├── /docs/ → 内置 HTML 技术文档
├── ./datas (volume) → SQLite + 日志
└── conf.ini (volume) → 配置

与裸机一致：**管理端与文档同一端口 `5860`**，无需 Nginx 即可内网访问。

## 2. 环境要求

| 组件 | 要求 |
| --- | --- |
| Docker | Docker Engine 20+ 或 Docker Desktop |
| Compose | Docker Compose v2（`docker compose`） |
| 宿主机 | 无需安装 Python / MySQL（试用 SQLite） |
| 端口 | 宿主机 **5860** 未被占用 |
| 运行时栈 | 镜像内 **Python 3.10 + gunicorn 22.0.0 + gevent 23.9.1**（勿期望 3.12+；Tier 2 已交付，见 [依赖升级 RFC](依赖升级RFC.html)） |

## 3. 快速开始（SQLite 试用）

首次启动前必须生成 `conf.ini`（**勿**直接 `cp conf.ci.ini`——其为内存库，Docker 下登录后会 `system error`）。推荐：

```
git clone https://github.com/sharepusher/CronPilot.git
cd CronPilot
python3 scripts/write_sqlite_conf.py \
  --out conf.ini --datas-dir datas --container-paths \
  --template conf.local.sqlite.example

docker compose up --build -d
```

也可 `cp conf.local.sqlite.example conf.ini` 后把路径改为容器内 `/opt/cronpilot/datas/*.sqlite`。若省略 `conf.ini`，Docker 可能把其挂载成目录导致启动失败。

| 项 | 值 |
| --- | --- |
| 管理端 | `http://<宿主机IP>:5860/` |
| 技术文档 | `http://<宿主机IP>:5860/docs/` |
| 默认登录 | 用户名 `admin` · 初始密码 = `login_pwd`（常为 `changeme`，**仅空库种子**） |
| 日常改密 | 管理端 **用户管理 → 编辑 → 新密码**；已有用户后改 `login_pwd` 并重启**不会**改库内密码 |

```
docker compose logs -f
docker compose down
```

## 4. 配置与数据持久化

`docker-compose.yml` 默认挂载：

| 宿主机路径 | 容器路径 | 说明 |
| --- | --- | --- |
| `./datas` | `/opt/cronpilot/datas` | SQLite 数据库、日志 |
| `./conf.ini` | `/opt/cronpilot/conf.ini` | 应用配置 |

修改配置后重启：

```
nano conf.ini
docker compose restart
```

## 5. 生产：容器 + MySQL

1. 在宿主机或独立服务器准备 MySQL，创建库与用户（见 [INSTALL.md](../INSTALL.md) 路径 B）。
2. 编辑宿主机 `conf.ini`：

```
is_single=1
cron_db_url=mysql+pymysql://cronpilot:密码@host.docker.internal:3306/cron_scheduler
cron_job_log_db_url=mysql+pymysql://cronpilot:密码@host.docker.internal:3306/cron_job_log
login_pwd=你的管理端初始密码（仅空库种子；日常改密走用户管理）
```

执行 `docker compose up -d`。

### MySQL 地址说明

| 环境 | `cron_db_url` 主机 |
| --- | --- |
| MySQL 在宿主机（Mac/Win Docker Desktop） | `host.docker.internal` |
| MySQL 在宿主机（Linux） | 宿主机网桥 IP 或 `172.17.0.1` |
| MySQL 在另一容器 | Compose 服务名，如 `mysql` |

## 6. 手动构建（不用 compose）

```
docker build -t cronpilot:latest .
docker run -d --name cronpilot \
  -p 5860:5860 \
  -v "$(pwd)/datas:/opt/cronpilot/datas" \
  -v "$(pwd)/conf.ini:/opt/cronpilot/conf.ini" \
  cronpilot:latest
```

等价 Dockerfile 副本：`scripts/docker/Dockerfile.run`（`docker build -f scripts/docker/Dockerfile.run .`）。

## 7. 镜像说明（v0.1.1+）

| 项目 | 说明 |
| --- | --- |
| 基础镜像 | `ubuntu:22.04` |
| Python | 3.10（deadsnakes PPA，容器内安装） |
| 虚拟环境 | `.venv-py39`（构建期创建） |
| 启动命令 | `bash scripts/run_production.sh` |
| 暴露端口 | **5860**（与裸机 `gun.py` 一致） |

构建期会自动跑健康检查（gunicorn 22 gevent worker）：`/docs/` 返回 HTML，`/` 返回 200 或 302。

`docker_start.sh`、`docker_gun.py`、`doc/supervisors.conf` 为旧 Supervisor 方案遗留，**新镜像不再使用**。

## 8. 与旧版 Docker 的区别

| 旧版（已废弃） | v0.1.1+ |
| --- | --- |
| Ubuntu 16.04 + Python 3.6 | Ubuntu 22.04 + Python 3.10 |
| 容器 `:80` → 宿主机 `5002` | 统一 **`:5860`** |
| Supervisor + `docker_start.sh` | 直接 `run_production.sh` |
| 豆瓣 pip 源 | 标准 `install_ubuntu.sh` |

`docker-compose.run.yml` 与 `docker-compose.yml` 内容相同，兼容旧命令 `-f docker-compose.run.yml`。

## 9. 开发者：CI 与本地验收

**Docker 声称「可用」须两条路径均通过**（缺一不可）：

| 路径 | 命令 | 验证什么 |
| --- | --- | --- |
| A · 隔离镜像 | `SMOKE_LEVEL=full bash scripts/verify_cronpilot_docker_mac.sh` | Dockerfile 构建 + 临时 conf |
| B · **用户黄金路径** | `bash scripts/verify_docker_compose.sh --keep-running` | **宿主机 `conf.ini` volume + 登录 + cron\_list** |

路径 B 才是 `docker compose up` 真实用法；路径 A 通过**不能**代替 B。

### 裸机安装脚本验收（非运行镜像）

在 Ubuntu / Rocky8 / CentOS7 容器内验证 `install_linux.sh` 链路：

```
bash scripts/docker/verify_all.sh all
```

GitHub Actions：`.github/workflows/docker-install-verify.yml`。

### Mac / 本地：compose 黄金路径（必跑）

```
bash scripts/verify_docker_compose.sh --keep-running
```

使用仓库根目录 `conf.ini`（勿为 `:memory:`），`docker compose up` 后 login + cron\_list 全量冒烟。

### 隔离镜像验收（补充，不能代替 compose）

```
bash scripts/verify_cronpilot_docker_mac.sh
```

扩展验收（含 login、cron\_list、`flask db`、容器内 gevent/gunicorn 版本）：

```
SMOKE_LEVEL=full bash scripts/verify_cronpilot_docker_mac.sh
```

构建根目录 `Dockerfile`，生成**临时 SQLite `conf.ini`**（不覆盖宿主机配置），启动容器并 curl `/docs/` 与 `/`。

## 10. 常见问题

| 现象 | 处理 |
| --- | --- |
| 登录后页面 `system error` / 日志 `no such table: cron_infos` | `conf.ini` 误用 `conf.ci.ini`（`:memory:`）或路径不对；执行 `python3 scripts/write_sqlite_conf.py --out conf.ini --datas-dir datas --container-paths`，容器内 `bash scripts/ensure_sqlite_tables.sh`，`docker compose restart` |
| `port is already allocated` | 改 `docker-compose.yml` 为 `"5861:5860"` 或释放 5860 |
| 容器启动后 502 / 无响应 | `docker compose logs`；确认 `conf.ini` 是文件且已正确挂载 |
| `conf.ini` 变成目录 | 删除该目录，`cp conf.ini.example conf.ini` 后重启 |
| 想清空试用数据 | `docker compose down` 后 `rm -rf datas/*.sqlite` |
| 宿主机 apt 坏了 | Docker 路径**不依赖**宿主机 apt 装 Python |
| 构建很慢 | 首次需 apt + pip，约 5–15 分钟；后续层有缓存 |

## 11. 相关文档

- [依赖升级 RFC](依赖升级RFC.html) — Tier 0～4 分层路线、Docker/Python 栈约束
- [INSTALL.md](../INSTALL.md) — 路径 A/B/C/D 总览
- [非 Docker 部署指南](非Docker部署指南.html) — 裸机生产、systemd、Nginx
- <ubuntu安装与运行.md> — Ubuntu 裸机分步
- <linux安装与运行.md> — Linux 安装总览

CronPilot · Docker 部署 · v0.1.1 ·
[Markdown 版](Docker部署指南.md) ·
[文档索引](index.html)

---

[← 文档索引（HTML）](index.html) · [← 文档索引（Markdown）](index.md)
