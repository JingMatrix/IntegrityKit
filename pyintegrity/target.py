# pyintegrity/target.py

import logging
import re
from . import adb, file_editor
from .constants import *
from .utils import Colors

logger = logging.getLogger(__name__)


def setup_target_parser(parser):
    """Adds arguments for the 'tee target' command."""
    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument('--show', action='store_true',
                              help='Show and interpret the current target.txt from the device.')
    target_group.add_argument(
        '--add', metavar='PACKAGE', help='Add or update a package in target.txt.')
    target_group.add_argument(
        '--remove', metavar='PACKAGE', help='Remove a package from target.txt.')
    parser.add_argument('--mode', choices=['auto', 'generate', 'patch'],
                        default='auto', help="Mode for the '--add' action.")
    parser.add_argument(
        '--keybox', help="Specify which keybox section to add the package to (e.g., aosp_keybox.xml).")
    parser.set_defaults(func=handle_target)


def handle_target(args):
    """Main handler for 'tee target' commands."""
    try:
        if args.show:
            _show_target_file()
        elif args.add:
            file_editor.modify_remote_text_file(
                TARGET_FILE_PATH, _add_package, args.add, args.mode, args.keybox)
            logger.info(
                f"Successfully added/updated '{args.add}' in {TARGET_FILE_PATH}.")
        elif args.remove:
            file_editor.modify_remote_text_file(
                TARGET_FILE_PATH, _remove_package, args.remove)
            logger.info(
                f"Successfully removed '{args.remove}' from {TARGET_FILE_PATH}.")
    except (adb.AdbError, RuntimeError) as e:
        logger.error(f"Operation failed: {e}")


def _show_target_file():
    """Pulls, interprets, and prints the target.txt file."""
    logger.info(f"Fetching and interpreting {TARGET_FILE_PATH} from device...")
    try:
        content = adb.shell_su(f"cat {TARGET_FILE_PATH}")
        if not content.strip():
            logger.warning(
                "target.txt is empty or does not exist on the device.")
            return

        print(f"\n{Colors.HEADER}--- Interpreted target.txt ---{Colors.ENDC}")
        current_keybox = "keybox.xml (default)"
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Keybox declaration
            if line.startswith('[') and line.endswith(']'):
                current_keybox = line[1:-1]
                print(
                    f"\n{Colors.CYAN}Keybox context switched to: {current_keybox}{Colors.ENDC}")
                continue

            # Package line
            match = re.match(r'^([\w\.\-]+)([!_?])?$', line)
            if match:
                pkg, mode_char = match.groups()
                mode_map = {'!': 'Generate', '?': 'Hack', None: 'Auto'}
                color_map = {'!': Colors.GREEN,
                             '?': Colors.WARNING, None: Colors.BLUE}
                mode_str = mode_map.get(mode_char, 'Auto')
                mode_color = color_map.get(mode_char, Colors.BLUE)

                print(f"- {Colors.BOLD}{pkg}{Colors.ENDC}")
                print(
                    f"  {Colors.GREY}Mode:{Colors.ENDC} {mode_color}{mode_str}{Colors.ENDC} | {Colors.GREY}Uses Keybox:{Colors.ENDC} {current_keybox}")

    except adb.AdbError:
        logger.warning("target.txt does not exist on the device.")


def _add_package(content, package_name, mode, keybox_name=None):
    """Modifies content to add/update a package under the correct keybox section."""
    # --- PRE-FLIGHT CHECK ---
    if keybox_name:
        logger.info(f"Checking for keybox '{keybox_name}' on device...")
        try:
            adb.shell_su(f"[ -f {TEE_BASE_DIR}/{keybox_name} ]")
        except adb.AdbError:
            raise RuntimeError(
                f"Target keybox '{keybox_name}' does not exist on the device. Aborting.")
        logger.info("Keybox found.")

    mode_map = {'generate': '!', 'patch': '?', 'auto': ''}
    new_line = f"{package_name}{mode_map[mode]}"

    # First, remove any existing instance of the package to avoid duplicates
    pattern_remove = re.compile(
        f"^{re.escape(package_name)}[!_?]?\n?", re.MULTILINE)
    content = pattern_remove.sub('', content)
    lines = content.splitlines()

    if not keybox_name:  # Add to the global section at the top
        lines.insert(0, new_line)
        return '\n'.join(lines)

    # Find the target keybox section to insert into
    section_header = f"[{keybox_name}]"
    insert_index = -1
    for i, line in enumerate(lines):
        if line.strip() == section_header:
            insert_index = i + 1
            break

    if insert_index != -1:
        # Section found, insert the line after the header
        lines.insert(insert_index, new_line)
    else:
        # Section not found, create it at the end
        if lines and lines[-1] != '':
            lines.append('')
        lines.append(section_header)
        lines.append(new_line)

    return '\n'.join(lines)


def _remove_package(content, package_name):
    """Modifies content to remove a package line."""
    pattern = re.compile(f"^{re.escape(package_name)}[!_?]?\n?", re.MULTILINE)

    if not pattern.search(content):
        logger.warning(
            f"Package '{package_name}' not found in the file. No changes made.")
        return None  # Return None to signal no change

    return pattern.sub('', content)
