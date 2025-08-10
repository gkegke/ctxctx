# ctxctx/search.py
import fnmatch
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

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
    is_ignored: Callable[[Path], bool],
    config: Config,
) -> List[Dict[str, Any]]:
    """Finds files matching the given query within the root directory.
    Supports exact paths, glob patterns, and multiple line ranges.
    :param query: The query string (e.g., 'src/file.py', 'foo.js:10,20:30,40',
                  '*.md').
    :param is_ignored: A callable function to check if a path should be ignored.
    :param config: The Config object containing root directory and search depth.
    :return: A list of dictionaries, each containing 'path' (a Path object) and optional
             'line_ranges'.
    """
    raw_matches: List[Dict[str, Any]] = []
    root_path: Path = config.root
    search_max_depth = config.search_max_depth

    original_query = query
    is_force_include_query = original_query.startswith(FORCE_INCLUDE_PREFIX)
    if is_force_include_query:
        query = original_query[len(FORCE_INCLUDE_PREFIX) :]
        logger.debug(
            f"Force-include query detected. Searching for: '{query}' from "
            f"original '{original_query}'"
        )

    query_parts = query.split(":", 1)
    base_query_str = query_parts[0]  # Keep as string for glob matching

    # NEW: Create a Path object for exact comparisons, stripping trailing slash
    # This ensures "foo/" and "foo" are treated the same for Path equality
    base_query_path_for_exact_match = Path(base_query_str.rstrip(os.sep))

    target_line_ranges: List[Tuple[int, int]] = []

    if len(query_parts) > 1:
        parsed_ranges = _parse_line_ranges(query_parts[1])
        if parsed_ranges:
            target_line_ranges = parsed_ranges
        else:
            logger.debug(
                f"Part after first colon in '{query}' is not a valid line "
                "range. Treating as full path/glob query."
            )
            # If line range parsing failed, treat the whole query as a path/glob
            base_query_str = (
                query  # Revert base_query_str to original query if line range parsing fails
            )
            base_query_path_for_exact_match = Path(base_query_str.rstrip(os.sep))  # Re-normalize
            target_line_ranges = []

    # Handle absolute paths separately
    query_path = Path(base_query_str)
    if query_path.is_absolute():
        if query_path.exists():
            if query_path.is_file():
                raw_matches.append({"path": query_path, "line_ranges": target_line_ranges})
                logger.debug(
                    f"Found exact absolute file match: {query_path} "
                    f"with ranges {target_line_ranges}"
                )
            elif query_path.is_dir():
                logger.debug(f"Searching absolute directory: {query_path}")
                for dirpath_str, _, filenames in os.walk(str(query_path)):
                    current_path_dir = Path(dirpath_str)
                    current_depth = len(current_path_dir.parts) - len(query_path.parts)
                    if current_depth >= search_max_depth:
                        logger.debug(
                            f"Max search depth ({search_max_depth}) reached "
                            f"for sub-path: {current_path_dir}. Pruning."
                        )
                        continue
                    for filename in filenames:
                        full_path = current_path_dir / filename
                        raw_matches.append({"path": full_path, "line_ranges": []})
                        logger.debug(f"Found file from absolute directory search: " f"{full_path}")

    # Remaining logic for relative paths and globs using os.walk
    # This loop collects all potential matches, regardless of ignore status initially
    for dirpath_str, dirnames, filenames in os.walk(str(root_path)):
        current_dir_path = Path(dirpath_str)
        current_depth = len(current_dir_path.parts) - len(root_path.parts)
        if current_depth >= search_max_depth and current_dir_path != root_path:
            logger.debug(
                f"Reached max search depth ({search_max_depth}) at {current_dir_path}. " "Pruning."
            )
            dirnames[:] = []
            continue

        # Handle directory matches (if the query itself is a directory)
        for dirname in list(dirnames):
            full_path_dir = current_dir_path / dirname
            rel_path_dir = full_path_dir.relative_to(root_path)

            # Check for directory match (purely based on name/path match, not ignore status)
            is_dir_match = (
                # Exact relative path match (e.g., 'src' == 'src')
                rel_path_dir == base_query_path_for_exact_match
                or Path(dirname)
                == Path(
                    base_query_path_for_exact_match.name
                )  # Exact base name match (e.g., 'src' == 'src' if query was 'src')
                or fnmatch.fnmatch(dirname, base_query_str)  # Glob match on base name (strings)
                or fnmatch.fnmatch(
                    str(rel_path_dir), base_query_str
                )  # Glob match on relative path (strings)
            )

            if is_dir_match:
                logger.debug(
                    f"Directory match found for query '{original_query}':"
                    f"{full_path_dir}. Including contents."
                )
                # Recursively add all files within the matched directory, up to search_max_depth
                for d_dirpath_str, _, d_filenames in os.walk(str(full_path_dir)):
                    d_current_path_dir = Path(d_dirpath_str)
                    sub_depth_from_matched_dir = len(d_current_path_dir.parts) - len(
                        full_path_dir.parts
                    )
                    total_depth = current_depth + 1 + sub_depth_from_matched_dir
                    if total_depth >= search_max_depth:
                        logger.debug(
                            f"Max search depth ({search_max_depth}) reached "
                            f"for sub-path: {d_current_path_dir}. Pruning."
                        )
                        continue
                    for d_filename in d_filenames:
                        d_full_path = d_current_path_dir / d_filename
                        raw_matches.append({"path": d_full_path, "line_ranges": []})
                        logger.debug(f"Found file from directory search: {d_full_path}")
                dirnames.remove(dirname)  # Prune this directory from further os.walk traversal
                continue

        # Handle file matches
        for filename in filenames:
            full_path_file = current_dir_path / filename
            rel_path_file = full_path_file.relative_to(root_path)

            # Check for file match (purely based on name/path match, not ignore status)
            is_file_match = (
                base_query_path_for_exact_match
                == rel_path_file  # Path object comparison (e.g., 'main.py' == 'main.py')
                or base_query_path_for_exact_match
                == Path(
                    filename
                )  # Path object comparison (e.g., 'main.py' == 'main.py' if query was 'main.py')
                or fnmatch.fnmatch(filename, base_query_str)  # String glob matching
                or fnmatch.fnmatch(str(rel_path_file), base_query_str)  # String glob matching
            )

            if is_file_match:
                if target_line_ranges:
                    raw_matches.append({"path": full_path_file, "line_ranges": target_line_ranges})
                    logger.debug(
                        f"Found specific file match: {full_path_file} with line "
                        f"ranges {target_line_ranges}"
                    )
                else:
                    raw_matches.append({"path": full_path_file, "line_ranges": []})
                    logger.debug(f"Found general file match: {full_path_file}")

    # --- Apply Ignore Logic ---
    # Filter raw_matches using the is_ignored callable
    filtered_matches: List[Dict[str, Any]] = []
    for match in raw_matches:
        path: Path = match["path"]
        # The is_ignored function encapsulates all ignore/force-include rules.
        # If the path is force-included, is_ignored will return False.
        if not is_ignored(path):
            filtered_matches.append(match)
        else:
            logger.debug(f"Skipping ignored path: {path}")

    # --- Consolidate and Deduplicate Matches ---
    unique_matches: Dict[Path, Dict[str, Any]] = {}
    for match in filtered_matches:
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
