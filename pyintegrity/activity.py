# pyintegrity/activity.py

import logging
import os
import random
import tempfile
import string
from . import adb

logger = logging.getLogger(__name__)

# Global constant for the Play Store package
PLAY_STORE_PACKAGE = "com.android.vending"
# Path to the module script that modifies packages.xml
PACKAGE_MODIFIER_SCRIPT = "/data/adb/modules/BetterKnownInstalled/post-fs-data.sh"


def setup_activity_parser(parser):
    """Adds arguments for the 'activity' command."""
    activity_subparsers = parser.add_subparsers(
        dest='activity_command', required=True, help='Activity actions')

    parser_reset = activity_subparsers.add_parser(
        'reset',
        help='A full sequence to reset device activity: reinstall Play Store, patch packages.xml, and soft-reboot.'
    )
    parser_reset.add_argument(
        '-r', '--reboot',
        action='store_true',
        help="Perform a full system reboot at the end instead of the default soft reboot."
    )
    parser_reset.set_defaults(func=handle_activity_reset)


def handle_activity_reset(args):
    """
    Handles the full, multi-step 'activity reset' process.
    """
    logger.info("Starting full activity reset process...")

    try:

        serial = ''.join(random.choices(
            string.ascii_uppercase + string.digits, k=10))

        logger.info(f"Setting serial number to: {serial}")
        adb.run_adb_command(['shell', 'su', '-c',
                             f'resetprop ro.serialno {serial}'])
        adb.run_adb_command(['shell', 'su', '-c',
                             f'resetprop ro.boot.serialno {serial}'])

        # --- Step 1: Reinstall the Google Play Store ---
        logger.info(f"--- Step 1/3: Reinstalling '{PLAY_STORE_PACKAGE}' ---")

        # Find all APK paths for the package
        logger.info(f"Finding APK paths for {PLAY_STORE_PACKAGE}...")
        paths_result = adb.run_adb_command(
            ['shell', 'pm', 'path', PLAY_STORE_PACKAGE])
        apk_paths = [p.replace('package:', '')
                     for p in paths_result.stdout.strip().splitlines()]

        if not apk_paths:
            logger.error(
                f"Could not find package '{PLAY_STORE_PACKAGE}' on device. Aborting.")
            return

        with tempfile.TemporaryDirectory() as temp_dir:
            # Pull all APKs to a local temporary directory
            logger.info(
                f"Pulling {len(apk_paths)} APK(s) to a temporary directory...")
            for path in apk_paths:
                local_file_path = os.path.join(
                    temp_dir, os.path.basename(path))
                adb.pull_file(path, local_file_path)

            # Uninstall the package
            logger.info(f"Uninstalling {PLAY_STORE_PACKAGE}...")
            adb.run_adb_command(['uninstall', PLAY_STORE_PACKAGE], check=False)

            # Reinstall from the pulled APKs
            logger.info("Reinstalling from pulled files...")
            pulled_apks = [os.path.join(temp_dir, f) for f in os.listdir(
                temp_dir) if f.endswith('.apk')]

            install_cmd = [
                'install-multiple'] if len(pulled_apks) > 1 else ['install']
            install_cmd.extend(pulled_apks)

            adb.run_adb_command(install_cmd)

        logger.info(f"--- Step 1/3: Play Store reinstalled successfully. ---")

        # --- Step 2: Modify packages.xml by running the script ---
        logger.info(
            f"--- Step 2/3: Executing script to modify packages.xml ---")
        logger.info(f"Running: {PACKAGE_MODIFIER_SCRIPT}")

        script_output = adb.shell_su(f'sh {PACKAGE_MODIFIER_SCRIPT}')
        logger.debug(f"Script output:\n{script_output}")

        logger.info(f"--- Step 2/3: Script execution finished. ---")

        # --- Step 3: Perform a soft reboot or full reboot ---
        if args.reboot:
            logger.info(
                f"--- Step 3/3: Performing a full system reboot... ---")
            adb.run_adb_command(['reboot'])
            logger.info("Reboot command sent.")
        else:
            logger.info(f"--- Step 3/3: Performing a soft reboot... ---")
            # This command will terminate the ADB shell, so we don't expect a clean exit.
            adb.shell_su('killall system_server')
            logger.info(
                "Soft reboot command sent. The device UI will now restart.")

        logger.info("Activity reset process initiated successfully.")

    except adb.AdbError as e:
        logger.error(f"Activity reset process failed: {e}")
    except Exception as e:
        is_debug = logging.getLogger().isEnabledFor(logging.DEBUG)
        logger.error(
            f"An unexpected error occurred during activity reset: {e}", exc_info=is_debug)
