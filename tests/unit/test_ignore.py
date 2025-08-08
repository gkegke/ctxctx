# tests/unit/test_ignore.py
import os

import pytest

from ctxctx.config import CONFIG, DEFAULT_CONFIG
from ctxctx.ignore import IgnoreManager


@pytest.fixture(autouse=True)
def setup_config_for_ignore_tests(fs):
    """Ensures CONFIG is reset and ROOT is set for each test in test_ignore.py."""
    # Reset CONFIG to its default state before each test
    # This fixture runs automatically due to autouse=True reset_config in conftest.py,
    # but explicitly setting CONFIG here ensures it's in a known state for setup.
    CONFIG.clear()
    CONFIG.update(DEFAULT_CONFIG.copy())

    # Create a dummy root directory
    root_path = "/test_project"
    fs.create_dir(root_path)
    CONFIG["ROOT"] = root_path
    # Configure specific ignore files for testing purposes
    CONFIG["ADDITIONAL_IGNORE_FILENAMES"] = [".testignore"]
    CONFIG["SCRIPT_DEFAULT_IGNORE_FILE"] = "ctxignore.txt"
    return root_path


# Existing fixture for general ignore tests (can still be used for base ignore scenarios)
@pytest.fixture
def ignore_manager(fs, setup_config_for_ignore_tests):
    """Fixture to provide a configured IgnoreManager with a fake filesystem."""
    root_path = setup_config_for_ignore_tests
    # Instantiate without force_include_patterns for general ignore tests
    return IgnoreManager(CONFIG, root_path)


def test_is_ignored_explicit_name(ignore_manager, fs):
    """
    Tests if a file/directory matching an explicit ignore name is ignored.
    ROI: High (Core ignore logic). TTI: Low.
    """
    fs.create_file(os.path.join(ignore_manager.root_path, "node_modules", "foo.js"))
    fs.create_dir(os.path.join(ignore_manager.root_path, "__pycache__"))
    assert (
        ignore_manager.is_ignored(os.path.join(ignore_manager.root_path, "node_modules", "foo.js"))
        is True
    )
    assert ignore_manager.is_ignored(os.path.join(ignore_manager.root_path, "__pycache__")) is True
    assert (
        ignore_manager.is_ignored(os.path.join(ignore_manager.root_path, "src", "main.py"))
        is False
    )


def test_is_ignored_substring_pattern(fs, setup_config_for_ignore_tests):
    """
    Tests if a file matching a substring ignore pattern is ignored.
    ROI: Medium (Covers common log/lock files). TTI: Low.
    """
    root_path = setup_config_for_ignore_tests
    # Adding to CONFIG directly ensures the fixture's cleanup is consistent
    CONFIG["SUBSTRING_IGNORE_PATTERNS"].append("temp_file")

    # Re-initialize IgnoreManager after config change if not using the fixture's auto-init
    manager = IgnoreManager(CONFIG, root_path)

    fs.create_file(os.path.join(root_path, "logs", "temp_file_001.log"))
    fs.create_file(os.path.join(root_path, "src", "sub", "another_temp_file.txt"))
    assert manager.is_ignored(os.path.join(root_path, "logs", "temp_file_001.log")) is True
    assert (
        manager.is_ignored(os.path.join(root_path, "src", "sub", "another_temp_file.txt")) is True
    )
    assert manager.is_ignored(os.path.join(root_path, "src", "file.py")) is False


def test_is_ignored_additional_ignore_files(fs, setup_config_for_ignore_tests):
    """
    Tests if additional ignore files (e.g., .dockerignore) are correctly applied.
    ROI: Medium (Supports wider project types). TTI: Low.
    """
    root_path = setup_config_for_ignore_tests
    fs.create_file(
        os.path.join(root_path, ".testignore"),
        contents="""
temp_data/
*.bak
""",
    )
    # Re-initialize IgnoreManager to load additional ignore files
    manager = IgnoreManager(CONFIG, root_path)

    fs.create_dir(os.path.join(root_path, "temp_data"))
    fs.create_file(os.path.join(root_path, "temp_data", "file.txt"))
    fs.create_file(os.path.join(root_path, "src", "image.bak"))

    assert manager.is_ignored(os.path.join(root_path, "temp_data", "file.txt")) is True
    assert manager.is_ignored(os.path.join(root_path, "src", "image.bak")) is True
    assert manager.is_ignored(os.path.join(root_path, "src", "model.json")) is False


def test_is_ignored_root_path_behavior(ignore_manager):
    """
    Tests that the root path itself is not ignored.
    ROI: Low (Edge case, but important for correctness). TTI: Low.
    """
    assert ignore_manager.is_ignored(ignore_manager.root_path) is False


# --- NEW Force Include Tests ---


