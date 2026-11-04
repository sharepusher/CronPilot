"""Read-only check for auto-restarting Compose schedulers sharing a local database path."""
import argparse
import json
import subprocess
from pathlib import Path


def overlaps(a, b):
    a, b = Path(a).resolve(), Path(b).resolve()
    try:
        a.relative_to(b)
        return True
    except ValueError:
        try:
            b.relative_to(a)
            return True
        except ValueError:
            return False


def hazards(config, database):
    result = []
    for name, service in config.get('services', {}).items():
        restart = str(service.get('restart') or 'no').lower()
        env = service.get('environment') or {}
        scheduler = str(env.get('CRONPILOT_SCHEDULER_ENABLED') or 'true').lower()
        if restart == 'no' or scheduler in ('0', 'false', 'no'):
            continue
        for volume in service.get('volumes', []):
            if volume.get('type') == 'bind' and volume.get('source') and overlaps(volume['source'], database):
                result.append(name)
                break
    return sorted(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compose-file', type=Path, default=Path('docker-compose.yml'))
    parser.add_argument('--database', type=Path, default=Path('datas/job_log.sqlite'))
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        sample = {'services': {'runner': {'restart': 'unless-stopped', 'volumes': [
            {'type': 'bind', 'source': '/tmp/example-data', 'target': '/app/datas'}]}}}
        assert hazards(sample, '/tmp/example-data/job.sqlite') == ['runner']
        sample['services']['runner']['environment'] = {'CRONPILOT_SCHEDULER_ENABLED': 'false'}
        assert hazards(sample, '/tmp/example-data/job.sqlite') == []
        print('PREFLIGHT_SELF_TEST: OK')
        return 0
    try:
        result = subprocess.run(['docker', 'compose', '-f', str(args.compose_file), 'config', '--format', 'json'],
                                capture_output=True, text=True, check=True, timeout=20)
        config = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        print('PREFLIGHT_UNAVAILABLE: cannot safely inspect Compose configuration')
        return 2
    found = hazards(config, args.database)
    if found:
        print('PREFLIGHT_BLOCK: auto-restarting scheduler shares database path; services=' + ','.join(found))
        return 1
    print('PREFLIGHT_OK: no matching risk in this Compose file; other containers are not inspected')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
