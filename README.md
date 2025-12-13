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
4.  [BetterKnownInstalled](https://github.com/Pixel-Props/BetterKnownInstalled)

## Usage

Ensure your Android device is connected to your computer with ADB debugging enabled and authorized. For more detailed logging on any command, add the global `--debug` flag.

### `activity` Command

The `activity reset` command automates the entire process of resetting the device's integrity activity state.

**To run the command (with a soft reboot):**
```sh
python integritykit.py activity reset
```

**To run the command with a full system reboot instead:**
```sh
python integritykit.py activity reset --reboot
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
Pixel 8 Pro               husky_beta                2025-11-05
Pixel 8                   shiba_beta                2025-11-05
Pixel Fold                felix_beta                2025-11-05
Pixel 7a                  lynx_beta                 2025-10-05
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

## Planned Features
The following features are planned for future releases:
*   **TEESimulator Management**: A `tee` subcommand to view, manage, and update the configuration files for TEESimulator (`keybox.xml`, `target.txt`, etc.) directly from the command line.
