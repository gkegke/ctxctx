# tests/unit/test_search.py
import os
from typing import Callable, List

import pytest

from ctxctx.config import CONFIG, DEFAULT_CONFIG
from ctxctx.ignore import IgnoreManager
from ctxctx.search import FORCE_INCLUDE_PREFIX, find_matches


# Ensure this fixture resets the config and sets up the root path
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
    fs.create_file(os.path.join(root_path, "LICENSE"))  # Added for new test

    fs.create_dir(os.path.join(root_path, "src"))
    fs.create_file(os.path.join(root_path, "src", "utils.py"), contents="class MyClass: pass")
    fs.create_file(os.path.join(root_path, "src", "temp_data.log"))  # Will be ignored by substring
    fs.create_file(os.path.join(root_path, "src", "README.md"))  # Added for new test
    fs.create_file(os.path.join(root_path, "src", ".gitignore"))  # Added for new test

    fs.create_dir(os.path.join(root_path, "docs"))
    fs.create_file(os.path.join(root_path, "docs", "guide.md"))
    fs.create_file(os.path.join(root_path, "docs", "LICENSE"))  # Added for new test

    fs.create_dir(os.path.join(root_path, "node_modules"))  # Ignored by default
    fs.create_file(os.path.join(root_path, "node_modules", "lib.js"))
    fs.create_dir(os.path.join(root_path, "git_ignored_dir"))
    fs.create_file(os.path.join(root_path, "git_ignored_dir", "ignored_file.txt"))
    fs.create_file(
        os.path.join(root_path, ".gitignore"),
        contents="git_ignored_dir/\n*.log\n.gitignore\n",
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
    assert (
        len(matches) == 3
    )  # Changed: Expected 3 files now (README.md, docs/guide.md, src/README.md)
    assert any(m["path"] == os.path.join(root, "README.md") for m in matches)
    assert any(m["path"] == os.path.join(root, "docs", "guide.md") for m in matches)
    assert any(
        m["path"] == os.path.join(root, "src", "README.md") for m in matches
    )  # Changed: Added check for new file
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


def test_find_matches_ignores_excluded_files(search_setup_fs, fs):  # Added fs fixture
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
    assert (
        len(matches_ignored_file_glob) == 0
    )  # This assertion should now pass due to search.py refactoring

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
    assert len(matches) == 2  # Changed: Now includes src/README.md as it's not ignored
    assert any(
        m["path"] == os.path.join(root, "src", "utils.py") for m in matches
    )  # Changed: Assert specific files
    assert any(
        m["path"] == os.path.join(root, "src", "README.md") for m in matches
    )  # Changed: Assert specific files
    for m in matches:  # Changed: Iterating to check line_ranges for all matches
        assert m["line_ranges"] == []


# --- NEW Force Include Tests for Search ---


def test_find_matches_force_include_file(search_setup_fs):
    """
    Tests finding a specific file that is normally ignored when using a force-include query.
    ROI: High (Core force-include functionality). TTI: Low.
    """
    root, create_is_ignored = search_setup_fs
    # 'node_modules/lib.js' is normally ignored by 'node_modules' explicit ignore
    query = f"{FORCE_INCLUDE_PREFIX}node_modules/lib.js"

    # Simulate cli.py: `is_ignored` function is set up with force-include patterns
    # The patterns passed to IgnoreManager should NOT contain the prefix
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
    query = f"{FORCE_INCLUDE_PREFIX}*.log"

    # Simulate cli.py: `is_ignored` function is set up with force-include patterns
    # The patterns passed to IgnoreManager should NOT contain the prefix
    force_include_patterns = ["*.log"]  # Changed: Simplified pattern, *.log should match both
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
    query = f"{FORCE_INCLUDE_PREFIX}node_modules/lib.js:1,5"

    # Simulate cli.py: `is_ignored` function is set up with force-include
    # pattern (path part of query)
    # The pattern passed to IgnoreManager should NOT contain the prefix
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
    query = f"{FORCE_INCLUDE_PREFIX}git_ignored_dir/"

    # Simulate cli.py: `is_ignored` function is set up with force-include pattern
    # The pattern passed to IgnoreManager should NOT contain the prefix
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
    query = f"{FORCE_INCLUDE_PREFIX}main.py"

    # `is_ignored` is created without force-include patterns as there's no override needed
    is_ignored = create_is_ignored()

    matches = find_matches(query, root, is_ignored, CONFIG["SEARCH_MAX_DEPTH"])
    assert len(matches) == 1
    assert matches[0]["path"] == os.path.join(root, "main.py")
    assert matches[0]["line_ranges"] == []


def test_find_matches_force_include_simple_filename_only_finds_root(search_setup_fs):
    """
    Tests that a 'force:filename.ext' query finds the file at the project root
    and potentially other directories if not ignored,
    as the special early-exit logic has been removed.
    This test's assertion is changed to reflect the refactored find_matches.
    """
    root, create_is_ignored = search_setup_fs

    # Both README.md files are NOT ignored by default ignore rules
    # This test verifies the new logic's behavior regardless of ignore status.
    query = f"{FORCE_INCLUDE_PREFIX}README.md"

    # is_ignored is created without force-include patterns as these files are not ignored
    is_ignored = create_is_ignored()

    matches = find_matches(query, root, is_ignored, CONFIG["SEARCH_MAX_DEPTH"])

    # Changed: After refactoring, 'force:README.md' will now find ALL README.md files
    # because the early exit for simple filenames is removed, and is_ignored does not ignore them.
    assert len(matches) == 2
    assert any(m["path"] == os.path.join(root, "README.md") for m in matches)
    assert any(m["path"] == os.path.join(root, "src", "README.md") for m in matches)
    assert all(m["line_ranges"] == [] for m in matches)


def test_find_matches_force_include_simple_filename_with_line_ranges_only_finds_root(
    search_setup_fs,
):
    """
    Tests that 'force:filename.ext:ranges' finds all matching files and applies ranges.
    This test's assertion is changed to reflect the refactored find_matches.
    """
    root, create_is_ignored = search_setup_fs
    query = f"{FORCE_INCLUDE_PREFIX}LICENSE:1,5"
    is_ignored = create_is_ignored()

    matches = find_matches(query, root, is_ignored, CONFIG["SEARCH_MAX_DEPTH"])

    # Changed: After refactoring, 'force:LICENSE:1,5' will now find ALL LICENSE files
    # because the early exit for simple filenames is removed, and is_ignored does not ignore them.
    assert len(matches) == 2
    assert any(
        m["path"] == os.path.join(root, "LICENSE") and m["line_ranges"] == [(1, 5)]
        for m in matches
    )
    assert any(
        m["path"] == os.path.join(root, "docs", "LICENSE") and m["line_ranges"] == [(1, 5)]
        for m in matches
    )


def test_find_matches_force_include_simple_filename_not_at_root_returns_empty(
    search_setup_fs, fs
):  # Added fs fixture
    """
    Tests that a bare 'force:filename.ext' query finds a file in a subdirectory,
    reflecting that simple name queries search recursively.
    """
    root, create_is_ignored = search_setup_fs

    # A file that only exists in a subdirectory, not at root
    fs.create_dir(os.path.join(root, "sub"))  # Ensure 'sub' directory exists for the file
    fs.create_file(os.path.join(root, "sub", "non_root_file.txt"))

    query = f"{FORCE_INCLUDE_PREFIX}non_root_file.txt"
    is_ignored = create_is_ignored()

    matches = find_matches(query, root, is_ignored, CONFIG["SEARCH_MAX_DEPTH"])
    assert len(matches) == 1


def test_find_matches_force_include_dotted_filename_only_finds_root(search_setup_fs):
    """
    Tests that 'force:.gitignore' now finds all .gitignore files due to refactoring.
    """
    root, create_is_ignored = search_setup_fs
    # Root .gitignore and src/.gitignore exist from fixture setup

    query = f"{FORCE_INCLUDE_PREFIX}.gitignore"

    # The query is `force:.gitignore`, so we must tell the IgnoreManager to override
    # any default ignore rule for `.gitignore` files.
    force_include_patterns = [".gitignore"]
    is_ignored = create_is_ignored(force_include_patterns=force_include_patterns)

    matches = find_matches(query, root, is_ignored, CONFIG["SEARCH_MAX_DEPTH"])
    assert (
        len(matches) == 2
    )  # Changed: Now finds both /project/.gitignore and /project/src/.gitignore
    assert any(m["path"] == os.path.join(root, ".gitignore") for m in matches)
    assert any(m["path"] == os.path.join(root, "src", ".gitignore") for m in matches)
    assert all(m["line_ranges"] == [] for m in matches)


def test_find_matches_force_include_path_with_slash_still_searches_deeply(search_setup_fs):
    """
    Tests that 'force:path/to/file.ext' (with a slash) still behaves like a normal
    recursive force-include, finding the file wherever it is, even if it's the only one.
    This ensures the new root-only logic doesn't interfere with path-specific queries.
    """
    root, create_is_ignored = search_setup_fs

    # This file is ignored by default (.gitignore rule: git_ignored_dir/)
    ignored_deep_file = os.path.join(root, "git_ignored_dir", "ignored_file.txt")

    query = f"{FORCE_INCLUDE_PREFIX}git_ignored_dir/ignored_file.txt"

    # The is_ignored function needs to know about the force-include pattern
    force_include_patterns = ["git_ignored_dir/ignored_file.txt"]
    is_ignored = create_is_ignored(force_include_patterns=force_include_patterns)

    matches = find_matches(query, root, is_ignored, CONFIG["SEARCH_MAX_DEPTH"])
    assert len(matches) == 1
    assert matches[0]["path"] == ignored_deep_file
    assert matches[0]["line_ranges"] == []
