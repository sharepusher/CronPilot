# CronPilot UI X2+X3 对比 Demo

> HTML 版：[UI重设计-X2X3对比Demo.html](UI重设计-X2X3对比Demo.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# X2 + X3 对比 Demo

任务中心两处偏差的当前状态 vs 建议修复方案 · 2026-08-18

X2

## Exception Panel："查看详情 →" → icon-btn

★★ 中

主任务表格的操作列已是 icon-btn 风格（✓ 已符合）。
剩余偏差仅在 **Exception Panel（需要关注的任务）**中——每行末尾的"查看详情 →"是文字链接，与整体 icon-btn 风格不一致。

当前：文字链接"查看详情 →"

需要关注的任务（3）

×411
testbap
最近失败 2026-08-10
[查看详情 →](#)

×103
admin-multi-group-task
最近失败 2026-08-19
[查看详情 →](#)

×97
global-shared-task
最近失败 2026-08-19
[查看详情 →](#)

问题
"查看详情 →" 为文字链接；与主表格 icon-btn 风格不一致；文字占据横向空间

建议：改为执行记录 icon-btn

需要关注的任务（3）

×411
testbap
最近失败 2026-08-10

×103
admin-multi-group-task
最近失败 2026-08-19

×97
global-shared-task
最近失败 2026-08-19

修复
改为与主表格相同的文档 icon-btn；tooltip 提示"查看执行记录"；视觉更紧凑

X3

## 页头右侧：统计数字 → "新建任务" btn-primary

★★ 中

"新建任务"按钮已存在于过滤栏末尾（有 cron:write 权限时显示）。
Mockup 要求：将其提升到**页头右侧**，改用 `btn-primary` 样式，增强视觉层次感。
过滤栏末尾的按钮可以保留或移除（建议移除以避免重复）。

当前：页头显示统计数字；"新建"在过滤栏末尾

# 任务中心

管理与监控所有定时任务

**8** 个任务 · 8 连续失败 · 6 今日告警

全部
连续失败
今日失败

运行中
全部（可见）

新建任务

问题
页头右侧是统计数字而非 CTA 按钮；"新建任务"混在过滤栏末尾，视觉权重低，不符合 Mockup 主操作突出模式

建议：页头右侧放 btn-primary；统计数字保留在页头左侧副标题区

# 任务中心

管理与监控所有定时任务 · **8** 个任务 · 8 失败

新建任务

全部
连续失败
今日失败

运行中
全部（可见）

修复
"新建任务"移到页头右侧，改用 btn-primary 强调色；统计数字融入副标题行；过滤栏仅保留过滤功能

## 变更总结

| ID | 页面 | 具体变更 | 文件 | 工作量 |
| --- | --- | --- | --- | --- |
| X2 | 任务中心 · Exception Panel | 将每行"查看详情 →"文字链接替换为文档 icon-btn（与主表格一致） | dashboard.html | XS（10 min） |
| X3 | 任务中心 · 页头 | ① 页头右侧改为 btn-primary "新建任务"（有 cron:write 时）；② 统计数字移入副标题行；③ 过滤栏末尾按钮移除 | dashboard.html | S（20 min） |

[文档索引](index.html) · [Markdown](UI重设计-X2X3对比Demo.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
