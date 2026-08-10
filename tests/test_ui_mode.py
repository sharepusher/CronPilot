"""Tests for ui_mode context processor (OPT-P2-14 S0).

Validates:
- Default values (classic / light) when no cookies
- Valid cookie values are respected
- Invalid cookie values fall back to defaults
- Template context variables are injected

Fields returned by inject_ui_mode (update when adding new fields):
- ui_mode: str ('classic'|'console')
- theme: str ('light'|'dark')
- sidebar_collapsed: bool
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from flask import Flask


def _make_app():
    """Minimal Flask app with ui_mode context processor."""
    app = Flask(
        __name__,
        template_folder=os.path.join(ROOT, 'app', 'templates'),
        static_folder=os.path.join(ROOT, 'app', 'static'),
    )
    app.secret_key = 'test-ui-mode'
    app.config['TESTING'] = True

    from app.ui_mode import inject_ui_mode
    app.context_processor(inject_ui_mode)

    @app.route('/test-ui-mode')
    def test_view():
        from flask import render_template_string
        return render_template_string(
            '{{ ui_mode }}|{{ theme }}'
        )

    @app.route('/test-ui-mode-full')
    def test_view_full():
        from flask import render_template_string
        return render_template_string(
            '{{ ui_mode }}|{{ theme }}|collapsed:{{ sidebar_collapsed }}'
        )

    return app


class TestUiModeContextProcessor(unittest.TestCase):
    """Test inject_ui_mode context processor."""

    def setUp(self):
        self.app = _make_app()
        self.client = self.app.test_client()

    def test_default_values_no_cookies(self):
        """Without cookies, defaults to classic/light."""
        resp = self.client.get('/test-ui-mode')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data.decode(), 'classic|light')

    def test_classic_mode_cookie(self):
        """cp_ui_mode=classic is respected."""
        self.client.set_cookie('cp_ui_mode', 'classic', domain='localhost')
        resp = self.client.get('/test-ui-mode')
        self.assertEqual(resp.data.decode(), 'classic|light')

    def test_console_mode_cookie(self):
        """cp_ui_mode=console is respected."""
        self.client.set_cookie('cp_ui_mode', 'console', domain='localhost')
        resp = self.client.get('/test-ui-mode')
        self.assertEqual(resp.data.decode(), 'console|light')

    def test_dark_theme_cookie(self):
        """cp_theme=dark is respected."""
        self.client.set_cookie('cp_theme', 'dark', domain='localhost')
        resp = self.client.get('/test-ui-mode')
        self.assertEqual(resp.data.decode(), 'classic|dark')

    def test_console_dark_combo(self):
        """Both cookies: console + dark."""
        self.client.set_cookie('cp_ui_mode', 'console', domain='localhost')
        self.client.set_cookie('cp_theme', 'dark', domain='localhost')
        resp = self.client.get('/test-ui-mode')
        self.assertEqual(resp.data.decode(), 'console|dark')

    def test_invalid_ui_mode_falls_back(self):
        """Invalid cp_ui_mode falls back to classic."""
        self.client.set_cookie('cp_ui_mode', 'invalid_mode', domain='localhost')
        resp = self.client.get('/test-ui-mode')
        self.assertEqual(resp.data.decode(), 'classic|light')

    def test_invalid_theme_falls_back(self):
        """Invalid cp_theme falls back to light."""
        self.client.set_cookie('cp_theme', 'neon', domain='localhost')
        resp = self.client.get('/test-ui-mode')
        self.assertEqual(resp.data.decode(), 'classic|light')

    def test_empty_string_cookie_falls_back(self):
        """Empty string cookies fall back to defaults."""
        self.client.set_cookie('cp_ui_mode', '', domain='localhost')
        self.client.set_cookie('cp_theme', '', domain='localhost')
        resp = self.client.get('/test-ui-mode')
        self.assertEqual(resp.data.decode(), 'classic|light')

    def test_sidebar_collapsed_default(self):
        """Without cp_sidebar_collapsed cookie, defaults to False."""
        resp = self.client.get('/test-ui-mode-full')
        self.assertIn('collapsed:False', resp.data.decode())

    def test_sidebar_collapsed_true(self):
        """cp_sidebar_collapsed=1 sets sidebar_collapsed to True."""
        self.client.set_cookie('cp_sidebar_collapsed', '1', domain='localhost')
        resp = self.client.get('/test-ui-mode-full')
        self.assertIn('collapsed:True', resp.data.decode())

    def test_sidebar_collapsed_zero(self):
        """cp_sidebar_collapsed=0 sets sidebar_collapsed to False."""
        self.client.set_cookie('cp_sidebar_collapsed', '0', domain='localhost')
        resp = self.client.get('/test-ui-mode-full')
        self.assertIn('collapsed:False', resp.data.decode())


if __name__ == '__main__':
    unittest.main()
