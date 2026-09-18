# CronPilot · 复盘文档索引

[← 返回文档总索引](../index.html)

本目录汇总 CronPilot 事后复盘文档（Bug 分析、事故回顾、预防方案等）。

## 安全与前端关键问题

- [安全问题 S1–S5 修复复盘](2026-08-security-S1-S5.html)
- [P0 前端关键 Bug 复盘](2026-08-P0-frontend-bugs.html)
- [全面 Code Review 综合复盘](2026-08-全面CodeReview复盘.html)
- [SEC-6 SSRF DNS Fail-Open 修复](2026-08-SEC6-SSRF-dns-fail-open.html)
- [停用用户同名覆盖启用（OPT-P0-22）](2026-09-停用用户同名恢复.html)
- [auth_version Session 缺键 Fail-Open](2026-09-auth-version-session-failopen.html)
- [全局管理员可停用种子账号](2026-09-全局管理员可停用种子账号.html)
- [执行详情 URL 脱敏缺失修复](2026-09-execution-detail-url-redaction.html)（Presenter 边界 · 全参数值脱敏，2026-09-15）
- [执行失败分类与 HTTP 响应语义](2026-09-执行失败分类与HTTP响应语义.html)（TypeError 误归类 · 无响应语义缺失，2026-09-18）
- [执行侧观测传输状态误导修复](2026-09-执行侧观测传输状态误导修复.html)（连接失败/已发送未响应分流，2026-09-18）
- [执行侧观测 sent 状态判定修复](2026-09-执行侧观测sent状态判定修复.html)（Presenter/模板契约对齐，2026-09-18）
- [Run Inspector HTTP 状态标签未消费修复](2026-09-RunInspector-http状态标签未消费修复.html)（Presenter/模板字段对齐，2026-09-18）
- [执行侧观测外层 fatal 阶段映射修复](2026-09-执行侧观测外层fatal阶段映射修复.html)（outer fatal 三阶段映射，2026-09-18）
- [执行侧观测 R1 状态兜底修复](2026-09-执行侧观测R1状态兜底修复.html)（三角色传输状态兜底，2026-09-18）
- [执行侧观测 R2 异常矩阵修复](2026-09-执行侧观测R2异常矩阵修复.html)（异常子类/response 证据分流，2026-09-18）
- [PinnedIPAdapter HTTP 协议参数错误](2026-09-PinnedIPAdapter-HTTP协议参数错误.html)（HTTP 误传 TLS 参数 · HTTP/HTTPS 分支修复，2026-09-18）
- [任务详情 seconds 展示丢失修复](2026-09-task-detail-seconds-display.html)（调度表达式完整性 · 六字段展示，2026-09-16）
- [Dashboard 相对时间测试确定性修复](2026-09-dashboard-relative-time-test-determinism.html)（可注入时间基准 · 消除时钟漂移，2026-09-16）
- [全量回归门禁收口修复](2026-09-regression-gate-cleanup.html)（legacy 门禁 · 无上下文日志，2026-09-16）
- [ORM legacy 门禁误报修复](2026-09-ORM-legacy-urlsplit误报修复.html)（urlsplit 别名与 `.query` 误报，2026-09-18）
- [Run Inspector raw detail 与时间线顺序](2026-09-RunInspector-raw-detail与时间线顺序.html)（禁 JSON · 时间线上移，2026-09-16）
- [执行记录 pending 误标「未知」](2026-09-执行记录pending误标未知.html)（已入队徽章 · in_progress 白名单，2026-09-16）
- [任务中心下线异常任务](2026-09-任务中心下线异常任务Bug修复复盘.html)（下线任务排除异常提醒面板，2026-09-09）
- [下次执行相对时间误显示](2026-09-下次执行相对时间误显示.html)（空 minute vs APScheduler 默认 0 · 已修复，2026-09-16）

## Redesign UI