def test_is_ignored_with_force_include_exact_file(fs, setup_config_for_ignore_tests):
    """
    Tests that a file normally ignored by explicit name is force-included.
    ROI: High (Core force-include logic). TTI: Low.
    """
    root_path = setup_config_for_ignore_tests
    # Create a file that would normally be ignored by EXPLICIT_IGNORE_NAMES (node_modules)
    fs.create_dir(os.path.join(root_path, "node_modules"))
    ignored_file = os.path.join(root_path, "node_modules", "foo.js")
    fs.create_file(ignored_file)

    # Instantiate IgnoreManager with a force-include pattern for this file
    force_include_patterns = ["node_modules/foo.js"]  # Relative path for force include pattern
    manager = IgnoreManager(CONFIG, root_path, force_include_patterns=force_include_patterns)

    # Assert that the file is NOT ignored due to force-include
    assert manager.is_ignored(ignored_file) is False

    # Also test an actual ignored file that is not force-included
    another_ignored_file = os.path.join(root_path, "node_modules", "bar.js")
    fs.create_file(another_ignored_file)
    assert manager.is_ignored(another_ignored_file) is True


def test_is_ignored_with_force_include_glob(fs, setup_config_for_ignore_tests):
    """
    Tests that files matching a glob force-include pattern override other ignore rules.
    ROI: High (Flexible force-include). TTI: Low.
    """
    root_path = setup_config_for_ignore_tests
    fs.create_dir(os.path.join(root_path, "logs"))
    temp_log_file = os.path.join(root_path, "logs", "temp_data_report.log")
    fs.create_file(temp_log_file)
    another_log_file = os.path.join(root_path, "app.log")
    fs.create_file(another_log_file)
    regular_file = os.path.join(root_path, "src", "main.py")
    fs.create_dir(os.path.join(root_path, "src"))
    fs.create_file(regular_file)

    # Add a generic ignore pattern for logs (e.g., in .gitignore or substring_ignore)
    fs.create_file(os.path.join(root_path, ".gitignore"), contents="*.log\n")
    CONFIG["SUBSTRING_IGNORE_PATTERNS"].append("temp_data")

    # Force include all log files with a glob
    force_include_patterns = ["*.log", "logs/*.log"]
    manager = IgnoreManager(CONFIG, root_path, force_include_patterns=force_include_patterns)

    assert manager.is_ignored(temp_log_file) is False  # Force-included despite substring ignore
    assert manager.is_ignored(another_log_file) is False  # Force-included despite .gitignore
    assert manager.is_ignored(regular_file) is False  # Should still not be ignored


def test_is_ignored_with_force_include_in_ignored_dir(fs, setup_config_for_ignore_tests):
    """
    Tests that a specific file inside an otherwise ignored directory can be force-included.
    ROI: Medium (Granular control). TTI: Low.
    """
    root_path = setup_config_for_ignore_tests
    # 'node_modules' is in DEFAULT_CONFIG['EXPLICIT_IGNORE_NAMES']
    ignored_dir = os.path.join(root_path, "node_modules")
    file_in_ignored_dir = os.path.join(ignored_dir, "some_package", "index.js")
    fs.create_dir(os.path.join(ignored_dir, "some_package"))
    fs.create_file(file_in_ignored_dir)

    # Force include the specific file
    force_include_patterns = ["node_modules/some_package/index.js"]
    manager = IgnoreManager(CONFIG, root_path, force_include_patterns=force_include_patterns)

    assert manager.is_ignored(file_in_ignored_dir) is False
    assert (
        manager.is_ignored(os.path.join(ignored_dir, "other.js")) is True
    )  # Other files in ignored dir still ignored


def test_is_ignored_force_include_precedence(fs, setup_config_for_ignore_tests):
    """
    Tests that force-include patterns take precedence over explicit ignore rules.
    ROI: High (Critical for feature correctness). TTI: Low.
    """
    root_path = setup_config_for_ignore_tests
    file_path = os.path.join(root_path, "important_config.yml")
    fs.create_file(file_path)

    # Make sure it's ignored by default by adding to explicit ignores
    CONFIG["EXPLICIT_IGNORE_NAMES"].add("important_config.yml")

    # Now, try to force include it
    force_include_patterns = ["important_config.yml"]
    manager = IgnoreManager(CONFIG, root_path, force_include_patterns=force_include_patterns)

    assert manager.is_ignored(file_path) is False

    # Check if a non-force-included file is still ignored
    other_ignored_file = os.path.join(root_path, "temp.log")
    fs.create_file(other_ignored_file)
    CONFIG["SUBSTRING_IGNORE_PATTERNS"].append("temp.log")
    # Re-initialize manager because CONFIG was changed after initial instantiation
    manager_reinit = IgnoreManager(
        CONFIG, root_path, force_include_patterns=force_include_patterns
    )
    assert manager_reinit.is_ignored(other_ignored_file) is True


def test_is_ignored_force_include_no_match(fs, setup_config_for_ignore_tests):
    """
    Tests that force-include patterns only affect matching files and don't override
    ignore rules for non-matching files.
    ROI: Medium (Ensures no unintended side effects). TTI: Low.
    """
    root_path = setup_config_for_ignore_tests
    ignored_file = os.path.join(root_path, "node_modules", "foo.js")
    fs.create_dir(os.path.join(root_path, "node_modules"))
    fs.create_file(ignored_file)

    # Force include a different pattern that doesn't match the ignored file
    force_include_patterns = ["src/*.py"]
    manager = IgnoreManager(CONFIG, root_path, force_include_patterns=force_include_patterns)

    # Assert that the original ignored file is still ignored
    assert manager.is_ignored(ignored_file) is True
