# pyintegrity/packages.py

from . import packages_info, packages_patch, packages_reinstall, packages_restore


def setup_packages_parser(parser):
    """
    Sets up the main 'packages' command and delegates its subcommands.
    """
    subparsers = parser.add_subparsers(
        dest='packages_command', required=True, help='Package database actions')

    # Delegate parser setup to each module
    packages_info.setup_info_parser(subparsers.add_parser(
        'info', help='Pull and display a summary of the package database.'))
    packages_patch.setup_patch_parser(subparsers.add_parser(
        'patch', help='Patch package installer origins in packages.xml.'))
    packages_reinstall.setup_reinstall_parser(subparsers.add_parser(
        'reinstall', help='Perform a clean reinstall of a package and patch its origin.'))
    packages_restore.setup_restore_parser(subparsers.add_parser(
        'restore', help='Restore packages.xml from a local backup.'))
