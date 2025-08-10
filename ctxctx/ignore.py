# ctxctx/ignore.py
import fnmatch
import logging
import os
from pathlib import Path
from typing import Callable, List, Optional, Set  # Added Callable

# Fix: Revert parse_files import. Only parse_gitignore is needed.
from gitignore_parser import parse_gitignore

from .config import Config

logger = logging.getLogger(__name__)


class IgnoreManager:
    """
    Manages ignore rules for file system traversal.
    Combines explicit, substring, and .gitignore rules, with force-include overrides.
    """

    def __init__(
        self,
        config: Config,
        force_include_patterns: Optional[List[str]] = None,
    ):
        self.config = config
        self.root_path: Path = self.config.root

        # Patterns from config that are not gitignore-style (simple explicit names)
        # These act as a fallback if no .gitignore or other specific ignore files are present
        self._hardcoded_explicit_names: Set[str] = set()

        # Fix: Change _gitignore_matcher to be a list of matchers
        self._gitignore_matchers: List[Callable[[str], bool]] = []

        # Substring patterns remain separate as they are not glob/gitignore style
        self._substring_ignore_patterns: List[str] = []

        self._force_include_patterns: List[str] = (
            force_include_patterns if force_include_patterns is not None else []
        )
        self.init_ignore_set()

    def _is_explicitly_force_included(self, file_path: Path) -> bool:
        """Checks if an *absolute* file_path is explicitly force-included by user queries."""
        try:
            # Convert file_path to be relative to the root for consistent pattern matching
            relative_file_path = file_path.relative_to(self.root_path)
            relative_file_path_str = relative_file_path.as_posix()
        except ValueError:
            # If file_path is not under root, it cannot be force-included by a relative pattern.
            return False

        # Get the basename for simple filename matching
        base_name = file_path.name

        for pattern_str in self._force_include_patterns:
            # Normalize pattern_str to a Path object for consistent comparison,
            # removing trailing slash
            normalized_pattern_path = Path(pattern_str.rstrip(os.sep))

            # Case 1: Exact match of relative paths
            if relative_file_path == normalized_pattern_path:
                logger.debug(
                    f"Path {file_path} force-included by exact relative path match: '{pattern_str}'"
                )
                return True

            # Case 2: Pattern is a directory path, and file_path is inside it
            # This handles queries like "force:foo/" and files like "foo/bar.txt"
            # It relies on relative_to() which correctly identifies if a path is inside another.
            # Check if the pattern (as string or path) suggests a directory
            if normalized_pattern_path.is_dir() or pattern_str.endswith(os.sep):
                try:
                    # Check if relative_file_path is a sub-path of normalized_pattern_path
                    relative_file_path.relative_to(normalized_pattern_path)
                    logger.debug(
                        f"Path {file_path} force-included by directory pattern: '{pattern_str}'"
                    )
                    return True
                except ValueError:
                    pass  # Not a child of this directory pattern

            # Case 3: Glob match on string representation of relative path
            if fnmatch.fnmatch(relative_file_path_str, pattern_str):
                logger.debug(f"Path {file_path} force-included by glob match: '{pattern_str}'")
                return True

            # FIX: Case 4: Glob match on basename, for simple filename patterns like
            # '.gitignore' or '*.log'
            if fnmatch.fnmatch(base_name, pattern_str):
                logger.debug(
                    f"Path {file_path} force-included by basename glob match: '{pattern_str}'"
                )
                return True
        return False

    def init_ignore_set(self) -> None:
        """Initializes the ignore sets based on current config."""
        # Load hardcoded explicit names (simple fnmatch patterns from config defaults)
        self._hardcoded_explicit_names = set(self.config.explicit_ignore_names)

        # Load substring ignore patterns (unique to ctxctx)
        self._substring_ignore_patterns = list(self.config.substring_ignore_patterns)

        # Prepare list of file paths for gitignore-parser
        gitignore_style_files_to_load: List[Path] = []

        # 1. Script default ignore file (e.g., prompt_builder_ignore.txt)
        script_ignore_file_path = self.root_path / self.config.script_default_ignore_file
        if script_ignore_file_path.is_file():
            gitignore_style_files_to_load.append(script_ignore_file_path)

        # 2. Main .gitignore
        if self.config.use_gitignore:
            gitignore_path = self.root_path / self.config.gitignore_path
            if gitignore_path.is_file():
                gitignore_style_files_to_load.append(gitignore_path)

        # 3. Additional ignore filenames (e.g., .dockerignore)
        for ignore_filename in self.config.additional_ignore_filenames:
            additional_ignore_path = self.root_path / ignore_filename
            if additional_ignore_path.is_file():
                gitignore_style_files_to_load.append(additional_ignore_path)

        # Fix: Iterate and create a matcher for each file, adding to _gitignore_matchers list
        self._gitignore_matchers = []  # Clear any previous matchers
        if gitignore_style_files_to_load:
            for file_path in gitignore_style_files_to_load:
                try:
                    # parse_gitignore takes a single file path
                    matcher = parse_gitignore(file_path, base_dir=self.root_path)
                    self._gitignore_matchers.append(matcher)
                    logger.debug(f"Loaded gitignore rules from: {file_path}")
                except Exception as e:
                    # Log as warning but don't stop processing other files
                    logger.warning(f"Error initializing gitignore matcher for '{file_path}': {e}")

        logger.debug(
            f"Initialized hardcoded explicit ignore set with "
            f"{len(self._hardcoded_explicit_names)} patterns."
        )
        logger.debug(
            f"Initialized substring ignore patterns with "
            f"{len(self._substring_ignore_patterns)} patterns."
        )
        logger.debug(f"Initialized {len(self._gitignore_matchers)} gitignore-style matchers.")

    def is_ignored(self, full_path: Path) -> bool:
        """Checks if a path should be ignored based on global ignore patterns.
        This function handles force-include, gitignore-style rules, hardcoded
        explicit patterns (fnmatch), and substring matches, in order of precedence.
        """
        # Highest precedence: Force include rules
        if self._is_explicitly_force_included(full_path):
            return False

        # Paths outside the root directory are always ignored
        try:
            rel_path = full_path.relative_to(self.root_path)
            rel_path_str = str(rel_path)
        except ValueError:
            logger.debug(
                f"Path '{full_path}' is not relative to root "
                f"'{self.root_path}'. Treating as ignored (e.g., external paths)."
            )
            return True

        # The root directory itself is never ignored
        if rel_path == Path("."):
            return False

        # 1. Check gitignore-style patterns (from .gitignore, prompt_builder_ignore.txt etc.)
        # Fix: Iterate through all loaded matchers
        for matcher in self._gitignore_matchers:
            # Pass the absolute path string to the gitignore_parser matcher.
            # The library is designed to handle absolute paths, resolving them
            # and then matching them against rules relative to its base_dir.
            if matcher(str(full_path)):
                logger.debug(f"Ignored by gitignore-style rule: {full_path}")
                return True

        # 2. Check hardcoded explicit names (using fnmatch, for patterns not handled by
        # gitignore files, or as a default)
        # These patterns are simpler globs applied to base name, relative path, or path parts.
        base_name = full_path.name
        rel_path_parts = rel_path.parts
        for p in self._hardcoded_explicit_names:
            is_match = (
                p == rel_path_str  # Exact relative path match
                or p == base_name  # Exact base name match
                or fnmatch.fnmatch(rel_path_str, p)  # Glob match on relative path
                or fnmatch.fnmatch(base_name, p)  # Glob match on base name
                or any(
                    fnmatch.fnmatch(part, p) for part in rel_path_parts
                )  # Glob match on any path component
            )
            if is_match:
                logger.debug(f"Ignored by hardcoded explicit pattern: {full_path} (pattern: {p})")
                return True

        # 3. Check substring patterns (lowest precedence)
        if any(
            pattern.lower() in rel_path_str.lower() for pattern in self._substring_ignore_patterns
        ):
            logger.debug(
                f"Ignored by substring pattern match: {full_path} " f"(rel_path: {rel_path_str})"
            )
            return True

        return False
