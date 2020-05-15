from jinja2 import Markup
from . import main
from .. import tex_env


@main.app_template_filter()
def join_list(in_list):
    return " | ".join(in_list)


@main.app_template_filter()
def nice_date(date):
    return Markup(date.strftime("%d. %B %Y %I:%M%p"))


tex_env.filters['nice_date'] = nice_date
