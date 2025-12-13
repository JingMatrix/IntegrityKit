#!/usr/bin/env python3

from pyintegrity import utils, main
import sys
import logging

# Manually parse for the debug flag before doing anything else.
args_list = sys.argv[1:]
debug_mode = '--debug' in args_list
if debug_mode:
    # Remove the flag so it's not processed again by argparse
    args_list.remove('--debug')

# Set up the logger with the correct level.
utils.setup_logging(debug=debug_mode)
log = logging.getLogger(__name__)

# The main execution is now delegated to the main module.
# We pass the cleaned arguments list to it.
if __name__ == "__main__":
    main.run(args_list)
