# IntegrityKit

A Python command-line toolkit designed to streamline the development and management of Google Play Integrity bypass techniques on rooted Android devices.

## Project Description

IntegrityKit is a command-line tool that combines a whole set of development utilities related to `Google Play Integrity`. It provides a clean, powerful interface to automate complex tasks that are often performed manually.

This tool is currently in active development.

## Prerequisites

To use IntegrityKit, you must have the following set up.

#### On Your Computer:
*   Python and some related packages.
*   Android Debug Bridge (`adb`) installed and available in your system's PATH.

#### On Your Rooted Android Device:
Your device must have the following modules installed and enabled (via Magisk, KernelSU, or APatch):

1.  [NeoZygisk](https://github.com/JingMatrix/NeoZygisk)
2.  [PlayIntegrityFix](https://github.com/JingMatrix/PlayIntegrityFix)
3.  [TEESimulator](https://github.com/JingMatrix/TEESimulator)

## Usage

Ensure your Android device is connected to your computer with ADB debugging enabled and authorized. For more detailed logging on any command, add the global `--debug` flag.

### `activity` Command

The `activity reset` command automates the entire process of resetting the device's integrity activity state.
```sh
python integritykit.py activity reset
```

### `pif` Command Suite

The `pif` command provides a full suite of tools to manage device profiles for PlayIntegrityFix using a local cache.

#### Recommended PIF Workflow

Here is the recommended, multi-step workflow for managing your `pif.json` profile:

**Step 1: Fetch and cache the latest device profiles**
This downloads all available profiles from Google's servers and saves them to a local JSON file.

```sh
python integritykit.py pif fetch
```

**Step 2: List the cached profiles to see your options**
Displays a colorized table of the profiles you just downloaded.
```sh
python integritykit.py pif list
```

Example output:
```
--- Device Profiles in Cache (/home/user/.config/integritykit/profiles.json) ---
Model                     Product ID                Security Patch
-------------------------------------------------------------------
Pixel 6                   oriole_beta               2025-09-05
Pixel 6 Pro               raven_beta                2025-09-05
Pixel 6a                  bluejay_beta              2025-09-05
Pixel 7                   panther_beta              2025-10-05
Pixel 7 Pro               cheetah_beta              2025-10-05
```

**Step 3: Choose and apply a profile to your device**
Select a profile from the list using its `Product ID`.
```sh
python integritykit.py pif apply --product lynx_beta
```
Or, to apply a random profile from the cache:
```sh
python integritykit.py pif apply --random
```

**Step 4: Force the changes to take effect**
This kills the necessary GMS process so it reloads your new `pif.json`.
```sh
python integritykit.py pif kill-gms
```

#### All-in-One `apply` Command
For convenience, you can combine fetching, applying, and killing the GMS process into a single command:
```sh
# Fetch latest profiles, apply a random one, and kill GMS all at once
python integritykit.py pif apply --random --update-cache --kill-gms
```

### `tee` Command Suite

This suite provides comprehensive tools to manage all `TEESimulator` configuration files.

#### Syncing Configs for Manual Editing (`tee sync`)
This is the recommended workflow if you prefer to edit `target.txt` and `security_patch.txt` manually.

```sh
# 1. Pull the current configs from your device to a local directory
python integritykit.py tee sync --pull

# The tool will print the location (e.g., ~/.config/integritykit/device_configs/).
# 2. Edit the files in that directory with your favorite text editor.

# 3. Push your changes back to the device
python integritykit.py tee sync --push
```

#### Keybox Management (`tee keybox`)
Manage hardware-backed keyboxes through a local cache.

**Recommended Keybox Workflow:**
```sh
# 1. Verify and import valid keyboxes from a local directory into the cache.
# The tool will check them against Google's CRL and name them by their serial number.
python integritykit.py tee keybox import /path/to/your/keyboxes/

# 2. List the keyboxes now available in your local cache
python integritykit.py tee keybox list --local

# 3. Push a keybox from your cache to the device.
# This command backs up the existing keybox.xml on the device before replacing it.
python integritykit.py tee keybox push <serial_number>.xml --as keybox.xml

# Or, push the built-in AOSP (software) keybox
python integritykit.py tee keybox push --aosp --as keybox_aosp.xml
```

#### In-Place Config Modification (`tee target` & `tee patch`)
Modify `target.txt` and `security_patch.txt` directly from the command line.

**`target.txt` Examples:**
```sh
# Add a rule for an app, placing it under the 'aosp_keybox.xml' section
# The tool will first check if 'aosp_keybox.xml' exists on the device.
python integritykit.py tee target --add org.matrix.demo --mode generate --keybox aosp_keybox.xml

# Remove the rule for an app
python integritykit.py tee target --remove org.matrix.demo
```

**`security_patch.txt` Examples:**
```sh
# Set a global value for the system patch level
python integritykit.py tee patch --set-global --key system --value 2025-10-05

# Set a package-specific override
python integritykit.py tee patch --set-package com.google.android.gms --key all --value today
```
