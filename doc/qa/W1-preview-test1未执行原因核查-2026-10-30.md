# W1 预览 test1 未执行原因核查

> HTML 版：[W1-preview-test1未执行原因核查-2026-10-30.html](W1-preview-test1未执行原因核查-2026-10-30.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# W1 预览 test1 未执行原因核查

2026-10-30 · 只读核查完成；未修改实现、任务数据或服务开关。

## 结论

127.0.0.1:5002 是 W1 表单验证用隔离预览。其启动脚本显式设置 CRONPILOT\_SCHEDULER\_ENABLED=false，未启动调度器；因此可以保存任务，但不会定时触发 HTTP 请求，也不会生成执行记录。该结论仅针对 W1 预览实例。

## 证据与可重现命令

- `lsof -nP -iTCP:5002 -sTCP:LISTEN`：Python PID 35307。
- `ps -p 35307 -o pid=,command=`：运行 /private/tmp/cronpilot\_w1\_isolated\_browser.py。
- `sed -n '1,100p' /private/tmp/cronpilot_w1_isolated_browser.py`：第 11 行关闭调度器；W1\_PREVIEW 分支创建 w1\_preview，使用临时隔离数据库和 5002 端口。
- `lsof -p 35307 -Fn`：隔离数据库为 /private/var/folders/9s/vb2p40tn0c53xs0dl5xsmy1c0000gn/T/cronpilot-w1-browser-ljlaz8r3/isolated.sqlite。
- 对上述库执行 `sqlite3 -readonly -header -column 数据库路径 "select id,task_name,status,hour,minute,last_operator_name from cron_infos where task_name='test1'; select count(*) as total_job_logs from job_log; select count(*) as scheduled_jobs from apscheduler_jobs;"`：test1 id=2、status=1、hour=\*、minute=\*/2、last\_operator\_name=w1\_preview；执行日志总数 0；调度 Job 总数 0。

## 原因链路

app/\_\_init\_\_.py 的调度开关分支在 false 时只初始化 scheduler，不调用 start()；预览脚本也没有后续启动调度器。数据库任务的运行中状态只说明业务配置已启用，不能证明当前进程有活动调度循环。此处没有证据表明问题来自用户权限或两分钟表达式。

## 处理边界

需要真实执行时，须提供启用调度器的隔离运行环境，并验证定时触发与日志生成；当前脚本定位为表单预览。此次仅回答原因，不擅自启用现存任务的外部请求。临时目录和进程信息为本次核查快照。

[文档索引](../index.html) · [Markdown 版](W1-preview-test1未执行原因核查-2026-10-30.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
