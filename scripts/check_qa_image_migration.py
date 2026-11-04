#!/usr/bin/env python3
"""Verify the frozen QA image inventory survives content-addressed migration."""
import argparse
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


class ImageLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'img' and attrs.get('src'):
            self.links.append(attrs['src'])
        if tag == 'a' and attrs.get('href'):
            self.links.append(attrs['href'])


def check(root, inventory):
    root = Path(root)
    errors = []
    manifest_path = root / 'doc/assets/screenshots/manifest.json'
    try:
        records = json.loads(Path(inventory).read_text())['entries']
        assets = json.loads(manifest_path.read_text())['assets']
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return ['invalid inventory or manifest: ' + str(exc)]
    by_legacy = {}
    for asset in assets:
        for old in asset.get('legacy_paths', []):
            by_legacy.setdefault(old, []).append(asset)
    for record in records:
        old, sha = record['path'], record['sha256']
        matches = by_legacy.get(old, [])
        if len(matches) != 1:
            errors.append('missing or ambiguous mapping: ' + old)
            continue
        asset = matches[0]
        expected = 'doc/assets/screenshots/' + sha + '.png'
        if asset.get('sha256') != sha or asset.get('canonical_path') != expected:
            errors.append('mapping hash mismatch: ' + old)
            continue
        target = root / expected
        if not target.is_file():
            errors.append('mapped image missing: ' + old)
        elif hashlib.sha256(target.read_bytes()).hexdigest() != sha:
            errors.append('mapped image bytes mismatch: ' + old)
        if (root / old).exists():
            errors.append('legacy image still present: ' + old)
    old_targets = {(root / record['path']).resolve() for record in records}
    for path in (root / 'doc').rglob('*'):
        if path.suffix.lower() not in ('.html', '.md') or not path.is_file():
            continue
        text = path.read_text(encoding='utf-8')
        if path.suffix.lower() == '.html':
            parser = ImageLinks()
            parser.feed(text)
            links = parser.links
        else:
            links = re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', text)
        for link in links:
            parsed = urlsplit(link.strip('<>'))
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            target = (path.parent / unquote(parsed.path)).resolve()
            if target in old_targets:
                errors.append('active link still points to old image: ' + str(path.relative_to(root)))
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--inventory', type=Path)
    args = parser.parse_args()
    inventory = args.inventory or args.root / 'doc/qa/evidence/release-image-governance-2026-11-03/inventory.json'
    errors = check(args.root, inventory)
    if errors:
        for error in errors:
            print('ERROR:', error)
        print('QA image migration failed:', len(errors))
        return 1
    print('QA image migration: all frozen paths mapped with unchanged bytes')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
