# pyintegrity/sync.py

import logging
import os
from . import adb, utils
from .utils import Colors

logger = logging.getLogger(__name__)

# --- Constants ---
TEE_BASE_DIR = "/data/adb/tricky_store"
SYNC_DIR = os.path.join(utils.get_cache_dir(), "device_configs")
FILES_TO_SYNC = ["target.txt", "security_patch.txt"]


def setup_sync_parser(parser):
    """Adds arguments for the 'tee sync' command."""
    os.makedirs(SYNC_DIR, exist_ok=True)

    sync_group = parser.add_mutually_exclusive_group(required=True)
    sync_group.add_argument('--pull', action='store_true',
                            help='Pull config files from device to local sync directory.')
    sync_group.add_argument('--push', action='store_true',
                            help='Push config files from local sync directory to device.')
    parser.set_defaults(func=handle_sync)


def handle_sync(args):
    """Main handler for 'tee sync' commands."""
    logger.info(
        f"Local sync directory is: {Colors.CYAN}{SYNC_DIR}{Colors.ENDC}")
    try:
        if args.pull:
            for filename in FILES_TO_SYNC:
                remote_path = f"{TEE_BASE_DIR}/{filename}"
                local_path = os.path.join(SYNC_DIR, filename)
                try:
                    adb.pull_file_as_root(remote_path, local_path)
                    logger.info(f"Successfully pulled '{filename}'.")
                except FileNotFoundError:
                    logger.warning(
                        f"'{filename}' not found on device, skipping.")
            logger.info(
                f"{Colors.GREEN}Pull complete. You can now edit the files locally.{Colors.ENDC}")
        elif args.push:
            for filename in FILES_TO_SYNC:
                local_path = os.path.join(SYNC_DIR, filename)
                remote_path = f"{TEE_BASE_DIR}/{filename}"
                if os.path.exists(local_path):
                    logger.info(f"Pushing local '{filename}' to device...")
                    adb.transfer_and_clean(local_path, remote_path)
                    logger.info(f"Successfully pushed '{filename}'.")
                else:
                    logger.warning(
                        f"Local file '{filename}' not found, skipping.")
            logger.info(f"{Colors.GREEN}Push complete.{Colors.ENDC}")

    except (adb.AdbError, RuntimeError) as e:
        logger.error(f"Sync operation failed: {e}")
