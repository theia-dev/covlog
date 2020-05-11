from flask import Blueprint
main = Blueprint('main', __name__)
from . import views, jinja_helper, admin_views
