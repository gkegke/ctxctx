# ctxctx/content.py
import logging
from pathlib import Path  # Added import
from typing import List, Optional, Tuple

from .exceptions import FileReadError

logger = logging.getLogger(__name__)


def get_file_content(
    path: Path, line_ranges: Optional[List[Tuple[int, int]]] = None
) -> str:  # Changed path type hint
    """Reads file content, optionally by line ranges."""
    try:
        with open(path, "r", encoding="utf-8") as f:  # open() accepts Path objects
            lines = f.readlines()
    except Exception as e:
        raise FileReadError(f"Error reading file '{path}': {e}")

    if line_ranges:
        content_parts = []
        last_line_read = 0

        sorted_ranges = sorted(line_ranges)

        for start_line, end_line in sorted_ranges:
            if last_line_read > 0 and start_line > last_line_read + 1:
                content_parts.append(
                    f"// ... (lines {last_line_read + 1} to " f"{start_line - 1} omitted)\n"
                )

            start_idx = max(0, start_line - 1)
            end_idx = min(len(lines), end_line)

            if start_idx >= len(lines):
                logger.warning(
                    f"Start line {start_line} out of bounds for file "
                    f"'{path}' (file has {len(lines)} lines). "
                    "Skipping range."
                )
                continue

            if start_idx >= end_idx:
                logger.warning(
                    f"Invalid line range {start_line},{end_line} in file "
                    f"'{path}'. Skipping range."
                )
                continue

            content_parts.append(f"// Lines {start_line}-{end_line}:\n")
            content_parts.append("".join(lines[start_idx:end_idx]))
            last_line_read = end_line

        return "".join(content_parts).strip()

    return "".join(lines).strip()
