# ctxctx/cli.py
import argparse
import logging
import sys

from . import __version__ as app_version
from .app import CtxCtxApp
from .exceptions import CtxError  # Import the base custom exception

logger = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    """Parses command line arguments."""
    parser = argparse.ArgumentParser(
        prog="ctxctx",
        description=(
            "Intelligently select, format, and present relevant project "
            "files and directory structure \\n"
            "as context for Large Language Models (LLMs).\\n\\n"
            "Arguments can also be read from a file by prefixing the filename "
            "with '@'.\\nFor example: 'ctxctx @prompt_args'. Comments "
            "(lines starting with '#') \\n"
            "in the file are ignored."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
        fromfile_prefix_chars="@",
    )
    parser.add_argument(
        "queries",
        nargs="*",
        help=(
            "Files, folders, glob patterns, or specific content queries.\\n"
            "  - Path (e.g., 'src/main.py', 'docs/')\\n"
            "  - Glob (e.g., '*.py', 'src/**/*.js')\\n"
            "  - Line ranges (e.g., 'path/to/file.js:100,150' or "
            "'path/to/file.py:10,20:50,60')\\n"
            "  - Force include (e.g., 'force:node_modules/foo.js', 'force:*.log') "
            "to override ignore rules."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process queries and print output to console without " "writing files.",
    )
    parser.add_argument(
        "--profile",
        type=str,
        help="Name of a predefined context profile from 'prompt_profiles.yaml'.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging for more verbose output.",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        help="Path to a file where all logs should be written " "(at DEBUG level).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {app_version}",
        help="Show program's version number and exit.",
    )
    return parser.parse_args()


def main():
    """Main entry point for the command-line interface."""
    args = parse_arguments()
    try:
        app = CtxCtxApp(args)
        app.run()
    except CtxError as e:
        # Catch all custom application-specific errors
        logger.error(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        # Catch any truly unexpected system-level errors that weren't anticipated
        logger.exception(f"An unexpected fatal error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
