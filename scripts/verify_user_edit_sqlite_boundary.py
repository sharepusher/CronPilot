#!/usr/bin/env python3
"""Owned temporary SQLite files only: independent-connection boundary verification."""
import argparse
import json
import multiprocessing
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from scripts.user_edit_sqlite_fixture import FileFixture, _mutate_worker, _service_worker


def require(ok, phase):
    if not ok:
        raise AssertionError(phase)


def _engine(path):
    return create_engine('sqlite:///' + str(path), connect_args={'timeout': 0})


def _competitor(path, run_id, queue):
    engine = _engine(path)
    try:
        with engine.begin() as connection:
            require(connection.scalar(text('SELECT id FROM verification_run')) == run_id,
                    'competitor_sentinel_mismatch')
            connection.execute(text("UPDATE calibration SET value='competitor' WHERE id=1"))
        queue.put({'state': 'committed'})
    except OperationalError as error:
        code = getattr(error.orig, 'sqlite_errorcode', None)
        queue.put({'state': 'busy' if code == 5 else 'unexpected_db_error', 'code': code})
    except Exception:
        queue.put({'state': 'worker_error'})
    finally:
        engine.dispose()


def _spawn_competitor(path, run_id):
    context = multiprocessing.get_context('spawn')
    queue = context.Queue()
    process = context.Process(target=_competitor, args=(str(path), run_id, queue))
    process.start()
    try:
        result = queue.get(timeout=10)
        process.join(timeout=10)
        require(not process.is_alive() and process.exitcode == 0, 'competitor_not_finished')
        return result
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
        queue.close()
        queue.join_thread()


def calibrate(path, mode, run_id):
    engine = _engine(path)
    try:
        with engine.connect() as connection:
            actual = connection.exec_driver_sql('PRAGMA journal_mode=' + mode).scalar_one()
            require(actual.upper() == mode, 'journal_mode_unavailable')
            connection.exec_driver_sql('CREATE TABLE verification_run (id TEXT PRIMARY KEY)')
            connection.execute(text('INSERT INTO verification_run VALUES (:id)'), {'id': run_id})
            connection.exec_driver_sql('CREATE TABLE calibration (id INTEGER PRIMARY KEY, value TEXT)')
            connection.exec_driver_sql("INSERT INTO calibration VALUES (1,'original')")
            connection.commit()
            # No protection: an independent process can insert its committed write.
            require(connection.exec_driver_sql('SELECT value FROM calibration WHERE id=1').scalar_one()
                    == 'original', 'calibration_row_missing')
            unprotected = _spawn_competitor(path, run_id)
            require(unprotected['state'] == 'committed', 'unprotected_control_not_writable')
            connection.rollback()
            connection.exec_driver_sql('BEGIN IMMEDIATE')
            require(connection.connection.driver_connection.in_transaction, 'no_physical_transaction')
            protected = _spawn_competitor(path, run_id)
            require(protected == {'state': 'busy', 'code': 5}, 'protected_control_not_busy')
            connection.rollback()
            released = _spawn_competitor(path, run_id)
            require(released['state'] == 'committed', 'release_control_still_blocked')
        return {'mode': mode, 'unprotected': unprotected, 'protected': protected,
                'after_release': released, 'passed': True}
    finally:
        engine.dispose()



def _start_worker(function, args):
    context = multiprocessing.get_context('spawn')
    queue = context.Queue()
    process = context.Process(target=function, args=tuple(args) + (queue,))
    process.start()
    return process, queue


def _finish_worker(process, queue):
    try:
        result = queue.get(timeout=10)
        process.join(timeout=10)
        require(not process.is_alive() and process.exitcode == 0, 'worker_not_finished')
        require(result.get('state') not in ('worker_error', 'unexpected_db_error'), 'worker_failed')
        return result
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
        queue.close()
        queue.join_thread()


