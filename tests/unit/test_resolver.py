# [FILE: /tests/unit/test_resolver.py]
from pathlib import Path

import pytest

from ctxctx.config import Config, get_default_config
from ctxctx.resolver import FileResolver


@pytest.fixture
# Changed: Use fs fixture from pyfakefs directly for temporary root
def temp_config(fs) -> Config:
    """Provides a Config object with its root set to a temporary directory in fakefs."""
    config = get_default_config()
    # Use fs to create the root directory in the fake filesystem
    root = Path("/fake_project_root")
    fs.create_dir(root)
    config.root = root
    return config


@pytest.fixture
# Changed: Use fs fixture and temp_config to create files in fakefs
def file_structure(fs, temp_config):
    """Creates a standard file structure in fakefs and returns the list of all files."""
    root = temp_config.root
    # fmt: off
    paths_to_create = [
        root / "src/main.py",
        root / "src/utils.py",
        root / "src/config/settings.py",
        root / "tests/test_main.py",
        root / "tests/test_utils.py",
        root / "docs/guide.md",
        root / "README.md",
    ]
    # fmt: on
    for p in paths_to_create:
        fs.create_file(p)  # Use fs.create_file to make files in fakefs
    return paths_to_create  # Return the list of Path objects (which are now fake paths)


def test_resolver_include_only(temp_config, file_structure):
    """
    Tests that 'include' patterns correctly establish the base set of files.
    ROI: 10/10
    """
    resolver = FileResolver(temp_config)
    all_files_data, unique_paths = resolver.resolve(
        all_project_files=file_structure,
        include_patterns=["src/**/*.py"],
        exclude_patterns=[],
        queries=[],
    )
    paths = {p.name for p in unique_paths}
    assert paths == {"main.py", "utils.py", "settings.py"}
    assert len(unique_paths) == 3


def test_resolver_include_then_exclude(temp_config, file_structure):
    """
    Tests that 'exclude' correctly prunes files matched by 'include'.
    ROI: 10/10
    """
    resolver = FileResolver(temp_config)
    _, unique_paths = resolver.resolve(
        all_project_files=file_structure,
        include_patterns=["**/*.py"],
        exclude_patterns=["*/config/*", "tests/test_utils.py"],
        queries=[],
    )
    paths = {p.relative_to(temp_config.root).as_posix() for p in unique_paths}
    assert paths == {"src/main.py", "src/utils.py", "tests/test_main.py"}


def test_resolver_queries_are_additive(temp_config, file_structure):
    """
    Tests that 'queries' add files not covered by 'include' patterns.
    ROI: 9/10
    """
    resolver = FileResolver(temp_config)
    _, unique_paths = resolver.resolve(
        all_project_files=file_structure,
        include_patterns=["src/**/*.py"],
        exclude_patterns=[],
        queries=["README.md", "docs/guide.md"],  # These are not .py files
    )
    paths = {p.name for p in unique_paths}
    assert paths == {
        "main.py",
        "utils.py",
        "settings.py",
        "README.md",
        "guide.md",
    }


def test_resolver_exclude_overrides_queries(temp_config, file_structure):
    """
    Tests that 'exclude' prunes files added by both 'include' and 'queries'.
    ROI: 9/10
    """
    resolver = FileResolver(temp_config)
    _, unique_paths = resolver.resolve(
        all_project_files=file_structure,
        include_patterns=["src/**/*.py"],
        exclude_patterns=["src/utils.py"],
        queries=["src/utils.py", "README.md"],  # Explicitly query the file to be excluded
    )
    paths = {p.name for p in unique_paths}
    assert "utils.py" not in paths
    assert paths == {"main.py", "settings.py", "README.md"}


def test_resolver_line_range_merging(temp_config, file_structure):
    """
    Tests that line ranges from queries are correctly applied and merged.
    ROI: 9/10
    """
    resolver = FileResolver(temp_config)
    main_py_path = temp_config.root / "src/main.py"

    all_files_data, unique_paths = resolver.resolve(
        all_project_files=file_structure,
        include_patterns=["src/main.py"],  # Includes main.py with no line ranges
        exclude_patterns=[],
        queries=[
            "src/main.py:10,20",  # Query with one range
            "src/main.py:5,15:30,40",  # Query with two ranges, one overlapping
        ],
    )

    assert len(unique_paths) == 1
    assert main_py_path in unique_paths

    main_py_data = next(d for d in all_files_data if d["path"] == main_py_path)
    # Ranges should be combined, deduplicated, and sorted
    expected_ranges = [[5, 15], [10, 20], [30, 40]]
    assert main_py_data["line_ranges"] == expected_ranges


def test_resolver_no_matches(temp_config, file_structure):
    """Tests behavior with no matching rules or queries."""
    resolver = FileResolver(temp_config)
    all_files_data, unique_paths = resolver.resolve(
        all_project_files=file_structure,
        include_patterns=["*.nonexistent"],
        exclude_patterns=[],
        queries=[],
    )
    assert not all_files_data
    assert not unique_paths


def test_resolver_only_queries_no_includes(temp_config, file_structure):
    """
    Tests resolution when only queries are provided, and no explicit 'include' rules.
    This should default to considering all project files, then filtering by queries.
    """
    resolver = FileResolver(temp_config)
    _, unique_paths = resolver.resolve(
        all_project_files=file_structure,
        include_patterns=[],  # No include patterns
        exclude_patterns=[],
        queries=["README.md", "src/utils.py"],
    )
    paths = {p.name for p in unique_paths}
    assert paths == {"README.md", "utils.py"}
    assert len(unique_paths) == 2


def test_resolver_empty_project_files(temp_config):
    """Tests resolution with an empty list of project files."""
    resolver = FileResolver(temp_config)
    all_files_data, unique_paths = resolver.resolve(
        all_project_files=[],
        include_patterns=["**/*.py"],
        exclude_patterns=[],
        queries=["README.md"],
    )
    assert not all_files_data
    assert not unique_paths
