# tests/unit/test_config.py
from pathlib import Path

import pytest

from ctxctx.config import apply_profile_config, get_default_config, load_profile_config
from ctxctx.exceptions import ConfigurationError


@pytest.fixture(autouse=True)
def setup_config(fs):
    """Ensures a fresh default config and root path are available for each test."""
    test_config = get_default_config()
    root_path = Path("/test_project")
    fs.create_dir(root_path)
    test_config["ROOT"] = str(root_path)
    # PROFILE_CONFIG_FILE is no longer a separate setting/attribute,
    # as profiles are merged into the default config file.
    return root_path, test_config


def create_profile_file(fs, root_path: Path, config_filename: str, content: str):
    """Helper to create the main YAML config file with profile content."""
    profile_path = root_path / config_filename
    fs.create_file(profile_path, contents=content)
    return profile_path


def test_load_profile_config_success(fs, setup_config):
    """
    Tests successful loading of a profile configuration from the main config file.
    ROI: High (Core profile feature). TTI: Low.
    """
    root_path, test_config = setup_config
    profile_content = """
profiles:
  dev:
    TREE_MAX_DEPTH: 5
    OUTPUT_FORMATS: ["md"]
    EXPLICIT_IGNORE_NAMES:
      - "temp_dev"
    queries:
      - "src/"
      - "tests/"
  prod:
    TREE_MAX_DEPTH: 2
    USE_GITIGNORE: False
"""
    # Create the main config file, which now contains profiles
    create_profile_file(fs, root_path, test_config.default_config_filename, profile_content)

    # Load from the main config file using its filename
    dev_profile = load_profile_config("dev", root_path, test_config.default_config_filename)
    assert dev_profile["TREE_MAX_DEPTH"] == 5
    assert "md" in dev_profile["OUTPUT_FORMATS"]
    assert "temp_dev" in dev_profile["EXPLICIT_IGNORE_NAMES"]
    assert "src/" in dev_profile["queries"]
    assert "tests/" in dev_profile["queries"]

    prod_profile = load_profile_config("prod", root_path, test_config.default_config_filename)
    assert prod_profile["TREE_MAX_DEPTH"] == 2
    assert prod_profile["USE_GITIGNORE"] is False


def test_load_profile_config_file_not_found(fs, setup_config):
    """
    Tests error handling when the main config file (containing profiles) does not exist.
    ROI: High (Robustness). TTI: Low.
    """
    root_path, test_config = setup_config
    # Do not create the file
    with pytest.raises(
        ConfigurationError,
        match=f"Configuration file not found: '.*{test_config.default_config_filename}'.*",
    ):
        load_profile_config("any_profile", root_path, test_config.default_config_filename)


def test_load_profile_config_malformed_yaml(fs, setup_config):
    """
    Tests error handling for malformed YAML in the main config file.
    ROI: High (Robustness). TTI: Low.
    """
    root_path, test_config = setup_config
    malformed_content = """
profiles:
  dev:
    TREE_MAX_DEPTH: 5
  - this is not yaml
"""
    create_profile_file(fs, root_path, test_config.default_config_filename, malformed_content)

    with pytest.raises(
        ConfigurationError,
        match=f"Error loading YAML config from '.*{test_config.default_config_filename}'.*",
    ):
        load_profile_config("dev", root_path, test_config.default_config_filename)


def test_load_profile_config_profile_not_found(fs, setup_config):
    """
    Tests error handling when the requested profile name is not in the file.
    ROI: High (User feedback). TTI: Low.
    """
    root_path, test_config = setup_config
    profile_content = """
profiles:
  only_profile:
    TREE_MAX_DEPTH: 5
"""
    create_profile_file(fs, root_path, test_config.default_config_filename, profile_content)

    with pytest.raises(
        ConfigurationError,
        match=f"Profile 'non_existent' not found in '.*{test_config.default_config_filename}'.*",
    ):
        load_profile_config("non_existent", root_path, test_config.default_config_filename)


def test_apply_profile_config_merging(setup_config):
    """
    Tests that apply_profile_config correctly merges different types of data.
    ROI: High (Core config modification). TTI: Medium.
    """
    root_path, base_config = setup_config

    test_config_for_merge = get_default_config()

    profile_data = {
        "TREE_MAX_DEPTH": 10,
        "OUTPUT_FORMATS": ["json", "txt"],  # New format, should extend
        "EXPLICIT_IGNORE_NAMES": {
            "new_ignore_item",
            "another_item",
        },  # New items, should update set
        "SUBSTRING_IGNORE_PATTERNS": ["new_substring"],  # New patterns, should extend list
        "NEW_SETTING": "value",  # New setting, should be added
    }

    apply_profile_config(test_config_for_merge, profile_data)

    # Assert against attributes of the Config object
    assert test_config_for_merge.tree_max_depth == 10

    # OUTPUT_FORMATS should contain 'md', 'json', 'txt' and be unique
    assert "md" in test_config_for_merge.output_formats
    assert "json" in test_config_for_merge.output_formats
    assert "txt" in test_config_for_merge.output_formats
    # Check for uniqueness and correct count
    assert len(set(test_config_for_merge.output_formats)) == 3

    # EXPLICIT_IGNORE_NAMES should have old and new items
    assert ".git" in test_config_for_merge.explicit_ignore_names  # From default
    assert "new_ignore_item" in test_config_for_merge.explicit_ignore_names
    assert "another_item" in test_config_for_merge.explicit_ignore_names
    # The default config now has 18 explicit ignore names
    # (15 from previous + 3 new ctxctx-internal items)
    # We added 2 more items from the profile.
    assert len(test_config_for_merge.explicit_ignore_names) == 18 + 2

    # SUBSTRING_IGNORE_PATTERNS should have old and new items
    assert "package-lock.json" in test_config_for_merge.substring_ignore_patterns  # From default
    assert "new_substring" in test_config_for_merge.substring_ignore_patterns
    # The default config has 7 substring patterns. We added 1 more.
    assert len(set(test_config_for_merge.substring_ignore_patterns)) == 7 + 1

    # New settings added to _data should be accessible via _data or potentially new attributes
    assert test_config_for_merge["NEW_SETTING"] == "value"
