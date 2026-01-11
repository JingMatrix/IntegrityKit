# pyintegrity/adb.py

import logging
import random
import subprocess
import time
import tempfile
import os

logger = logging.getLogger(__name__)


class AdbError(Exception):
    """Custom exception for ADB command failures."""
    pass


def check_adb_device():
    """
    Verifies that ADB is available and at least one device is connected
    and authorized.

    Raises:
        AdbError: If adb command is not found or no devices are connected.
    """
    logger.debug("Checking for ADB and connected devices...")
    try:
        result = subprocess.run(
            ['adb', 'devices'],
            capture_output=True,
            text=True,
            check=True
        )

        # The output of 'adb devices' includes a header line.
        # A successful connection will have more than just the header.
        lines = result.stdout.strip().splitlines()
        if len(lines) < 2:
            raise AdbError(
                "No devices found. Please connect a device and ensure it's authorized.")

        # Check if devices are in a ready state (not 'unauthorized' or 'offline')
        for line in lines[1:]:
            if 'device' in line and 'unauthorized' not in line and 'offline' not in line:
                logger.info(
                    f"Successfully connected to device: {line.split()[0]}")
                return

        raise AdbError(
            "A device is connected but may be offline or unauthorized.")

    except FileNotFoundError:
        raise AdbError(
            "ADB command not found. Please ensure ADB is installed and in your system's PATH.")
    except subprocess.CalledProcessError as e:
        raise AdbError(
            f"An error occurred while running 'adb devices': {e.stderr}")


def run_adb_command(args_list, check=True):
    """
    A wrapper to execute any ADB command. It automatically prepends 'adb'.

    Args:
        args_list (list): The command arguments as a list of strings (e.g., ['shell', 'ls']).
        check (bool): If True, raises AdbError on a non-zero exit code.

    Returns:
        subprocess.CompletedProcess: The result of the command execution.
    """
    command = ['adb'] + args_list
    logger.debug(f"Executing command: {' '.join(command)}")
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=check
        )
        # We no longer log stderr here, as successful commands can write to it.
        return result
    except FileNotFoundError:
        raise AdbError("ADB command not found. Is it in your PATH?")
    except subprocess.CalledProcessError as e:
        # Stderr is now correctly logged only on actual command failure.
        error_message = (
            f"ADB command failed with exit code {e.returncode}.\n"
            f"Command: {' '.join(e.cmd)}\n"
            f"Stderr: {e.stderr.strip()}"
        )
        raise AdbError(error_message)


def shell_su(command):
    """
    Executes a command on the device's shell with root privileges.

    Args:
        command (str): The command string to execute as root.

    Returns:
        str: The stdout from the command.
    """
    logger.debug(f"Executing root command: {command}")
    result = run_adb_command(['shell', f"su -c '{command}'"])
    return result.stdout.strip()


def push_file(local_path, remote_path):
    """
    Pushes a local file to a remote location on the device.

    Args:
        local_path (str): The path to the file on your computer.
        remote_path (str): The destination path on the Android device.
    """
    if not os.path.exists(local_path):
        raise AdbError(f"Local file not found: {local_path}")

    logger.info(f"Pushing '{local_path}' to '{remote_path}'...")
    run_adb_command(['push', local_path, remote_path])
    logger.debug("Push successful.")


def pull_file(remote_path, local_path):
    """
    Pulls a remote file from the device to a local path.

    Args:
        remote_path (str): The path to the file on the Android device.
        local_path (str): The destination path on your computer.
    """
    logger.info(f"Pulling '{remote_path}' to '{local_path}'...")
    run_adb_command(['pull', remote_path, local_path])
    logger.debug("Pull successful.")


def transfer_and_clean(local_file_path, final_destination):
    """
    Pushes a file to a temporary location, moves it to its final destination
    with root, and cleans up.

    Args:
        local_file_path (str): The path to the file on your computer.
        final_destination (str): The final, root-protected path on the device.
    """
    temp_device_path = f"/data/local/tmp/{os.path.basename(local_file_path)}"

    # 1. Push to temporary location
    push_file(local_file_path, temp_device_path)

    # 2. Move to final destination with root
    logger.info(f"Moving file to '{final_destination}' using root...")
    shell_su(f"mv {temp_device_path} {final_destination}")

    # 3. Set correct permissions (optional but good practice)
    shell_su(f"chmod 644 {final_destination}")
    logger.debug(f"Set permissions for {final_destination}")

    # The 'mv' command already cleaned up the temp file, no need to rm.
    logger.info("File transfer complete.")


def pull_file_as_root(remote_path, local_path):
    """
    Pulls a root-protected file from the device by staging it in a temporary,
    world-readable location first. This is the most reliable method.
    """
    logger.info(
        f"Pulling root-protected file '{remote_path}' to '{local_path}'...")
    try:
        # Generate a unique temporary path on the device
        temp_remote_filename = f"tmp_pull_{int(time.time())}_{random.randint(1000, 9999)}"
        temp_remote_path = f"/data/local/tmp/{temp_remote_filename}"

        shell_su(f"cp {remote_path} {temp_remote_path}")

        shell_su(f"chown shell:shell {temp_remote_path}")

        shell_su(f"chmod 644 {temp_remote_path}")

        run_adb_command(['pull', temp_remote_path, local_path])

        logger.debug("Root pull successful.")

    except AdbError as e:
        # Check if the error was due to the original file not existing
        if "No such file" in e.args[0]:
            raise FileNotFoundError(f"Remote file not found: {remote_path}")
        else:
            raise

    finally:
        # 4. Clean up the temporary file on the device, regardless of success
        if 'temp_remote_path' in locals():
            logger.debug(
                f"Cleaning up temporary file on device: {temp_remote_path}")
            # Use a non-checking command, as we want to clean up even if the pull failed
            run_adb_command(
                ['shell', 'rm', '-f', temp_remote_path], check=False)


def _pull_and_convert_xml(remote_path, temp_dir):
    """Helper to pull and convert a single XML file."""
    # (Identical to the one in packages_patch.py, kept here for module independence)
    filename = os.path.basename(remote_path)
    local_text_path = os.path.join(temp_dir, filename)
    temp_abx_name = f"tmp_{filename}_{random.randint(1000, 9999)}.abx"
    temp_abx_path = f"/data/local/tmp/{temp_abx_name}"
    temp_xml_path = temp_abx_path.replace('.abx', '.xml')
    try:
        shell_su(f"cp \"{remote_path}\" \"{temp_abx_path}\"")
        shell_su(f"abx2xml \"{temp_abx_path}\" \"{temp_xml_path}\"")
        pull_file_as_root(temp_xml_path, local_text_path)
        return local_text_path
    finally:
        shell_su(f"rm -f \"{temp_abx_path}\" \"{temp_xml_path}\"")
