import logging

from .config import CONFIG

# Configure a basic logger for the package
# This can be further configured in cli.py for user-facing output
# Changed: Use __name__ for module-specific logger
logger = logging.getLogger(__name__)
logger.addHandler(
    logging.NullHandler()
)  # Prevent "No handlers could be found for logger" warnings
logger.setLevel(logging.INFO)  # Default level

__version__ = CONFIG.get("VERSION", "0.3.1")
