# 复盘：check_ui_contract.py 子字符串误报（legacy-class 检测）

> HTML 版：[2026-08-check_ui_contract-false-positive.html](2026-08-check_ui_contract-false-positive.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 复盘：check\_ui\_contract.py 子字符串误报（legacy-class 检测）

**日期**：2026-08-17  
**关联**：OPT-P1-16 Phase 1C — UI Contract Static Guard  
**严重级别**：低（仅影响工具误报计数，不影响业务代码）  
**发现方式**：Phase 2 计划分析时审查 legacy-class 输出，发现 `tags.html:44` 的 `btn-danger-c` 被误报为 `btn-danger`

## 1. Bug 定位

文件：`scripts/check_ui_contract.py`，函数 `check_legacy_classes()`

两个具体误报位置：

- `app/templates/redesign/tags.html:44` — `class="btn-c btn-danger-c btn-xs btn-tag-delete"`
- `app/templates/redesign/registration_review.html:46` — `class="btn-c btn-danger-c btn-xs js-reject-btn ..."`
- 同样风险但未实际命中的前缀类：`btn-primary-c`、`btn-success-c`、`btn-default-c`

错误代码（修复前）：

```
class_val = m.group(1)
for legacy in LEGACY_CLASSES:
    if legacy in class_val:   # ← 字符串子串匹配
```

## 2. 根因

HTML class 属性是空格分隔的 **token 列表**，其成员检测必须先 tokenize 再做集合判断。编写函数时将字符串 `in` 操作视为"足够精确"，没有意识到 HTML class 属性的分词语义：`"btn-danger" in "btn-danger-c btn-xs"` 在 Python 字符串层面为 True，但在 HTML 语义层面是错误匹配。

行为层追溯：

- 脚本在 Phase 1C 创建时，直接从"检测字符串是否包含关键词"的直觉出发
- 没有对 HTML token 分词这一领域知识做显式测试
- 项目中 `btn-danger-c` 等类名在 v1 模板已有使用，但 Phase 1C 创建时未比对已有类名前缀

## 3. 测试漏洞

`check_ui_contract.py` 在创建时（Phase 1C）**没有配套单元测试文件**。本应存在如下测试：

```
def test_no_false_positive_btn_danger_c():
    lines = ['<a class="btn-c btn-danger-c btn-xs">删除</a>']
    assert check_legacy_classes(lines, "test.html") == []
```

如果该测试存在，脚本在 Phase 1C 首次运行时就会失败，误报不会进入下一轮。

## 4. 修复

将字符串子串匹配替换为 HTML token 集合判断（1 行核心变更）：

```
# 修复前
class_val = m.group(1)
if legacy in class_val:

# 修复后
tokens = set(m.group(1).split())
if legacy in tokens:
```

此修复同步消除了 `btn-primary-c`、`btn-success-c`、`btn-default-c` 的潜在前缀匹配风险。违规计数从 72 → 68（4 个误报消除）。

## 5. 防护测试

新增 `tests/test_check_ui_contract.py`，包含 25 个测试用例，覆盖：

| 测试类 | 测试内容 |
| --- | --- |
| `TestLegacyClassDetection` | 4 个 false-positive 防护（btn-danger-c/primary-c/success-c/default-c）；6 个真阳性检测；行号报告正确性 |
| `TestInlineStyleAllowlist` | CSS var / display / width 100% / position 允许；font-weight / font-size / margin 拦截 |
| `TestInlineStyleCheck` | font-weight inline 检测；display:none 放行 |
| `TestHexInStyleAttr` | hex 色值检测；class 属性 hex 不误报；CSS var 放行 |

运行命令：

```
python3 -m unittest tests.test_check_ui_contract -v
# 期望：25 tests pass
```

## 6. 同类排查

`LEGACY_CLASSES` 中所有 `btn-*` 前缀条目均已被 token 匹配方案同步修复，无残留同类风险。

| 被修复的潜在前缀冲突 | 项目实际类名 | 状态 |
| --- | --- | --- |
| `btn-danger` | `btn-danger-c` | ✓ 已修复 |
| `btn-primary` | `btn-primary-c` | ✓ 已修复 |
| `btn-success` | `btn-success-c` | ✓ 已修复 |
| `btn-default` | `btn-default-c` | ✓ 已修复 |

`check_inline_styles()` 和 `check_hex_in_style_attr()` 不涉及 class 属性解析，无同类问题。

## 7. 预防方案

| # | 措施 | 落地位置 | 验证命令 |
| --- | --- | --- | --- |
| 1 | 单元测试覆盖 token 边界（防止回退到子串匹配） | `tests/test_check_ui_contract.py`（已创建，25 用例） | `python3 -m unittest tests.test_check_ui_contract -v` |
| 2 | 脚本顶部注释明确"必须用 token 匹配，禁用子字符串匹配"规则 | `scripts/check_ui_contract.py` `check_legacy_classes()` 函数注释 | `grep -n "token" scripts/check_ui_contract.py` |
| 3 | CI 接入时将 `test_check_ui_contract` 加入测试矩阵 | `.github/workflows/ui-contract.yml`（Phase 2 CI 接入时） | CI pipeline 绿色 |

**核心预防逻辑**：新增测试（措施 1）是根因的直接对策——缺少单元测试导致误报进入使用阶段，新增测试确保未来任何回退都能被立即捕获，而非等到人工审查。

---

[文档索引](../index.html) ·
[Markdown 版](2026-08-check_ui_contract-false-positive.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
