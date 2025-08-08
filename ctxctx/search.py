# ctxctx/search.py
import fnmatch
import logging
import os
from typing import Any, Callable, Dict, List, Tuple

logger = logging.getLogger(__name__)


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
                    "lines must be positive, and start <= end. Skipping."
                )
                continue
            parsed_ranges.append((start, end))
        except ValueError:
            logger.warning(
                f"Invalid line range format '{lr_str}'. Expected 'start,end'. " "Skipping."
            )
            return []
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
    matches: List[Dict[str, Any]] = []

    original_query = query
    if query.startswith("!"):
        query = query[1:]
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
            base_query_path = query
            target_line_ranges = []

    if os.path.isabs(base_query_path):
        if os.path.exists(base_query_path) and not is_ignored(base_query_path):
            if os.path.isfile(base_query_path):
                matches.append({"path": base_query_path, "line_ranges": target_line_ranges})
                logger.debug(
                    f"Added exact absolute file match: {base_query_path} "
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
                        if not is_ignored(full_path):
                            matches.append({"path": full_path, "line_ranges": []})
                            logger.debug(
                                f"Added file from absolute directory search: " f"{full_path}"
                            )
        return matches

    for dirpath, dirnames, filenames in os.walk(root):
        current_depth = dirpath[len(root) :].count(os.sep)
        if current_depth >= search_max_depth and dirpath != root:
            logger.debug(
                f"Reached max search depth ({search_max_depth}) at {dirpath}. " "Pruning."
            )
            dirnames[:] = []
            continue

        for dirname in list(dirnames):
            full_path_dir = os.path.join(dirpath, dirname)
            rel_path_dir = os.path.relpath(full_path_dir, root)

            if rel_path_dir == base_query_path.rstrip(os.sep) or dirname == base_query_path.rstrip(
                os.sep
            ):
                logger.debug(f"Exact directory match: {full_path_dir}")
                for d_dirpath, _, d_filenames in os.walk(full_path_dir):
                    sub_depth = d_dirpath[len(full_path_dir) :].count(os.sep)
                    if current_depth + sub_depth >= search_max_depth:
                        logger.debug(
                            f"Max search depth ({search_max_depth}) reached "
                            f"for sub-path: {d_dirpath}. Pruning."
                        )
                        continue
                    for d_filename in d_filenames:
                        d_full_path = os.path.join(d_dirpath, d_filename)
                        if not is_ignored(d_full_path):
                            matches.append({"path": d_full_path, "line_ranges": []})
                            logger.debug(
                                f"Added file from exact directory search: " f"{d_full_path}"
                            )
                dirnames.remove(dirname)
                continue

            if (
                fnmatch.fnmatch(dirname, base_query_path)
                or fnmatch.fnmatch(rel_path_dir, base_query_path)
                or base_query_path.lower() in dirname.lower()
                or base_query_path.lower() in rel_path_dir.lower()
            ):
                logger.debug(f"Glob/substring directory match: {full_path_dir}")
                for d_dirpath, _, d_filenames in os.walk(full_path_dir):
                    sub_depth = d_dirpath[len(full_path_dir) :].count(os.sep)
                    if current_depth + sub_depth >= search_max_depth:
                        logger.debug(
                            f"Max search depth ({search_max_depth}) reached "
                            f"for sub-path: {d_dirpath}. Pruning."
                        )
                        continue
                    for d_filename in d_filenames:
                        d_full_path = os.path.join(d_dirpath, d_filename)
                        if not is_ignored(d_full_path):
                            matches.append({"path": d_full_path, "line_ranges": []})
                            logger.debug(
                                f"Added file from glob/substring directory "
                                f"search: {d_full_path}"
                            )
                dirnames.remove(dirname)

        for filename in filenames:
            full_path_file = os.path.join(dirpath, filename)
            if is_ignored(full_path_file):
                logger.debug(f"Skipping ignored file: {full_path_file}")
                continue

            rel_path_file = os.path.relpath(full_path_file, root)

            is_direct_match = (
                os.path.normpath(base_query_path) == os.path.normpath(rel_path_file)
                or os.path.normpath(base_query_path) == os.path.normpath(filename)
                or os.path.normpath(base_query_path) == os.path.normpath(full_path_file)
            )
            is_glob_or_substring_match = (
                fnmatch.fnmatch(filename, base_query_path)
                or fnmatch.fnmatch(rel_path_file, base_query_path)
                or base_query_path.lower() in filename.lower()
                or base_query_path.lower() in rel_path_file.lower()
            )

            if is_direct_match or is_glob_or_substring_match:
                if is_direct_match and target_line_ranges:
                    matches.append({"path": full_path_file, "line_ranges": target_line_ranges})
                    logger.debug(
                        f"Specific file match: {full_path_file} with line "
                        f"ranges {target_line_ranges}"
                    )
                else:
                    matches.append({"path": full_path_file, "line_ranges": []})
                    logger.debug(f"General file match: {full_path_file}")

    unique_matches: Dict[str, Dict[str, Any]] = {}
    for match in matches:
        path = match["path"]
        current_line_ranges = match.get("line_ranges", [])

        if path not in unique_matches:
            unique_matches[path] = {
                "path": path,
                "line_ranges": current_line_ranges,
            }
        else:
            existing_line_ranges = unique_matches[path].get("line_ranges", [])

            combined_ranges_set = set(existing_line_ranges + current_line_ranges)
            unique_matches[path]["line_ranges"] = sorted(list(combined_ranges_set))
            logger.debug(f"Merged line ranges for existing match {path}.")

    return sorted(list(unique_matches.values()), key=lambda x: x["path"])
