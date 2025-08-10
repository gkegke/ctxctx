# tests/conftest.py
import pytest


# This fixture provides a fake filesystem for tests that need to interact with the file system.
# It automatically cleans up after each test.
@pytest.fixture
def fs(fs):
    return fs


# Optional: A fixture for the default config, useful if tests modify CONFIG directly
# but you want a fresh state for each test.
@pytest.fixture
def default_config_fixture():
    # Import CONFIG here to ensure we get the initial state
    from ctxctx.config import get_default_config

    return get_default_config()
