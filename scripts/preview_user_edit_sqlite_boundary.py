#!/usr/bin/env python3
"""Owned SQLite preview; credentials remain in a private local file, never HTTP evidence."""
import argparse
import json
import os
import secrets
import signal
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from werkzeug.serving import make_server

from scripts.user_edit_browser_harness import QuietHandler, require
from scripts.user_edit_sqlite_fixture import FileFixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=5091)
    parser.add_argument('--credentials-file', type=Path, required=True)
    args = parser.parse_args()
    require(not args.credentials_file.exists(), 'credential_file_must_be_new')
    run_id, password = secrets.token_hex(8), secrets.token_urlsafe(24)
    with TemporaryDirectory(prefix='cronpilot-user-boundary-') as directory:
        folder = Path(directory)
        (folder / '.run-id').write_text(run_id)
        fixture = FileFixture(folder / 'preview.sqlite', run_id, 'WAL', password)
        users = fixture.fixture('preview')
        require(fixture.app.test_client().get('/docs/index.html').status_code == 200,
                'preview_document_route_unavailable')
        credentials = {'base_url': 'http://127.0.0.1:%s' % args.port, 'pid': os.getpid(),
                       'username': users['actor']['username'], 'password': password,
                       'target_id': users['target']['id'], 'outside_id': users['outside']['id'],
                       'editor_url': '/rbac/users/edit?id=' + str(users['target']['id'])}
        fd = os.open(str(args.credentials_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as handle:
            json.dump(credentials, handle)
        def stop(_signal, _frame):
            raise SystemExit(0)
        signal.signal(signal.SIGTERM, stop)
        server = make_server('127.0.0.1', args.port, fixture.app, threaded=False,
                             request_handler=QuietHandler)
        print('SQLITE_BOUNDARY_PREVIEW: ready port=%s isolated=1' % args.port, flush=True)
        try:
            server.serve_forever()
        finally:
            server.server_close()
            fixture.close()


if __name__ == '__main__':
    main()
