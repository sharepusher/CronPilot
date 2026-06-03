# License Audit · CronPilot

> HTML 版：[LICENSE-AUDIT.html](LICENSE-AUDIT.html) · [文档索引](index.html) · [索引 Markdown](index.md)

[← 文档索引](index.html)

# License Audit 报告

**项目：**CronPilot · **审计日：**2026-05-29 · **范围：**仓库声明、上游、Python 依赖、静态前端、文档引用

## 1. 执行摘要

| 维度 | 结论 | 风险 |
| --- | --- | --- |
| 本仓库 LICENSE | 已补充 Apache-2.0（整改后） | 低 |
| 上游 CronPilot | GitHub `license: null`，无 LICENSE 文件 | 高 |
| Python 直接依赖 | 以 MIT/BSD/Apache/ISC 为主 | 低～中 |
| 需关注依赖 | chardet (LGPL)、certifi (MPL-2.0) | 中 |
| 静态前端 | jQuery/Bootstrap/FA 等未集中 NOTICE | 中 |
| 商业闭源分发 | 可行但需 NOTICE + 上游权利确认 | 中 |

## 2. 本仓库（CronPilot）

**整改前：**无 LICENSE，README 写「沿用原项目开源协议」但上游无明确协议 → 法律上**不可假定**可自由再分发。

**整改后：**

- `LICENSE` — Apache License 2.0（2026 CronPilot contributors）
- `NOTICE` — 上游来源声明与免责提示
- `THIRD_PARTY_NOTICES.md` — 依赖与静态资源清单

Apache-2.0 仅覆盖**本仓库贡献者**享有版权的部分；自上游复制的代码块在上游未授权时，Apache 文件本身不能替代上游许可。

## 3. 上游 aniu-lee/xiaoniu\_cron

- GitHub API：`"license": null`
- 默认分支无 `LICENSE` / `LICENSE.txt`
- **建议：**向作者确认许可（常见为 MIT）；或仅将上游作为内部参考、本仓库以净室新增文件为主

## 4. Python 依赖（requirements.txt）

基于 PyPI 元数据与业界惯例归类（共 40 个直接依赖）：

| 许可证族 | 代表包 | 商业使用 |
| --- | --- | --- |
| MIT | APScheduler, SQLAlchemy, gevent, redis, PyMySQL, … | 允许，保留版权声明 |
| BSD-3 | Flask, Jinja2, Werkzeug, click, Flask-SQLAlchemy, … | 允许，保留版权声明 |
| Apache-2.0 | requests, Flask-APScheduler, python-dateutil, … | 允许，NOTICE + 专利授权条款 |
| ISC | records | 允许 |
| ZPL-2.1 | zope.interface, zope.event | 允许（Zope Public License，类 BSD） |
| MPL-2.0 | certifi | 允许；修改 MPL 文件需回馈 |
| LGPL-2.1+ | chardet（经 requests 引入） | 动态链接通常可接受；法务需确认分发形态 |

未发现直接依赖**强 Copyleft**（GPL/AGPL）作为运行时必需项。

## 5. 静态前端（app/static/）

仓库内**厂商自带** jQuery、Vue、Bootstrap、Font Awesome、artDialog 等，多数为 MIT/BSD/OFL，但**未随发行版附带完整许可证全文**，不符合大型客户合规审计常见要求。

**建议：**增加 `app/static/NOTICE-frontend.txt` 或构建时自动生成 SBOM/attribution 页面。

## 6. 文档与参考实现

`doc/` 中对 **Plombery** 为分析性引用，未嵌入其源码 → MIT 文档引用无额外义务。若未来复制 Plombery 代码片段，需保留 MIT 声明。

## 7. Docker / 系统层

`Dockerfile` 基于 `ubuntu:16.04`（已 EOL），涉及 Canonical 镜像条款与系统包许可证，与 Python 包许可证审计正交，建议升级至 22.04/24.04 LTS。

## 8. 合规行动清单

| 优先级 | 行动 | 状态 |
| --- | --- | --- |
| P0 | 添加 Apache-2.0 LICENSE + NOTICE | 已完成 |
| P0 | THIRD\_PARTY\_NOTICES.md | 已完成 |
| P0 | 确认上游 CronPilot 书面许可 | 待办 |
| P1 | pip-licenses 纳入 CI 生成 SBOM | 待办 |
| P1 | 前端静态资源 NOTICE | 待办 |
| P2 | 升级 Dockerfile 基础镜像 | 待办 |

## 9. 免责声明

本报告为技术梳理，不构成法律意见。对外发布、SaaS 或政企投标前，请由法务基于实际分发形态（源码/二进制/Docker）终审。

[文档索引](index.html) · [Markdown](LICENSE-AUDIT.md) · [索引](index.html)

---

[← 文档索引（HTML）](index.html) · [← 文档索引（Markdown）](index.md)
