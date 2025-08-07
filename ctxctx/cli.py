# ctxctx/cli.py
import os
import sys
import argparse
import json
import logging
from typing import List, Dict, Any, Tuple, Set

from .config import CONFIG, apply_profile_config, load_profile_config
from .ignore import IgnoreManager
from .exceptions import ConfigurationError, FileReadError, TooManyMatchesError, CtxError
from .tree import generate_tree_string
from .search import find_matches
from .content import get_file_content 
from .output import format_file_content_markdown, format_file_content_json # Assuming these are in output.py

# Set up logging for CLI output
logger = logging.getLogger("ctx")
for handler in logger.handlers[:]:
    logger.removeHandler(handler)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(levelname)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

def parse_arguments() -> argparse.Namespace:
    """Parses command line arguments."""
    parser = argparse.ArgumentParser(
        prog="ctx",
        description="Intelligently select, format, and present relevant project files and directory structure "
                    "as context for Large Language Models (LLMs).\\n\\n"
                    "Arguments can also be read from a file by prefixing the filename with '@'.\\n"
                    "For example: 'ctx @prompt_args'. Comments (lines starting with '#') "
                    "in the file are ignored.",
        formatter_class=argparse.RawTextHelpFormatter,
        fromfile_prefix_chars='@'
    )
    parser.add_argument(
        "queries",
        nargs="*",
        help="Files, folders, glob patterns, or specific content queries.\\n"
             "  - Path (e.g., 'src/main.py', 'docs/')\\n"
             "  - Glob (e.g., '*.py', 'src/**/*.js')\\n"
             "  - Line ranges (e.g., 'path/to/file.js:100,150' or 'path/to/file.py:10,20:50,60')"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process queries and print output to console without writing files."
    )
    parser.add_argument(
        "--profile",
        type=str,
        help="Name of a predefined context profile from 'prompt_profiles.yaml'."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging for more verbose output."
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {CONFIG['VERSION']}",
        help="Show program's version number and exit."
    )
    return parser.parse_args()

