"""Read-only SQLite full-integrity and foreign-key diagnostic; no repair."""
import argparse
import sqlite3
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('database', type=Path)
    args = parser.parse_args()
    path = args.database.resolve(strict=True)
    if not path.is_file():
        raise SystemExit('database must be an existing file')
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    try:
        integrity = [row[0] for row in connection.execute('PRAGMA integrity_check')]
        foreign_count = sum(1 for _ in connection.execute('PRAGMA foreign_key_check'))
    finally:
        connection.close()
    if integrity != ['ok'] or foreign_count:
        print('FAIL: integrity=%s foreign_key_violations=%d' % (integrity, foreign_count))
        return 1
    print('OK: integrity_check and foreign_key_check')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
