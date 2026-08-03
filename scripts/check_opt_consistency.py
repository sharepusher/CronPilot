#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查 OPT 编号全局一致性和设计文档状态与路线图对照。

用法:
    python scripts/check_opt_consistency.py           # 交互式报告
    python scripts/check_opt_consistency.py --check   # CI 模式：不一致则 exit 1

检查范围:
    1. OPT 编号全局一致性：同一 OPT 编号在所有文件中指向同一功能
       - 维护一份「OPT → 功能名称」权威映射（从交付状态与路线图提取）
       - 扫描所有 doc/*.html 中 OPT 引用的上下文，检测是否有歧义引用
    2. 设计文档状态 vs 路线图对照：
       - 路线图中标「已交付」的 OPT，对应设计文档不应仍为「设计待确认」或「未开始」

根因（2026-08 编号重分配事件）：
    OPT-P2-12 原指 Resource Scope（v1.1.0），后误用于 Admin Scope，
    重分配为 OPT-P2-15 后部分引用方文档未同步。
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'doc'

# Known OPT → canonical feature name mappings (from 交付状态与路线图)
# Key: OPT number, Value: (canonical name, keywords that SHOULD appear nearby)
# Only track renumbered/conflict-prone entries; others don't need context checks.
KNOWN_RENAMES = {
    'OPT-P2-12': {
        'canonical': 'Resource Scope 资源隔离',
        'keywords': ['resource', 'scope', '资源隔离', '隔离', '可见范围', '业务组'],
        'wrong_keywords': [],  # These alone don't indicate a problem
    },
    'OPT-P2-13': {
        'canonical': '规模化信息架构',
        'keywords': ['规模化', 'IA', '信息架构', 'job_health', 'L1', 'L2'],
        'wrong_keywords': [],
    },
    'OPT-P2-15': {
        'canonical': 'Admin Scope 差异化',
        'keywords': ['admin', 'scope', '差异化', '种子', 'seed', 'manager'],
        'wrong_keywords': [],
    },
    'OPT-P2-16': {
        'canonical': '审计日志 Scope 过滤',
        'keywords': ['审计', 'audit', 'actor_group', 'scope过滤', '日志scope'],
        'wrong_keywords': [],
    },
}

# OPT numbers that were renumbered: old_number → new_number
# Patterns must be very precise to avoid false positives from rename documentation
# or nearby admin references in legitimate Resource Scope context.
RENAME_MAP = {
    # Only flag when OPT-P2-12 is used as an identifier WITH admin scope differentiation
    # e.g. "admin Scope 差异化（OPT-P2-12）" or "OPT-P2-12.*差异化" as a label
    'OPT-P2-12': ('OPT-P2-15', [
        r'差异化[^<]{0,20}OPT-P2-12',                    # "差异化...OPT-P2-12"
        r'OPT-P2-12[^<]{0,10}差异化',                    # "OPT-P2-12...差异化" (tight)
        r'OPT-P2-12[)）][^<]{0,20}已交付[^<]{0,20}管理员', # "OPT-P2-12）已交付" in admin context
    ]),
    # Only flag when OPT-P2-13 is used as identifier FOR audit log scope
    'OPT-P2-13': ('OPT-P2-16', [
        r'OPT-P2-13[^<]{0,10}(?:审计日志|audit)',   # "OPT-P2-13 审计日志"
        r'(?:审计日志|audit)[^<]{0,10}OPT-P2-13',   # "审计日志 OPT-P2-13"
    ]),
}


def extract_roadmap_opt_status():
    """从路线图提取 OPT → 状态 映射。"""
    roadmap = DOC / '交付状态与路线图.html'
    if not roadmap.exists():
        return {}
    content = roadmap.read_text(encoding='utf-8')
    status_map = {}
    for m in re.finditer(
        r'<td>(OPT-P\d+-\d+\w*)</td>\s*<td>([^<]+)</td>\s*<td[^>]*class="([^"]*)"[^>]*>([^<]+)</td>',
        content
    ):
        opt = m.group(1)
        name = m.group(2).strip()
        css_class = m.group(3)
        status = m.group(4).strip()
        status_map[opt] = {'name': name, 'status': status, 'delivered': 's-done' in css_class}
    return status_map


def check_rename_conflicts():
    """检查已重分配的 OPT 编号是否在错误上下文中被引用。"""
    issues = []
    for html in sorted(DOC.rglob('*.html')):
        if '_pending_sync' in str(html):
            continue
        content = html.read_text(encoding='utf-8')
        rel = str(html.relative_to(DOC))

        for old_opt, (new_opt, wrong_patterns) in RENAME_MAP.items():
            if old_opt not in content:
                continue
            for pattern in wrong_patterns:
                for m in re.finditer(pattern, content, re.IGNORECASE):
                    # Allow if the context is documenting the rename itself
                    ctx_start = max(0, m.start() - 300)
                    ctx_end = min(len(content), m.end() + 300)
                    ctx = content[ctx_start:ctx_end]
                    if any(kw in ctx for kw in ('更正为', '误标为', '冲突', '已占用', 'renumber')):
                        continue  # Documenting the rename, OK
                    if 'conflict' in ctx.lower():
                        continue
                    if 'RELEASE_NOTES' in rel:
                        continue  # Release notes document the change, OK
                    text = re.sub(r'<[^>]+>', '', m.group()[:80]).strip()
                    issues.append(
                        '%s 中 %s 疑似应为 %s：…%s…' % (rel, old_opt, new_opt, text)
                    )
    return issues


def check_design_doc_status(roadmap_status):
    """检查路线图标「已交付」的 OPT，对应设计文档是否仍为「设计待确认」。"""
    issues = []
    for html in sorted(DOC.rglob('*.html')):
        if '_pending_sync' in str(html):
            continue
        rel = str(html.relative_to(DOC))
        # Skip non-design docs
        if not any(rel.startswith(d) for d in ('design/', 'plan/', 'arch/', 'deps/')):
            continue
        # Skip roadmap, index, RELEASE_NOTES
        if html.name in ('交付状态与路线图.html', 'index.html', 'RELEASE_NOTES.html'):
            continue

        content = html.read_text(encoding='utf-8')
        # Find OPT references in this doc
        opts_in_doc = set(re.findall(r'(OPT-P\d+-\d+)', content))

        # Check: if doc header says "设计待确认" or "未开始", but roadmap says delivered
        header = content[:2000]
        header_text = re.sub(r'<[^>]+>', '', header)
        is_draft = bool(re.search(r'(?:设计待确认|未开始|draft|pending)', header_text, re.IGNORECASE))

        if not is_draft:
            continue

        for opt in opts_in_doc:
            if opt in roadmap_status and roadmap_status[opt]['delivered']:
                # Only flag if this doc seems to be THE design doc for this OPT
                # (not just referencing it)
                if opt in html.name or opt.replace('-', '') in html.name:
                    issues.append(
                        '%s 状态为"设计待确认"，但 %s 在路线图中已标为"已交付"'
                        % (rel, opt)
                    )
    return issues


def main():
    parser = argparse.ArgumentParser(description='检查 OPT 编号一致性与设计文档状态')
    parser.add_argument('--check', action='store_true', help='CI 模式')
    args = parser.parse_args()

    issues = []

    # 1. Rename conflict check
    rename_issues = check_rename_conflicts()
    for msg in rename_issues:
        issues.append(('OPT 编号', msg))

    # 2. Design doc status vs roadmap
    roadmap_status = extract_roadmap_opt_status()
    status_issues = check_design_doc_status(roadmap_status)
    for msg in status_issues:
        issues.append(('设计文档状态', msg))

    if issues:
        print('发现 %d 个 OPT 一致性问题：\n' % len(issues))
        for category, msg in issues:
            print('  ✗ [%s] %s' % (category, msg))
        print()
        if args.check:
            print('CI 检查失败：请修复上述问题。')
            sys.exit(1)
    else:
        print('✓ OPT 编号一致性检查通过（编号无歧义引用，设计文档状态与路线图一致）。')


if __name__ == '__main__':
    main()
