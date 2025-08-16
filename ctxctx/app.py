# ctxctx/app.py
import datetime
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from . import __version__ as app_version
from .config import (
    Config,
    apply_profile_config,
    generate_default_config_file,
    get_default_config,
    load_base_config_file,
    load_profile_config,
)
from .content import get_file_content
from .exceptions import (
    ConfigurationError,
    FileReadError,
    OutputFormattingError,
    OutputWriteError,
    QueryProcessingError,
    TooManyMatchesError,
)
from .ignore import IgnoreManager
from .logging_utils import setup_main_logging
from .output import format_file_content_json, format_file_content_markdown
from .search import FORCE_INCLUDE_PREFIX, find_matches
from .tree import generate_tree_string

logger = logging.getLogger(__name__)


class CtxCtxApp:
    """Encapsulates the core logic and state for the ctxctx application."""

    def __init__(self, args: Any):  # Use Any for args to avoid circular import with argparse
        self.args = args
        # Initialize config with defaults; it will be modified by profiles and base config
        self.config: Config = get_default_config()
        # self.root_path is now directly accessible via self.config.root (which is a Path object)
        self.ignore_manager: Optional[IgnoreManager] = None
        # is_ignored_func now expects Path objects
        self.is_ignored_func: Optional[Callable[[Path], bool]] = None
        # Store original queries, and a mutable list for processing
        self.original_queries = list(args.queries)
        self.queries = list(args.queries)

        self._setup_application()
        logger.info(f"--- LLM Context Builder (v{app_version}) ---")
        self._log_initial_configuration()

    def _setup_application(self) -> None:
        """
        Orchestrates the main application setup steps.
        """
        self._init_logging()
        # Config object handles root resolution during merge.
        self._load_and_apply_base_config_file()  # NEW: Load general config file first
        self._load_and_apply_profile()
        self._initialize_ignore_manager()

    def _init_logging(self) -> None:
        """Initializes the main application logging."""
        setup_main_logging(self.args.debug, self.args.log_file)

    def _create_default_config_if_needed(self, config_filepath: Path) -> None:
        """Helper to create the default config file if it's missing."""
        if self.args.dry_run:
            logger.info(
                f"Config file '{config_filepath.name}' not found. "
                "Skipping creation in dry-run mode."
            )
            return

        try:
            logger.info(
                f"Config file '{config_filepath.name}' not found. Creating a default one..."
            )
            generate_default_config_file(config_filepath)
            logger.info(
                f"✅ A default '{config_filepath.name}' has been created. "
                "You can customize it for future runs."
            )
        except (ConfigurationError, Exception) as e:
            # This could happen if PyYAML is not installed or due to file permissions.
            # Log a warning but don't fail the entire run. The app can proceed with defaults.
            logger.warning(f"⚠️ Could not create default config file '{config_filepath.name}': {e}")

    def _load_and_apply_base_config_file(self) -> None:
        """
        Loads and applies configuration from the default config file (e.g., .ctxctx.yaml).
        If the file does not exist, it creates a default one.
        """
        config_filepath = self.config.root / self.config.default_config_filename
        logger.debug(f"Attempting to load base config from: {config_filepath}")

        if not config_filepath.is_file():
            self._create_default_config_if_needed(config_filepath)
            # After attempting to create, we return. The app will use defaults on this run.
            return

        try:
            config_data = load_base_config_file(config_filepath)
            if config_data:
                self.config.merge(config_data)
                logger.info(f"Applied base configuration from: {config_filepath}")
            else:
                logger.debug(f"Base configuration file found but was empty: {config_filepath}")
        except ConfigurationError as e:
            raise e  # Re-raise, as it's already a CtxError and well-formatted
        except Exception as e:
            # Catch any other unexpected errors and wrap them
            raise ConfigurationError(
                f"An unexpected error occurred while loading base config file"
                f"'{config_filepath}': {e}"
            ) from e

    def _load_and_apply_profile(self) -> None:
        """Loads and applies configuration from a specified profile, if any."""
        if not self.args.profile:
            return

        # Removed the try-except and sys.exit here. ConfigurationError is now propagated.
        profile_data = load_profile_config(
            self.args.profile, self.config.root, self.config.profile_config_file
        )
        apply_profile_config(self.config, profile_data)  # Pass the config object
        logger.info(f"Active Profile: {self.args.profile}")

        if "queries" in profile_data:
            self.queries.extend(profile_data["queries"])

    def _initialize_ignore_manager(self) -> None:
        """Initializes the IgnoreManager with global and profile-specific ignore rules."""
        force_include_patterns = []
        for q in self.queries:
            if q.startswith(FORCE_INCLUDE_PREFIX):
                # The path for force_include_patterns should not contain line ranges,
                # as the `is_ignored` function works on full paths to check if they
                # *should* be ignored,
                # not what specific part of them is relevant.
                # Convert to Path object for consistency, then to string for the pattern list.
                path_part = Path(q[len(FORCE_INCLUDE_PREFIX) :].split(":", 1)[0])
                force_include_patterns.append(str(path_part))
        self.ignore_manager = IgnoreManager(
            self.config, force_include_patterns
        )  # Pass the config object
        self.is_ignored_func = self.ignore_manager.is_ignored

    def _log_initial_configuration(self) -> None:
        """Logs the initial application configuration and ignore patterns."""
        logger.info(f"Root Directory: {self.config.root}")
        logger.info(f"Tree Max Depth: {self.config.tree_max_depth}")
        logger.info(f"Search Max Depth: {self.config.search_max_depth}")
        logger.info(f"Max Matches Per Query: {self.config.max_matches_per_query}")

        if not self.ignore_manager:  # Should not happen after _initialize_ignore_manager
            logger.error("IgnoreManager not initialized during logging setup.")
            return

        # Fix: Change _explicit_ignore_set to _hardcoded_explicit_names
        all_ignore_patterns_display = sorted(
            list(self.ignore_manager._hardcoded_explicit_names)
            + self.ignore_manager._substring_ignore_patterns
        )
        logger.info(f"Combined Ignore Patterns ({len(all_ignore_patterns_display)}):\n")
        for p in all_ignore_patterns_display[:10]:
            logger.info(f"  - {p}")
        if len(all_ignore_patterns_display) > 10:
            logger.info(f"  ...and {len(all_ignore_patterns_display) - 10} more.")

        if self.ignore_manager._force_include_patterns:
            logger.info(
                f"Force Include Patterns "
                f"({len(self.ignore_manager._force_include_patterns)}):\n"
            )
            for p in sorted(self.ignore_manager._force_include_patterns)[:10]:
                logger.info(f"  - {FORCE_INCLUDE_PREFIX}{p}")
            if len(self.ignore_manager._force_include_patterns) > 10:
                logger.info(
                    f"  ...and {len(self.ignore_manager._force_include_patterns) - 10} " "more."
                )

        if self.config.additional_ignore_filenames:
            logger.info(
                f"Additional Ignore Files: "
                f"{', '.join(self.config.additional_ignore_filenames)}"
            )
        logger.info("-" * 20)

    def _generate_project_structure(self) -> str:
        """Generates the directory tree string."""
        logger.info("Generating directory tree...")
        tree_output = generate_tree_string(
            self.config.root,  # config.root is already a Path
            self.is_ignored_func,
            self.config,  # Pass the config object
            # Individual tree-related config values are now read directly from
            # config object in tree.py
        )
        if not tree_output:
            logger.warning(
                "No directory tree generated (possibly due to ignore rules " "or empty root).\n"
            )
        return tree_output

    def _process_all_queries(
        self,
    ) -> Tuple[List[Dict[str, Any]], Set[Path]]:  # Changed Set[str] to Set[Path]
        """
        Processes all input queries, finds matches, and consolidates them.
        Returns a list of matched file data and a set of unique matched paths.
        """
        logger.info("Processing file queries...")
        all_matched_files_data: List[Dict[str, Any]] = []
        unique_matched_paths: Set[Path] = set()  # Changed to Path
        consolidated_matches: Dict[Path, Dict[str, Any]] = {}  # Keys are now Path objects

        if not self.queries:
            logger.info("No specific file queries provided. " "Including directory tree only.\n")
            return [], set()

        for query in self.queries:
            logger.debug(f"Processing query: '{query}'")
            try:
                matches = find_matches(
                    query, self.is_ignored_func, self.config  # Pass the config object
                )

                if not matches:
                    logger.warning(f"⚠️ No non-ignored matches found for: '{query}'")
                    continue

                if len(matches) > self.config.max_matches_per_query:
                    # Ensure example_paths are strings for error message
                    example_paths = [str(m["path"].relative_to(self.config.root)) for m in matches]
                    # Raise TooManyMatchesError directly; it will be caught by the main handler.
                    raise TooManyMatchesError(
                        query,
                        len(matches),
                        self.config.max_matches_per_query,
                        example_paths,
                    )

                logger.info(f"✅ Using {len(matches)} non-ignored match(es) for " f"'{query}'")
                for match in matches:
                    path: Path = match["path"]  # path is now Path object
                    # Line ranges from search.py are List[List[int]] for JSON
                    # serialization convenience
                    current_line_ranges = match.get("line_ranges", [])

                    if path not in consolidated_matches:
                        consolidated_matches[path] = {
                            "path": path,  # Store Path object
                            "line_ranges": current_line_ranges,
                        }
                    else:
                        existing_line_ranges = consolidated_matches[path].get("line_ranges", [])
                        # Combine and sort line ranges, ensuring no duplicates.
                        # Convert to tuples for set to ensure hashability, then back
                        # to list of lists.
                        combined_ranges = sorted(
                            list(set(tuple(r) for r in existing_line_ranges + current_line_ranges))
                        )
                        consolidated_matches[path]["line_ranges"] = [
                            list(r) for r in combined_ranges
                        ]
                    unique_matched_paths.add(path)

            except TooManyMatchesError:
                # Re-raise the TooManyMatchesError to be caught by the top-level handler
                raise
            except Exception as e:
                # Catch any other unexpected errors during query processing and raise a
                # specific exception
                raise QueryProcessingError(
                    f"An unexpected error occurred processing query '{query}': {e}", query=query
                ) from e

        all_matched_files_data = list(consolidated_matches.values())
        return all_matched_files_data, unique_matched_paths

    def _format_all_content_for_output(
        self, all_matched_files_data: List[Dict[str, Any]]
    ) -> Tuple[
        List[str], List[Dict[str, Any]], Dict[Path, Optional[int]]
    ]:  # Changed Dict[str, Optional[int]] to Dict[Path, Optional[int]]
        """
        Formats matched file content for Markdown and JSON output.
        Returns markdown content lines, JSON file data list, and character counts.
        """
        markdown_content_lines: List[str] = []
        json_files_data_list: List[Dict[str, Any]] = []
        file_char_counts: Dict[Path, Optional[int]] = {}  # Changed to Path

        if all_matched_files_data:
            markdown_content_lines.append("\n# Included File Contents\n")
            all_matched_files_data.sort(
                key=lambda x: str(x["path"])
            )  # Sort by string representation of path
            for file_data in all_matched_files_data:
                path: Path = file_data["path"]  # path is a Path object
                try:
                    markdown_output = format_file_content_markdown(
                        file_data, self.config.root, get_file_content
                    )
                    markdown_content_lines.append(markdown_output)

                    json_output = format_file_content_json(
                        file_data, self.config.root, get_file_content
                    )
                    json_files_data_list.append(json_output)

                    if "content" in json_output and json_output["content"] is not None:
                        file_char_counts[path] = len(json_output["content"])
                    else:
                        file_char_counts[path] = 0
                except FileReadError as e:
                    logger.warning(f"Skipping file '{path}' due to read " f"error: {e}")
                    # Use Path.relative_to()
                    markdown_content_lines.append(
                        f"**[FILE: /{path.relative_to(self.config.root)}]**"
                        f"\n```\n// Error reading file: {e}\n```"
                    )
                    file_char_counts[path] = None
                except Exception as e:
                    # Catch any other unexpected errors during formatting and raise
                    # a specific exception
                    raise OutputFormattingError(
                        f"An unexpected error occurred formatting file '{path}': {e}",
                        file_path=str(path),
                    ) from e
        else:
            markdown_content_lines.append("\n_No specific files included based on queries._\n")

        return markdown_content_lines, json_files_data_list, file_char_counts

    def _build_final_json_data(
        self,
        tree_output: str,
        json_files_data_list: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Constructs the final JSON output data structure including metadata.
        Calculates total character count for JSON.
        """
        now_utc = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"

        # Ensure paths in json_files_data_list are strings for JSON serialization
        serialized_json_files_data_list = []
        for item in json_files_data_list:
            copied_item = item.copy()
            if isinstance(copied_item.get("path"), Path):
                copied_item["path"] = str(copied_item["path"])
            serialized_json_files_data_list.append(copied_item)

        output_json_data: Dict[str, Any] = {
            "directory_structure": tree_output,
            "details": {
                "generated_at": now_utc,
                "root_directory": str(self.config.root),  # Convert Path to str for JSON
                "queries_used": self.original_queries,
                "tree_depth_limit": self.config.tree_max_depth,
                "search_depth_limit": self.config.search_max_depth,
                "files_included_count": len(serialized_json_files_data_list),
                # total_characters_json will be added after this dict is built and stringified
            },
            "files": serialized_json_files_data_list,  # Use serialized list
        }

        # Calculate total_characters_json *after* the dict is fully formed
        # (except for this field itself).
        # We dump it to a string first to get its character length,
        # then add that length back.
        temp_json_string_for_size = json.dumps(output_json_data, indent=2, ensure_ascii=False)
        output_json_data["details"]["total_characters_json"] = len(temp_json_string_for_size)
        return output_json_data

    def _log_summary(
        self,
        unique_matched_paths: Set[Path],  # Changed Set[str] to Set[Path]
        file_char_counts: Dict[
            Path, Optional[int]
        ],  # Changed Dict[str, Optional[int]] to Dict[Path, Optional[int]]
        output_json_data: Dict[str, Any],
        output_markdown_lines: List[str],
    ) -> None:
        """Logs the summary of matched files and total character counts."""
        logger.info(
            f"\n--- Matched Files Summary ({len(unique_matched_paths)} " "unique files) ---"
        )
        if unique_matched_paths:
            for file_path in sorted(list(unique_matched_paths)):  # Still sorting Path objects
                relative_path = file_path.relative_to(self.config.root)  # Use Path.relative_to()
                char_count = file_char_counts.get(file_path)
                if char_count is not None:
                    logger.info(f"  - {relative_path} ({char_count} characters)")
                else:
                    logger.info(f"  - {relative_path} (Content not available or error)")
        else:
            logger.info("  No files included based on queries.")
        logger.info("-" * 20)

        # Calculate total chars for markdown for summary logging
        total_markdown_chars = len("".join(output_markdown_lines))

        logger.info(
            f"Completed. Total {len(unique_matched_paths)} file(s) "
            "and directory tree processed."
        )
        logger.info(
            f"Total chars: {total_markdown_chars} (Markdown), "
            f"{output_json_data['details']['total_characters_json']} (JSON)"
        )

    def _handle_output(
        self,
        output_markdown_lines: List[str],
        output_json_data: Dict[str, Any],
    ) -> None:
        """Handles writing output to console (dry run) or files."""
        if self.args.dry_run:
            logger.info("\n--- Dry Run Output Preview (Markdown) ---")
            print("\n\n".join(output_markdown_lines))
            logger.info("\n--- Dry Run Output Preview (JSON) ---")
            print(json.dumps(output_json_data, indent=2, ensure_ascii=False))
            logger.info("\n🎯 Dry run complete. No files were written.")
        else:
            # Removed success flag and sys.exit(1) here. OutputWriteError is now raised.
            for output_format in self.config.output_formats:
                # self.config.output_file_base_name is a string. Combine with Path object.
                output_filepath = Path(f"{self.config.output_file_base_name}.{output_format}")
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
                    raise OutputWriteError(
                        f"Error: Could not write to output file '{output_filepath}': {e}",
                        file_path=str(output_filepath),
                    ) from e

    def run(self) -> None:
        """Executes the main application logic."""
        # The main logic flow. All errors are now propagated up to cli.py's main function.
        if self.args.dry_run:
            logger.info("Mode: DRY RUN (no files will be written)")

        tree_output = self._generate_project_structure()

        all_matched_files_data, unique_matched_paths = self._process_all_queries()

        output_markdown_lines: List[str] = [
            f"# Project Structure for {self.config.root.name}\n"
        ]  # Use .name for basename
        if self.args.profile:
            output_markdown_lines.append(f"**Profile:** `{self.args.profile}`\n")
        output_markdown_lines.append("```\n[DIRECTORY_STRUCTURE]\n")
        output_markdown_lines.append(tree_output)
        output_markdown_lines.append("```\n")

        markdown_content_lines, json_files_data_list, file_char_counts = (
            self._format_all_content_for_output(all_matched_files_data)
        )
        output_markdown_lines.extend(markdown_content_lines)

        output_json_data = self._build_final_json_data(tree_output, json_files_data_list)

        self._log_summary(
            unique_matched_paths, file_char_counts, output_json_data, output_markdown_lines
        )

        self._handle_output(output_markdown_lines, output_json_data)
