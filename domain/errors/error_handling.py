import traceback

from domain.config.slack import get_slack_url
from domain.logging.app_logging import configure_logging
from infrastructure.slack import send_slack_message

logger = configure_logging(__name__)


def handle_error(exception):
    """
    A common error handler that prints the exception message, stack trace, and sends the message to slack
    :param exception: The exception to log
    """
    error_message = getattr(exception, 'message', repr(exception))
    logger.error(error_message)
    logger.error(traceback.format_exc())
    send_slack_message(error_message, get_slack_url)