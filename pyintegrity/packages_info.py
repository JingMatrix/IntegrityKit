# pyintegrity/packages_info.py

import logging
import tempfile
import textwrap
import xml.etree.ElementTree as ET
from collections import Counter
from . import adb
from .constants import *
from .utils import Colors

logger = logging.getLogger(__name__)


PACKAGE_SOURCE_MAP = {
    '0': 'Unspecified',
    '1': 'Other',
    '2': 'Store',
    '3': 'Local File',
    '4': 'Downloaded File'
}


def setup_info_parser(parser):
    """Adds arguments for the 'packages info' command."""
    info_group = parser.add_mutually_exclusive_group(required=True)
    info_group.add_argument('--summary', action='store_true',
                            help='Show a high-level summary of the package database.')
    info_group.add_argument('--list-packages', action='store_true',
                            help='List packages with filtering options.')
    info_group.add_argument('--package', metavar='PACKAGE_NAME',
                            help='Show detailed installer info for a single package.')

    parser.add_argument(
        '--filter',
        choices=['user', 'system', 'sideloaded', 'no-installer'],
        help="Filter for --list-packages: user, system, sideloaded, no-installer."
    )
    parser.set_defaults(func=handle_info)


def handle_info(args):
    """Main handler for 'packages info' commands."""
    logger.info("--- Pulling and converting package files for analysis ---")
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            local_packages_xml, _ = adb._pull_and_convert_xml(
                PACKAGES_XML_PATH, temp_dir)
            tree = ET.parse(local_packages_xml)
            root = tree.getroot()

            if args.summary:
                _show_summary(root, temp_dir)
            elif args.list_packages:
                _list_packages(root, args.filter)
            elif args.package:
                _show_package_details(root, args.package)

        except FileNotFoundError:
            logger.error(
                f"{Colors.FAIL}Could not find {PACKAGES_XML_PATH} on the device.{Colors.ENDC}")
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during analysis: {e}", exc_info=True)


def _show_summary(root, temp_dir):
    """Displays the high-level summary."""
    version_info = root.find('version')
    print(f"\n{Colors.HEADER}--- Package Database Summary ---{Colors.ENDC}")
    if version_info is not None:
        print(
            f" {Colors.BOLD}SDK Version:{Colors.ENDC} {version_info.get('sdkVersion')}")
        print(
            f" {Colors.BOLD}Fingerprint:{Colors.ENDC} {version_info.get('buildFingerprint')}")

    all_packages = root.findall('package')
    installers = [p.get('installer', 'None') for p in all_packages]
    installer_counts = Counter(installers)

    print(f"\n {Colors.CYAN}Package Counts:{Colors.ENDC}")
    print(f"  - Total Packages: {len(all_packages)}")

    print(f"\n {Colors.CYAN}Installers Found:{Colors.ENDC}")
    for installer, count in installer_counts.most_common():
        color = Colors.GREEN if installer == 'com.android.vending' else Colors.WARNING
        print(f"  - {color}{installer}{Colors.ENDC}: {count} packages")

    try:
        local_warnings_xml, _ = adb._pull_and_convert_xml(
            PACKAGES_WARNINGS_XML_PATH, temp_dir)
        warnings_tree = ET.parse(local_warnings_xml)
        if len(warnings_tree.getroot()) > 0:
            print(
                f"\n{Colors.FAIL}--- Found {len(warnings_tree.getroot())} entries in packages-warnings.xml ---{Colors.ENDC}")
        else:
            print(
                f"\n{Colors.GREEN}--- packages-warnings.xml is clean (No warnings) ---{Colors.ENDC}")
    except FileNotFoundError:
        print(
            f"\n{Colors.GREEN}--- packages-warnings.xml not found (No warnings) ---{Colors.ENDC}")
    print()


def _list_packages(root, filter_type):
    """Lists packages with optional filtering."""
    all_packages = root.findall('package')

    if filter_type == 'user':
        packages = [p for p in all_packages if p.get(
            'codePath', '').startswith('/data/app')]
    elif filter_type == 'system':
        packages = [p for p in all_packages if not p.get(
            'codePath', '').startswith('/data/app')]
    elif filter_type == 'sideloaded':
        packages = [
            p for p in all_packages
            if p.get('codePath', '').startswith('/data/app')
            and p.get('packageSource') not in ['0', '2']
        ]
    elif filter_type == 'no-installer':
        packages = [p for p in all_packages if p.get('installer') is None]
    else:
        packages = all_packages

    print(
        f"\n{Colors.HEADER}--- Package List ({filter_type or 'all'}) ---{Colors.ENDC}")
    print(f"{Colors.BOLD}{'Package Name':<50} {'Installer':<30} {'Source'}{Colors.ENDC}")
    print("-" * 100)
    for pkg in packages:
        name = pkg.get('name', 'N/A')
        installer = pkg.get('installer', 'None')
        source_code = pkg.get('packageSource', 'N/A')

        source_str = PACKAGE_SOURCE_MAP.get(
            source_code, f"Unknown ({source_code})")
        installer_color = Colors.GREEN if installer == 'com.android.vending' else Colors.WARNING

        wrapped_name = textwrap.wrap(name, width=48)

        # Print first line with all data
        print(
            f"{wrapped_name[0]:<50} {installer_color}{installer:<30}{Colors.ENDC} {source_str}")

        # Print subsequent lines of the wrapped name, indented
        for line in wrapped_name[1:]:
            print(f"{line:<50}")


def _show_package_details(root, package_name):
    """Shows detailed info for a single package."""
    pkg = root.find(f".//package[@name='{package_name}']")
    if pkg is None:
        logger.error(f"Package '{package_name}' not found in the database.")
        return

    print(f"\n{Colors.HEADER}--- Details for {package_name} ---{Colors.ENDC}")
    print(f" {Colors.BOLD}{'Version Code:':<25}{Colors.ENDC} {pkg.get('version')}")
    print(f" {Colors.BOLD}{'User ID:':<25}{Colors.ENDC} {pkg.get('userId')}")
    print(f" {Colors.BOLD}{'Install Path:':<25}{Colors.ENDC} {pkg.get('codePath')}")

    print(f"\n {Colors.CYAN}Installer Information:{Colors.ENDC}")
    print(f"  - {'installer:':<23} {pkg.get('installer', 'Not Set')}")
    print(f"  - {'installInitiator:':<23} {pkg.get('installInitiator', 'Not Set')}")
    print(f"  - {'installerUid:':<23} {pkg.get('installerUid', 'Not Set')}")
    print(f"  - {'packageSource:':<23} {pkg.get('packageSource', 'Not Set')}")
    print(f"  - {'isOrphaned:':<23} {pkg.get('isOrphaned', 'Not Set')}")
    print(
        f"  - {'installOriginator:':<23} {pkg.get('installOriginator', 'Not Set')}")
