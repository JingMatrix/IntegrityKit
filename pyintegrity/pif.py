# pyintegrity/pif.py

import logging
import requests
import json
import random
import tempfile
import os
import re
from . import adb
from . import utils
from .utils import Colors

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

logger = logging.getLogger(__name__)

# --- Constants ---
DROIDGUARD_PROCESS = "com.google.android.gms.unstable"
DEFAULT_CACHE_FILE = os.path.join(utils.get_cache_dir(), "profiles.json")


# --- Cache-Centric Command Structure ---

def setup_pif_parser(parser):
    """Adds the full suite of 'pif' sub-commands."""
    pif_subparsers = parser.add_subparsers(
        dest='pif_command', required=True, help='PIF actions')

    # 1. pif fetch
    parser_fetch = pif_subparsers.add_parser(
        'fetch', help='Download device profiles from Google and save them to the cache.')
    parser_fetch.add_argument(
        '--output', help=f"Save cache to a custom file path (default: {DEFAULT_CACHE_FILE}).")
    # Note: --android-version and --type are not implemented yet, but are good future additions
    parser_fetch.set_defaults(func=handle_fetch)

    # 2. pif list
    parser_list = pif_subparsers.add_parser(
        'list', help='List all device profiles stored in the cache.')
    parser_list.add_argument(
        '--cache-file', help=f"Read from a custom cache file (default: {DEFAULT_CACHE_FILE}).")
    parser_list.set_defaults(func=handle_list)

    # 3. pif apply
    parser_apply = pif_subparsers.add_parser(
        'apply', help='Select a profile from the cache, generate pif.json, and push it to the device.')
    apply_group = parser_apply.add_mutually_exclusive_group(required=True)
    apply_group.add_argument(
        '--product', help='The product ID of the profile to apply (e.g., oriole_beta).')
    apply_group.add_argument('-r', '--random', action='store_true',
                             help='Select a random profile from the cache.')
    parser_apply.add_argument(
        '--cache-file', help=f"Use a custom cache file (default: {DEFAULT_CACHE_FILE}).")
    parser_apply.add_argument('--update-cache', action='store_true',
                              help='Run "fetch" to update the cache before applying.')
    parser_apply.add_argument('--kill-gms', action='store_true',
                              help='Kill the GMS process after applying the profile.')
    parser_apply.set_defaults(func=handle_apply)

    # 4. pif kill-gms
    parser_kill = pif_subparsers.add_parser(
        'kill-gms', help='Kill the GMS unstable process to force profile reload.')
    parser_kill.set_defaults(func=handle_kill_gms)


# --- Command Handler Functions ---

def handle_fetch(args):
    """Logic for the 'pif fetch' command."""
    cache_path = args.output or DEFAULT_CACHE_FILE
    logger.info(
        f"Starting to fetch profiles. They will be saved to: {cache_path}")

    try:
        devices = _get_latest_profiles()
        profiles = []
        total = len(devices)

        for i, dev in enumerate(devices):
            logger.info(
                f"Fetching fingerprint for {dev['model']} ({i+1}/{total})...")
            try:
                fingerprint, patch = _get_fingerprint_from_ota(dev['ota_url'])
                profiles.append({
                    "model": dev['model'],
                    "product": dev['product'],
                    "fingerprint": fingerprint,
                    "security_patch": patch
                })
            except RuntimeError as e:
                logger.warning(
                    f"Could not fetch metadata for {dev['product']}. Skipping. Reason: {e}")

        if not profiles:
            logger.error(
                "Failed to fetch any valid profiles. The cache will not be updated.")
            return

        _save_cache(cache_path, profiles)
        logger.info(
            f"Successfully saved {len(profiles)} device profiles to the cache.")

    except (requests.RequestException, RuntimeError) as e:
        logger.error(f"Failed during fetch operation: {e}")
    except Exception as e:
        is_debug = logging.getLogger().isEnabledFor(logging.DEBUG)
        logger.error(f"An unexpected error occurred: {e}", exc_info=is_debug)


