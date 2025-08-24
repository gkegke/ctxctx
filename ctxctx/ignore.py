# ctxctx/ignore.py
import fnmatch
import logging
import os
from pathlib import Path
from typing import List, Optional, Set

from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern

from .config import Config

logger = logging.getLogger(__name__)


class IgnoreManager:
    """
    Manages ignore rules for file system traversal.
    Combines explicit, substring, and .gitignore rules, with force-include overrides,
    using `pathspec` for consistent and efficient gitignore-style matching.
    """

    def __init__(
        self,
        config: Config,
        force_include_patterns: Optional[List[str]] = None,
    ):
        self.config = config
        self.root_path: Path = self.config.root
        self._hardcoded_explicit_names: Set[str] = set()
        self._substring_ignore_patterns: List[str] = []
        self._force_include_patterns: List[str] = (
            force_include_patterns if force_include_patterns is not None else []
        )
        self.pathspec: Optional[PathSpec] = None
        self.init_ignore_set()

    def _is_explicitly_force_included(self, file_path: Path) -> bool:
        """Checks if a file_path is explicitly force-included by user queries."""
        try:
            relative_file_path = file_path.relative_to(self.root_path)
            relative_file_path_str = relative_file_path.as_posix()
        except ValueError:
            return False

        base_name = file_path.name

        for pattern_str in self._force_include_patterns:
            normalized_pattern_path = Path(pattern_str.rstrip(os.sep))
            if relative_file_path == normalized_pattern_path:
                return True
            if pattern_str.endswith(os.sep) or (self.root_path / pattern_str).is_dir():
                try:
                    relative_file_path.relative_to(pattern_str.rstrip(os.sep))
                    return True
                except ValueError:
                    pass
            if fnmatch.fnmatch(relative_file_path_str, pattern_str) or fnmatch.fnmatch(
                base_name, pattern_str
            ):
                return True
            if file_path.is_dir():
                try:
                    normalized_pattern_path.relative_to(relative_file_path)
                    return True
                except ValueError:
                    pass
        return False

    def init_ignore_set(self) -> None:
        """Initializes the ignore sets based on current config."""
        self._hardcoded_explicit_names = set(self.config.explicit_ignore_names)
        self._substring_ignore_patterns = list(self.config.substring_ignore_patterns)

        all_patterns = []
        files_to_load = []

        if self.config.use_gitignore:
            files_to_load.append(self.root_path / self.config.gitignore_path)
        # REMOVED: The script's default ignore file is no longer loaded as a separate file.
        # Its patterns are now part of config.explicit_ignore_names.
        # files_to_load.append(self.root_path / self.config.script_default_ignore_file)
        for fname in self.config.additional_ignore_filenames:
            files_to_load.append(self.root_path / fname)

        for file_path in files_to_load:
            if file_path.is_file():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        all_patterns.extend(f.readlines())
                    logger.debug(f"Loaded gitignore rules from: {file_path}")
                except IOError as e:
                    logger.warning(f"Could not read ignore file '{file_path}': {e}")

        if all_patterns:
            self.pathspec = PathSpec.from_lines(GitWildMatchPattern, all_patterns)
            logger.debug(
                f"Initialized pathspec with {len(all_patterns)} gitignore-style patterns."
            )
        else:
            self.pathspec = None

    def is_ignored(self, full_path: Path) -> bool:
        """
        Checks if a path should be ignored.
        Order of precedence:
        1. Force-include rules (overrides all ignores).
        2. Path outside root directory check.
        3. Gitignore-style patterns via `pathspec`.
        4. Hardcoded explicit name patterns (fnmatch).
        5. Substring patterns.
        """
        if self._is_explicitly_force_included(full_path):
            return False

        try:
            rel_path = full_path.relative_to(self.root_path)
        except ValueError:
            return True

        if rel_path == Path("."):
            return False

        if self.pathspec and self.pathspec.match_file(rel_path.as_posix()):
            logger.debug(f"Ignored by gitignore-style rule: {full_path}")
            return True

        base_name = full_path.name
        rel_path_str = rel_path.as_posix()
        rel_path_parts = rel_path.parts
        for p in self._hardcoded_explicit_names:
            is_match = (
                p == rel_path_str
                or p == base_name
                or fnmatch.fnmatch(rel_path_str, p)
                or fnmatch.fnmatch(base_name, p)
                or any(fnmatch.fnmatch(part, p) for part in rel_path_parts)
            )
            if is_match:
                logger.debug(f"Ignored by hardcoded explicit pattern: {full_path} (pattern: {p})")
                return True

        if any(
            pattern.lower() in rel_path_str.lower() for pattern in self._substring_ignore_patterns
        ):
            logger.debug(f"Ignored by substring pattern match: {full_path}")
            return True

        return False
