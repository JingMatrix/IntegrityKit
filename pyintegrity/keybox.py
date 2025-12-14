# pyintegrity/keybox.py

import logging
import os
import requests
import shutil
import time
import tempfile
from cryptography import x509
import xml.etree.ElementTree as ET
import importlib.resources
from . import adb, utils
from .utils import Colors

logger = logging.getLogger(__name__)

# --- Constants ---
TEE_BASE_DIR = "/data/adb/tricky_store"
KEYBOX_CACHE_DIR = os.path.join(utils.get_cache_dir(), "keyboxes")
KEYBOX_BACKUP_DIR = os.path.join(KEYBOX_CACHE_DIR, "backup")
CRL_URL = 'https://android.googleapis.com/attestation/status'

# --- Main Parser Setup ---


def setup_keybox_parser(parser):
    """Adds arguments for the 'tee keybox' command."""
    os.makedirs(KEYBOX_CACHE_DIR, exist_ok=True)
    os.makedirs(KEYBOX_BACKUP_DIR, exist_ok=True)

    keybox_group = parser.add_mutually_exclusive_group(required=True)
    keybox_group.add_argument(
        '--list', action='store_true', help='List keyboxes on the device.')
    keybox_group.add_argument(
        '--list-local', action='store_true', help='List keyboxes in the local cache.')
    keybox_group.add_argument('--show', metavar='FILENAME',
                              help='Show parsed details of a keybox from the device.')
    keybox_group.add_argument('--verify', metavar='PATH',
                              help='Verify local keybox file(s) against Google CRL.')
    keybox_group.add_argument('--import', dest='import_path', metavar='PATH',
                              help='Verify and import valid keyboxes into the local cache.')
    keybox_group.add_argument(
        '--push', metavar='LOCAL_NAME', help='Push a keybox from local cache to device.')
    keybox_group.add_argument('--push-aosp', action='store_true',
                              help='Push the built-in AOSP keybox to the device.')
    parser.add_argument('--as', dest='as_filename',
                        help='Rename file during import or specify remote name for push.')
    parser.add_argument('--force', action='store_true',
                        help='Force overwrite during import if a file with the same name exists.')
    parser.set_defaults(func=handle_keybox)


# --- Keybox Command Handler and Helpers ---

def handle_keybox(args):
    """Main handler for all 'tee keybox' commands."""
    try:
        if args.list:
            _list_remote_keyboxes()
        elif args.list_local:
            _list_local_keyboxes()
        elif args.show:
            _show_remote_keybox(args.show)
        elif args.verify:
            if not x509:
                raise ImportError(
                    "Please install 'cryptography' (`pip install cryptography`) to verify keyboxes.")
            _verify_local_keyboxes(
                args.verify, import_valid=False, as_filename=None, force_overwrite=False)
        elif args.import_path:
            if not x509:
                raise ImportError(
                    "Please install 'cryptography' to import keyboxes.")
            _verify_local_keyboxes(args.import_path, import_valid=True, as_filename=args.as_filename,
                                   force_overwrite=args.force)
        elif args.push:
            _push_keybox(args.push, args.as_filename)
        elif args.push_aosp:
            _push_aosp_keybox(args.as_filename)
    except (adb.AdbError, RuntimeError, FileNotFoundError) as e:
        logger.error(f"Operation failed: {e}")


def _list_remote_keyboxes():
    """Lists all XML files in the TEESimulator directory on the device."""
    logger.info("Listing keyboxes on device...")
    output = adb.shell_su(f"find {TEE_BASE_DIR} -maxdepth 1 -name '*.xml'")
    files = [os.path.basename(f) for f in output.strip().splitlines()]

    if not files:
        logger.warning(
            f"No keybox (.xml) files found in {TEE_BASE_DIR} on the device.")
        return

    print(
        f"\n{Colors.HEADER}--- Keyboxes on Device ({TEE_BASE_DIR}) ---{Colors.ENDC}")
    for f in files:
        print(f"- {f}")
    print()


def _list_local_keyboxes():
    """Lists all XML files in the local cache."""
    logger.info(f"Listing keyboxes in local cache: {KEYBOX_CACHE_DIR}")
    files = [f for f in os.listdir(KEYBOX_CACHE_DIR) if f.endswith('.xml')]

    if not files:
        logger.warning(
            "No keyboxes found in the local cache. Use 'tee keybox --import' to add some.")
        return

    print(f"\n{Colors.HEADER}--- Keyboxes in Local Cache ---{Colors.ENDC}")
    for f in files:
        print(f"- {f}")
    print()


