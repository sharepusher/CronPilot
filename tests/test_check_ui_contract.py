"""
Unit tests for scripts/check_ui_contract.py

Key regression: token-based legacy-class detection must NOT produce
false positives for classes with a legacy name as a prefix
(e.g. "btn-danger-c" must not match "btn-danger").
"""
import sys
import os
import unittest

# Allow importing from project root without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.check_ui_contract import (
    check_legacy_classes,
    check_inline_styles,
    check_hex_in_style_attr,
    _is_allowed_style,
)


class TestLegacyClassDetection(unittest.TestCase):

    # ── False-positive guard (regression: substring → token matching) ──────

    def test_no_false_positive_btn_danger_c(self):
        """'btn-danger-c' (project class) must NOT match legacy 'btn-danger'."""
        lines = ['<a class="btn-c btn-danger-c btn-xs">删除</a>']
        result = check_legacy_classes(lines, 'test.html')
        self.assertEqual(result, [], msg="btn-danger-c must not trigger btn-danger rule")

    def test_no_false_positive_btn_primary_c(self):
        """'btn-primary-c' must NOT match legacy 'btn-primary'."""
        lines = ['<a class="btn-c btn-primary-c">操作</a>']
        result = check_legacy_classes(lines, 'test.html')
        self.assertEqual(result, [], msg="btn-primary-c must not trigger btn-primary rule")

    def test_no_false_positive_btn_success_c(self):
        """'btn-success-c' must NOT match legacy 'btn-success'."""
        lines = ['<button class="btn-c btn-success-c js-ajax-submit">批准</button>']
        result = check_legacy_classes(lines, 'test.html')
        self.assertEqual(result, [], msg="btn-success-c must not trigger btn-success rule")

    def test_no_false_positive_btn_default_c(self):
        """'btn-default-c' must NOT match legacy 'btn-default'."""
        lines = ['<button class="btn-c btn-default-c">取消</button>']
        result = check_legacy_classes(lines, 'test.html')
        self.assertEqual(result, [], msg="btn-default-c must not trigger btn-default rule")

    # ── True-positive detection ────────────────────────────────────────────

    def test_detect_btn_danger(self):
        """Bare 'btn-danger' token must be reported."""
        lines = ['<button class="btn btn-danger">确认删除</button>']
        result = check_legacy_classes(lines, 'test.html')
        self.assertTrue(
            any(v['detail'] == 'class contains "btn-danger"' for v in result),
            msg="btn-danger should be reported as legacy class"
        )

    def test_detect_btn_primary(self):
        lines = ['<button class="btn btn-primary js-ajax-submit">保存</button>']
        result = check_legacy_classes(lines, 'test.html')
        self.assertTrue(
            any(v['detail'] == 'class contains "btn-primary"' for v in result)
        )

    def test_detect_control_group(self):
        lines = ['<div class="control-group">']
        result = check_legacy_classes(lines, 'test.html')
        self.assertTrue(
            any(v['detail'] == 'class contains "control-group"' for v in result)
        )

    def test_detect_form_control(self):
        lines = ['<textarea class="form-control" rows="3"></textarea>']
        result = check_legacy_classes(lines, 'test.html')
        self.assertTrue(
            any(v['detail'] == 'class contains "form-control"' for v in result)
        )

    def test_detect_controls(self):
        lines = ['<div class="controls"><input type="text"></div>']
        result = check_legacy_classes(lines, 'test.html')
        self.assertTrue(
            any(v['detail'] == 'class contains "controls"' for v in result)
        )

    def test_line_number_reported_correctly(self):
        lines = [
            '<div class="cp-main">',
            '<button class="btn btn-danger">删除</button>',
        ]
        result = check_legacy_classes(lines, 'test.html')
        self.assertEqual(result[0]['line'], 2)

    def test_cp_btn_classes_not_flagged(self):
        """Project-native cp-btn classes must not be flagged."""
        lines = ['<button class="cp-btn cp-btn--primary cp-btn--sm">保存</button>']
        result = check_legacy_classes(lines, 'test.html')
        self.assertEqual(result, [])


class TestInlineStyleAllowlist(unittest.TestCase):

    def test_css_var_allowed(self):
        self.assertTrue(_is_allowed_style('color:var(--cp-danger)'))

    def test_display_none_allowed(self):
        self.assertTrue(_is_allowed_style('display:none'))

    def test_width_100pct_allowed(self):
        self.assertTrue(_is_allowed_style('width:100%'))

    def test_position_allowed(self):
        self.assertTrue(_is_allowed_style('position:relative'))

    def test_font_weight_not_allowed(self):
        self.assertFalse(_is_allowed_style('font-weight:600'))

    def test_font_size_not_allowed(self):
        self.assertFalse(_is_allowed_style('font-size:11px'))

    def test_margin_not_allowed(self):
        self.assertFalse(_is_allowed_style('margin-top:8px'))

    def test_width_px_not_allowed(self):
        """Specific px widths (e.g. column widths) should not be allowed as inline."""
        self.assertFalse(_is_allowed_style('width:140px'))


class TestInlineStyleCheck(unittest.TestCase):

    def test_detect_font_weight_inline(self):
        lines = ['<th style="font-weight:600">操作</th>']
        result = check_inline_styles(lines, 'test.html')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['type'], 'inline-style')

    def test_allow_display_none(self):
        lines = ['<div style="display:none">hidden</div>']
        result = check_inline_styles(lines, 'test.html')
        self.assertEqual(result, [])

    def test_allow_css_var_only(self):
        lines = ['<span style="color:var(--cp-danger);font-weight:inherit">text</span>']
        # font-weight:inherit is NOT a CSS var but also not a known violation pattern
        # Actually "inherit" is a keyword — should fail since it's not in our allowlist
        result = check_inline_styles(lines, 'test.html')
        # "font-weight:inherit" is not allowed (not a CSS var, not display/position/dimension)
        self.assertEqual(len(result), 1)


class TestHexInStyleAttr(unittest.TestCase):

    def test_detect_hex_color_in_style(self):
        lines = ['<div style="color:#FF0000">text</div>']
        result = check_hex_in_style_attr(lines, 'test.html')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['type'], 'hardcoded-color')

    def test_no_hex_in_class_attr(self):
        """Hex in class attr (not style) should not be flagged."""
        lines = ['<div class="color-FF0000">text</div>']
        result = check_hex_in_style_attr(lines, 'test.html')
        self.assertEqual(result, [])

    def test_css_var_in_style_not_flagged(self):
        lines = ['<div style="color:var(--cp-danger)">text</div>']
        result = check_hex_in_style_attr(lines, 'test.html')
        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()
