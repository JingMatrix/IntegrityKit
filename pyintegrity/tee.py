# pyintegrity/tee.py

from . import keybox, target, patch, sync


def setup_tee_parser(parser):
    """
    Sets up the main 'tee' command and delegates its subcommands
    to their respective modules.
    """
    tee_subparsers = parser.add_subparsers(
        dest='tee_command', required=True, help='TEESimulator actions')

    # Delegate parser setup to each module
    keybox.setup_keybox_parser(tee_subparsers.add_parser(
        'keybox', help='Manage TEESimulator keyboxes.'))
    target.setup_target_parser(tee_subparsers.add_parser(
        'target', help='Manage the target.txt file.'))
    patch.setup_patch_parser(tee_subparsers.add_parser(
        'patch', help='Manage the security_patch.txt file.'))
    sync.setup_sync_parser(tee_subparsers.add_parser(
        'sync', help='Sync config files between device and local machine.'))
