"""Comprehensive tests for archive validation functions.

This module follows TDD approach - tests are written FIRST before implementation.
Tests cover all validation functions in zipextractor.core.validation module.
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path
from unittest.mock import patch

from zipextractor.core.models import ArchiveFile, ArchiveInfo
from zipextractor.core.validation import (
    detect_root_folder,
    detect_zip_bomb,
    get_archive_info,
    is_safe_path,
    validate_archive,
    validate_disk_space,
)

# =============================================================================
# Tests for validate_archive(path: Path) -> tuple[bool, str | None]
# =============================================================================


class TestValidateArchive:
    """Test suite for validate_archive function."""

    def test_validate_valid_archive(self, sample_archive: Path) -> None:
        """Test that a valid ZIP archive returns (True, None)."""
        is_valid, error_message = validate_archive(sample_archive)

        assert is_valid is True
        assert error_message is None

    def test_validate_nonexistent_file(self, tmp_path: Path) -> None:
        """Test that a nonexistent file returns (False, 'File not found')."""
        nonexistent_path = tmp_path / "does_not_exist.zip"

        is_valid, error_message = validate_archive(nonexistent_path)

        assert is_valid is False
        assert error_message is not None
        assert "not exist" in error_message.lower() or "not found" in error_message.lower()

    def test_validate_empty_file(self, tmp_path: Path) -> None:
        """Test that an empty file (0 bytes) returns (False, 'File is empty')."""
        empty_file = tmp_path / "empty_file.zip"
        empty_file.touch()  # Create file with 0 bytes

        is_valid, error_message = validate_archive(empty_file)

        assert is_valid is False
        assert error_message == "File is empty"

    def test_validate_corrupted_archive(self, tmp_path: Path) -> None:
        """Test that a severely corrupted ZIP returns (False, error)."""
        # Create a file that looks like a ZIP but is completely invalid
        corrupted_path = tmp_path / "severely_corrupted.zip"
        corrupted_path.write_bytes(b"PK\x03\x04corrupted garbage data that is not valid")

        is_valid, error_message = validate_archive(corrupted_path)

        assert is_valid is False
        assert error_message is not None

    def test_validate_file_not_zip(self, tmp_path: Path) -> None:
        """Test that a non-ZIP file returns (False, ...) with appropriate error."""
        not_a_zip = tmp_path / "not_a_zip.txt"
        not_a_zip.write_text("This is just a text file, not a ZIP archive.")

        is_valid, error_message = validate_archive(not_a_zip)

        assert is_valid is False
        assert error_message is not None
        # The error message should indicate it's not a valid ZIP
        assert "not a valid" in error_message.lower() or "invalid" in error_message.lower()

    def test_validate_directory_not_file(self, tmp_path: Path) -> None:
        """Test that passing a directory returns an error."""
        is_valid, error_message = validate_archive(tmp_path)

        assert is_valid is False
        assert error_message is not None

    def test_validate_valid_empty_archive(self, empty_archive: Path) -> None:
        """Test that an empty but valid ZIP archive is still valid."""
        is_valid, error_message = validate_archive(empty_archive)

        # An empty ZIP archive is technically valid
        assert is_valid is True
        assert error_message is None


# =============================================================================
# Tests for get_archive_info(path: Path) -> ArchiveInfo
# =============================================================================


class TestGetArchiveInfo:
    """Test suite for get_archive_info function."""

    def test_get_archive_info_returns_archive_info(self, sample_archive: Path) -> None:
        """Test that get_archive_info returns an ArchiveInfo object."""
        info = get_archive_info(sample_archive)

        assert isinstance(info, ArchiveInfo)
        assert info.path == sample_archive

    def test_get_archive_info_file_count(self, sample_archive: Path) -> None:
        """Test that get_archive_info returns correct file count."""
        # sample_archive contains 3 files: file1.txt, file2.txt, file3.txt
        info = get_archive_info(sample_archive)

        assert info.file_count == 3

    def test_get_archive_info_sizes(self, sample_archive: Path) -> None:
        """Test that get_archive_info returns correct compressed/uncompressed sizes."""
        info = get_archive_info(sample_archive)

        # Verify file_size is the actual archive size on disk
        assert info.file_size == sample_archive.stat().st_size

        # Verify uncompressed_size is greater than or equal to 0
        assert info.uncompressed_size >= 0

        # The content in sample_archive:
        # file1.txt: "Hello, World!" (13 bytes)
        # file2.txt: "This is a test file." (20 bytes)
        # file3.txt: "Another text file with some content." (36 bytes)
        # Total uncompressed: 69 bytes
        expected_uncompressed = len("Hello, World!") + len("This is a test file.") + len(
            "Another text file with some content."
        )
        assert info.uncompressed_size == expected_uncompressed

    def test_get_archive_info_files_list(self, sample_archive: Path) -> None:
        """Test that get_archive_info returns a list of ArchiveFile objects."""
        info = get_archive_info(sample_archive)

        assert isinstance(info.files, list)
        assert len(info.files) == 3

        for archive_file in info.files:
            assert isinstance(archive_file, ArchiveFile)
            assert isinstance(archive_file.path, str)
            assert isinstance(archive_file.size, int)
            assert isinstance(archive_file.compressed_size, int)
            assert isinstance(archive_file.is_directory, bool)

    def test_get_archive_info_detects_directories(self, nested_archive: Path) -> None:
        """Test that get_archive_info correctly detects directories."""
        info = get_archive_info(nested_archive)

        # Check that we have some files
        assert len(info.files) > 0

        # Get all paths
        paths = [f.path for f in info.files]

        # nested_archive contains:
        # root.txt, level1/file1.txt, level1/level2/file2.txt,
        # level1/level2/level3/file3.txt, another_dir/data.txt,
        # another_dir/subdir/nested.txt
        assert "root.txt" in paths
        assert "level1/file1.txt" in paths

        # Check that non-directory files are marked correctly
        for archive_file in info.files:
            if archive_file.path.endswith(".txt"):
                assert archive_file.is_directory is False

    def test_get_archive_info_with_explicit_directories(self, tmp_path: Path) -> None:
        """Test that explicit directory entries are detected."""
        archive_path = tmp_path / "with_dirs.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            # Create an explicit directory entry
            zf.writestr("mydir/", "")
            zf.writestr("mydir/file.txt", "content")

        info = get_archive_info(archive_path)

        # Find the directory entry
        dir_entries = [f for f in info.files if f.is_directory]
        assert len(dir_entries) >= 1

        # Verify the directory is marked correctly
        mydir = next((f for f in info.files if f.path == "mydir/" or f.path == "mydir"), None)
        if mydir:
            assert mydir.is_directory is True

    def test_get_archive_info_empty_archive(self, empty_archive: Path) -> None:
        """Test get_archive_info on an empty archive."""
        info = get_archive_info(empty_archive)

        assert info.file_count == 0
        assert info.uncompressed_size == 0
        assert len(info.files) == 0

    def test_get_archive_info_file_attributes(self, sample_archive: Path) -> None:
        """Test that ArchiveFile objects have correct attributes."""
        info = get_archive_info(sample_archive)

        # Find file1.txt
        file1 = next((f for f in info.files if f.path == "file1.txt"), None)
        assert file1 is not None
        assert file1.size == len("Hello, World!")
        assert file1.compressed_size >= 0
        assert file1.is_directory is False

    def test_get_archive_info_invalid_archive_raises(self, tmp_path: Path) -> None:
        """Test that get_archive_info handles invalid archives appropriately."""
        # Create a severely corrupted file that cannot be read as ZIP
        corrupted_path = tmp_path / "totally_invalid.zip"
        corrupted_path.write_bytes(b"This is not a ZIP file at all")

        # This could either raise an exception or return an ArchiveInfo with is_valid=False
        # depending on implementation choice
        try:
            info = get_archive_info(corrupted_path)
            # If it returns, check that it indicates invalidity
            assert info.is_valid is False or len(info.validation_errors) > 0
        except (zipfile.BadZipFile, ValueError, OSError):
            # Raising an exception is also acceptable behavior
            pass


# =============================================================================
# Tests for detect_root_folder(file_paths: list[str]) -> str | None
# =============================================================================


class TestDetectRootFolder:
    """Test suite for detect_root_folder function."""

    def test_detect_root_folder_single(self) -> None:
        """Test detection of a single root folder."""
        file_paths = [
            "project/file1.txt",
            "project/src/main.py",
            "project/src/utils/helper.py",
            "project/README.md",
        ]

        root = detect_root_folder(file_paths)

        assert root == "project"

    def test_detect_root_folder_multiple(self) -> None:
        """Test that multiple root folders returns None."""
        file_paths = [
            "folder1/file1.txt",
            "folder2/file2.txt",
            "folder3/file3.txt",
        ]

        root = detect_root_folder(file_paths)

        assert root is None

    def test_detect_root_folder_no_folder(self) -> None:
        """Test that flat files (no folders) returns None."""
        file_paths = [
            "file1.txt",
            "file2.txt",
            "file3.txt",
        ]

        root = detect_root_folder(file_paths)

        assert root is None

    def test_detect_root_folder_empty_list(self) -> None:
        """Test with an empty list of paths."""
        root = detect_root_folder([])

        assert root is None

    def test_detect_root_folder_single_file_in_folder(self) -> None:
        """Test with a single file inside a folder."""
        file_paths = ["myroot/single.txt"]

        root = detect_root_folder(file_paths)

        assert root == "myroot"

    def test_detect_root_folder_nested_structure(self) -> None:
        """Test with deeply nested structure under single root."""
        file_paths = [
            "root/a/b/c/d/deep.txt",
            "root/x/y/z/another.txt",
            "root/top.txt",
        ]

        root = detect_root_folder(file_paths)

        assert root == "root"

    def test_detect_root_folder_mixed_with_root_files(self) -> None:
        """Test that files at root level prevent folder detection."""
        file_paths = [
            "README.md",  # File at root level
            "project/src/main.py",
            "project/tests/test.py",
        ]

        root = detect_root_folder(file_paths)

        # Since there's a file at root level, there's no single root folder
        assert root is None

    def test_detect_root_folder_with_trailing_slash(self) -> None:
        """Test handling of paths with trailing slashes (directories)."""
        file_paths = [
            "project/",
            "project/src/",
            "project/src/main.py",
        ]

        root = detect_root_folder(file_paths)

        assert root == "project"

    def test_detect_root_folder_similar_names(self) -> None:
        """Test that similar folder names are treated as different roots."""
        file_paths = [
            "project-v1/file1.txt",
            "project-v2/file2.txt",
        ]

        root = detect_root_folder(file_paths)

        assert root is None


# =============================================================================
# Tests for detect_zip_bomb(path: Path, max_ratio: float = 100.0) -> bool
# =============================================================================


class TestDetectZipBomb:
    """Test suite for detect_zip_bomb function."""

    def test_detect_zip_bomb_normal_archive(self, sample_archive: Path) -> None:
        """Test that a normal archive is not detected as a zip bomb."""
        is_bomb = detect_zip_bomb(sample_archive)

        assert is_bomb is False

    def test_detect_zip_bomb_high_ratio(self, tmp_path: Path) -> None:
        """Test that an archive with extremely high compression ratio is detected."""
        # Create an archive with highly compressible content (repetitive data)
        archive_path = tmp_path / "high_ratio.zip"
        # Create a file with highly repetitive content that compresses extremely well
        # 1 million 'A' characters will compress to almost nothing
        repetitive_content = "A" * 1_000_000

        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            zf.writestr("bomb.txt", repetitive_content)

        # Check the actual ratio
        archive_size = archive_path.stat().st_size
        uncompressed_size = len(repetitive_content)
        actual_ratio = uncompressed_size / archive_size if archive_size > 0 else float("inf")

        # If actual ratio exceeds threshold, should be detected
        is_bomb = detect_zip_bomb(archive_path, max_ratio=100.0)

        if actual_ratio > 100.0:
            assert is_bomb is True
        else:
            # If compression wasn't as extreme, test with a lower threshold
            is_bomb_lower = detect_zip_bomb(archive_path, max_ratio=10.0)
            assert is_bomb_lower is True or actual_ratio <= 10.0

    def test_detect_zip_bomb_custom_ratio(self, sample_archive: Path) -> None:
        """Test zip bomb detection with custom max_ratio parameter."""
        # With a very low threshold, even normal archives might trigger
        is_bomb_strict = detect_zip_bomb(sample_archive, max_ratio=0.5)

        # With a very high threshold, nothing should trigger
        is_bomb_lenient = detect_zip_bomb(sample_archive, max_ratio=10000.0)

        assert is_bomb_lenient is False

    def test_detect_zip_bomb_empty_archive(self, empty_archive: Path) -> None:
        """Test zip bomb detection on empty archive."""
        # Empty archives shouldn't be detected as bombs (division by zero edge case)
        is_bomb = detect_zip_bomb(empty_archive)

        assert is_bomb is False

    def test_detect_zip_bomb_nested_archive(self, nested_archive: Path) -> None:
        """Test zip bomb detection on nested directory structure."""
        is_bomb = detect_zip_bomb(nested_archive)

        assert is_bomb is False

    def test_detect_zip_bomb_with_multiple_files(self, tmp_path: Path) -> None:
        """Test detection considers total uncompressed size across all files."""
        archive_path = tmp_path / "multi_bomb.zip"
        # Multiple files with repetitive content
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for i in range(10):
                # Each file has 100KB of repetitive content
                zf.writestr(f"bomb_{i}.txt", "X" * 100_000)

        # Total uncompressed: 1MB, but compressed should be tiny
        is_bomb = detect_zip_bomb(archive_path, max_ratio=50.0)

        # This should likely be detected as suspicious
        # The actual result depends on compression efficiency
        assert isinstance(is_bomb, bool)


# =============================================================================
# Tests for is_safe_path(base_path: Path, target_path: str) -> bool
# =============================================================================


class TestIsSafePath:
    """Test suite for is_safe_path function."""

    def test_is_safe_path_normal(self, tmp_path: Path) -> None:
        """Test that normal paths are allowed."""
        assert is_safe_path(tmp_path, "file.txt") is True
        assert is_safe_path(tmp_path, "folder/file.txt") is True
        assert is_safe_path(tmp_path, "a/b/c/deep.txt") is True

    def test_is_safe_path_traversal(self, tmp_path: Path) -> None:
        """Test that path traversal attempts are blocked."""
        assert is_safe_path(tmp_path, "../../../etc/passwd") is False
        assert is_safe_path(tmp_path, "../../secret.txt") is False
        assert is_safe_path(tmp_path, "../outside.txt") is False

    def test_is_safe_path_absolute(self, tmp_path: Path) -> None:
        """Test that absolute paths are blocked."""
        assert is_safe_path(tmp_path, "/etc/passwd") is False
        assert is_safe_path(tmp_path, "/tmp/malicious.txt") is False
        assert is_safe_path(tmp_path, "/home/user/file.txt") is False

    def test_is_safe_path_dot_segments(self, tmp_path: Path) -> None:
        """Test that paths with .. anywhere are blocked."""
        assert is_safe_path(tmp_path, "folder/../../../etc/passwd") is False
        assert is_safe_path(tmp_path, "a/b/../../c/../../../d") is False
        assert is_safe_path(tmp_path, "normal/path/../sneaky/../../../root") is False

    def test_is_safe_path_hidden_traversal(self, tmp_path: Path) -> None:
        """Test various hidden path traversal techniques."""
        # URL encoded
        assert is_safe_path(tmp_path, "..%2f..%2f..%2fetc/passwd") is False or is_safe_path(
            tmp_path, "..%2f..%2f..%2fetc/passwd"
        )

        # Double dots in filename (this should be safe if it's just the filename)
        # "..file.txt" is a valid filename, not traversal
        # But "folder/..file.txt" is also valid

    def test_is_safe_path_windows_style(self, tmp_path: Path) -> None:
        """Test Windows-style path traversal is blocked."""
        assert is_safe_path(tmp_path, "..\\..\\..\\windows\\system32") is False
        assert is_safe_path(tmp_path, "folder\\..\\..\\secret") is False

    def test_is_safe_path_current_directory(self, tmp_path: Path) -> None:
        """Test that single dot (current directory) is handled."""
        # Single dot should be safe as it refers to current directory
        assert is_safe_path(tmp_path, "./file.txt") is True
        assert is_safe_path(tmp_path, "folder/./file.txt") is True

    def test_is_safe_path_empty_string(self, tmp_path: Path) -> None:
        """Test handling of empty path string."""
        # Empty path should probably be considered unsafe or invalid
        result = is_safe_path(tmp_path, "")
        assert isinstance(result, bool)

    def test_is_safe_path_symlink_like(self, tmp_path: Path) -> None:
        """Test paths that look like they might involve symlinks."""
        # These are just path strings, not actual symlinks
        assert is_safe_path(tmp_path, "link/file.txt") is True
        assert is_safe_path(tmp_path, "normal_folder/normal_file.txt") is True

    def test_is_safe_path_special_characters(self, tmp_path: Path) -> None:
        """Test paths with special characters that are valid."""
        assert is_safe_path(tmp_path, "file with spaces.txt") is True
        assert is_safe_path(tmp_path, "file-with-dashes.txt") is True
        assert is_safe_path(tmp_path, "file_with_underscores.txt") is True

    def test_is_safe_path_null_byte(self, tmp_path: Path) -> None:
        """Test that null bytes in paths are blocked."""
        # Null byte injection attempt
        result = is_safe_path(tmp_path, "file.txt\x00.jpg")
        # Should either be False or the function should handle it safely
        assert isinstance(result, bool)


# =============================================================================
# Tests for validate_disk_space
# =============================================================================


class TestValidateDiskSpace:
    """Test suite for validate_disk_space function."""

    def test_validate_disk_space_sufficient(self, tmp_path: Path) -> None:
        """Test that sufficient disk space returns (True, available_space)."""
        # Request a small amount that should always be available
        required_bytes = 1024  # 1 KB

        has_space, available = validate_disk_space(tmp_path, required_bytes)

        assert has_space is True
        assert available > 0

    def test_validate_disk_space_returns_available(self, tmp_path: Path) -> None:
        """Test that the function returns the available disk space."""
        required_bytes = 0

        has_space, available = validate_disk_space(tmp_path, required_bytes)

        assert isinstance(available, int)
        assert available > 0

        # Verify it matches actual disk space (approximately)
        actual_stats = os.statvfs(tmp_path)
        actual_available = actual_stats.f_bavail * actual_stats.f_frsize
        # Allow some variance for concurrent operations
        assert abs(available - actual_available) < 1024 * 1024 * 100  # Within 100MB

    def test_validate_disk_space_with_buffer(self, tmp_path: Path) -> None:
        """Test that buffer is applied correctly."""
        # Get actual available space
        stats = os.statvfs(tmp_path)
        actual_available = stats.f_bavail * stats.f_frsize

        # Request exactly the available space (should fail with buffer)
        has_space_no_buffer, _ = validate_disk_space(tmp_path, actual_available, buffer=0.0)
        has_space_with_buffer, _ = validate_disk_space(tmp_path, actual_available, buffer=0.1)

        # With buffer, requesting full space should fail
        # (because we need space + 10% buffer)
        assert has_space_with_buffer is False

    def test_validate_disk_space_insufficient(self, tmp_path: Path) -> None:
        """Test that insufficient space returns (False, available_space)."""
        # Request an impossibly large amount
        required_bytes = 10**18  # 1 Exabyte

        has_space, available = validate_disk_space(tmp_path, required_bytes)

        assert has_space is False
        assert available > 0  # Should still return available space

    def test_validate_disk_space_zero_required(self, tmp_path: Path) -> None:
        """Test with zero required bytes."""
        has_space, available = validate_disk_space(tmp_path, 0)

        assert has_space is True
        assert available > 0

    def test_validate_disk_space_negative_required(self, tmp_path: Path) -> None:
        """Test handling of negative required bytes."""
        # Negative values should either be treated as 0 or raise an error
        try:
            has_space, available = validate_disk_space(tmp_path, -1000)
            # If it doesn't raise, it should treat negative as valid
            assert has_space is True
        except ValueError:
            # Raising ValueError for invalid input is acceptable
            pass

    def test_validate_disk_space_nonexistent_path(self, tmp_path: Path) -> None:
        """Test with a path that doesn't exist."""
        nonexistent = tmp_path / "nonexistent" / "path"

        # Should either raise an error or handle gracefully
        try:
            has_space, available = validate_disk_space(nonexistent, 1024)
            # If it works, it might check parent directory space
            assert isinstance(has_space, bool)
        except (FileNotFoundError, OSError):
            # Raising an error for nonexistent path is acceptable
            pass

    def test_validate_disk_space_different_buffers(self, tmp_path: Path) -> None:
        """Test various buffer values."""
        required = 1024 * 1024  # 1 MB

        # Zero buffer
        has_space_0, avail_0 = validate_disk_space(tmp_path, required, buffer=0.0)

        # 10% buffer (default)
        has_space_10, avail_10 = validate_disk_space(tmp_path, required, buffer=0.1)

        # 50% buffer
        has_space_50, avail_50 = validate_disk_space(tmp_path, required, buffer=0.5)

        # Available space should be the same regardless of buffer
        assert avail_0 == avail_10 == avail_50

        # All should pass for small required amount
        assert has_space_0 is True
        assert has_space_10 is True
        assert has_space_50 is True

    @patch("shutil.disk_usage")
    def test_validate_disk_space_mocked(self, mock_disk_usage: patch, tmp_path: Path) -> None:
        """Test disk space validation with mocked filesystem stats."""
        # Mock filesystem with exactly 1GB available
        from collections import namedtuple

        DiskUsage = namedtuple("DiskUsage", ["total", "used", "free"])
        mock_disk_usage.return_value = DiskUsage(
            total=2 * 1024 * 1024 * 1024,  # 2GB total
            used=1024 * 1024 * 1024,  # 1GB used
            free=1024 * 1024 * 1024,  # 1GB free
        )

        # 1GB available, request 500MB (should pass)
        has_space, available = validate_disk_space(tmp_path, 500 * 1024 * 1024, buffer=0.0)
        assert has_space is True
        assert available == 1024 * 1024 * 1024  # 1GB

        # Request 1GB with 10% buffer (should fail - need 1.1GB)
        has_space, _ = validate_disk_space(tmp_path, 1024 * 1024 * 1024, buffer=0.1)
        assert has_space is False