- [Phase 2 Mockup 偏离复盘](2026-08-Phase2-Mockup偏离复盘.html)
- [Redesign 功能页 77 个质量缺陷结构性复盘](2026-08-Redesign功能页质量缺陷结构性复盘.html)
- [Redesign 筛选交互降级复盘](2026-08-Redesign筛选交互降级.html)
- [Redesign CSS 硬编码颜色修复](2026-08-redesign-css-hardcoded-colors.html)
- [Dashboard AJAX 路径错误 F1+F2+F3](2026-08-dashboard-ajax-path.html)
- [F5 jQuery defer 致 inline script 失效](2026-08-F5-jQuery-defer-inline-script.html)
- [标签页 Bootstrap Modal 迁移](2026-08-Z3-标签页Bootstrap模态框迁移.html)
- [确认对话框修复与个人资料页](2026-08-确认对话框修复与个人资料页.html)
- [Dashboard 表格操作列溢出修复](2026-09-Dashboard表格溢出修复.html)
- [R3-C 设计偏离原方案 Demo UI](2026-09-R3-C设计偏离原方案DemoUI.html)（子设计 AFTER 须锚定父 Demo §B，2026-09-16）
- [误把 Demo §C 当成 §B](2026-09-误把Demo-C当成-B.html)（多节 Demo 须写明节号，2026-09-17）
- [Tier 3-5 代码质量修复](2026-08-tier345-code-quality.html)

## 表单与 UX

- [change_password 嵌套 form](2026-08-change-password-nested-form.html)
- [用户管理页 UX 三 Bug](2026-08-users-ux-bugs.html)
- [cron_add 错误重定向 + CpModal 全局化](2026-08-cron-add-error-redirect-and-modal-globalization.html)
- [标签管理增强 OPT-P1-11](2026-08-标签管理增强.html)

## 基础设施与工程

- [users_reset_password 装饰器丢失](2026-08-missing-route-decorator.html)
- [迁移脚本清零有效时间戳](2026-08-迁移脚本清零有效时间戳.html)
- [文档链接 140 处 broken](2026-08-doc-links-broken-index.html)
- [check_ui_contract 子字符串误报](2026-08-check_ui_contract-false-positive.html)
- [test_rbac_phase 测试维护债务](2026-08-test-rbac-phase-maintenance-debt.html)
- [Release Notes Unreleased 残留清理](2026-09-release-notes-unreleased-cleanup.html)
- [质量门禁四项修复复盘](2026-09-质量门禁四项修复复盘.html)
- [触发术语全仓治理](2026-09-trigger-terminology-cleanup.html)
- [调度器幽灵任务清理复盘](2026-08-调度器幽灵任务清理复盘.html)
- [文档索引结构损坏与登记丢失](2026-09-文档索引结构损坏与登记丢失.html)（剪贴断裂 · 登记删除 · 索引结构门禁，2026-09-11）
- [评估交付格式与测试状态漂移](2026-09-评估交付格式与测试状态漂移.html)（Canvas 误作交付 · 测试状态错误标记，2026-09-11）
- [P1 测试夹具认证契约漂移](2026-09-P1测试夹具认证契约漂移.html)（Session schema fixture · 模型注册顺序，2026-09-11）
- [P2 触发 URL 签名与记录不一致](2026-09-P2触发URL签名与记录不一致.html)（fragment 解析 · PreparedRequest · 脱敏边界，2026-09-11）
- [设计 Demo HTML 未入库丢失](2026-09-设计Demo未入库丢失.html)（未跟踪 Demo 被删无法恢复 · 索引链接门禁，2026-09-14）
- [健康度未满阈值误标「健康」](2026-09-健康度未满阈值误标健康.html)（失败 1～2 次勿标健康 · 方案 A，2026-09-16）
- [UX 设计方案与页面对比拆分](2026-09-UX设计方案与页面对比拆分.html)（单页 UX 误拆独立 Demo · 默认内嵌，2026-09-16）
- [B1 认证夹具复盘与修复计划](2026-09-B1认证夹具复盘与修复计划.html)（Review 未通过 · 30 失败 + 5 错误 · 2026-09-14）
- [任务链路日志三个 Bug 修复](2026-09-任务链路日志Bug修复复盘.html)（NameError / 签名脱敏 / to_json 死字段，2026-09-07）

## 流程与元复盘

- [元复盘：Agent 复盘失效机制](2026-08-元复盘-复盘失效机制.html)
- [错误 Mockup 文件评估复盘](2026-08-错误Mockup文件评估复盘.html)
- [统一手册数值重复偏离](2026-08-统一手册数值重复偏离.html)
