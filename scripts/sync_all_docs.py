#!/usr/bin/env python3
"""同步 Linux 安装 / venv / Docker 验证相关文档（可 sudo 运行以更新 root 属主文件）。"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


PENDING = ROOT / "doc" / "_pending_sync"
MANIFEST_NAME = "pending_apply.manifest"


def _append_manifest(rel: Path) -> None:
    """登记待 sudo 合并的相对路径（勿登记目录说明/归档文件）。"""
    PENDING.mkdir(parents=True, exist_ok=True)
    manifest = PENDING / MANIFEST_NAME
    line = f"{rel.as_posix()}\n"
    existing = manifest.read_text(encoding="utf-8") if manifest.exists() else ""
    if line not in existing:
        with manifest.open("a", encoding="utf-8") as f:
            f.write(line)


def write(path: Path, content: str) -> None:
    try:
        path.write_text(content, encoding="utf-8")
        print(f"updated {path.relative_to(ROOT)}")
    except PermissionError:
        rel = path.relative_to(ROOT)
        dest = PENDING / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        _append_manifest(rel)
        print(f"pending {rel} -> doc/_pending_sync/{rel} (see {MANIFEST_NAME})")


def patch_file(path: Path, old: str, new: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        if new.split("\n", 1)[0] in text:
            print(f"skip (already patched) {path.relative_to(ROOT)}")
            return False
        raise SystemExit(f"patch miss in {path}: {old[:60]}...")
    write(path, text.replace(old, new, 1))
    return True


LINUX_INSTALL_BLOCK_MD = """### 3.1 Linux 一键安装（Ubuntu / CentOS 7·8，推荐）

自动识别发行版、**自动创建虚拟环境**（`.venv-py*`），无需手动 `source activate` 即可用 `run_production.sh` 启动。

| 场景 | 命令 |
| --- | --- |
| **生产（MySQL）** | `sudo bash scripts/install_linux.sh --production` → 编辑 `conf.ini` → `bash scripts/run_production.sh` |
| **试用（SQLite）** | `sudo bash scripts/install_linux.sh --production --sqlite` → `bash scripts/run_production.sh` |

速查：[INSTALL.md](../INSTALL.md) · 分平台：[linux安装与运行.md](linux安装与运行.md) · [ubuntu安装与运行.md](ubuntu安装与运行.md) · [centos安装与运行.md](centos安装与运行.md)

安装链路：`install_linux.sh` → `bootstrap_venv.sh` → `install_production_deps.sh`（同一 venv）。

```
git clone git@github.com:sharepusher/CronPilot.git
cd CronPilot
sudo bash scripts/install_linux.sh --production
bash scripts/check_python_all.sh
bash scripts/run_production.sh
```

### 3.2 手动安装（macOS 或自定义环境）

```
git clone git@github.com:sharepusher/CronPilot.git
cd CronPilot

bash scripts/cronpilot.sh check
bash scripts/cronpilot.sh install
bash scripts/install_production_deps.sh

cp conf.ini.example conf.ini
mkdir -p datas/logs
```

支持 **Python 3.8～3.11**。`run_production.sh` 自动使用 venv，一般不必 `source activate`。
"""

OLD_INSTALL_MD = """### 3.1 获取代码与虚拟环境

```
git clone git@github.com:sharepusher/CronPilot.git
cd CronPilot

bash scripts/check_python.sh
bash scripts/install_core_deps.sh
# 或指定: PY=python3.9 bash scripts/install_core_deps.sh
source .venv-py310/bin/activate   # 目录随版本变化，如 .venv-py38
pip install -r requirements.txt   # 生产 Gunicorn 需全量依赖

cp conf.ini.example conf.ini
mkdir -p datas/logs
```

支持 **Python 3.8 / 3.9 / 3.10 / 3.11**；本地冒烟可用 `requirements-core.txt`（`start_local.sh` 已内置）。
"""

LINUX_INSTALL_BLOCK_HTML = """    <h3>3.1 Linux 一键安装（Ubuntu / CentOS 7·8，推荐）</h3>
    <p>自动识别发行版、<strong>自动创建虚拟环境</strong>（<code>.venv-py*</code>）。生产用 MySQL；试用加 <code>--sqlite</code>。</p>
    <table>
      <tr><th>场景</th><th>命令</th></tr>
      <tr><td>生产 MySQL</td><td><code>sudo bash scripts/install_linux.sh --production</code> → 编辑 conf.ini → <code>bash scripts/run_production.sh</code></td></tr>
      <tr><td>试用 SQLite</td><td><code>sudo bash scripts/install_linux.sh --production --sqlite</code> → <code>bash scripts/run_production.sh</code></td></tr>
    </table>
    <p class="formats" style="font-size:.88rem">速查：<a href="../INSTALL.md">INSTALL.md</a> · <a href="linux安装与运行.md">linux</a> · <a href="ubuntu安装与运行.md">ubuntu</a> · <a href="centos安装与运行.md">centos</a></p>
    <pre>git clone git@github.com:sharepusher/CronPilot.git
