#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描模板与 Vue 组件中的硬编码十六进制颜色，输出收编映射表。

用法:
    python scripts/audit_hardcoded_colors.py             # 交互式报告
    python scripts/audit_hardcoded_colors.py --check      # CI 模式：存在硬编码色则 exit 1
    python scripts/audit_hardcoded_colors.py --csv        # 输出 CSV 可导入表格
    python scripts/audit_hardcoded_colors.py --mapping     # 输出色值→令牌建议映射表

允许名单:
    console-theme.css 中的令牌定义本身不计入违规。
    --allow-file 可追加其他豁免文件（相对于仓库根）。
"""
import argparse
import csv
import io
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCAN_DIRS = [
    (ROOT / 'app' / 'templates', '**/*.html'),
    (ROOT / 'frontend' / 'src', '**/*.vue'),
]

ALLOW_FILES_DEFAULT = {
    'app/static/css/console-theme.css',
}

HEX6_RE = re.compile(r'#([0-9a-fA-F]{6})\b')

KNOWN_MAPPING = {
    '#64748b': ('--muted',        '次要文字/灰色提示'),
    '#94a3b8': ('--faint',        '更淡的灰/禁用态'),
    '#0f172a': ('--ink',          '标题/正文深色文字'),
    '#1e293b': ('--ink',          '深色文字（略浅于 0f172a）'),
    '#f59e0b': ('--warn',         '警告色/琥珀'),
    '#d97706': ('--warn',         '警告色/深琥珀'),
    '#b45309': ('--warn',         '警告文字色/深琥珀'),
    '#b91c1c': ('--danger',       '错误/危险色'),
    '#dc2626': ('--danger',       '错误/危险色'),
    '#c0392b': ('--danger',       '危险（label-danger 覆写）'),
    '#059669': ('--success',      '成功色/翠绿'),
    '#16a34a': ('--success',      '成功色/绿'),
    '#166534': ('--success',      '成功色文字/深绿'),
    '#0284c7': ('--state-running','执行中状态色'),
    '#9333ea': ('--state-timeout','超时状态色'),
    '#0891b2': ('--accent',       '强调色/信号青'),
    '#2563eb': ('--accent',       '蓝色强调（待决策统一）'),
    '#1d4ed8': ('--accent',       '深蓝强调（待决策统一）'),
    '#2980b9': ('--role-admin',   '管理员角色徽标'),
    '#16a085': ('--role-operator','运维角色徽标'),
    '#27ae60': ('--role-viewer',  '观察者角色徽标'),
    '#e67e22': ('--role-seed',    '种子角色徽标'),
    '#ffffff': ('--surface',      '卡片/面板背景'),
    '#e2e8f0': ('--border',       '边框色（slate-200）'),
    '#f1f5f9': ('--surface-2',    '浅灰背景（slate-100）'),
    '#f0fdf4': ('--success-bg',   '成功提示背景（绿底）'),
    '#bbf7d0': ('--success-border','成功提示边框'),
    '#dcfce7': ('--success-bg-2', '成功提示深底'),
    '#14532d': ('--success',      '成功文字深色'),
    '#fef2f2': ('--danger-bg',    '错误提示背景（红底）'),
    '#fecaca': ('--danger-border','错误提示边框'),
    '#fca5a5': ('--danger-border','错误边框/浅红（red-300）'),
    '#991b1b': ('--danger',       '深红文字（red-800）'),
    '#fffbeb': ('--warn-bg',      '警告背景（琥珀底）'),
    '#fcd34d': ('--warn-border',  '警告边框（yellow-300）'),
    '#78350f': ('--warn',         '警告深文字（amber-900）'),
    '#fde68a': ('--warn-border',  '警告指示（yellow-200）'),
    '#fef3c7': ('--warn-bg',      '警告背景浅（amber-100）'),
    '#92400e': ('--warn',         '警告深文字（amber-800）'),
    '#ffedd5': ('--warn-bg',      '警告背景（orange-100，角色徽标底）'),
    '#475569': ('--ink-2',        '次标题/筛选项文字（slate-600）'),
    '#334155': ('--ink-2',        '筛选项文字（slate-700）'),
    '#cbd5e1': ('--border',       '边框/禁用态（slate-300）'),
    '#f8fafc': ('--surface-2',    '极浅背景（slate-50）'),
    '#9ca3af': ('--faint',        '图标/禁用态（gray-400）'),
    '#57534e': ('--muted',        '已下线 chip 文字（stone-600）'),
    '#78716c': ('--muted',        '已下线 chip 背景（stone-500）'),
    '#f5f5f4': ('--surface-2',    '已下线 chip 底（stone-100）'),
    '#d6d3d1': ('--border',       '已下线 chip 边框（stone-300）'),
    '#15803d': ('--success',      '成功/启用文字（green-700）'),
    '#2c3e50': ('--topbar-bg',    'topbar 背景（Flat UI midnight）'),
    '#ecf0f1': ('--topbar-text',  'topbar 文字（Flat UI silver）'),
    '#7f8c8d': ('--topbar-muted', 'topbar 次要文字（Flat UI asbestos）'),
    '#337ab7': ('--accent',       '链接色（Bootstrap 蓝）'),
    '#3498db': ('--accent',       'label-default 背景（Flat UI peter river）'),
    '#93c5fd': ('--accent-border','运行中 chip 边框（blue-300）'),
    '#eff6ff': ('--accent-bg',    '运行中 chip 背景（blue-50）'),
    '#dbeafe': ('--accent-bg',    '角色徽标背景（blue-100）'),
}


def scan_files(allow_files):
    """扫描并返回 {color_lower: [(relpath, lineno, line_text), ...]}."""
    hits = defaultdict(list)
    for base_dir, glob in SCAN_DIRS:
        if not base_dir.exists():
            continue
        for fpath in sorted(base_dir.glob(glob)):
            rel = str(fpath.relative_to(ROOT))
            if rel in allow_files:
                continue
            try:
                lines = fpath.read_text(encoding='utf-8').splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for i, line in enumerate(lines, 1):
                for m in HEX6_RE.finditer(line):
                    color = '#' + m.group(1).lower()
                    hits[color].append((rel, i, line.strip()))
    return hits


def print_summary(hits):
    total = sum(len(v) for v in hits.values())
    unique = len(hits)
    files = set()
    for locs in hits.values():
        for rel, _, _ in locs:
            files.add(rel)

    print('=' * 72)
    print('CronPilot 硬编码颜色审计报告')
    print('=' * 72)
    print(f'总计: {total} 处硬编码  |  {unique} 个独立色值  |  {len(files)} 个文件')
    print()

    sorted_colors = sorted(hits.items(), key=lambda x: -len(x[1]))

    print('-' * 72)
    print(f'{"色值":<12} {"出现次数":>8}  {"文件数":>6}  {"建议令牌":<22} {"说明"}')
    print('-' * 72)
    for color, locs in sorted_colors:
        file_count = len(set(r for r, _, _ in locs))
        mapping = KNOWN_MAPPING.get(color)
        token = mapping[0] if mapping else '（待分类）'
        desc = mapping[1] if mapping else ''
        print(f'{color:<12} {len(locs):>8}  {file_count:>6}  {token:<22} {desc}')
    print('-' * 72)
    print()

    print('=' * 72)
    print('按文件分布明细')
    print('=' * 72)
    file_colors = defaultdict(list)
    for color, locs in sorted_colors:
        for rel, lineno, text in locs:
            file_colors[rel].append((lineno, color, text))

    for rel in sorted(file_colors.keys()):
        entries = sorted(file_colors[rel], key=lambda x: x[0])
        print(f'\n  {rel} ({len(entries)} 处)')
        for lineno, color, text in entries:
            mapping = KNOWN_MAPPING.get(color)
            token = mapping[0] if mapping else '?'
            preview = text[:80] + ('...' if len(text) > 80 else '')
            print(f'    L{lineno:<5} {color}  → {token:<20} {preview}')

    unmapped = [c for c in sorted_colors if c[0] not in KNOWN_MAPPING]
    if unmapped:
        print()
        print('=' * 72)
        print(f'未映射色值（需人工确认语义后分配令牌）: {len(unmapped)} 个')
        print('=' * 72)
        for color, locs in unmapped:
            file_count = len(set(r for r, _, _ in locs))
            sample = locs[0]
            print(f'  {color}  ×{len(locs)}  ({file_count}文件)  '
                  f'样本: {sample[0]}:L{sample[1]}')


def print_csv(hits):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['色值', '文件', '行号', '建议令牌', '说明', '代码片段'])
    sorted_colors = sorted(hits.items(), key=lambda x: -len(x[1]))
    for color, locs in sorted_colors:
        mapping = KNOWN_MAPPING.get(color)
        token = mapping[0] if mapping else ''
        desc = mapping[1] if mapping else ''
        for rel, lineno, text in sorted(locs):
            writer.writerow([color, rel, lineno, token, desc, text[:120]])
    print(buf.getvalue())


def print_mapping_table(hits):
    print('=' * 72)
    print('色值 → 令牌映射表（用于批量替换参考）')
    print('=' * 72)
    print(f'{"色值":<12} {"令牌":<24} {"说明":<30} {"出现次数":>8}')
    print('-' * 72)

    mapped = []
    unmapped = []
    for color in sorted(hits.keys()):
        count = len(hits[color])
        if color in KNOWN_MAPPING:
            token, desc = KNOWN_MAPPING[color]
            mapped.append((color, token, desc, count))
        else:
            unmapped.append((color, count))

    for color, token, desc, count in sorted(mapped, key=lambda x: x[1]):
        print(f'{color:<12} {token:<24} {desc:<30} {count:>8}')

    if unmapped:
        print()
        print(f'--- 未映射 ({len(unmapped)} 个，需人工确认) ---')
        for color, count in sorted(unmapped, key=lambda x: -x[1]):
            print(f'{color:<12} {"?":<24} {"待确认语义":<30} {count:>8}')

    print('-' * 72)
    total_mapped = sum(c for _, _, _, c in mapped)
    total_unmapped = sum(c for _, c in unmapped)
    total = total_mapped + total_unmapped
    print(f'已映射: {total_mapped}/{total} ({total_mapped*100//total}%)  '
          f'未映射: {total_unmapped}/{total} ({total_unmapped*100//total}%)')


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true',
                        help='CI 模式: 存在硬编码颜色则 exit 1')
    parser.add_argument('--csv', action='store_true',
                        help='输出 CSV 格式')
    parser.add_argument('--mapping', action='store_true',
                        help='输出色值→令牌建议映射表')
    parser.add_argument('--allow-file', action='append', default=[],
                        help='追加豁免文件（相对仓库根）')
    args = parser.parse_args()

    allow_files = set(ALLOW_FILES_DEFAULT)
    allow_files.update(args.allow_file)

    hits = scan_files(allow_files)

    if not hits:
        print('未发现硬编码颜色。')
        return 0

    if args.csv:
        print_csv(hits)
    elif args.mapping:
        print_mapping_table(hits)
    elif args.check:
        total = sum(len(v) for v in hits.values())
        unique = len(hits)
        print(f'ERROR: 发现 {total} 处硬编码颜色 ({unique} 个独立色值)，'
              f'请迁移至 CSS 变量。', file=sys.stderr)
        print(f'运行 python scripts/audit_hardcoded_colors.py 查看详情。',
              file=sys.stderr)
        return 1
    else:
        print_summary(hits)

    return 0


if __name__ == '__main__':
    sys.exit(main())
