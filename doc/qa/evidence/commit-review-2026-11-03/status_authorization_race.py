import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from apscheduler.schedulers.background import BackgroundScheduler
from flask_apscheduler import APScheduler
from flask import Flask
from sqlalchemy import create_engine,event
from app import db
from app.services.cron_status_apply import save_status
from datas.model.cron_infos import CronInfos
from datas.model.rbac_user import RbacUser
from datas.model.resource_group import ResourceGroup
from datas.model.task_group import TaskGroup
from datas.model.user_group import UserGroup
from datas.model.operation_log import OperationLog
from app.crons import cron_do
with TemporaryDirectory(prefix='cronpilot-status-review-') as directory:
 app=Flask(__name__); uri='sqlite:///'+str(Path(directory)/'review.sqlite')
 app.config.update(SECRET_KEY='review',SQLALCHEMY_DATABASE_URI=uri,SQLALCHEMY_TRACK_MODIFICATIONS=False);db.init_app(app)
 with app.test_request_context('/update_status',method='POST'):
  db.create_all(); db.session.add_all([RbacUser(id=1,username='op',role='operator',is_active=1,auth_version=0,password_hash='test'),ResourceGroup(id=1,name='A')])
  task=CronInfos(task_name='status-review',task_keyword='test',status=0,scope_type='GROUP',hour='1',minute='0');db.session.add(task);db.session.flush();tid=task.id
  db.session.add_all([UserGroup(user_id=1,group_id=1),TaskGroup(task_id=tid,group_id=1)]);db.session.commit()
  other=create_engine(uri);done=[]
  def revoke(_conn,_cursor,sql,_params,_ctx,_many):
   if not done and sql.lstrip().startswith('SELECT user_groups.'):
    done.append(True)
    with other.begin() as c:c.execute(RbacUser.__table__.update().where(RbacUser.id==1).values(role='viewer',auth_version=1))
  base=BackgroundScheduler(timezone='UTC');api=APScheduler(scheduler=base);api.app=app;base.start(paused=True)
  base.add_job(cron_do,'cron',id='cron_%s'%tid,args=[tid],hour='1',minute='0',next_run_time=None)
  event.listen(db.engine,'before_cursor_execute',revoke)
  try:
   with patch('app.services.cron_status_apply.scheduler',api),patch('app.services.cron_edit_apply.scheduler',api):
    result=save_status(tid,1,actor_id=1)
  finally:event.remove(db.engine,'before_cursor_execute',revoke)
  db.session.expire_all();print({'independent_revocation_committed':bool(done),'ok':result[0],'current_role':db.session.get(RbacUser,1).role,'stored_status':db.session.get(CronInfos,tid).status,'real_job_resumed':api.get_job('cron_%s'%tid).next_run_time is not None})
  base.shutdown();db.session.remove();other.dispose();db.engine.dispose()