cd CronPilot
sudo bash scripts/install_linux.sh --production
bash scripts/run_production.sh</pre>
    <h3>3.2 手动安装（macOS / 自定义）</h3>
    <pre>bash scripts/cronpilot.sh install
bash scripts/install_production_deps.sh
cp conf.ini.example conf.ini</pre>
    <p style="color:var(--muted);font-size:.9rem">Python 3.8～3.11；<code>run_production.sh</code> 自动使用 venv。</p>
"""

OLD_INSTALL_HTML = """    <h3>3.1 获取代码与虚拟环境</h3>
    <pre>git clone git@github.com:sharepusher/CronPilot.git
cd CronPilot

bash scripts/check_python.sh
bash scripts/install_core_deps.sh
# 或指定: PY=python3.9 bash scripts/install_core_deps.sh
source .venv-py310/bin/activate   # 目录随版本变化，如 .venv-py38
pip install -r requirements.txt   # 生产 Gunicorn 需全量依赖

cp conf.ini.example conf.ini
mkdir -p datas/logs</pre>
    <p style="color:var(--muted);font-size:.9rem">支持 <strong>Python 3.8 / 3.9 / 3.10 / 3.11</strong>；本地冒烟可用 <code>requirements-core.txt</code>（<code>start_local.sh</code> 已内置）。</p>
"""

INDEX_MD_EXTRA = """
| Linux 安装总览 | — | [linux安装与运行.md](linux安装与运行.md) |
| Ubuntu 安装与运行 | — | [ubuntu安装与运行.md](ubuntu安装与运行.md) |
| CentOS 安装与运行 | — | [centos安装与运行.md](centos安装与运行.md) |
| 仓库安装速查 | — | [INSTALL.md](../INSTALL.md) |
"""

RELEASE_LINUX_BLOCK = """
### Linux 安装与运行（Ubuntu + CentOS 7/8）

| 脚本 / 文档 | 说明 |
| --- | --- |
| `scripts/install_linux.sh` | 统一入口，自动识别发行版 |
| `scripts/install_ubuntu.sh` / `install_centos.sh` | 分平台一键安装 |
| `scripts/bootstrap_venv.sh` | 自动 `.venv-py*` + 核心依赖 |
| `scripts/install_production_deps.sh` | 同一 venv 安装 Gunicorn + gevent |
| `scripts/run_production.sh` | 生产启动（无需手动 activate） |
| `scripts/docker/verify_all.sh` | Docker 验收 Ubuntu / Rocky8 / CentOS7 |
| [INSTALL.md](../INSTALL.md) | 安装速查（MySQL 生产 / SQLite 试用） |

```bash
sudo bash scripts/install_linux.sh --production
bash scripts/run_production.sh
```

### Docker 安装验收 CI

- 工作流：`.github/workflows/docker-install-verify.yml`
- 矩阵构建验证 venv + gunicorn + `/docs/`（SQLite 试用路径）

"""


def patch_readme() -> None:
    path = ROOT / "README.md"
    text = path.read_text(encoding="utf-8")
    if "install_linux.sh" in text and "INSTALL.md" in text:
        print("skip README (linux section present)")
        return
    old = """### 安装

```bash
git clone https://github.com/sharepusher/CronPilot.git
cd CronPilot

bash scripts/check_python.sh
bash scripts/install_core_deps.sh   # 或 PY=python3.8 bash scripts/install_core_deps.sh
source .venv-py*/bin/activate       # 按实际目录名，如 .venv-py310
pip install -r requirements.txt     # 生产需 gevent 时用全量依赖

cp conf.ini.example conf.ini
mkdir -p datas/logs
# 编辑 conf.ini：cron_db_url、cron_job_log_db_url、login_pwd、redis、SSRF 等
python scripts/hash_login_password.py '强密码'   # 推荐写入 login_pwd
```"""
    new = """### 安装

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
```"""
    if old not in text:
        raise SystemExit("README install section not found")
    text = text.replace(old, new, 1)
    text = text.replace(
        """### 启动服务（监听外网）

```bash
cd /opt/cronpilot/CronPilot
source .venv/bin/activate
export FLASK_CONFIG=production

