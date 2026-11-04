from unittest.mock import patch
from tests.test_rbac_scope import TestScopeIntegration
from datas.model.rbac_user import RbacUser
from datas.model.cron_infos import CronInfos
from sqlalchemy import select

for mode in ('old_session','viewer_login'):
    for path in ('/cron_edit','/update_status','/cron_add'):
        f=TestScopeIntegration('test_login_sets_group_ids'); f.setUp()
        try:
            f._login('op_a')
            with f.app.app_context():
                user=f.db.session.scalar(select(RbacUser).where(RbacUser.username=='op_a'))
                user.role='viewer'; user.auth_version=int(user.auth_version or 0)+1
                f.db.session.commit()
                before=f.db.session.get(CronInfos,f.a_id).status
            if mode=='viewer_login':
                with f.client.session_transaction() as sess: sess.clear()
                f._login('op_a')
                with f.client.session_transaction() as sess: assert sess.get('role') == 'viewer'
            data={'id':f.a_id,'status':'0','task_name':'must-not-create'}
            with patch('app.services.cron_status_apply.apply_status') as apply:
                response=f.client.post(path,data=data,headers={'X-Requested-With':'XMLHttpRequest'})
                result=response.get_json(silent=True)
                if mode=='old_session':
                    assert result and result.get('errcode')==1 and '失效' in result.get('errmsg','')
                else:
                    assert response.status_code==403 and result and result.get('errcode')==1
                assert apply.call_count==0
            with f.app.app_context():
                assert f.db.session.get(CronInfos,f.a_id).status==before
                assert f.db.session.scalar(select(CronInfos).where(CronInfos.task_name=='must-not-create')) is None
            print(mode,path,'HTTP',response.status_code,'denied=True')
        finally:
            with f.app.app_context(): f.db.session.remove(); f.db.drop_all()
print('NEW_REQUEST_AUTHORIZATION: OK cases=6')
