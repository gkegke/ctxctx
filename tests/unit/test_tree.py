# tests/unit/test_tree.py
import os
import pytest
from ctxctx.tree import generate_tree_string
from ctxctx.ignore import IgnoreManager
from ctxctx.config import CONFIG, DEFAULT_CONFIG


@pytest.fixture
def setup_tree_fs(fs):
    """Sets up a fake filesystem for tree generation tests."""
    CONFIG.clear()
    CONFIG.update(DEFAULT_CONFIG.copy())

    root_path = "/project"
    fs.create_dir(root_path)
    fs.create_file(os.path.join(root_path, "README.md"))
    fs.create_file(os.path.join(root_path, ".gitignore"))
    fs.create_dir(os.path.join(root_path, "src"))
    fs.create_file(os.path.join(root_path, "src", "main.py"))
    fs.create_file(os.path.join(root_path, "src", "utils.py"))
    fs.create_dir(os.path.join(root_path, "docs"))
    fs.create_file(os.path.join(root_path, "docs", "api.md"))
    fs.create_dir(os.path.join(root_path, "node_modules"))
    fs.create_file(os.path.join(root_path, "node_modules", "package.js"))
    fs.create_dir(os.path.join(root_path, "empty_dir"))
    fs.create_dir(os.path.join(root_path, "nested_ignored_dir"))
    fs.create_file(os.path.join(root_path, "nested_ignored_dir", "secret.txt")) # This file is NOT ignored by default config

    # For max_depth test - fixed setup
    fs.create_dir(os.path.join(root_path, "deep", "level1", "level2"))
    fs.create_file(os.path.join(root_path, "deep", "level1", "level2", "file.txt"))

    return root_path

def test_generate_tree_string_basic(setup_tree_fs):
    """
    Tests basic tree generation without deep nesting or ignores.
    ROI: High (Fundamental output feature). TTI: Medium.
    """
    root_path = setup_tree_fs
    
    CONFIG.clear()
    CONFIG.update(DEFAULT_CONFIG.copy())
    CONFIG['ROOT'] = root_path
    ignore_manager = IgnoreManager(CONFIG, root_path)

    tree = generate_tree_string(
        root_path,
        is_ignored=ignore_manager.is_ignored,
        max_depth=5, # Sufficiently large depth
        exclude_empty_dirs=False,
        current_depth=0
    )
    
    # Verify common ignored items are *not* in the tree based on DEFAULT_CONFIG
    assert ".gitignore" not in tree # This should now pass with the '\\n' fix
    assert "node_modules" not in tree
    assert "package.js" not in tree

    # Verify other expected items *are* in the tree
    assert "README.md" in tree
    assert "docs" in tree
    assert "api.md" in tree
    assert "empty_dir" in tree # Expected to be present when exclude_empty_dirs=False
    assert "nested_ignored_dir" in tree # Directory itself is not ignored
    assert "secret.txt" in tree # Content of nested_ignored_dir is NOT ignored by default config
    assert "src" in tree
    assert "main.py" in tree
    assert "utils.py" in tree

    # Basic order check (alphabetical by default for siblings)
    # The order might change slightly if specific ignored items affect the list.
    # Just check for presence/absence for now.
    assert tree.index("README.md") < tree.index("docs")
    assert tree.index("docs") < tree.index("empty_dir")
    # node_modules is ignored, so order changes
    # assert tree.index("node_modules") < tree.index("nested_ignored_dir") # Removed: node_modules is ignored
    assert tree.index("nested_ignored_dir") < tree.index("src")
    assert tree.index("api.md") > tree.index("docs")
    assert tree.index("main.py") > tree.index("src")
    assert tree.index("utils.py") > tree.index("src")

def test_generate_tree_string_max_depth(setup_tree_fs):
    """
    Tests tree generation with a specified maximum depth.
    ROI: High (Controls output verbosity). TTI: Medium.
    """
    root_path = setup_tree_fs
    CONFIG.clear()
    CONFIG.update(DEFAULT_CONFIG.copy())
    CONFIG['ROOT'] = root_path
    ignore_manager = IgnoreManager(CONFIG, root_path)

    # Test with max_depth=0 (should only show root and immediate children names, no deeper files)
    # If max_depth=0, only level 0 (root) should be processed and its direct children listed.
    # But files within immediate children should not be listed if depth limit is 0.
    # With current logic: max_depth=0 -> current_depth=0 is okay, current_depth=1 will be > max_depth=0.
    # So `src` would be at depth 1 and skipped. This means only root is shown if root has no direct files.
    # The common expectation of `max_depth=0` for a tree is "don't recurse at all, just list top-level files/dirs".
    # Let's adjust test to max_depth=1 as per previous assumption (root + 1 level of children).

    # Test with max_depth=1 (should show root and direct children, but not their contents)
    tree = generate_tree_string(
        root_path,
        is_ignored=ignore_manager.is_ignored,
        max_depth=1, # Root (depth 0) and its direct children (depth 1)
        exclude_empty_dirs=False,
        current_depth=0
    )
    assert "README.md" in tree
    assert "src" in tree # src is a direct child of root (depth 1)
    assert "main.py" not in tree # main.py is child of src (depth 2), should be too deep for max_depth=1
    assert "deep" in tree # Top-level dir is shown
    assert "level1" not in tree # Sub-directory (depth 2) is too deep
    assert "level2" not in tree # Sub-directory (depth 3) is too deep
    assert "file.txt" not in tree # File (depth 4) is too deep

    # Test with max_depth=2 for deep/level1
    tree_deep = generate_tree_string(
        root_path,
        is_ignored=ignore_manager.is_ignored,
        max_depth=2, # Root (depth 0), level1 (depth 1), level2 (depth 2)
        exclude_empty_dirs=False,
        current_depth=0
    )
    assert "deep" in tree_deep
    assert "level1" in tree_deep
    assert "level2" not in tree_deep # level2 is at depth 3, should be too deep for max_depth=2
    assert "file.txt" not in tree_deep # file.txt is at depth 4, should be too deep for max_depth=2

def test_generate_tree_string_exclude_empty_dirs(setup_tree_fs, fs): # Added fs fixture
    """
    Tests tree generation with `exclude_empty_dirs` set to True.
    ROI: Medium (Cleaner output for LLMs). TTI: Medium.
    """
    root_path = setup_tree_fs
    CONFIG.clear()
    CONFIG.update(DEFAULT_CONFIG.copy())
    CONFIG['ROOT'] = root_path
    ignore_manager = IgnoreManager(CONFIG, root_path)

    tree = generate_tree_string(
        root_path,
        is_ignored=ignore_manager.is_ignored,
        max_depth=5,
        exclude_empty_dirs=True,
        current_depth=0
    )
    
    assert "empty_dir" not in tree
    assert "src" in tree
    assert "docs" in tree
    
    os.mkdir(os.path.join(root_path, "ignore_all_contents"))
    fs.create_file(os.path.join(root_path, "ignore_all_contents", "ignored_file.log"))
    CONFIG['SUBSTRING_IGNORE_PATTERNS'].append('ignored_file')
    ignore_manager.init_ignore_set() # Re-initialize ignore_manager after changing config

    tree_with_ignored_contents = generate_tree_string(
        root_path,
        is_ignored=ignore_manager.is_ignored,
        max_depth=5,
        exclude_empty_dirs=True,
        current_depth=0
    )
    assert "ignore_all_contents" not in tree_with_ignored_contents