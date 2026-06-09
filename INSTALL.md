# CronPilot · Linux 安装指南（Ubuntu + CentOS 7/8）

## 一键安装（推荐）

```bash
git clone https://github.com/sharepusher/CronPilot.git
cd CronPilot
sudo bash scripts/install_linux.sh --production --sqlite
bash scripts/run_production.sh
```

`install_linux.sh` 会自动识别发行版并调用对应脚本。

| 检测到 | 脚本 | Python |
|--------|------|--------|
| Ubuntu / Debian | `install_ubuntu.sh` | apt 安装 3.8–3.11 |
| CentOS 7 | `install_centos.sh` | SCL `rh-python38` |
| CentOS 8 / Rocky / Alma | `install_centos.sh` | `python39` |

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
- `--sqlite` 试用默认密码 `changeme`（请修改 `conf.ini`）
