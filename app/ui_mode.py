"""UI mode & color theme context processor for dual-mode (Classic/Console) support.

OPT-P2-14 S0: Reads Cookie values and injects `ui_mode` / `theme` into all
Jinja templates so that `<html>` can render the correct `data-ui-mode` and
`data-theme` attributes on first paint (SSR, no FOUC).

OPT-P1-16 Phase 1: Added `ui_version` (v1/v2) for redesign dual-track.
"""

from flask import request, current_app

_VALID_UI_MODES = ('classic', 'console')
_VALID_THEMES = ('light', 'dark')
_VALID_UI_VERSIONS = ('v1', 'v2')


def inject_ui_mode():
    """Return template context with current ui_mode, theme, and ui_version from cookies."""
    ui_mode = request.cookies.get('cp_ui_mode', 'classic')
    theme = request.cookies.get('cp_theme', 'light')
    sidebar_collapsed = request.cookies.get('cp_sidebar_collapsed', '0') == '1'

    if ui_mode not in _VALID_UI_MODES:
        ui_mode = 'classic'
    if theme not in _VALID_THEMES:
        theme = 'light'

    # OPT-P1-16: UI version for redesign dual-track
    ui_version = request.cookies.get('cp_ui_version', 'v1')
    if current_app.config.get('CRONPILOT_FORCE_NEW_UI'):
        ui_version = 'v2'
    if ui_version not in _VALID_UI_VERSIONS:
        ui_version = 'v1'

    return {
        'ui_mode': ui_mode,
        'theme': theme,
        'sidebar_collapsed': sidebar_collapsed,
        'ui_version': ui_version,
    }
