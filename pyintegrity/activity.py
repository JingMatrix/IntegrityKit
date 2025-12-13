# pyintegrity/activity.py

import logging
import random
import string
from . import adb

logger = logging.getLogger(__name__)


def setup_activity_parser(parser):
    """Adds arguments for the 'activity reset' command."""
    activity_subparsers = parser.add_subparsers(
        dest='activity_command', required=True, help='Activity actions')

    parser_reset = activity_subparsers.add_parser(
        'reset',
        help='Reset the device activity level by changing the device serial number.'
    )
    parser_reset.add_argument(
        '--serial',
        help='Optional: Specify a custom serial number to set.'
    )
    parser_reset.add_argument(
        '-r', '--reboot',
        action='store_true',
        help="Optional: Reboot the device after changing the serial number."
    )
    parser_reset.set_defaults(func=handle_activity_reset)


def handle_activity_reset(args):
    """
    Resets the device's serial number to a new random or specified value.
    This has been found to be sufficient to reset the device activity level.
    """
    logger.info("Starting device serial number reset process...")

    try:
        # Determine the new serial number
        if args.serial:
            new_serial = args.serial
            logger.info(f"Using user-provided serial number: {new_serial}")
        else:
            # Generate a realistic 16-character alphanumeric serial
            new_serial = ''.join(random.choices(
                string.ascii_uppercase + string.digits, k=16))
            logger.info(f"Generated new random serial number: {new_serial}")

        # Set the new serial number using root privileges
        logger.info(f"Setting ro.serialno to {new_serial}...")
        adb.shell_su(f'resetprop ro.serialno {new_serial}')

        logger.info(f"Setting ro.boot.serialno to {new_serial}...")
        adb.shell_su(f'resetprop ro.boot.serialno {new_serial}')

        logger.info(
            "Serial number properties updated successfully. A reboot is recommended for all apps to see the change.")

        # Optionally reboot the device
        if args.reboot:
            logger.info("Rebooting device...")
            adb.run_adb_command(['reboot'])
            logger.info("Reboot command sent.")

    except adb.AdbError as e:
        logger.error(f"Failed to reset serial number: {e}")
    except Exception as e:
        is_debug = logging.getLogger().isEnabledFor(logging.DEBUG)
        logger.error(
            f"An unexpected error occurred during serial reset: {e}", exc_info=is_debug)
