# ctxctx/ignore.py
import fnmatch
import logging
import os
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class IgnoreManager:
    def __init__(
        self,
        config: Dict[str, Any],
        root_path: str,
        force_include_patterns: Optional[List[str]] = None,
    ):
        self.config = config
        self.root_path = root_path
        self._explicit_ignore_set: Set[str] = set()
        self._substring_ignore_patterns: List[str] = []
        self._force_include_patterns: List[str] = (
            force_include_patterns if force_include_patterns is not None else []
        )
        self.init_ignore_set()

    def _load_patterns_from_file(self, filepath: str) -> Set[str]:
        """Loads ignore patterns from a given file."""
        patterns: Set[str] = set()
        full_filepath = filepath

        if not os.path.isfile(full_filepath):
            logger.debug(f"Ignore file not found: {full_filepath}")
            return patterns

        try:
            with open(full_filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # A proper .gitignore parser would handle '!' for negations,
                    # but for now we only filter comments. Force-includes are handled
                    # by separate command-line arguments.
                    if not line or line.startswith("#"):  # Changed: Removed line.startswith("!")
                        continue

                    # .gitignore patterns:
                    # 'foo/' matches directory foo
                    # '/foo' matches foo only at root
                    # 'foo' matches foo anywhere
                    # We store paths relative to the root for consistency, and strip leading
                    # '/' if present as fnmatch works on filenames/relative paths, and the
                    # "match anywhere" glob (e.g. '**/foo') is handled by the search logic
                    # or explicit checks.
                    if line.startswith("/"):
                        line = line[1:]
                    # Trailing '/' is often significant for directories, but fnmatch
                    # typically operates on files. For simplicity, we'll keep it for
                    # explicit matches, but allow globs to match regardless.
                    # For directory patterns like "foo/", fnmatch might not directly
                    # match "foo/bar.txt". The IgnoreManager's is_ignored logic needs
                    # to handle this by checking both file and directory path parts.
                    patterns.add(line)
        except Exception as e:
            logger.warning(f"Could not load patterns from {full_filepath}: {e}")
        return patterns

    def _is_explicitly_force_included(self, full_path: str) -> bool:
        """Checks if the given full_path matches any of the force_include_patterns
        provided by the user. Force include patterns support globs and relative
        paths.
        """
        try:
            rel_path = os.path.relpath(full_path, self.root_path)
        except ValueError:
            logger.debug(
                f"Path '{full_path}' is not relative to root "
                f"'{self.root_path}'. Treating as not force-included."
            )
            return False

        norm_rel_path = os.path.normpath(rel_path)
        base_name = os.path.basename(full_path)
        rel_path_parts = norm_rel_path.split(os.sep)

        for pattern in self._force_include_patterns:
            norm_pattern = os.path.normpath(pattern)

            # Direct match
            if norm_pattern == norm_rel_path:
                logger.debug(
                    f"FORCE INCLUDE: Exact relative path match for "
                    f"'{full_path}' with pattern '{pattern}'"
                )
                return True

            # Glob match against full relative path
            if fnmatch.fnmatch(norm_rel_path, norm_pattern):
                logger.debug(
                    f"FORCE INCLUDE: Glob relative path match for "
                    f"'{full_path}' with pattern '{pattern}'"
                )
                return True

            # Glob match against base name
            if fnmatch.fnmatch(base_name, norm_pattern):
                logger.debug(
                    f"FORCE INCLUDE: Glob base name match for '{full_path}' "
                    f"with pattern '{pattern}'"
                )
                return True

            # Glob match against any path component (e.g., "foo" matches "dir/foo/bar.txt")
            if any(fnmatch.fnmatch(part, norm_pattern) for part in rel_path_parts):
                logger.debug(
                    f"FORCE INCLUDE: Path component glob match for "
                    f"'{full_path}' with pattern '{pattern}'"
                )
                return True

        return False

    def init_ignore_set(self):
        """Initializes the ignore set based on current config."""
        self._explicit_ignore_set = set(self.config["EXPLICIT_IGNORE_NAMES"])
        self._substring_ignore_patterns = list(self.config["SUBSTRING_IGNORE_PATTERNS"])

        script_ignore_file_path = os.path.join(
            self.root_path, self.config["SCRIPT_DEFAULT_IGNORE_FILE"]
        )
        self._explicit_ignore_set.update(self._load_patterns_from_file(script_ignore_file_path))

        if self.config["USE_GITIGNORE"]:
            self._explicit_ignore_set.update(
                self._load_patterns_from_file(
                    os.path.join(self.root_path, self.config["GITIGNORE_PATH"])
                )
            )

        for ignore_filename in self.config["ADDITIONAL_IGNORE_FILENAMES"]:
            self._explicit_ignore_set.update(
                self._load_patterns_from_file(os.path.join(self.root_path, ignore_filename))
            )

        logger.debug(
            f"Initialized explicit ignore set with " f"{len(self._explicit_ignore_set)} patterns."
        )
        logger.debug(
            f"Initialized substring ignore patterns with "
            f"{len(self._substring_ignore_patterns)} patterns."
        )

    def is_ignored(self, full_path: str) -> bool:
        """Checks if a path should be ignored based on global ignore patterns.
        This function handles both explicit and substring matches, and basic
        glob patterns. It prioritizes force-include rules: if a path is
        force-included, it is never ignored.
        """
        if self._is_explicitly_force_included(full_path):
            return False

        try:
            rel_path = os.path.relpath(full_path, self.root_path)
        except ValueError:
            logger.debug(
                f"Path '{full_path}' is not relative to root "
                f"'{self.root_path}'. Treating as ignored."
            )
            return True

        if rel_path == ".":
            return False

        base_name = os.path.basename(full_path)
        rel_path_parts = rel_path.split(os.sep)

        for p in self._explicit_ignore_set:
            norm_p = os.path.normpath(p)

            # Check if norm_p matches the relative path, base name, or any part
            # using direct match or glob patterns.
            is_match = (
                norm_p == rel_path
                or norm_p == base_name
                or fnmatch.fnmatch(rel_path, norm_p)
                or fnmatch.fnmatch(base_name, norm_p)
                or any(fnmatch.fnmatch(part, norm_p) for part in rel_path_parts)
            )

            if is_match:
                logger.debug(f"Ignored by explicit pattern: {full_path} (pattern: {p})")
                return True

        if any(pattern.lower() in rel_path.lower() for pattern in self._substring_ignore_patterns):
            logger.debug(
                f"Ignored by substring pattern match: {full_path} " f"(rel_path: {rel_path})"
            )
            return True

        return False
