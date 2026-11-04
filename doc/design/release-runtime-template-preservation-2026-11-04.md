# 发布包运行时模板字节保护修复设计

> HTML 版：[release-runtime-template-preservation-2026-11-04.html](release-runtime-template-preservation-2026-11-04.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 发布包运行时模板字节保护修复设计

2026-11-04 · v4 · 已按确认方案修复并验收，发布状态 ready，待用户手动发布 · 阻断 v4.2.0 发布 · [Before/After 页面行为对比](#page-compare)

## 版本记录

v4（2026-11-04）：B1–B4 验收完成，源码修复提交 d074674；最终发布文档和 ready 清单收口后从最终 SHA 重建附件，来源以 build.json 为准，不将未来 SHA 写回源文件造成循环。

v3（2026-11-04）：用户回复“确认实施”。已按 v2 修改构建器、独立检查器与测试；旧实现 5 项包回归出现 2 失败、1 错误，修复后发布专项 11/11 通过。全量及最终包链路验收进行中，发布仍 blocked。

v2（2026-11-04）：全包原字节及全模板复核；补入独立检查器的 query-only 契约对齐，明确三文件实现范围和分层验收；区分直接证据与路由推断。用户本轮只要求分析，未视为实现确认。

v1：实际最终包检查发现运行时模板遭文档重写，提供代码与包双侧证据、最小修复和验收。

## 交付契约

对象：Git 提交→公开 tar.gz→Flask/Jinja 页面；调用方：本地发布命令和 tag workflow；认证沿用现有登录与 RBAC；版本来源固定 Git SHA；文档可按明确范围改写链接，运行时代码/模板必须原字节保留；异常构建不得标记 ready。证据同时记录源模板可解析、包模板不可解析、解压包有执行记录时 GET/AJAX 返回及修复后分页 URL。无 API 字段变化，不修改业务权限，不产生截图。

## 1. 问题与证据

P1：07dddb3 的最终 tar 共 301 个文件。按“根级 Markdown + doc/ 内 Markdown/HTML/HTM”为文档范围，另外 279 个文件应原字节保留；逐个与构建报告所列 Git blob 对比，仅 app/templates/redesign/\_exec\_logs\_pagination.html 不同。40 个源模板语法解析全部通过；40 个包内模板中只有这一份解析失败，错误为未知 endif，期待 endfor。该模板发生 3 次链接重写；全包重写总数为 1837，其中另外 1834 次属于文档文件。

源码路由已读 app/main/views.py:581–655、726–793 和 execution\_logs.html:70–92：普通 GET 在 page\_data.items 非空时 include 该模板；partial=1 分支则无论有无结果都会直接渲染分页模板。因此影响包括“有记录的普通页面”和“进入正常 partial 分支的空/非空 AJAX 请求”。无记录的普通页面绕开 include，空库黄金路径没有覆盖这些分支。

证据边界：本轮直接执行了 Git blob 与包字节比较、Jinja 语法解析；HTTP 500 是基于已读路由和模板链的确定性推断，尚未以解压服务执行该故障 HTTP 请求。没有把解析通过等同于过滤器、继承、路由或浏览器全部通过。失败附件在 /private/tmp/cronpilot-v420-blocked-07dddb3，禁止上传。

可复现分析材料：[只读诊断脚本](../qa/evidence/release-runtime-template-analysis-2026-11-04/probe.py)、[实际结果](../qa/evidence/release-runtime-template-analysis-2026-11-04/results.json)。该脚本不是修复实现，也不是已新增的回归测试。

## 2. 根因

已读 scripts/build\_release\_asset.py:21–26、114–147、180–200：rewrite\_links 仅按 .html/.md/.htm 扩展名挑选，运行时 app/templates/\*.html 也进入文档重写。HTML\_LINK\_RE 在双引号 href 内遇到 keywords.get('task\_name') 的单引号提前截断；query-only URL 的空 path 又被 resolved\_repo\_target 解释为模板父目录，public\_url 将其换成 GitHub tree 链接，删除原 Jinja if 前缀却保留 endif，导致语法损坏。发布包与源码测试输入不是同一个制品。

## 3. 方案（v2 推荐）

1. **主修复：按发布文档身份限制重写。**仅允许已选入包的根级 Markdown，以及 doc/ 路径组件下且后缀属于 .md/.html/.htm 的文档进入链接处理。其余所有文件在 UTF-8 解码和正则执行前直接原样返回，包括 app/、frontend/、scripts/、datas/、配置和其他运行时输入。这里的 doc/ 是完整目录组件，不能误匹配 docs/、doc-example/ 或文件名中含 doc 的路径。该规则与现有独立检查器的根文档/doc 扫描边界对齐，不再用“所有 HTML”推断文档身份。
2. **次修复：正确处理当前文档查询。**构建器对无路径的 ?page=2、?page=2#part 等引用不做父目录查找或外链重写，保留原字节。已有空值、锚点、外链、包内相对路径和指向仓库外文档的行为分别回归。非空路径链接的查询迁移策略不在本次扩大。
3. **契约补齐：独立检查器同步 URL 语义。**scripts/check\_release\_asset.py 的 normalize\_target 同样将无路径引用认作当前文档，不以 doc 目录或空字符串充当待查找文件。否则新增的正确查询链接夹具会被误报断链。只调整该语义，不引入 Jinja/Flask 依赖，不把独立标准库资产检查器改成应用启动器，也不共享构建器实现函数掩盖同源错误。
4. **防复发：对包做独立验证。**tests/test\_release\_asset.py 加入真实 Jinja 分页模板、其他运行时 HTML/MD/二进制字节夹具，构建后与临时 Git fixture 的原始 blob 逐字节相等；预期由夹具定义，不能调用构建器的分类函数计算“应该保留”的集合。再单独验证包内模板可解析/渲染、分页参数及文档重写正反向路径。最终真实包的全部非文档文件均执行独立 Git blob 比对，不能只检查已知的一个模板。

### 页面行为对比（无截图）

依据已读 execution\_logs.html:15–88、\_exec\_logs\_rows.html:1–63；不改变设计列数、筛选器或状态单元，仅恢复源码既有页面行为。

#### BEFORE · 解压包有执行记录

##### 执行记录

模板链推断 HTTP 500 · 已直接复现 TemplateSyntaxError: unknown tag endif

记录列表无法正常渲染；空库页面不能发现此问题。

#### AFTER · 同一执行记录

##### 执行记录

结果：非成功 / 全部 / 进行中 / 仅失败 / 仅异常 / 仅成功

| # | 任务名称 | 返回内容 | 执行时间 | 耗时 | 结果 | 操作 |
| --- | --- | --- | --- | --- | --- | --- |
| 1001 | 验收任务 | HTTP 500 | 验收时间 | 1s | ● 失败 | 详情 |

‹ 1 2 › · 链接保持当前站点查询参数；原有筛选与 AJAX 行为保持。

## 4. 范围

scripts/build\_release\_asset.py、scripts/check\_release\_asset.py、tests/test\_release\_asset.py，以及发布设计/复盘/验收和状态清单；不修改 app 模板/CSS/JS、API、业务模型、权限、截图资产或 workflow 信任边界。本次不处理已延期的自动发布仓库上下文问题。

## 5. 分批

1. B1：v2 明确确认后，补运行时字节不变、模板语法、文档重写、query-only 构建/检查端到端失败回归；先记录当前实现如何失败。
2. B2：按路径限制重写，构建器和独立检查器各自修正空 path 语义；不改应用模板，不引入依赖，不处理其他 HTML/Markdown 语法扩展。
3. B3：聚焦及全量回归；真实包双构建、截图排除、独立资产检查、全包原字节对比及模板解析；隔离安装后覆盖普通 GET/AJAX 空结果/非空结果及两页筛选翻页，自动操作但不生成截图。
4. B4：七项复盘与文档门禁通过，再记录 ready 并提交；从最终提交重新构建，核对来源/校验和和工作区清洁；不让用户再手动补检查。用户仍负责最终 tag/push/网页 Release。

## 6. 验收与判定标准

1. **字节边界：**正向文档 fixture 只有根级 Markdown 和 doc/ 的合规文档可变化；app 模板、其他 app 文件、frontend HTML/MD、scripts HTML/MD、datas 文件、相似目录名及非文档后缀均与 Git blob 相同。最终包按实际选择数重新统计，279 仅是失败包的历史测量，不能硬编码为未来阈值。
2. **URL 契约：**空 href、#fragment、?query、?query#fragment 保留；包内文件链接保留；排除的仓库文档正确外链化并保留现有片段行为；真正缺失的本地文档仍拒绝。正确查询链接归档必须使独立 checker 退出 0，坏链接归档必须退出非零。
3. **模板：**真实分页模板解码与语法检查通过；有前后页、单页、零结果和含特殊字符筛选词均渲染；所有输出分页链接指向当前站点，页面/筛选参数正确。只做 parse 不足以替代这些断言。
4. **集成：**在最终 tar 解压目录、独立 SQLite 和端口运行。普通 GET：无记录/有记录；partial=1：无记录/有记录；至少两页数据：前后翻页、筛选保留、HTTP 200 与 JSON rows/pagination/total 契约。必要时按现有登录及权限准备临时 Operator；不修改权限规则，不生成截图。
5. **发布：**.venv-py311/bin/python -m unittest tests.test\_release\_asset -v；全量 discovery；Ruff app、文档/图片/术语/版本门禁；同一 ref 双构建 cmp 相同；独立 check\_release\_asset.py 通过；非文档全包 Git blob 对比及 Jinja 解析通过；隔离安装和登录黄金路径通过。任何制品级失败均保持 blocked，不以源码绿灯覆盖。

## 7. 风险与范围控制

运行时字节保护是必要且可验证的不变量；无需改任何业务模板或“修正”模板写法。正常文档外链行为保留，避免删掉全部重写后产生大量部署文档断链。新根级 HTML 或新的文档目录不会自动获得重写权，未来由清单与设计显式扩展；当前清单只有合规根 Markdown、9 个 doc HTML 和对应 Markdown，无根级 HTML。

本次不把正则替换器升级成通用 HTML/Markdown 解析器，不扩大 URL scheme、编码、非空路径 query、任意转义语法或清单来源策略；这些边界维持现状，不能宣称已全部解决。文档路径保护不改变包文件集合、权限、元数据归一化、截图排除或 SHA 算法；只改变被错误处理的运行时内容及明确的无路径 URL 行为。最终 tar/校验和/build.json 必须全部重建，不能复用或手工修补旧包。

确定性边界：同一个 ref 的两次构建必须一致；使用完整 SHA 和使用 v4.2.0 标签时，构建器现有 public\_ref 规则会生成不同的文档 URL，整包哈希可能不同，不能把这种允许的文档差异误报为新运行时回归。无论文档链接使用 SHA 还是 tag，全部非文档文件必须与同一源 commit 原字节相等。清单来源策略本轮不改，正式验收仍要求已提交清单与干净工作区。

## 准确性与合理性评估

### 准确性：根因有直接证据，原 v1 边界说明需补齐

重写范围错误→HTML 正则截断→空 path 解析为父目录→外链替换删掉 if 但遗留 endif，三段错误链已分别复现。279 个受保护文件中唯一差异及 40 个模板中唯一语法失败形成对应证据。新增查询文档的独立检查夹具则直接复现 v1 的缺口：README.md 的 ?view=compact 和 doc/index.html 的 ?page=2 被当断链，checker 退出 1。v2 已把修复 checker 写入范围。实际选入的 9 个文档 HTML 未发现 query-only 或属性内异种引号链接，因此后者是契约补齐，不冒称第二个已出现的生产故障。

### 合理性：修打包边界比改页面模板更小且更稳

- 仅改正则引号匹配：不足。即便 Jinja 结构不被截断，空路径仍可能让合法查询链接变成 GitHub 目录链接，语法绿而导航错。
- 仅对空 path 返回：能躲过当前分页例子，却继续让其他运行时相对链接进入重写，未建立原字节边界。
- 只排除已知分页文件或所有 app 模板：覆盖不完整，frontend/ 或其他运行时 HTML/MD 仍可被误处理。
- 删除所有链接重写：会使不随包发布的设计/历史文档链接失效，违背现有精简包文档契约。
- 换通用 HTML 解析器：对当前问题没有必要，范围和序列化差异更大，也不能替代“运行时不重写”的边界。
- v2：三个现有文件的有限改动，不改产品行为、不加依赖、保留文档功能，并用包内容和真实链路双重验证，推荐采用。

### 证据强度与剩余不确定性

已经证实的是当前/历史重建包的错误、源码输入完整、错误路径和测试缺口；尚未证实的是修复有效、最终包 HTTP/浏览器已恢复或旧线上附件必然受影响。Jinja parse 只验证语法树，不能证明过滤器注册、上下文、路由、数据或 AJAX 正常；这是为何 v2 保留字节比较、解析、渲染、实际 GET/AJAX 四层。准确性依据现有实现、只读探针和标准 URL 语义，不使用主观评分代替验证。

### 依据

[RFC 3986 §5.2.2](https://www.rfc-editor.org/rfc/rfc3986.html#section-5.2.2)：无路径引用沿用基准路径，查询存在时使用新查询，不能把当前文档当父目录。[Jinja 官方 parse API](https://jinja.palletsprojects.com/en/stable/api/#jinja2.Environment.parse)及本机 environment.py:599–626 已核对：parse 产出语法树，不等于完成应用渲染。

## v2 分析时验证结果（历史，修复前）

0e31f8f 业务及 73854ac 归档候选全量 1168 tests / OK / skipped=12；07dddb3 双构建相同、资产检查通过，但该包模板 parse 明确失败。本轮只运行诊断，未编写防护测试或修改实现；v2 的 B1–B4 均未实施。状态清单已改 blocked，不能把源码绿色结果代替包页面验收。

## 历史归因核验（2026-11-04）

git blame -L 114,147 scripts/build\_release\_asset.py 指向 bed58fdad7aa4771a21cf6cffef99dccacf8e725（2026-10-14，build: add image governance and release tooling）。git diff v4.1.1..HEAD -- scripts/build\_release\_asset.py app/templates/redesign/\_exec\_logs\_pagination.html release/package-manifest.txt 为空；本轮发布收尾未改这三个输入，0e31f8f..HEAD 的改动仅是文档与发布状态清单。

实际历史重现：.venv-py311/bin/python scripts/build\_release\_asset.py --version 4.1.1 --ref v4.1.1 --output /private/tmp/cronpilot-v411-historical-reproduction/cronpilot-4.1.1.tar.gz 成功。直接解析 v4.1.1 Git blob 的该模板通过；对该重建 tar 中模板执行同一 Jinja parse，报相同 TemplateSyntaxError: Encountered unknown tag 'endif'（期待 endfor）。故已证实仓库内历史打包逻辑在 v4.1.1 已有此缺陷，本轮只是重建并发现，没有引入打包器回归。

边界：未下载、核对之前实际上传的 GitHub Release 附件，不能据此断言历史线上部署一定使用了损坏包。直接从 Git 源码运行不会经过文档重写。此次交付问题是源码/空库门禁未覆盖非空执行记录的最终制品，曾过早将状态置为 ready；已按实际制品失败撤回。

## 分析复现入口与适用边界

在仓库根使用 .venv-py311/bin/python doc/qa/evidence/release-runtime-template-analysis-2026-11-04/probe.py；需保留 /private/tmp/cronpilot-v420-blocked-07dddb3/cronpilot-4.2.0.tar.gz 及 .build.json。该失败包若已清理，在当前未修改打包实现的阶段可用 scripts/build\_release\_asset.py --version 4.2.0 --ref 07dddb3 --output 指定该路径重新构建。构建清单与该提交保持一致。探针输出原字节差异、模板语法错误及现有 URL 行为，仅写 /private/tmp 分析结果。

查询链接单独诊断：.venv-py311/bin/python [doc/qa/evidence/release-runtime-template-analysis-2026-11-04/query\_probe.py](../qa/evidence/release-runtime-template-analysis-2026-11-04/query_probe.py)，使用临时归档，不依赖失败包；预修复 checker 返回 1 并给出两个误报，诊断本身因成功重现而退出 0。冻结脚本用于解释旧行为，未来正式防护测试必须期待有效查询链接通过，不可把这个“期待失败”探针当成修复后绿灯。

## v2 方案修订复盘（仅文档，7 项）

1. 定位：v1 方案包含构建器 query-only 保留，却未把独立 checker 的 normalize\_target 纳入范围。
2. 根因：原分析沿损坏模板向构建器逆查，在选定正确 URL 语义后没有沿制品验收链正向复核独立消费者。
3. 测试漏洞：原发布夹具只覆盖 README 的隐藏文档外链，没有 query-only 或运行时 Jinja；故既不能发现模板改坏，也不能揭示新语义与 checker 不一致。
4. 修订：本轮仅修订 v2 设计，将 checker 纳入三文件范围，细化完整原字节边界与证据分级；尚未改产品/工具实现。
5. 防护验证：query\_probe.py 已真实重现两个误报；最终正式测试须覆盖 builder+checker 端到端有效归档及真正断链否定归档。probe.py 已比较实际全包并解析全部 40 个模板。
6. 同类排查：失败包 279 个非文档成员仅一个被改写；选入的 9 个文档 HTML 没有 query-only/异种引号属性，未扩成无证据的全站问题。
7. 预防方案：本设计 §6 新增“语义改动必须以独立消费者检查正确和错误两类制品”的验收矩阵；结果保存在 evidence/.../results.json，复现命令为 query\_probe.py。未来落实位置 tests/test\_release\_asset.py 的端到端构建与检查用例，且验收以最后重建包为对象，不能以源码测试代替。

## v2 文档验收

.venv-py311/bin/python scripts/html\_docs\_to\_markdown.py --check、scripts/check\_doc\_completeness.py --check、scripts/check\_doc\_links.py --check、scripts/check\_opt\_consistency.py --check，以及 bash scripts/check\_pending\_sync.sh、git diff --check 均退出 0；413 个 HTML 已登记，3156 个引用无 broken。两份诊断脚本在当前未改实现上运行退出 0，query\_probe 的被测 checker 按预期退出 1，不能记成产品验收通过。发布保持 blocked，不代表 v2 已实施或已确认。

## 最终实施验收（v4）

全量 ready 状态回归：1172 tests / 563.365s / OK (skipped=12)，退出 0；发布专项 11/11，路由 86/86。首次全量的唯一失败是清单仍 blocked 时的 tag-preparable 自检；真实包验证通过、清单恢复 ready 后已完整重跑成功，未将该失败隐去或当作产品修复。

实际候选 d074674：301 个文件，279 个非文档成员全部与 Git blob 相同；40 个模板均解析通过；两次 tar 完全相同；独立资产检查通过。全新目录和 venv 安装锁定核心依赖成功；50994 隔离 SQLite 黄金路径双重启、POST 登录 302、核心页面/API 200、空库断言通过。

解压包原生应用、内存数据库和 Operator：13 项 HTTP 断言通过，覆盖全局/单任务日志的有记录、空结果、第一页/第二页 GET/AJAX；真实浏览器登录、7 列日志、分页、带单引号关键词筛选及空结果 DOM 验证通过。测试数据为 45 条临时日志，无截图；50993 服务保留供用户复验。

Agent 自证：SOURCE\_RUNTIME\_BYTES\_EQUAL=279；JINJA\_TEMPLATES\_PARSE\_OK=40；OPERATOR\_HTTP\_CHECKS=13；BROWSER\_FILTERED\_PAGE2\_FIRST\_RECORD=25；EMPTY\_AJAX\_ROWS=0；GOLDEN\_PATH: OK。

证据：[汇总](../qa/evidence/release-runtime-template-fix-2026-11-04/validation.json)、[包字节结果](../qa/evidence/release-runtime-template-fix-2026-11-04/candidate-artifact.json)、[HTTP](../qa/evidence/release-runtime-template-fix-2026-11-04/candidate-http.json)、[浏览器文字记录](../qa/evidence/release-runtime-template-fix-2026-11-04/browser.json)。复现工具：[verify\_artifact.py](../qa/evidence/release-runtime-template-fix-2026-11-04/verify_artifact.py)、[verify\_packaged\_logs.py](../qa/evidence/release-runtime-template-fix-2026-11-04/verify_packaged_logs.py)。

HTTP 验收首次夹具缺注册申请模型表，已在 db.create\_all 前导入完整模型后重跑通过；这是验证准备修正，未修改产品。保护措施为明确内存 URL、StaticPool、源应用路径、禁调度及完整模型注册。真实 MySQL、Docker、Python 3.8–3.10 未重跑，未沿用旧截图充当新证据。

## 实施记录与七项修复复盘

1. **Bug 定位：**scripts/build\_release\_asset.py 的 rewrite\_links 把运行时 HTML 当成文档；实际包分页模板与 Git blob 不同、出现未知 endif。check\_release\_asset.py 对合法 query-only 文档链接另有误报。
2. **根因：**仅凭文件后缀判断可重写对象；正则不理解 Jinja，空 path 被并入父目录；生成端与独立检查端没有同一 URL 语义契约。
3. **测试漏洞：**原夹具只检查 README 隐藏文档外链和确定性，没有运行时模板、原字节对比或 query-only；空库普通页面不加载该模板，单测与空库黄金路径未覆盖制品渲染。
4. **修复：**仅根级 Markdown/doc 文档进入重写，其余在解码前原样返回；生成器和 checker 各自识别无 path 链接；后缀大小写识别与格式选择一致。业务模板、权限、模型、工作流未改。
5. **防护测试：**tests.test\_release\_asset.ReleaseAssetTest 新增 test\_runtime\_files\_preserve\_git\_bytes\_and\_pagination\_renders、test\_runtime\_html\_is\_preserved\_before\_utf8\_decoding、test\_document\_queries\_survive\_build\_and\_independent\_validation、test\_independent\_validator\_still\_rejects\_missing\_document。分别断言 Git 字节、零/单/多页筛选、解码前保护、合法查询及真正断链拒绝。旧实现 2 fail/1 error，修复后全部 11 项通过（4.250s）。
6. **同类排查：**既有失败包 279 个非文档成员仅一处不同；40 源模板均可解析，失败包仅该模板报错。正式候选还须全包逐字节对比和真实 GET/AJAX，而非只回测这个模板。
7. **预防方案：**已在 tests/test\_release\_asset.py 落实独立 Git fixture 原字节、真实模板和 builder→checker 正反用例门禁；运行 .venv-py311/bin/python -m unittest tests.test\_release\_asset -v 可重现。最终包另验证独立数据库下有/无记录 GET/AJAX 与多页交互，验收结果归档至 doc/qa/evidence/release-runtime-template-fix-2026-11-04/。

## v1 文档验收记录（历史）

.venv-py311/bin/python scripts/html\_docs\_to\_markdown.py --check、scripts/check\_doc\_completeness.py --check、scripts/check\_doc\_links.py --check、scripts/check\_opt\_consistency.py --check，以及 bash scripts/check\_pending\_sync.sh、git diff --check 均退出 0；413 个 HTML 已登记，3156 个引用无 broken。scripts/check\_version\_consistency.py --check --tag v4.2.0 退出 1，明确因 blocked 与非空 release\_blockers 拒绝发布，这是当前预期门禁结果。

[Markdown](release-runtime-template-preservation-2026-11-04.md) · [文档索引](../index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
