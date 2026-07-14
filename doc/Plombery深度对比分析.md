# CronPilot vs Plombery — 深度架构与技术对比

> HTML 版：[Plombery深度对比分析.html](Plombery深度对比分析.html) · [文档索引](index.html) · [索引 Markdown](index.md)

# CronPilot × Plombery 深度对比分析

从前端交互 → 前后端契约 → 调度执行 → 数据与安全 → 部署运维 · 基于双项目源码与 Plombery architecture.html（2026-05）

[← 文档索引](index.html)

## 目录

1. [0. 一句话定位](#s0)
2. [1. 产品形态与边界](#s1)
3. [2. 前端技术栈与架构](#s2)
4. [3. 页面级交互对比](#s3)
5. [4. 前后端交互契约](#s4)
6. [5. 后端分层与领域模型](#s5)
7. [6. 调度子系统实现](#s6)
8. [7. 任务执行与结果语义](#s7)
9. [8. 数据与存储架构](#s8)
10. [9. 实时通信与可观测性](#s9)
11. [10. 认证与安全](#s10)
12. [11. 通知与告警](#s11)
13. [12. 配置与扩展机制](#s12)
14. [13. 部署与运维](#s13)
15. [14. 工程质量与测试](#s14)
16. [15. 综合评分与选型](#s15)
17. [16. 共存与迁移路径](#s16)
18. [17. CronPilot 可借鉴与优化（守正出奇）](#s17)

## 0. 一句话定位

CronPilot：**跨语言 HTTP 定时触发台** —— 到点 GET 你的业务 URL，记响应、关键词告警，适合「已有微服务，只要统一 Cron」。  
Plombery：**嵌入式 Python 流水线调度框架** —— 代码里 `@task` 组成 Pipeline，进程内执行，Web UI 看 Run/日志/输出，适合「Python 管道 + 可观测 UI」。

## 1. 产品形态与边界

| 维度 | CronPilot | Plombery |
| --- | --- | --- |
| 交付形态 | 独立产品（Docker 一键、conf.ini 配置） | Python 库嵌入用户应用（`register_pipeline` + `get_app()`） |
| 任务定义存储 | 数据库表 `cron_infos`，Web/API 动态 CRUD | 内存注册表（代码即配置），重启后定义来自代码 |
| 执行发生位置 | 业务方服务器（HTTP 回调） | Plombery 所在 Python 进程 |
| 任务拓扑 | 单步：1 触发器 → 1 URL | 线性 Pipeline：Task₁ → Task₂ → …（返回值串联） |
| 手动触发 | 无一等公民「立即运行」按钮（仅改 cron/date） | Web「Run」+ `POST /api/pipelines/{id}/run` |
| 非 Python 业务 | 天然支持 | 需 HTTP 触发 pipeline 或放弃 Plombery 执行模型 |

## 2. 前端技术栈与架构

### 2.1 技术栈对照

| 层级 | CronPilot | Plombery |
| --- | --- | --- |
| 渲染 | **SSR** Jinja2 服务端渲染 | **CSR SPA** React 19 + Vite 7 |
| UI 库 | SimpleBoot Admin + Bootstrap 3 风格 | Tremor + Tailwind + Heroicons |
| JS 运行时 | jQuery 1.x 生态 + wind.js 模块加载 | ESM、TypeScript、React Router 7 |
| 数据层 | 无前端状态库；页面内嵌服务端数据 | TanStack Query（缓存、失效、重试） |
| 构建 | 静态文件直出，无前端构建链 | `vite build` → 嵌入 `plombery/static/` |
| 表单 | HTML input + 服务端校验错误 | Pydantic → JSON Schema → `JsonSchemaForm` |
| 实时 | 无 | socket.io-client + WebSocketContext |

### 2.2 架构模式差异（影响迭代成本）

#### CronPilot：多页 SSR + 局部 Ajax

- 每个功能独立 URL（`/cron_list`、`/cron_add`）
- 公共布局靠模板 `{% extends admin_base.html %}`，但 Jumbotron/Tab 每页复制
- 交互增强靠 class 约定：`js-ajax-form`、`js-ajax-delete`
- 弹窗子页用 artDialog iframe（日志列表）

#### Plombery：SPA + REST 驱动

- 文件系统路由：`pages/pipelines/[pipelineId]/...`
- `repository.ts` 集中 HTTP；组件只消费 Query/Mutation
- 运行详情为深链路：`/pipelines/.../runs/{runId}`
- 图表组件：RunsStatusChart、RunsDurationChart

### 2.3 信息架构（IA）对比

```
CronPilot                          Plombery
─────────────                          ────────
/check_pass (登录)                     /login (OAuth)
    │                                      │
/cron_list ─┬─ /cron_add                 / (Pipelines 列表)
            ├─ /cron_edit                /pipelines/{id} (详情+Triggers+图表)
            ├─ /job_log_all_list         /pipelines/{id}/triggers/{tid}
            └─ /api_doc                      └─ /runs/{runId} (日志+输出+状态)
[iframe] job_log_list
[iframe] job_log_item_list
```

Plombery 以 **Pipeline → Trigger → Run** 三级组织；CronPilot 以 **Task(cron\_infos) → job\_log** 两级，无「一次运行」的强类型页面（只有日志行）。

## 3. 页面级交互对比

### 3.1 登录

| 步骤 | CronPilot | Plombery |
| --- | --- | --- |
| 用户操作 | 单输入框 password → POST `/check_pass` | 选择 Google/Microsoft → OAuth 重定向链 |
| 成功反馈 | 302 → `/cron_list` | Session 写入 → 重定向 SPA → `GET /api/auth/whoami` |
| 失败反馈 | 302 带 `?msg=` 或页面红色文案 | OAuth 错误页 / 前端 AuthContext 未登录态 |
| 前端状态 | 无全局用户对象；仅靠 Cookie Session | `AuthContext` 缓存 user、providers |
| 体验版特例 | `is_dev=1` 时 placeholder 显示明文密码 | 无；`auth=null` 时全开放 API |

### 3.2 任务/流水线列表

| 交互点 | CronPilot `cron_list` | Plombery `PipelinesList` / `RunsList` |
| --- | --- | --- |
| 数据加载 | 服务端分页 `paginate(20)`，关键词 GET 表单刷新整页 | `useQuery(listPipelines)`；Runs 默认最近 30 条 + WS 增量 |
| 搜索 | task\_name 模糊 → 提交后 SSR 重渲染 | Pipeline 列表无复杂筛选；Runs 可按 pipeline/trigger 过滤（API） |
| 状态展示 | 文本：已停止/运行中/已结束 | `StatusBadge`：PENDING/RUNNING/COMPLETED/FAILED… |
| 行内操作 | 运行/停止（Ajax GET）、编辑（整页）、删除（confirm+Ajax） | 进入详情；手动 Run 在详情页 Dialog |
| 批量 | checkbox + POST 批量删除 | 无批量删除运行记录（架构未强调） |
| 实时更新 | 操作后 Ajax 提示或跳转；列表不自动刷新 | `socket.on('run-update')` 插入/更新行，完成后 invalidateQueries |

### 3.3 创建/编辑任务

| 维度 | CronPilot `cron_add/edit` | Plombery |
| --- | --- | --- |
| 定义入口 | Web 表单填 cron 字段 + URL | 代码 `register_pipeline`；Web 仅手动 run + 查看 |
| 定时 UI | 下拉切换「具体时间 / 定时模式」；手写 day/hour/minute… | 代码里 `CronTrigger`；UI 展示 triggers 与 next\_fire\_time |
| 参数输入 | 无结构化 params；参数塞在 req\_url query | Pydantic Model → JSON Schema 表单（ManualRunDialog） |
| 校验时机 | 提交后服务端返回 JSON `errcode=1` | POST 时 FastAPI 422 + 字段级错误映射到表单 |
| 日期控件 | `js-datetime`（datePicker.js） | Schema 驱动（类型由 JSON Schema 决定） |

### 3.4 执行记录 / 运行详情

| 能力 | CronPilot | Plombery |
| --- | --- | --- |
| 主列表 | `job_log_all_list`：log\_id、任务名、响应体、时间、耗时 | `RunsList`：status、pipeline、trigger、started、duration |
| 详情页 | 无独立 Run 详情路由；iframe 看 item 明细 | 专属 Run 页：LogViewer + Tasks 输出 + Traceback 对话框 |
| 日志查看 | 展示回调 HTTP 响应文本（可能很长、非结构化） | JSONL 结构化级别/时间/task 过滤；WS 追加行 |
| 任务输出 | 无 | `GET /runs/{id}/data/{task}` + DataViewerDialog（含表格） |
| 失败诊断 | 看 content 是否含 fail 关键词 | FAILED 状态 + reason 字段 + traceback 弹窗 |

### 3.5 前端交互实现细节（代码级）

#### CronPilot：Ajax 表单管线

```
// app/static/js/common.js 核心路径
$('form.js-ajax-form').validate({ submitHandler: function(form) {
  $(form).ajaxSubmit({
    dataType: 'json',
    success: function(data) {
      if (data.url) location.href = data.url;
      else if (data.errcode === 0) reloadPage();
    },
    error: function(xhr) {
      art.dialog / tips_error 显示 resp.errmsg
    }
  });
}});
```

特点：成功/失败都依赖 **同一 JSON 形状**；无类型约束；整页刷新与局部提示混用。

#### Plombery：Mutation + 路由跳转

```
// ManualRunDialog.tsx
const runPipelineMutation = useMutation(runPipeline(pipeline.id))
await runPipelineMutation.mutateAsync(params)
navigate(`/pipelines/${data.pipeline_id}/triggers/${data.trigger_id}/runs/${data.id}`)
```

特点：运行创建后**立即进入可观测详情页**；422 错误映射到表单字段（`PlomberyHttpError`）。

## 4. 前后端交互契约

### 4.1 API 风格与路由组织

| 项 | CronPilot | Plombery |
| --- | --- | --- |
| Web 与 API 分离 | Web：`main` 返回 HTML；API：`/api` 前缀 JSON | 统一 FastAPI；`/api/*` JSON，`/*` SPA |
| REST 成熟度 | RPC 风格（`/cron/add`、query 传参） | 资源导向（`/pipelines/{id}/run`） |
| 文档 | 内嵌 `api_doc.html` 静态表 + JS 拼 HOST | OpenAPI 自动生成（FastAPI 默认） |
| 版本控制 | 无 API 版本号 | 无显式版本（库随应用发布） |

### 4.2 响应 envelope 对比

| 场景 | CronPilot | Plombery |
| --- | --- | --- |
| Web Ajax | `{ errcode, errmsg, url }` — `web_api_return()` | 不适用（SPA 不走该格式） |
| 开放 API | `{ errcode, errmsg, data }` — `api_return()` | 成功：资源 JSON 或 204；失败：HTTP 4xx/5xx + `detail` |
| 成功语义 | `errcode=0` 字符串与数字混用风险（requests.js 用 `'0'`） | HTTP 200 + 强类型 Pydantic 响应模型 |

### 4.3 典型请求序列对比

#### 创建定时任务

```
CronPilot (Web 添加)
Browser --POST /cron_add (form)--> Flask main.cron_add
       <-- JSON {errcode:0, url:"/cron_list"}-- 
       (或 Ajax 不跳转)
Flask: 校验 cron 字段 → INSERT cron_infos → scheduler.add_job("cron_{id}", cron_do)

Plombery (代码注册)
Developer: register_pipeline(id, tasks, triggers=[CronTrigger...])
Startup: orchestrator.register_pipeline → scheduler.add_job(job_id, func=run, kwargs={pipeline, trigger})
```

#### 触发执行

```
CronPilot
APScheduler → cron_do(id) → requests.GET(req_url, params=log_id, sign)
           → INSERT job_log(content=响应体)

Plombery
APScheduler → run(pipeline, trigger) → for task in pipeline.tasks: await _execute_task
           → store_task_output → UPDATE pipeline_runs → sio.emit('run-update')
```

### 4.4 认证在请求中的携带方式

| 通道 | CronPilot | Plombery |
| --- | --- | --- |
| Web | Flask Session Cookie（`is_login`） | Session Cookie（OAuth 后） |
| API | `access_token` 在 query/form | `NeedsAuth` Depends；Cookie credentials: include |
| 执行回调 | 业务 URL 上 `cronpilot_sign` | N/A（进程内执行） |
| CORS | 未显式配置 | `settings.allowed_origins` |

## 5. 后端分层与领域模型

| 层次 | CronPilot | Plombery |
| --- | --- | --- |
| 入口 | `manage:app` + Gunicorn gevent | 用户 `uvicorn app:app` |
| 路由 | Flask Blueprint `main` / `api` | FastAPI APIRouter `pipelines` / `runs` / `auth` |
| 领域核心 | `CronInfos` + APScheduler Job 镜像 | `Pipeline` / `Task` / `Trigger` + `PipelineRun` |
| 执行器 | `crons.cron_do`（HTTP 客户端） | `orchestrator/executor.run`（async 任务循环） |
| 上下文 | `scheduler.app.app_context()` | `contextvars`：pipeline\_context / run\_context / task\_context |
| 校验 | views 内联数百行 cron 校验（Web/API 重复） | Pydantic 模型 + FastAPI 自动校验 |

### 5.1 领域模型深度对照

```
CronPilot                          Plombery
─────────────                          ────────
CronInfos (持久化任务定义)              Pipeline (代码注册, 含 tasks[])
  ├─ schedule 字段拆分                    ├─ Trigger[] (schedule + params)
  ├─ req_url (执行目标)                   └─ params: BaseModel (输入 schema)
  └─ status 0/1/-1
                                       PipelineRun (一次执行)
JobLog (每次触发一条)                     ├─ status 状态机
  ├─ content = HTTP body                  ├─ tasks_run[] (每 Task 状态/耗时)
  └─ log_id = 回调关联 ID                 ├─ input_params JSON
JobLogItems (业务回传明细)                └─ reason
                                       文件: run_{id}/logs.jsonl, {task}.json
```

## 6. 调度子系统实现

| 配置项 | CronPilot | Plombery |
| --- | --- | --- |
| Scheduler 类 | `CuBackgroundScheduler` (thread) | `AsyncIOScheduler` |
| JobStore | SQLAlchemy 独立库 `cron_db_url` | 默认内存（文档：SQLite 元数据；调度 job 在 scheduler 内） |
| Job ID | `cron_{cron_infos.id}` | `{pipeline_id}: {trigger_id}` |
| 执行函数 | `cron_do` 同步 + thread pool | `run` async |
| coalesce | **false**（积压可能连续跑多次） | **true**（合并为一次） |
| misfire\_grace\_time | 50s | 60s |
| max\_instances | 20 / job | 10000 / job（依赖业务幂等） |
| 暂停/恢复 | `pause_job` / `resume_job` + DB status | trigger.paused 跳过注册；运行中靠 executor 状态机 |

### 6.1 多实例/集群策略（关键差异）

#### CronPilot：允许多 Worker，双层锁

- **L1** `scheduler.lock` + portalocker：同机仅一进程 poll due jobs
- **L2** Redis `@single_task`：集群间 `cron_do` 互斥（TTL 120s）
- 设计意图：水平扩展 + 共享 MySQL JobStore

#### Plombery：文档明确反对多 Worker

- 推荐 **Uvicorn workers=1** 单副本
- 多副本无内置锁 → 定时任务重复触发
- 演进方向：外置调度或 Redis 分布式锁（文档「局限与演进」）

## 7. 任务执行与结果语义

### 7.1 「成功/失败」如何判定

| 判定来源 | CronPilot | Plombery |
| --- | --- | --- |
| HTTP 状态码 | **不判断**（requests 不抛则视为可记录） | N/A（非 HTTP 执行） |
| 响应体关键词 | `error_keyword` 子串匹配 → 告警 | 不使用关键词；Task 异常 → FAILED |
| 异常捕获 | requests 异常 → job\_log + 告警 | Task except → 流水线 FAILED，后续 Task 中断 |
| 结构化状态 | 任务级 status，非 run 级 COMPLETED | PipelineRunStatus 完整状态机 |
| 重试 | **无**自动重试 | **无**内置重试策略矩阵（失败即停） |

### 7.2 超时与并发

| 项 | CronPilot | Plombery |
| --- | --- | --- |
| 单次超时 | HTTP 120s 固定 | 无全局 pipeline 超时（单 task 受 async 调度影响） |
| 并发模型 | ThreadPool 30 + 每 job max\_instances 20 | AsyncIO 单线程事件循环；sync task → `asyncio.to_thread` |
| 长任务进度 | 业务调 `/api/cron/add_log` | task 内 `logger.info` → WS 实时 |

### 7.3 数据传递

**CronPilot**：平台 → 业务只传 query（`cronpilot_log_id`、`sign`）；业务 → 平台通过 HTTP 响应体或 add\_log API。  
**Plombery**：Task 间通过 Python 返回值；Pipeline 输入通过 Pydantic `params`；输出落盘 JSON 供 UI 下载查看。

## 8. 数据与存储架构

| 数据类型 | CronPilot | Plombery |
| --- | --- | --- |
| 任务定义 | MySQL/SQLite `cron_infos` | Python 进程内存（代码） |
| 调度状态 | `apscheduler_jobs`（独立 DB URL） | APScheduler 内部 + pipeline 注册信息 |
| 运行元数据 | `job_log`（扁平，无 task 维度） | `pipeline_runs` + JSON `tasks_run` |
| 大对象/日志 | TEXT 存响应（可能膨胀） | `.data/runs/run_{id}/logs.jsonl` + task JSON 文件 |
| 迁移 | Flask-Migrate（docker\_start 自动 migrate） | Alembic 启动时 upgrade；遗留库 stamp 逻辑 |
| 历史Retention | `job_log_counts` 每任务保留 N 条 | 列表 API 默认最近 30 条（无自动归档文档） |

## 9. 实时通信与可观测性

| 能力 | CronPilot | Plombery |
| --- | --- | --- |
| 运行列表刷新 | 手动刷新 / 分页跳转 | WS `run-update` + React state 合并 |
| 日志流 | 无 | WS `logs.{run_id}` + QueueHandler 异步 |
| 日志格式 | 非结构化文本 | JSON：level、timestamp、message、task |
| 指标图表 | 无 | RunsStatusChart、RunsDurationChart（Tremor） |
| 链路追踪 | 无 | 无 OpenTelemetry；有 traceback 对话框 |
| 文件日志 | datas/logs info/error 轮转 | 每 run 独立 logs.jsonl |

```
// Plombery LogViewer：REST 初始加载 + WS 追加
useQuery(getLogs(run.id))
socket.on(`logs.${run.id}`, msg => queryClient.setQueryData(['logs', run.id], append))

// CronPilot：仅 SSR 表格展示 item.content
job_log_all_list.html → 点击 iframe → job_log_item_list
```

## 10. 认证与安全

| 威胁面 | CronPilot | Plombery |
| --- | --- | --- |
| 管理面认证 | 三角色 RBAC：用户名+密码（`rbac_users`）；空表种子 `admin`/`login_pwd`；改密走用户管理 | OAuth2 + Session（可关闭） |
| API 鉴权 | 可选 access\_token 明文 | NeedsAuth；内网可 auth=null 全开放 |
| 执行面 | SSRF 风险（任意 req\_url）；回调 MD5 签名为可选 | 执行本地代码；需信任 pipeline 作者 |
| 路径安全 | 无用户文件读取 API | `_check_is_valid_path` 防穿越 |
| RBAC | 无 | 无（登录即全权限） |
| 依赖安全 | Flask 1.1 / Py3.6 等较旧 | Py3.9–3.13 CI；较新栈 |

## 11. 通知与告警

| 维度 | CronPilot | Plombery |
| --- | --- | --- |
| 触发条件 | 异常 + error\_keyword 命中 | NotificationRule 匹配 PipelineRunStatus |
| 通道实现 | 硬编码：企微、钉钉、自定义 WebHook | Apprise URL（80+ 服务） |
| 模板 | 纯文本拼接时间戳 | 邮件 HTML Jinja 模板 |
| 与 UI 关系 | 配置在 conf.ini，UI 不可编辑 | 配置在代码/ yaml（非 Web 表单） |

## 12. 配置与扩展机制

| 项 | CronPilot | Plombery |
| --- | --- | --- |
| 配置源 | `conf.ini` 单文件 | 环境变量 + `plombery.config.yaml` + Pydantic Settings |
| 热更新 | 需重启进程 | Pipeline 需重启加载代码 |
| 扩展任务 | 改 DB/API 即可，无需发版平台 | 改 Python 代码 + 重启应用 |
| 对外集成 | HTTP API 增删任务 | HTTP API 触发 run；定义仍在代码 |
| 前端扩展 | 改 Jinja + jQuery | 改 React 组件或 fork 前端 |

## 13. 部署与运维

| 项 | CronPilot | Plombery |
| --- | --- | --- |
| 进程模型 | Gunicorn gevent ×2~4（Docker ×4） | Uvicorn **workers=1** |
| 反向代理 | 端口映射即可 | 需配置 `/ws` WebSocket 升级 |
| 持久化 | 双 SQLite 或双 MySQL + Redis（集群） | 单卷：plombery.db + .data/ |
| 升级 | docker exec migrate | 启动自动 alembic upgrade |
| Windows | 有专门部署文档 | 依赖 asyncio，理论可行但未强调 |

## 14. 工程质量与测试

| 项 | CronPilot | Plombery |
| --- | --- | --- |
| 单元测试 | 未见完整 tests 目录 | pytest：api、logging 等 |
| 类型系统 | 无类型标注为主 | Pydantic + TypeScript 全覆盖 |
| 前端 CI | 无 | tsc + vite build |
| 代码重复 | Web/API cron 校验大量重复 | executor 集中执行逻辑 |
| 文档 | README + 自建 HTML | 官方站点 + architecture.html |

## 15. 综合评分与选型（主观权重：中小团队运维场景）

| 维度 (权重) | CronPilot | Plombery | 说明 |
| --- | --- | --- | --- |
| 跨语言集成 (20%) | ★★★★★ | ★★☆☆☆ | HTTP 回调 vs Python 内执行 |
| 运维 UI 体验 (15%) | ★★☆☆☆ | ★★★★★ | SSR 老栈 vs 现代 SPA+实时 |
| 运行可观测 (15%) | ★★☆☆☆ | ★★★★★ | 响应文本 vs 结构化日志+状态机 |
| 任务编排 (10%) | ★☆☆☆☆ | ★★★☆☆ | 单 URL vs 线性 Pipeline |
| 动态配置 (10%) | ★★★★★ | ★★☆☆☆ | DB 改任务 vs 改代码重启 |
| 集群扩展 (10%) | ★★★☆☆ | ★★☆☆☆ | 有 Redis 锁但仍复杂；Plombery 默认单实例 |
| 安全现代性 (10%) | ★★★☆☆ | ★★★★☆ | OAuth vs 本地 RBAC；SSRF vs 本地执行 |
| 技术债/维护 (10%) | ★★☆☆☆ | ★★★★☆ | 旧依赖 vs 现代栈+测试 |

### 场景选型速查

| 你的场景 | 推荐 |
| --- | --- |
| 10+ 微服务，只要统一 Cron 触发既有 REST 接口 | **CronPilot** |
| 数据团队 Python ETL，要多步串联、看实时日志、手动带参运行 | **Plombery** |
| 既要统一调度台，又要复杂 Python 管道 | **组合**：CronPilot 回调 Plombery `POST .../run` |
| DAG、重试矩阵、千级任务分布式 | 两者都不合适 → Airflow/Prefect/Dagster |

## 16. 共存与迁移路径

### 16.1 推荐组合架构

```
┌─────────────┐   GET + sign    ┌──────────────┐   in-process    ┌─────────┐
│ CronPilot│ ──────────────► │ Plombery API │ ───────────────►│ @tasks  │
│ (调度/审计)  │                 │ /pipelines/…/run              │ Pipeline│
└─────────────┘                 └──────────────┘                 └─────────┘
       │                                │
       │ job_log                        │ pipeline_runs + WS logs
       ▼                                ▼
   运维看触发记录                      开发看 Run 详情
```

### 16.2 迁移检查清单

| 从 CronPilot → Plombery | 从 Plombery → CronPilot |
| --- | --- |
| 每个 req\_url 改写成 @task 或 pipeline | 每个 pipeline 暴露 HTTP 端点作 req\_url |
| 接受「改代码+重启」替代 Web 改 cron | 接受「无实时日志流、无 task 输出 UI」 |
| 部署改为单 worker | 配置 Redis+MySQL 若要多节点 |
| 告警改为 Apprise 规则 | 告警改为 keyword + 企微/钉钉 |

## 17. CronPilot 可借鉴与优化（守正出奇）

**完整论证版（每条含：Plombery 对照 → 现状不足 → 为何优化 → 价值 → 优先级依据）：**
[**产品优化需求-借鉴Plombery.html（详版 PRD）**](产品优化需求-借鉴Plombery.html)

#### 必须保留的核心优势（优化时不得削弱）

- **HTTP 回调执行模型**：继续以 `req_url` 触发业务系统，不改为进程内执行 Python。
- **跨语言集成**：任何能接 GET 的服务均可接入，无需迁入 CronPilot 运行时。
- **Web/API 动态配置**：任务存 `cron_infos`，运维无需发版即可增删改定时规则。
- **Crontab 兼容 + 秒级**：字段级 cron 与一次性 `run_date` 保持现有语义。
- **集群能力**：保留 portalocker + Redis `@single_task`，优于 Plombery 默认单实例限制。
- **轻量部署**：Docker 一键、conf.ini、双 SQLite 开箱即用。
- **回调签名与 add\_log**：`cronpilot_sign`、长任务进度回传仍是差异化能力。

### 17.0 差距总览：为何需要优化

与 Plombery 对比，CronPilot 在**「调度触发」**上更强（跨语言、集群、动态配置），在**「一次执行的可观测闭环」**上明显偏弱。Plombery 用户默认拥有：Run 状态机、详情页、实时日志、失败原因；我方用户只能在表格里读一段 HTTP 响应，且 HTTP 500 可能仍显示为「成功」。

| 能力域 | Plombery 水平 | CronPilot 现状 | 差距等级 |
| --- | --- | --- | --- |
| 执行成败语义 | COMPLETED/FAILED 明确 | 仅 keyword + 异常；不看 status\_code | **高** |
| 排障路径 | Run 详情 + 日志流 | 表格 + iframe 碎片 | **高** |
| 安全（HTTP 模型特有） | 无 SSRF 面 | 任意 req\_url | **高** |
| 工程契约 | FastAPI+Pydantic | 双份校验、errcode 类型 bug | **中** |
| 集群扩展 | 弱（单 worker） | 双锁 + 多 worker | **我方优势** |

### 17.0.1 优先级定义

| 级别 | 判定 | 典型项 |
| --- | --- | --- |
| P0 | 不修可能出事或阻塞一切改造 | SQLi、SSRF、明文密码、校验双份 |
| P1 | 运维效率与「是否关心结果」的产品承诺 | status 字段、详情页、失败规则、立即执行 |
| P2 | 体验增强，有临时替代方案 | SSE、图表、metrics、OAuth |

以下分域摘要；每条 OPT 的完整对比与验收见 [详版 PRD](产品优化需求-借鉴Plombery.html)。

### 17.1 典型案例深剖：「平台是否关心执行结果？」

|  |  |
| --- | --- |
| Plombery | Task 异常 → `PipelineRunStatus.FAILED`；UI 红标；通知规则按 status 触发。用户无需读响应体。 |
| CronPilot 现状 | `crons.cron_do` 在 `requests.get` 成功后仅把 `req.text` 写入 `job_log.content`；另用 `error_keyword in ret` 决定是否 `wechat_info_err`。**不读取 `req.status_code`。** |
| 具体不足 | ① HTTP 502/500 常显示为「成功记录」；② 200 但业务失败且无关键词则静默；③ 列表无法筛失败；④ 与用户问「是否关心结果」的答案不一致。 |
| 优化（P1） | OPT-P1-01/02：`job_log.status` + `fail_on_http_4xx_5xx` + `fail_reason`。 |
| 价值 | 产品承诺可验证；告警准确率提升；对标 Plombery 的「执行结果语义」，而不改变 HTTP 回调模型。 |

详见 [OPT-P1-01](产品优化需求-借鉴Plombery.html#opt-p1-01)、[OPT-P1-02](产品优化需求-借鉴Plombery.html#opt-p1-02)。

### 17.2 分域优化清单与优先级

| 域 | ID | 优先级 | 现状核心问题 | 借鉴 Plombery 什么 | 价值一句话 |
| --- | --- | --- | --- | --- | --- |
| 安全/质量 | OPT-P0-01 | P0 | SQL 字符串拼接 | ORM 参数化 | 过安全审计 |
| OPT-P0-02 | P0 | 明文密码 | OAuth/Secret 体系 | 配置泄露不致命 |
| OPT-P0-03 | P0 | 任意 req\_url（SSRF） | （无此面，我方必补） | HTTP 模型安全闸门 |
| OPT-P0-04 | P0 | errcode 类型不一致 | HTTP 状态 + 稳定 JSON | Ajax/集成可靠 |
| OPT-P0-05 | P0 | Web/API 双份校验 | 单一边界校验 | 降本、防行为漂移 |
| 可观测/UI | OPT-P1-01 | P1 | 无单次执行 status | StatusBadge + Run 状态机 | 看得懂成败 |
| OPT-P1-02 | P1 | 不看 HTTP 状态码 | FAILED 语义 | 少漏告警 |
| OPT-P1-03 | P1 | iframe 碎片排障 | Run 详情路由 | 排障效率 |
| OPT-P1-04 | P1 | 无立即执行 | ManualRunDialog | 联调补跑 |
| OPT-P1-05 | P1 | add\_log 体验弱 | logger + WS | 长任务可观测 |
| OPT-P1-06~08 | P1 | 文档/模板/启动清理 | OpenAPI、Layout、自愈 | 专业可维护 |
| 体验/规模 | OPT-P2-01 | P2 | 无实时 | Socket.IO（我方用 SSE） | 实时感 |
| OPT-P2-02 | P2 | 无统计 | Runs 图表 | 管理可视化 |
| OPT-P2-03~05 | P2 | 调度/存储/监控 | coalesce、文件存储、metrics | 规模化 |
| OPT-P2-06~09 | P2 | 通知/OAuth 等 | Apprise、OAuth | 企业集成 |

每一行的「现状 → 对比 → 原因 → 价值 → 验收」见 [详版 PRD](产品优化需求-借鉴Plombery.html) 对应 OPT 卡片。

### 17.3 前端：为何不整站重写 React

**Plombery** 的体验来自 React + Query + WS，但代价是 Node 构建链、前端独立迭代、单 worker 约束。**CronPilot** 的用户看重 Docker 一键、无构建。优化应走：

- P1：状态徽章 + 详情页 + partial 模板（解决 80% 体感差距）
- P2：SSE + Chart.js（补实时与统计，仍 SSR）

这与 Plombery「组件化思想」对齐，而非「技术栈照搬」。

### 17.4 调度与集群：保持优势

Plombery 文档明确**禁止**多 worker 无锁扩展；CronPilot 的 portalocker + Redis 是差异化能力，**不应为对齐 Plombery 而削弱**。可借鉴的是：启动清理悬空状态（P1-08）、coalesce 可配置（P2-03）、文档化「推荐拓扑」。

### 17.5 明确不借鉴

进程内 Pipeline、纯代码注册、强制单 worker、整站 React、平台 DAG —— 均会牺牲 HTTP 跨语言或动态配置优势。组合方案：cron 回调 Plombery `POST /run`。

### 17.6 实施路线图

| 阶段 | 周期 | 交付 | 用户可感知价值 |
| --- | --- | --- | --- |
| Phase A | 1–2 周 | 全部 P0 | 「能放心上生产」— 安全与契约 |
| Phase B | 3–6 周 | P1 可观测包 | 「看得懂成败、点得进详情」— 对齐 Plombery 核心体验 |
| Phase C | 按需 | P2 选型 | 实时、图表、企业监控 |

**总结：**优化不是变成 Plombery，而是在**保留 HTTP 调度台 + 集群**前提下，补齐 Plombery 最强的**执行可观测闭环**与**工程规范**。详版论证与验收标准见
<产品优化需求-借鉴Plombery.html>。

参考：CronPilot 源码 · Plombery `docs/architecture.html` 与 `src/plombery`、`frontend/src`  
[返回文档索引](index.html)
· [Markdown](Plombery深度对比分析.md) · [索引](index.html)

---

[← 文档索引（HTML）](index.html) · [← 文档索引（Markdown）](index.md)
