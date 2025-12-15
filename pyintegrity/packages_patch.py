# pyintegrity/packages_patch.py

import logging
import tempfile
import os
import xml.etree.ElementTree as ET
import time
from . import adb, file_editor
from .constants import *
from .utils import Colors

logger = logging.getLogger(__name__)


def setup_patch_parser(parser):
    """Adds arguments for the 'packages patch' command."""
    parser.add_argument(
        '--package', help='Patch only a single specified package instead of all.')
    parser.add_argument('--all', action='store_true',
                             help='Force patching of ALL packages, including system apps.')
    parser.add_argument('--origin', default='com.android.vending',
                        help='Specify a custom installer origin (default: com.android.vending).')
    parser.add_argument(
        '--source',
        default='0',
        help='Set a specific packageSource value. 0=Unspecified, 2=Store, 3=Local File, 4=Downloaded. Default is 0.'
    )
    parser.add_argument('--no-backup', action='store_true',
                        help='Skip creating a local backup of the original file.')
    parser.add_argument('--apply-changes', action='store_true',
                        help='Perform a soft reboot to apply changes immediately.')
    parser.add_argument('--full-reboot', action='store_true',
                        help='Perform a full reboot instead of a soft one if --apply-changes is used.')
    parser.set_defaults(func=handle_patch)


def handle_patch(args):
    """Main handler for 'packages patch' command."""
    try:
        _patch_origin_command(args.package, args.all, args.origin, args.source,
                              args.no_backup, args.apply_changes, args.full_reboot)
    except (adb.AdbError, RuntimeError, FileNotFoundError) as e:
        logger.error(f"{Colors.FAIL}Operation failed: {e}{Colors.ENDC}")


def _patch_origin_command(target_package, patch_all, origin_package, package_source, no_backup, apply_changes, full_reboot):
    """The main worker logic for patching package origins."""
    logger.info("Starting package origin patching process...")

    # Step 0: Pre-flight checks
    logger.info("--- Step 0/6: Checking for required on-device binaries... ---")
    try:
        adb.shell_su("command -v abx2xml && command -v xml2abx")
    except adb.AdbError:
        raise RuntimeError(
            "Required binaries 'abx2xml' and 'xml2abx' not found.")

    with tempfile.TemporaryDirectory() as temp_dir:
        # Step 1: Backup
        if not no_backup:
            _backup_remote_files()

        # Step 2: Process packages.xml
        logger.info(
            f"--- Step 2/6: Processing {os.path.basename(PACKAGES_XML_PATH)}... ---")
        try:
            local_xml_path = adb._pull_and_convert_xml(
                PACKAGES_XML_PATH, temp_dir)
        except FileNotFoundError:
            raise RuntimeError(
                f"Could not find {PACKAGES_XML_PATH}. Aborting.")

        tree = ET.parse(local_xml_path)
        root = tree.getroot()

        origin_pkg_elem = root.find(f".//package[@name='{origin_package}']")
        if not origin_pkg_elem:
            raise RuntimeError(
                f"Specified origin package '{origin_package}' not found in database.")
        origin_uid = origin_pkg_elem.get('userId')
        logger.info(
            f"Found origin package '{origin_package}' with userId: {origin_uid}")

        all_packages = root.findall('package')
        packages_to_patch = []

        if target_package:
            # User specified a single package, overriding all filters
            logger.info(f"Targeting single package: {args.package}")
            pkg = root.find(f".//package[@name='{args.package}']")
            if not pkg:
                raise RuntimeError(
                    f"Target package '{args.package}' not found.")
            packages_to_patch.append(pkg)

        elif patch_all:
            # User wants to patch everything
            logger.info("Targeting ALL packages as requested by --all flag.")
            packages_to_patch = all_packages

        else:
            # Default smart behavior: target only sideloaded user apps
            logger.info(
                "Targeting sideloaded user apps by default (use --all to override).")
            packages_to_patch = [
                p for p in all_packages
                if p.get('codePath', '').startswith('/data/app') and p.get('packageSource') not in ['0', '2']
            ]

        if not packages_to_patch:
            raise RuntimeError(f"Target package '{target_package}' not found.")

        modified_count = 0
        for pkg in packages_to_patch:
            changed = False

            attributes_to_set = {
                'installer': origin_package,
                'installInitiator': origin_package,
                'installerUid': origin_uid,
                'packageSource': package_source
            }

            attributes_to_remove = ['installOriginator']

            for key, value in attributes_to_set.items():
                if pkg.get(key) != value:
                    pkg.set(key, value)
                    changed = True

            for key in attributes_to_remove:
                if key in pkg.attrib:
                    del pkg.attrib[key]
                    changed = True

            if pkg.get('isOrphaned') == 'true':
                del pkg.attrib['isOrphaned']
                changed = True
            if pkg.get('installInitiatorUninstalled') == 'true':
                del pkg.attrib['installInitiatorUninstalled']
                changed = True

            if changed:
                modified_count += 1

        logger.info(f"Patched origin for {len(packages_to_patch)} package(s).")
        modified_packages_path = os.path.join(
            temp_dir, "packages.modified.xml")
        tree.write(modified_packages_path,
                   encoding='utf-8', xml_declaration=True)

        # Step 3: Clear warnings
        logger.info(
            f"--- Step 3/6: Preparing clean {os.path.basename(PACKAGES_WARNINGS_XML_PATH)}... ---")
        warnings_content = "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?><packages />"
        modified_warnings_path = os.path.join(
            temp_dir, "packages-warnings.modified.xml")
        with open(modified_warnings_path, 'w') as f:
            f.write(warnings_content)

        # Steps 4 & 5: Push, convert, replace, and restore
        _push_and_finalize(modified_packages_path, modified_warnings_path)

        # Step 6: Apply changes
        if apply_changes:
            logger.info("--- Step 6/6: Applying changes... ---")
            if full_reboot:
                logger.info("Performing a full system reboot...")
                adb.run_adb_command(['reboot'])
            else:
                logger.info("Performing a soft reboot...")
                adb.shell_su('killall system_server')
        else:
            logger.warning(
                "Patching complete. A reboot (or 'system soft-reboot') is required for changes to take effect.")


