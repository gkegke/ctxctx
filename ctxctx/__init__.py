import logging

# Removed: from .config import CONFIG # No longer directly importing CONFIG here

# Configure a basic logger for the package
# This can be further configured in cli.py for user-facing output
# Changed: Use __name__ for module-specific logger
logger = logging.getLogger(__name__)
logger.addHandler(
    logging.NullHandler()
)  # Prevent "No handlers could be found for logger" warnings
logger.setLevel(logging.INFO)  # Default level

# Changed: __version__ is now a static string, independent of config.py's CONFIG
__version__ = "0.3.1"