def _show_remote_keybox(filename):
    """Pulls and shows parsed info for a remote keybox."""
    logger.info(f"Fetching '{filename}' from device...")
    remote_path = f"{TEE_BASE_DIR}/{filename}"

    # Use a temporary directory to avoid file handle buffering issues
    with tempfile.TemporaryDirectory() as temp_dir:
        local_path = os.path.join(temp_dir, filename)

        # 1. Pull the file using our robust, root-aware function
        adb.pull_file_as_root(remote_path, local_path)

        # 2. Now, safely open and read the file AFTER it has been fully written
        with open(local_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if not content:
            raise RuntimeError(
                f"File '{filename}' is empty or could not be read.")

        _print_keybox_details(filename, content)


def _print_keybox_details(filename, xml_content):
    """Parses and prints keybox XML in a human-readable format."""
    print(f"\n{Colors.HEADER}--- Details for {filename} ---{Colors.ENDC}")
    try:
        root = ET.fromstring(xml_content)
        device_id = root.find('.//Keybox').get('DeviceID', 'Not Found')
        print(f"  {Colors.BOLD}Device ID:{Colors.ENDC} {device_id}")

        for key in root.findall('.//Key'):
            algo = key.get('algorithm', 'Unknown')
            print(
                f"\n  {Colors.CYAN}--- Key Algorithm: {algo.upper()} ---{Colors.ENDC}")

            certs = key.findall('.//Certificate')
            if not certs:
                print(
                    f"    {Colors.WARNING}No certificates found for this algorithm.{Colors.ENDC}")
                continue

            print(
                f"    {Colors.BOLD}Certificate Chain ({len(certs)} certs):{Colors.ENDC}")
            for i, cert_elem in enumerate(certs):
                try:
                    if not x509:
                        print(
                            f"      {i+1}. {Colors.GREY}(Install 'cryptography' for details){Colors.ENDC}")
                        continue

                    cert_text = "\n".join(
                        line.strip() for line in cert_elem.text.strip().split("\n"))
                    cert = x509.load_pem_x509_certificate(cert_text.encode())
                    subject = cert.subject.rfc4514_string()
                    serial = f"{cert.serial_number:x}"
                    print(
                        f"      {Colors.BOLD}{i+1}. Subject:{Colors.ENDC} {subject}")
                    print(
                        f"         {Colors.GREY}Serial: {serial}{Colors.ENDC}")
                except Exception:
                    print(
                        f"      {Colors.FAIL}{i+1}. Could not parse certificate.{Colors.ENDC}")

    except ET.ParseError:
        print(f"  {Colors.FAIL}Error: Not a valid XML file.{Colors.ENDC}")
    print()


def _fetch_crl():
    """Fetches and returns the Google CRL."""
    logger.info("Fetching latest Google Certificate Revocation List (CRL)...")
    try:
        response = requests.get(CRL_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to fetch CRL from Google: {e}")


def _verify_local_keyboxes(path, import_valid, as_filename, force_overwrite):
    """
    Verifies local keybox files by correctly parsing each key's leaf certificate,
    and optionally imports valid ones.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"The specified path does not exist: {path}")

    files_to_check = []
    if os.path.isdir(path):
        files_to_check = [os.path.join(path, f)
                          for f in os.listdir(path) if f.endswith('.xml')]
    elif os.path.isfile(path) and path.endswith('.xml'):
        files_to_check = [path]

    if not files_to_check:
        logger.warning(f"No .xml files found at the specified path.")
        return

    if as_filename and len(files_to_check) > 1:
        raise RuntimeError(
            "--as can only be used when importing a single file, not a directory.")

    crl = _fetch_crl()
    if not crl or "entries" not in crl:
        raise RuntimeError("Fetched CRL is invalid or empty.")

    summary = {'valid': 0, 'revoked': 0, 'invalid': 0, 'imported': 0}
    for file_path in files_to_check:
        filename = os.path.basename(file_path)
        is_valid_file = True

        leaf_serials = []
        human_readable_serials = []

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            # Iterate through each <Key> tag in the file
            for key_elem in root.findall('.//Key'):
                algo = key_elem.get('algorithm', 'unknown')

                # The leaf certificate is always the FIRST certificate in the chain
                leaf_cert_elem = key_elem.find(
                    './CertificateChain/Certificate')

                if leaf_cert_elem is None or not leaf_cert_elem.text:
                    logger.warning(
                        f"  - Key with algorithm '{algo}' in {filename} is missing its leaf certificate. This key cannot be verified.")
                    continue

                # Parse this specific leaf certificate
                cert_text = "\n".join(
                    line.strip() for line in leaf_cert_elem.text.strip().split("\n"))
                cert = x509.load_pem_x509_certificate(cert_text.encode())
                serial_num_str = f"{cert.serial_number:x}"

                leaf_serials.append(serial_num_str)
                human_readable_serials.append(
                    f"{algo.upper()}: {serial_num_str}")

            if not leaf_serials:
                is_valid_file = False
                logger.info(
                    f"\n{Colors.WARNING}{Colors.BOLD}[INVALID] {filename}{Colors.ENDC}\n  Reason: No valid leaf certificates could be extracted from any keys.")
                summary['invalid'] += 1

        except Exception as e:
            is_valid_file = False
            logger.info(
                f"\n{Colors.WARNING}{Colors.BOLD}[INVALID] {filename}{Colors.ENDC}\n  Reason: Failed to parse XML or a certificate inside it. Error: {e}")
            summary['invalid'] += 1

        if not is_valid_file:
            continue

        # Check all found leaf serials against the CRL
        is_revoked = any(sn in crl["entries"] for sn in leaf_serials)

        # Display results for this file
        serial_info = '\n'.join([f"  - {s}" for s in human_readable_serials])
        if is_revoked:
            logger.info(
                f"\n{Colors.FAIL}{Colors.BOLD}[REVOKED] {filename}{Colors.ENDC}\n{serial_info}")
            summary['revoked'] += 1
        else:
            logger.info(
                f"\n{Colors.GREEN}{Colors.BOLD}[VALID] {filename}{Colors.ENDC}\n{serial_info}")
            summary['valid'] += 1
            if import_valid:
                # --- NEW IMPORT NAMING LOGIC ---
                if as_filename:
                    target_filename = as_filename if as_filename.endswith(
                        '.xml') else f"{as_filename}.xml"
                else:
                    # Default name is the first found leaf serial number
                    target_filename = f"{leaf_serials[0]}.xml"

                dest_path = os.path.join(KEYBOX_CACHE_DIR, target_filename)

                if os.path.exists(dest_path) and not force_overwrite:
                    logger.warning(
                        f"  {Colors.WARNING}File '{target_filename}' already exists in cache. Use --force to overwrite. Skipping.{Colors.ENDC}")
                    continue

                shutil.copy2(file_path, dest_path)
                logger.info(
                    f"  {Colors.GREEN}Successfully imported to cache as '{target_filename}'.{Colors.ENDC}")
                summary['imported'] += 1

    print(f"\n{Colors.HEADER}--- Verification Summary ---{Colors.ENDC}")
    print(f"  {Colors.GREEN}Valid: {summary['valid']}{Colors.ENDC}")
    print(f"  {Colors.FAIL}Revoked: {summary['revoked']}{Colors.ENDC}")
    print(f"  {Colors.WARNING}Invalid: {summary['invalid']}{Colors.ENDC}")
    if import_valid:
        print(
            f"  {Colors.CYAN}Imported to Cache: {summary['imported']}{Colors.ENDC}")
    print()


def _push_keybox(local_name, remote_name):
    """Pushes a keybox from the local cache to the device, with backups."""
    local_path = os.path.join(KEYBOX_CACHE_DIR, local_name)
    if not os.path.exists(local_path):
        raise FileNotFoundError(
            f"Keybox '{local_name}' not found in local cache. Use 'tee keybox --import' first.")

    _backup_and_push(local_path, remote_name)
    logger.info(
        f"Successfully pushed '{local_name}' to device as '{remote_name}'.")


def _push_aosp_keybox(remote_name):
    """Pushes the built-in AOSP keybox to the device, with backups."""
    logger.info("Using built-in AOSP keybox.")
    try:
        # This is the correct, robust way to access package data
        with importlib.resources.path('pyintegrity.resources', 'keybox_aosp.xml') as aosp_path:
            _backup_and_push(aosp_path, remote_name)
            logger.info(
                f"Successfully pushed AOSP keybox to device as '{remote_name}'.")
    except FileNotFoundError:
        raise RuntimeError(
            "Could not find the packaged keybox_aosp.xml. Check your installation.")


def _backup_and_push(local_path_to_push, remote_name):
    """Handles the backup and push logic."""
    remote_path = f"{TEE_BASE_DIR}/{remote_name}"

    # Backup existing remote file
    try:
        backup_filename = f"{remote_name}.{int(time.time())}.bak"
        local_backup_path = os.path.join(KEYBOX_BACKUP_DIR, backup_filename)
        logger.info(
            f"Backing up remote '{remote_name}' to '{local_backup_path}'...")
        adb.pull_file_as_root(remote_path, local_backup_path)
    except adb.AdbError:
        logger.warning(
            f"Could not back up '{remote_name}'. It may not exist on the device.")

    # Pre-push verification
    with open(local_path_to_push, 'r') as f:
        content = f.read()
    try:
        ET.fromstring(content)
        logger.info(
            "Local keybox content is well-structured XML. Proceeding with push.")
    except ET.ParseError:
        raise RuntimeError(
            "The local keybox file is not valid XML. Aborting push.")

    # Push the new file
    adb.transfer_and_clean(local_path_to_push, remote_path)
