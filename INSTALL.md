# CronPilot · Linux 安装指南（Ubuntu + CentOS 7/8）

## 数据库怎么选？

| 场景 | 推荐 | 说明 |
|------|------|------|
| **生产 / 正式环境** | **MySQL** | `conf.ini.example` 默认即 MySQL；支持多节点、`is_single=0` 时与 Redis 配合 |
| **本地试用 / 验收** | SQLite | 加 `--sqlite`，**无需安装 MySQL**，装完即可访问 `:5860` |

INSTALL.md 里曾把 `--sqlite` 写在最前面，是为了降低「第一次跑起来」的门槛，**不代表生产也用 SQLite**。生产请用下方 **MySQL 安装**。

---

## 一键安装 · 生产（MySQL，推荐）

### 1. 安装应用与 Python 依赖

```bash
git clone https://github.com/sharepusher/CronPilot.git
cd CronPilot
sudo bash scripts/install_linux.sh --production
```

`install_linux.sh` 会自动识别发行版：

| 检测到 | 脚本 | Python |
|--------|------|--------|
| Ubuntu / Debian | `install_ubuntu.sh` | apt 安装 3.8–3.11 |
| CentOS 7 | `install_centos.sh` | SCL `rh-python38` |
| CentOS 8 / Rocky / Alma | `install_centos.sh` | `python39` |

### 2. 准备 MySQL

在目标机安装 MySQL 5.7+ / 8.0，并创建库与用户（示例）：

```sql
CREATE DATABASE cron_scheduler CHARACTER SET utf8mb4;
CREATE DATABASE cron_job_log CHARACTER SET utf8mb4;
CREATE USER 'cronpilot'@'localhost' IDENTIFIED BY '强密码';
GRANT ALL ON cron_scheduler.* TO 'cronpilot'@'localhost';
GRANT ALL ON cron_job_log.* TO 'cronpilot'@'localhost';
FLUSH PRIVILEGES;
```

### 3. 编辑 `conf.ini`

```bash
cp conf.ini.example conf.ini   # 若安装脚本已生成可跳过
nano conf.ini
```

```ini
is_single=1
cron_db_url=mysql+pymysql://cronpilot:强密码@127.0.0.1:3306/cron_scheduler
cron_job_log_db_url=mysql+pymysql://cronpilot:强密码@127.0.0.1:3306/cron_job_log
login_pwd=请改为强密码
```

生成密码哈希（推荐）：

```bash
bash scripts/cronpilot.sh exec python scripts/hash_login_password.py '你的强密码'
```

### 4. 启动

```bash
bash scripts/run_production.sh
```

---

## 一键安装 · 试用（SQLite，无需 MySQL）

适合：功能验收、演示、单机 POC。**不建议用于生产**（并发、备份、集群能力弱于 MySQL）。

```bash
git clone https://github.com/sharepusher/CronPilot.git
cd CronPilot
sudo bash scripts/install_linux.sh --production --sqlite
bash scripts/run_production.sh
```

`--sqlite` 会自动写入：

- `datas/cron.sqlite`、`datas/job_log.sqlite`
- `is_single=1`
- 默认登录密码 `changeme`（**请立即修改** `conf.ini`）

---

## 分平台文档

- [doc/linux安装与运行.md](doc/linux安装与运行.md)
- [doc/ubuntu安装与运行.md](doc/ubuntu安装与运行.md)
- [doc/centos安装与运行.md](doc/centos安装与运行.md)

## 检查 Python

```bash
bash scripts/check_python_all.sh   # 含 CentOS SCL 路径
bash scripts/cronpilot.sh check
```

## 防火墙

**Ubuntu：** `sudo ufw allow 5860/tcp`

**CentOS / RHEL：**

```bash
sudo firewall-cmd --permanent --add-port=5860/tcp
sudo firewall-cmd --reload
```

## 访问

- 管理端：`http://<IP>:5860/`
- 技术文档：`http://<IP>:5860/docs/`
