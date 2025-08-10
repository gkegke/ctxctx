# tests/unit/test_config.py
from pathlib import Path  # Added Path import

import pytest

from ctxctx.config import apply_profile_config, get_default_config, load_profile_config
from ctxctx.exceptions import ConfigurationError


@pytest.fixture(autouse=True)
def setup_config(fs):
    """Ensures a fresh default config and root path are available for each test."""
    test_config = get_default_config()  # Get a fresh, mutable default config
    root_path = Path("/test_project")  # Changed to Path object
    fs.create_dir(root_path)
    # The Config object's `root` attribute is automatically resolved from the internal _data
    test_config["ROOT"] = str(root_path)  # Pass as string, Config will convert to Path.resolve()
    # Changed: Set PROFILE_CONFIG_FILE on the *test_config* dictionary for the instance
    test_config["PROFILE_CONFIG_FILE"] = "test_profiles.yaml"
    return root_path, test_config


# Changed: create_profile_file now takes the specific config dictionary
def create_profile_file(
    fs, root_path: Path, config_dict, content
):  # Added type hint for root_path
    """Helper to create the profile YAML file."""
    # Use Path / operator for cleaner path joining
    profile_path = root_path / config_dict["PROFILE_CONFIG_FILE"]
    fs.create_file(profile_path, contents=content)
    return profile_path


# Changed: fixture now provides test_config
def test_load_profile_config_success(fs, setup_config):
    """
    Tests successful loading of a profile configuration.
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
    # Changed: Pass test_config to create_profile_file
    create_profile_file(fs, root_path, test_config._data, profile_content)  # Pass _data dict

    # Changed: Pass profile_config_filename from test_config's internal data
    dev_profile = load_profile_config("dev", root_path, test_config.profile_config_file)
    assert dev_profile["TREE_MAX_DEPTH"] == 5
    assert "md" in dev_profile["OUTPUT_FORMATS"]
    assert "temp_dev" in dev_profile["EXPLICIT_IGNORE_NAMES"]
    assert "src/" in dev_profile["queries"]
    assert "tests/" in dev_profile["queries"]

    # Changed: Pass profile_config_filename from test_config's internal data
    prod_profile = load_profile_config("prod", root_path, test_config.profile_config_file)
    assert prod_profile["TREE_MAX_DEPTH"] == 2
    assert prod_profile["USE_GITIGNORE"] is False


# Changed: fixture now provides test_config
def test_load_profile_config_file_not_found(fs, setup_config):
    """
    Tests error handling when the profile file does not exist.
    ROI: High (Robustness). TTI: Low.
    """
    root_path, test_config = setup_config
    # Do not create the file
    with pytest.raises(
        ConfigurationError, match=r"Profile configuration file not found: '.*test_profiles.yaml'.*"
    ):
        # Changed: Pass profile_config_filename from test_config's internal data
        load_profile_config("any_profile", root_path, test_config.profile_config_file)


# Changed: fixture now provides test_config
def test_load_profile_config_malformed_yaml(fs, setup_config):
    """
    Tests error handling for malformed YAML in the profile file.
    ROI: High (Robustness). TTI: Low.
    """
    root_path, test_config = setup_config
    malformed_content = """
profiles:
  dev:
    TREE_MAX_DEPTH: 5
  - this is not yaml
"""
    # Changed: Pass test_config to create_profile_file
    create_profile_file(fs, root_path, test_config._data, malformed_content)  # Pass _data dict

    with pytest.raises(
        ConfigurationError, match=r"Error loading YAML config from '.*test_profiles.yaml'.*"
    ):
        # Changed: Pass profile_config_filename from test_config's internal data
        load_profile_config("dev", root_path, test_config.profile_config_file)


# Changed: fixture now provides test_config
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
    # Changed: Pass test_config to create_profile_file
    create_profile_file(fs, root_path, test_config._data, profile_content)  # Pass _data dict

    with pytest.raises(
        ConfigurationError, match=r"Profile 'non_existent' not found in '.*test_profiles.yaml'.*"
    ):
        # Changed: Pass profile_config_filename from test_config's internal data
        load_profile_config("non_existent", root_path, test_config.profile_config_file)


# Changed: fixture now provides test_config
def test_apply_profile_config_merging(setup_config):
    """
    Tests that apply_profile_config correctly merges different types of data.
    ROI: High (Core config modification). TTI: Medium.
    """
    root_path, base_config = setup_config  # Use base_config from fixture

    # Start with a mutable copy of the default CONFIG for this test
    # Changed: Create a new Config object for manipulation, not a dict copy
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

    # Changed: Apply profile to the test-specific config object
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
    # The default config has 14 explicit ignore names. We added 2 more.
    assert len(test_config_for_merge.explicit_ignore_names) == 14 + 2

    # SUBSTRING_IGNORE_PATTERNS should have old and new items
    assert "package-lock.json" in test_config_for_merge.substring_ignore_patterns  # From default
    assert "new_substring" in test_config_for_merge.substring_ignore_patterns
    # The default config has 7 substring patterns. We added 1 more.
    assert len(set(test_config_for_merge.substring_ignore_patterns)) == 7 + 1

    # New settings added to _data should be accessible via _data or potentially new attributes
    # For a truly 'new_setting', it wouldn't have an attribute, so direct _data access is fine.
    assert test_config_for_merge["NEW_SETTING"] == "value"
