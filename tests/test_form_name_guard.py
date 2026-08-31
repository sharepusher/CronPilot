# -*- coding:utf-8 -*-
"""静态门禁：cron_add/cron_edit 表单的 name 属性必须与 CronFormValidator.vue 的选择器一致。

CronFormValidator.vue 通过 querySelector('input[name=xxx]') 硬编码读取表单字段，
如果表单迁移时修改了 name 属性，组件会静默失效（不报错、不提示、校验不工作）。
本测试防止这类无声破坏。
"""
import os
import re
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TEMPLATES = os.path.join(ROOT, 'app', 'templates')
VUE_SRC = os.path.join(ROOT, 'frontend', 'src', 'components', 'CronFormValidator.vue')

REQUIRED_FIELD_NAMES = {
    'day_of_week', 'day', 'hour', 'minute', 'second',
    'req_url', 'req_method', 'req_body',
}

REQUIRED_IDS = {'cron_div'}

REQUIRED_FORM_CLASSES = {'js-cron-form'}


def _extract_name_attrs(html):
    return set(re.findall(r'name="([^"]+)"', html))


def _extract_ids(html):
    return set(re.findall(r'id="([^"]+)"', html))


def _extract_form_classes(html):
    classes = set()
    for m in re.finditer(r'<form\b([^>]*)>', html, re.IGNORECASE):
        classes.update(re.findall(r'class="[^"]*\b(js-cron-form)\b[^"]*"', m.group(1)))
    return classes


def _extract_vue_selectors(vue_src):
    names = set(re.findall(r"querySelector\(['\"](?:input|select|textarea)\[name=([^\]]+)\]", vue_src))
    ids = set(re.findall(r"getElementById\(['\"]([^'\"]+)['\"]", vue_src))
    form_classes = set(re.findall(r"querySelector\(['\"]form\.([^'\"]+)['\"]", vue_src))
    return names, ids, form_classes


class TestCronFormNameGuard(unittest.TestCase):
    """redesign/task_form.html 的 name 属性必须覆盖 Vue 组件依赖的全部字段。"""

    def _check_template(self, template_name):
        path = os.path.join(TEMPLATES, template_name)
        with open(path, encoding='utf-8') as f:
            html = f.read()
        names = _extract_name_attrs(html)
        ids = _extract_ids(html)
        form_classes = _extract_form_classes(html)

        missing_names = REQUIRED_FIELD_NAMES - names
        self.assertFalse(
            missing_names,
            '%s 缺少 CronFormValidator.vue 依赖的 name 属性: %s' % (template_name, missing_names),
        )
        missing_ids = REQUIRED_IDS - ids
        self.assertFalse(
            missing_ids,
            '%s 缺少 CronFormValidator.vue 依赖的 id: %s' % (template_name, missing_ids),
        )
        missing_classes = REQUIRED_FORM_CLASSES - form_classes
        self.assertFalse(
            missing_classes,
            '%s 缺少 CronFormValidator.vue 依赖的 form class: %s' % (template_name, missing_classes),
        )

    def test_task_form_has_required_names(self):
        self._check_template(os.path.join('redesign', 'task_form.html'))


class TestVueSelectorsMatchGuardList(unittest.TestCase):
    """Vue 组件中的选择器必须全部在守护清单中，防止新增选择器遗漏。"""

    @unittest.skipIf(not os.path.isfile(VUE_SRC), 'CronFormValidator.vue not found')
    def test_vue_selectors_covered(self):
        with open(VUE_SRC, encoding='utf-8') as f:
            vue = f.read()
        names, ids, form_classes = _extract_vue_selectors(vue)
        uncovered_names = names - REQUIRED_FIELD_NAMES
        self.assertFalse(
            uncovered_names,
            'CronFormValidator.vue 新增了 name 选择器但未加入守护清单: %s' % uncovered_names,
        )
        uncovered_ids = ids - REQUIRED_IDS
        self.assertFalse(
            uncovered_ids,
            'CronFormValidator.vue 新增了 id 选择器但未加入守护清单: %s' % uncovered_ids,
        )


if __name__ == '__main__':
    unittest.main()
