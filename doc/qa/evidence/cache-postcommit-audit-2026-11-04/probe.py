"""Isolated fault injection; uses only the registration test's in-memory DB."""
import json
from sqlalchemy import event
from tests.test_user_edit_change_set import TestUserEditChangeSet
from app.rbac import services
from app.api import _resolve_user_token, _SCOPE_CACHE
from datas.model.rbac_user import RbacUser
from datas.model.resource_group import ResourceGroup


def probe(name):
    case = TestUserEditChangeSet()
    case.setUp()
    try:
        with case.app.test_request_context('/rbac/users/edit', method='POST'):
            target = case.db.session.get(RbacUser, case.target_id)
            target.api_token = 'isolated-cache-audit-token'
            group = ResourceGroup(name='cache-probe-extra')
            case.db.session.add(group)
            case.db.session.commit()
            extra_id = group.id
            _resolve_user_token('isolated-cache-audit-token')
            session = case.db.session()
            state = {'committed': False}

            def committed(_session):
                state['committed'] = True

            def reject(ctx):
                if state['committed'] and ctx.is_column_load:
                    raise RuntimeError('isolated postcommit read failure')

            event.listen(session, 'after_commit', committed)
            event.listen(session, 'do_orm_execute', reject)
            calls = {
                'disable': lambda: services.set_user_active(case.target_id, 0, 'test', case.actor_id),
                'reset_password': lambda: services.trigger_password_reset(case.target_id, case.actor_id),
                'set_groups': lambda: services.set_user_groups(case.target_id, [extra_id]),
                'change_password': lambda: services.change_own_password(
                    case.target_id, 'test-password', 'new-test-password', 'new-test-password'),
                'issue_token': lambda: services.issue_user_api_token(case.target_id),
            }
            raised = False
            try:
                calls[name]()
            except RuntimeError:
                raised = True
            finally:
                event.remove(session, 'after_commit', committed)
                event.remove(session, 'do_orm_execute', reject)
            case.db.session.remove()
            stored = case.db.session.get(RbacUser, case.target_id)
            cached = _resolve_user_token('isolated-cache-audit-token')
            return {
                'case': name, 'committed': state['committed'], 'raised_after_commit': raised,
                'old_token_still_resolves': cached is not None,
                'stored_active': bool(stored.is_active),
                'old_token_still_stored': stored.api_token == 'isolated-cache-audit-token',
            }
    finally:
        _SCOPE_CACHE.clear()
        case.tearDown()


if __name__ == '__main__':
    print(json.dumps([probe(name) for name in (
        'disable', 'reset_password', 'set_groups', 'change_password', 'issue_token',
    )], indent=2))
