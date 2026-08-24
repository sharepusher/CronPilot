# 操作记录 — CronPilot

> HTML 版：[oplog_debug.html](oplog_debug.html) · [文档索引](../../../index.html) · [索引 Markdown](../../../index.md)

[CronPilot](/)

运维操作

[任务中心](/)
[执行记录](/job_log_all_list)

系统配置

[业务组](/rbac/groups)
[标签](/rbac/tags)

系统管理

[用户管理](/rbac/users)
[注册审批](/rbac/registration_review)
[审计](/rbac/audit-logs)
[操作记录](/operation_log_list)

个人设置

[个人资料](/rbac/profile)
[修改密码](/rbac/password)
[API Token](/rbac/api_token)

开发者

[API 文档](/api_doc)

搜索任务或操作…
`⌘K`

A

admin
系统管理员

A

admin

系统管理员

[修改密码](/rbac/password)
[API Token](/rbac/api_token)[切换到经典界面](#)[退出登录](/rbac/logout)

# 操作记录

用户在控制台中的变更历史

本页为**任务配置变更**审计（创建 / 编辑 / 启动 / 暂停 / 下线）。登录与权限事件见[RBAC 审计](/rbac/audit-logs)。

全部操作
创建任务
修改任务
启动/暂停
下线任务
搜索

| ID | 用户 | 类型 | 内容 | IP | 时间 |
| --- | --- | --- | --- | --- | --- |
| 17 | davytest | 创建任务 | b4-browser-test · minute=\*/10、req\_url=https://httpbin.org/get | 127.0.0.1 | 2026-08-13 19:43:04 |
| 16 | davytest | 创建任务 | b4-test-task · hour=\*、minute=\*/5、req\_url=https://httpbin.org/get | 127.0.0.1 | 2026-08-13 19:42:21 |
| 15 | davytest | 下线任务 | tagged-task-test · 下线：下线 | 127.0.0.1 | 2026-08-10 17:47:24 |
| 14 | davytest | 暂停任务 | testbap · 暂停：运行中 → 已暂停 | 127.0.0.1 | 2026-08-10 17:47:12 |
| 13 | davytest | 创建任务 | testbap · hour=\*/2、req\_url=http://google.com | 127.0.0.1 | 2026-08-07 14:53:01 |
| 12 | testop | 创建任务 | cross-group-tag-test · minute=45、req\_url=https://example.com/crosstest | 127.0.0.1 | 2026-08-06 17:29:00 |
| 11 | testop | 创建任务 | tag-isolation-verify · minute=30、req\_url=https://example.com/tag-isolation-test | 127.0.0.1 | 2026-08-06 16:52:40 |
| 10 | testop | 创建任务 | payment-tag-isolation-test · minute=30、req\_url=https://example.com/payment-test | 127.0.0.1 | 2026-08-06 16:47:29 |
| 9 | testop | 修改任务 | tagged-task-test · 修改 | 127.0.0.1 | 2026-08-05 15:59:05 |
| 8 | testop | 创建任务 | tagged-task-test · minute=15、req\_url=https://example.com/tagged | 127.0.0.1 | 2026-08-05 15:54:52 |
| 7 | davytest | 修改任务 | global-shared-task · scope\_type GROUP→GLOBAL | 127.0.0.1 | 2026-08-05 15:30:45 |
| 6 | davytest | 修改任务 | global-shared-task · scope\_type GLOBAL→GROUP | 127.0.0.1 | 2026-08-05 15:30:28 |
| 5 | testop | 修改任务 | multi-group-test-task · 修改 | 127.0.0.1 | 2026-08-05 15:21:24 |
| 4 | testop | 修改任务 | multi-group-test-task · minute 1→5、task\_keyword 测试多组可见任务→测试多组任务 | 127.0.0.1 | 2026-08-05 15:21:08 |
| 3 | davytest | 创建任务 | admin-multi-group-task · minute=10、req\_url=https://example.com/admin-multi | 127.0.0.1 | 2026-08-05 14:43:49 |
| 2 | davytest | 创建任务 | global-shared-task · minute=5、req\_url=https://example.com/global-test | 127.0.0.1 | 2026-08-05 14:43:25 |
| 1 | testop | 创建任务 | multi-group-test-task · minute=1、req\_url=https://example.com/test-multi-group | 127.0.0.1 | 2026-08-05 11:52:53 |

17 total

[1](/operation_log_list?page=1)

`↑↓` 导航
`↵` 选择
`Esc` 关闭

[文档索引](index.html) · [Markdown](oplog_debug.md) · [索引](index.html)

---

[← 文档索引（HTML）](../../../index.html) · [← 文档索引（Markdown）](../../../index.md)
