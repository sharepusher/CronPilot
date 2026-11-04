"""Frozen diagnostic of the pre-fix checker; writes only a temporary archive."""
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[4]
files = {
    'README.md': b'[current](?view=compact)\n',
    'INSTALL.md': b'Install\n',
    'LICENSE': b'License\n',
    'RELEASE_NOTES.md': b'Notes\n',
    'manage.py': b'pass\n',
    'requirements.txt': b'',
    'doc/index.html': b'<a href="?page=2">page 2</a>',
}
with tempfile.TemporaryDirectory(prefix='cronpilot-query-contract-') as directory:
    archive = Path(directory) / 'query.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        for path, content in files.items():
            member = tarfile.TarInfo('cronpilot-0.0.0/' + path)
            member.size = len(content)
            tar.addfile(member, io.BytesIO(content))
    result = subprocess.run(
        [sys.executable, str(root / 'scripts/check_release_asset.py'),
         '--archive', str(archive), '--version', '0.0.0'],
        cwd=root, capture_output=True, text=True, check=False,
    )
    print(json.dumps({'checker_returncode': result.returncode,
                      'stderr': result.stderr}, ensure_ascii=False, indent=2))
    # This frozen diagnostic is for the unmodified implementation, not a
    # post-fix regression. New regression tests must expect valid links to pass.
    assert result.returncode == 1
    assert 'README.md -> ?view=compact' in result.stderr
    assert 'doc/index.html -> ?page=2' in result.stderr
