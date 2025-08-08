# ctxctx/tree.py
import logging
import os
from typing import Callable, Set

logger = logging.getLogger(__name__)


def generate_tree_string(
    path: str,
    is_ignored: Callable[[str], bool],
    max_depth: int,
    exclude_empty_dirs: bool,
    current_depth: int = 0,
    prefix: str = "",
    visited_paths: Set[str] = None,
) -> str:
    """Generates a string representation of the directory tree.
    :param path: The current directory path to traverse.
    :param is_ignored: A callable function to check if a path should be ignored.
    :param max_depth: Maximum recursion depth for the tree view (inclusive, e.g.,
                      1 means root + 1 level of children).
    :param exclude_empty_dirs: If True, directories that only contain ignored
                               files or are empty are excluded.
    :param current_depth: The current recursion depth (0 for the initial call).
    :param prefix: The string prefix for current level (for indentation).
    :param visited_paths: Set to keep track of visited paths to prevent infinite
                          recursion (symlinks).
    :return: A string representing the directory tree.
    """
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

    if not os.path.isdir(path):
        logger.debug(f"Path is not a directory: {path}")
        return ""

    entries_to_process = []
    try:
        all_entries = sorted(os.listdir(path))
        for entry in all_entries:
            full_entry_path = os.path.join(path, entry)
            if not is_ignored(full_entry_path):
                entries_to_process.append(entry)
            else:
                logger.debug(f"Skipping ignored entry in tree: {full_entry_path}")
    except PermissionError:
        logger.warning(f"Permission denied accessing directory: {path}")
        return ""
    except Exception as e:
        logger.warning(f"Error listing directory {path}: {e}")
        return ""

    tree_lines = []
    has_meaningful_content_in_children = False

    for i, entry in enumerate(entries_to_process):
        full_path_entry = os.path.join(path, entry)
        is_last = i == len(entries_to_process) - 1
        connector = "└── " if is_last else "├── "

        entry_line = prefix + connector + entry

        if os.path.isdir(full_path_entry):
            if current_depth < max_depth:
                extension = "    " if is_last else "│   "
                child_tree_output = generate_tree_string(
                    full_path_entry,
                    is_ignored,
                    max_depth,
                    exclude_empty_dirs,
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
                        f"Pruning empty or all-ignored directory from tree: " f"{full_path_entry}"
                    )
            else:
                logger.debug(
                    f"Directory {full_path_entry} (depth {current_depth + 1}) "
                    f"exceeds max display depth ({max_depth}). Not descending."
                )
        else:
            if current_depth + 1 <= max_depth:
                tree_lines.append(entry_line)
                has_meaningful_content_in_children = True
            else:
                logger.debug(
                    f"File {full_path_entry} (depth {current_depth + 1}) "
                    f"exceeds max depth ({max_depth}). Skipping."
                )

    if exclude_empty_dirs and not has_meaningful_content_in_children and current_depth > 0:
        logger.debug(f"Pruning directory with no meaningful content from tree: {path}")
        return ""

    return "\n".join(tree_lines)
