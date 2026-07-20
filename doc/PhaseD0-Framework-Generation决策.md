# CronPilot · Phase D0 · Framework Generation 决策

> HTML 版：[PhaseD0-Framework-Generation决策.html](PhaseD0-Framework-Generation决策.html) · [文档索引](index.html) · [索引 Markdown](index.md)

[← 文档索引](index.html)
依赖演进Phase D0已确认

# Phase D0 · Framework Generation 决策

Python 3.8–3.11 · Flask 2.3 线 + SA2/FSA3/Alembic 同窗 · DEC-008

状态：Confirmed · 2026-07-20 · **D1 pin bump 已交付**（Flask 2.3.3 + SA 2.0.36 + FSA 3.1.1）

**已确认包（2026-07-20）：**

- **A1** — Python **3.8–3.11**（与安装脚本 / 稳定栈口径一致；不默认 3.12+）。*修订 2026-07-20：撤回曾选的 A2（弃 3.8）；D1 pin 本身均 `Requires-Python ≥3.8`，保留 3.8 不影响 pin 选型。*
- **B1** — **Flask 2.3.x** + Werkzeug/Jinja/Click 对齐 + **SQLAlchemy 2.0.x** + **Flask-SQLAlchemy 3.1.x** + 匹配 Alembic/Flask-Migrate
- **同窗 bump** — Flask 链与 SA2/FSA3/Alembic 在同一 D1 依赖 PR（或紧密连续、不可单独合入的半升状态）
- **§5.1 不做** — 无 Flask-Login/WTF；无 3.12+；本窗不 bump gevent/gunicorn/APS 主版本
- 记入 [依赖升级 RFC](依赖升级RFC.html) **DEC-008**；**Phase D1 / D2 已落地**；下一步 **Phase D3（OPT-P2-11）**

**定位：**本页属 **OPT-P2-11** 下 Framework Generation 的**决策闸门**（Phase D0）。编号读法见 [需求编号与缩写规范](需求编号与缩写规范.html)。前置 Phase A/B/C 已交付。本页确认后仍**不自动改** `requirements*.txt` 中的 Flask/SA pin——那是 **Phase D1**。

## 一、Flask 2.3 与 Flask 3 的区别（为何选 B1）

### 1.1 版本线定位

| 维度 | Flask 2.3.x（B1） | Flask 3.x / 3.1（B2） |
| --- | --- | --- |
| 相对本仓库 | 从 **1.1.2** 升到 2.3：一次「代际跳跃」，但官方仍维护 2.3 行为模型 | 再跨一层主版本：清理 2.3 已弃用 API + Werkzeug 3 硬依赖 |
| Python | 官方 ≥3.8；与本仓 **3.8–3.11** 完全兼容 | 3.0.x 仍支持 3.8；**仅 3.1+**丢弃 3.8。本仓保留 3.8，故若日后选 B2 宜锁 **Flask 3.0.x** 或先弃 3.8；选 B1 的主因仍是回归面，非 Python 底线 |
| Werkzeug | 2.3.x 线 | **≥3.0**（与 Flask 3 强绑定；URL/路由/异常栈变化更多） |
| Jinja2 / Click / itsdangerous | 3.1+ / 8.1+ / 2.1+（随 2.3 抬升） | 继续抬升，与 Werkzeug 3 同生态 |
| 相对 1.1 的破坏面 | 已去掉：`FLASK_ENV`、`before_first_request`、旧 JSON 配置键、部分 `app.` 属性快捷方式等（2.3 已删） | 在 2.3 基础上再删：`_app_ctx_stack` / `_request_ctx_stack`、`flask.escape`/`Markup` 再导出、`locked_cached_property`、`signals_available` 等 |
| 与 FSA 3.1 | 满足 `Flask≥2.2.5`，可配 SA 2 | 同样满足，但多一层 Flask/Werkzeug 回归 |
| 风险/工期 | 中（推荐首跳） | 高（建议稳定运行 B1 后再评估） |

### 1.2 对本仓库的实际含义

- CronPilot 现为 **Flask 1.1.2**：无论 2.3 还是 3，都要过「去掉 1.x 废弃用法 + 会话/JSON/蓝图」回归。
- 自研 RBAC + signed cookie，不用 Flask-Login；表单不用 WTF——Flask 3 的「清理」对业务价值有限，却放大 Werkzeug 3 回归面。
- **B1** 已能解锁 FSA 3.1 + SA 2（本里程碑真正目标）；B2（Flask 3）不增加「能否升 ORM」能力。选 B1 是为控制 **Werkzeug 3 / 弃用清理** 的回归面，**不是**因为「Flask 3 全家不支持 Python 3.8」（3.0 仍支持 3.8；3.1+ 才丢 3.8）。

