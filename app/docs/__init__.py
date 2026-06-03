from flask import Blueprint

docs = Blueprint('docs', __name__, url_prefix='/docs')

from . import views  # noqa: E402,F401
