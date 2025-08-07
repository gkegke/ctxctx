# ctxctx/config.py
import os
import sys
import yaml
from typing import Dict, Any, List, Set, Union
from .exceptions import ConfigurationError # Import the custom exception
import copy # Added for deepcopy

# === CONFIGURATION ===
# Define the immutable default values structure
_DEFAULT_CONFIG_TEMPLATE = {
    'ROOT': '.',
    'OUTPUT_FILE_BASE_NAME': 'prompt_input_files',
    'OUTPUT_FORMATS': ('md', 'json'), # Changed to tuple for immutable default

    'TREE_MAX_DEPTH': 3,
    'TREE_EXCLUDE_EMPTY_DIRS': False,

    'SEARCH_MAX_DEPTH': 5,
    'MAX_MATCHES_PER_QUERY': 5,

    'EXPLICIT_IGNORE_NAMES': frozenset({ # Changed to frozenset for immutable default
        '.git', '.gitignore', 'node_modules', '__pycache__', '.venv', '.idea', '.DS_Store',
        '.vscode', 'dist', 'build', 'coverage', 'logs', 'temp', 'tmp',
        'playwright-report', 'playwright-results', 'test-results', 'playwright_user_data'
    }),
    'SUBSTRING_IGNORE_PATTERNS': ( # Changed to tuple for immutable default
        'package-lock.json',
        'playwright-report',
        'yarn.lock',
        'npm-debug.log',
        '.env',
        '__snapshots__',
        '.next',
        'out',
    ),
    'ADDITIONAL_IGNORE_FILENAMES': ('.dockerignore', '.npmignore', '.eslintignore'), # Changed to tuple

    'SCRIPT_DEFAULT_IGNORE_FILE': 'prompt_builder_ignore.txt', # This file will be looked for in the project root
    'PROFILE_CONFIG_FILE': 'prompt_profiles.yaml',
    'VERSION': '0.1.0',
    # --- New additions for .gitignore support ---
    'USE_GITIGNORE': True, # Whether to automatically load .gitignore files
    'GITIGNORE_PATH': '.gitignore', # Default .gitignore file name
}

def get_default_config() -> Dict[str, Any]:
    """Returns a deep copy of the default configuration, ensuring mutability for runtime."""
    default_copy = copy.deepcopy(_DEFAULT_CONFIG_TEMPLATE)
    # Convert immutable types back to mutable ones for CONFIG object's use
    default_copy['OUTPUT_FORMATS'] = list(default_copy['OUTPUT_FORMATS'])
    default_copy['EXPLICIT_IGNORE_NAMES'] = set(default_copy['EXPLICIT_IGNORE_NAMES'])
    default_copy['SUBSTRING_IGNORE_PATTERNS'] = list(default_copy['SUBSTRING_IGNORE_PATTERNS'])
    default_copy['ADDITIONAL_IGNORE_FILENAMES'] = list(default_copy['ADDITIONAL_IGNORE_FILENAMES'])
    return default_copy

CONFIG = get_default_config() # Initialize CONFIG with a fresh copy
DEFAULT_CONFIG = get_default_config() # Initialize CONFIG with a fresh copy

def _merge_dicts(d1: Dict[str, Any], d2: Dict[str, Any]) -> None:
    """Recursively merges d2 into d1. d2 overrides d1 for scalar values, merges for collections."""
    for k, v in d2.items():
        if k in d1 and isinstance(d1[k], dict) and isinstance(v, dict):
            _merge_dicts(d1[k], v)
        elif k in d1 and isinstance(d1[k], list) and isinstance(v, list):
            d1[k].extend(v)
            # For lists that represent unique items (like patterns), remove duplicates
            if k in ['OUTPUT_FORMATS', 'SUBSTRING_IGNORE_PATTERNS', 'ADDITIONAL_IGNORE_FILENAMES']:# Removed FUNCTION_PATTERNS as it's not in the default config
                d1[k] = list(set(d1[k]))
        elif k in d1 and isinstance(d1[k], set) and isinstance(v, set):
            d1[k].update(v)
        else:
            d1[k] = v

def load_profile_config(profile_name: str, root_path: str) -> Dict[str, Any]:
    """
    Loads configuration from a YAML profile file and returns the selected profile data.
    Raises ConfigurationError if file not found or profile not found.
    """
    profile_config_path = os.path.join(root_path, CONFIG['PROFILE_CONFIG_FILE'])

    if not os.path.isfile(profile_config_path):
        raise ConfigurationError(f"Profile configuration file not found: '{profile_config_path}'.")

    try:
        with open(profile_config_path, 'r', encoding='utf-8') as f:
            all_profiles_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Error loading YAML config from '{profile_config_path}': {e}")
    except Exception as e:
        raise ConfigurationError(f"Error reading YAML config file '{profile_config_path}': {e}")

    if not all_profiles_data or not isinstance(all_profiles_data, dict) or 'profiles' not in all_profiles_data:
        raise ConfigurationError(f"Invalid profile configuration file '{profile_config_path}'. Expected 'profiles' key at root.")

    if profile_name not in all_profiles_data['profiles']:
        raise ConfigurationError(f"Profile '{profile_name}' not found in '{profile_config_path}'.")

    return all_profiles_data['profiles'][profile_name]

def apply_profile_config(config: Dict[str, Any], profile_data: Dict[str, Any]) -> None:
    """Applies profile data to the main configuration dictionary."""
    _merge_dicts(config, profile_data)