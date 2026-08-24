# 复盘：Redesign CSS 硬编码颜色与重复定义

> HTML 版：[2026-08-redesign-css-hardcoded-colors.html](2026-08-redesign-css-hardcoded-colors.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 复盘：Redesign CSS 硬编码颜色与重复定义

**日期**：2026-08-24  
**严重度**：中  
**触发来源**：代码 Review / 自查审计  
**关联**：OPT-P1-16（Redesign Phase 1）

## 1. Bug 定位

3 个 redesign CSS 文件中共 15 处硬编码十六进制颜色：

| 文件 | 行号 | 硬编码值 | 应使用的变量 |
| --- | --- | --- | --- |
| `redesign-components.css` | 55, 61, 423, 461, 467, 797, 803 | `#fff` | `var(--cp-on-filled)` |
| `redesign-pages.css` | 96 | `#fff` | `var(--cp-on-filled)` |
| `redesign-pages.css` | 614-615 | `--cp-warning`（不存在） | `--cp-warn-accent` / `--cp-warn-bg` |
| `redesign-pages.css` | 771 | `#ddd` | `var(--cp-border)` |
| `redesign-pages.css` | 897 | `--cp-warning`（不存在） | `--cp-warn-accent` |
| `redesign-pages.css` | 1103 | `--cp-white`（不存在） | `var(--cp-on-filled)` |
| `redesign-mockup-shared.css` | 162, 167, 172 | 带硬编码 fallback 的变量引用 | 移除 fallback，新增缺失变量 |

另外存在 `.cp-breadcrumb` 在 `redesign-layout.css` 和 `redesign-pages.css` 中重复定义（属性值冲突），以及 Print `@media` 中选择器引用了不存在的 `.redesign-*` 类名。

## 2. 根因

- **硬编码颜色**：开发 redesign CSS 时直接写 `#fff` 等色值，虽然 `console-theme.css` 已有 `--cp-on-filled: #ffffff` 变量，但未统一使用。引用了不存在的变量名（`--cp-warning` 而非 `--cp-warn-accent`），反映对变量命名体系不够熟悉。
- **重复定义**：`redesign-layout.css`（布局层）和 `redesign-pages.css`（页面层）各自独立添加了 breadcrumb 样式，未检查跨文件是否已存在同名选择器。
- **Print 选择器**：编写 print 样式时使用了 `.redesign-*` 命名约定，后来 DOM 类名统一改为 `.cp-*`，print 块未同步更新。

## 3. 测试漏洞

- 颜色审计 CI（`audit_hardcoded_colors.py --check`）仅扫描 HTML 模板和 Vue 文件，不覆盖 CSS 文件中的硬编码色值。
- 无 CSS 选择器有效性测试（CSS 中引用的 class 是否存在于 DOM 中）。
- 无 CSS 变量存在性检测（CSS 中引用的 `var(--cp-*)` 是否在 `:root` 中有定义）。

## 4. 修复

- 15 处硬编码全部替换为 CSS 变量引用
- 在 `console-theme.css` 中新增 `--cp-warn-text` 和 `--cp-danger-text`（含暗色主题）
- 删除 `redesign-layout.css` 中的重复 breadcrumb 块，保留 `redesign-pages.css` 版本
- 修正 Print 选择器：`.redesign-sidebar` → `.cp-sidebar` 等

## 5. 防护测试

```
# 验证 redesign CSS 文件中无硬编码颜色
grep -n '#[0-9a-fA-F]\{3,8\}[; )]' app/static/css/redesign-*.css | grep -v '/\*' && echo "FAIL" || echo "OK"

# 验证 print 选择器使用正确的 class
grep -n '\.redesign-' app/static/css/redesign-pages.css && echo "FAIL" || echo "OK"

# 验证 breadcrumb 不再重复定义
grep -c '\.cp-breadcrumb' app/static/css/redesign-layout.css  # 应为 0
```

## 6. 同类排查

- `redesign-components.css`：已清理，0 处硬编码
- `redesign-pages.css`：已清理，0 处硬编码
- `redesign-mockup-shared.css`：已清理 fallback
- `console-mode.css`：不在 redesign 范围，暂不处理
- `console-theme.css`：变量定义文件，允许硬编码

## 7. 预防方案

**措施**：扩展 `audit_hardcoded_colors.py` 的扫描范围，增加对 `app/static/css/redesign-*.css` 文件的检查。排除 `console-theme.css`（变量定义文件）和 CSS 注释行。

**落地位置**：`scripts/audit_hardcoded_colors.py`（CI 门禁自动触发）

**验证命令**：

```
grep -n '#[0-9a-fA-F]\{3,8\}[; )]' app/static/css/redesign-*.css | grep -v '/\*' && echo "FAIL" || echo "OK"
```

[文档索引](index.html) · [Markdown](2026-08-redesign-css-hardcoded-colors.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