def business_case(directory, mode, case, run_id, password):
    path = directory / (mode + '_' + case + '.sqlite')
    fixture = FileFixture(path, run_id, mode, password)
    held = None
    try:
        users = fixture.fixture(case)
        actor, target = users['actor'], users['target']
        original, requested = fixture.values(target, actor)
        mutation = {
            'actor_role_before': 'actor_role', 'actor_inactive_before': 'actor_inactive',
            'actor_scope_before': 'actor_scope', 'target_inactive_before': 'target_inactive',
            'target_scope_before': 'target_scope', 'same_field_before': 'same_field',
            'equivalent_before': 'equivalent', 'unrelated_before': 'unrelated',
        }.get(case)
        common = (str(path), run_id, actor['id'], target['id'])
        if mutation:
            changed = _finish_worker(*_start_worker(_mutate_worker, common + (mutation,)))
            require(changed['state'] == 'committed', 'setup_mutation_not_committed')
        before = fixture.state(target)
        if case == 'same_field_before':
            requested['email'] = 'requested@example.invalid'
        if case == 'email_clear':
            requested['email'] = None
        if case == 'auth_update':
            requested['role'] = 'operator'
        fault = {'flush_failure': 'flush_after', 'unknown_before': 'commit_before',
                 'unknown_after': 'commit_after', 'restore_failure': 'restore_failure'}.get(case)
        context = multiprocessing.get_context('spawn')
        ready, release = (context.Event(), context.Event()) if case in (
            'save_first_role', 'save_first_target') else (None, None)
        if case == 'admission_busy':
            held = _engine(path).connect()
            held.exec_driver_sql('BEGIN IMMEDIATE')
        process, queue = _start_worker(_service_worker, common + (
            original, requested, fault, ready, release))
        concurrent = None
        try:
            if ready is not None:
                require(ready.wait(10), 'protected_read_not_reached')
                concurrent = _finish_worker(*_start_worker(_mutate_worker, common + (
                    'actor_role' if case == 'save_first_role' else 'same_field',)))
                require(concurrent == {'state': 'busy', 'code': 5}, 'mutation_crossed_boundary')
                release.set()
            result = _finish_worker(process, queue)
        finally:
            if release is not None:
                release.set()
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
            if held is not None:
                held.rollback()
                held.close()
                held.engine.dispose()
                held = None
        expected_outcome = 'updated'
        if case in ('actor_role_before', 'actor_inactive_before', 'actor_scope_before',
                    'target_inactive_before', 'target_scope_before', 'admission_busy',
                    'flush_failure', 'restore_failure'):
            expected_outcome = 'failed'
        elif case == 'same_field_before':
            expected_outcome = 'conflict'
        elif case == 'equivalent_before':
            expected_outcome = 'already_applied'
        elif case in ('unknown_before', 'unknown_after'):
            expected_outcome = 'commit_unknown'
        require(result['outcome'] == expected_outcome, 'unexpected_service_outcome')
        expected = dict(before)
        durable = expected_outcome == 'updated' or case == 'unknown_after'
        if durable:
            expected.update(nickname='requested', audit=before['audit'] + 1)
            if case == 'email_clear':
                expected['email'] = None
            if case == 'auth_update':
                expected.update(role='operator', auth_version=before['auth_version'] + 1)
        after = fixture.state(target)
        if case == 'auth_update':
            require(after['secret'] != before['secret'], 'authorization_token_not_changed')
            expected['secret'] = after['secret']
        require(after == expected, 'unexpected_business_or_audit_effects')
        require(result['commits'] == int(durable), 'unexpected_commit_count')
        require(result['relationship_dml'] == 0, 'profile_edit_changed_relationships')
        require(result['cache_invalidations'] == int(case == 'auth_update'), 'unexpected_cache_effect')
        require(result['pool_timeout_after'] == 5000, 'connection_timeout_not_restored')
        if expected_outcome != 'updated':
            require(not result['transaction_at_return'], 'terminal_transaction_still_active')
        if case == 'restore_failure':
            require(result['invalidations'] == 1, 'unsafe_connection_not_discarded')
            require(result.get('restore_fault_hits') == 1, 'restore_fault_not_hit_once')
        if concurrent:
            retried = _finish_worker(*_start_worker(_mutate_worker, common + (
                'actor_role' if case == 'save_first_role' else 'same_field',)))
            require(retried['state'] == 'committed', 'writer_not_released')
            if case == 'save_first_target':
                require(fixture.state(target)['nickname'] == 'concurrent', 'later_legal_write_lost')
        return {'mode': mode, 'case_id': case, 'outcome': expected_outcome,
                'trace': result, 'competition': concurrent,
                'audit_delta': after['audit'] - before['audit'],
                'credential_changed': after['secret'] != before['secret'],
                'group_preserved': after['groups'] == before['groups'], 'passed': True}
    finally:
        if held is not None:
            held.rollback()
            held.close()
            held.engine.dispose()
        fixture.close()


