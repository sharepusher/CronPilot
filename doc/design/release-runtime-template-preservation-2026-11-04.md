# 发布包运行时模板字节保护修复设计

> HTML 版：[release-runtime-template-preservation-2026-11-04.html](release-runtime-template-preservation-2026-11-04.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 发布包运行时模板字节保护修复设计

2026-11-04 · v1 · 待用户确认，未修改实现 · 阻断 v4.2.0 发布 · [Before/After 页面行为对比](#page-compare)

## 版本记录

v1：实际最终包检查发现运行时模板遭文档重写，提供代码与包双侧证据、最小修复和验收。

## 交付契约

对象：Git 提交→公开 tar.gz→Flask/Jinja 页面；调用方：本地发布命令和 tag workflow；认证沿用现有登录与 RBAC；版本来源固定 Git SHA；文档可按明确范围改写链接，运行时代码/模板必须原字节保留；异常构建不得标记 ready。证据同时记录源模板可解析、包模板不可解析、解压包有执行记录时 GET/AJAX 返回及修复后分页 URL。无 API 字段变化，不修改业务权限，不产生截图。

## 1. 问题与证据

P1：最终包 07dddb3 的 app/templates/redesign/\_exec\_logs\_pagination.html 被改写。源码 Jinja parse 通过；包内 parse 报 TemplateSyntaxError：Encountered unknown tag 'endif'，期待 endfor。execution\_logs.html 在 page\_data.items 非空时 include 该模板，所以有记录的执行日志页及复用该模板的 AJAX 会失败；不是只在超过一页时发生。空库黄金路径没有进入此分支。

失败附件已隔离到 /private/tmp/cronpilot-v420-blocked-07dddb3，不应上传。既有 check\_release\_asset.py 仍退出 0，说明当前独立资产检查未覆盖 Jinja 可解析性/运行时字节完整性。

## 2. 根因

已读 scripts/build\_release\_asset.py:21–26、114–147、180–200：rewrite\_links 仅按 .html/.md/.htm 扩展名挑选，运行时 app/templates/\*.html 也进入文档重写。HTML\_LINK\_RE 在双引号 href 内遇到 keywords.get('task\_name') 的单引号提前截断；query-only URL 的空 path 又被 resolved\_repo\_target 解释为模板父目录，public\_url 将其换成 GitHub tree 链接，删除原 Jinja if 前缀却保留 endif，导致语法损坏。发布包与源码测试输入不是同一个制品。

## 3. 方案

1. 给文档链接重写增加明确路径边界：只处理根级发布 Markdown 和 doc/ 下已选的文档；app/、frontend/、scripts/ 等运行时文件原字节保留，不凭后缀判定文档身份。根级文档和 doc/ 仓库外链接重写继续保留。
2. 对 query-only/空 path 的文档链接返回无需重写；其语义是当前文档查询，不是父目录链接。保留外链、锚点及合法文档路径的现有行为。
3. 为 tests/test\_release\_asset.py 增加真实 Jinja 分页模板及包含引号、查询参数的夹具，构建后断言 app 文件字节与 Git blob 相同；对实际包模板做 Jinja parse/render，并断言 href 保持 ?page=... 与筛选参数。保留确定性和文档链接重写原回归。

### 页面行为对比（无截图）

依据已读 execution\_logs.html:15–88、\_exec\_logs\_rows.html:1–63；不改变设计列数、筛选器或状态单元，仅恢复源码既有页面行为。

#### BEFORE · 解压包有执行记录

##### 执行记录

HTTP 500 · TemplateSyntaxError: unknown tag endif

记录列表无法正常渲染；空库页面不能发现此问题。

#### AFTER · 同一执行记录

##### 执行记录

结果：非成功 / 全部 / 进行中 / 仅失败 / 仅异常 / 仅成功

| # | 任务名称 | 返回内容 | 执行时间 | 耗时 | 结果 | 操作 |
| --- | --- | --- | --- | --- | --- | --- |
| 1001 | 验收任务 | HTTP 500 | 验收时间 | 1s | ● 失败 | 详情 |

‹ 1 2 › · 链接保持当前站点查询参数；原有筛选与 AJAX 行为保持。

## 4. 范围

scripts/build\_release\_asset.py、tests/test\_release\_asset.py、发布设计/复盘/验收和 ready 清单；不修改 app 模板/CSS/JS、API、业务模型、权限、截图资产或 workflow 信任边界。本次不处理已延期的自动发布仓库上下文问题。

## 5. 分批

1. B1：确认本文后，先补构建模板原字节/解析与 query-only 失败回归。
2. B2：按路径限制文档重写并处理空 path；保持其余打包行为；聚焦测试及真实包对比。
3. B3：复盘、全量回归、真实包双构建、独立资产检查、全模板解析与有记录 GET/AJAX/翻页验收；使用隔离数据，自动操作但不生成截图。
4. B4：全部通过后归档 ready、提交、按最终 SHA 重建附件并确认工作区干净；用户再手动 tag/push/Release。

## 6. 验收

聚焦：.venv-py311/bin/python -m unittest tests.test\_release\_asset -v；全量：.venv-py311/bin/python -m unittest discover -s tests -p 'test\_\*.py'；Ruff app、文档/版本/图片/术语门禁。构建脚本从真实候选 commit 双构建，cmp 相同，check\_release\_asset.py 通过；逐个比较包内 app/、frontend/、scripts/ 原字节与 Git blob，所有 Jinja 模板可解析（按实际应用环境注册过滤器与扩展）。仓库外安装黄金路径外加至少一条执行记录、两页数据、有筛选参数的 GET/AJAX/翻页路径，断言 200、7 列、链接不跳 GitHub、筛选保留。无截图。

## 7. 风险

路径限制可能遗漏新的根文档，需用现有清单验证保留链接重写范围；不扩大到运行时 HTML。包内相对文档链接检查继续使用现有独立检查。不得为了保模板而取消全部文档重写。缺任何制品级验收都维持 blocked；已生成失败包仅保留诊断，不能作为发布附件。

## 当前验证结果（未修复）

0e31f8f 业务及 73854ac 归档候选全量 1168 tests / OK / skipped=12；07dddb3 双构建相同、资产检查通过，但该包模板 parse 明确失败。新回归尚未编写，B1–B4 均未实施。状态清单已改 blocked，不能把源码绿色结果代替包页面验收。

## 历史归因核验（2026-11-04）

git blame -L 114,147 scripts/build\_release\_asset.py 指向 bed58fdad7aa4771a21cf6cffef99dccacf8e725（2026-10-14，build: add image governance and release tooling）。git diff v4.1.1..HEAD -- scripts/build\_release\_asset.py app/templates/redesign/\_exec\_logs\_pagination.html release/package-manifest.txt 为空；本轮发布收尾未改这三个输入，0e31f8f..HEAD 的改动仅是文档与发布状态清单。

实际历史重现：.venv-py311/bin/python scripts/build\_release\_asset.py --version 4.1.1 --ref v4.1.1 --output /private/tmp/cronpilot-v411-historical-reproduction/cronpilot-4.1.1.tar.gz 成功。直接解析 v4.1.1 Git blob 的该模板通过；对该重建 tar 中模板执行同一 Jinja parse，报相同 TemplateSyntaxError: Encountered unknown tag 'endif'（期待 endfor）。故已证实仓库内历史打包逻辑在 v4.1.1 已有此缺陷，本轮只是重建并发现，没有引入打包器回归。

边界：未下载、核对之前实际上传的 GitHub Release 附件，不能据此断言历史线上部署一定使用了损坏包。直接从 Git 源码运行不会经过文档重写。此次交付问题是源码/空库门禁未覆盖非空执行记录的最终制品，曾过早将状态置为 ready；已按实际制品失败撤回。

## 文档验收结果

.venv-py311/bin/python scripts/html\_docs\_to\_markdown.py --check、scripts/check\_doc\_completeness.py --check、scripts/check\_doc\_links.py --check、scripts/check\_opt\_consistency.py --check，以及 bash scripts/check\_pending\_sync.sh、git diff --check 均退出 0；413 个 HTML 已登记，3156 个引用无 broken。scripts/check\_version\_consistency.py --check --tag v4.2.0 退出 1，明确因 blocked 与非空 release\_blockers 拒绝发布，这是当前预期门禁结果。

[Markdown](release-runtime-template-preservation-2026-11-04.md) · [文档索引](../index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
