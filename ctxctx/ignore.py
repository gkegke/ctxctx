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
                    if not line or line.startswith("#") or line.startswith("!"):
                        continue

                    if line.startswith("/"):
                        line = line[1:]
                    if line.endswith("/"):
                        line = line.rstrip("/")
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
                f"'{self.root_path}'. Treating as ignored."
            )
            return False

        norm_rel_path = os.path.normpath(rel_path)
        base_name = os.path.basename(full_path)
        rel_path_parts = norm_rel_path.split(os.sep)

        for pattern in self._force_include_patterns:
            norm_pattern = os.path.normpath(pattern)

            if norm_pattern == norm_rel_path:
                logger.debug(
                    f"FORCE INCLUDE: Exact relative path match for "
                    f"'{full_path}' with pattern '{pattern}'"
                )
                return True

            if fnmatch.fnmatch(norm_rel_path, norm_pattern):
                logger.debug(
                    f"FORCE INCLUDE: Glob relative path match for "
                    f"'{full_path}' with pattern '{pattern}'"
                )
                return True

            if fnmatch.fnmatch(base_name, norm_pattern):
                logger.debug(
                    f"FORCE INCLUDE: Glob base name match for '{full_path}' "
                    f"with pattern '{pattern}'"
                )
                return True

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

            if norm_p == base_name or norm_p == rel_path:
                logger.debug(f"Ignored by exact pattern match: {full_path} " f"(pattern: {p})")
                return True

            if fnmatch.fnmatch(rel_path, norm_p):
                logger.debug(
                    f"Ignored by relative path glob match: {full_path} " f"(pattern: {p})"
                )
                return True

            if fnmatch.fnmatch(base_name, norm_p):
                logger.debug(f"Ignored by base name glob match: {full_path} " f"(pattern: {p})")
                return True

            if any(fnmatch.fnmatch(part, norm_p) for part in rel_path_parts):
                logger.debug(
                    f"Ignored by path component glob match: {full_path} " f"(pattern: {p})"
                )
                return True

        if any(pattern.lower() in rel_path.lower() for pattern in self._substring_ignore_patterns):
            logger.debug(
                f"Ignored by substring pattern match: {full_path} " f"(rel_path: {rel_path})"
            )
            return True

        return False
