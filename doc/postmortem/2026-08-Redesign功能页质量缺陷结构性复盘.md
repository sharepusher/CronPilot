# 复盘：Redesign 实施产生 77 个质量缺陷的结构性分析

> HTML 版：[2026-08-Redesign功能页质量缺陷结构性复盘.html](2026-08-Redesign功能页质量缺陷结构性复盘.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 复盘：Redesign 实施产生 77 个质量缺陷的结构性分析

**审查时间**：2026-08-24  
**审查范围**：`app/templates/redesign/` 全部 23 个功能页  
**关联设计**：`doc/design/Redesign功能页全量审查与修复计划.html`  
**严重度分布**：Critical 2 · Medium ~35 · Low ~40

## 一、Bug 定位

### Critical（功能不可用）

| 编号 | 文件 | 位置 | 现象 |
| --- | --- | --- | --- |
| C1 | `dashboard.html` | 行 324-336 | `cpRetire()` POST 到 `/cron_retire` 缺 `reason` 字段 → `validate_retire_reason(None)` 返回错误 → 下线操作永远失败 |
| C2 | `user_form.html` | 行 146-155 | 编辑停用用户时仍展示 `<option value="1">启用</option>`，与"停用不可恢复"策略矛盾 |

### Medium（数据错误 + 安全 + UX）

| 编号 | 文件 | 问题 |
| --- | --- | --- |
| M1 | `tags.html:179-181` | 状态映射 `status === 2` 应为 `=== 0`（暂停） |
| M2 | `execution_logs.html:219` | Esc 选择器 `a[href$="job_log_all_list"]` 在单任务视图失效 |
| M3 | `task_detail.html / run_inspector.html` | `onclick="cpCopy('{{ keyword }}')"` — keyword 含引号时 JS 断裂 |

## 二、根因（行为层分析）

### 2.1 直接技术根因

| Bug | 直接原因 | 行为层原因 |
| --- | --- | --- |
| C1 cpRetire 缺 reason | 开发者参照 `cpToggleStatus`（不需要 reason）的 POST 模式写了 cpRetire | **无接口契约对照机制**——调用后端前不验证参数清单 |
| C2 is\_active 展示"启用" | 模板无条件渲染 is\_active 字段（仅判断 `{% if user %}`） | **策略知识与 UI 实现分离**——service 层策略未传达到模板层 |
| M1 状态码=2 | 开发者凭记忆写 `2=暂停`（实际为 `0=暂停`） | **无枚举常量前端共享**——Python model 定义 ≠ JS 可访问 |
| M3 onclick 注入 | Jinja `{{ }}` 直接嵌入 JS 字符串上下文 | **安全编码规范只覆盖 HTML 层**——JS 字符串上下文的 XSS 不在检查项中 |

### 2.2 系统性根因（Why × 5）

| 层级 | 问题 | 原因 |
| --- | --- | --- |
| Why-1 | 23 页中有 77 个质量缺陷 | 开发时未执行全维度质量审查 |
| Why-2 | 为什么没执行？ | 验收标准 = 视觉还原 + 正向路径功能正常 |
| Why-3 | 为什么验收标准只有 2 维？ | Redesign 定位为"UI 迁移"而非"功能重写"，因此沿用旧标准 |
| Why-4 | 为什么 UI 迁移不要求边界验收？ | 假设"v1 已验证过功能完整性，v2 只是换皮"——但实际重写了所有 JS 交互 |
| Why-5 | 为什么重写 JS 没触发完整测试？ | **无 E2E 测试基础设施**——手动测试只覆盖正向路径 |

**核心结构性根因**：Redesign 被定位为"UI 换皮"，但实际上重写了所有前端交互逻辑（JS/AJAX/事件处理），等价于功能重写。然而验收标准仍停留在"换皮"级别（只看视觉一致性），未升级为"重写"级别（需覆盖边界/安全/可访问性）。

## 三、测试漏洞

| 测试层级 | 现有覆盖 | 无法发现的问题 |
| --- | --- | --- |
| Python 单元测试 | service 层逻辑、校验器 | 前端是否正确传递参数（C1）、UI 是否对齐策略（C2） |
| `test_ajax_form_guard` | form 结构完整性 | AJAX 手写 POST 的字段完整性 |
| `test_redesign_sidebar` | 导航权限可见性 | 页面内部功能 bug |
| `verify_golden_path.sh` | 关键路径 HTTP 200 | 具体表单操作的成功/失败结果 |
| **缺失层** | **前端 → 后端参数契约测试**：对比模板 AJAX 调用字段与后端 endpoint 必需参数 | |
| **缺失层** | **E2E 浏览器测试**：模拟用户操作全流程（点击 → 确认 → 结果验证） | |

## 四、修复计划

详见 `doc/design/Redesign功能页全量审查与修复计划.html` §三：

- **Batch 1**：2 个 Critical bug（C1 + C2）
- **Batch 2**：功能 bug + 安全（M1 + M2 + M3）
- **Batch 3**：UX 改善（loading state + required + clipboard）
- **Batch 4**：可访问性补全（aria-label + label-for + modal ARIA）

## 五、防护测试

| 新增测试 | 覆盖内容 | 验证命令 |
| --- | --- | --- |
| `tests/test_frontend_api_contract.py` | 模板 AJAX 调用字段与后端 endpoint 必需参数对照 | `python -m unittest tests.test_frontend_api_contract -v` |
| `scripts/check_status_constants.py` | 模板中硬编码 `status === N` 与 model 定义一致性 | `python scripts/check_status_constants.py --check` |
| `scripts/check_a11y_basics.py` | icon button 有 aria-label、label 有 for、form 有 CSRF | `python scripts/check_a11y_basics.py --check` |

## 六、同类排查

| 模式 | 搜索方法 | 发现 |
| --- | --- | --- |
| 硬编码状态码 | `grep -rn "status === [0-9]" app/templates/redesign/` | tags.html 1 处（M1） |
| onclick 内联 Jinja 变量 | `grep -n "onclick=.*{{" app/templates/redesign/` | task\_detail + run\_inspector 2 处（M3） |
| POST 调用可能缺字段 | 手动对比 $.post 参数 vs request.values.get 列表 | cpRetire 1 处（C1） |
| 策略冲突 UI 字段 | `grep -n "is_active" app/templates/redesign/` | user\_form 1 处（C2） |

## 七、预防方案

| # | 措施 | 解决问题 | 落地位置 | 验证命令 |
| --- | --- | --- | --- | --- |
| P1 | **新页面交付检查清单**（4 维度：功能/安全/边界/可访问性），每维度有具体检查项 | Why-2 验收标准不全 | `.cursor/rules/cronpilot-format-guard.mdc` 新增「新页面交付质量检查清单」节 | `grep "交付质量检查" .cursor/rules/cronpilot-format-guard.mdc` |
| P2 | **前端 API 参数契约测试**：CI 自动对比模板 AJAX 字段名与后端 endpoint 必需参数 | C1 缺字段 | `scripts/check_frontend_api_contract.py` + `.github/workflows/ui-contract.yml` | `python scripts/check_frontend_api_contract.py --check` |
| P3 | **状态枚举前端共享**：在 `_base.html` 的 GV 对象中注入后端状态常量，或在模板中使用 `{% set %}` 引用 Python 常量 | M1 状态码硬编码 | `app/templates/redesign/_base.html` GV 扩展 + 修改 tags.html 引用 | `grep -c "status === [0-9]" app/templates/redesign/*.html` = 0 |
| P4 | **JS 上下文 XSS 检查**：CI 脚本扫描模板中 `onclick="...{{ }}..."` 模式并报错 | M3 onclick 注入 | `scripts/check_ui_contract.py` 新增 `check_onclick_injection()` | `python scripts/check_ui_contract.py --check` |

**预防体系设计原则**：每个预防措施对应一个可自动化验证的 CI 门禁。不依赖人工 Code Review 的纪律性（已被证明不可靠），而是让 CI 在 push/PR 时自动拦截。

## 八、复盘质量自检

| 检查项 | 状态 |
| --- | --- |
| Q1: 预防方案是否新增了可验证的措施？ | ✓ 4 项 CI 门禁/测试/检查清单，每项附验证命令 |
| Q2: 预防方案能否被第三方重现验证？ | ✓ 每项给出了文件路径 + 命令 |
| Q3: 根因是否追到行为层？ | ✓ Why×5 追到"Redesign 定位为 UI 迁移但实际是功能重写，验收未升级" |
| Q4: 预防方案与根因是否因果对应？ | ✓ P1→Why-2, P2→C1, P3→M1, P4→M3 |

[文档索引](index.html) · [Markdown](2026-08-Redesign功能页质量缺陷结构性复盘.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
