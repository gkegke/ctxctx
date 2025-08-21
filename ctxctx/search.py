# ctxctx/search.py
import fnmatch
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .config import Config

logger = logging.getLogger(__name__)

FORCE_INCLUDE_PREFIX = "force:"


def _parse_line_ranges(ranges_str: str) -> List[Tuple[int, int]]:
    """Parses a string like '1,50:80,200' into a list of (start, end) tuples.
    Returns an empty list if parsing fails for any segment.
    """
    parsed_ranges: List[Tuple[int, int]] = []
    if not ranges_str:
        return parsed_ranges

    individual_range_strs = ranges_str.split(":")
    for lr_str in individual_range_strs:
        try:
            start_s, end_s = lr_str.split(",")
            start = int(start_s)
            end = int(end_s)
            if start <= 0 or end <= 0 or start > end:
                logger.warning(
                    f"Invalid line range format '{lr_str}': Start and end "
                    "lines must be positive, and start <= end. Skipping invalid segment."
                )
                continue
            parsed_ranges.append((start, end))
        except ValueError:
            logger.warning(
                f"Invalid line range format '{lr_str}'. Expected 'start,end'. "
                "Skipping invalid segment."
            )
            continue
    return parsed_ranges


def find_matches(
    query: str,
    all_project_files: List[Path],
    config: Config,
) -> List[Dict[str, Any]]:
    """
    Finds files matching the given query from a pre-compiled list of project files.
    This function no longer walks the filesystem.

    :param query: The query string (e.g., 'src/file.py', 'foo.js:10,20:30,40', '*.md').
    :param all_project_files: A list of all non-ignored Path objects in the project.
    :param config: The Config object containing root directory.
    :return: A list of dictionaries, each containing 'path' and optional 'line_ranges'.
    """
    raw_matches: List[Dict[str, Any]] = []
    root_path: Path = config.root

    original_query = query
    is_force_include_query = original_query.startswith(FORCE_INCLUDE_PREFIX)
    if is_force_include_query:
        # The force include logic is now handled upfront in the single walk by IgnoreManager.
        # Here, we just need to strip the prefix to get the actual pattern.
        query = original_query[len(FORCE_INCLUDE_PREFIX) :]

    query_parts = query.split(":", 1)
    base_query_str = query_parts[0]
    target_line_ranges: List[Tuple[int, int]] = []

    if len(query_parts) > 1:
        parsed_ranges = _parse_line_ranges(query_parts[1])
        if parsed_ranges:
            target_line_ranges = parsed_ranges
        else:
            # If line range parsing failed, treat the whole query as a path/glob
            base_query_str = query

    # --- Refactored and Fixed Matching Logic ---
    # Determine if the query string points to an existing directory.
    clean_base_query_for_dir_check = base_query_str.rstrip("/\\")
    potential_dir_path = config.root / clean_base_query_for_dir_check
    query_is_directory = potential_dir_path.is_dir()

    for file_path in all_project_files:
        # For consistent matching, we compare against relative paths and the file's name.
        try:
            relative_path = file_path.relative_to(root_path)
        except ValueError:
            # This can happen if a force-included file is outside the project root.
            # In this case, we'll match against the full path string.
            relative_path = file_path

        filename = file_path.name
        relative_path_str = relative_path.as_posix()

        # A file is a match if EITHER:
        # 1. The query, treated as a glob, matches the file's relative path or name.
        is_glob_match = fnmatch.fnmatch(relative_path_str, base_query_str) or fnmatch.fnmatch(
            filename, base_query_str
        )

        # 2. The query was identified as a directory, and the file is inside that directory.
        is_dir_content_match = False
        if query_is_directory:
            try:
                # Path.relative_to() will succeed if file_path is inside potential_dir_path,
                # and raise ValueError otherwise. This is a robust check for containment.
                file_path.relative_to(potential_dir_path)
                is_dir_content_match = True
            except ValueError:
                is_dir_content_match = False

        if is_glob_match or is_dir_content_match:
            raw_matches.append(
                {
                    "path": file_path,
                    "line_ranges": target_line_ranges or [],  # Use specified ranges or empty list
                }
            )

    # --- Ignore Logic is no longer needed here ---
    # Filtering was already done when all_project_files was created in app.py.

    # --- Consolidate and Deduplicate Matches ---
    # This logic remains useful for merging line ranges if a file is matched by
    # multiple queries in the future, or for complex queries.
    unique_matches: Dict[Path, Dict[str, Any]] = {}
    for match in raw_matches:
        path = match["path"]
        current_line_ranges = match.get("line_ranges", [])

        if path not in unique_matches:
            unique_matches[path] = {
                "path": path,
                "line_ranges": current_line_ranges,
            }
        else:
            existing_line_ranges = unique_matches[path].get("line_ranges", [])
            # Combine and sort line ranges, ensuring no duplicates
            # Convert to tuples for set, then back to list of lists for consistency
            combined_ranges_set = set(tuple(r) for r in existing_line_ranges + current_line_ranges)
            unique_matches[path]["line_ranges"] = sorted([list(r) for r in combined_ranges_set])
            logger.debug(f"Merged line ranges for existing match {path}.")

    return sorted(list(unique_matches.values()), key=lambda x: str(x["path"]))
