# [FILE: /ctxctx/resolver.py] - Full File Change
import logging
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

# Changed: Import PathSpec from pathspec instead of Matcher from gitignore_parser
from pathspec import (
    PathSpec,  # type: ignore # Adding type ignore as pathspec might not have full type stubs
)

from .config import Config
from .search import find_matches

logger = logging.getLogger(__name__)


class FileResolver:
    """
    Resolves the final list of files to include based on profile rules and queries.
    The resolution logic is as follows:
    1. Define a base set of files:
       - If `include` patterns or `queries` are provided, the base set starts empty.
       - Otherwise (e.g., only `exclude` is used), the base set starts with ALL
         non-ignored project files.
    2. Populate the set:
       - Add all files matching `include` patterns (from the master list of all files).
       - Add all files matching `queries` (from the master list of all files).
    3. Prune the set:
       - Remove all files from the populated set that match `exclude` patterns.
    This ensures that `include` and `queries` act as positive selectors, while `exclude`
    can act on the entire project if no positive selectors are given.
    """

    def __init__(self, config: Config):
        self.config = config
        self.root_path = config.root

    def _apply_glob_patterns(self, file_paths: Set[Path], patterns: List[str]) -> Set[Path]:
        """Helper to find all files in file_paths that match any of the glob patterns.
        Uses pathspec for consistency with gitignore-style matching,
        which correctly interprets `**` and other patterns.
        """
        if not patterns:
            return set()

        # Create a PathSpec matcher from the patterns
        # Use 'gitwildmatch' for gitignore-style pattern matching
        pathspec_matcher = PathSpec.from_lines("gitwildmatch", patterns)

        matched_files = set()
        for file_path in file_paths:
            try:
                # PathSpec expects paths relative to the root it's defined for.
                # In our case, the patterns are defined relative to self.root_path.
                relative_path_str = file_path.relative_to(self.root_path).as_posix()
            except ValueError:
                # If file_path is not under root, it cannot be matched by relative patterns.
                continue

            if pathspec_matcher.match_file(relative_path_str):
                matched_files.add(file_path)
        return matched_files

    def resolve(
        self,
        all_project_files: List[Path],
        include_patterns: List[str],
        exclude_patterns: List[str],
        queries: List[str],
    ) -> Tuple[List[Dict[str, Any]], Set[Path]]:
        """
        Executes the file resolution logic.

        :param all_project_files: The master list of all non-globally-ignored files.
        :param include_patterns: Glob patterns from the profile's 'include' key.
        :param exclude_patterns: Glob patterns from the profile's 'exclude' key.
        :param queries: Specific queries from profile 'queries' and the CLI.
        :return: A tuple containing (list of matched file data, set of unique matched paths).
        """
        all_project_files_set = set(all_project_files)
        logger.debug(f"Resolver starting with {len(all_project_files_set)} candidate files.")

        candidate_files: Set[Path]
        # 1. Establish the base set of candidates.
        #    - If 'include' or 'queries' are specified, we start with an empty set and add to it.
        #    - Otherwise (e.g., only 'exclude' is used), we start with all files.
        if include_patterns or queries:
            candidate_files = set()
        else:
            candidate_files = all_project_files_set.copy()

        # 2a. Add files based on 'include' patterns.
        if include_patterns:
            included_by_rule = self._apply_glob_patterns(all_project_files_set, include_patterns)
            candidate_files.update(included_by_rule)
            logger.info(f"Applied 'include' rules, found {len(included_by_rule)} files.")

        # 2b. Add files based on explicit 'queries' from profile and CLI.
        logger.info(f"Processing {len(queries)} explicit queries...")
        query_matches: List[Dict[str, Any]] = []
        if queries:
            for query in queries:
                try:
                    matches = find_matches(query, all_project_files, self.config)
                    if matches:
                        query_matches.extend(matches)
                    else:
                        logger.warning(f"⚠️ No non-ignored matches found for query: '{query}'")
                except Exception as e:
                    logger.error(f"Error processing query '{query}': {e}")
                    continue
            # Add the paths from query matches to our candidate set
            for match in query_matches:
                candidate_files.add(match["path"])

        # 3. Apply 'exclude' patterns to the collected set of candidates.
        if exclude_patterns:
            excluded_files = self._apply_glob_patterns(candidate_files, exclude_patterns)
            candidate_files -= excluded_files
            logger.info(
                f"Applied 'exclude' rules, removing {len(excluded_files)} files. "
                f"{len(candidate_files)} remain."
            )

        # 4. Consolidate all results, merging line ranges where necessary.
        consolidated_matches: Dict[Path, Dict[str, Any]] = {}

        # First, add files from the include/exclude logic (which have no line ranges)
        for _path in sorted(list(candidate_files)):
            consolidated_matches[_path] = {"path": _path, "line_ranges": []}

        # Next, add or merge files from the query logic, which might have line ranges
        for match in query_matches:
            path: Path = match["path"]
            # Only process queries that survived the exclusion step
            if path not in candidate_files:
                continue

            current_line_ranges = match.get("line_ranges", [])
            existing_ranges = consolidated_matches.get(path, {}).get("line_ranges", [])

            combined_ranges = sorted(
                list(set(tuple(r) for r in existing_ranges + current_line_ranges))
            )
            consolidated_matches[path] = {
                "path": path,
                "line_ranges": [list(r) for r in combined_ranges],
            }

        all_matched_files_data = sorted(
            list(consolidated_matches.values()), key=lambda x: str(x["path"])
        )
        unique_matched_paths = set(consolidated_matches.keys())

        logger.info(f"Resolver finished. Final file count: {len(unique_matched_paths)}.")
        return all_matched_files_data, unique_matched_paths
