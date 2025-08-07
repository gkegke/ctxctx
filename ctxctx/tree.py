# ctxctx/tree.py
import os
from typing import Set, List, Callable
import logging

logger = logging.getLogger("ctx")

def generate_tree_string(path: str, is_ignored: Callable[[str], bool], \
                         max_depth: int, exclude_empty_dirs: bool, \
                         current_depth: int = 0, prefix: str = '', visited_paths: Set[str] = None) -> str:
    """
    Generates a string representation of the directory tree.
    :param path: The current directory path to traverse.
    :param is_ignored: A callable function to check if a path should be ignored.
    :param max_depth: Maximum recursion depth for the tree view (inclusive, e.g., 1 means root + 1 level of children).
    :param exclude_empty_dirs: If True, directories that only contain ignored files or are empty are excluded.
    :param current_depth: The current recursion depth (0 for the initial call).
    :param prefix: The string prefix for current level (for indentation).
    :param visited_paths: Set to keep track of visited paths to prevent infinite recursion (symlinks).
    :return: A string representing the directory tree.
    """
    if visited_paths is None:
        visited_paths = set()

    if path in visited_paths:
        logger.debug(f"Skipping already visited path (likely symlink): {path}")
        return ""
    visited_paths.add(path)

    # Check if the current path itself should be ignored.
    # We allow the initial call's path (root) to be processed even if its name matches an ignore pattern.
    # For subdirectories, if they are explicitly ignored, we don't descend.
    if current_depth > 0 and is_ignored(path):
        logger.debug(f"Ignoring path for tree generation: {path}")
        return ""

    # If the current path itself is deeper than the maximum allowed depth, it (and its children) should not be displayed.
    # If current_depth == max_depth, this path *is* displayed, but we do not recurse into its subdirectories.
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
        connector = '└── ' if is_last else '├── '

        entry_line = prefix + connector + entry
        
        if os.path.isdir(full_path_entry):
            # Recurse into a subdirectory ONLY if the current depth is strictly less than max_depth.
            # If current_depth == max_depth, its children are at depth > max_depth and should not be shown.
            if current_depth < max_depth: 
                extension = '    ' if is_last else '│   '
                child_tree_output = generate_tree_string(
                    full_path_entry, is_ignored, max_depth, exclude_empty_dirs,
                    current_depth + 1, prefix + extension, visited_paths
                )
                if child_tree_output:
                    # Directory has displayable content (either itself or children)
                    tree_lines.append(entry_line)
                    tree_lines.append(child_tree_output)
                    has_meaningful_content_in_children = True
                elif not exclude_empty_dirs:
                    # Directory is empty of displayable children (recursively), but we don't exclude empty dirs
                    tree_lines.append(entry_line)
                    has_meaningful_content_in_children = True
                else:
                    # Directory is empty of displayable children, and we DO exclude empty dirs.
                    # This directory won't be added to tree_lines.
                    logger.debug(f"Pruning empty or all-ignored directory from tree: {full_path_entry}")
            else: # current_depth >= max_depth: Cannot recurse. The entry itself is at depth > max_depth, so don't list it.
                logger.debug(f"Directory {full_path_entry} (depth {current_depth + 1}) exceeds max display depth ({max_depth}). Not descending.")
        else: # It's a file
            # Files are displayed if their *own* depth (current_depth + 1, relative to root) is <= max_depth.
            if current_depth + 1 <= max_depth:
                tree_lines.append(entry_line)
                has_meaningful_content_in_children = True
            else:
                logger.debug(f"File {full_path_entry} (depth {current_depth + 1}) exceeds max depth ({max_depth}). Skipping.")

    # This check ensures that if a directory itself ends up empty after filtering/recursion,
    # and exclude_empty_dirs is True, it's not included in its parent's output.
    # It applies *after* processing all children.
    if exclude_empty_dirs and not has_meaningful_content_in_children and current_depth > 0:
        logger.debug(f"Pruning directory with no meaningful content from tree: {path}")
        return ""

    return '\n'.join(tree_lines)