# tests/unit/test_search.py
import os
from typing import Callable, List

import pytest

from ctxctx.config import CONFIG, DEFAULT_CONFIG
from ctxctx.ignore import IgnoreManager
from ctxctx.search import find_matches


@pytest.fixture
def search_setup_fs(fs):
    """
    Sets up a fake filesystem for search tests, returning the root path
    and a callable to create an `is_ignored` function with specific `force_include_patterns`.
    """
    # Ensure CONFIG is reset for each test run (handled by conftest.py autouse fixture)
    CONFIG.clear()
    CONFIG.update(DEFAULT_CONFIG.copy())

    root_path = "/project"
    fs.create_dir(root_path)
    fs.create_file(os.path.join(root_path, "main.py"), contents="def foo(): pass")
    fs.create_file(os.path.join(root_path, "README.md"))
    fs.create_dir(os.path.join(root_path, "src"))
    fs.create_file(os.path.join(root_path, "src", "utils.py"), contents="class MyClass: pass")
    fs.create_file(os.path.join(root_path, "src", "temp_data.log"))  # Will be ignored by substring
    fs.create_dir(os.path.join(root_path, "docs"))
    fs.create_file(os.path.join(root_path, "docs", "guide.md"))
    fs.create_dir(os.path.join(root_path, "node_modules"))  # Ignored by default
    fs.create_file(os.path.join(root_path, "node_modules", "lib.js"))
    fs.create_dir(os.path.join(root_path, "git_ignored_dir"))
    fs.create_file(os.path.join(root_path, "git_ignored_dir", "ignored_file.txt"))
    fs.create_file(
        os.path.join(root_path, ".gitignore"), contents="git_ignored_dir/\n*.log\n"
    )  # Simulate gitignore
    fs.create_file(os.path.join(root_path, "app.log"))  # A top-level log file

    CONFIG["ROOT"] = root_path
    CONFIG["SUBSTRING_IGNORE_PATTERNS"].append("temp_data")  # Ensure this is ignored
    CONFIG["SEARCH_MAX_DEPTH"] = 5  # Default, sufficient for tests

    def create_is_ignored(force_include_patterns: List[str] = None) -> Callable[[str], bool]:
        """
        Helper to create an is_ignored callable for tests with specific
        force_include_patterns.
        """
        # Use a fresh copy of CONFIG to ensure isolation between different
        # calls to create_is_ignored
        current_config = CONFIG.copy()
        manager = IgnoreManager(
            current_config, root_path, force_include_patterns=force_include_patterns or []
        )
        return manager.is_ignored

    return root_path, create_is_ignored


def test_find_matches_exact_file(search_setup_fs):
    """Tests finding an exact file path."""
    root, create_is_ignored = search_setup_fs
    is_ignored = create_is_ignored()  # No force-includes for this test
    query = "main.py"
    matches = find_matches(query, root, is_ignored, CONFIG["SEARCH_MAX_DEPTH"])
    assert len(matches) == 1
    assert matches[0]["path"] == os.path.join(root, "main.py")
    assert matches[0]["line_ranges"] == []


def test_find_matches_glob_pattern(search_setup_fs):
    """Tests finding files using a glob pattern."""
    root, create_is_ignored = search_setup_fs
    is_ignored = create_is_ignored()  # No force-includes for this test
    query = "*.md"
    matches = find_matches(query, root, is_ignored, CONFIG["SEARCH_MAX_DEPTH"])
    assert len(matches) == 2
    assert any(m["path"] == os.path.join(root, "README.md") for m in matches)
    assert any(m["path"] == os.path.join(root, "docs", "guide.md") for m in matches)
    for m in matches:
        assert m["line_ranges"] == []


def test_find_matches_line_range_query(search_setup_fs):
    """Tests parsing and returning line range information from a query."""
    root, create_is_ignored = search_setup_fs
    is_ignored = create_is_ignored()  # No force-includes for this test
    query = "src/utils.py:10,20"
    matches = find_matches(query, root, is_ignored, CONFIG["SEARCH_MAX_DEPTH"])
    assert len(matches) == 1
    assert matches[0]["path"] == os.path.join(root, "src", "utils.py")
    assert matches[0]["line_ranges"] == [(10, 20)]


def test_find_matches_ignores_excluded_files(search_setup_fs, fs):
    """Tests that files/directories marked as ignored are not included in matches."""
    root, create_is_ignored = search_setup_fs
    is_ignored = (
        create_is_ignored()
    )  # No force-includes for this test, so default ignore rules apply

    # Test file ignored by substring
    query_ignored_file_substring = "src/temp_data.log"
    matches_ignored_file_substring = find_matches(
        query_ignored_file_substring, root, is_ignored, CONFIG["SEARCH_MAX_DEPTH"]
    )
    assert len(matches_ignored_file_substring) == 0

    # Test file ignored by .gitignore (glob)
    query_ignored_file_glob = "app.log"
    matches_ignored_file_glob = find_matches(
        query_ignored_file_glob, root, is_ignored, CONFIG["SEARCH_MAX_DEPTH"]
    )
    assert len(matches_ignored_file_glob) == 0

    # Test directory ignored by explicit name (node_modules)
    query_ignored_dir_explicit = "node_modules"
    matches_ignored_dir_explicit = find_matches(
        query_ignored_dir_explicit, root, is_ignored, CONFIG["SEARCH_MAX_DEPTH"]
    )
    assert len(matches_ignored_dir_explicit) == 0

    query_file_in_ignored_dir_explicit = "node_modules/lib.js"
    matches_file_in_ignored_dir_explicit = find_matches(
        query_file_in_ignored_dir_explicit, root, is_ignored, CONFIG["SEARCH_MAX_DEPTH"]
    )
    assert len(matches_file_in_ignored_dir_explicit) == 0

    # Test directory ignored by .gitignore
    query_git_ignored_dir = "git_ignored_dir/"
    matches_git_ignored_dir = find_matches(
        query_git_ignored_dir, root, is_ignored, CONFIG["SEARCH_MAX_DEPTH"]
    )
    assert len(matches_git_ignored_dir) == 0  # Directory and its contents are ignored

    query_file_in_git_ignored_dir = "git_ignored_dir/ignored_file.txt"
    matches_file_in_git_ignored_dir = find_matches(
        query_file_in_git_ignored_dir, root, is_ignored, CONFIG["SEARCH_MAX_DEPTH"]
    )
    assert len(matches_file_in_git_ignored_dir) == 0


