# tests/unit/test_tree.py
from pathlib import Path  # Added Path import

import pytest

from ctxctx.config import get_default_config  # Added Config import
from ctxctx.ignore import IgnoreManager
from ctxctx.tree import generate_tree_string


@pytest.fixture
def setup_tree_fs(fs):
    """Sets up a fake filesystem for tree generation tests."""
    test_config = get_default_config()  # Get a fresh, mutable default config

    root_path = Path("/project")  # Changed to Path object
    fs.create_dir(root_path)
    fs.create_file(root_path / "README.md")
    fs.create_file(root_path / ".gitignore")  # This file should now be ignored by default
    fs.create_dir(root_path / "src")
    fs.create_file(root_path / "src" / "main.py")
    fs.create_file(root_path / "src" / "utils.py")
    fs.create_dir(root_path / "docs")
    fs.create_file(root_path / "docs" / "api.md")
    fs.create_dir(root_path / "node_modules")
    fs.create_file(root_path / "node_modules" / "package.js")
    fs.create_dir(root_path / "empty_dir")
    fs.create_dir(root_path / "nested_ignored_dir")
    fs.create_file(root_path / "nested_ignored_dir" / "secret.txt")

    # For max_depth test - fixed setup
    deep_path = root_path / "deep" / "level1" / "level2"
    fs.create_dir(deep_path)
    fs.create_file(deep_path / "file.txt")

    # Changed: Set ROOT on the *test_config* object's attribute
    test_config.root = root_path

    return root_path, test_config


def test_generate_tree_string_basic(setup_tree_fs):
    """
    Tests basic tree generation without deep nesting or ignores.
    ROI: High (Fundamental output feature). TTI: Medium.
    """
    root_path, test_config = setup_tree_fs

    # Changed: Pass test_config to IgnoreManager
    ignore_manager = IgnoreManager(test_config)

    # Pass the config object instead of individual max_depth and exclude_empty_dirs
    tree = generate_tree_string(
        root_path,
        is_ignored=ignore_manager.is_ignored,
        config=test_config,  # Pass the config object
        current_depth=0,
    )

    # Verify common ignored items are *not* in the tree based on DEFAULT_CONFIG
    assert ".gitignore" not in tree
    assert "node_modules" not in tree
    assert "package.js" not in tree

    # Verify other expected items *are* in the tree
    assert "README.md" in tree
    assert "docs" in tree
    assert "api.md" in tree
    assert "empty_dir" in tree  # Expected to be present when exclude_empty_dirs=False in config
    assert "nested_ignored_dir" in tree  # Directory itself is not ignored by default
    assert "secret.txt" in tree  # Content of nested_ignored_dir is NOT ignored by default config
    assert "src" in tree
    assert "main.py" in tree
    assert "utils.py" in tree

    # Basic order check (alphabetical by default for siblings)
    # The order might change slightly if specific ignored items affect the list.
    # Just check for presence/absence for now.
    assert tree.index("README.md") < tree.index("docs")
    assert tree.index("docs") < tree.index("empty_dir")
    # node_modules is ignored, so order changes
    assert tree.index("nested_ignored_dir") < tree.index("src")
    assert tree.index("api.md") > tree.index("docs")
    assert tree.index("main.py") > tree.index("src")
    assert tree.index("utils.py") > tree.index("src")


def test_generate_tree_string_max_depth(setup_tree_fs):
    """
    Tests tree generation with a specified maximum depth.
    ROI: High (Controls output verbosity). TTI: Medium.
    """
    root_path, test_config = setup_tree_fs
    # Changed: Pass test_config to IgnoreManager
    ignore_manager = IgnoreManager(test_config)

    # Temporarily modify config for this test
    test_config.tree_max_depth = 1  # Set max_depth attribute on config

    # Pass the config object
    tree = generate_tree_string(
        root_path,
        is_ignored=ignore_manager.is_ignored,
        config=test_config,
        current_depth=0,
    )
    assert "README.md" in tree
    assert "src" in tree  # src is a direct child of root (depth 1)
    assert (
        "main.py" not in tree
    )  # main.py is child of src (depth 2), should be too deep for max_depth=1
    assert "deep" in tree  # Top-level dir is shown
    assert "level1" not in tree  # Sub-directory (depth 2) is too deep
    assert "level2" not in tree  # Sub-directory (depth 3) is too deep
    assert "file.txt" not in tree  # File (depth 4) is too deep

    # Test with max_depth=2 for deep/level1
    test_config.tree_max_depth = 2  # Set max_depth attribute on config
    tree_deep = generate_tree_string(
        root_path,
        is_ignored=ignore_manager.is_ignored,
        config=test_config,
        current_depth=0,
    )
    assert "deep" in tree_deep
    assert "level1" in tree_deep
    assert "level2" not in tree_deep  # level2 is at depth 3, should be too deep for max_depth=2
    assert (
        "file.txt" not in tree_deep
    )  # file.txt is at depth 4, should be too deep for max_depth=2


def test_generate_tree_string_exclude_empty_dirs(setup_tree_fs, fs):
    """
    Tests tree generation with `exclude_empty_dirs` set to True.
    ROI: Medium (Cleaner output for LLMs). TTI: Medium.
    """
    root_path, test_config = setup_tree_fs
    # Changed: Pass test_config to IgnoreManager
    ignore_manager = IgnoreManager(test_config)

    # Temporarily modify config for this test
    test_config.tree_exclude_empty_dirs = True  # Set exclude_empty_dirs attribute on config

    tree = generate_tree_string(
        root_path,
        is_ignored=ignore_manager.is_ignored,
        config=test_config,
        current_depth=0,
    )

    assert "empty_dir" not in tree
    assert "src" in tree
    assert "docs" in tree

    ignore_all_contents_dir = root_path / "ignore_all_contents"
    fs.create_dir(ignore_all_contents_dir)
    fs.create_file(ignore_all_contents_dir / "ignored_file.log")
    # Changed: Modify the test_config attribute
    test_config.substring_ignore_patterns.append("ignored_file")
    # Re-initialize ignore_manager because config was changed
    ignore_manager = IgnoreManager(test_config)

    tree_with_ignored_contents = generate_tree_string(
        root_path,
        is_ignored=ignore_manager.is_ignored,
        config=test_config,
        current_depth=0,
    )
    assert "ignore_all_contents" not in tree_with_ignored_contents
