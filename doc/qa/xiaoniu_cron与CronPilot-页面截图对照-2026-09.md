# xiaoniu_cron ↔ CronPilot 页面截图对照（2026-09）

> HTML 版：[xiaoniu_cron与CronPilot-页面截图对照-2026-09.html](xiaoniu_cron与CronPilot-页面截图对照-2026-09.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# xiaoniu\_cron ↔ CronPilot 页面截图对照

本页把两套系统**实际跑起来**后的关键画面并排对照：上游取公开 HEAD（2022-12-26）干净工作树；
CronPilot 取本机 v4 线 Redesign 管理端。截图视口 **1440×900**，采集于 2026-09-24。

环境：上游 `http://127.0.0.1:5002`（密码 `123456`）·
CronPilot `http://127.0.0.1:5001`（种子 `admin` / `ci-test-password`；新建任务页用 `ops_demo`）·
资产目录 `doc/qa/assets/ui-compare-2026-09/` · 版本 v1.0 · 2026-09-24  
姊妹文：
[① 坑与账本](我用Cursor重构十年GitHub项目的坑-专栏-2026-09.html) ·
[② 假完成工业](假完成工业-Cursor重构工程病理学-2026-09.html) ·
[③ 工程代价与终局](工程代价与终局对比-xiaoniu_cron与CronPilot-2026-09.html)

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v1.0 | 2026-09-24 | 首发：双系统实装截图 · 同构页并排 + CronPilot 独有页 |

**怎么读：**「同构页」两边都有对应入口；「CronPilot 独有」是上游无等价页面的能力面（RBAC/组/标签/审计等）。
截图是交付证据，不是设计 Mockup。本地复验请保持两服务运行后硬刷新。

## 一、采集范围与登录

| 系统 | 版本锚点 | 端口 | 登录 | 截图数 |
| --- | --- | --- | --- | --- |
| xiaoniu\_cron | git `0883731` · 2022-12-26 | 5002 | 仅密码 `123456` | 5 |
| CronPilot | 本机运行中的 v4 线 Redesign | 5001 | 用户名+密码；CSRF；可注册申请 | 14 |

## 二、同构页面：Before / After

### 2.1 登录

上游：共享口令一栏到底。CronPilot：用户名+密码、忘记密码、申请注册、品牌化 Auth 卡。

上游 · /check\_pass

![上游登录页](../assets/screenshots/73e5ed4763101e5b31b71ca8ab2f8779802d23ce9f142edb720afcca34ce2ce3.png)

CronPilot · /rbac/login

![CronPilot 登录页](../assets/screenshots/a271663b6dcca6c9c6a53554c58f3e8d73d3e4160781c268f6c8f3d4a152cab7.png)

### 2.2 任务列表 / 任务中心

上游：顶栏四链 + 批量删除 + cron 字段列。CronPilot：侧栏信息架构 + 健康度/逾期统计 + 异常面板 + 下次执行。

上游 · /cron\_list

![上游任务列表](../assets/screenshots/d8674261d463817a7199d05b8d75dccfb41044e2ac4c1fa32f3c0bb8368443c0.png)

CronPilot · / （任务中心）

![CronPilot 任务中心](../assets/screenshots/11fd24258be10f3f95a76a227afa7a976680bf063f1b96832ebbaea0afc4cfec.png)

### 2.3 新建任务

上游任意登录者可进添加页。CronPilot 需 `cron:write`（本截图账号 `ops_demo`）；表单含组/校验/路径提示。

上游 · /cron\_add

![上游新建任务](../assets/screenshots/b27f693a4542408f622d8af751ac29089467d90a51865eccca1d8a52014c30cf.png)

CronPilot · /cron\_add

![CronPilot 新建任务](../assets/screenshots/3e404209f981c3e591825b44853bce989e9144a84bb09c95d2794224b6e46d76.png)

### 2.4 执行记录

两端都有全局执行日志；CronPilot 增加筛选、状态语义与 Redesign 表格密度。

上游 · /job\_log\_all\_list

![上游执行记录](../assets/screenshots/ff7cc9e17487df2e61073b0d8dcfe75c40ee3236b64f088d37111ebd1c6b3e49.png)

CronPilot · /job\_log\_all\_list

![CronPilot 执行记录](../assets/screenshots/78cc2682eba96ea560174058552ad76dc0e8b9afa6945563dced023187a00122.png)

### 2.5 API 文档

上游静态说明页；CronPilot 权限过滤后的查询式文档（另有 Swagger 入口，本页截管理端文档）。

上游 · /api\_doc

![上游 API 文档](../assets/screenshots/773ad9e068584bfab384369b648a1bf8dbf200b4d600a9aa154380a3ad040c5e.png)

CronPilot · /api\_doc

![CronPilot API 文档](../assets/screenshots/3362000dc0be42af5b7abf350cc61f19cbe3289a4f551867a38e02ec677c04f3.png)

## 三、CronPilot 独有页面（上游无等价入口）

这些画面本身就是终局差距：从「一个密码管全部」到组织协作与审计。

用户管理 · /rbac/users

![用户管理](../assets/screenshots/35da476db74a4146004de4cc28e5bbe6faf2d9837228cbb10dedec9b99b39b12.png)

业务组 · /rbac/groups

![业务组](../assets/screenshots/ce4cc03607834174831c7dac9e8ca8403337b3cfe893642a726de48687536600.png)

标签 · /rbac/tags

![标签](../assets/screenshots/ec676b7f1318fdebe43f9ab188ceec64ac6136804173001b57f95c199cf82cae.png)

变更记录 · /operation\_log\_list

![操作记录](../assets/screenshots/8fbc8969c297079bb22f0e9fd32c42ae6f45b3f1900f42f9ac227c1365a86bd7.png)

访问审计 · /rbac/audit-logs

![访问审计](../assets/screenshots/94de3901d8e53ef651bcb10c6d0c8df194b10a1138eeee44686f04224ac03538.png)

API Token · /rbac/api\_token

该历史截图包含凭据且不具备继续保留价值，已删除；页面对照关系由文字记录保留。

注册审批 · /rbac/registration\_review

![注册审批](../assets/screenshots/7b863a526e4c62bfbc9ba18aed3361f28389cfb98f43dff6af4a08c232c42f82.png)

个人资料 · /rbac/profile

![个人资料](../assets/screenshots/94414833f4072c9c390246b7fab3e9a8057d47448cfd4070adc4d2a181a4a354.png)

任务详情 · /task\_detail?id=1

![任务详情](../assets/screenshots/845b82f18b406312c914410ddb38b9e9a34f45a027e417afacbda7d89fa821f8.png)

说明

上游只有列表行内「编辑/删除/运行记录」，没有独立任务详情页、健康度时间线、组归属与 RBAC 导航。
右侧空白位留给后续补截（如 Run Inspector、Swagger UI）。

## 四、对照结论（画面层）

| 维度 | 画面证据 | 含义 |
| --- | --- | --- |
| 身份模型 | 登录页：单密码 vs 用户名+密码+注册 | 从共享密钥到账户体系 |
| 信息架构 | 顶栏 4 项 vs 侧栏分组（运维/配置/管理/个人） | 能力面从「够用」变为「可运营」 |
| 可观测 | 列表状态字 vs 统计卡+异常面板+健康点 | 排障从翻日志变为结构化监控 |
| 协作边界 | 上游无用户/组/审计页 | 终局质变点，不单是换皮 |
| 视觉时代 | Bootstrap/artDialog 后台 vs Console Redesign | 观感差距一目了然，但是结果不是目标 |

**与姊妹篇③的衔接：**画面对照证明「跨代」；工程代价文解释「为何贵」。
不要只凭截图宣称完成——登录态、权限角色与否定路径仍须按验收清单核对。

## 五、本地复验

```
# 上游（干净工作树示例）
# http://127.0.0.1:5002/  密码 123456

# CronPilot
# http://127.0.0.1:5001/rbac/login
# admin / ci-test-password
# 新建任务页：ops_demo / ops-demo-pass（需 cron:write）

ls doc/qa/assets/ui-compare-2026-09/*.png | wc -l   # 期望 19
```

[文档索引](../index.html) ·
[Markdown](xiaoniu_cron与CronPilot-页面截图对照-2026-09.md) ·
[工程代价与终局](工程代价与终局对比-xiaoniu_cron与CronPilot-2026-09.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
