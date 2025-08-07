# tests/unit/test_search.py
import os
import pytest
from ctxctx.search import find_matches
from ctxctx.ignore import IgnoreManager
from ctxctx.config import CONFIG, DEFAULT_CONFIG


@pytest.fixture
def search_setup_fs(fs):
    """Sets up a fake filesystem for search tests."""
    CONFIG.clear()
    CONFIG.update(DEFAULT_CONFIG.copy())

    root_path = "/project"
    fs.create_dir(root_path)
    fs.create_file(os.path.join(root_path, "main.py"), contents="def foo(): pass")
    fs.create_file(os.path.join(root_path, "README.md"))
    fs.create_dir(os.path.join(root_path, "src"))
    fs.create_file(os.path.join(root_path, "src", "utils.py"), contents="class MyClass: pass")
    fs.create_file(os.path.join(root_path, "src", "temp_data.log")) # Will be ignored by substring
    fs.create_dir(os.path.join(root_path, "docs"))
    fs.create_file(os.path.join(root_path, "docs", "guide.md"))
    fs.create_dir(os.path.join(root_path, "node_modules")) # Ignored by default
    fs.create_file(os.path.join(root_path, "node_modules", "lib.js"))

    CONFIG['ROOT'] = root_path
    CONFIG['SUBSTRING_IGNORE_PATTERNS'].append('temp_data') # Ensure this is ignored
    CONFIG['SEARCH_MAX_DEPTH'] = 5 # Default, sufficient for tests

    # Create an IgnoreManager instance for the tests
    ignore_manager = IgnoreManager(CONFIG, root_path)
    return root_path, ignore_manager.is_ignored

def test_find_matches_exact_file(search_setup_fs):
    """
    Tests finding an exact file path.
    ROI: High (Basic functionality). TTI: Low.
    """
    root, is_ignored = search_setup_fs
    query = "main.py"
    matches = find_matches(query, root, is_ignored, CONFIG['SEARCH_MAX_DEPTH'])
    assert len(matches) == 1
    assert matches[0]['path'] == os.path.join(root, "main.py")
    # Assert line_ranges is empty for a simple file query
    assert matches[0]['line_ranges'] == [] # Changed: removed start_line/functions, added line_ranges

def test_find_matches_glob_pattern(search_setup_fs):
    """
    Tests finding files using a glob pattern.
    ROI: High (Flexible search). TTI: Medium.
    """
    root, is_ignored = search_setup_fs
    query = "*.md"
    matches = find_matches(query, root, is_ignored, CONFIG['SEARCH_MAX_DEPTH'])
    assert len(matches) == 2
    assert any(m['path'] == os.path.join(root, "README.md") for m in matches)
    assert any(m['path'] == os.path.join(root, "docs", "guide.md") for m in matches)
    # Ensure line_ranges is empty for glob matches too
    for m in matches:
        assert m['line_ranges'] == []

def test_find_matches_line_range_query(search_setup_fs):
    """
    Tests parsing and returning line range information from a query.
    ROI: High (Precise context). TTI: Low.
    """
    root, is_ignored = search_setup_fs
    query = "src/utils.py:10,20"
    matches = find_matches(query, root, is_ignored, CONFIG['SEARCH_MAX_DEPTH'])
    assert len(matches) == 1
    assert matches[0]['path'] == os.path.join(root, "src", "utils.py")
    assert matches[0]['line_ranges'] == [(10, 20)] # Changed: use line_ranges tuple list

# REMOVED: test_find_matches_functions_query as 'funcs=' is no longer supported.

def test_find_matches_ignores_excluded_files(search_setup_fs):
    """
    Tests that files/directories marked as ignored are not included in matches.
    ROI: High (Integrates with ignore manager). TTI: Low-Medium.
    """
    root, is_ignored = search_setup_fs
    
    # Test file ignored by substring
    query_ignored_file = "src/temp_data.log"
    matches_ignored_file = find_matches(query_ignored_file, root, is_ignored, CONFIG['SEARCH_MAX_DEPTH'])
    assert len(matches_ignored_file) == 0

    # Test directory ignored by explicit name (node_modules)
    query_ignored_dir = "node_modules"
    matches_ignored_dir = find_matches(query_ignored_dir, root, is_ignored, CONFIG['SEARCH_MAX_DEPTH'])\
    # This query for a directory "node_modules" should indeed return 0 matches as the directory itself is ignored
    assert len(matches_ignored_dir) == 0

    query_file_in_ignored_dir = "node_modules/lib.js"
    matches_file_in_ignored_dir = find_matches(query_file_in_ignored_dir, root, is_ignored, CONFIG['SEARCH_MAX_DEPTH'])
    assert len(matches_file_in_ignored_dir) == 0

def test_find_matches_directory_query(search_setup_fs):
    """
    Tests that a directory query returns all non-ignored files within it.
    ROI: Medium (Folder-level context). TTI: Medium.
    """
    root, is_ignored = search_setup_fs
    query = "src/"
    matches = find_matches(query, root, is_ignored, CONFIG['SEARCH_MAX_DEPTH'])
    assert len(matches) == 1 # Only utils.py, as temp_data.log is ignored
    assert matches[0]['path'] == os.path.join(root, "src", "utils.py")
    assert matches[0]['line_ranges'] == [] # Directory queries don't imply line ranges