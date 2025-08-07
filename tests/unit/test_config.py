# tests/unit/test_config.py
import os
import pytest
import yaml
from ctxctx.config import CONFIG, get_default_config, load_profile_config, apply_profile_config
from ctxctx.exceptions import ConfigurationError

@pytest.fixture(autouse=True)
def setup_config(fs):
    """Ensures CONFIG is reset and ROOT is set for each test, creates profile file."""
    # Reset CONFIG to its default state before each test
    CONFIG.clear() # Clear existing, then update with a fresh default
    CONFIG.update(get_default_config())

    # Create a dummy root directory
    root_path = "/test_project"
    fs.create_dir(root_path)
    CONFIG['ROOT'] = root_path
    CONFIG['PROFILE_CONFIG_FILE'] = "test_profiles.yaml" # Use a specific name for tests
    return root_path

def create_profile_file(fs, root_path, content):
    """Helper to create the profile YAML file."""
    profile_path = os.path.join(root_path, CONFIG['PROFILE_CONFIG_FILE'])
    fs.create_file(profile_path, contents=content)
    return profile_path

def test_load_profile_config_success(fs, setup_config):
    """
    Tests successful loading of a profile configuration.
    ROI: High (Core profile feature). TTI: Low.
    """
    root_path = setup_config
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
    create_profile_file(fs, root_path, profile_content)

    dev_profile = load_profile_config("dev", root_path)
    assert dev_profile['TREE_MAX_DEPTH'] == 5
    assert "md" in dev_profile['OUTPUT_FORMATS']
    assert "temp_dev" in dev_profile['EXPLICIT_IGNORE_NAMES']
    assert "src/" in dev_profile['queries']
    assert "tests/" in dev_profile['queries']

    prod_profile = load_profile_config("prod", root_path)
    assert prod_profile['TREE_MAX_DEPTH'] == 2
    assert prod_profile['USE_GITIGNORE'] is False

def test_load_profile_config_file_not_found(fs, setup_config):
    """
    Tests error handling when the profile file does not exist.
    ROI: High (Robustness). TTI: Low.
    """
    root_path = setup_config
    # Do not create the file
    with pytest.raises(ConfigurationError, match=r"Profile configuration file not found: '.*test_profiles.yaml'.*"):
        load_profile_config("any_profile", root_path)

def test_load_profile_config_malformed_yaml(fs, setup_config):
    """
    Tests error handling for malformed YAML in the profile file.
    ROI: High (Robustness). TTI: Low.
    """
    root_path = setup_config
    malformed_content = """
profiles:
  dev:
    TREE_MAX_DEPTH: 5
  - this is not yaml
"""
    create_profile_file(fs, root_path, malformed_content)

    with pytest.raises(ConfigurationError, match=r"Error loading YAML config from '.*test_profiles.yaml'.*"):
        load_profile_config("dev", root_path)

def test_load_profile_config_profile_not_found(fs, setup_config):
    """
    Tests error handling when the requested profile name is not in the file.
    ROI: High (User feedback). TTI: Low.
    """
    root_path = setup_config
    profile_content = """
profiles:
  only_profile:
    TREE_MAX_DEPTH: 5
"""
    create_profile_file(fs, root_path, profile_content)

    with pytest.raises(ConfigurationError, match=r"Profile 'non_existent' not found in '.*test_profiles.yaml'.*"):
        load_profile_config("non_existent", root_path)

def test_apply_profile_config_merging(setup_config):
    """
    Tests that apply_profile_config correctly merges different types of data.
    ROI: High (Core config modification). TTI: Medium.
    """
    # Start with default CONFIG (reset by fixture)
    initial_config = get_default_config() # Get a fresh default for comparison

    profile_data = {
        'TREE_MAX_DEPTH': 10,
        'OUTPUT_FORMATS': ["json", "txt"], # New format, should extend
        'EXPLICIT_IGNORE_NAMES': {"new_ignore_item", "another_item"}, # New items, should update set
        'SUBSTRING_IGNORE_PATTERNS': ["new_substring"], # New patterns, should extend list
        # 'FUNCTION_PATTERNS': {'.js': "new_js_regex"}, # This key is not in default config
        'NEW_SETTING': "value" # New setting, should be added
    }

    apply_profile_config(CONFIG, profile_data)

    assert CONFIG['TREE_MAX_DEPTH'] == 10
    
    # OUTPUT_FORMATS should contain 'md', 'json', 'txt' and be unique
    assert 'md' in CONFIG['OUTPUT_FORMATS']
    assert 'json' in CONFIG['OUTPUT_FORMATS']
    assert 'txt' in CONFIG['OUTPUT_FORMATS']
    assert len(set(CONFIG['OUTPUT_FORMATS'])) == 3 # Check for uniqueness

    # EXPLICIT_IGNORE_NAMES should have old and new items
    assert '.git' in CONFIG['EXPLICIT_IGNORE_NAMES'] # From default
    assert 'new_ignore_item' in CONFIG['EXPLICIT_IGNORE_NAMES']
    assert 'another_item' in CONFIG['EXPLICIT_IGNORE_NAMES']
    
    # SUBSTRING_IGNORE_PATTERNS should have old and new items
    assert 'package-lock.json' in CONFIG['SUBSTRING_IGNORE_PATTERNS'] # From default
    assert 'new_substring' in CONFIG['SUBSTRING_IGNORE_PATTERNS']
    assert len(set(CONFIG['SUBSTRING_IGNORE_PATTERNS'])) == len(initial_config['SUBSTRING_IGNORE_PATTERNS']) + 1 # Check uniqueness

    assert CONFIG['NEW_SETTING'] == "value"