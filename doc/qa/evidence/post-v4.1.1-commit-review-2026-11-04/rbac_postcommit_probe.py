import json
from sqlalchemy import event
from tests.test_user_edit_change_set import TestUserEditChangeSet
from app.rbac.services import build_user_edit_intent, update_user_management
from datas.model.rbac_user import RbacUser
case=TestUserEditChangeSet();case.setUp()
with case.app.test_request_context('/rbac/users/edit',method='POST'):
 original,requested=case._service_values(role='operator')
 session=case.db.session();state={'committed':False}
 def committed(_):state['committed']=True
 def reject(ctx):
  if state['committed'] and ctx.is_column_load:raise RuntimeError('review postcommit read unavailable')
 event.listen(session,'after_commit',committed);event.listen(session,'do_orm_execute',reject)
 try:
  result=update_user_management(case.actor_id,case.target_id,original,requested,build_user_edit_intent(original,requested))
  outcome={'returned':result['ok']}
 except RuntimeError as exc:outcome={'raised_after_commit':str(exc)}
 finally:event.remove(session,'after_commit',committed);event.remove(session,'do_orm_execute',reject)
 case.db.session.remove();target=case.db.session.get(RbacUser,case.target_id);outcome['stored_role']=target.role
 print(json.dumps(outcome))
case.tearDown()
