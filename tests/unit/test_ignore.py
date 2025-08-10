# tests/unit/test_ignore.py
from pathlib import Path  # Added Path import

import pytest

from ctxctx.config import get_default_config
from ctxctx.ignore import IgnoreManager


@pytest.fixture(autouse=True)
def setup_config_for_ignore_tests(fs):
    """Ensures a fresh default config and root path are available for each test."""
    test_config = get_default_config()  # Get a fresh, mutable default config
    root_path = Path("/test_project")  # Changed to Path object
    fs.create_dir(root_path)
    test_config.root = root_path  # Set root directly on the Config object's attribute
    # Configure specific ignore files for testing purposes directly on test_config
    test_config.additional_ignore_filenames = [".testignore"]  # Access attributes
    test_config.script_default_ignore_file = "ctxignore.txt"  # Access attributes
    return root_path, test_config


def test_is_ignored_explicit_name(setup_config_for_ignore_tests, fs):
    """
    Tests if a file/directory matching an explicit ignore name is ignored.
    ROI: High (Core ignore logic). TTI: Low.
    """
    root_path, test_config = setup_config_for_ignore_tests
    manager = IgnoreManager(test_config)  # Instantiate manager within the test

    # Create paths as Path objects
    node_modules_file = root_path / "node_modules" / "foo.js"
    pycache_dir = root_path / "__pycache__"
    src_main_file = root_path / "src" / "main.py"

    fs.create_file(node_modules_file)
    fs.create_dir(pycache_dir)
    fs.create_dir(root_path / "src")
    fs.create_file(src_main_file)

    assert manager.is_ignored(node_modules_file) is True
    assert manager.is_ignored(pycache_dir) is True
    assert manager.is_ignored(src_main_file) is False


def test_is_ignored_substring_pattern(fs, setup_config_for_ignore_tests):
    """
    Tests if a file matching a substring ignore pattern is ignored.
    ROI: Medium (Covers common log/lock files). TTI: Low.
    """
    root_path, test_config = setup_config_for_ignore_tests
    # Adding to test_config directly ensures the instance uses it
    test_config.substring_ignore_patterns.append("temp_file")  # Access attribute

    # Re-initialize IgnoreManager after config change
    manager = IgnoreManager(test_config)

    # Create paths as Path objects
    log_file = root_path / "logs" / "temp_file_001.log"
    another_file = root_path / "src" / "sub" / "another_temp_file.txt"
    regular_file = root_path / "src" / "file.py"

    fs.create_dir(root_path / "logs")
    fs.create_file(log_file)
    fs.create_dir(root_path / "src" / "sub")
    fs.create_file(another_file)
    fs.create_file(regular_file)

    assert manager.is_ignored(log_file) is True
    assert manager.is_ignored(another_file) is True
    assert manager.is_ignored(regular_file) is False


def test_is_ignored_additional_ignore_files(fs, setup_config_for_ignore_tests):
    """
    Tests if additional ignore files (e.g., .dockerignore) are correctly applied.
    ROI: Medium (Supports wider project types). TTI: Low.
    """
    root_path, test_config = setup_config_for_ignore_tests
    # Use Path / operator
    testignore_path = root_path / ".testignore"
    fs.create_file(
        testignore_path,
        contents="""
temp_data/
*.bak
""",
    )
    # Re-initialize IgnoreManager to load additional ignore files
    manager = IgnoreManager(test_config)

    # Create paths as Path objects
    temp_data_dir = root_path / "temp_data"
    temp_data_file = temp_data_dir / "file.txt"
    image_bak_file = root_path / "src" / "image.bak"
    model_json_file = root_path / "src" / "model.json"

    fs.create_dir(temp_data_dir)
    fs.create_file(temp_data_file)
    fs.create_dir(root_path / "src")
    fs.create_file(image_bak_file)
    fs.create_file(model_json_file)

    assert manager.is_ignored(temp_data_file) is True
    assert manager.is_ignored(image_bak_file) is True
    assert manager.is_ignored(model_json_file) is False


def test_is_ignored_root_path_behavior(setup_config_for_ignore_tests):
    """
    Tests that the root path itself is not ignored.
    ROI: Low (Edge case, but important for correctness). TTI: Low.
    """
    root_path, test_config = setup_config_for_ignore_tests
    manager = IgnoreManager(test_config)
    assert manager.is_ignored(root_path) is False


# --- NEW Force Include Tests ---