# 前台（调试）
gunicorn -c gun.py manage:app

# 或指定绑定（与 gun.py 一致：0.0.0.0:5860）
gunicorn -b 0.0.0.0:5860 -w 2 -k gevent manage:app
```""",
        """### 启动服务（监听外网）

```bash
cd /opt/cronpilot/CronPilot
bash scripts/run_production.sh
# 内部使用 .venv-py*/bin/gunicorn，监听 0.0.0.0:5860
```""",
        1,
    )
    fw_old = """### 防火墙

```bash
sudo ufw allow 5860/tcp
```"""
    fw_new = """### 防火墙

**Ubuntu：** `sudo ufw allow 5860/tcp`

**CentOS / RHEL：** `sudo firewall-cmd --permanent --add-port=5860/tcp && sudo firewall-cmd --reload`

**Docker 验收（可选）：** `bash scripts/docker/verify_all.sh all`"""
    if fw_old in text:
        text = text.replace(fw_old, fw_new, 1)
    write(path, text)


def patch_release_notes_root() -> None:
    path = ROOT / "RELEASE_NOTES.md"
    text = path.read_text(encoding="utf-8")
    marker = "### CI（GitHub Actions）"
    if "Linux 安装与运行（Ubuntu + CentOS" in text:
        print("skip RELEASE_NOTES.md (linux section present)")
        return
    if marker not in text:
        raise SystemExit("RELEASE_NOTES marker not found")
    text = text.replace(marker, RELEASE_LINUX_BLOCK.strip() + "\n\n" + marker, 1)
    ci_old = "| install-full | 在 3.10 安装完整 `requirements.txt` 验证 gevent 等 |"
    ci_new = ci_old + "\n| Docker install verify | 矩阵 Ubuntu / Rocky8 / CentOS7 完整安装 + venv + gunicorn |"
    if ci_old in text:
        text = text.replace(ci_old, ci_new, 1)
    write(path, text)


def patch_index_md() -> None:
    path = ROOT / "doc" / "index.md"
    text = path.read_text(encoding="utf-8")
    if "linux安装与运行" in text:
        print("skip doc/index.md")
        return
    text = text.replace(
        "| 非 Docker 部署指南 |",
        "| Linux 安装总览 | — | [linux安装与运行.md](linux安装与运行.md) |\n| Ubuntu 安装 | — | [ubuntu安装与运行.md](ubuntu安装与运行.md) |\n| CentOS 安装 | — | [centos安装与运行.md](centos安装与运行.md) |\n| 安装速查 INSTALL | — | [INSTALL.md](../INSTALL.md) |\n| 非 Docker 部署指南 |",
        1,
    )
    text = text.replace("*CronPilot · 技术文档 · v0.1.0*", "*CronPilot · 技术文档 · v0.1.1*")
    text = text.replace(
        "- [README.md](../README.md) — 快速开始与非 Docker 部署摘要",
        "- [README.md](../README.md) — 快速开始与非 Docker 部署摘要\n- [INSTALL.md](../INSTALL.md) — Linux 安装速查（Ubuntu + CentOS、venv、MySQL/SQLite）",
        1,
    )
    write(path, text)


def patch_index_html() -> None:
    path = ROOT / "doc" / "index.html"
    text = path.read_text(encoding="utf-8")
    if "linux安装与运行" in text:
        print("skip doc/index.html")
        return
    card = """
    <div class="card featured" style="border-color:#059669">
      <h2><a href="linux安装与运行.md">Linux 安装与运行（Ubuntu + CentOS）</a></h2>
      <p><span class="tag">运维</span><span class="tag">venv</span><span class="tag">一键安装</span></p>
      <p>install_linux.sh、虚拟环境、MySQL 生产 / SQLite 试用、Docker 验收。</p>
      <p class="formats"><a href="linux安装与运行.md">总览</a><a href="ubuntu安装与运行.md">Ubuntu</a><a href="centos安装与运行.md">CentOS</a><a href="../INSTALL.md">INSTALL</a></p>
    </div>
"""
    text = text.replace(
        '    <div class="card featured" style="border-color:#ea580c">',
        card + '    <div class="card featured" style="border-color:#ea580c">',
        1,
    )
    text = text.replace(
        "<p>v0.1.1：/docs/、Markdown、Python 自动匹配、CI；v0.1.0：Phase A P0。</p>",
        "<p>v0.1.1：Linux 安装、venv、Docker 验收、/docs/、Python 自动匹配；v0.1.0：Phase A P0。</p>",
        1,
    )
    write(path, text)


def patch_doc_release_notes() -> None:
    for name in ("doc/RELEASE_NOTES.md", "doc/RELEASE_NOTES.html"):
        path = ROOT / name
        text = path.read_text(encoding="utf-8")
        if "install_linux" in text:
            print(f"skip {name}")
            continue
        if name.endswith(".md"):
            insert = RELEASE_LINUX_BLOCK + "\n### CI\n\n- Docker install verify（Ubuntu / Rocky8 / CentOS7）\n"
            text = text.replace("### CI\n", insert, 1)
        else:
            block = """<h3>Linux 安装（Ubuntu + CentOS 7/8）</h3>
<ul>
<li><code>install_linux.sh</code> → 自动 <code>.venv-py*</code> → <code>run_production.sh</code></li>
<li><a href="../INSTALL.md">INSTALL.md</a> · <a href="linux安装与运行.md">linux</a> · <a href="ubuntu安装与运行.md">ubuntu</a> · <a href="centos安装与运行.md">centos</a></li>
<li>Docker 验收：<code>scripts/docker/verify_all.sh</code></li>
</ul>
"""
            text = text.replace("<h3>CI</h3>", block + "<h3>CI</h3>", 1)
        write(path, text)


def patch_agents() -> None:
    path = ROOT / "AGENTS.md"
    text = path.read_text(encoding="utf-8")
    if "install_linux" in text:
        print("skip AGENTS.md")
        return
    text = text.replace(
        "```bash\nbash scripts/cronpilot.sh start",
        "```bash\nsudo bash scripts/install_linux.sh --production   # Linux 裸机\nbash scripts/cronpilot.sh start",
        1,
    )
    write(path, text)