def _backup_remote_files():
    """Pulls and stores backups of the critical package files."""
    logger.info("--- Step 1/6: Backing up original package files... ---")
    for remote_path in [PACKAGES_XML_PATH, PACKAGES_WARNINGS_XML_PATH]:
        filename = os.path.basename(remote_path)
        backup_path = os.path.join(
            PACKAGES_BACKUP_DIR, f"{filename}.{int(time.time())}.abx")
        try:
            adb.pull_file_as_root(remote_path, backup_path)
            logger.info(f"Backed up '{filename}' to '{backup_path}'")
        except FileNotFoundError:
            logger.warning(f"'{filename}' not on device, skipping backup.")


def _push_and_finalize(local_packages_path, local_warnings_path):
    """Pushes, converts, moves, and restores permissions for the package files."""
    logger.info(
        "--- Step 4/6: Pushing modified files and converting to binary... ---")
    tmp_xml_packages = "/data/local/tmp/packages.modified.xml"
    tmp_xml_warnings = "/data/local/tmp/warnings.modified.xml"
    final_abx_packages = "/data/local/tmp/packages.final.abx"
    final_abx_warnings = "/data/local/tmp/warnings.final.abx"

    adb.transfer_and_clean(local_packages_path, tmp_xml_packages)
    adb.transfer_and_clean(local_warnings_path, tmp_xml_warnings)

    adb.shell_su(f"xml2abx {tmp_xml_packages} {final_abx_packages}")
    adb.shell_su(f"xml2abx {tmp_xml_warnings} {final_abx_warnings}")

    logger.info(
        "--- Step 5/6: Replacing files on device and restoring context... ---")
    adb.shell_su(f"mv {final_abx_packages} {PACKAGES_XML_PATH}")
    adb.shell_su(f"mv {final_abx_warnings} {PACKAGES_WARNINGS_XML_PATH}")
    adb.shell_su(
        f"chown system:system {PACKAGES_XML_PATH} {PACKAGES_WARNINGS_XML_PATH}")
    adb.shell_su(f"chmod 640 {PACKAGES_XML_PATH} {PACKAGES_WARNINGS_XML_PATH}")
    adb.shell_su(
        f"restorecon {PACKAGES_XML_PATH} {PACKAGES_WARNINGS_XML_PATH}")

    logger.info(
        f"{Colors.GREEN}Successfully patched package database.{Colors.ENDC}")