def handle_list(args):
    """Logic for the 'pif list' command with colored output."""
    cache_path = args.cache_file or DEFAULT_CACHE_FILE
    profiles = _load_cache(cache_path)
    if not profiles:
        return  # _load_cache already printed an error

    print(
        f"\n{Colors.HEADER}--- Device Profiles in Cache ({cache_path}) ---{Colors.ENDC}")

    # Define headers with color and bolding
    model_header = f"{Colors.BOLD}{Colors.CYAN}{'Model':<25}{Colors.ENDC}"
    product_header = f"{Colors.BOLD}{Colors.CYAN}{'Product ID':<25}{Colors.ENDC}"
    patch_header = f"{Colors.BOLD}{Colors.CYAN}{'Security Patch':<15}{Colors.ENDC}"

    print(f"{model_header} {product_header} {patch_header}")
    print(f"{Colors.CYAN}{'-' * 67}{Colors.ENDC}")  # Separator line

    for p in profiles:
        # Print each row with standard colors
        model = f"{p['model']:<25}"
        product = f"{p['product']:<25}"
        patch = f"{p['security_patch']:<15}"
        print(f"{model} {product} {patch}")

    print("\n")


def handle_apply(args):
    """Logic for the 'pif apply' command."""
    if args.update_cache:
        logger.info(
            "--- --update-cache flag detected. Running fetch first... ---")
        handle_fetch(args)
        logger.info("--- Fetch complete. Proceeding with apply... ---")

    cache_path = args.cache_file or DEFAULT_CACHE_FILE
    profiles = _load_cache(cache_path)
    if not profiles:
        return

    selected_profile = None
    if args.random:
        selected_profile = random.choice(profiles)
        logger.info(f"Randomly selected profile: {selected_profile['model']}")
    else:  # args.product
        selected_profile = next(
            (p for p in profiles if p['product'] == args.product), None)
        if not selected_profile:
            logger.error(
                f"Product ID '{args.product}' not found in the cache. Run 'pif list' to see options.")
            return

    logger.info(
        f"Applying profile for: {selected_profile['model']} ({selected_profile['product']})")

    pif_data = {
        "FINGERPRINT": selected_profile['fingerprint'],
        "MANUFACTURER": "Google",
        "MODEL": selected_profile['model'],
        "SECURITY_PATCH": selected_profile['security_patch']
    }
    pif_json_str = json.dumps(pif_data, indent=2)
    logger.info("Generated pif.json content:\n" + pif_json_str)

    try:
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".json", encoding='utf-8') as tmp:
            tmp.write(pif_json_str)
            temp_file_path = tmp.name

        logger.info("Pushing pif.json to device...")
        adb.transfer_and_clean(temp_file_path, "/data/adb/pif.json")
        logger.info("pif.json successfully updated on device.")

        if args.kill_gms:
            logger.info(
                "--- --kill-gms flag detected. Killing GMS process... ---")
            _kill_gms_process()

    except adb.AdbError as e:
        logger.error(f"Failed to apply profile: {e}")
    finally:
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


def handle_kill_gms(args):
    """Logic for the 'pif kill-gms' command."""
    _kill_gms_process()


# --- Internal Helper Functions ---

def _get_cache_path(args):
    """Determines the correct cache path from args or default."""
    return getattr(args, 'cache_file', None) or args.output or DEFAULT_CACHE_FILE


def _load_cache(path):
    """Loads and returns profiles from a JSON cache file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Cache file not found at '{path}'.")
        logger.error(
            "Please run 'integritykit pif fetch' first to create the cache.")
        return None
    except json.JSONDecodeError:
        logger.error(f"Cache file at '{path}' is corrupted or not valid JSON.")
        return None


def _save_cache(path, data):
    """Saves profile data to a JSON cache file."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def _kill_gms_process():
    """Finds and kills the GMS unstable process."""
    logger.info(f"Attempting to kill '{DROIDGUARD_PROCESS}'...")
    try:
        pid_output = adb.shell_su(f"pidof {DROIDGUARD_PROCESS}")
        if not pid_output:
            logger.warning(
                f"Process '{DROIDGUARD_PROCESS}' not found. It might not be running.")
            return
        for pid in pid_output.split():
            logger.info(f"Killing process with PID: {pid}")
            adb.shell_su(f"kill -9 {pid}")
        logger.info(
            "Successfully sent kill signal. GMS will restart automatically.")
    except adb.AdbError as e:
        logger.error(f"Failed to kill GMS process: {e}")


