# cron-scheduler-admin

中心化 **HTTP 定时回调调度台**：到点向业务 `req_url` 发起 GET，支持 Web 管理、REST API 动态改任务、秒级 Cron、集群双锁与执行日志。

本项目在 [aniu-lee/xiaoniu_cron](https://github.com/aniu-lee/xiaoniu_cron) 基础上独立演进，完成 **Phase A（P0）** 安全与质量改造及完整技术文档，**不向原仓库强推合并**。

## 与原版差异（Phase A / P0）

| 能力 | 说明 |
|------|------|
| SQL 安全 | 删除任务/清理日志改为 SQLAlchemy ORM，消除拼接 SQL |
| 登录安全 | 支持 `login_pwd` 明文（兼容）与 `pbkdf2` 哈希 |
| SSRF 防护 | `block_private_ip`、`url_allow_hosts`、执行前二次校验 |
| API 契约 | 统一 `errcode` 数字类型；修复前端 `requests.js` 判断 |
| 校验统一 | `cron_validator` + `cron_service`，Web/API 单一路径 |

后续路线图见 `doc/产品优化需求-借鉴Plombery.html`（P1 可观测、P2 体验）。

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

### 2. 依赖（Python 3.8～3.11）

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# 若 gevent 安装失败，可用 scripts/start_local.sh（核心依赖子集）
```

### 3. 启动

```bash
bash scripts/start_local.sh
# 或
export FLASK_CONFIG=development
python -c "from app import create_app; create_app('development').run(host='127.0.0.1', port=5001)"
```

浏览器打开：`http://127.0.0.1:5001/`，密码为 `conf.ini` 中的 `login_pwd`。

### 4. 测试

```bash
python -m unittest tests.test_p0_phase_a -v
```

手工冒烟与用例表见：**[doc/P0测试用例与验收手册.html](doc/P0测试用例与验收手册.html)**

## 技术文档（HTML）

在浏览器中打开 **`doc/index.html`**：

- 架构设计、详细技术方案、前端设计
- Plombery 深度对比、详版 PRD
- P0 测试手册、仓库拆分方案

## 目录结构

```
app/
  services/          # cron_validator、cron_service、url_security、job_log_service
  auth/              # 密码哈希校验
  main/              # Web 管理端
  api/               # REST API
doc/                 # 技术文档（HTML）
tests/               # P0 单元测试
scripts/             # 本地启动、密码哈希工具
```

## 配置项（P0 新增）

| 键 | 默认 | 说明 |
|----|------|------|
| `block_private_ip` | `1` | 禁止回调内网/本机/元数据地址 |
| `url_allow_hosts` | 空 | 非空时仅允许列出的主机（逗号分隔） |
| `url_ssrf_observe_only` | `0` | `1` 时仅记录不拦截（灰度） |

## 许可证与致谢

沿用原项目开源协议。感谢 [xiaoniu_cron](https://github.com/aniu-lee/xiaoniu_cron) 作者与社区。

## 仓库关系

- **本仓库**：`cron-scheduler-admin` — 持续开发
- **上游参考**：`aniu-lee/xiaoniu_cron` — 只读对照，可选 cherry-pick 原仓库修复