def main():
    args = parse_arguments()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    CONFIG['ROOT'] = os.path.abspath(CONFIG['ROOT'])
    logger.debug(f"Root directory set to: {CONFIG['ROOT']}")

    if args.profile:
        try:
            try:
                import yaml # noqa: F401
            except ImportError:
                raise ConfigurationError("PyYAML is not installed. Cannot use external profiles. Install with: pip install 'ctx[yaml]'")

            profile_data = load_profile_config(args.profile, CONFIG['ROOT'])
            apply_profile_config(CONFIG, profile_data)
            logger.info(f"Active Profile: {args.profile}")

            if 'queries' in profile_data:
                args.queries.extend(profile_data['queries'])

        except ConfigurationError as e:
            logger.error(f"Error loading profile: {e}")
            sys.exit(1)

    ignore_manager = IgnoreManager(CONFIG, CONFIG['ROOT'])
    is_ignored_func = ignore_manager.is_ignored

    logger.info(f"--- LLM Context Builder (v{CONFIG['VERSION']}) ---")
    logger.info(f"Root Directory: {CONFIG['ROOT']}")
    logger.info(f"Tree Max Depth: {CONFIG['TREE_MAX_DEPTH']}")
    logger.info(f"Search Max Depth: {CONFIG['SEARCH_MAX_DEPTH']}")
    logger.info(f"Max Matches Per Query: {CONFIG['MAX_MATCHES_PER_QUERY']}")

    all_ignore_patterns_display = sorted(list(ignore_manager._explicit_ignore_set) + ignore_manager._substring_ignore_patterns)
    logger.info(f"Combined Ignore Patterns ({len(all_ignore_patterns_display)}):\n") # Added newline for better formatting
    for p in all_ignore_patterns_display[:10]:
        logger.info(f"  - {p}")
    if len(all_ignore_patterns_display) > 10:
        logger.info(f"  ...and {len(all_ignore_patterns_display) - 10} more.")

    if CONFIG['ADDITIONAL_IGNORE_FILENAMES']:
        logger.info(f"Additional Ignore Files: {', '.join(CONFIG['ADDITIONAL_IGNORE_FILENAMES'])}")

    if args.dry_run:
        logger.info("Mode: DRY RUN (no files will be written)")
    logger.info("-" * 20)

    logger.info("\nGenerating directory tree...")
    tree_output = generate_tree_string(
        CONFIG['ROOT'],
        is_ignored_func,
        CONFIG['TREE_MAX_DEPTH'],
        CONFIG['TREE_EXCLUDE_EMPTY_DIRS'],
        current_depth=0
    )
    if not tree_output:
        logger.warning("No directory tree generated (possibly due to ignore rules or empty root).\\n")

    logger.info("\nProcessing file queries...")
    all_matched_files_data: List[Dict[str, Any]] = []
    unique_matched_paths: Set[str] = set()

    if not args.queries:
        logger.info("No specific file queries provided. Including directory tree only.\\n")
    else:
        # Dictionary to temporarily store and consolidate matches for unique paths
        consolidated_matches: Dict[str, Dict[str, Any]] = {}

        for query in args.queries:
            logger.debug(f"Processing query: '{query}'")
            try:
                matches = find_matches(query, CONFIG['ROOT'], is_ignored_func, CONFIG['SEARCH_MAX_DEPTH'])

                # Filter out ignored matches (should largely be handled by find_matches now, but double-check)
                matches = [m for m in matches if not is_ignored_func(m['path'])]

                if not matches:
                    logger.warning(f"⚠️ No non-ignored matches found for: '{query}'")
                    continue

                if len(matches) > CONFIG['MAX_MATCHES_PER_QUERY']:
                    example_paths = [os.path.relpath(m['path'], CONFIG['ROOT']) for m in matches]
                    raise TooManyMatchesError(query, len(matches), CONFIG['MAX_MATCHES_PER_QUERY'], example_paths)

                logger.info(f"✅ Using {len(matches)} non-ignored match(es) for '{query}'")
                for match in matches:
                    path = match['path']
                    current_line_ranges = match.get('line_ranges', [])

                    if path not in consolidated_matches:
                        consolidated_matches[path] = {'path': path, 'line_ranges': current_line_ranges}
                    else:
                        # Merge line ranges for existing file
                        existing_line_ranges = consolidated_matches[path].get('line_ranges', [])
                        # Combine and remove duplicates, then sort
                        combined_ranges = sorted(list(set(existing_line_ranges + current_line_ranges)))
                        
                        # Optional: Optimize merged ranges (e.g., [1,5], [6,10] -> [1,10])
                        # For now, just a list of distinct tuples is fine as content.py handles it
                        consolidated_matches[path]['line_ranges'] = combined_ranges
                    unique_matched_paths.add(path) # Keep track of unique file paths

            except TooManyMatchesError as e:
                logger.error(f"❌ {e}")
                sys.exit(1)
            except Exception as e:
                logger.error(f"An unexpected error occurred processing query '{query}': {e}")
                logger.debug(f"Traceback: {e.__traceback__}")
                sys.exit(1)
        
        # Convert consolidated_matches dictionary to list for output
        all_matched_files_data = list(consolidated_matches.values())


    output_markdown_lines: List[str] = []
    output_json_data: Dict[str, Any] = {
        'directory_structure': tree_output,
        'files': []
    }

    output_markdown_lines.append(f"# Project Structure for {os.path.basename(CONFIG['ROOT'])}\\n")
    if args.profile:
        output_markdown_lines.append(f"**Profile:** `{args.profile}`\\n")
    output_markdown_lines.append("```\\n[DIRECTORY_STRUCTURE]\\n")
    output_markdown_lines.append(tree_output)
    output_markdown_lines.append("```\\n")

    if all_matched_files_data:
        output_markdown_lines.append("\\n# Included File Contents\\n")
        all_matched_files_data.sort(key=lambda x: x['path'])
        for file_data in all_matched_files_data:
            try:
                # Pass file_data as is; format_file_content_markdown will look for 'line_ranges'
                output_markdown_lines.append(format_file_content_markdown(file_data, CONFIG['ROOT'], get_file_content)) # Removed FUNCTION_PATTERNS
                output_json_data['files'].append(format_file_content_json(file_data, CONFIG['ROOT'], get_file_content)) # Removed FUNCTION_PATTERNS
            except FileReadError as e:
                logger.warning(f"Skipping file '{file_data['path']}' due to read error: {e}")
                output_markdown_lines.append(f"**[FILE: /{os.path.relpath(file_data['path'], CONFIG['ROOT'])}]**\\n```\\n// Error reading file: {e}\\n```")
            except Exception as e:
                logger.error(f"An unexpected error occurred formatting file '{file_data['path']}': {e}")
                logger.debug(f"Traceback: {e.__traceback__}")
                sys.exit(1)
    else:
        output_markdown_lines.append("\\n_No specific files included based on queries._\\n")

    logger.info(f"\n--- Matched Files Summary ({len(unique_matched_paths)} unique files) ---")
    if unique_matched_paths:
        for file_path in sorted(list(unique_matched_paths)):
            logger.info(f"  - {os.path.relpath(file_path, CONFIG['ROOT'])}")
    else:
        logger.info("  No files included based on queries.")
    logger.info("-" * 20)

    if args.dry_run:
        logger.info("\n--- Dry Run Output Preview (Markdown) ---")
        print('\n\n'.join(output_markdown_lines))
        logger.info("\n--- Dry Run Output Preview (JSON) ---")
        print(json.dumps(output_json_data, indent=2, ensure_ascii=False))
        logger.info("\n🎯 Dry run complete. No files were written.")
    else:
        success = True
        for output_format in CONFIG['OUTPUT_FORMATS']:
            output_filepath = f"{CONFIG['OUTPUT_FILE_BASE_NAME']}.{output_format}"
            try:
                if output_format == 'md':
                    with open(output_filepath, 'w', encoding='utf-8') as f:
                        f.write('\n\n'.join(output_markdown_lines))
                elif output_format == 'json':
                    with open(output_filepath, 'w', encoding='utf-8') as f:
                        json.dump(output_json_data, f, indent=2, ensure_ascii=False)
                logger.info(f"🎯 Wrote output in '{output_format}' format to '{output_filepath}'.")
            except IOError as e:
                logger.error(f"Error: Could not write to output file '{output_filepath}': {e}")
                success = False
        if success:
            logger.info(f"\nCompleted. Total {len(unique_matched_paths)} file(s) and directory tree processed.")

if __name__ == '__main__':
    main()