"""Verify real archive bytes against its Git commit, independently of the builder."""
import argparse
import json
import subprocess
import tarfile
from pathlib import Path

from jinja2 import Environment

parser = argparse.ArgumentParser()
parser.add_argument('--archive', type=Path, required=True)
parser.add_argument('--repository', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
report = json.loads(Path(str(args.archive) + '.build.json').read_text())
raw_tree = subprocess.check_output(
    ['git', 'ls-tree', '-rz', '-r', report['source_commit']], cwd=args.repository)
tree = {}
for entry in raw_tree.split(b'\0'):
    if entry:
        metadata, name = entry.split(b'\t', 1)
        tree[name.decode()] = metadata.decode().split()[2]
protected = templates = 0
with tarfile.open(args.archive) as tar:
    members = {m.name.split('/', 1)[1]: m for m in tar.getmembers()}
    assert set(members) == {f['path'] for f in report['files']}
    for path, member in members.items():
        packed = tar.extractfile(member).read()
        # Intentionally independent of build_release_asset.rewrite_links.
        parts = path.split('/')
        documentation = (len(parts) == 1 and path.lower().endswith('.md')) or (
            parts[0] == 'doc' and Path(path).suffix.lower() in {'.html', '.htm', '.md'})
        if not documentation:
            original = subprocess.check_output(
                ['git', 'cat-file', 'blob', tree[path]], cwd=args.repository)
            assert packed == original, 'runtime bytes changed: ' + path
            protected += 1
        if path.startswith('app/templates/') and path.endswith('.html'):
            Environment().parse(packed.decode())
            templates += 1
result = {'source_commit': report['source_commit'], 'archive_files': len(members),
          'protected_files_equal': protected, 'templates_parsed': templates,
          'archive_sha256': report['archive_sha256'], 'status': 'passed'}
args.output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
