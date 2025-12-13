# pyintegrity/utils.py

import logging
import os
import sys
try:
    import colorlog
except ImportError:
    colorlog = None


class Colors:
    """A simple class to hold ANSI color codes for printing."""
    # Check if stdout is a terminal, disable colors if not (e.g., redirecting to a file)
    _is_tty = sys.stdout.isatty()

    HEADER = '\033[95m' if _is_tty else ''   # Light Magenta
    BLUE = '\033[94m' if _is_tty else ''      # Blue
    CYAN = '\033[96m' if _is_tty else ''      # Cyan
    GREEN = '\033[92m' if _is_tty else ''     # Green
    WARNING = '\033[93m' if _is_tty else ''  # Yellow
    FAIL = '\033[91m' if _is_tty else ''      # Red
    ENDC = '\033[0m' if _is_tty else ''       # End Color (reset)
    BOLD = '\033[1m' if _is_tty else ''       # Bold


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


def get_cache_dir():
    """
    Returns the appropriate user-level cache directory for the current OS.
    """
    if sys.platform == "win32":
        # C:\Users\<user>\AppData\Roaming\IntegrityKit
        path = os.path.join(os.environ.get("APPDATA", ""), "IntegrityKit")
    else:
        # ~/.config/integritykit
        path = os.path.join(os.path.expanduser("~"), ".config", "integritykit")

    # Ensure the directory exists
    os.makedirs(path, exist_ok=True)
    return path
