# ctxctx/output.py
import logging
from pathlib import Path  # Added import
from typing import Any, Callable, Dict, List, Tuple

logger = logging.getLogger(__name__)


def format_file_content_markdown(
    file_data: Dict[str, Any],
    root_path: Path,  # Changed type hint
    get_file_content_func: Callable[
        [Path, List[Tuple[int, int]]], str
    ],  # Changed Callable signature
) -> str:
    """Formats file content for Markdown output.
    :param file_data: Dictionary containing 'path' (Path object), and optionally 'line_ranges'
                      (list of tuples).
    :param root_path: The root directory of the project (Path object).
    :param get_file_content_func: The function to call to retrieve file content.
    :return: Markdown formatted string.
    """
    path: Path = file_data["path"]  # Expects Path object
    rel_path = path.relative_to(root_path)  # Changed to Path.relative_to()

    content_raw = get_file_content_func(path, file_data.get("line_ranges"))

    ext = path.suffix.lstrip(".")  # Changed to Path.suffix
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
    root_path: Path,  # Changed type hint
    get_file_content_func: Callable[
        [Path, List[Tuple[int, int]]], str
    ],  # Changed Callable signature
) -> Dict[str, Any]:
    """Formats file content for JSON output.
    :param file_data: Dictionary containing 'path' (Path object), and optionally 'line_ranges'
                      (list of tuples).
    :param root_path: The root directory of the project (Path object).
    :param get_file_content_func: The function to call to retrieve file content.
    :return: Dictionary for JSON output.
    """
    path: Path = file_data["path"]  # Expects Path object
    rel_path = path.relative_to(root_path)  # Changed to Path.relative_to()

    content_raw = get_file_content_func(path, file_data.get("line_ranges"))

    # For JSON output, paths should generally be strings
    data = {"path": f"/{rel_path}", "content": content_raw}

    line_ranges = file_data.get("line_ranges")
    if line_ranges:
        data["line_ranges"] = line_ranges

    return data
