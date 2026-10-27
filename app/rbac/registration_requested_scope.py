# -*- coding:utf-8 -*-
"""注册申请目标 Scope 的纯规范化规则（无 Session、无数据库写入）。"""

GROUP_ALL_MARKER = '__ALL__'


def normalize_registration_requested_scope(role, raw_group_ids, valid_group_ids):
    """将表单列表或历史 CSV 规范为 global / concrete / invalid。

    valid_group_ids 由调用方从数据库当前资源组读取；本函数只做确定性规则判断。
    """
    valid_ids = frozenset(int(value) for value in (valid_group_ids or []))
    normalized_input = False

    if isinstance(raw_group_ids, str):
        raw_text = raw_group_ids
        stripped = raw_text.strip()
        normalized_input = stripped != raw_text
        if not stripped:
            return _invalid('groups_required')
        values = stripped.split(',')
    else:
        values = list(raw_group_ids or [])
        if not values:
            return _invalid('groups_required')

    tokens = []
    for value in values:
        token = str(value).strip()
        if token != str(value):
            normalized_input = True
        if not token:
            return _invalid('empty_group_token')
        tokens.append(token)

    if GROUP_ALL_MARKER in tokens:
        if len(tokens) != 1:
            return _invalid('global_and_specific_groups_mixed')
        if role != 'admin':
            return _invalid('global_requires_admin')
        return {
            'ok': True,
            'kind': 'global',
            'group_ids': (),
            'reason': 'allowed',
            'normalized': normalized_input,
        }

    group_ids = []
    seen = set()
    for token in tokens:
        try:
            group_id = int(token)
        except (TypeError, ValueError):
            return _invalid('invalid_group_id')
        if group_id <= 0:
            return _invalid('invalid_group_id')
        if group_id not in valid_ids:
            return _invalid('group_not_found')
        if group_id in seen:
            normalized_input = True
            continue
        seen.add(group_id)
        group_ids.append(group_id)

    if not group_ids:
        return _invalid('groups_required')
    return {
        'ok': True,
        'kind': 'concrete',
        'group_ids': tuple(sorted(group_ids)),
        'reason': 'allowed',
        'normalized': normalized_input or group_ids != sorted(group_ids),
    }


def _invalid(reason):
    return {
        'ok': False,
        'kind': 'invalid',
        'group_ids': (),
        'reason': reason,
        'normalized': False,
    }
