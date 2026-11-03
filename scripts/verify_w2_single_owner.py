"""C-0 单主机进程生命周期锁可行性；仅使用隔离文件和 JobStore。"""
import json
import multiprocessing as mp
import sys
import tempfile
from pathlib import Path

import portalocker
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.CuBackgroundScheduler import CuBackgroundScheduler


def owner(lock_path, job_url, events, commands):
    with open(lock_path, 'a+b') as lock_file:
        try:
            portalocker.lock(lock_file, portalocker.LOCK_EX | portalocker.LOCK_NB)
        except portalocker.exceptions.LockException:
            events.put('rejected_before_jobstore')
            return
        scheduler = CuBackgroundScheduler(jobstores={'default': SQLAlchemyJobStore(url=job_url)}, timezone='UTC')
        scheduler.start(paused=True)
        try:
            if scheduler.get_job('probe') is None:
                scheduler.add_job('time:time', 'cron', hour='12', id='probe', next_run_time=None)
            events.put('owner_ready')
            while True:
                command = commands.get(timeout=30)
                if command == 'resume':
                    scheduler.resume_job('probe')
                    events.put('running' if scheduler.get_job('probe').next_run_time is not None else 'unexpected')
                elif command == 'inspect':
                    events.put('paused' if scheduler.get_job('probe').next_run_time is None else 'running')
                elif command == 'exit':
                    return
                else:
                    raise ValueError('unknown command')
        finally:
            scheduler.shutdown(wait=True)  # 锁覆盖调度器关闭；不删除锁文件。


def main():
    ctx = mp.get_context('spawn')
    processes = []
    with tempfile.TemporaryDirectory(prefix='cronpilot-w2-owner-') as directory:
        root = Path(directory)
        lock = str(root / 'owner.lock')
        url = 'sqlite:///' + str(root / 'jobs.sqlite')

        def start():
            events, commands = ctx.Queue(), ctx.Queue()
            process = ctx.Process(target=owner, args=(lock, url, events, commands))
            processes.append(process)
            process.start()
            return process, events, commands

        try:
            first, events, commands = start()
            assert events.get(timeout=15) == 'owner_ready'
            contender, rejected, _ = start()
            assert rejected.get(timeout=15) == 'rejected_before_jobstore'
            contender.join(timeout=10)
            assert contender.exitcode == 0
            commands.put('inspect')
            assert events.get(timeout=10) == 'paused'
            # 只有已确认旧进程真正退出后才接管，不用锁 TTL 推断退出。
            first.terminate()
            first.join(timeout=10)
            assert not first.is_alive()
            second, events2, commands2 = start()
            assert events2.get(timeout=15) == 'owner_ready'
            commands2.put('inspect')
            assert events2.get(timeout=10) == 'paused'
            commands2.put('resume')
            assert events2.get(timeout=10) == 'running'
            commands2.put('exit')
            second.join(timeout=10)
            assert second.exitcode == 0
            third, events3, commands3 = start()
            assert events3.get(timeout=15) == 'owner_ready'
            commands3.put('inspect')
            assert events3.get(timeout=10) == 'running'
            commands3.put('exit')
            third.join(timeout=10)
            assert third.exitcode == 0
        finally:
            for process in processes:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)
    print(json.dumps({'host_local_lifetime_lock': True, 'second_owner_rejected_before_jobstore': True,
                      'takeover_after_confirmed_process_exit': True, 'restart_retains_jobstore_state': True,
                      'scheduler_globally_paused': True, 'isolated_cleanup': True}))


if __name__ == '__main__':
    main()
