# ctxctx/cache.py
import logging
import pickle
from pathlib import Path
from typing import Dict, List, Optional

from .config import Config

logger = logging.getLogger(__name__)

CACHE_VERSION = "1.0"
CACHE_DIR_NAME = ".ctxctx_cache"
CACHE_FILENAME = "file_list.pkl"


def _get_cache_filepath(config: Config) -> Path:
    """Returns the full path to the cache file."""
    return config.root / CACHE_DIR_NAME / CACHE_FILENAME


def _get_dependency_mtimes(config: Config, profile_name: Optional[str]) -> Dict[Path, float]:
    """
    Gets the modification times of all files that can invalidate the cache.
    This includes config files and all active ignore files.
    """
    mtimes: Dict[Path, float] = {}
    files_to_check: List[Path] = []

    # 1. Base config file
    files_to_check.append(config.root / config.default_config_filename)

    # 2. Profile config file (if a profile is used)
    if profile_name:
        files_to_check.append(config.root / config.profile_config_file)

    # 3. All ignore files used by IgnoreManager
    if config.use_gitignore:
        files_to_check.append(config.root / config.gitignore_path)
    files_to_check.append(config.root / config.script_default_ignore_file)
    for fname in config.additional_ignore_filenames:
        files_to_check.append(config.root / fname)

    for fpath in files_to_check:
        if fpath.is_file():
            try:
                mtimes[fpath] = fpath.stat().st_mtime
            except OSError as e:
                logger.warning(f"Could not stat dependency file '{fpath}': {e}")
                # If we can't stat a file, we can't trust the cache
                return {}
    return mtimes


def load_cache(config: Config, profile_name: Optional[str]) -> Optional[List[Path]]:
    """
    Loads the file list from the cache if it's valid.
    Returns the list of Path objects or None if the cache is invalid or disabled.
    """
    if not config.use_cache:
        logger.debug("Cache is disabled in config. Skipping.")
        return None

    cache_filepath = _get_cache_filepath(config)
    if not cache_filepath.is_file():
        logger.debug("Cache file not found.")
        return None

    logger.debug(f"Attempting to load from cache: {cache_filepath}")
    try:
        with open(cache_filepath, "rb") as f:
            data = pickle.load(f)

        # Basic validation
        if (
            not isinstance(data, dict)
            or data.get("version") != CACHE_VERSION
            or "metadata" not in data
            or "files" not in data
        ):
            logger.warning("Cache data is corrupt or outdated. Invalidating.")
            return None

        # Invalidation check: Compare dependency modification times
        current_mtimes = _get_dependency_mtimes(config, profile_name)
        cached_mtimes = data["metadata"].get("mtimes", {})

        if current_mtimes != cached_mtimes:
            logger.info("Configuration or ignore files have changed. Invalidating cache.")
            return None

        logger.info(f"✅ Cache is valid. Loaded {len(data['files'])} file paths.")
        return data["files"]

    except (pickle.UnpicklingError, EOFError, KeyError, Exception) as e:
        logger.warning(f"Failed to load cache file, will perform full walk: {e}")
        return None


def save_cache(config: Config, profile_name: Optional[str], files: List[Path]) -> None:
    """Saves the given list of files to the cache."""
    if not config.use_cache:
        return

    cache_filepath = _get_cache_filepath(config)
    try:
        cache_dir = cache_filepath.parent
        cache_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "version": CACHE_VERSION,
            "metadata": {"mtimes": _get_dependency_mtimes(config, profile_name)},
            "files": files,
        }

        with open(cache_filepath, "wb") as f:
            pickle.dump(data, f)
        logger.debug(f"Saved {len(files)} file paths to cache at '{cache_filepath}'")

    except (IOError, pickle.PicklingError, Exception) as e:
        logger.error(f"Could not write to cache file '{cache_filepath}': {e}")
