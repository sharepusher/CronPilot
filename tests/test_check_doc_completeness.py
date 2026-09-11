"""Regression tests for the doc index structure gate."""

import unittest

from scripts.check_doc_completeness import find_structure_errors

# 2026-09 事故原文：搬运 <li> 条目时剪贴边界落在 "<li>\n<div class=..." 中间
CORRUPTED = """<ul class="doc-list">
      <li>
        <div       <li>
        <div class="title">
          <a href="a.html">A</a>
        </div>
        <div class="links"><a href="a.html">HTML</a></div>
      </li>
class="title">
          <a href="b.html">B</a>
        </div>
        <div class="links"><a href="b.html">HTML</a></div>
      </li>
</ul>"""

WELL_FORMED = """<ul class="doc-list">
      <li>
        <div class="title">
          <a href="a.html">A</a>
        </div>
        <div class="links"><a href="a.html">HTML</a></div>
      </li>
</ul>"""


class TestIndexStructureGate(unittest.TestCase):

    def test_detects_cut_paste_corruption(self):
        errors = find_structure_errors(CORRUPTED)
        joined = ' | '.join(errors)
        self.assertIn('剪贴断裂', joined)
        self.assertIn('裸露的属性文本', joined)
        self.assertIn('不配对', joined)

    def test_accepts_well_formed_list(self):
        self.assertEqual(find_structure_errors(WELL_FORMED), [])

    def test_detects_unclosed_block_tag(self):
        errors = find_structure_errors('<ul><li><div class="title">A</div></ul>')
        self.assertTrue(any('未闭合' in e or '不配对' in e for e in errors), errors)

    def test_ignores_attribute_text_inside_code_samples(self):
        sample = '<div><pre>\nhref="{{ url_for(\'x\') }}"\n</pre></div>'
        self.assertEqual(find_structure_errors(sample), [])


if __name__ == "__main__":
    unittest.main()
