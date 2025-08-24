# ctxctx/logging_utils.py
import logging
import sys
from typing import IO, Optional


def setup_main_logging(debug_mode: bool, log_file: Optional[str] = None, stream: IO = sys.stdout):
    """Centralized logging configuration for the ctxctx package.
    Configures a StreamHandler for console output and optionally a FileHandler.

    :param debug_mode: If True, sets log level to DEBUG.
    :param log_file: Optional path to a file for logging.
    :param stream: The stream to use for the console handler (e.g., sys.stdout or sys.stderr).
    """
    main_logger = logging.getLogger("ctxctx")

    # Clear any existing handlers to prevent duplicate logging
    for handler in main_logger.handlers[:]:
        main_logger.removeHandler(handler)

    # Console handler that writes to the specified stream
    console_handler = logging.StreamHandler(stream)

    formatter = logging.Formatter("%(levelname)s: %(message)s")
    console_handler.setFormatter(formatter)

    # Set console level based on debug_mode, but logger level will be the final gatekeeper
    console_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    main_logger.addHandler(console_handler)

    # Set the main logger's level
    if debug_mode:
        main_logger.setLevel(logging.DEBUG)
    else:
        main_logger.setLevel(logging.INFO)

    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            # More verbose formatter for the log file
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - "
                "%(lineno)d: %(message)s"
            )
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(logging.DEBUG)  # Always log at DEBUG level to file
            main_logger.addHandler(file_handler)
            main_logger.info(f"Logging also to file: {log_file}")
        except IOError as e:
            main_logger.error(f"Could not open log file '{log_file}': {e}")
