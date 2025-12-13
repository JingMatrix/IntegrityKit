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

Ensure your Android device is connected to your computer with ADB debugging enabled and authorized.

The primary command currently available is `activity reset`. This command automates the entire process of resetting the device's integrity activity state.

**To run the command (with a soft reboot):**
```sh
python integritykit.py activity reset
```

**To run the command with a full system reboot instead:**
```sh
python integritykit.py activity reset --reboot
```

For more detailed logging, use the `--debug` flag:
```sh
python integritykit.py --debug activity reset
```

## Features

#### Current Features
*   **Activity Reset (`activity reset`)**:
    *   Completely reinstalls the Google Play Store package.
    *   Executes the `BetterKnownInstalled` module script to patch `packages.xml`, making all apps appear as if they were installed by the Play Store.
    *   Performs a fast, soft reboot (`killall system_server`) to apply the changes in seconds.

#### Planned Features
The following features are planned for future releases:
*   **PlayIntegrityFix Management**: A `pif` subcommand to fetch the latest device profiles, generate `pif.json`, and apply the configuration.
*   **TEESimulator Management**: A `tee` subcommand to view, manage, and update the configuration files for TEESimulator (`keybox.xml`, `target.txt`, etc.) directly from the command line.
