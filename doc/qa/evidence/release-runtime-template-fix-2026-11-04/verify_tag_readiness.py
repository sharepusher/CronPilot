"""Run the existing version gate with a future tag set, without creating a tag."""
import contextlib
import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

root = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location('release_version_gate', root / 'scripts/check_version_consistency.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
manifest = json.loads((root / 'release/release-manifest.json').read_text())
tag = 'v' + manifest['version']
actual_tags = gate.get_git_tags()
readme = (root / 'README.md').read_text()
assert '发布就绪候选 **' + tag + '**' in readme
assert tag in gate.extract_readme_versions(root / 'README.md')
# Do not claim publication simply because a tag is about to be created.
latest_published = next(t for t in actual_tags if t != tag)
assert '最近已发布 **' + latest_published + '**' in readme
output = io.StringIO()
status = 0
with patch.object(gate, 'get_git_tags', return_value=[tag] + [t for t in actual_tags if t != tag]), \
        patch.object(sys, 'argv', ['check_version_consistency.py', '--check', '--tag', tag]), \
        contextlib.redirect_stdout(output):
    try:
        gate.main()
    except SystemExit as error:
        status = error.code
assert gate.get_git_tags() == actual_tags, 'real Git tags were changed'
result = {'simulated_tag': tag, 'real_tags_unchanged': True,
          'readme_sha256': hashlib.sha256(readme.encode()).hexdigest(),
          'gate_exit': status, 'output': output.getvalue()}
print(json.dumps(result, ensure_ascii=False, indent=2))
assert status == 0, output.getvalue()
