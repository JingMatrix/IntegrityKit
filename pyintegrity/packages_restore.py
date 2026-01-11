# pyintegrity/packages_restore.py

import logging
import os
import glob
import time
from datetime import datetime
from . import adb
from .constants import *
from .utils import Colors

logger = logging.getLogger(__name__)


def setup_restore_parser(parser):
    """Adds arguments for the 'packages restore' command."""
    restore_group = parser.add_mutually_exclusive_group(required=True)
    restore_group.add_argument(
        '--list', action='store_true', help='List available local backups.')
    restore_group.add_argument('backup_number', nargs='?', type=int,
                               help='The number of the backup to restore (from --list).')

    parser.add_argument('--apply-changes', action='store_true',
                        help='Perform a soft reboot to apply the restored file immediately.')
    parser.add_argument('--force', '-f', action='store_true',
                        help='Bypass the confirmation prompt before restoring.')
    parser.set_defaults(func=handle_restore)


def _get_backups():
    """Scans the backup directory and returns a sorted list of backup files."""
    backup_pattern = os.path.join(PACKAGES_BACKUP_DIR, "packages.xml.*.bk")
    # Use glob to find all matching files
    files = glob.glob(backup_pattern)
    # Sort files by modification time, newest first
    files.sort(key=os.path.getmtime, reverse=True)
    return files


def handle_restore(args):
    """Main handler for the 'restore' command."""
    try:
        if args.list:
            _list_backups()
        elif args.backup_number is not None:
            _restore_backup(args.backup_number, args.force, args.apply_changes)
    except (adb.AdbError, RuntimeError, FileNotFoundError, IndexError) as e:
        logger.error(f"{Colors.FAIL}Operation failed: {e}{Colors.ENDC}")


def _list_backups():
    """Lists available backups in a numbered, human-readable format."""
    logger.info(f"Scanning for backups in: {PACKAGES_BACKUP_DIR}")
    backups = _get_backups()

    if not backups:
        logger.warning("No backups found.")
        return

    print(f"\n{Colors.HEADER}--- Available Backups for packages.xml ---{Colors.ENDC}")
    print(f"{Colors.BOLD}{'Num':<5} {'Timestamp':<25} {'Filename'}{Colors.ENDC}")
    print(f"{Colors.CYAN}{'-' * 70}{Colors.ENDC}")

    for i, backup_path in enumerate(backups):
        mtime = os.path.getmtime(backup_path)
        # Convert timestamp to a readable date-time string
        timestamp_str = datetime.fromtimestamp(
            mtime).strftime('%Y-%m-%d %H:%M:%S')
        filename = os.path.basename(backup_path)
        print(f"{i+1:<5} {timestamp_str:<25} {filename}")
    print()


def _restore_backup(backup_number, force, apply_changes):
    """Worker function to perform the restore operation."""
    backups = _get_backups()
    if not backups:
        raise RuntimeError("No backups found to restore.")

    if not (1 <= backup_number <= len(backups)):
        raise IndexError(
            f"Invalid backup number. Please choose a number between 1 and {len(backups)}.")

    # Get the selected backup file path (adjust for 0-based index)
    selected_backup = backups[backup_number - 1]
    filename = os.path.basename(selected_backup)

    if not force:
        try:
            confirm = input(
                f"{Colors.WARNING}This will overwrite the current packages.xml on your device with the backup '{filename}'.{Colors.ENDC}\nAre you sure you want to continue? [y/N]: ")
            if confirm.lower() != 'y':
                logger.info("Aborted by user.")
                return
        except (KeyboardInterrupt, EOFError):
            logger.info("\nAborted by user.")
            return

    logger.info(f"--- Step 1/2: Pushing backup '{filename}' to device... ---")

    # 1. Push the selected binary backup to the device's staging area
    temp_remote_path = f"/data/local/tmp/{filename}"
    adb.transfer_and_clean(selected_backup, temp_remote_path)

    logger.info("--- Step 2/2: Replacing file and restoring context... ---")

    # 2. Atomically move the file and restore permissions/context
    adb.shell_su(
        f"mv {temp_remote_path} {PACKAGES_XML_PATH}")

    adb.shell_su(
        f"chown system:system {PACKAGES_XML_PATH}")

    adb.shell_su(
        f"chmod 640 {PACKAGES_XML_PATH}")

    adb.shell_su(
        f"restorecon {PACKAGES_XML_PATH}")


    logger.info(
        f"{Colors.GREEN}Successfully restored {PACKAGES_XML_PATH} from backup.{Colors.ENDC}")

    if apply_changes:
        logger.info("Performing a soft reboot to apply changes...")
        adb.shell_su('killall system_server')
    else:
        logger.warning(
            "Restore complete. A reboot (or 'system soft-reboot') is required for the change to take effect.")
