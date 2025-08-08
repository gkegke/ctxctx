# ctxctx/output.py
import logging
import os
from typing import Any, Callable, Dict, List, Tuple

logger = logging.getLogger(__name__)


def format_file_content_markdown(
    file_data: Dict[str, Any],
    root_path: str,
    get_file_content_func: Callable[[str, List[Tuple[int, int]]], str],
) -> str:
    """Formats file content for Markdown output.
    :param file_data: Dictionary containing 'path', and optionally 'line_ranges'
                      (list of tuples).
    :param root_path: The root directory of the project.
    :param get_file_content_func: The function to call to retrieve file content.
    :return: Markdown formatted string.
    """
    path = file_data["path"]
    rel_path = os.path.relpath(path, root_path)

    content_raw = get_file_content_func(path, file_data.get("line_ranges"))

    ext = os.path.splitext(path)[1].lstrip(".")
    lang = ""
    if ext:
        lang_map = {
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "md": "markdown",
            "json": "json",
            "yaml": "yaml",
            "yml": "yaml",
            "sh": "bash",
            "css": "css",
            "html": "html",
            "xml": "xml",
            "go": "go",
            "rb": "ruby",
            "java": "java",
            "c": "c",
            "cpp": "cpp",
            "h": "c",
            "hpp": "cpp",
            "rs": "rust",
            "php": "php",
            "swift": "swift",
            "kt": "kotlin",
            "scala": "scala",
            "vue": "vue",
            "jsx": "javascript",
            "tsx": "typescript",
        }
        lang = lang_map.get(ext, ext)

    header = f"**[FILE: /{rel_path}]**"
    line_ranges = file_data.get("line_ranges")
    if line_ranges:
        ranges_str = ", ".join([f"{s}-{e}" for s, e in line_ranges])
        header += f" (Lines: {ranges_str})"

    return f"{header}\n```{lang}\n{content_raw}\n```"


def format_file_content_json(
    file_data: Dict[str, Any],
    root_path: str,
    get_file_content_func: Callable[[str, List[Tuple[int, int]]], str],
) -> Dict[str, Any]:
    """Formats file content for JSON output.
    :param file_data: Dictionary containing 'path', and optionally 'line_ranges'
                      (list of tuples).
    :param root_path: The root directory of the project.
    :param get_file_content_func: The function to call to retrieve file content.
    :return: Dictionary for JSON output.
    """
    path = file_data["path"]
    rel_path = os.path.relpath(path, root_path)

    content_raw = get_file_content_func(path, file_data.get("line_ranges"))

    data = {"path": f"/{rel_path}", "content": content_raw}

    line_ranges = file_data.get("line_ranges")
    if line_ranges:
        data["line_ranges"] = line_ranges

    return data