def patch_install_md() -> None:
    path = ROOT / "INSTALL.md"
    text = path.read_text(encoding="utf-8")
    if "docker/verify_all" in text:
        print("skip INSTALL.md docker section")
        return
    docker = """
## Docker 验收（可选）

在已安装 Docker 的环境验证完整安装链路（venv + gevent + gunicorn + `/docs/`）：

```bash
bash scripts/docker/verify_all.sh all
# 或: ubuntu | centos8 | centos7
```

CI 工作流：`.github/workflows/docker-install-verify.yml`。

"""
    text = text.rstrip() + "\n" + docker
    write(path, text)


def patch_cursor_rule() -> None:
    path = ROOT / ".cursor/rules/cronpilot-release-deploy.mdc"
    text = path.read_text(encoding="utf-8")
    if "install_linux" in text:
        print("skip cronpilot-release-deploy.mdc")
        return
    text = text.replace(
        "## 非 Docker 部署（标准路径）\n\n1. `cp conf.ini.example conf.ini`",
        "## 非 Docker 部署（标准路径）\n\n**Linux（Ubuntu / CentOS 7·8）：** `sudo bash scripts/install_linux.sh --production` → 配置 MySQL → `bash scripts/run_production.sh`。试用加 `--sqlite`。详见 `INSTALL.md`。\n\n1. `cp conf.ini.example conf.ini`",
        1,
    )
    text = text.replace(
        "2. `bash scripts/install_core_deps.sh`",
        "2. `bash scripts/cronpilot.sh install` 或 `bash scripts/install_core_deps.sh`（自动 `.venv-py*`）",
        1,
    )
    text = text.replace(
        "- CI：**Unit tests**",
        "- CI：**Unit tests**、**Docker install verify**（Ubuntu/Rocky8/CentOS7）",
        1,
    )
    write(path, text)


