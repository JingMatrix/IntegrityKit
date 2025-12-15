# pyintegrity/packages_reinstall.py

import logging
import os
import tempfile
from . import adb
from .packages_patch import _patch_origin_command
from .constants import *
from .utils import Colors

logger = logging.getLogger(__name__)


def setup_reinstall_parser(parser):
    """Adds arguments for the 'packages reinstall' command."""
    parser.add_argument(
        'package_name', help='The package name of the app to reinstall.')
    parser.add_argument('--origin', default='com.android.vending',
                        help='Patch the installer origin to this package after reinstalling.')
    parser.set_defaults(func=handle_reinstall)


def handle_reinstall(args):
    """Main handler for the 'reinstall' command."""
    try:
        _reinstall_command(args.package_name, args.origin)
    except (adb.AdbError, RuntimeError, FileNotFoundError) as e:
        logger.error(f"{Colors.FAIL}Operation failed: {e}{Colors.ENDC}")


def _reinstall_command(package_name, origin):
    """Performs a clean reinstall and then patches the installer origin."""
    logger.info(f"--- Step 1/3: Backing up '{package_name}' APKs... ---")

    paths_result = adb.run_adb_command(['shell', 'pm', 'path', package_name])
    apk_paths = [p.replace('package:', '')
                 for p in paths_result.stdout.strip().splitlines()]
    if not apk_paths:
        raise RuntimeError(
            f"Could not find package '{package_name}' on device.")

    with tempfile.TemporaryDirectory() as temp_dir:
        for path in apk_paths:
            adb.pull_file(path, os.path.join(temp_dir, os.path.basename(path)))
        logger.info(
            f"Pulled {len(apk_paths)} APK split(s) to a temporary directory.")

        # Step 2: Uninstall and Reinstall
        logger.info(f"--- Step 2/3: Reinstalling '{package_name}'... ---")
        logger.info(f"Uninstalling {package_name}...")
        adb.run_adb_command(['uninstall', package_name])

        logger.info("Reinstalling from pulled files...")
        pulled_apks = [os.path.join(temp_dir, f) for f in os.listdir(
            temp_dir) if f.endswith('.apk')]
        cmd = ['install-multiple'] if len(pulled_apks) > 1 else ['install']
        cmd.extend(pulled_apks)
        adb.run_adb_command(cmd)
        logger.info("Reinstallation complete.")

        # Step 3: Patch the origin
        logger.info(
            f"--- Step 3/3: Patching installer origin to '{origin}'... ---")
        _patch_origin_command(
            target_package=package_name,
            origin_package=origin,
            no_backup=True,  # No need to backup again
            apply_changes=False,
            full_reboot=False
        )

    logger.warning(
        "Reinstall and patch complete. A reboot (or 'system soft-reboot') is required to apply the changes.")
