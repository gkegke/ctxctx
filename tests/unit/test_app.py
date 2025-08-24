# [FILE: /tests/unit/test_app.py] - Full File Change
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pytest

from ctxctx.app import CtxCtxApp
from ctxctx.config import Config, get_default_config


def setup_test_fs(fs, root: Path):
    """Helper to create a standard file structure for app tests, excluding ctxctx config files."""
    fs.create_dir(root / "src")
    fs.create_file(root / "src/main.py", contents="def main(): pass")
    fs.create_file(root / "src/utils.py", contents="def helper(): pass")
    fs.create_dir(root / "node_modules")
    fs.create_file(root / "node_modules/lib.js")
    fs.create_file(root / ".gitignore", contents="node_modules/\n")
    # REMOVED: fs.create_file(root / ".ctxctx.yaml", contents="""...""")
    # The .ctxctx.yaml file will now be created specifically by individual tests if needed.


@pytest.fixture
def temp_config(fs, monkeypatch) -> Config:
    """
    Provides a Config object and sets up a temporary fake directory as the
    current working directory. This ensures the app initializes correctly
    within the isolated test environment.
    """
    temp_dir = Path("/fake_project")
    fs.create_dir(temp_dir)
    # Critical fix: Change the current working directory so CtxCtxApp's default
    # config uses this path as its root.
    monkeypatch.chdir(temp_dir)

    # This config is now mainly for setting up files in tests, as the app
    # will create its own based on the new CWD.
    config = get_default_config()
    config.root = temp_dir
    config.default_config_filename = ".ctxctx.yaml"
    return config


@pytest.fixture
def mock_args() -> Namespace:
    """Provides a default Namespace object for args."""
    return Namespace(
        queries=[],
        dry_run=False,
        profile=None,
        list_files=False,
        debug=False,
        log_file=None,
    )


def test_app_run_list_files(fs, temp_config, mock_args, capsys):
    """
    Tests that `_run_list_files` prints sorted, non-ignored files to stdout.
    """
    # Arrange
    root = temp_config.root
    setup_test_fs(fs, root)
    # Explicitly create the default config file for this test
    fs.create_file(
        root / temp_config.default_config_filename,
        contents="""
ROOT: .
OUTPUT_FORMATS: ["md", "json"]
""",
    )
    mock_args.list_files = True

    # Act
    # With monkeypatch.chdir in temp_config, the app will run in /fake_project
    app = CtxCtxApp(mock_args)
    app.run()

    # Assert
    captured = capsys.readouterr()
    stdout = captured.out

    assert "src/main.py" in stdout
    assert "src/utils.py" in stdout
    # .gitignore is ignored by default config, so it should NOT be listed.
    assert ".gitignore" not in stdout
    assert "node_modules/lib.js" not in stdout  # Ignored by .gitignore
    assert temp_config.default_config_filename not in stdout  # Now explicitly ignored


@patch("ctxctx.app.FileResolver")
def test_app_run_with_profile_integration(MockFileResolver, fs, temp_config, mock_args, caplog):
    """
    Tests the end-to-end flow of using a profile.
    """
    # Arrange
    root = temp_config.root
    setup_test_fs(fs, root)
    # Explicitly create the main config file with profile content for this test
    fs.create_file(
        root / temp_config.default_config_filename,
        contents="""
profiles:
  test_profile:
    description: "A test profile."
    include: ["*.py"]
    exclude: ["utils.py"]
    queries: ["README.md"]
""",
    )
    mock_args.profile = [["test_profile"]]

    mock_resolver_instance = MockFileResolver.return_value
    mock_resolver_instance.resolve.return_value = (
        [{"path": root / "src/main.py"}],
        {root / "src/main.py"},
    )

    # Act
    app = CtxCtxApp(mock_args)
    app.run()

    # Assert
    assert "Active Profile(s): test_profile" in caplog.text
    # Verify the profile loaded correctly by checking what was passed to the resolver
    mock_resolver_instance.resolve.assert_called_once()
    call_kwargs = mock_resolver_instance.resolve.call_args.kwargs
    assert call_kwargs["include_patterns"] == ["*.py"]
    assert call_kwargs["exclude_patterns"] == ["utils.py"]
    assert "README.md" in call_kwargs["queries"]


def test_app_dry_run_output(fs, temp_config, mock_args, capsys):
    """
    Tests that --dry-run prints to console and writes no files.
    """
    # Arrange
    root = temp_config.root
    # Ensure .ctxctx.yaml exists even for a dry run, so it's ignored properly
    fs.create_file(
        root / temp_config.default_config_filename,
        contents="""
ROOT: .
OUTPUT_FORMATS: ["md", "json"]
""",
    )
    fs.create_file(root / "main.py", contents="file content")
    mock_args.dry_run = True
    mock_args.queries = ["main.py"]

    # Act
    app = CtxCtxApp(mock_args)
    app.run()

    # Assert
    captured = capsys.readouterr()
    # In dry-run mode, logs go to stdout by default if not listing files
    output = captured.out

    assert "--- Dry Run Output Preview (Markdown) ---" in output
    assert "--- Dry Run Output Preview (JSON) ---" in output
    # The file path in the output should be relative to the project root
    assert "**[FILE: /main.py]**" in output
    assert "🎯 Dry run complete. No files were written." in output

    output_md = root / f"{temp_config.output_file_base_name}.md"
    assert not output_md.exists()
