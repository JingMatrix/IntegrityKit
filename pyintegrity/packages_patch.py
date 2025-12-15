# pyintegrity/packages_patch.py

import logging
import tempfile
import os
import xml.etree.ElementTree as ET
import time
from . import adb
from .constants import *
from .utils import Colors

logger = logging.getLogger(__name__)


def setup_patch_parser(parser):
    """Adds arguments for the 'packages patch' command with advanced filtering."""
    # Group for mutually exclusive targeting flags
    target_group = parser.add_mutually_exclusive_group()
    target_group.add_argument(
        '--package', help='Patch only a single specified package.')
    target_group.add_argument(
        '--filter',
        choices=['user', 'system', 'no-installer', 'all'],
        help='Filter which packages to patch. Default is smart-sideloaded.'
    )

    parser.add_argument('--origin', default='com.android.vending',
                        help='Installer origin to set. Use "" or 0 to remove origin info.')
    parser.add_argument('--source', default='0',
                        help='packageSource to set. 0=Unspecified, 2=Store. Default is 0.')
    parser.add_argument('--no-backup', action='store_true',
                        help='Skip creating a local backup.')
    parser.add_argument('--apply-changes', action='store_true',
                        help='Perform a soft reboot to apply changes.')
    parser.add_argument('--full-reboot', action='store_true',
                        help='Perform a full reboot if --apply-changes is used.')
    parser.set_defaults(func=handle_patch)


def handle_patch(args):
    """Main handler that calls the core worker function with parsed arguments."""
    try:
        _patch_packages(
            target_package=args.package,
            target_filter=args.filter,
            origin_package=args.origin,
            package_source=args.source,
            no_backup=args.no_backup,
            apply_changes=args.apply_changes,
            full_reboot=args.full_reboot
        )
    except (adb.AdbError, RuntimeError, FileNotFoundError) as e:
        logger.error(f"{Colors.FAIL}Operation failed: {e}{Colors.ENDC}")


def _patch_packages(target_package, target_filter, origin_package, package_source, no_backup, apply_changes, full_reboot):
    """
    The core reusable worker function for patching packages.xml.
    This function is independent of argparse.
    """
    logger.info("Starting package origin patching process...")

    adb.shell_su("command -v abx2xml && command -v xml2abx")
    if not no_backup:
        _backup_remote_files()

    with tempfile.TemporaryDirectory() as temp_dir:
        local_xml_path = adb._pull_and_convert_xml(PACKAGES_XML_PATH, temp_dir)
        tree = ET.parse(local_xml_path)
        root = tree.getroot()

        origin_uid = None
        if origin_package and origin_package not in ['0', '']:
            origin_pkg_elem = root.find(
                f".//package[@name='{origin_package}']")
            if not origin_pkg_elem:
                raise RuntimeError(
                    f"Specified origin package '{origin_package}' not found.")
            origin_uid = origin_pkg_elem.get('userId')
            logger.info(f"Using origin '{origin_package}' (uid: {origin_uid})")

        packages_to_patch = _get_packages_to_patch(
            root, target_package, target_filter)
        if not packages_to_patch:
            logger.warning(
                "No packages matched the criteria for patching. No changes will be made.")
            return

        logger.info(f"Found {len(packages_to_patch)} package(s) to patch.")

        modified_count = 0
        for pkg_element in packages_to_patch:
            if _modify_package_element(pkg_element, origin_uid, origin_package, package_source):
                modified_count += 1

        logger.info(f"Patched attributes for {modified_count} package(s).")

        if modified_count > 0:
            modified_packages_path = os.path.join(
                temp_dir, "packages.modified.xml")
            tree.write(modified_packages_path,
                       encoding='utf-8', xml_declaration=True)

            warnings_content = "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?><packages />"
            modified_warnings_path = os.path.join(
                temp_dir, "packages-warnings.modified.xml")
            with open(modified_warnings_path, 'w') as f:
                f.write(warnings_content)

            _push_and_finalize(modified_packages_path, modified_warnings_path)

            if apply_changes:
                reboot_cmd = ['reboot'] if full_reboot else [
                    'shell', 'su', '-c', 'killall system_server']
                logger.info(
                    f"Applying changes via {'full' if full_reboot else 'soft'} reboot...")
                adb.run_adb_command(reboot_cmd)
            else:
                logger.warning(
                    "Patching complete. A reboot is required for changes to take effect.")
        else:
            logger.info("No packages required modification.")


def _get_packages_to_patch(root, target_package, target_filter):
    """Uses filter arguments to return a list of package elements to modify."""
    all_packages = root.findall('package')
    if target_package:
        logger.info(f"Filtering by single package: {target_package}")
        pkg = root.find(f".//package[@name='{target_package}']")
        return [pkg] if pkg else []

    filter_map = {
        'user': lambda p: p.get('codePath', '').startswith('/data/app'),
        'system': lambda p: not p.get('codePath', '').startswith('/data/app'),
        'no-installer': lambda p: p.get('installer') is None,
        'all': lambda p: True,
        None: lambda p: p.get('codePath', '').startswith('/data/app') and p.get('packageSource') not in ['0', '2']
    }

    log_messages = {
        'user': "Filtering for ALL user-installed packages.",
        'system': "Filtering for ALL system packages.",
        'no-installer': "Filtering for packages with no installer attribute.",
        'all': "Targeting ALL packages.",
        None: "Filtering for sideloaded user apps (default behavior)."
    }

    logger.info(log_messages[target_filter])
    return [p for p in all_packages if filter_map[target_filter](p)]


def _modify_package_element(pkg_element, origin_uid, origin_package, package_source):
    """Modifies a single package element. Returns True if changed."""
    changed = False

    if origin_package in [None, '0', '']:
        attributes_to_remove = [
            'installer', 'installInitiator', 'installerUid', 'installOriginator']
        for key in attributes_to_remove:
            if key in pkg_element.attrib:
                del pkg_element.attrib[key]
                changed = True
        if pkg_element.get('packageSource') != '0':
            pkg_element.set('packageSource', '0')
            changed = True
    else:
        attributes_to_set = {
            'installer': origin_package, 'installInitiator': origin_package,
            'installerUid': origin_uid, 'packageSource': package_source
        }
        for key, value in attributes_to_set.items():
            if pkg_element.get(key) != value:
                pkg_element.set(key, value)
                changed = True

    if 'installOriginator' in pkg_element.attrib:
        del pkg_element.attrib['installOriginator']
        changed = True
    if pkg_element.get('isOrphaned') == 'true':
        del pkg_element.attrib['isOrphaned']
        changed = True
    if pkg_element.get('installInitiatorUninstalled') == 'true':
        del pkg_element.attrib['installInitiatorUninstalled']
        changed = True

    if changed:
        logger.debug(f"Patched: {pkg_element.get('name')}")

    return changed


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
