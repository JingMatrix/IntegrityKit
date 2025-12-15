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

### `packages` Command Suite

This is the primary suite of tools for inspecting and modifying the Android package manager database.

#### Inspecting the Database (`packages info`)

Before making changes, you can safely inspect the current state of your device's apps.

```sh
# Show a high-level summary of installers on your device
python integritykit.py packages info --summary

# List all user-installed apps that were NOT installed by the Play Store
python integritykit.py packages info --list-packages --filter sideloaded

# Get detailed installer information for a specific app
python integritykit.py packages info --package com.example.app
```

#### Patching Installer Origin (`packages patch`)

This command modifies `packages.xml` to change how apps appear to be installed.

**Recommended Usage (Smart Patching):**
By default, this command intelligently finds and patches only user-installed apps that are not already correctly marked as being from the Play Store.
```sh
# Patch all sideloaded apps to appear as if installed by the Play Store
python integritykit.py packages patch

# After patching, apply the changes with a fast, soft reboot
python integritykit.py system soft-reboot
```

**Power-User Options:**
```sh
# Patch a SINGLE package, specifying a different origin (e.g., Aurora Store)
python integritykit.py packages patch --package com.example.app --origin com.aurora.store

# Force a patch of ALL packages on the system (including system apps)
python integritykit.py packages patch --all

# Combine patching with an immediate soft reboot
python integritykit.py packages patch --apply-changes
```

#### Reinstalling Packages (`packages reinstall`)

This command performs a clean reinstallation of an app and automatically patches its installer origin to the Play Store.

```sh
python integritykit.py packages reinstall com.example.app
```

#### Restoring Backups (`packages restore`)

The `patch` command automatically creates local backups. You can use these to revert changes if needed.

```sh
# 1. List available backups
python integritykit.py packages restore --list

# 2. Restore a specific backup from the list (with confirmation)
python integritykit.py packages restore 1

# 3. Apply the restored database with a soft reboot
python integritykit.py system soft-reboot
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

### `system` Command Suite

Provides general system-level utilities.

```sh
# Perform a fast, soft reboot (restarts the Android UI)
python integritykit.py system soft-reboot

# Change the device serial number to a new random value
python integritykit.py system serial

# Set a specific serial number
python integritykit.py system serial --set <YOUR_SERIAL>
```
