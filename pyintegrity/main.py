# pyintegrity/main.py

import argparse
import sys
import logging

from . import adb
from . import pif
from . import tee
from . import activity

# This logger is already configured by the entrypoint script
logger = logging.getLogger(__name__)


def create_parser():
    """Creates and configures the argument parser."""
    parser = argparse.ArgumentParser(
        prog="pyintegrity",
        description="A command-line tool to manage "
        "Google Play Integrity bypass techniques.",
        add_help=False
    )

    # We add a generic group for global options to show up nicely in help
    global_options = parser.add_argument_group('global arguments')
    global_options.add_argument(
        '-h', '--help',
        action='help',
        help='Show this help message and exit'
    )
    global_options.add_argument(
        '--debug',
        action='store_true',
        help="Enable verbose debug logging."
    )

    subparsers = parser.add_subparsers(
        dest='command', required=True, help='Available commands')

    # Delegate parser setup to each module
    pif.setup_pif_parser(subparsers.add_parser(
        'pif', help='Manage PlayIntegrityFix (pif.json).'))
    activity.setup_activity_parser(subparsers.add_parser(
        'activity', help='Manage device activity.'))
    tee.setup_tee_parser(subparsers.add_parser(
        'tee', help='Manage TEESimulator configurations (keybox, target, patch).'))

    return parser


def run(argv=None):
    """
    Parses arguments and executes the main logic.
    Called by the entrypoint script.
    """
    parser = create_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    try:
        # Check for ADB connection before running any command
        adb.check_adb_device()

        # Call the function associated with the chosen command
        if hasattr(args, 'func'):
            args.func(args)
        else:
            parser.print_help()

    except adb.AdbError as e:
        logger.error(f"ADB Error: {e}")
        sys.exit(1)
    except Exception as e:
        is_debug = logging.getLogger().isEnabledFor(logging.DEBUG)
        logger.error(f"An unexpected error occurred: {e}", exc_info=is_debug)
        sys.exit(1)
