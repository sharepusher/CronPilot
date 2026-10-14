# 任务触发 URL 3xx 失败语义与 Pinning 修复设计（2026-10）

> HTML 版：[任务触发URL-3xx失败语义与Pinning修复设计-2026-10.html](任务触发URL-3xx失败语义与Pinning修复设计-2026-10.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 任务触发 URL 3xx 失败语义与 Pinning 修复设计

版本：rev.2 · 日期：2026-10-10 · 状态：**已确认并实施** · 关联：[代码全面 Review](../qa/2026-10-10-代码全面Review与未提交变更评估.html)、[复盘](../postmortem/2026-10-10-任务触发安全与测试契约漂移复盘.html)

**实施记录：**用户于 2026-10-10 明确确认实施 A→B→C。A/B/C 的代码和测试契约均已完成；完整测试套件 832 项通过、12 项跳过。关联的 MySQL ID 迁移仅完成方言/SQLite 回放测试，本机未安装 MySQL 客户端，真实 MySQL 临时库演练仍是关联迁移的独立发布前事项。按交付规程重启本地服务并探测 `/rbac/login` 时，宿主环境拒绝监听 127.0.0.1:5001（日志 `Operation not permitted`，HTTP 为 000），故真实浏览器 POST 登录未执行；该环境阻塞不以测试通过替代。

## 1. 问题

`app/crons.py` 已为任务触发请求设置 `allow_redirects=False`，因此 3xx 表示仅收到首跳响应，配置的触发 URL 不会自动请求 Location 目标。然而 `app.services.job_log_outcome.evaluate_http_response()` 仅把 4xx/5xx 判为失败，导致 3xx 被写成 success。管理员通过定时执行或“立即执行”看到成功日志，但目标服务未被请求。

当前本地配置库的 `test163`、`testgoogle` 共出现 47 条 301；历史上都以 `redirect_limit` 显性失败，未发现成功完成自动跳转的任务。本设计消除假成功，不恢复自动跳转。

## 2. 根因

请求传输策略改变后，HTTP 响应到 JobLog 的结果分类没有同步更新。恢复 requests 默认跳转也不可取：跨协议 Location 会绕过仅挂载在首跳协议上的 pinned adapter；同协议跨主机时 adapter 仍使用首跳 IP/Host。另有 IPv6 地址直接拼入 netloc，缺少 RFC 3986 方括号，AAAA 解析会在 requests 层失败。

## 3. 推荐方案与取舍

**推荐：**保持 `allow_redirects=False`，将 300–399 无条件映射为 `STATUS_FAIL` 与稳定原因 `redirect_blocked`；在执行事件中仅记录脱敏后的跳转目标摘要；为 IPv6 pinned IP 生成方括号 netloc；删除失效的 DNS fail-open 配置和文档承诺。

**拒绝：**恢复 requests 自动跳转。它既无法保证每一跳重新 URL 校验与 DNS pinning，也会让 POST 在 301/302/303 时被库默认改写为 GET，并丢失既有签名/追踪参数的明确契约。

**后续能力（不属于本设计）：**若未来有已确认的业务必须跟随跳转，另建设计，实现每跳 URL 解析、校验、DNS、新 pinned session、方法/签名策略和最大跳数；不得由本次修复隐式开启。

## 4. 范围与非范围

- 修改任务触发路径 `cron_do()` 的响应结果语义、执行事件白名单和对应测试。
- 修改 pinned URL 重写的 IPv6 netloc 表示及对应测试。
- 移除不再生效的 `url_ssrf_dns_fail_open` 代码、样例配置与 Release Notes 承诺，并验证 DNS 失败恒定拒绝。
- 修正本轮暴露的 ID 策略测试与执行日志裸子串断言，恢复全量测试可信度。
- **不做：**不改登录、Session、Flask 浏览器跳转、页面模板/CSS/JS；不自动修改任何 `req_url`；不访问或猜测外部目标地址；不实现逐跳跳转能力。

## 5. 页面可见结果对比

无页面结构或交互变更；唯一可见差异是既有执行日志对同一首跳 301 的事实分类。

| BEFORE：当前未提交行为 | AFTER：本设计行为 |
| --- | --- |
| ``` 任务：test163；操作：定时 / 立即执行；首跳：HTTP 301 Location: …；执行结果：成功；实际：没有请求 Location 目标 ``` | ``` 任务：test163；操作：定时 / 立即执行；首跳：HTTP 301 Location: …；执行结果：失败（redirect_blocked）；实际：没有请求 Location 目标 ``` |

## 6. 分批实施

| 批次 | 改动 | 退出条件 |
| --- | --- | --- |
| A：结果准确性 | 为 3xx 增加 `redirect_blocked`；记录脱敏 Location 摘要，且不记录 query 值或凭据。 | 本地 HTTP server 返回 301/302/307/308 时，目标 handler 未被调用、JobLog 为 fail、http\_status 保留首跳状态。 |
| B：地址与配置契约 | IPv6 netloc 加方括号；移除失效 fail-open 开关及承诺。 | IPv4/IPv6、HTTP/HTTPS、端口有无的 adapter 测试通过；DNS 失败在配置键不存在、0、1 三种输入下均拒绝。 |
| C：门禁可信度 | 改为数据库自增 ID 行为断言；执行日志筛选改为结构化行 ID 断言。 | 相关测试和完整测试套件完成并通过；MySQL 临时库验证 BIGINT 迁移保留索引、nullable 与自增语义。 |

## 7. 验收

- `.venv-py311/bin/python -m unittest tests.test_b1_execution_status tests.test_cron_execution_transport -v`：覆盖 GET/POST × 301/302/303/307/308；本设计仅断言均为 fail，不请求目标。
- `.venv-py311/bin/python -m unittest tests.test_p0_phase_a tests.test_config_keys -v`：覆盖 IPv6 和 fail-closed 配置行为。
- `.venv-py311/bin/python -m unittest tests.test_job_health tests.test_exec_logs_partial -v`：测试契约不再依赖 50-bit 或裸数字。
- `bash scripts/cronpilot.sh test`：必须取得完整完成态成功输出；再执行 MySQL 临时库迁移演练。
- 服务重启后，以有 `cron:write` 权限的测试账户登录，执行一个本地 302 夹具任务的“立即执行”：页面可打开日志详情且结果为失败 `redirect_blocked`；正常登录、退出和普通页面跳转仍正常。

## 8. 风险与回滚

风险是原来依赖跳转的任务会从循环/假成功变为明确失败；这正是安全与可观测性要求。任务负责人可在确认业务目标后把 `req_url` 调整为直接地址，但不可通过恢复自动跳转绕过本设计。若本批出现回归，仅回滚本批代码与配置文档；不得回滚为不受校验的自动跳转。

**实施边界：**A→B→C 已按本设计实施。任务 URL 数据调整及“安全逐跳跳转”仍不在本次授权范围。

[文档索引](../index.html) · [Markdown](任务触发URL-3xx失败语义与Pinning修复设计-2026-10.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
