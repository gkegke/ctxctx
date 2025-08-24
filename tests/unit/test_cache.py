import time
from pathlib import Path

import pytest

from ctxctx import cache
from ctxctx.config import Config, get_default_config


@pytest.fixture
def temp_config(tmp_path: Path) -> Config:
    """Provides a Config object with its root set to a temporary directory for test isolation."""
    config = get_default_config()
    config.root = tmp_path
    # Create a dummy config file, as its mtime is tracked for cache invalidation
    config.default_config_filename = "test.ctxctx.yaml"
    (tmp_path / config.default_config_filename).touch()
    return config


def test_save_and_load_cache_happy_path(temp_config: Config):
    """Tests that a file list can be saved and then loaded successfully."""
    # Arrange
    file_list = [temp_config.root / "src/main.py", temp_config.root / "README.md"]
    for p in file_list:
        p.parent.mkdir(exist_ok=True, parents=True)
        p.touch()

    # Act: Save the cache
    cache.save_cache(temp_config, "test_profile", file_list)

    # Assert: Cache file exists
    cache_filepath = cache._get_cache_filepath(temp_config)
    assert cache_filepath.exists()

    # Act: Load the cache
    loaded_files = cache.load_cache(temp_config, "test_profile")

    # Assert: Loaded data matches saved data
    assert loaded_files is not None
    assert isinstance(loaded_files, list)
    assert all(isinstance(p, Path) for p in loaded_files)
    assert set(loaded_files) == set(file_list)


def test_load_cache_invalidated_by_mtime(temp_config: Config):
    """Tests that cache is invalidated if a dependency file's mtime changes."""
    # Arrange
    file_list = [temp_config.root / "file1.py"]
    cache.save_cache(temp_config, None, file_list)
    time.sleep(0.01)  # Ensure mtime will be different

    # Act: Modify a dependency file (the main config file)
    (temp_config.root / temp_config.default_config_filename).touch()

    # Assert: Loading the cache now returns None because it's invalid
    loaded_files = cache.load_cache(temp_config, None)
    assert loaded_files is None


def test_load_cache_corrupted_file(temp_config: Config):
    """Tests that a corrupted cache file results in a cache miss (returns None)."""
    # Arrange
    cache_filepath = cache._get_cache_filepath(temp_config)
    cache_filepath.parent.mkdir(exist_ok=True, parents=True)
    with open(cache_filepath, "wb") as f:
        f.write(b"this is not valid pickle data")

    # Act
    loaded_files = cache.load_cache(temp_config, None)

    # Assert
    assert loaded_files is None


def test_save_cache_when_disabled(temp_config: Config):
    """Tests that save_cache does not write a file when disabled."""
    # Arrange
    temp_config.use_cache = False
    file_list = [temp_config.root / "file1.py"]

    # Act
    cache.save_cache(temp_config, None, file_list)

    # Assert
    assert not cache._get_cache_filepath(temp_config).exists()


def test_load_cache_when_not_found(temp_config: Config):
    """Tests that load_cache returns None when the cache file doesn't exist."""
    # Arrange
    assert not cache._get_cache_filepath(temp_config).exists()

    # Act
    result = cache.load_cache(temp_config, None)

    # Assert
    assert result is None


def test_load_cache_when_disabled(temp_config: Config):
    """Tests that load_cache returns None when caching is disabled in config."""
    # Arrange
    file_list = [temp_config.root / "file1.py"]
    cache.save_cache(temp_config, None, file_list)
    assert cache._get_cache_filepath(temp_config).exists()

    temp_config.use_cache = False

    # Act
    result = cache.load_cache(temp_config, None)

    # Assert
    assert result is None
