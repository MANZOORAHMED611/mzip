"""Pytest fixtures for ZIP file testing."""

import zipfile
from pathlib import Path

import pytest


@pytest.fixture
def sample_archive(tmp_path: Path) -> Path:
    """Create a valid ZIP with a few text files."""
    archive_path = tmp_path / "sample.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("file1.txt", "Hello, World!")
        zf.writestr("file2.txt", "This is a test file.")
        zf.writestr("file3.txt", "Another text file with some content.")
    return archive_path


@pytest.fixture
def corrupted_archive(tmp_path: Path) -> Path:
    """Create a corrupted ZIP file."""
    archive_path = tmp_path / "corrupted.zip"
    # First create a valid ZIP
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("file.txt", "Some content that will be corrupted.")
    # Corrupt the file by overwriting part of it with garbage
    with archive_path.open("r+b") as f:
        f.seek(10)
        f.write(b"\x00\x00\x00\x00\x00\x00\x00\x00")
    return archive_path


@pytest.fixture
def empty_archive(tmp_path: Path) -> Path:
    """Create an empty ZIP file."""
    archive_path = tmp_path / "empty.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED):
        pass  # Create empty archive
    return archive_path


@pytest.fixture
def nested_archive(tmp_path: Path) -> Path:
    """Create a ZIP with nested directories."""
    archive_path = tmp_path / "nested.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("root.txt", "Root level file")
        zf.writestr("level1/file1.txt", "Level 1 file")
        zf.writestr("level1/level2/file2.txt", "Level 2 file")
        zf.writestr("level1/level2/level3/file3.txt", "Level 3 file")
        zf.writestr("another_dir/data.txt", "Another directory file")
        zf.writestr("another_dir/subdir/nested.txt", "Deeply nested file")
    return archive_path


@pytest.fixture
def large_archive(tmp_path: Path) -> Path:
    """Create a ZIP with larger content."""
    archive_path = tmp_path / "large.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Create files with substantial content
        for i in range(10):
            # Each file contains ~10KB of content
            content = f"File {i} content line\n" * 500
            zf.writestr(f"large_file_{i}.txt", content)
        # Add one larger file (~100KB)
        large_content = "X" * 1024 * 100
        zf.writestr("extra_large.txt", large_content)
    return archive_path
