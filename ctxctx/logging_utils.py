# ctxctx/logging_utils.py
import logging
import sys
from typing import Optional


def setup_main_logging(debug_mode: bool, log_file: Optional[str] = None):
    """Centralized logging configuration for the ctxctx package.
    Configures a StreamHandler for console output and optionally a FileHandler.
    """
    main_logger = logging.getLogger("ctxctx")

    for handler in main_logger.handlers[:]:
        main_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s: %(message)s")
    console_handler.setFormatter(formatter)

    console_handler.setLevel(logging.INFO)
    main_logger.addHandler(console_handler)

    if debug_mode:
        main_logger.setLevel(logging.DEBUG)
    else:
        main_logger.setLevel(logging.INFO)

    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - "
                "%(lineno)d: %(message)s"
            )
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(logging.DEBUG)
            main_logger.addHandler(file_handler)
            main_logger.info(f"Logging also to file: {log_file}")
        except IOError as e:
            main_logger.error(f"Could not open log file '{log_file}': {e}")
