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
    from ctxctx.config import DEFAULT_CONFIG

    return DEFAULT_CONFIG.copy()


# Optional: A fixture for the mutable CONFIG, allowing tests to modify it
# while ensuring it's reset for each test run.
@pytest.fixture(autouse=True)
def reset_config():
    from ctxctx.config import CONFIG, DEFAULT_CONFIG

    original_config = DEFAULT_CONFIG.copy()  # Store a true copy of default
    # Clear current CONFIG and update with default values
    CONFIG.clear()
    CONFIG.update(original_config)
    yield
    # No cleanup needed after yield because of
    # `autouse=True` and `CONFIG.clear()` / `update()` pattern.
    # The next test will get a fresh copy from DEFAULT_CONFIG.
