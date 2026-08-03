#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查 git tag 与文档中版本列表的一致性。

用法:
    python scripts/check_version_consistency.py           # 交互式报告
    python scripts/check_version_consistency.py --check   # CI 模式：不一致则 exit 1

检查范围:
    1. README.md 版本表（「| **vX.Y.Z** |」格式）
    2. doc/交付状态与路线图.html 已发布版本表（「<strong>vX.Y.Z</strong>」格式）
    3. README.md 概述行中的「当前版本」与最新 tag 一致
    4. RELEASE_NOTES.md 中各 tag 对应的章节存在
    5. RELEASE_NOTES.md [Unreleased] 节无残留实质内容
    6. RELEASE_NOTES.md 底部版本总览表涵盖所有已发布版本
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

README = ROOT / 'README.md'
ROADMAP = ROOT / 'doc' / '交付状态与路线图.html'
RELEASE_NOTES = ROOT / 'RELEASE_NOTES.md'


def get_git_tags():
    """获取所有 vX.Y.Z 格式的 git tag，按版本降序。"""
    try:
        result = subprocess.run(
            ['git', 'tag', '--sort=-v:refname'],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        tags = []
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if re.match(r'^v\d+\.\d+\.\d+$', line):
                tags.append(line)
        return tags
    except FileNotFoundError:
        return []


def extract_readme_versions(path):
    """从 README.md 版本表中提取版本号。"""
    if not path.exists():
        return set()
    text = path.read_text(encoding='utf-8')
    return set(re.findall(r'\|\s*\*\*?(v\d+\.\d+\.\d+)\*\*?\s*\|', text))


def extract_readme_current_version(path):
    """从 README.md 概述行提取「当前版本」。"""
    if not path.exists():
        return None
    text = path.read_text(encoding='utf-8')
    m = re.search(r'当前版本\s*\*\*(v\d+\.\d+\.\d+)\*\*', text)
    return m.group(1) if m else None


def extract_roadmap_versions(path):
    """从交付状态与路线图.html 的已发布版本表中提取版本号。"""
    if not path.exists():
        return set()
    text = path.read_text(encoding='utf-8')
    return set(re.findall(r'<strong>(v\d+\.\d+\.\d+)</strong>', text))


def extract_release_notes_versions(path):
    """从 RELEASE_NOTES.md 中提取章节版本号。"""
    if not path.exists():
        return set()
    text = path.read_text(encoding='utf-8')
    return set(re.findall(r'^## \[(\d+\.\d+\.\d+)\]', text, re.MULTILINE))


def check_unreleased_residual(path):
    """检查 [Unreleased] 节是否有实质性残留内容（### 小节或非注释列表项）。"""
    if not path.exists():
        return []
    text = path.read_text(encoding='utf-8')
    m = re.search(r'^## \[Unreleased\]\s*\n(.*?)(?=^## \[|\Z)',
                  text, re.MULTILINE | re.DOTALL)
    if not m:
        return []
    section = m.group(1)
    subsections = re.findall(r'^### .+', section, re.MULTILINE)
    list_items = re.findall(r'^- (?!No draft).+', section, re.MULTILINE)
    issues = []
    if subsections:
        issues.append('Unreleased 节含 %d 个 ### 小节（疑似未合并到正式版本）：%s'
                       % (len(subsections), ', '.join(s.strip() for s in subsections[:3])))
    if list_items:
        issues.append('Unreleased 节含 %d 个实质列表项（疑似未合并）' % len(list_items))
    return issues


def check_version_index_table(path, expected_versions):
    """检查 RELEASE_NOTES.md 底部版本一览表是否涵盖所有已发布版本。"""
    if not path.exists():
        return []
    text = path.read_text(encoding='utf-8')
    m = re.search(r'^## Version index\s*\n(.*?)(?=^## |\Z)',
                  text, re.MULTILINE | re.DOTALL)
    if not m:
        m = re.search(r'^## 版本一览\s*\n(.*?)(?=^## |\Z)',
                      text, re.MULTILINE | re.DOTALL)
    if not m:
        return ['RELEASE_NOTES 中未找到 "Version index" / "版本一览" 表']
    table_text = m.group(1)
    table_versions = set(re.findall(r'\*?\*?(\d+\.\d+\.\d+)\*?\*?', table_text))
    missing = expected_versions - table_versions
    if missing:
        return ['版本总览表缺少: %s' % ', '.join('v' + v for v in sorted(missing))]
    return []


def main():
    parser = argparse.ArgumentParser(description='检查版本一致性')
    parser.add_argument('--check', action='store_true',
                        help='CI 模式：不一致则 exit 1')
    args = parser.parse_args()

    tags = get_git_tags()
    if not tags:
        print('⚠ 未找到 git tag（非 git 仓库或无 vX.Y.Z tag）')
        sys.exit(0)

    latest_tag = tags[0]
    tag_set = set(tags)

    readme_versions = extract_readme_versions(README)
    roadmap_versions = extract_roadmap_versions(ROADMAP)
    release_notes_versions = {'v' + v for v in extract_release_notes_versions(RELEASE_NOTES)}
    readme_current = extract_readme_current_version(README)

    issues = []

    # 1. README 版本表 vs git tags
    missing_in_readme = tag_set - readme_versions
    if missing_in_readme:
        for v in sorted(missing_in_readme):
            issues.append(('README 版本表', f'缺少 {v}'))

    # 2. 路线图版本表 vs git tags
    missing_in_roadmap = tag_set - roadmap_versions
    if missing_in_roadmap:
        for v in sorted(missing_in_roadmap):
            issues.append(('交付状态路线图', f'缺少 {v}'))

    # 3. RELEASE_NOTES vs git tags
    missing_in_notes = tag_set - release_notes_versions
    if missing_in_notes:
        for v in sorted(missing_in_notes):
            issues.append(('RELEASE_NOTES', f'缺少 {v} 章节'))

    # 4. README 概述行「当前版本」vs 最新 tag
    if readme_current and readme_current != latest_tag:
        issues.append(('README 概述行', f'当前版本为 {readme_current}，最新 tag 为 {latest_tag}'))

    # 5. Unreleased 节残留检查
    for msg in check_unreleased_residual(RELEASE_NOTES):
        issues.append(('RELEASE_NOTES [Unreleased]', msg))

    # 6. 版本总览表完整性
    rn_versions_raw = extract_release_notes_versions(RELEASE_NOTES)
    for msg in check_version_index_table(RELEASE_NOTES, rn_versions_raw):
        issues.append(('RELEASE_NOTES 版本总览', msg))

    # 输出
    if issues:
        print(f'发现 {len(issues)} 个版本一致性问题：\n')
        for source, desc in issues:
            print(f'  ✗ [{source}] {desc}')
        print()
        if args.check:
            print('CI 检查失败：请补全上述缺失项。')
            sys.exit(1)
        else:
            print('建议：发版时同步更新 README 版本表、交付状态路线图、RELEASE_NOTES。')
    else:
        print(f'✓ 版本一致性检查通过（{len(tags)} 个 tag，全部在 README/路线图/RELEASE_NOTES 中找到）。')


if __name__ == '__main__':
    main()
