# ctxctx/tree.py
import logging
from pathlib import Path  # Added import
from typing import Callable, Set

from .config import Config  # Import Config class

logger = logging.getLogger(__name__)


def generate_tree_string(
    path: Path,  # Changed type hint
    is_ignored: Callable[[Path], bool],  # Changed Callable signature
    config: Config,  # Pass config object
    current_depth: int = 0,
    prefix: str = "",
    visited_paths: Set[Path] = None,  # Changed Set[str] to Set[Path]
) -> str:
    """Generates a string representation of the directory tree.
    :param path: The current directory path to traverse (Path object).
    :param is_ignored: A callable function to check if a path should be ignored.
    :param config: The Config object containing tree generation parameters like max_depth.
    :param current_depth: The current recursion depth (0 for the initial call).
    :param prefix: The string prefix for current level (for indentation).
    :param visited_paths: Set to keep track of visited paths to prevent infinite
                          recursion (symlinks).
    :return: A string representing the directory tree.
    """
    max_depth = config.tree_max_depth  # Get max_depth from config
    exclude_empty_dirs = config.tree_exclude_empty_dirs  # Get exclude_empty_dirs from config

    if visited_paths is None:
        visited_paths = set()

    if path in visited_paths:
        logger.debug(f"Skipping already visited path (likely symlink): {path}")
        return ""
    visited_paths.add(path)

    if current_depth > 0 and is_ignored(path):
        logger.debug(f"Ignoring path for tree generation: {path}")
        return ""

    if current_depth > max_depth:
        logger.debug(f"Max depth ({max_depth}) exceeded for path: {path}. Pruning.")
        return ""

    if not path.is_dir():  # Changed to Path.is_dir()
        logger.debug(f"Path is not a directory: {path}")
        return ""

    entries_to_process = []
    try:
        # Use iterdir() to get Path objects directly, then sort by name string
        all_entries = sorted(path.iterdir(), key=lambda p: p.name)
        for entry_path in all_entries:  # entry_path is already a Path object
            if not is_ignored(entry_path):
                entries_to_process.append(entry_path)
            else:
                logger.debug(f"Skipping ignored entry in tree: {entry_path}")
    except PermissionError:
        logger.warning(f"Permission denied accessing directory: {path}")
        return ""
    except Exception as e:
        logger.warning(f"Error listing directory {path}: {e}")
        return ""

    tree_lines = []
    has_meaningful_content_in_children = False

    for i, entry_path in enumerate(entries_to_process):  # entry_path is a Path object
        is_last = i == len(entries_to_process) - 1
        connector = "└── " if is_last else "├── "

        entry_line = prefix + connector + entry_path.name  # Use .name for display

        if entry_path.is_dir():  # Changed to Path.is_dir()
            if current_depth < max_depth:
                extension = "    " if is_last else "│   "
                child_tree_output = generate_tree_string(
                    entry_path,  # Pass Path object
                    is_ignored,
                    config,  # Pass the config object
                    current_depth + 1,
                    prefix + extension,
                    visited_paths,
                )
                if child_tree_output:
                    tree_lines.append(entry_line)
                    tree_lines.append(child_tree_output)
                    has_meaningful_content_in_children = True
                elif not exclude_empty_dirs:
                    tree_lines.append(entry_line)
                    has_meaningful_content_in_children = True
                else:
                    logger.debug(
                        f"Pruning empty or all-ignored directory from tree: " f"{entry_path}"
                    )
            else:
                logger.debug(
                    f"Directory {entry_path} (depth {current_depth + 1}) "
                    f"exceeds max display depth ({max_depth}). Not descending."
                )
        else:  # It's a file
            if current_depth + 1 <= max_depth:
                tree_lines.append(entry_line)
                has_meaningful_content_in_children = True
            else:
                logger.debug(
                    f"File {entry_path} (depth {current_depth + 1}) "
                    f"exceeds max depth ({max_depth}). Skipping."
                )

    if exclude_empty_dirs and not has_meaningful_content_in_children and current_depth > 0:
        logger.debug(f"Pruning directory with no meaningful content from tree: {path}")
        return ""

    return "\n".join(tree_lines)