def main() -> None:
    md_path = ROOT / "doc" / "非Docker部署指南.md"
    md_text = md_path.read_text(encoding="utf-8")
    if OLD_INSTALL_MD in md_text:
        md_text = md_text.replace(OLD_INSTALL_MD, LINUX_INSTALL_BLOCK_MD, 1)
    elif "3.1 Linux 一键安装" not in md_text:
        raise SystemExit("非Docker部署指南.md: 无法定位安装段落")
    md_extra = md_path
    t = md_text
    for a, b in [
        ("### 3.2 配置 conf.ini", "### 3.3 配置 conf.ini"),
        ("### 3.3 MySQL 示例", "### 3.4 MySQL 示例"),
        ("### 3.4 SQLite 单机试用", "### 3.5 SQLite 单机试用"),
        ("v0.1.0 · [Markdown 版]", "v0.1.1 · [Markdown 版]"),
        (
            "cd /opt/cronpilot/CronPilot\nsource .venv/bin/activate\nexport FLASK_CONFIG=production\n\ngunicorn -c gun.py manage:app",
            "cd /opt/cronpilot/CronPilot\nbash scripts/run_production.sh",
        ),
        (
            "sudo ufw allow 5860/tcp\n\ncurl",
            "sudo ufw allow 5860/tcp\n\n**CentOS：** `sudo firewall-cmd --permanent --add-port=5860/tcp && sudo firewall-cmd --reload`\n\ncurl",
        ),
        (
            "python -m unittest tests.test_p0_phase_a tests.test_cronpilot_sign -v",
            "bash scripts/cronpilot.sh test\nbash scripts/docker/verify_all.sh all   # 可选 Docker 验收",
        ),
        (".venv/bin/gunicorn", ".venv-py311/bin/gunicorn"),
    ]:
        if a in t:
            t = t.replace(a, b, 1)
    write(md_extra, t)

    patch_file(ROOT / "doc" / "非Docker部署指南.html", OLD_INSTALL_HTML, LINUX_INSTALL_BLOCK_HTML)
    html_p = ROOT / "doc" / "非Docker部署指南.html"
    t = html_p.read_text(encoding="utf-8")
    for a, b in [
        ("<h3>3.2 配置 conf.ini</h3>", "<h3>3.3 配置 conf.ini</h3>"),
        ("<h3>3.3 MySQL 示例</h3>", "<h3>3.4 MySQL 示例</h3>"),
        ("<h3>3.4 SQLite 单机试用</h3>", "<h3>3.5 SQLite 单机试用</h3>"),
        (
            "cd /opt/cronpilot/CronPilot\nsource .venv/bin/activate",
            "cd /opt/cronpilot/CronPilot\nbash scripts/run_production.sh",
        ),
        (".venv/bin/gunicorn", ".venv-py311/bin/gunicorn"),
    ]:
        if a in t:
            t = t.replace(a, b, 1)
    write(html_p, t)

    patch_index_md()
    patch_index_html()
    patch_readme()
    patch_release_notes_root()
    patch_doc_release_notes()
    patch_agents()
    patch_install_md()
    patch_cursor_rule()
    patch_project_overview()
    patch_linux_guides()
    print("done.")
    if PENDING.exists() and (PENDING / MANIFEST_NAME).is_file():
        print("\n部分文件属 root，已写入 doc/_pending_sync/ 并登记 manifest。请执行:")
        print("  sudo bash scripts/apply_pending_docs.sh")
        print("（仅合并 manifest 中的路径；主文件若比副本新将自动跳过）")


def patch_project_overview() -> None:
    path = ROOT / "doc" / "项目总览与技术文档.md"
    text = path.read_text(encoding="utf-8")
    if "install_linux.sh" in text:
        print("skip 项目总览")
        return
    insert = """
### Linux 安装（Ubuntu + CentOS 7/8）

- 统一入口：`sudo bash scripts/install_linux.sh --production`（自动 `.venv-py*`）
- 速查：[INSTALL.md](../INSTALL.md) · [linux安装与运行.md](linux安装与运行.md)
- Docker 验收：`bash scripts/docker/verify_all.sh all`

"""
    text = text.replace(
        "[#### 非 Docker 部署指南",
        insert + "[#### 非 Docker 部署指南",
        1,
    )
    write(path, text)


def patch_linux_guides() -> None:
    linux = ROOT / "doc" / "linux安装与运行.md"
    text = linux.read_text(encoding="utf-8")
    if "verify_install_flow" in text:
        print("skip linux安装与运行.md extras")
        return
    extra = """
## 虚拟环境（自动）

一键安装会调用 `bootstrap_venv.sh` 创建 `.venv-py*`，`run_production.sh` 直接使用 venv 内 gunicorn，**无需** `source activate`。

## 生产 vs 试用

| 场景 | 命令 |
|------|------|
| 生产 MySQL | `sudo bash scripts/install_linux.sh --production` → 编辑 `conf.ini` |
| 试用 SQLite | 加 `--sqlite` |

详见 [INSTALL.md](../INSTALL.md)。

## 验证

```bash
bash scripts/verify_install_flow.sh
bash scripts/docker/verify_all.sh all   # 需 Docker
```
"""
    write(linux, text.rstrip() + "\n" + extra)


if __name__ == "__main__":
    main()
