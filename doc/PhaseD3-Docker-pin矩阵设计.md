# CronPilot · Phase D3 · Docker pin 矩阵设计

> HTML 版：[PhaseD3-Docker-pin矩阵设计.html](PhaseD3-Docker-pin矩阵设计.html) · [文档索引](index.html) · [索引 Markdown](index.md)

[← 文档索引](index.html)
OPT-P2-11Phase D3部分交付

# Phase D3 · Docker / pip show 矩阵

Framework Generation 运行时硬门：容器内 pin 与 requirements 一致

状态：D3-1 ✓ · D3-2/D3-3 **暂缓**（Docker 环境问题，2026-07-20 用户确认先不验 compose）

**D3-1 已交付（2026-07-20）：**
`scripts/assert_framework_pins.py` + `scripts/assert_framework_pins.sh`；
本地 `.venv-py311` 8/8 pin OK；故意错版本路径返回 exit 1。

**D3-2 / D3-3 暂缓（2026-07-20）：**用户确认本机 Docker 有问题，**先不进行 Docker / compose 验证**。
pin 断言已挂入 `verify_docker_compose.sh`，但**不得**将 Phase D3 整体标为已交付，直至：
`bash scripts/verify_docker_compose.sh --rebuild` 实测通过并完成 NOTICE/路线图收尾（D3-3）。

**定位：**属 **OPT-P2-11** · Framework Generation 子阶段 **Phase D3**
（见 [Phase D0](PhaseD0-Framework-Generation决策.html) 验收契约 #4）。
闭合「声明 pin」与「Docker 镜像实际安装」之间的缺口。

## 一、问题 / 根因 / 方案

| 项 | 内容 |
| --- | --- |
| 问题 | Phase D1 已 pin Flask 2.3.3 / SA 2.0.36 / FSA 3.1.1 等；本地 `cronpilot.sh test` 与 `verify_all --local-only` 已绿。 现有 `verify_docker_compose.sh` 只断言 gevent/gunicorn/apscheduler **可 import**，**不比对** Framework Generation 核心 pin。 镜像层缓存或安装路径漂移时，可能出现「文档已升、容器仍旧栈」。 |
| 根因 | 三套真相（requirements / 本地 venv / Docker 镜像）未焊死；D0 刻意把 compose + `pip show` 留到 D3，避免与 pin/Mapped 同窗。 |
| 方案 | 新增可复用的容器内 pin 断言（从 `requirements.txt` 读期望版本）→ 挂入 compose 黄金路径 → 核对 `THIRD_PARTY_NOTICES.md` → 文档标 Phase D3 已交付。 |

## 二、范围

| 做 | 不做 |
| --- | --- |
| - 脚本：容器内 `pip show`（或等价）断言核心包版本 - 接入 `verify_docker_compose.sh`（建议 `--rebuild` 时必跑） - `verify_all.sh --docker-only --with-compose` 路径覆盖该断言 - 核对/微调 `THIRD_PARTY_NOTICES.md` 与 pin 一致 - RELEASE / 交付状态 / D0·RFC 状态更新 | - Flask 3 / Python 3.12+ / 再 bump 主依赖 - Tier 3b/3c 生产库迁移 - OPT-P1-\* 功能 - 强制改 Dockerfile 结构（仅当断言失败且根因在镜像安装时最小修复） - 把 install-full 三发行版矩阵全部重跑（可选后续，非本窗必达） |

## 三、断言 pin 清单（D3 硬门）

以仓库根 `requirements.txt` 为准（与 Phase D1 同窗集合）。容器内版本必须**精确相等**：

| 包 | 期望（当前） |
| --- | --- |
| Flask | 2.3.3 |
| Werkzeug | 2.3.8 |
| Jinja2 | 3.1.6 |
| SQLAlchemy | 2.0.36 |
| Flask-SQLAlchemy | 3.1.1 |
| alembic | 1.14.1 |
| Flask-Migrate | 4.0.7 |
| blinker | 1.8.2 |

实现时从 `requirements.txt` **解析**上述包的 `==` 版本，避免脚本内再写死一份（防双源漂移）。包名列表可维护在脚本常量中。

## 四、分批

| 批 | 内容 | 可独立验收 |
| --- | --- | --- |
| **D3-1** ✓ | 新增 `scripts/assert_framework_pins.sh` / `.py`： 支持本地 venv；读 requirements → `pip show` → 失败打印 diff。 | 本地 venv：8/8 OK（2026-07-20） |
| **D3-2** 暂缓 | 挂入 `verify_docker_compose.sh`（脚本已合入）。 *2026-07-20：用户确认 Docker 有问题，跳过 compose 实测。* | 恢复 Docker 后补跑 `--rebuild` |
| **D3-3** 暂缓 | 核对 NOTICE；RELEASE / 交付状态 / D0·RFC 标 Phase D3 已交付； `html_docs_to_markdown.py --check`。依赖 D3-2 实测通过后才做。 | 待 D3-2 |

## 五、验收门禁

| # | 门禁 |
| --- | --- |
| 1 | 本地：`bash scripts/assert_framework_pins.sh`（或等价）对开发 venv 通过 |
| 2 | `bash scripts/verify_docker_compose.sh --rebuild --keep-running`（或 verify\_all docker compose 节）通过，且日志含 pin 断言 OK |
| 3 | 容器内抽查：`pip show Flask SQLAlchemy Flask-SQLAlchemy` 与 requirements 一致 |
| 4 | `THIRD_PARTY_NOTICES.md` 上述包版本一致 |
| 5 | 文档同步 + `html_docs_to_markdown.py --check` |

## 六、风险与注意

- Docker 不可用时：D3-2 无法在本机完成 → 不得宣称 Phase D3 已交付；可只合 D3-1 并标明「compose 待 CI/有 Docker 的环境」。
- 断言失败优先查：未 `--rebuild`、install 脚本装的是 core 而非 full、`CRONPILOT_VENV` 指错。
- 不扩大到 centos/ubuntu 多 Dockerfile 全矩阵（那是可选加固，非本窗必达）。

**确认方式：**请回复「按 Phase D3 设计执行」或列出修改点。
确认前**不**新增断言脚本、不改 verify\_\*、不改「已交付」文档状态。

[Phase D0](PhaseD0-Framework-Generation决策.html) ·
[依赖升级 RFC](依赖升级RFC.html) ·
[交付状态](交付状态与路线图.html) ·
[编号规范](需求编号与缩写规范.html)

CronPilot · Phase D3 设计 · 待确认 2026-07-20 · [索引](index.html) · [Markdown](PhaseD3-Docker-pin矩阵设计.md) · [索引](index.html)

---

[← 文档索引（HTML）](index.html) · [← 文档索引（Markdown）](index.md)
