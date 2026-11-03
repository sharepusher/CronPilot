"""隔离复现当前下线先移除调度、后提交失败的基线缺陷；修复后此复现应不再成立。"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unittest.mock import patch
from tempfile import TemporaryDirectory
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from flask_apscheduler import APScheduler
from app import db
from app.crons import cron_do
from app.services.cron_service import retire_cron_by_id
from tests.test_cron_edit_noop import TestCronEditNoop
case=TestCronEditNoop('test_direct_service_preserves_model_return_and_zero_side_effects');case.setUp()
try:
 with TemporaryDirectory() as folder:
  scheduler=BackgroundScheduler(jobstores={'default':SQLAlchemyJobStore(url='sqlite:///'+str(Path(folder)/'jobs.sqlite'))})
  api=APScheduler(scheduler=scheduler);scheduler.start(paused=True)
  try:
   key='cron_%s'%case.task_id
   scheduler.add_job(cron_do,'cron',id=key,args=[case.task_id],hour='23',minute='59',next_run_time=None)
   with patch('app.services.cron_service.scheduler',api),patch.object(db.session,'commit',side_effect=RuntimeError('commit failure')):
    try: retire_cron_by_id(case.task_id,'isolated assessment')
    except RuntimeError: pass
   db.session.rollback();db.session.refresh(case.task)
   assert scheduler.get_job(key) is None and case.task.status==0
   print('REPRODUCED: scheduler job absent, database status=0')
  finally: scheduler.shutdown(wait=True)
finally: case.tearDown()
