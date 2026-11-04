"""In-memory mutation calibration; never modifies production files."""
import ast
import json
from pathlib import Path
from unittest.mock import patch

from app.rbac import services
from tests.test_rbac_postcommit_boundary import TestRbacPostcommitBoundary

source = Path('app/rbac/services.py').read_text()
functions = {node.name: ast.get_source_segment(source, node)
             for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)}
mutations = [
    ('update_user_management', 'if auth_changed:\n        _invalidate_api_scope_cache(user_id)',
     'if auth_changed:\n        _invalidate_api_scope_cache(user.id)', 'edit'),
    ('set_user_active', '(committed_username, reason)', '(user.username, reason)', 'disable'),
    ('issue_user_api_token', "'token': committed_token", "'token': user.api_token", 'token'),
]
results = {}
for name, before, after, case in mutations:
    assert before in functions[name]
    namespace = dict(services.__dict__)
    exec(compile(functions[name].replace(before, after), '<negative-control>', 'exec'), namespace)
    detected = False
    with patch.object(services, name, namespace[name]):
        try:
            TestRbacPostcommitBoundary().exercise(case)
        except AssertionError:
            detected = True
    assert detected, name + ' mutation escaped detection'
    results[case] = detected
print(json.dumps(results, sort_keys=True))
