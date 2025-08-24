# [FILE: /ctxctx/app.py]
# ctxctx/app.py
import datetime
import json
import logging
import os
import sys
from itertools import chain
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from . import __version__ as app_version
from . import cache
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
from .resolver import FileResolver
from .search import FORCE_INCLUDE_PREFIX
from .tree import generate_tree_string

logger = logging.getLogger(__name__)


class CtxCtxApp:
    """Encapsulates the core logic and state for the ctxctx application."""

    def __init__(self, args: Any):  # Use Any for args to avoid circular import with argparse
        self.args = args
        self.config: Config = get_default_config()
        self.ignore_manager: Optional[IgnoreManager] = None
        self.is_ignored_func: Optional[Callable[[Path], bool]] = None
        self.profile_data: Dict[str, Any] = {}
        self.resolver: Optional[FileResolver] = None  # Correctly initialized as optional

        self.original_queries = list(args.queries)
        self.queries: List[str] = []
        self.active_profiles: List[str] = []

        self._setup_application()
        logger.info(f"--- LLM Context Builder (v{app_version}) ---")
        self._log_initial_configuration()

    def _pre_process_queries_for_profiles(self) -> None:
        """
        Scans all incoming arguments for profile flags, activates them,
        and separates them from file/path queries. This handles both the dedicated
        `--profile` arg and profile flags inside argfiles.
        """
        # 1. Handle the dedicated --profile argument from argparse
        if self.args.profile:
            # `action="append"` with `nargs="+` creates a list of lists,
            # e.g., [['search', 'cliAndApp']]
            # We need to flatten it into a single list of profile names.
            self.active_profiles.extend(chain.from_iterable(self.args.profile))

        # 2. Handle `--profile <name>` pairs found within positional queries (from argfiles)
        remaining_queries = []
        query_iterator = iter(self.original_queries)
        for q in query_iterator:
            q_stripped = q.strip()
            if not q_stripped or q_stripped.startswith("#"):
                continue

            if q_stripped == "--profile":
                try:
                    profile_name = next(query_iterator).strip()
                    if profile_name and not profile_name.startswith("-"):
                        self.active_profiles.append(profile_name)
                    else:
                        logger.warning(
                            f"Ignoring invalid profile name after '--profile': {profile_name}"
                        )
                except StopIteration:
                    logger.warning("Ignoring '--profile' flag at end of query list with no name.")
            elif q_stripped.startswith("--profile"):
                parts = q_stripped.split(maxsplit=1)
                if len(parts) > 1:
                    self.active_profiles.append(parts[1])
                else:
                    logger.warning(f"Ignoring malformed profile flag: {q_stripped}")
            else:
                remaining_queries.append(q_stripped)

        self.queries = remaining_queries
        self.active_profiles = sorted(list(set(self.active_profiles)))  # Deduplicate

    def _setup_application(self) -> None:
        """
        Orchestrates the main application setup steps in the correct order.
        """
        self._init_logging()
        self._pre_process_queries_for_profiles()
        self._load_and_apply_base_config_file()
        self._load_and_apply_profiles()

        # CRITICAL FIX: Initialize resolver and ignore_manager AFTER all configs are loaded.
        self.resolver = FileResolver(self.config)
        self._initialize_ignore_manager()

    def _init_logging(self) -> None:
        """Initializes the main application logging."""
        log_stream = sys.stderr if self.args.list_files else sys.stdout
        setup_main_logging(self.args.debug, self.args.log_file, stream=log_stream)

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
            return

        try:
            config_data = load_base_config_file(config_filepath)
            if config_data:
                self.config.merge(config_data)
                logger.info(f"Applied base configuration from: {config_filepath}")
            else:
                logger.debug(f"Base configuration file found but was empty: {config_filepath}")
        except ConfigurationError as e:
            raise e
        except Exception as e:
            raise ConfigurationError(
                f"An unexpected error occurred while loading base config file"
                f"'{config_filepath}': {e}"
            ) from e

    def _load_and_apply_profiles(self) -> None:
        """Loads and applies configuration from all active profiles, merging their settings."""
        if not self.active_profiles:
            return

        logger.info(f"Active Profile(s): {', '.join(self.active_profiles)}")
        for profile_name in self.active_profiles:
            try:
                profile_data_single = load_profile_config(
                    profile_name, self.config.root, self.config.default_config_filename
                )
                config_from_profile = {
                    k: v
                    for k, v in profile_data_single.items()
                    if k not in ["include", "exclude", "queries", "description"]
                }
                if config_from_profile:
                    apply_profile_config(self.config, config_from_profile)

                for key in ["queries", "include", "exclude"]:
                    if key in profile_data_single:
                        self.profile_data.setdefault(key, []).extend(profile_data_single[key])

            except ConfigurationError as e:
                logger.error(f"Could not load profile '{profile_name}': {e}")
                continue

    def _initialize_ignore_manager(self) -> None:
        """Initializes the IgnoreManager with global and profile-specific ignore rules."""
        all_queries_for_force_include = self.queries + self.profile_data.get("queries", [])

        force_include_patterns = []
        for q in all_queries_for_force_include:
            if q.startswith(FORCE_INCLUDE_PREFIX):
                path_part = Path(q[len(FORCE_INCLUDE_PREFIX) :].split(":", 1)[0])
                force_include_patterns.append(str(path_part))

        self.ignore_manager = IgnoreManager(self.config, force_include_patterns)
        self.is_ignored_func = self.ignore_manager.is_ignored

    def _log_initial_configuration(self) -> None:
        """Logs the initial application configuration and ignore patterns."""
        logger.info(f"Root Directory: {self.config.root}")
        logger.info(f"Tree Max Depth: {self.config.tree_max_depth}")
        logger.info(f"Search Max Depth: {self.config.search_max_depth}")
        logger.info(f"Max Matches Per Query: {self.config.max_matches_per_query}")

        if not self.ignore_manager:
            logger.error("IgnoreManager not initialized during logging setup.")
            return

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
            self.config.root,
            self.is_ignored_func,
            self.config,
        )
        if not tree_output:
            logger.warning(
                "No directory tree generated (possibly due to ignore rules " "or empty root).\n"
            )
        return tree_output

    def _collect_all_project_files(self) -> List[Path]:
        """
        Walks the entire project directory once to collect all non-ignored files.
        This is a major performance optimization. It now uses a cache.
        """
        logger.debug("Attempting to load file list from cache...")
        cached_files = cache.load_cache(self.config, ",".join(self.active_profiles))
        if cached_files is not None:
            cache.save_cache(self.config, ",".join(self.active_profiles), cached_files)
            return cached_files

        logger.info("Cache not found or invalid. Performing a full file system walk...")
        all_files: List[Path] = []
        if not self.is_ignored_func:
            logger.error("Ignore function not initialized before file collection.")
            return []

        for dirpath_str, dirnames, filenames in os.walk(self.config.root, topdown=True):
            current_dir_path = Path(dirpath_str)
            dirnames[:] = [d for d in dirnames if not self.is_ignored_func(current_dir_path / d)]
            for filename in filenames:
                full_path = current_dir_path / filename
                if not self.is_ignored_func(full_path):
                    all_files.append(full_path)

        cache.save_cache(self.config, ",".join(self.active_profiles), all_files)
        logger.debug(f"Collected {len(all_files)} non-ignored files from project walk.")
        return all_files

    def _process_and_resolve_files(
        self,
        all_project_files: List[Path],
    ) -> Tuple[List[Dict[str, Any]], Set[Path]]:
        """
        Delegates file resolution to the FileResolver.
        """
        if not self.resolver:
            raise ConfigurationError("FileResolver was not initialized correctly.")

        logger.info("Resolving files based on profile rules and queries...")

        profile_queries_raw = self.profile_data.get("queries", [])
        profile_queries = [
            q
            for q in (line.strip() for line in profile_queries_raw)
            if q and not q.startswith("#")
        ]
        all_queries = profile_queries + self.queries

        try:
            return self.resolver.resolve(
                all_project_files=all_project_files,
                include_patterns=self.profile_data.get("include", []),
                exclude_patterns=self.profile_data.get("exclude", []),
                queries=all_queries,
            )
        except TooManyMatchesError:
            raise
        except Exception as e:
            raise QueryProcessingError(
                f"An unexpected error occurred during file resolution: {e}"
            ) from e

    def _format_all_content_for_output(
        self, all_matched_files_data: List[Dict[str, Any]]
    ) -> Tuple[List[str], List[Dict[str, Any]], Dict[Path, Optional[int]]]:
        """
        Formats matched file content for Markdown and JSON output.
        Returns markdown content lines, JSON file data list, and character counts.
        """
        markdown_content_lines: List[str] = []
        json_files_data_list: List[Dict[str, Any]] = []
        file_char_counts: Dict[Path, Optional[int]] = {}

        if all_matched_files_data:
            markdown_content_lines.append("\n# Included File Contents\n")
            for file_data in all_matched_files_data:
                path: Path = file_data["path"]
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
                    markdown_content_lines.append(
                        f"**[FILE: /{path.relative_to(self.config.root)}]**"
                        f"\n```\n// Error reading file: {e}\n```"
                    )
                    file_char_counts[path] = None
                except Exception as e:
                    raise OutputFormattingError(
                        f"An unexpected error occurred formatting file '{path}': {e}",
                        file_path=str(path),
                    ) from e
        else:
            markdown_content_lines.append(
                "\n_No specific files included based on queries or rules._\n"
            )

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
        now_utc = (
            datetime.datetime.now(datetime.UTC)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )

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
                "root_directory": str(self.config.root),
                "queries_used": self.original_queries,
                "tree_depth_limit": self.config.tree_max_depth,
                "search_depth_limit": self.config.search_max_depth,
                "files_included_count": len(serialized_json_files_data_list),
            },
            "files": serialized_json_files_data_list,
        }

        temp_json_string_for_size = json.dumps(output_json_data, indent=2, ensure_ascii=False)
        output_json_data["details"]["total_characters_json"] = len(temp_json_string_for_size)
        return output_json_data

    def _log_summary(
        self,
        unique_matched_paths: Set[Path],
        file_char_counts: Dict[Path, Optional[int]],
        output_json_data: Dict[str, Any],
        output_markdown_lines: List[str],
    ) -> None:
        """Logs the summary of matched files and total character counts."""
        logger.info(
            f"\n--- Matched Files Summary ({len(unique_matched_paths)} " "unique files) ---"
        )
        if unique_matched_paths:
            for file_path in sorted(list(unique_matched_paths)):
                relative_path = file_path.relative_to(self.config.root)
                char_count = file_char_counts.get(file_path)
                if char_count is not None:
                    logger.info(f"  - {relative_path} ({char_count} characters)")
                else:
                    logger.info(f"  - {relative_path} (Content not available or error)")
        else:
            logger.info("  No files included based on rules or queries.")
        logger.info("-" * 20)

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
            for output_format in self.config.output_formats:
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

    def _run_list_files(self) -> None:
        """
        Executes the 'list-files' mode. Collects all non-ignored files,
        sorts them, and prints them to stdout with a helpful header.
        Logs are directed to stderr to keep stdout clean.
        """
        logger.info("Mode: LIST FILES (listing all non-ignored files)")
        all_project_files = self._collect_all_project_files()

        if not all_project_files:
            logger.warning("No files found after applying current ignore rules.")
            return

        relative_paths = sorted(
            [p.relative_to(self.config.root).as_posix() for p in all_project_files]
        )

        print("# List of all non-ignored files found by ctxctx.", file=sys.stdout)
        print(
            "# To use this with ctxctx, save it to a file (e.g., 'cargs') and run: ctxctx @cargs",
            file=sys.stdout,
        )
        print(
            "# To exclude a file or directory, comment out its line (add '#') or delete it.",
            file=sys.stdout,
        )
        print(
            "# You can also add directory paths (e.g., src/utils/) or glob patterns (*.ts).\n",
            file=sys.stdout,
        )

        for rel_path in relative_paths:
            print(rel_path, file=sys.stdout)

        logger.info(
            f"\nListed {len(relative_paths)} file(s). "
            "Redirect this output to a file to create an argument list for ctxctx."
        )

    def run(self) -> None:
        """Executes the main application logic."""
        if self.args.list_files:
            self._run_list_files()
            return

        if self.args.dry_run:
            logger.info("Mode: DRY RUN (no files will be written)")

        tree_output = self._generate_project_structure()
        all_project_files = self._collect_all_project_files()

        all_matched_files_data, unique_matched_paths = self._process_and_resolve_files(
            all_project_files
        )

        output_markdown_lines: List[str] = [f"# Project Structure for {self.config.root.name}\n"]
        if self.active_profiles:
            output_markdown_lines.append(f"**Profile(s):** `{', '.join(self.active_profiles)}`\n")
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
