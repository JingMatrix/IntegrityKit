# pyintegrity/system.py

import logging
import random
import string
from . import adb
from .constants import *
from .utils import Colors

logger = logging.getLogger(__name__)


def setup_system_parser(parser):
    """Adds arguments for the 'system' command suite."""
    subparsers = parser.add_subparsers(
        dest='system_command', required=True, help='System-level actions')

    # --- Soft-reboot Command ---
    parser_soft_reboot = subparsers.add_parser(
        'soft-reboot',
        help='Performs a soft reboot by restarting the Android system server.'
    )
    parser_soft_reboot.set_defaults(func=handle_soft_reboot)

    # --- Serial Command ---
    parser_serial = subparsers.add_parser(
        'serial',
        help='Change the device serial number to reset the activity level.'
    )
    parser_serial.add_argument(
        '--set',
        metavar='SERIAL',
        help='Optional: Specify a custom serial number to set.'
    )
    parser_serial.set_defaults(func=handle_serial)


def handle_soft_reboot(args):
    """Executes a soft reboot."""
    logger.info("Performing a soft reboot (killing system_server)...")
    logger.warning(
        "The device screen will go black and restart the Android UI. This may disconnect ADB temporarily.")
    try:
        # The ADB connection will be severed by this command, so we don't check for a clean exit.
        adb.shell_su('killall system_server')
        logger.info(
            "Command sent. Please wait for the device to restart its UI.")
    except adb.AdbError as e:
        # It's common to get a connection error as the device restarts, which is expected.
        logger.warning(
            f"Soft reboot command sent, but an ADB error occurred (this is often normal): {e}")


def handle_serial(args):
    """Resets the device's serial number to a new random or specified value."""
    logger.info("Starting device serial number reset process...")

    try:
        if args.set:
            new_serial = args.set
            logger.info(f"Using user-provided serial number: {new_serial}")
        else:
            new_serial = ''.join(random.choices(
                string.ascii_uppercase + string.digits, k=16))
            logger.info(f"Generated new random serial number: {new_serial}")

        logger.info(f"Setting ro.serialno to {new_serial}...")
        adb.shell_su(f'resetprop ro.serialno {new_serial}')

        logger.info(f"Setting ro.boot.serialno to {new_serial}...")
        adb.shell_su(f'resetprop ro.boot.serialno {new_serial}')

        logger.info(
            f"{Colors.GREEN}Serial number successfully changed to {new_serial}.{Colors.ENDC}")
        logger.warning(
            "A full reboot is recommended for all apps to see this change.")

    except adb.AdbError as e:
        logger.error(f"Failed to reset serial number: {e}")
