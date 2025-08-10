# tests/unit/test_content.py
import logging
from pathlib import Path

import pytest

from ctxctx.content import get_file_content
from ctxctx.exceptions import FileReadError


@pytest.fixture
def content_setup_fs(fs):
    """
    Setup a basic file system for content-related tests.
    """
    project_root = Path("/project")
    fs.create_dir(project_root)

    # Create simple.txt for line range tests
    # Use Path / operator for cleaner path joining
    with open(project_root / "simple.txt", "w") as f:
        f.write("Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6\n")

    # Create an empty file
    fs.create_file(project_root / "empty.txt")

    # Create a file that can't be read (simulate permission error if needed)
    # For now, tests will rely on mocking open or expecting FileReadError directly.
    # fs.create_file(project_root / "unreadable.txt")

    return project_root


# --- Tests ---


def test_get_file_content_full(content_setup_fs):
    """
    Tests getting the full content of a file.
    ROI: High (Basic functionality). TTI: Low.
    """
    root_path = content_setup_fs
    filepath = root_path / "simple.txt"
    content = get_file_content(filepath)
    assert content == "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6"


def test_get_file_content_line_range(content_setup_fs):
    """
    Tests getting file content within a specified line range.
    ROI: High (Precise context). TTI: Low.
    """
    root_path = content_setup_fs
    filepath = root_path / "simple.txt"

    # FIX: Pass line_ranges as a list of tuples as expected by get_file_content signature
    content = get_file_content(filepath, line_ranges=[(2, 4)])
    expected_content = "// Lines 2-4:\nLine 2\nLine 3\nLine 4"
    assert content == expected_content


def test_get_file_content_multiple_line_ranges(content_setup_fs):
    """
    Tests getting file content with multiple non-contiguous line ranges.
    ROI: Medium. TTI: Low.
    """
    root_path = content_setup_fs
    filepath = root_path / "simple.txt"
    content = get_file_content(filepath, line_ranges=[(1, 1), (5, 6)])
    expected_content = (
        "// Lines 1-1:\nLine 1\n// ... (lines 2 to 4 omitted)\n// Lines 5-6:\nLine 5\nLine 6"
    )
    assert content == expected_content


def test_get_file_content_overlapping_line_ranges(content_setup_fs):
    """
    Tests getting file content with overlapping line ranges.
    The current `get_file_content` function sorts but does not merge overlapping ranges.
    It will print each specified range.
    """
    root_path = content_setup_fs
    filepath = root_path / "simple.txt"
    content = get_file_content(filepath, line_ranges=[(1, 3), (2, 4)])

    # Expected output based on current `content.py` logic (sorts and processes distinctly)
    expected_content = (
        "// Lines 1-3:\nLine 1\nLine 2\nLine 3\n" "// Lines 2-4:\nLine 2\nLine 3\nLine 4"
    )
    assert content == expected_content


def test_get_file_content_out_of_bounds_line_range(content_setup_fs, caplog):
    """
    Tests handling line ranges that are out of bounds.
    ROI: Medium. TTI: Low.
    """
    root_path = content_setup_fs
    filepath = root_path / "simple.txt"

    with caplog.at_level(logging.WARNING):
        content = get_file_content(filepath, line_ranges=[(100, 105)])  # Entirely out of bounds
        assert content.strip() == ""
        assert "Start line 100 out of bounds" in caplog.text

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        content = get_file_content(
            filepath, line_ranges=[(1, 2), (5, 100)]
        )  # Partially out of bounds
        expected_content = (
            "// Lines 1-2:\nLine 1\nLine 2\n"  # Corrected: Include Line 2
            "// ... (lines 3 to 4 omitted)\n// Lines 5-100:\nLine 5\nLine 6"
        )
        assert content == expected_content
        # Ensure no warning for start line 5 if it's within bounds
        assert "Start line 5 out of bounds" not in caplog.text


def test_get_file_content_invalid_filepath(caplog):
    """
    Tests handling an invalid file path.
    ROI: High (Robustness). TTI: Low.
    """
    invalid_filepath = Path("/nonexistent/file.txt")
    with pytest.raises(FileReadError) as excinfo:
        get_file_content(invalid_filepath)
    assert "Error reading file" in str(excinfo.value)


def test_get_file_content_empty_file(content_setup_fs):
    """
    Tests getting content from an empty file.
    ROI: Low. TTI: Low.
    """
    root_path = content_setup_fs
    filepath = root_path / "empty.txt"
    content = get_file_content(filepath)
    assert content == ""