# --- Web Scraping Logic ---

def _parse_subversion_link(href):
    # (This function is unchanged)
    type_priority = 1
    sub_version = 0
    if 'qpr' in href or re.search(r'/\d+\.\d+', href):
        type_priority = 3
        match = re.search(r'(qpr|\.)(\d+)', href)
        if match:
            sub_version = int(match.group(2))
    elif 'beta' in href:
        type_priority = 2
        match = re.search(r'beta(\d+)', href)
        if match:
            sub_version = int(match.group(1))
    return (type_priority, sub_version)


def _get_latest_profiles():
    # Step 1: Discover Major Version
    base_url = "https://developer.android.com"
    versions_url = f"{base_url}/about/versions"
    response = requests.get(versions_url, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    major_versions = [int(m.group(1)) for m in (re.search(r'/about/versions/(\d+)$', a['href'])
                                                for a in soup.find_all('a', href=re.compile(r'/about/versions/\d+$'))) if m]
    if not major_versions:
        raise RuntimeError("Could not find any major version links.")
    latest_major_version = max(major_versions)
    major_version_page_url = f"{base_url}/about/versions/{latest_major_version}"
    # Step 2: Discover Best Sub-version
    response = requests.get(major_version_page_url, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    sub_version_pages = [
        {'href': f"/about/versions/{latest_major_version}", 'key': (1, 0)}]
    sub_version_pages.extend({'href': a['href'], 'key': _parse_subversion_link(
        a['href'])} for a in soup.find_all('a', href=re.compile(f'/about/versions/{latest_major_version}/.*')))
    sub_version_pages.sort(key=lambda x: x['key'], reverse=True)
    best_page = sub_version_pages[0]
    # Step 3: Parse OTA Page
    ota_page_url = f"{base_url}{best_page['href']}/download-ota"
    logger.info(f"Fetching profiles from best build page: {ota_page_url}")
    response = requests.get(ota_page_url, timeout=15)
    if response.status_code != 200:
        raise RuntimeError(f"Failed to access OTA page at {ota_page_url}")
    page_content = response.text
    ota_url_pattern = r'https://[\w./-]+/ota/[\w./-]+_beta-ota-[\w.-]+\.zip'
    all_ota_urls = re.findall(ota_url_pattern, page_content)
    if not all_ota_urls:
        raise RuntimeError(
            "Failed to find any OTA download URLs in page source.")
    soup = BeautifulSoup(page_content, 'html.parser')
    devices, device_table = [], soup.find('table', id='images')
    if not device_table:
        raise RuntimeError("Could not find device table on OTA page.")
    for row in device_table.find_all('tr', id=True):
        product_id = row['id']
        model_name_tag = row.find('td')
        if not model_name_tag:
            continue
        model_name = model_name_tag.text.strip()
        ota_url = next(
            (url for url in all_ota_urls if f"/{product_id}_beta-ota-" in url), None)
        if ota_url:
            devices.append({"product": f"{product_id}_beta",
                           "model": model_name, "ota_url": ota_url})
    if not devices:
        raise RuntimeError("Failed to parse any device profiles.")
    return devices


def _get_fingerprint_from_ota(ota_url):
    # This is your corrected, working version
    headers = {
        'Range': 'bytes=0-2048',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    with requests.get(ota_url, headers=headers, stream=True, verify=False, timeout=20) as r:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        r.raise_for_status()
        metadata = r.content
    fingerprint, patch = None, None
    text_chunk = metadata.decode('utf-8', errors='ignore')
    for line in text_chunk.splitlines():
        if 'post-build=' in line and not fingerprint:
            fingerprint = line.split('post-build=')[-1].strip()
        if 'security-patch-level=' in line and not patch:
            patch = line.split('security-patch-level=')[-1].strip()
        if fingerprint and patch:
            break
    if not fingerprint or not patch:
        raise RuntimeError(
            "Could not extract fingerprint/patch from OTA metadata.")
    return fingerprint, patch
