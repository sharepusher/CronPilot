# -*- coding:utf-8 -*-
import unittest

from app.services.job_log_display import job_log_badge, job_log_content_preview, job_log_status_line


class TestJobLogDisplay(unittest.TestCase):
    def test_status_from_http_code(self):
        self.assertEqual(job_log_status_line(200, 'ok body'), ('HTTP 200', 'ok'))
        self.assertEqual(job_log_status_line(404, 'nf'), ('HTTP 404', 'warn'))
        self.assertEqual(job_log_status_line(500, 'err'), ('HTTP 500', 'fail'))

    def test_status_from_error_content(self):
        self.assertEqual(
            job_log_status_line(None, '发生严重错误: timeout'),
            ('请求异常', 'fail'),
        )
        self.assertEqual(
            job_log_status_line(None, '回调URL安全校验未通过'),
            ('未执行回调', 'muted'),
        )

    def test_badge(self):
        self.assertEqual(job_log_badge('success'), ('成功', 'ok'))
        self.assertEqual(job_log_badge('fail'), ('失败', 'fail'))
        self.assertEqual(job_log_badge(None), (None, None))

    def test_content_preview_truncates(self):
        long_text = 'x' * 200
        self.assertTrue(job_log_content_preview(long_text, 120).endswith('…'))
        self.assertEqual(job_log_content_preview('short', 120), 'short')


if __name__ == '__main__':
    unittest.main()
