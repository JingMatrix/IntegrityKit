# pyintegrity/file_editor.py

import logging
import tempfile
import os
from . import adb

logger = logging.getLogger(__name__)


def modify_remote_text_file(remote_path, modification_function, *args, **kwargs):
    """
    A generic helper to safely modify a remote text file in-place.
    It pulls the file, runs a user-provided function to modify its content,
    and pushes it back.

    Args:
        remote_path (str): The full path to the file on the device.
        modification_function (callable): A function that accepts a string (file content)
                                          and returns a string (modified content).
        *args, **kwargs: Additional arguments to pass to the modification_function.

    Returns:
        bool: True on success, False on failure.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        local_path = os.path.join(temp_dir, os.path.basename(remote_path))

        try:
            # 1. Pull the file
            logger.info(f"Pulling remote file: {remote_path}")
            adb.pull_file_as_root(remote_path, local_path)

            with open(local_path, 'r', encoding='utf-8') as f:
                original_content = f.read()

            logger.debug("Original content:\n" + original_content)

        except adb.AdbError:
            logger.info(
                "Remote file does not exist. Starting with empty content.")
            original_content = ""

        # 2. Run the modification function
        logger.info("Modifying content locally...")
        modified_content = modification_function(
            original_content, *args, **kwargs)

        # 3. Pre-push verification and comparison
        if modified_content is None or modified_content == original_content:
            logger.info(
                "Content was not modified or modification failed. Aborting push.")
            return True  # Not an error, just no change

        logger.debug("Modified content:\n" + modified_content)

        # 4. Push the modified file back
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)

        logger.info(f"Pushing modified file back to {remote_path}")
        adb.transfer_and_clean(local_path, remote_path)

        return True