def test_find_matches_directory_query(search_setup_fs):
    """Tests that a directory query returns all non-ignored files within it."""
    root, create_is_ignored = search_setup_fs
    is_ignored = create_is_ignored()  # No force-includes for this test
    query = "src/"
    matches = find_matches(query, root, is_ignored, CONFIG["SEARCH_MAX_DEPTH"])
    assert len(matches) == 1  # Only utils.py, as temp_data.log is ignored
    assert matches[0]["path"] == os.path.join(root, "src", "utils.py")
    assert matches[0]["line_ranges"] == []


# --- NEW Force Include Tests for Search ---


def test_find_matches_force_include_file(search_setup_fs):
    """
    Tests finding a specific file that is normally ignored when using a force-include query.
    ROI: High (Core force-include functionality). TTI: Low.
    """
    root, create_is_ignored = search_setup_fs
    # 'node_modules/lib.js' is normally ignored by 'node_modules' explicit ignore
    query = "!node_modules/lib.js"

    # Simulate cli.py: `is_ignored` function is set up with force-include patterns
    force_include_patterns = ["node_modules/lib.js"]
    is_ignored = create_is_ignored(force_include_patterns=force_include_patterns)

    matches = find_matches(query, root, is_ignored, CONFIG["SEARCH_MAX_DEPTH"])
    assert len(matches) == 1
    assert matches[0]["path"] == os.path.join(root, "node_modules", "lib.js")
    assert matches[0]["line_ranges"] == []


def test_find_matches_force_include_glob(search_setup_fs):
    """
    Tests finding files matching a force-include glob pattern that would normally be ignored.
    ROI: High (Flexible force-include). TTI: Medium.
    """
    root, create_is_ignored = search_setup_fs
    # 'src/temp_data.log' is ignored by substring, 'app.log' by .gitignore glob
    query = "!*.log"

    # Simulate cli.py: `is_ignored` function is set up with force-include patterns
    force_include_patterns = ["*.log", "src/*.log"]  # Include both general and specific log globs
    is_ignored = create_is_ignored(force_include_patterns=force_include_patterns)

    matches = find_matches(query, root, is_ignored, CONFIG["SEARCH_MAX_DEPTH"])
    # Should find 'src/temp_data.log' and 'app.log'
    assert len(matches) == 2
    assert any(m["path"] == os.path.join(root, "src", "temp_data.log") for m in matches)
    assert any(m["path"] == os.path.join(root, "app.log") for m in matches)
    for m in matches:
        assert m["line_ranges"] == []


def test_find_matches_force_include_with_line_ranges(search_setup_fs):
    """
    Tests that force-include works correctly when combined with line range queries.
    ROI: Medium (Combined feature test). TTI: Low.
    """
    root, create_is_ignored = search_setup_fs
    # 'node_modules/lib.js' is ignored by default
    query = "!node_modules/lib.js:1,5"

    # Simulate cli.py: `is_ignored` function is set up with force-include
    # pattern (path part of query)
    force_include_patterns = ["node_modules/lib.js"]
    is_ignored = create_is_ignored(force_include_patterns=force_include_patterns)

    matches = find_matches(query, root, is_ignored, CONFIG["SEARCH_MAX_DEPTH"])
    assert len(matches) == 1
    assert matches[0]["path"] == os.path.join(root, "node_modules", "lib.js")
    assert matches[0]["line_ranges"] == [(1, 5)]


def test_find_matches_force_include_directory(search_setup_fs):
    """
    Tests that a force-include query for a directory returns its non-ignored contents.
    ROI: Medium (Directory force-include). TTI: Medium.
    """
    root, create_is_ignored = search_setup_fs
    # 'git_ignored_dir/' is ignored by .gitignore in fixture setup
    query = "!git_ignored_dir/"

    # Simulate cli.py: `is_ignored` function is set up with force-include pattern
    force_include_patterns = ["git_ignored_dir/"]
    is_ignored = create_is_ignored(force_include_patterns=force_include_patterns)

    matches = find_matches(query, root, is_ignored, CONFIG["SEARCH_MAX_DEPTH"])
    assert len(matches) == 1  # Should find 'git_ignored_dir/ignored_file.txt'
    assert matches[0]["path"] == os.path.join(root, "git_ignored_dir", "ignored_file.txt")
    assert matches[0]["line_ranges"] == []


def test_find_matches_force_include_with_no_effect_if_not_ignored(search_setup_fs):
    """
    Tests that a force-include query for an already non-ignored file behaves normally.
    ROI: Low (Ensures `!` doesn't break normal behavior). TTI: Low.
    """
    root, create_is_ignored = search_setup_fs
    # 'main.py' is NOT ignored by default config
    query = "!main.py"

    # `is_ignored` is created without force-include patterns as there's no override needed
    is_ignored = create_is_ignored()

    matches = find_matches(query, root, is_ignored, CONFIG["SEARCH_MAX_DEPTH"])
    assert len(matches) == 1
    assert matches[0]["path"] == os.path.join(root, "main.py")
    assert matches[0]["line_ranges"] == []