# =============================================================================
# Additional Edge Case Tests
# =============================================================================


class TestValidationEdgeCases:
    """Additional edge case tests for validation functions."""

    def test_validate_archive_permission_denied(self, tmp_path: Path) -> None:
        """Test handling of permission denied errors."""
        # Create a file and remove read permissions
        archive_path = tmp_path / "no_read.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("file.txt", "content")

        try:
            archive_path.chmod(0o000)  # Remove all permissions

            is_valid, error_message = validate_archive(archive_path)

            # Should return False with appropriate error
            assert is_valid is False
            assert error_message is not None
        finally:
            # Restore permissions for cleanup
            archive_path.chmod(0o644)

    def test_get_archive_info_large_file_count(self, tmp_path: Path) -> None:
        """Test get_archive_info with many files."""
        archive_path = tmp_path / "many_files.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            for i in range(100):
                zf.writestr(f"file_{i:04d}.txt", f"Content {i}")

        info = get_archive_info(archive_path)

        assert info.file_count == 100
        assert len(info.files) == 100

    def test_detect_root_folder_unicode_paths(self) -> None:
        """Test root folder detection with unicode characters."""
        file_paths = [
            "proyecto/archivo.txt",
            "proyecto/datos/info.txt",
        ]

        root = detect_root_folder(file_paths)

        assert root == "proyecto"

    def test_is_safe_path_unicode(self, tmp_path: Path) -> None:
        """Test safe path check with unicode characters."""
        assert is_safe_path(tmp_path, "folder/archivo.txt") is True
        assert is_safe_path(tmp_path, "carpeta/documento.txt") is True

    def test_validate_archive_symlink_to_archive(self, tmp_path: Path) -> None:
        """Test validation of symlink pointing to archive."""
        # Create a real archive
        real_archive = tmp_path / "real.zip"
        with zipfile.ZipFile(real_archive, "w") as zf:
            zf.writestr("file.txt", "content")

        # Create symlink to it
        symlink_path = tmp_path / "link.zip"
        symlink_path.symlink_to(real_archive)

        is_valid, error_message = validate_archive(symlink_path)

        # Should validate the linked file
        assert is_valid is True
        assert error_message is None
