# pyintegrity/patch.py

import logging
import re
from . import adb, file_editor
from .utils import Colors

logger = logging.getLogger(__name__)
PATCH_FILE_PATH = "/data/adb/tricky_store/security_patch.txt"


def setup_patch_parser(parser):
    """Adds arguments for the 'tee patch' command."""
    patch_group = parser.add_mutually_exclusive_group(required=True)
    patch_group.add_argument('--show', action='store_true',
                             help='Show and interpret the current security_patch.txt.')
    patch_group.add_argument(
        '--set-global', action='store_true', help='Set a global patch level value.')
    patch_group.add_argument('--set-package', metavar='PACKAGE',
                             help='Set a patch level value for a specific package.')
    patch_group.add_argument('--remove', metavar='PACKAGE',
                             help='Remove the entire config block for a specific package.')

    parser.add_argument(
        '--key', choices=['all', 'system', 'vendor', 'boot'], help="The patch key to set.")
    parser.add_argument(
        '--value', help="The patch value to set (e.g., 2025-11-05, today, no).")
    parser.set_defaults(func=handle_patch)


def handle_patch(args):
    """Main handler for 'tee patch' commands."""
    try:
        if args.show:
            _show_patch_file()
        elif args.set_global:
            if not args.key or not args.value:
                logger.error(
                    "--key and --value are required for --set-global.")
                return
            file_editor.modify_remote_text_file(
                PATCH_FILE_PATH, _set_value, None, args.key, args.value)
        elif args.set_package:
            if not args.key or not args.value:
                logger.error(
                    "--key and --value are required for --set-package.")
                return
            file_editor.modify_remote_text_file(
                PATCH_FILE_PATH, _set_value, args.set_package, args.key, args.value)
        elif args.remove:
            file_editor.modify_remote_text_file(
                PATCH_FILE_PATH, _remove_package_section, args.remove)

    except (adb.AdbError, RuntimeError) as e:
        logger.error(f"Operation failed: {e}")


def _show_patch_file():
    """Pulls, interprets, and prints the security_patch.txt file."""
    # (Implementation for this would be similar to _show_target_file, parsing sections and key-values)
    logger.info(f"Fetching {PATCH_FILE_PATH} from device...")
    try:
        content = adb.shell_su(f"cat {PATCH_FILE_PATH}")
        if not content.strip():
            logger.warning("security_patch.txt is empty or does not exist.")
            return
        print(
            f"\n{Colors.HEADER}--- Raw security_patch.txt ---{Colors.ENDC}\n{content}\n")
    except adb.AdbError:
        logger.warning("security_patch.txt does not exist on the device.")


def _set_value(content, package_name, key, value):
    """Adds or updates a key-value pair in the specified section."""
    lines = content.splitlines()
    new_line = f"{key}={value}"

    section_start = -1
    section_end = len(lines)

    if package_name:
        # Find the specific package section
        for i, line in enumerate(lines):
            if line.strip() == f"[{package_name}]":
                section_start = i
                break
        # Find the end of this section
        if section_start != -1:
            for i in range(section_start + 1, len(lines)):
                if lines[i].strip().startswith('['):
                    section_end = i
                    break
    else:
        # Global section is from the start until the first [section]
        section_start = 0
        for i, line in enumerate(lines):
            if line.strip().startswith('['):
                section_end = i
                break

    # Search within the section to see if the key already exists
    for i in range(section_start, section_end):
        if i < len(lines) and lines[i].strip().startswith(f"{key}="):
            logger.info(f"Found existing key '{key}' in section. Updating it.")
            lines[i] = new_line
            return '\n'.join(lines)

    # Key doesn't exist, we need to add it
    if package_name and section_start == -1:
        # Section doesn't exist, add it and the line
        logger.info(
            f"Package section '[{package_name}]' not found. Creating it.")
        if lines and lines[-1] != '':
            lines.append('')
        lines.append(f"[{package_name}]")
        lines.append(new_line)
    else:
        # Section exists, just insert the line
        lines.insert(section_end, new_line)

    return '\n'.join(lines)


def _remove_package_section(content, package_name):
    """Removes an entire package section from the content."""
    lines = content.splitlines()
    new_lines = []
    in_section_to_remove = False

    for line in lines:
        stripped_line = line.strip()
        if stripped_line == f"[{package_name}]":
            in_section_to_remove = True
            continue
        elif stripped_line.startswith('[') and stripped_line.endswith(']'):
            in_section_to_remove = False

        if not in_section_to_remove:
            new_lines.append(line)

    return '\n'.join(new_lines)
