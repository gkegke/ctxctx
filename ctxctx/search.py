# ctxctx/search.py
import os
import re
import fnmatch
from typing import List, Dict, Any, Callable, Tuple
import logging

logger = logging.getLogger("ctx")

def _parse_line_ranges(ranges_str: str) -> List[Tuple[int, int]]:
    """
    Parses a string like '1,50:80,200' into a list of (start, end) tuples.
    Returns an empty list if parsing fails for any segment.
    """
    parsed_ranges: List[Tuple[int, int]] = []
    if not ranges_str:
        return parsed_ranges

    individual_range_strs = ranges_str.split(':')
    for lr_str in individual_range_strs:
        try:
            start_s, end_s = lr_str.split(',')
            start = int(start_s)
            end = int(end_s)
            # Basic validation: start should be <= end, and both positive
            if start <= 0 or end <= 0 or start > end:
                logger.warning(f"Invalid line range format '{lr_str}': Start and end lines must be positive, and start <= end. Skipping.")
                continue
            parsed_ranges.append((start, end))
        except ValueError:
            logger.warning(f"Invalid line range format '{lr_str}'. Expected 'start,end'. Skipping.")
            return [] # If any part fails, assume no valid ranges from this string
    return parsed_ranges

def find_matches(query: str, root: str, is_ignored: Callable[[str], bool], search_max_depth: int) -> List[Dict[str, Any]]:
    """
    Finds files matching the given query within the root directory.
    Supports exact paths, glob patterns, and multiple line ranges.
    :param query: The query string (e.g., 'src/file.py', 'foo.js:10,20:30,40', '*.md').
    :param root: The root directory to start the search from.
    :param is_ignored: A callable function to check if a path should be ignored.
    :param search_max_depth: Maximum directory depth to traverse for file content search.
    :return: A list of dictionaries, each containing 'path' and optional 'line_ranges'.
    """
    matches: List[Dict[str, Any]] = []

    # Strategy: Split on the first colon to separate path/glob from potential line ranges
    query_parts = query.split(':', 1)
    base_query_path = query_parts[0]
    target_line_ranges: List[Tuple[int, int]] = []

    if len(query_parts) > 1:
        # Attempt to parse line ranges from the second part of the split
        parsed_ranges = _parse_line_ranges(query_parts[1])
        if parsed_ranges:
            target_line_ranges = parsed_ranges
        else:
            # If the part after the colon is NOT a valid line range (e.g., 'my_dir:subdir'),
            # then treat the entire original query as a path/glob and ignore line range parsing.
            logger.debug(f"Part after first colon in '{query}' is not a valid line range. Treating as full path/glob query.")
            base_query_path = query # Revert to original query as full path/glob
            target_line_ranges = [] # Ensure no line ranges are applied

    # Handle absolute paths directly first
    if os.path.isabs(base_query_path):
        if os.path.exists(base_query_path) and not is_ignored(base_query_path):
            if os.path.isfile(base_query_path):
                matches.append({'path': base_query_path, 'line_ranges': target_line_ranges})
                logger.debug(f"Added exact absolute file match: {base_query_path} with ranges {target_line_ranges}")
            elif os.path.isdir(base_query_path):
                # If an absolute directory is given, include all non-ignored files within it.
                # Line ranges don't apply to directory queries.
                logger.debug(f"Searching absolute directory: {base_query_path}")
                for dirpath, _, filenames in os.walk(base_query_path):
                    current_depth = dirpath[len(base_query_path):].count(os.sep)
                    if current_depth >= search_max_depth:
                        logger.debug(f"Max search depth ({search_max_depth}) reached for sub-path: {dirpath}. Pruning.")
                        continue # Don't descend further
                    for filename in filenames:
                        full_path = os.path.join(dirpath, filename)
                        if not is_ignored(full_path):
                            matches.append({'path': full_path, 'line_ranges': []}) # No specific ranges for dir matches
                            logger.debug(f"Added file from absolute directory search: {full_path}")
        return matches # Return immediately for absolute paths

    # Handle relative path, partial name, and glob matches
    for dirpath, dirnames, filenames in os.walk(root):
        current_depth = dirpath[len(root):].count(os.sep)
        if current_depth >= search_max_depth and dirpath != root:
            logger.debug(f"Reached max search depth ({search_max_depth}) at {dirpath}. Pruning.")
            dirnames[:] = [] # Don't descend further
            continue

        # Prune ignored directories from os.walk traversal
        dirnames[:] = [d for d in dirnames if not is_ignored(os.path.join(dirpath, d))]
 # Line above was missing a closing parenthesis. Added it.

        # Check for directory matches (based on base_query_path)
        # Note: Iterate over a copy of dirnames to allow modification
        for dirname in list(dirnames):
            full_path_dir = os.path.join(dirpath, dirname)
            rel_path_dir = os.path.relpath(full_path_dir, root)

            # Prioritize exact match for directory before glob/substring
            # This handles cases like `ctx my_folder/`
            if rel_path_dir == base_query_path.rstrip(os.sep) or dirname == base_query_path.rstrip(os.sep):
                logger.debug(f"Exact directory match: {full_path_dir}")
                # Include all non-ignored files within this directory (recursive)
                for d_dirpath, _, d_filenames in os.walk(full_path_dir):
                    sub_depth = d_dirpath[len(full_path_dir):].count(os.sep)
                    if current_depth + sub_depth >= search_max_depth:
                        logger.debug(f"Max search depth ({search_max_depth}) reached for sub-path: {d_dirpath}. Pruning.")
                        continue
                    for d_filename in d_filenames:
                        d_full_path = os.path.join(d_dirpath, d_filename)
                        if not is_ignored(d_full_path):
                            matches.append({'path': d_full_path, 'line_ranges': []}) # No specific ranges for dir matches
                            logger.debug(f"Added file from exact directory search: {d_full_path}")
                dirnames.remove(dirname) # Already processed this directory, skip further os.walk traversal of its children
                continue

            # Check if directory name or its relative path matches glob/substring
            # This handles cases like `ctx src/my*` or `ctx *config/`
            if fnmatch.fnmatch(dirname, base_query_path) or fnmatch.fnmatch(rel_path_dir, base_query_path) or \
               base_query_path.lower() in dirname.lower() or base_query_path.lower() in rel_path_dir.lower():
                logger.debug(f"Glob/substring directory match: {full_path_dir}")
                for d_dirpath, _, d_filenames in os.walk(full_path_dir):
                    sub_depth = d_dirpath[len(full_path_dir):].count(os.sep)
                    if current_depth + sub_depth >= search_max_depth:
                        logger.debug(f"Max search depth ({search_max_depth}) reached for sub-path: {d_dirpath}. Pruning.")
                        continue
                    for d_filename in d_filenames:
                        d_full_path = os.path.join(d_dirpath, d_filename)
                        if not is_ignored(d_full_path):
                            matches.append({'path': d_full_path, 'line_ranges': []}) # No specific ranges for dir matches
                            logger.debug(f"Added file from glob/substring directory search: {d_full_path}")
                dirnames.remove(dirname) # Already processed, avoid redundant traversal


        # Check for file matches
        for filename in filenames:
            full_path_file = os.path.join(dirpath, filename)
            if is_ignored(full_path_file):
                logger.debug(f"Skipping ignored file: {full_path_file}")
                continue

            rel_path_file = os.path.relpath(full_path_file, root)

            # Check if filename or its relative path matches query (or glob)
            # Use os.path.normpath for consistent comparison (e.g., removing '..' or '.' components)
            is_direct_match = (
                os.path.normpath(base_query_path) == os.path.normpath(rel_path_file) or
                os.path.normpath(base_query_path) == os.path.normpath(filename) or
                os.path.normpath(base_query_path) == os.path.normpath(full_path_file)
            )
            is_glob_or_substring_match = (
                fnmatch.fnmatch(filename, base_query_path) or
                fnmatch.fnmatch(rel_path_file, base_query_path) or
                base_query_path.lower() in filename.lower() or
                base_query_path.lower() in rel_path_file.lower()
            )

            if is_direct_match or is_glob_or_substring_match:
                # Apply line filters only if the original query was specific to this file AND had ranges.
                # For general glob/partial matches (where target_line_ranges is empty), we want the whole file.
                if is_direct_match and target_line_ranges:
                     matches.append({'path': full_path_file, 'line_ranges': target_line_ranges})
                     logger.debug(f"Specific file match: {full_path_file} with line ranges {target_line_ranges}")
                else: # For general glob/partial matches, include the whole file (no specific ranges)
                    matches.append({'path': full_path_file, 'line_ranges': []})
                    logger.debug(f"General file match: {full_path_file}")

    # Remove duplicates based on 'path' and then sort.
    # When duplicates exist, merge their line_ranges.
    unique_matches: Dict[str, Dict[str, Any]] = {}
    for match in matches:
        path = match['path']
        current_line_ranges = match.get('line_ranges', [])

        if path not in unique_matches:
            unique_matches[path] = {'path': path, 'line_ranges': current_line_ranges}
        else:
            # If a match for this path already exists, combine its line_ranges
            existing_line_ranges = unique_matches[path].get('line_ranges', [])
            
            # Combine and de-duplicate ranges
            # Use a set of tuples to handle de-duplication, then convert back to list and sort
            combined_ranges_set = set(existing_line_ranges + current_line_ranges)
            unique_matches[path]['line_ranges'] = sorted(list(combined_ranges_set))
            logger.debug(f"Merged line ranges for existing match {path}.")

    return sorted(list(unique_matches.values()), key=lambda x: x['path'])