def test_is_ignored_with_force_include_exact_file(fs, setup_config_for_ignore_tests):
    """
    Tests that a file normally ignored by explicit name is force-included.
    ROI: High (Core force-include logic). TTI: Low.
    """
    root_path, test_config = setup_config_for_ignore_tests
    # Create a file that would normally be ignored by EXPLICIT_IGNORE_NAMES (node_modules)
    node_modules_dir = root_path / "node_modules"
    ignored_file = node_modules_dir / "foo.js"
    fs.create_dir(node_modules_dir)
    fs.create_file(ignored_file)

    # Instantiate IgnoreManager with a force-include pattern for this file
    force_include_patterns = ["node_modules/foo.js"]  # Relative path for force include pattern
    manager = IgnoreManager(test_config, force_include_patterns=force_include_patterns)

    # Assert that the file is NOT ignored due to force-include
    assert manager.is_ignored(ignored_file) is False

    # Also test an actual ignored file that is not force-included
    another_ignored_file = node_modules_dir / "bar.js"
    fs.create_file(another_ignored_file)
    assert manager.is_ignored(another_ignored_file) is True


def test_is_ignored_with_force_include_glob(fs, setup_config_for_ignore_tests):
    """
    Tests that files matching a glob force-include pattern override other ignore rules.
    ROI: High (Flexible force-include). TTI: Low.
    """
    root_path, test_config = setup_config_for_ignore_tests
    logs_dir = root_path / "logs"
    temp_log_file = logs_dir / "temp_data_report.log"
    another_log_file = root_path / "app.log"
    src_dir = root_path / "src"
    regular_file = src_dir / "main.py"

    fs.create_dir(logs_dir)
    fs.create_file(temp_log_file)
    fs.create_file(another_log_file)
    fs.create_dir(src_dir)
    fs.create_file(regular_file)

    # Add a generic ignore pattern for logs (e.g., in .gitignore or substring_ignore)
    fs.create_file(root_path / ".gitignore", contents="*.log\n")
    # Changed: Modify the test_config attribute
    test_config.substring_ignore_patterns.append("temp_data")

    # Force include all log files with a glob
    force_include_patterns = ["*.log", "logs/*.log"]
    manager = IgnoreManager(test_config, force_include_patterns=force_include_patterns)

    assert manager.is_ignored(temp_log_file) is False  # Force-included despite substring ignore
    assert manager.is_ignored(another_log_file) is False  # Force-included despite .gitignore
    assert manager.is_ignored(regular_file) is False  # Should still not be ignored


def test_is_ignored_with_force_include_in_ignored_dir(fs, setup_config_for_ignore_tests):
    """
    Tests that a specific file inside an otherwise ignored directory can be force-included.
    ROI: Medium (Granular control). TTI: Low.
    """
    root_path, test_config = setup_config_for_ignore_tests
    # 'node_modules' is in DEFAULT_CONFIG['EXPLICIT_IGNORE_NAMES']
    ignored_dir = root_path / "node_modules"
    file_in_ignored_dir = ignored_dir / "some_package" / "index.js"
    fs.create_dir(ignored_dir / "some_package")
    fs.create_file(file_in_ignored_dir)

    # Force include the specific file
    force_include_patterns = ["node_modules/some_package/index.js"]
    manager = IgnoreManager(test_config, force_include_patterns=force_include_patterns)

    assert manager.is_ignored(file_in_ignored_dir) is False
    assert (
        manager.is_ignored(ignored_dir / "other.js")
    ) is True  # Other files in ignored dir still ignored


def test_is_ignored_force_include_precedence(fs, setup_config_for_ignore_tests):
    """
    Tests that force-include patterns take precedence over explicit ignore rules.
    ROI: High (Critical for feature correctness). TTI: Low.
    """
    root_path, test_config = setup_config_for_ignore_tests
    file_path = root_path / "important_config.yml"
    fs.create_file(file_path)

    # Make sure it's ignored by default by adding to explicit ignores
    # Changed: Modify the test_config attribute
    test_config.explicit_ignore_names.add("important_config.yml")

    # Now, try to force include it
    force_include_patterns = ["important_config.yml"]
    manager = IgnoreManager(test_config, force_include_patterns=force_include_patterns)

    assert manager.is_ignored(file_path) is False

    # Check if a non-force-included file is still ignored
    other_ignored_file = root_path / "temp.log"
    fs.create_file(other_ignored_file)
    # Changed: Modify the test_config attribute
    test_config.substring_ignore_patterns.append("temp.log")
    # Re-initialize manager because config was changed
    manager_reinit = IgnoreManager(test_config, force_include_patterns=force_include_patterns)
    assert manager_reinit.is_ignored(other_ignored_file) is True


def test_is_ignored_force_include_no_match(fs, setup_config_for_ignore_tests):
    """
    Tests that force-include patterns only affect matching files and don't override
    ignore rules for non-matching files.
    ROI: Medium (Ensures no unintended side effects). TTI: Low.
    """
    root_path, test_config = setup_config_for_ignore_tests
    ignored_dir = root_path / "node_modules"
    ignored_file = ignored_dir / "foo.js"
    fs.create_dir(ignored_dir)
    fs.create_file(ignored_file)

    # Force include a different pattern that doesn't match the ignored file
    force_include_patterns = ["src/*.py"]
    manager = IgnoreManager(test_config, force_include_patterns=force_include_patterns)

    # Assert that the original ignored file is still ignored
    assert manager.is_ignored(ignored_file) is True
