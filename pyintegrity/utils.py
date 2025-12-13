# pyintegrity/utils.py

import logging
import sys
try:
    import colorlog
except ImportError:
    colorlog = None


def setup_logging(debug=False):
    """
    Configures the root logger for the application with colored output.
    """
    level = logging.DEBUG if debug else logging.INFO
    logger = logging.getLogger()
    logger.handlers = []  # Clear any existing handlers
    logger.setLevel(level)

    # Use colorlog if available, otherwise fall back to a standard formatter
    if colorlog:
        handler = colorlog.StreamHandler(sys.stdout)
        formatter = colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s - [%(levelname)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            log_colors={
                'DEBUG':    'cyan',
                'INFO':     'green',
                'WARNING':  'yellow',
                'ERROR':    'red',
                'CRITICAL': 'red,bg_white',
            }
        )
    else:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - [%(levelname)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Silence noisy libraries if not in debug mode
    if not debug:
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    logging.debug("Debug mode enabled. Verbose logging is active.")
