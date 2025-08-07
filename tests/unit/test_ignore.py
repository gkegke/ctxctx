# tests/unit/test_ignore.py
import os
import pytest
from ctxctx.ignore import IgnoreManager
from ctxctx.config import CONFIG, DEFAULT_CONFIG


@pytest.fixture
def ignore_manager(fs):
    """Fixture to provide a configured IgnoreManager with a fake filesystem."""
    CONFIG.clear()
    CONFIG.update(DEFAULT_CONFIG.copy())

    root_path = "/project"
    fs.create_dir(root_path)
    CONFIG['ROOT'] = root_path
    CONFIG['ADDITIONAL_IGNORE_FILENAMES'] = [".testignore"]
    CONFIG['SCRIPT_DEFAULT_IGNORE_FILE'] = "ctxignore.txt"

    return IgnoreManager(CONFIG, root_path)

def test_is_ignored_explicit_name(ignore_manager, fs):
    """
    Tests if a file/directory matching an explicit ignore name is ignored.
    ROI: High (Core ignore logic). TTI: Low.
    """
    fs.create_file("/project/node_modules/foo.js")
    fs.create_dir("/project/__pycache__")
    assert ignore_manager.is_ignored("/project/node_modules/foo.js") is True
    assert ignore_manager.is_ignored("/project/__pycache__") is True
    assert ignore_manager.is_ignored("/project/src/main.py") is False

def test_is_ignored_substring_pattern(ignore_manager, fs):
    """
    Tests if a file matching a substring ignore pattern is ignored.
    ROI: Medium (Covers common log/lock files). TTI: Low.
    """
    # Adding to CONFIG directly ensures the fixture's cleanup is consistent
    CONFIG['SUBSTRING_IGNORE_PATTERNS'].append('temp_file')
    ignore_manager.init_ignore_set() # Re-initialize after config change

    fs.create_file("/project/logs/temp_file_001.log")
    fs.create_file("/project/src/sub/another_temp_file.txt")
    assert ignore_manager.is_ignored("/project/logs/temp_file_001.log") is True
    assert ignore_manager.is_ignored("/project/src/sub/another_temp_file.txt") is True
    assert ignore_manager.is_ignored("/project/src/file.py") is False

def test_is_ignored_additional_ignore_files(ignore_manager, fs):
    """
    Tests if additional ignore files (e.g., .dockerignore) are correctly applied.
    ROI: Medium (Supports wider project types). TTI: Low.
    """
    fs.create_file("/project/.testignore", contents="""
temp_data/
*.bak
""")
    ignore_manager.init_ignore_set() # Re-initialize to load additional ignore files

    assert ignore_manager.is_ignored("/project/temp_data/file.txt") is True
    assert ignore_manager.is_ignored("/project/src/image.bak") is True
    assert ignore_manager.is_ignored("/project/src/model.json") is False

def test_is_ignored_root_path_behavior(ignore_manager):
    """
    Tests that the root path itself is not ignored.
    ROI: Low (Edge case, but important for correctness). TTI: Low.
    """
    assert ignore_manager.is_ignored("/project") is False