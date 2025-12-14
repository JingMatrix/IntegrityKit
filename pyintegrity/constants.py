# pyintegrity/constants.py

import os
from . import utils

# --- TEE Simulator ---
TEE_BASE_DIR = "/data/adb/tricky_store"
KEYBOX_CACHE_DIR = os.path.join(utils.get_cache_dir(), "keyboxes")
KEYBOX_BACKUP_DIR = os.path.join(KEYBOX_CACHE_DIR, "backup")
SYNC_DIR = os.path.join(utils.get_cache_dir(), "device_configs")
TARGET_FILE_PATH = f"{TEE_BASE_DIR}/target.txt"
PATCH_FILE_PATH = f"{TEE_BASE_DIR}/security_patch.txt"

# --- PIF ---
PIF_JSON_PATH = "/data/adb/pif.json"
DROIDGUARD_PROCESS = "com.google.android.gms.unstable"
DEFAULT_CACHE_FILE = os.path.join(utils.get_cache_dir(), "profiles.json")

# --- Keybox Verification ---
CRL_URL = 'https://android.googleapis.com/attestation/status'


__all__ = [
    'TEE_BASE_DIR',
    'KEYBOX_CACHE_DIR',
    'KEYBOX_BACKUP_DIR',
    'SYNC_DIR',
    'TARGET_FILE_PATH',
    'PATCH_FILE_PATH',
    'PIF_JSON_PATH',
    'DROIDGUARD_PROCESS',
    'DEFAULT_CACHE_FILE',
    'CRL_URL',
]
