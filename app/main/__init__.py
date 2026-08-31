from flask import Blueprint

main = Blueprint('main', __name__)


@main.app_template_filter('humanize_schedule')
def _humanize_schedule_filter(item):
    from app.services.cron_schedule_display import humanize_schedule
    return humanize_schedule(item)


@main.app_template_filter('format_cron_expression')
def _format_cron_expression_filter(item):
    from app.services.cron_schedule_display import format_cron_expression
    return format_cron_expression(item)


@main.app_template_filter('schedule_empty_hint')
def _schedule_empty_hint_filter(item, status=None):
    from app.services.cron_schedule_display import schedule_empty_hint
    return schedule_empty_hint(item, status)


from . import errors, views
