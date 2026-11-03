#!/usr/bin/env python3
"""Execute the actual user-edit preflight with jQuery and isolated browser DOMs."""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def _edit_script():
    template = (ROOT / 'app/templates/redesign/user_form.html').read_text()
    marker = '{% if user and not view_mode and not edit_unavailable %}'
    return template.split(marker, 1)[1].split('{% endif %}', 1)[0]


def verify(executable_path=None):
    select = '<select name="group_ids" multiple>%s</select>'
    concrete = '<option value="1" selected>A</option>'
    global_option = '<option value="__ALL__" selected>ALL</option>'
    hidden = '<input type="hidden" name="group_ids" value="%s">'
    cases = [
        ('specific_noop', [1], select % concrete, 0, 'admin'),
        ('order_and_duplicates', [1, 2], select % (
            '<option value="2" selected>B</option>' + concrete + concrete), 0, 'admin'),
        ('global_noop', [], select % global_option, 0, 'admin'),
        ('global_to_specific', [], select % concrete, 1, 'admin'),
        ('specific_to_global', [1], select % global_option, 1, 'admin'),
        ('add_group', [1], select % (concrete + '<option value="2" selected>B</option>'), 1, 'admin'),
        ('remove_group', [1, 2], select % concrete, 1, 'admin'),
        ('empty_is_not_global', [], select % '<option value="1">A</option>', 1, 'admin'),
        ('mixed_marker', [], select % (concrete + global_option), 1, 'admin'),
        ('invalid_integer', [1], hidden % '1oops', 1, 'admin'),
        ('unsafe_integer', [1], hidden % '9007199254740992', 1, 'admin'),
        ('disabled_source', [], '<select name="group_ids" disabled multiple>' +
         global_option + '</select>', 1, 'admin'),
        ('conflicting_sources', [1], (select % concrete) + (hidden % '1'), 1, 'admin'),
        ('multiple_selects', [1], (select % concrete) * 2, 1, 'admin'),
        ('hidden_noop', [1], hidden % '1', 0, 'admin'),
        ('hidden_change', [1], hidden % '2', 1, 'admin'),
        ('missing_control', [], '', 1, 'admin'),
        ('non_admin_global', [], select % global_option, 1, 'viewer'),
    ]
    results = []
    with sync_playwright() as playwright:
        options = {'headless': True}
        if executable_path:
            options['executable_path'] = executable_path
        browser = playwright.chromium.launch(**options)
        try:
            for name, original_groups, markup, expected_posts, role in cases:
                page = browser.new_page()
                page.set_content(
                    '<form class="js-ajax-form js-user-edit-form" novalidate action="/rbac/users/edit">'
                    '<input name="email" value="a@example.invalid"><input name="nickname" value="old">'
                    '<select name="job_title"><option selected>qa</option></select>'
                    '<select name="role"><option selected>' + role + '</option></select>' + markup +
                    '<button type="submit" class="js-ajax-submit">保存</button></form>'
                )
                page.add_script_tag(path=str(ROOT / 'app/static/js/jquery.js'))
                page.evaluate('''() => {
                    window.calls = []; window.messages = [];
                    window.CpToast = {success: function(m) { messages.push(m); }};
                    jQuery.ajax = function(options) { calls.push(options.data); };
                }''')
                page.add_script_tag(path=str(ROOT / 'app/static/js/common-redesign.js'))
                original = {
                    'email': 'a@example.invalid', 'nickname': 'old', 'job_title': 'qa',
                    'role': role, 'group_ids': original_groups,
                }
                page.add_script_tag(content=_edit_script().replace(
                    '{{ user_edit_original|tojson }}', json.dumps(original),
                ))
                page.evaluate('calls = []; messages = []')
                expected_payload = page.evaluate("jQuery('form').serialize()")
                page.get_by_role('button', name='保存').click()
                actual = page.evaluate('({calls: calls, messages: messages})')
                assert len(actual['calls']) == expected_posts, (name, actual)
                if expected_posts:
                    assert actual['calls'] == [expected_payload], (name, 'payload was changed')
                    assert not actual['messages'], (name, actual)
                else:
                    assert actual['messages'] == ['未检测到变更，无需保存'], (name, actual)
                results.append({'case': name, 'posts': len(actual['calls']), 'passed': True})
                page.close()
        finally:
            browser.close()
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--executable-path')
    parser.add_argument('--json-output', type=Path)
    args = parser.parse_args()
    results = verify(args.executable_path)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print('USER_EDIT_GROUP_PREFLIGHT: OK cases=%s' % len(results))


if __name__ == '__main__':
    main()
