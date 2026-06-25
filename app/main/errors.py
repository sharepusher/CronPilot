from flask import render_template, session

from . import main


@main.app_errorhandler(404)
def page_not_found(e):
    if session.get('is_login'):
        return render_template('errors/404.html'), 404
    return render_template('errors/404_guest.html'), 404


@main.app_errorhandler(500)
def internal_server_error(e):
    return 'system err'
