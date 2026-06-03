import os

from flask import abort, current_app, send_from_directory

from . import docs


def _doc_root():
    return os.path.join(current_app.config['BASEDIR'], 'doc')


@docs.route('/')
@docs.route('/index.html')
def index():
    return send_from_directory(_doc_root(), 'index.html')


@docs.route('/<path:filename>')
def serve(filename):
    if '..' in filename.split('/'):
        abort(404)
    resp = send_from_directory(_doc_root(), filename)
    if filename.lower().endswith('.md'):
        resp.headers['Content-Type'] = 'text/markdown; charset=utf-8'
    return resp
