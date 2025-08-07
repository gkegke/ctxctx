# ctxctx/content.py
import os
from typing import Optional, List, Tuple
from .exceptions import FileReadError
import logging

logger = logging.getLogger("ctx")

def get_file_content(path: str, line_ranges: Optional[List[Tuple[int, int]]] = None) -> str:
    """Reads file content, optionally by line ranges."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        raise FileReadError(f"Error reading file '{path}': {e}")

    if line_ranges:
        content_parts = []
        last_line_read = 0 # To track if we need to add "..." for omissions

        # Sort ranges to ensure they are processed in order and for correct omission detection
        sorted_ranges = sorted(line_ranges)

        for start_line, end_line in sorted_ranges:
            # Add omission indicator if there's a gap between the current range and the previous one
            if last_line_read > 0 and start_line > last_line_read + 1:
                content_parts.append(f"// ... (lines {last_line_read + 1} to {start_line - 1} omitted)\n")
            
            # Adjust for 0-based indexing for file lines
            start_idx = max(0, start_line - 1)
            end_idx = min(len(lines), end_line) # end_line is inclusive for user, exclusive for slice

            if start_idx >= len(lines):
                logger.warning(f"Start line {start_line} out of bounds for file '{path}' (file has {len(lines)} lines). Skipping range.")
                continue

            # Ensure end_idx is not before start_idx if user provides inverse range
            if start_idx >= end_idx:
                logger.warning(f"Invalid line range {start_line},{end_line} in file '{path}'. Skipping range.")
                continue

            content_parts.append(f"// Lines {start_line}-{end_line}:\n") # Indicate which lines are included
            content_parts.append("".join(lines[start_idx:end_idx]))
            last_line_read = end_line # Update the last line read

        return "".join(content_parts).strip()
    
    # If no specific line ranges are provided, return the entire file content
    return "".join(lines).strip()