BUSINESS_CASES = (
    'normal', 'actor_role_before', 'actor_inactive_before', 'actor_scope_before',
    'target_inactive_before', 'target_scope_before', 'same_field_before',
    'equivalent_before', 'unrelated_before', 'save_first_role', 'save_first_target',
    'admission_busy', 'flush_failure', 'unknown_before', 'unknown_after', 'restore_failure',
    'email_clear', 'auth_update',
)


def verify(output, calibration_only=False, executable=None):
    import secrets
    output.mkdir(parents=True, exist_ok=True)
    require(not any(output.iterdir()), 'output_must_be_empty')
    run_id = secrets.token_hex(8)
    with TemporaryDirectory(prefix='cronpilot-user-boundary-') as folder:
        directory = Path(folder).resolve()
        (directory / '.run-id').write_text(run_id)
        calibration = [calibrate(directory / (mode + '.sqlite'), mode, run_id)
                       for mode in ('DELETE', 'WAL')]
        result = {'status': 'calibration_passed', 'run_id': run_id, 'calibration': calibration}
        if not calibration_only:
            business = []
            for mode in ('DELETE', 'WAL'):
                for case in BUSINESS_CASES:
                    print('CASE_START: ' + mode + '/' + case, flush=True)
                    business.append(business_case(directory, mode, case, run_id, secrets.token_urlsafe(20)))
                    print('CASE_PASS: ' + mode + '/' + case, flush=True)
            require(len(business) == 2 * len(BUSINESS_CASES), 'missing_business_cases')
            from playwright.sync_api import sync_playwright

            from scripts.user_edit_sqlite_http import browser_case
            from scripts.user_edit_sqlite_task_probe import probe
            http_cases = []
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True, executable_path=executable)
                try:
                    for mode in ('DELETE', 'WAL'):
                        for case in ('revoke_first_role', 'revoke_first_target',
                                     'save_first_role', 'save_first_target'):
                            print('HTTP_START: ' + mode + '/' + case, flush=True)
                            http_cases.append(browser_case(directory, mode, case, run_id,
                                                           secrets.token_urlsafe(20), browser, output))
                            print('HTTP_PASS: ' + mode + '/' + case, flush=True)
                finally:
                    browser.close()
            require(len(http_cases) == 8, 'http_matrix_incomplete')
            task_probes = [probe(directory, mode, run_id, secrets.token_urlsafe(20))
                           for mode in ('DELETE', 'WAL')]
            result.update(status='passed', scope='rbac_user_edit_only', business=business,
                          http_cases=http_cases, task_probes=task_probes)
    result['temporary_files_removed'] = not directory.exists()
    require(result['temporary_files_removed'], 'temporary_files_not_removed')
    (output / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print('SQLITE_BOUNDARY: OK modes=2 controls=6 business=%s http=%s' % (
        len(result.get('business', [])), len(result.get('http_cases', []))))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--calibration-only', action='store_true')
    parser.add_argument('--executable-path')
    args = parser.parse_args()
    try:
        verify(args.output_dir, args.calibration_only, args.executable_path)
    except Exception as error:
        phase = error.args[0] if type(error) is AssertionError else 'environment_or_driver'
        print('SQLITE_BOUNDARY: FAILED type=%s phase=%s' % (type(error).__name__, phase), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
