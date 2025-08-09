# ctxctx/search.py
import fnmatch
import logging
import os
from typing import Any, Callable, Dict, List, Tuple

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
    root: str,
    is_ignored: Callable[[str], bool],
    search_max_depth: int,
) -> List[Dict[str, Any]]:
    """Finds files matching the given query within the root directory.
    Supports exact paths, glob patterns, and multiple line ranges.
    :param query: The query string (e.g., 'src/file.py', 'foo.js:10,20:30,40',
                  '*.md').
    :param root: The root directory to start the search from.
    :param is_ignored: A callable function to check if a path should be ignored.
    :param search_max_depth: Maximum directory depth to traverse for file
                             content search.
    :return: A list of dictionaries, each containing 'path' and optional
             'line_ranges'.
    """
    raw_matches: List[Dict[str, Any]] = []

    original_query = query
    is_force_include_query = original_query.startswith(FORCE_INCLUDE_PREFIX)
    if is_force_include_query:
        query = original_query[len(FORCE_INCLUDE_PREFIX) :]
        logger.debug(
            f"Force-include query detected. Searching for: '{query}' from "
            f"original '{original_query}'"
        )

    query_parts = query.split(":", 1)
    base_query_path = query_parts[0]
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
            base_query_path = query
            target_line_ranges = []

    # Handle absolute paths separately
    if os.path.isabs(base_query_path):
        if os.path.exists(
            base_query_path
        ):  # Removed 'and (not is_ignored(base_query_path))' check here
            if os.path.isfile(base_query_path):
                raw_matches.append({"path": base_query_path, "line_ranges": target_line_ranges})
                logger.debug(
                    f"Found exact absolute file match: {base_query_path} "
                    f"with ranges {target_line_ranges}"
                )
            elif os.path.isdir(base_query_path):
                logger.debug(f"Searching absolute directory: {base_query_path}")
                for dirpath, _, filenames in os.walk(base_query_path):
                    current_depth = dirpath[len(base_query_path) :].count(os.sep)
                    if current_depth >= search_max_depth:
                        logger.debug(
                            f"Max search depth ({search_max_depth}) reached "
                            f"for sub-path: {dirpath}. Pruning."
                        )
                        continue
                    for filename in filenames:
                        full_path = os.path.join(dirpath, filename)
                        raw_matches.append({"path": full_path, "line_ranges": []})
                        logger.debug(f"Found file from absolute directory search: " f"{full_path}")
        # This was an early return, but now we'll process raw_matches for ignore filtering.
        # So no return here, let it fall through to filtering.

    # Remaining logic for relative paths and globs using os.walk
    # This loop collects all potential matches, regardless of ignore status initially
    for dirpath, dirnames, filenames in os.walk(root):
        current_depth = dirpath[len(root) :].count(os.sep)
        if current_depth >= search_max_depth and dirpath != root:
            logger.debug(
                f"Reached max search depth ({search_max_depth}) at {dirpath}. " "Pruning."
            )
            dirnames[:] = []
            continue

        # Handle directory matches (if the query itself is a directory)
        for dirname in list(dirnames):  # Use list(dirnames) to modify dirnames in loop
            full_path_dir = os.path.join(dirpath, dirname)
            rel_path_dir = os.path.relpath(full_path_dir, root)

            # Check for directory match (purely based on name/path match, not ignore status)
            is_dir_match = (
                rel_path_dir.rstrip(os.sep)
                == base_query_path.rstrip(os.sep)  # Exact relative path match
                or dirname
                == base_query_path.rstrip(
                    os.sep
                )  # Exact base name match (for dir queries like "src")
                or fnmatch.fnmatch(dirname, base_query_path)  # Glob match on base name
                or fnmatch.fnmatch(rel_path_dir, base_query_path)  # Glob match on relative path
            )

            if is_dir_match:
                logger.debug(
                    f"Directory match found for query '{original_query}':"
                    f"{full_path_dir}. Including contents."
                )
                # Recursively add all files within the matched directory, up to search_max_depth
                for d_dirpath, _, d_filenames in os.walk(full_path_dir):
                    sub_depth_from_matched_dir = d_dirpath[len(full_path_dir) :].count(os.sep)
                    total_depth = current_depth + 1 + sub_depth_from_matched_dir
                    if total_depth >= search_max_depth:
                        logger.debug(
                            f"Max search depth ({search_max_depth}) reached "
                            f"for sub-path: {d_dirpath}. Pruning."
                        )
                        continue
                    for d_filename in d_filenames:
                        d_full_path = os.path.join(d_dirpath, d_filename)
                        raw_matches.append({"path": d_full_path, "line_ranges": []})
                        logger.debug(f"Found file from directory search: {d_full_path}")
                dirnames.remove(dirname)  # Prune this directory from further os.walk traversal
                continue

        # Handle file matches
        for filename in filenames:
            full_path_file = os.path.join(dirpath, filename)
            rel_path_file = os.path.relpath(full_path_file, root)

            # Check for file match (purely based on name/path match, not ignore status)
            is_file_match = (
                os.path.normpath(base_query_path) == os.path.normpath(rel_path_file)
                or os.path.normpath(base_query_path) == os.path.normpath(filename)
                # Removed 'or os.path.normpath(base_query_path) == os.path.normpath(full_path_file)'
                # as full_path_file is absolute, base_query_path is usually relative or filename.
                or fnmatch.fnmatch(filename, base_query_path)
                or fnmatch.fnmatch(rel_path_file, base_query_path)
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
        path = match["path"]
        # The is_ignored function encapsulates all ignore/force-include rules.
        # If the path is force-included, is_ignored will return False.
        if not is_ignored(path):
            filtered_matches.append(match)
        else:
            logger.debug(f"Skipping ignored path: {path}")

    # --- Consolidate and Deduplicate Matches ---
    unique_matches: Dict[str, Dict[str, Any]] = {}
    for match in filtered_matches:  # Iterate over filtered_matches
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

    return sorted(list(unique_matches.values()), key=lambda x: x["path"])