安全说明：Flask 2.3.2+ 含会话 Cookie 相关修复；D1 锁定具体补丁版时应取 **2.3 线最新安全补丁**（实施时再 pin，本 D0 不写死小版本）。

## 二、「Flask 链与 SA2/FSA3/Alembic 同窗 bump」是什么意思

### 2.1 一句话

**同窗 bump** = 把互相硬依赖的一组包，在**同一个可发布单元**（通常一个依赖 PR / 一次发布候选）里一起升到兼容集合，中间状态不允许合入 `main` 或打生产 tag。

### 2.2 为何不能拆开升

| 若只升… | 结果 |
| --- | --- |
| 只升 SA 2，Flask 仍 1.1 + FSA 2.5 | FSA 2.5 与 SA 2 组合脆弱；官方推荐路径断裂 |
| 只升 FSA 3.1，Flask 仍 1.1 | **装不上/跑不起来**：FSA 3.1 要求 Flask ≥ 2.2.5（DEC-007） |
| 只升 Flask 2.3，SA/FSA 仍旧 | 可临时跑，但本里程碑目标（ORM 2.0）未达成；易长期停在「半代际」 |
| 升 SA2+FSA3，Alembic 仍锁 1.4.3 | 迁移工具与 SA 2 不匹配；`flask db` / 生产 upgrade 风险 |

### 2.3 「Flask 链」指哪些包

```
Flask 2.3.x
  ├─ Werkzeug 2.3.x
  ├─ Jinja2 3.1.x
  ├─ Click 8.1.x
  ├─ itsdangerous 2.x
  ├─ MarkupSafe 2.x
  └─ blinker（Flask 2.3+ 硬依赖）

同窗一并：
  SQLAlchemy 2.0.x
  Flask-SQLAlchemy 3.1.x
  alembic（匹配 SA 2 的版本）
  Flask-Migrate（匹配 FSA3 / Flask2）
```

### 2.4 同窗的操作定义（D1 门禁）

- **允许：**一个 commit/PR 改 `requirements-core.txt` + `requirements.txt` 中上表全部 pin；或「Flask 链 PR」与「SA/FSA/Alembic PR」在同一天合并且中间 `main` 不发布。
- **禁止：**合并后 `main` 上出现「FSA 3 + Flask 1.1」或「SA 2 + alembic 1.4.3」等半升组合并持续 >0 个发布点。
- **验收：**同窗 PR 必须一次性通过 `cronpilot.sh test` + `verify_all --local-only`；Docker 路径在 D3 补全。
- **不在同窗：**gevent / gunicorn / APS（已 Tier 2）；功能轨 OPT；`Mapped[]` 大批量（属 D2）。

错误（半升）:
main ──► 只合 FSA3 ──► 炸 / 或装不上
正确（同窗）:
main ──► [Flask2.3链 + SA2 + FSA3.1 + Alembic] 一次绿 ──► tag/发布候选

## 三、决策记录（已确认）

| 项 | 选择 | 状态 |
| --- | --- | --- |
| Python | A1 · 3.8–3.11（修订：撤回 A2） | 已确认 |
| 框架线 | B1 · Flask 2.3 + SA2 + FSA3.1 | 已确认 |
| 同窗 bump | 是 | 已确认 |
| §5.1 不做项 | 是 | 已确认 |
| DEC | DEC-008 | 已写入 RFC |
| D1 pin | 已交付 | 见 RELEASE\_NOTES |

## 四、子阶段（确认后）

D0 ✓ 决策（本页）
→ D1 pin bump ✓
→ D2 Mapped[] ✓
→ D3 全矩阵 / Docker / NOTICE
→ Tier 3b/3c 生产迁移校验

## 五、验收契约（D1+）

| # | 门禁 |
| --- | --- |
| 1 | `cronpilot.sh test`（含 AST / Phase B views 门禁） |
| 2 | `verify_all.sh --local-only` |
| 3 | CI Unit tests 矩阵 **3.8–3.11** |
| 4 | Docker compose 路径 + `pip show` 断言 pin（D3） |
| 5 | 登录 / Ajax / 任务中心 / JobStore / 双库回归 |
| 6 | 文档 + `THIRD_PARTY_NOTICES` + `html_docs_to_markdown.py --check` |

[依赖升级 RFC](依赖升级RFC.html) ·
[交付状态与路线图](交付状态与路线图.html) ·
[文档索引](index.html)

CronPilot · Phase D0 Framework Generation 决策 · 已确认 2026-07-20 · [Markdown](PhaseD0-Framework-Generation决策.md) · [索引](index.html)

---

[← 文档索引（HTML）](index.html) · [← 文档索引（Markdown）](index.md)
