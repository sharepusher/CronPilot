# v0.1.1 补充：Ubuntu 安装与运行

（请合并进 `RELEASE_NOTES.md` 的 `[0.1.1]` 章节，位于「Python 3.8–3.11」与「CI」之间。）

### Ubuntu 安装与运行（20.04 / 22.04 / 24.04）

| 脚本 / 文档 | 说明 |
|-------------|------|
| `scripts/install_ubuntu.sh` | 一键安装系统包（`build-essential`、`libev-dev`、`python3.8–3.11`）与 Python 依赖 |
| `scripts/bootstrap_venv.sh` | 创建 `.venv-py*` 并安装 `requirements-core.txt` |
| `scripts/install_production_deps.sh` | 安装 Gunicorn + gevent（Ubuntu 需 `libev-dev`） |
| `scripts/run_production.sh` | 生产启动 `0.0.0.0:5860` |
| `scripts/systemd/cronpilot.service.example` | systemd 单元模板 |
| `doc/ubuntu安装与运行.md` | Ubuntu 分步说明与排错 |

**试用（SQLite，无需 MySQL）：**

```bash
sudo bash scripts/install_ubuntu.sh --production --sqlite
bash scripts/run_production.sh
```

访问：`http://<服务器IP>:5860/` · 文档 `http://<IP>:5860/docs/`（默认密码 `changeme`，请修改 `conf.ini`）。
