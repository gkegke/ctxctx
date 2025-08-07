import logging
from .config import CONFIG

# Configure a basic logger for the package
# This can be further configured in cli.py for user-facing output
logger = logging.getLogger("ctxctx")
logger.addHandler(logging.NullHandler()) # Prevent "No handlers could be found for logger" warnings
logger.setLevel(logging.INFO) # Default level

__version__ = CONFIG.get('VERSION', '0.1.0')