# ctxctx/ignore.py
import os
import logging
import fnmatch
from typing import Dict, Any, Set, List

logger = logging.getLogger("ctx")

class IgnoreManager:
    def __init__(self, config: Dict[str, Any], root_path: str):
        self.config = config
        self.root_path = root_path
        self._explicit_ignore_set: Set[str] = set()
        self._substring_ignore_patterns: List[str] = []
        self.init_ignore_set()

    def _load_patterns_from_file(self, filepath: str) -> Set[str]:
        """Loads ignore patterns from a given file."""
        patterns = set()
        full_filepath = os.path.join(self.root_path, filepath) if not os.path.isabs(filepath) else filepath

        if not os.path.isfile(full_filepath):
            logger.debug(f"Ignore file not found: {full_filepath}")
            return patterns

        try:
            with open(full_filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Ignore empty lines, comments, and lines starting with '!' (negation not supported for now)
                    if not line or line.startswith('#') or line.startswith('!'):
                        continue
                    
                    # Basic processing for .gitignore-like patterns:
                    # Remove leading/trailing slashes for general matching (can be refined later with pathspec)
                    if line.startswith('/'):
                        line = line[1:]
                    if line.endswith('/'):
                        line = line.rstrip('/')
                    patterns.add(line)
        except Exception as e:
            logger.warning(f"Could not load patterns from {full_filepath}: {e}")
        return patterns

    def init_ignore_set(self):
        """Initializes the ignore set based on current config."""
        self._explicit_ignore_set = set(self.config['EXPLICIT_IGNORE_NAMES'])
        self._substring_ignore_patterns = list(self.config['SUBSTRING_IGNORE_PATTERNS'])

        script_ignore_file_path = os.path.join(self.root_path, self.config['SCRIPT_DEFAULT_IGNORE_FILE'])
        self._explicit_ignore_set.update(self._load_patterns_from_file(script_ignore_file_path))

        if self.config['USE_GITIGNORE']:
            self._explicit_ignore_set.update(self._load_patterns_from_file(self.config['GITIGNORE_PATH']))

        for ignore_filename in self.config['ADDITIONAL_IGNORE_FILENAMES']:
            self._explicit_ignore_set.update(self._load_patterns_from_file(ignore_filename))

        logger.debug(f"Initialized explicit ignore set with {len(self._explicit_ignore_set)} patterns.")
        logger.debug(f"Initialized substring ignore patterns with {len(self._substring_ignore_patterns)} patterns.")

    def is_ignored(self, full_path: str) -> bool:
        """
        Checks if a path should be ignored based on global ignore patterns.
        This function handles both explicit and substring matches, and basic glob patterns.
        """
        try:
            rel_path = os.path.relpath(full_path, self.root_path)
        except ValueError:
            logger.debug(f"Path '{full_path}' is not relative to root '{self.root_path}'. Treating as ignored.")
            return True

        if rel_path == '.':
            return False

        base_name = os.path.basename(full_path)
        rel_path_parts = rel_path.split(os.sep)

        # 1. Check against explicit ignore names/patterns (from EXPLICIT_IGNORE_NAMES, .gitignore, etc.)
        for p in self._explicit_ignore_set:
            # Check exact name/path match (e.g., 'node_modules', 'build')
            if p == base_name or p == rel_path:
                logger.debug(f"Ignored by exact pattern match: {full_path} (pattern: {p})")
                return True

            # Check glob patterns against full relative path (e.g., '*.pyc', 'src/*.js')
            if fnmatch.fnmatch(rel_path, p):
                logger.debug(f"Ignored by relative path glob match: {full_path} (pattern: {p})")
                return True
            
            # Check glob patterns against base name (e.g., 'temp*', 'foo.log')
            if fnmatch.fnmatch(base_name, p):
                logger.debug(f"Ignored by base name glob match: {full_path} (pattern: {p})")
                return True

            # Check if any component in the relative path matches the pattern
            # This handles deep directory ignores like `node_modules` or `__pycache__`
            # or `logs/` (where pattern 'logs' is in set)
            if any(fnmatch.fnmatch(part, p) for part in rel_path_parts):
                logger.debug(f"Ignored by path component glob match: {full_path} (pattern: {p})")
                return True

        # 2. Check against substring ignore patterns (e.g., 'package-lock.json')
        if any(pattern.lower() in rel_path.lower() for pattern in self._substring_ignore_patterns):
            logger.debug(f"Ignored by substring pattern match: {full_path} (rel_path: {rel_path})")
            return True

        return False