# CronPilot 产品优化需求（详版 · 借鉴 Plombery）

> HTML 版：[产品优化需求-借鉴Plombery.html](产品优化需求-借鉴Plombery.html) · [文档索引](index.html) · [索引 Markdown](index.md)

# CronPilot 产品优化需求（详版）

针对性对比 Plombery · 现状不足 · 优化理由 · 业务价值 · 明确优先级

[← 文档索引](index.html) ·
[深度对比全文](Plombery深度对比分析.html)

**目录**

1. [守正原则与优先级定义](#principle)
2. [P0 需求（安全与基础质量）](#p0)
3. [P1 需求（可观测与运维效率）](#p1)
4. [P2 需求（体验与规模化）](#p2)
5. [明确不做](#out)
6. [实施路线图](#roadmap)

## 守正原则与优先级定义

**守正（产品定位不变）：**继续做「中心化 HTTP 定时触发台」—— 到点 GET 业务 `req_url`，支持 Web/API 动态改任务、秒级 Cron、集群双锁、跨语言。不改为 Plombery 式「进程内 Python Pipeline」。

### 优先级判定标准

|  |  |
| --- | --- |
| P0 | 不修则可能**安全事故、数据破坏、生产误判**，或阻塞后续所有改造（技术债根因）。必须在本迭代完成。 |
| P1 | 不修则**运维成本高、故障难定位、与 Plombery 等现代平台体验差距大**，直接影响用户留存与口碑。应在 1–2 个版本内完成。 |
| P2 | 显著提升体验或规模化能力，但**有替代手段**（人工刷新、看文件日志等）。按资源排期。 |

## P0 需求（安全与基础质量）

**OPT-P0-01** P0 SQL 查询参数化，消除注入面

#### Plombery 对照

Plombery 运行元数据均经 SQLAlchemy Repository 写入，删除/查询走 ORM 或绑定参数；无业务方可控 SQL 拼接场景。

#### CronPilot 现状与不足

|  |  |
| --- | --- |
| 现状 | `main/views.py` 中 `db.session.execute("delete from job_log where cron_info_id='%s'" % cron_id)`； `crons.py` 的 `cron_del_job_log` 使用 `delete ... limit %s` 字符串拼接。 |
| 不足 | 若 `cron_id` 或配置被污染，存在 SQL 注入风险；不符合安全审计基线；与「企业级定时平台」定位不符。 |
| 为何 P0 | 属于**可利用漏洞类**，一旦管理端被攻破或参数篡改，影响整库。 |

#### 优化方案

全部改为 SQLAlchemy `filter().delete()` 或 `text()` + 命名参数；补充安全相关单测。

#### 价值与意义

|  |  |
| --- | --- |
| 对运维 | 通过等保/安全扫描，降低背锅风险。 |
| 对研发 | 统一数据访问范式，后续加字段不易再踩坑。 |

**验收：**全项目无 `execute("%` 拼接；安全扫描无 SQLi 告警。

**OPT-P0-02** P0 管理端密码哈希存储

#### Plombery 对照

生产推荐 OAuth2（Google/Microsoft）+ Session；密钥 `auth.secret_key` 用 SecretStr，不明文落盘。

#### CronPilot 现状与不足

|  |  |
| --- | --- |
| 现状 | `check_pass` 中 `login_pwd != password` 直接与 conf.ini 明文比对；`is_dev=1` 时登录页 placeholder 可提示明文密码。 |
| 不足 | conf.ini 泄露即全盘失守；镜像/备份/日志中常见明文配置；无法对接企业 SSO。 |
| 对比差距 | Plombery 内网可关 auth，但生产路径明确；CronPilot 生产仍普遍用单密码，且防护弱。 |

#### 优化方案

存储 bcrypt/scrypt 哈希；首次启动或迁移工具将明文转为哈希；保留「仅哈希」配置项。OAuth 放 P1，不阻塞 P0。

#### 价值与意义

配置泄露不直接等于后台沦陷；满足最基本账户安全要求，为后续 OAuth 打基础。

**验收：**磁盘上无明文密码；旧 conf 迁移文档齐全。

**OPT-P0-03** P0 回调 URL SSRF / 内网探测防护

#### Plombery 对照

任务在进程内执行，**不存在**「平台替用户请求任意 URL」模型；SSRF 风险主要在用户代码自身。

#### CronPilot 现状与不足

|  |  |
| --- | --- |
| 现状 | 仅校验 `req_url` 含 http/https；保存后 `cron_do` 由服务器发起 GET，可指向 `127.0.0.1`、云元数据 `169.254.169.254`、内网 Redis 等。 |
| 不足 | 恶意或误配任务可导致**内网扫描、云凭证窃取**；多租户场景下属于严重事故面。Plombery 无此攻击面，但这是 CronPilot **模式固有风险**，必须补。 |
| 为何 P0 | 属于架构型高危，与「能填 URL」的产品能力绑定，不修则无法对外宣传企业级。 |

#### 优化方案

conf.ini：`url_allow_hosts` 白名单和/或 `block_private_ip=1`；保存与执行前双重校验；可选「观察模式」先告警不拦截。

#### 价值与意义

平台从「任意 HTTP 客户端」变为「受控触发器」；与 Plombery 差异化：我们保留 HTTP 模型，但补上其天然没有的安全闸门。

**OPT-P0-04** P0 统一前后端 JSON 契约并修复 errcode 类型缺陷

#### Plombery 对照

REST 使用 HTTP 状态码 + Pydantic 校验；422 返回字段级 `detail`；前端 `ky` 按 status 分支，契约稳定。

#### CronPilot 现状与不足

|  |  |
| --- | --- |
| 现状 | Web 用 `web_api_return`；API 用 `api_return`（字段相同但入口分散）；`requests.js` 判断 `data.errcode == '0'`（字符串），而服务端返回数字 `0`。 |
| 不足 | 部分 Ajax 成功回调可能永不触发；对接方难以依赖统一规范；与 Plombery「一种错误模型」相比显得业余。 |

#### 优化方案

单一 `json_response(errcode, errmsg, data, url)`；文档约定类型；修复 JS 为 `=== 0`；API 错误逐步对齐 HTTP 状态码。

#### 价值与意义

减少「页面点了没反应」类工单；降低集成方沟通成本，为 OpenAPI（P1）奠基。

**OPT-P0-05** P0 Cron 校验与任务写入逻辑抽取（消灭 Web/API 双份实现）

#### Plombery 对照

触发器来自 APScheduler + Pydantic 模型校验；**单一路径**注册。参数非法在边界一次拒绝。

#### CronPilot 现状与不足

|  |  |
| --- | --- |
| 现状 | `main/views.py` 的 `cron_add`/`cron_edit` 与 `api/views.py` 的 `crons()` 各含约 300 行几乎相同的 day/hour/minute 校验。 |
| 不足 | **行为漂移风险：**修 Web 漏 API 或反之（历史上 hour 逗号列表曾出 bug）。  **无法单测：**校验埋在 view 里，回归成本高。  **阻碍 P1：**不加 status/http\_status 就要改两处。 |
| 为何 P0 | 这是技术债**根因**，不先收敛，后续每项可观测改造成本翻倍。 |

#### 优化方案

`services/cron_validator.py` + `services/cron_service.py`（add\_or\_update、pause、delete）；views 仅做参数提取与响应。

#### 价值与意义

对齐 Plombery「边界清晰」；研发效率与质量双提升，属性价比最高的重构。

**验收：**校验相关单测覆盖率 > 90% 场景；Web/API 共用一个 service 入口。

## P1 需求（可观测与运维效率）

以下问题在对比 Plombery 时最为刺眼：对方有 **PipelineRun 状态机 + 实时 UI**，我方仅有「任务是否在跑」和「回调返回的一大段文本」。

**OPT-P1-01** P1 单次执行结构化状态（success / fail / timeout）

#### Plombery 对照

`PipelineRunStatus`：PENDING → RUNNING → COMPLETED | FAILED | CANCELLED；UI `StatusBadge` 一眼可辨；通知按 status 匹配规则。

#### CronPilot 现状与不足

|  |  |
| --- | --- |
| 现状 | 任务级 `cron_infos.status`：0 停 / 1 跑 / -1 结束（指调度生命周期，非单次执行）。  每次触发仅有 `job_log.content` 存 HTTP 响应全文，**无 status 字段**。 |
| 不足 | 运维在「执行记录」里需人工读 JSON/HTML 判断成败；HTTP 500 但 body 无 "fail" 词 → **不告警、显示成功**（见 `crons.py` 未读 `req.status_code`）。  无法按失败筛选、无法做失败率统计（Plombery 默认可做 Runs 图表）。 |
| 用户原话场景 | 「系统关心调用结果吗？」— 目前**半关心**：只关心异常抛错和关键词，不关心语义化成败。 |

#### 优化方案

`job_log` 增加 `status`、`http_status`、`fail_reason`（枚举+短文本）；`cron_do` 写入时综合判定。

#### 价值与意义

|  |  |
| --- | --- |
| 运维 | 列表筛「失败」、排障时间从分钟级降到秒级；与 Plombery Runs 列表体验对齐。 |
| 产品 | 回答「平台是否关心结果」— **明确关心且可证明**。 |
| 商业 | 支撑 SLA 汇报、告警准确率提升，减少误报漏报纠纷。 |

**验收：**模拟 500/超时/keyword 命中三种情况，status 与告警行为符合配置。

**OPT-P1-02** P1 可配置失败判定规则（HTTP 状态码 + 关键词）

#### Plombery 对照

Task 抛异常 → 流水线 FAILED，语义清晰；不依赖响应体猜词。

#### CronPilot 现状与不足

|  |  |
| --- | --- |
| 现状 | 仅 `error_keyword` 子串匹配响应体；`requests.get` 不因 4xx/5xx 抛错（除非连接失败）。 |
| 不足 | 业务返回 200 + `{"success":false}` 无关键词 → 平台认为成功。  返回 502 空 body → 平台认为成功。  与「回调型调度」行业标准（看 HTTP + 业务码）不一致。 |

#### 优化方案

conf.ini：`fail_on_http_4xx_5xx=1`（默认开）、保留 keyword；可选 JSON path 规则（P2）。

#### 价值与意义

把「关心结果」从口号变成规则；减少夜间漏告警事故，对标云厂商定时触发产品的基线能力。

**优先级说明：**依赖 OPT-P1-01 的 status 字段，故排在 01 之后、同属 P1 首批。

**OPT-P1-03** P1 执行详情页（替代 iframe 碎片浏览）

#### Plombery 对照

路由 `/pipelines/.../runs/{runId}` 聚合：状态、耗时、Tasks、LogViewer、输出 JSON、Traceback 对话框。

#### CronPilot 现状与不足

|  |  |
| --- | --- |
| 现状 | `job_log_all_list` 表格展示 content 全文（可能极大）。  「更详细记录」用 `open_iframe_dialog` 打开 `job_log_item_list`，无统一 Run 视图。 |
| 不足 | 排障要在列表与弹窗间跳转；无法固定链接分享某次执行；长文本撑破表格；无 traceback/HTTP 元数据专区。  Plombery 用户已形成「点 Run 进详情」心智，我方体验明显落后一代。 |

#### 优化方案

`/job_log/{id}` 或 `?log_id=`：分区展示摘要、HTTP、content 折叠、items 时间线、关联任务 cron 表达式。

#### 价值与意义

降低 50%+ 日常排障点击次数；为 SSE（P2）提供挂载页；提升专业度，缩小与 Plombery 的「体感差距」。

**OPT-P1-04** P1 「立即执行」手动触发

#### Plombery 对照

`ManualRunDialog` + `POST /api/pipelines/{id}/run`；可带 JsonSchema 参数；创建后跳转 Run 详情。

#### CronPilot 现状与不足

|  |  |
| --- | --- |
| 现状 | 验证任务只能改 cron 为 1 分钟后或调 API 改 run\_date；无「现在就跑一次」。 |
| 不足 | 上线前验证、补跑、联调成本高；Plombery 将此作为核心卖点之一。 |

#### 优化方案

列表操作「立即执行」→ 异步调用 `cron_do`（注意集群锁）→ 跳转执行详情页（OPT-P1-03）。

#### 价值与意义

提升运维效率与产品完整度；不改变调度模型，仅补交互短板。

**OPT-P1-05** P1 长任务进度：强化 add\_log + 结构化明细

#### Plombery 对照

任务内 `logger.info` → JSONL + WebSocket 实时推送；无需业务再调第二个 API。

#### CronPilot 现状与不足

|  |  |
| --- | --- |
| 现状 | 已有 `/api/cron/add_log` + `job_log_items`，但 UI 仅 iframe 列表；无 level/time 字段；平台侧无实时推送。 |
| 不足 | 长任务场景下 Plombery「边跑边看日志」；我方「回调完才看到一大坨响应」，中间黑盒。 |

#### 优化方案

items 增加可选 `level`、规范 timestamp；详情页时间线展示；与 OPT-P2-01 SSE 衔接。

#### 价值与意义

发挥 xiaoniu 跨语言优势（业务用任何语言调 add\_log）；在「HTTP 分离部署」前提下逼近 Plombery 可观测性。

**OPT-P1-06** P1 OpenAPI 可交互文档，替代静态 api\_doc.html

#### Plombery 对照

FastAPI 自动生成 OpenAPI；官方文档与代码同步。

#### CronPilot 现状与不足

|  |  |
| --- | --- |
| 现状 | `api_doc.html` 手写表格 + JS 拼 HOST；与实现易脱节。 |
| 不足 | 集成方不能「Try it」；字段变更无编译期检查；显得不如 Plombery 现代。 |

#### 优化方案

Flask-Smorest / apispec 或维护 openapi.yaml + Swagger UI；与统一 JSON 契约（P0-04）同步。

#### 价值与意义

降低集成支持成本；提升开源项目专业形象。

**OPT-P1-07** P1 模板 partial 化与导航一致

#### Plombery 对照

React 组件复用 `PageLayout`、`Breadcrumbs`，无重复布局。

#### CronPilot 现状与不足

|  |  |
| --- | --- |
| 现状 | 9 个页面各自复制 Jumbotron + nav-tabs；`cron_edit` 的 active tab 仍写「任务添加」。 |
| 不足 | 改一处导航需改 N 文件；细节错误损害信任感；阻碍统一加「仪表盘」入口。 |

#### 优化方案

`templates/partials/`：header、nav、flash；各页只填 content block。

#### 价值与意义

降低 UI 迭代成本；为 P2 统计页嵌入铺路。不改 SSR 架构，借鉴 Plombery 组件化**思想**而非技术栈。

**OPT-P1-08** P1 进程启动时清理悬空执行记录

#### Plombery 对照

启动时将残留 PENDING/RUNNING 的手动运行标为 CANCELLED，避免 UI 假死状态。

#### CronPilot 现状与不足

|  |  |
| --- | --- |
| 现状 | 若引入 RUNNING 状态（P1-01）后，进程被 kill 可能留下永久 RUNNING；当前无 Run 状态故问题未暴露。 |
| 不足 | 与 Plombery 相比缺少「自愈」；升级/崩溃后数据可信度下降。 |

#### 优化方案

`create_app` 末尾：将超时未更新的 RUNNING 标 timeout 或 failed。

#### 价值与意义

与 P1-01 配套；保证状态机语义完整。

**优先级：**在 P1-01 上线同一版本交付。

**OPT-P1-09** P1 管理操作审计（operation\_log + 操作记录页）

#### Plombery 对照

Pipeline/Trigger 变更可追溯；Run 历史与配置变更多为 UI + DB 元数据分离。CronPilot 当前连「谁改了 cron 表达式」都无记录。

#### CronPilot 现状与不足

|  |  |
| --- | --- |
| 现状 | 管理端添加/编辑/启停/删除与 `/api/cron` 写操作**无审计表**；仅 `cron_infos` 保留**当前配置**；`job_log` 只记录**到点执行**结果，不是配置变更。 |
| 不足 | 无法回答「谁把 9 点改成 10 点」「昨晚谁删了任务」；合规与安全事件复盘困难；与详细技术方案已列风险「无审计日志」一致。 |

#### 优化方案

1. 新增表 `operation_log`（库：`cron_job_log_db`），字段见 [架构设计 §6.4](架构设计文档.html#s6)。
2. 新增 `app/services/operation_log_service.py`，在 `cron_service` / `main/views` / `api/views` 写库成功后统一 `record_operation`。
3. 管理页 `/operation_log_list`：分页、按任务名/操作类型/时间筛选；导航与「任务执行记录」分 Tab。
4. 编辑类操作 `detail_json` 存字段级 diff；删除类存最后快照摘要。
5. 配置 `operation_log_counts` 控制保留条数（默认可 5000）。

#### 记录范围（首批）

| action | 触发点 | channel |
| --- | --- | --- |
| `create_cron` | `/cron_add`、`/api/cron` 新建 | web / api |
| `update_cron` | `/cron_edit`、`/api/cron` 更新 | web / api |
| `toggle_status` | `/update_status`、`/api/cron/status` | web / api |
| `delete_cron` | `/cron_del` | web |
| `batch_delete_cron` | `/cron_batch_del` | web |
| `delete_job_log` | 执行记录删除（可选 P1） | web |

#### 价值与意义

补齐「配置变更」与「执行结果」边界；满足运维问责与轻量合规；不替代 `job_log`，两页职责清晰。

**验收：**Web 改任务后 `operation_log` 有行且 `detail_json` 含变更字段；API 改任务 `channel=api`；列表页可筛可查；删任务后仍可按 `task_name` 搜到历史。

**局限（单密码模式）：**无多用户账号时 `actor` 仅能记 session 指纹或固定 `admin`，细粒度到人需 P2 OAuth/多用户。

## P2 需求（体验与规模化）

P2 项均有明确价值，但可通过人工手段短期绕过，或依赖 P0/P1 完成后才有意义。

**OPT-P2-01** P2 SSE 推送执行记录与 add\_log 明细

#### 对比

Plombery 用 Socket.IO 双通道 `run-update`、`logs.{id}`。我方可用更轻的 SSE，仅在看详情页时订阅，避免全站 WS 基础设施。

#### 现状不足

长任务只能反复刷新 iframe/列表；运维感知延迟大。

#### 价值

在保留 SSR 前提下，补齐 Plombery 最吸引人的「实时感」；实施成本低于整站 React。

**依赖：**OPT-P1-03 详情页、OPT-P1-05 结构化 items。

**OPT-P2-02** P2 执行统计仪表盘（成功率 / 耗时趋势）

#### 对比

Plombery 有 RunsStatusChart、RunsDurationChart（Tremor）。

#### 现状不足

无聚合视图；管理者无法回答「这周失败了多少」除非导出 SQL。

#### 价值

管理可视化；对多任务运维场景提升决策效率。Chart.js + 一个聚合 API 即可，无需 Plombery 全量前端。

**依赖：**OPT-P1-01 status 字段。

**OPT-P2-03** P2 APScheduler coalesce 可配置

#### 对比

Plombery `coalesce=True`，停机恢复后不风暴执行。我方 `coalesce=False`，积压会连续触发多次回调。

#### 现状不足

长时间宕机恢复可能对业务造成突发 N 次 GET；对非幂等接口危险。

#### 价值

提升调度行为可预测性；conf 默认保持 false 兼容老用户，true 为推荐生产配置。

**OPT-P2-04** P2 超大响应体落盘（DB+文件分离）

#### 对比

Plombery 任务输出存 `.data/runs/`，DB 只存元数据。

#### 现状不足

整页 HTML/JSON 塞进 `job_log.content`，SQLite 膨胀、列表页卡死。

#### 价值

借鉴双存储；保持查询性能；大对象按需加载。

**OPT-P2-05** P2 Prometheus /metrics

#### 对比

Plombery 偏 UI 观测；我方更适合对接现有 Prometheus/Grafana 体系（企业运维常见）。

#### 价值

触发 QPS、失败率、histogram 耗时、Redis 锁失败计数 —— 补 Plombery 未强调的企业集成面。

**OPT-P2-06** P2 通知子系统 Notifier 抽象 + 按事件类型路由

#### 对比

Plombery `NotificationRule` + Apprise 80+ 通道。我方企微/钉钉/WebHook 写死在 `send_text`。

#### 现状不足

新增通道改核心函数；无法「仅失败发钉钉、keyword 发企微」。

#### 价值

扩展通知能力而不改 cron\_do；可选引入 Apprise 作为高级插件。

**OPT-P2-07** P2 可选 OAuth2 登录

#### 对比

Plombery 生产推荐 OAuth。我方企业客户常要求 SSO。

#### 为何 P2 非 P0

P0 哈希密码可短期满足；OAuth 实施与配置成本高，适合有明确客户需求时做。

#### 价值

对齐企业安全采购清单；内网仍可关闭，保留轻量优势。

**OPT-P2-08** P2 GET /api/runs 对外查询接口

#### 对比

对标 Plombery `GET /api/runs`，供 CI/监控拉取。

#### 价值

融入客户统一监控平台；减少「只能登 Web 看」的限制。

**OPT-P2-09** P2 Cron 可视化向导（保留高级文本）

#### 对比

Plombery 在代码里写 CronTrigger，不面向运维配 cron 字段；我方 Web 配 cron 是**优势**，向导是锦上添花。

#### 价值

降低误配；减少 support。优先级低于「成败可见」类需求。

## 明确不做（避免偏离定位）

| Plombery 能力 | 不做原因 | 替代策略 |
| --- | --- | --- |
| 进程内 @task Pipeline | 摧毁跨语言 HTTP 定位 | 组合架构：cron 回调 Plombery run API |
| 仅代码注册任务 | 丧失 Web/API 动态运维优势 | 保持 cron\_infos DB |
| 强制单 worker | 放弃已有集群双锁能力 | 文档写清集群拓扑；可选调度独立进程 |
| 全量 React 重写 | 部署复杂、与轻量 Docker 形象冲突 | SSR + SSE + 详情页 |
| 平台内 DAG 编排 | scope 爆炸；应用层编排 | 多任务 + 业务工作流引擎 |

## 实施路线图（与优先级绑定）

| 阶段 | 周期 | 交付项 | 业务可见价值 |
| --- | --- | --- | --- |
| **Phase A** | 1–2 周 | 全部 OPT-P0-01 ~ 05 | 安全可审计；API 集成稳定；后续改造不再双倍工时 |
| **Phase B** | 3–6 周 | OPT-P1-01 ~ 09（状态、详情、立即执行、OpenAPI、操作审计…） | 运维「看得懂成败、点得进详情、验得了任务」— 对齐 Plombery 核心体验 |
| **Phase C** | 按需 | OPT-P2 中选：SSE、仪表盘、metrics、coalesce… | 实时感与规模化；对接企业监控栈 |

### 优先级总览表

| ID | 名称 | 优先级 | 一句话价值 |
| --- | --- | --- | --- |
| OPT-P0-01 | SQL 参数化 | P0 | 消除注入，过安全审计 |
| OPT-P0-02 | 密码哈希 | P0 | 配置泄露不致命 |
| OPT-P0-03 | SSRF 防护 | P0 | HTTP 模型的安全闸门 |
| OPT-P0-04 | 统一 JSON 契约 | P0 | Ajax/集成可靠 |
| OPT-P0-05 | 校验/service 抽取 | P0 | 技术债根因，降本增效 |
| OPT-P1-01 | 执行 status | P1 | 明确关心成败 |
| OPT-P1-02 | 失败判定规则 | P1 | 少漏告警 |
| OPT-P1-03 | 执行详情页 | P1 | 排障效率 |
| OPT-P1-04 | 立即执行 | P1 | 联调补跑 |
| OPT-P1-05 | 强化 add\_log | P1 | 长任务可观测 |
| OPT-P1-06 | OpenAPI | P1 | 集成专业度 |
| OPT-P1-07 | 模板 partial | P1 | UI 可维护 |
| OPT-P1-08 | 启动清理悬空 Run | P1 | 状态可信 |
| OPT-P1-09 | 管理操作审计 | P1 | 配置变更可追溯 |
| OPT-P2-01 ~ 09 | SSE/图表/metrics… | P2 | 体验与规模化增强 |

论证详见各 OPT 卡片 · 对比全文：[Plombery深度对比分析](Plombery深度对比分析.html) ·
[架构摘要](架构设计文档.html#s14)
· [Markdown](产品优化需求-借鉴Plombery.md) · [索引](index.html)

---

[← 文档索引（HTML）](index.html) · [← 文档索引（Markdown）](index.md)
