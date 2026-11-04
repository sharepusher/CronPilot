import json
from sqlalchemy import event
from tests.test_user_edit_change_set import TestUserEditChangeSet
from app.rbac.services import build_user_edit_intent, update_user_management
from app.api import _resolve_user_token, _SCOPE_CACHE
from datas.model.rbac_user import RbacUser
case=TestUserEditChangeSet();case.setUp()
with case.app.test_request_context('/rbac/users/edit',method='POST'):
 target=case.db.session.get(RbacUser,case.target_id);target.role='operator';target.api_token='isolated-review-only-token';case.db.session.commit()
 old_scope=_resolve_user_token('isolated-review-only-token')
 original,requested=case._service_values(role='viewer')
 session=case.db.session();state={'committed':False}
 def committed(_):state['committed']=True
 def reject(ctx):
  if state['committed'] and ctx.is_column_load:raise RuntimeError('postcommit column load rejected')
 event.listen(session,'after_commit',committed);event.listen(session,'do_orm_execute',reject)
 try:update_user_management(case.actor_id,case.target_id,original,requested,build_user_edit_intent(original,requested));raised=False
 except RuntimeError:raised=True
 finally:event.remove(session,'after_commit',committed);event.remove(session,'do_orm_execute',reject)
 case.db.session.remove();stored=case.db.session.get(RbacUser,case.target_id).role
 cached=_resolve_user_token('isolated-review-only-token')
 print(json.dumps({'raised_after_commit':raised,'stored_role':stored,'old_token_resolves_role':cached['user_role'] if cached else None,'scope_before':old_scope['user_role']}))
 _SCOPE_CACHE.clear()
case.tearDown()
