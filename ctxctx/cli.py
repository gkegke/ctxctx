# ctxctx/cli.py
import argparse
import json
import logging
import os
import sys
from typing import Any, Dict, List, Set

from .config import CONFIG, apply_profile_config, load_profile_config
from .content import get_file_content
from .exceptions import ConfigurationError, FileReadError, TooManyMatchesError
from .ignore import IgnoreManager
from .logging_utils import setup_main_logging
from .output import format_file_content_json, format_file_content_markdown
from .search import find_matches
from .tree import generate_tree_string

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
            "  - Force include (e.g., '!node_modules/foo.js', '!*.log') "
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
        version=f"%(prog)s {CONFIG['VERSION']}",
        help="Show program's version number and exit.",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    setup_main_logging(args.debug, args.log_file)

    CONFIG["ROOT"] = os.path.abspath(CONFIG["ROOT"])
    logger.debug(f"Root directory set to: {CONFIG['ROOT']}")

    if args.profile:
        try:
            try:
                import yaml  # type: ignore # noqa: F401
            except ImportError:
                raise ConfigurationError(
                    "PyYAML is not installed. Cannot use external profiles. "
                    "Install with: pip install 'ctx[yaml]'"
                )

            profile_data = load_profile_config(args.profile, CONFIG["ROOT"])
            apply_profile_config(CONFIG, profile_data)
            logger.info(f"Active Profile: {args.profile}")

            if "queries" in profile_data:
                args.queries.extend(profile_data["queries"])

        except ConfigurationError as e:
            logger.error(f"Error loading profile: {e}")
            sys.exit(1)

    force_include_patterns = []
    for q in args.queries:
        if q.startswith("!"):
            force_include_patterns.append(q[1:].split(":", 1)[0])

    ignore_manager = IgnoreManager(CONFIG, CONFIG["ROOT"], force_include_patterns)
    is_ignored_func = ignore_manager.is_ignored

    logger.info(f"--- LLM Context Builder (v{CONFIG['VERSION']}) ---")
    logger.info(f"Root Directory: {CONFIG['ROOT']}")
    logger.info(f"Tree Max Depth: {CONFIG['TREE_MAX_DEPTH']}")
    logger.info(f"Search Max Depth: {CONFIG['SEARCH_MAX_DEPTH']}")
    logger.info(f"Max Matches Per Query: {CONFIG['MAX_MATCHES_PER_QUERY']}")

    all_ignore_patterns_display = sorted(
        list(ignore_manager._explicit_ignore_set) + ignore_manager._substring_ignore_patterns
    )
    logger.info(f"Combined Ignore Patterns ({len(all_ignore_patterns_display)}):\n")
    for p in all_ignore_patterns_display[:10]:
        logger.info(f"  - {p}")
    if len(all_ignore_patterns_display) > 10:
        logger.info(f"  ...and {len(all_ignore_patterns_display) - 10} more.")

    if ignore_manager._force_include_patterns:
        logger.info(
            f"Force Include Patterns " f"({len(ignore_manager._force_include_patterns)}):\n"
        )
        for p in sorted(ignore_manager._force_include_patterns)[:10]:
            logger.info(f"  - !{p}")
        if len(ignore_manager._force_include_patterns) > 10:
            logger.info(f"  ...and {len(ignore_manager._force_include_patterns) - 10} " "more.")

    if CONFIG["ADDITIONAL_IGNORE_FILENAMES"]:
        logger.info(
            f"Additional Ignore Files: " f"{', '.join(CONFIG['ADDITIONAL_IGNORE_FILENAMES'])}"
        )

    if args.dry_run:
        logger.info("Mode: DRY RUN (no files will be written)")
    logger.info("-" * 20)

    logger.info("Generating directory tree...")
    tree_output = generate_tree_string(
        CONFIG["ROOT"],
        is_ignored_func,
        CONFIG["TREE_MAX_DEPTH"],
        CONFIG["TREE_EXCLUDE_EMPTY_DIRS"],
        current_depth=0,
    )
    if not tree_output:
        logger.warning(
            "No directory tree generated (possibly due to ignore rules " "or empty root).\n"
        )

    logger.info("Processing file queries...")
    all_matched_files_data: List[Dict[str, Any]] = []
    unique_matched_paths: Set[str] = set()

    if not args.queries:
        logger.info("No specific file queries provided. " "Including directory tree only.\n")
    else:
        consolidated_matches: Dict[str, Dict[str, Any]] = {}

        for query in args.queries:
            logger.debug(f"Processing query: '{query}'")
            try:
                matches = find_matches(
                    query,
                    CONFIG["ROOT"],
                    is_ignored_func,
                    CONFIG["SEARCH_MAX_DEPTH"],
                )

                if not matches:
                    logger.warning(f"⚠️ No non-ignored matches found for: '{query}'")
                    continue

                if len(matches) > CONFIG["MAX_MATCHES_PER_QUERY"]:
                    example_paths = [os.path.relpath(m["path"], CONFIG["ROOT"]) for m in matches]
                    raise TooManyMatchesError(
                        query,
                        len(matches),
                        CONFIG["MAX_MATCHES_PER_QUERY"],
                        example_paths,
                    )

                logger.info(f"✅ Using {len(matches)} non-ignored match(es) for " f"'{query}'")
                for match in matches:
                    path = match["path"]
                    current_line_ranges = match.get("line_ranges", [])

                    if path not in consolidated_matches:
                        consolidated_matches[path] = {
                            "path": path,
                            "line_ranges": current_line_ranges,
                        }
                    else:
                        existing_line_ranges = consolidated_matches[path].get("line_ranges", [])
                        combined_ranges = sorted(
                            list(set(existing_line_ranges + current_line_ranges))
                        )
                        consolidated_matches[path]["line_ranges"] = combined_ranges
                    unique_matched_paths.add(path)

            except TooManyMatchesError as e:
                logger.error(f"❌ {e}")
                sys.exit(1)
            except Exception:
                logger.exception(f"An unexpected error occurred processing query '{query}'")
                sys.exit(1)

        all_matched_files_data = list(consolidated_matches.values())

    output_markdown_lines: List[str] = []
    output_json_data: Dict[str, Any] = {
        "directory_structure": tree_output,
        "files": [],
    }

    output_markdown_lines.append(f"# Project Structure for {os.path.basename(CONFIG['ROOT'])}\n")
    if args.profile:
        output_markdown_lines.append(f"**Profile:** `{args.profile}`\n")
    output_markdown_lines.append("```\n[DIRECTORY_STRUCTURE]\n")
    output_markdown_lines.append(tree_output)
    output_markdown_lines.append("```\n")

    if all_matched_files_data:
        output_markdown_lines.append("\n# Included File Contents\n")
        all_matched_files_data.sort(key=lambda x: x["path"])
        for file_data in all_matched_files_data:
            try:
                output_markdown_lines.append(
                    format_file_content_markdown(file_data, CONFIG["ROOT"], get_file_content)
                )
                output_json_data["files"].append(
                    format_file_content_json(file_data, CONFIG["ROOT"], get_file_content)
                )
            except FileReadError as e:
                logger.warning(f"Skipping file '{file_data['path']}' due to read " f"error: {e}")
                output_markdown_lines.append(
                    f"**[FILE: /{os.path.relpath(file_data['path'], CONFIG['ROOT'])}]**"
                    f"\n```\n// Error reading file: {e}\n```"
                )
            except Exception:
                logger.exception(
                    f"An unexpected error occurred formatting file " f"'{file_data['path']}'"
                )
                sys.exit(1)
    else:
        output_markdown_lines.append("\n_No specific files included based on queries._\n")

    logger.info(f"\n--- Matched Files Summary ({len(unique_matched_paths)} " "unique files) ---")
    if unique_matched_paths:
        for file_path in sorted(list(unique_matched_paths)):
            logger.info(f"  - {os.path.relpath(file_path, CONFIG['ROOT'])}")
    else:
        logger.info("  No files included based on queries.")
    logger.info("-" * 20)

    if args.dry_run:
        logger.info("\n--- Dry Run Output Preview (Markdown) ---")
        print("\n\n".join(output_markdown_lines))
        logger.info("\n--- Dry Run Output Preview (JSON) ---")
        print(json.dumps(output_json_data, indent=2, ensure_ascii=False))
        logger.info("\n🎯 Dry run complete. No files were written.")
    else:
        success = True
        for output_format in CONFIG["OUTPUT_FORMATS"]:
            output_filepath = f"{CONFIG['OUTPUT_FILE_BASE_NAME']}.{output_format}"
            try:
                if output_format == "md":
                    with open(output_filepath, "w", encoding="utf-8") as f:
                        f.write("\n\n".join(output_markdown_lines))
                elif output_format == "json":
                    with open(output_filepath, "w", encoding="utf-8") as f:
                        json.dump(output_json_data, f, indent=2, ensure_ascii=False)
                logger.info(
                    f"🎯 Wrote output in '{output_format}' format to " f"'{output_filepath}'."
                )
            except IOError as e:
                logger.error(f"Error: Could not write to output file " f"'{output_filepath}': {e}")
                success = False
        if success:
            logger.info(
                f"Completed. Total {len(unique_matched_paths)} file(s) "
                "and directory tree processed."
            )
            logger.info(
                f"Total chars: {len(''.join(output_markdown_lines))} "
                f"(Markdown), "
                f"{len(json.dumps(output_json_data, ensure_ascii=False))} "
                f"(JSON)"
            )


if __name__ == "__main__":
    main()
