"""UI mode & color theme context processor for dual-mode (Classic/Console) support.

OPT-P2-14 S0: Reads Cookie values and injects `ui_mode` / `theme` into all
Jinja templates so that `<html>` can render the correct `data-ui-mode` and
`data-theme` attributes on first paint (SSR, no FOUC).
"""

from flask import request

_VALID_UI_MODES = ('classic', 'console')
_VALID_THEMES = ('light', 'dark')


def inject_ui_mode():
    """Return template context with current ui_mode and theme from cookies."""
    ui_mode = request.cookies.get('cp_ui_mode', 'classic')
    theme = request.cookies.get('cp_theme', 'light')
    sidebar_collapsed = request.cookies.get('cp_sidebar_collapsed', '0') == '1'

    if ui_mode not in _VALID_UI_MODES:
        ui_mode = 'classic'
    if theme not in _VALID_THEMES:
        theme = 'light'

    return {'ui_mode': ui_mode, 'theme': theme, 'sidebar_collapsed': sidebar_collapsed}
