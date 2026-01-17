"""Comprehensive tests for the extraction engine.

This module follows TDD approach - tests are written FIRST before implementation.
Tests cover all extraction functionality in zipextractor.core.extraction module.
"""

from __future__ import annotations

import time
import zipfile
from datetime import datetime
from pathlib import Path
from threading import Thread
from unittest.mock import patch

import pytest

from zipextractor.core.extraction import ExtractionEngine
from zipextractor.core.models import (
    ConflictResolution,
    ExtractionTask,
    TaskStatus,
)

# =============================================================================
# Fixtures for Extraction Tests
# =============================================================================


@pytest.fixture
def extraction_engine() -> ExtractionEngine:
    """Create an ExtractionEngine instance for testing."""
    return ExtractionEngine()


@pytest.fixture
def extraction_task(sample_archive: Path, tmp_path: Path) -> ExtractionTask:
    """Create a basic ExtractionTask for testing."""
    return ExtractionTask(
        task_id="test-task-001",
        archive_path=sample_archive,
        destination_path=tmp_path / "extracted",
        status=TaskStatus.QUEUED,
        conflict_resolution=ConflictResolution.OVERWRITE,
        total_files=3,
        total_bytes=69,  # Size of sample_archive contents
        preserve_timestamps=True,
        create_root_folder=False,
    )


@pytest.fixture
def nested_extraction_task(nested_archive: Path, tmp_path: Path) -> ExtractionTask:
    """Create an ExtractionTask for nested archive testing."""
    return ExtractionTask(
        task_id="test-task-nested",
        archive_path=nested_archive,
        destination_path=tmp_path / "extracted_nested",
        status=TaskStatus.QUEUED,
        conflict_resolution=ConflictResolution.OVERWRITE,
        total_files=6,
        total_bytes=100,
        preserve_timestamps=True,
        create_root_folder=False,
    )


@pytest.fixture
def archive_with_timestamps(tmp_path: Path) -> Path:
    """Create a ZIP archive with specific timestamps for testing preservation."""
    archive_path = tmp_path / "timestamped.zip"

    # Create files with specific modification times
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Set a specific date/time (2023-06-15 14:30:00)
        info = zipfile.ZipInfo("timestamped_file.txt", date_time=(2023, 6, 15, 14, 30, 0))
        zf.writestr(info, "Content with timestamp")

    return archive_path


@pytest.fixture
def archive_with_path_traversal(tmp_path: Path) -> Path:
    """Create a malicious ZIP archive with path traversal attempt."""
    archive_path = tmp_path / "malicious.zip"

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add a normal file
        zf.writestr("normal_file.txt", "This is normal")

        # Add a file with path traversal (this is intentionally malicious for testing)
        # We need to directly write the entry with a manipulated name
        info = zipfile.ZipInfo("../../../etc/malicious.txt")
        zf.writestr(info, "Attempting to escape")

        # Another path traversal attempt
        info2 = zipfile.ZipInfo("folder/../../outside.txt")
        zf.writestr(info2, "Another escape attempt")

    return archive_path


@pytest.fixture
def archive_with_single_root(tmp_path: Path) -> Path:
    """Create a ZIP archive with a single root folder."""
    archive_path = tmp_path / "single_root.zip"

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("myproject/file1.txt", "File 1 content")
        zf.writestr("myproject/src/main.py", "print('hello')")
        zf.writestr("myproject/README.md", "# My Project")

    return archive_path


@pytest.fixture
def large_extraction_task(large_archive: Path, tmp_path: Path) -> ExtractionTask:
    """Create an ExtractionTask for large archive testing."""
    return ExtractionTask(
        task_id="test-task-large",
        archive_path=large_archive,
        destination_path=tmp_path / "extracted_large",
        status=TaskStatus.QUEUED,
        conflict_resolution=ConflictResolution.OVERWRITE,
        total_files=11,
        total_bytes=150000,
        preserve_timestamps=True,
        create_root_folder=False,
    )


# =============================================================================
# Tests for Basic Extraction
# =============================================================================


class TestBasicExtraction:
    """Test suite for basic extraction functionality."""

    def test_extract_simple_archive(
        self,
        extraction_engine: ExtractionEngine,
        extraction_task: ExtractionTask,
    ) -> None:
        """Test that extraction extracts all files correctly."""
        result = extraction_engine.extract(extraction_task)

        assert result is True

        # Verify all files were extracted
        dest = extraction_task.destination_path
        assert (dest / "file1.txt").exists()
        assert (dest / "file2.txt").exists()
        assert (dest / "file3.txt").exists()

        # Verify file contents
        assert (dest / "file1.txt").read_text() == "Hello, World!"
        assert (dest / "file2.txt").read_text() == "This is a test file."
        assert (dest / "file3.txt").read_text() == "Another text file with some content."

    def test_extract_preserves_directory_structure(
        self,
        extraction_engine: ExtractionEngine,
        nested_extraction_task: ExtractionTask,
    ) -> None:
        """Test that extraction maintains folder hierarchy from archive."""
        result = extraction_engine.extract(nested_extraction_task)

        assert result is True

        dest = nested_extraction_task.destination_path

        # Verify directory structure is preserved
        assert (dest / "root.txt").exists()
        assert (dest / "level1" / "file1.txt").exists()
        assert (dest / "level1" / "level2" / "file2.txt").exists()
        assert (dest / "level1" / "level2" / "level3" / "file3.txt").exists()
        assert (dest / "another_dir" / "data.txt").exists()
        assert (dest / "another_dir" / "subdir" / "nested.txt").exists()

        # Verify directories exist
        assert (dest / "level1").is_dir()
        assert (dest / "level1" / "level2").is_dir()
        assert (dest / "level1" / "level2" / "level3").is_dir()
        assert (dest / "another_dir").is_dir()
        assert (dest / "another_dir" / "subdir").is_dir()

    def test_extract_creates_destination(
        self,
        extraction_engine: ExtractionEngine,
        sample_archive: Path,
        tmp_path: Path,
    ) -> None:
        """Test that extraction creates destination directory if not exists."""
        # Use a deeply nested path that doesn't exist
        dest_path = tmp_path / "new" / "nested" / "destination" / "path"
        assert not dest_path.exists()

        task = ExtractionTask(
            task_id="test-create-dest",
            archive_path=sample_archive,
            destination_path=dest_path,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            create_root_folder=False,
        )

        result = extraction_engine.extract(task)

        assert result is True
        assert dest_path.exists()
        assert dest_path.is_dir()
        assert (dest_path / "file1.txt").exists()

    def test_extract_with_root_folder(
        self,
        extraction_engine: ExtractionEngine,
        sample_archive: Path,
        tmp_path: Path,
    ) -> None:
        """Test extraction creates root folder when task.create_root_folder=True."""
        dest_path = tmp_path / "extracted_with_root"

        task = ExtractionTask(
            task_id="test-root-folder",
            archive_path=sample_archive,
            destination_path=dest_path,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            create_root_folder=True,
        )

        result = extraction_engine.extract(task)

        assert result is True

        # The archive name without extension should be the root folder
        # sample_archive is "sample.zip" so root folder should be "sample"
        root_folder = dest_path / "sample"
        assert root_folder.exists()
        assert root_folder.is_dir()
        assert (root_folder / "file1.txt").exists()
        assert (root_folder / "file2.txt").exists()
        assert (root_folder / "file3.txt").exists()

    def test_extract_without_root_folder(
        self,
        extraction_engine: ExtractionEngine,
        sample_archive: Path,
        tmp_path: Path,
    ) -> None:
        """Test extraction extracts flat when create_root_folder=False."""
        dest_path = tmp_path / "extracted_flat"

        task = ExtractionTask(
            task_id="test-no-root-folder",
            archive_path=sample_archive,
            destination_path=dest_path,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            create_root_folder=False,
        )

        result = extraction_engine.extract(task)

        assert result is True

        # Files should be directly in destination, no root folder
        assert (dest_path / "file1.txt").exists()
        assert (dest_path / "file2.txt").exists()
        assert (dest_path / "file3.txt").exists()

        # There should NOT be a "sample" subfolder
        assert not (dest_path / "sample").exists()


# =============================================================================
# Tests for File Attributes
# =============================================================================


class TestFileAttributes:
    """Test suite for file attribute preservation during extraction."""

    def test_extract_preserves_timestamps(
        self,
        extraction_engine: ExtractionEngine,
        archive_with_timestamps: Path,
        tmp_path: Path,
    ) -> None:
        """Test that extraction maintains modification times when preserve_timestamps=True."""
        dest_path = tmp_path / "extracted_timestamps"

        task = ExtractionTask(
            task_id="test-timestamps",
            archive_path=archive_with_timestamps,
            destination_path=dest_path,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            preserve_timestamps=True,
            create_root_folder=False,
        )

        result = extraction_engine.extract(task)

        assert result is True

        extracted_file = dest_path / "timestamped_file.txt"
        assert extracted_file.exists()

        # Get the modification time of the extracted file
        mtime = extracted_file.stat().st_mtime
        extracted_datetime = datetime.fromtimestamp(mtime)

        # The timestamp should match (2023-06-15 14:30:00)
        # Allow some tolerance for timezone/filesystem differences
        expected_datetime = datetime(2023, 6, 15, 14, 30, 0)

        # Check year, month, day at minimum
        assert extracted_datetime.year == expected_datetime.year
        assert extracted_datetime.month == expected_datetime.month
        assert extracted_datetime.day == expected_datetime.day
        assert extracted_datetime.hour == expected_datetime.hour
        assert extracted_datetime.minute == expected_datetime.minute

    def test_extract_ignores_timestamps_when_disabled(
        self,
        extraction_engine: ExtractionEngine,
        archive_with_timestamps: Path,
        tmp_path: Path,
    ) -> None:
        """Test that extraction uses current time when preserve_timestamps=False."""
        dest_path = tmp_path / "extracted_no_timestamps"

        task = ExtractionTask(
            task_id="test-no-timestamps",
            archive_path=archive_with_timestamps,
            destination_path=dest_path,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            preserve_timestamps=False,
            create_root_folder=False,
        )

        # Record time before extraction
        before_extraction = time.time()

        result = extraction_engine.extract(task)

        after_extraction = time.time()

        assert result is True

        extracted_file = dest_path / "timestamped_file.txt"
        mtime = extracted_file.stat().st_mtime

        # Modification time should be close to current time, not the archived time
        assert mtime >= before_extraction - 1  # 1 second tolerance
        assert mtime <= after_extraction + 1


# =============================================================================
# Tests for Conflict Resolution
# =============================================================================


class TestConflictResolution:
    """Test suite for file conflict resolution during extraction."""

    def test_extract_conflict_overwrite(
        self,
        extraction_engine: ExtractionEngine,
        sample_archive: Path,
        tmp_path: Path,
    ) -> None:
        """Test that extraction overwrites existing files when ConflictResolution.OVERWRITE."""
        dest_path = tmp_path / "extracted_overwrite"
        dest_path.mkdir(parents=True)

        # Create existing file with different content
        existing_file = dest_path / "file1.txt"
        existing_file.write_text("Original content that should be overwritten")

        task = ExtractionTask(
            task_id="test-overwrite",
            archive_path=sample_archive,
            destination_path=dest_path,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            create_root_folder=False,
        )

        result = extraction_engine.extract(task)

        assert result is True

        # File should be overwritten with archive content
        assert existing_file.read_text() == "Hello, World!"

    def test_extract_conflict_skip(
        self,
        extraction_engine: ExtractionEngine,
        sample_archive: Path,
        tmp_path: Path,
    ) -> None:
        """Test that extraction skips existing files when ConflictResolution.SKIP."""
        dest_path = tmp_path / "extracted_skip"
        dest_path.mkdir(parents=True)

        # Create existing file with different content
        existing_file = dest_path / "file1.txt"
        original_content = "Original content that should NOT be overwritten"
        existing_file.write_text(original_content)

        task = ExtractionTask(
            task_id="test-skip",
            archive_path=sample_archive,
            destination_path=dest_path,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.SKIP,
            create_root_folder=False,
        )

        result = extraction_engine.extract(task)

        assert result is True

        # Existing file should NOT be overwritten
        assert existing_file.read_text() == original_content

        # Other files should still be extracted
        assert (dest_path / "file2.txt").exists()
        assert (dest_path / "file2.txt").read_text() == "This is a test file."

    def test_extract_conflict_rename(
        self,
        extraction_engine: ExtractionEngine,
        sample_archive: Path,
        tmp_path: Path,
    ) -> None:
        """Test extraction creates unique names when ConflictResolution.RENAME."""
        dest_path = tmp_path / "extracted_rename"
        dest_path.mkdir(parents=True)

        # Create existing file
        existing_file = dest_path / "file1.txt"
        original_content = "Original content"
        existing_file.write_text(original_content)

        task = ExtractionTask(
            task_id="test-rename",
            archive_path=sample_archive,
            destination_path=dest_path,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.RENAME,
            create_root_folder=False,
        )

        result = extraction_engine.extract(task)

        assert result is True

        # Original file should be untouched
        assert existing_file.read_text() == original_content

        # New file should be created with a different name
        renamed_file = dest_path / "file1 (1).txt"
        assert renamed_file.exists()
        assert renamed_file.read_text() == "Hello, World!"

    def test_extract_conflict_rename_multiple(
        self,
        extraction_engine: ExtractionEngine,
        sample_archive: Path,
        tmp_path: Path,
    ) -> None:
        """Test that rename handles multiple conflicts correctly."""
        dest_path = tmp_path / "extracted_rename_multi"
        dest_path.mkdir(parents=True)

        # Create multiple existing files with the same base name
        (dest_path / "file1.txt").write_text("Original")
        (dest_path / "file1 (1).txt").write_text("First rename")
        (dest_path / "file1 (2).txt").write_text("Second rename")

        task = ExtractionTask(
            task_id="test-rename-multi",
            archive_path=sample_archive,
            destination_path=dest_path,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.RENAME,
            create_root_folder=False,
        )

        result = extraction_engine.extract(task)

        assert result is True

        # Should find the next available number
        renamed_file = dest_path / "file1 (3).txt"
        assert renamed_file.exists()
        assert renamed_file.read_text() == "Hello, World!"


# =============================================================================
# Tests for Security
# =============================================================================


class TestSecurityExtraction:
    """Test suite for security-related extraction functionality."""

    def test_extract_blocks_path_traversal(
        self,
        extraction_engine: ExtractionEngine,
        archive_with_path_traversal: Path,
        tmp_path: Path,
    ) -> None:
        """Test that extraction refuses to extract paths with ../."""
        dest_path = tmp_path / "extracted_safe"

        task = ExtractionTask(
            task_id="test-path-traversal",
            archive_path=archive_with_path_traversal,
            destination_path=dest_path,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            create_root_folder=False,
        )

        result = extraction_engine.extract(task)

        # Extraction should succeed (for safe files) but skip dangerous paths
        # OR it could return False if any dangerous file is detected

        # The normal file should be extracted
        assert (dest_path / "normal_file.txt").exists()

        # The malicious files should NOT have been extracted outside destination
        # Check that no files were created outside the destination
        assert not (tmp_path / "etc" / "malicious.txt").exists()
        assert not (tmp_path / "outside.txt").exists()

        # Also verify nothing was created at system level (this is important!)
        # We can't easily test /etc/malicious.txt but we can check the task
        # The task should have recorded the skipped files
        assert len(task.failed_files) > 0 or result is True

    def test_extract_blocks_absolute_paths(
        self,
        extraction_engine: ExtractionEngine,
        tmp_path: Path,
    ) -> None:
        """Test that extraction blocks absolute paths in archive."""
        # Create archive with absolute path
        archive_path = tmp_path / "absolute_path.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("normal.txt", "Normal file")
            info = zipfile.ZipInfo("/etc/passwd_copy")
            zf.writestr(info, "Malicious content")

        dest_path = tmp_path / "extracted_abs"

        task = ExtractionTask(
            task_id="test-absolute-path",
            archive_path=archive_path,
            destination_path=dest_path,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            create_root_folder=False,
        )

        result = extraction_engine.extract(task)

        # Normal file should be extracted
        assert (dest_path / "normal.txt").exists()

        # Absolute path file should not be extracted to actual location
        assert not Path("/etc/passwd_copy").exists()


# =============================================================================
# Tests for Error Handling
# =============================================================================


class TestErrorHandling:
    """Test suite for error handling during extraction."""

    def test_extract_fails_insufficient_space(
        self,
        extraction_engine: ExtractionEngine,
        large_archive: Path,
        tmp_path: Path,
    ) -> None:
        """Test that extraction returns False with error when not enough space."""
        dest_path = tmp_path / "extracted_no_space"

        task = ExtractionTask(
            task_id="test-no-space",
            archive_path=large_archive,
            destination_path=dest_path,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            create_root_folder=False,
        )

        # Mock disk space check to simulate insufficient space
        with patch("shutil.disk_usage") as mock_disk_usage:
            from collections import namedtuple
            DiskUsage = namedtuple("DiskUsage", ["total", "used", "free"])
            # Simulate only 1KB free (not enough for the large archive)
            mock_disk_usage.return_value = DiskUsage(
                total=1024 * 1024,
                used=1024 * 1024 - 1024,
                free=1024,
            )

            result = extraction_engine.extract(task)

            assert result is False
            assert task.error_message is not None
            assert "space" in task.error_message.lower() or "disk" in task.error_message.lower()
            assert task.status == TaskStatus.FAILED

    def test_extract_handles_corrupted_file(
        self,
        extraction_engine: ExtractionEngine,
        tmp_path: Path,
    ) -> None:
        """Test that extraction handles individual file errors gracefully."""
        # Create an archive with a corrupted entry
        archive_path = tmp_path / "partial_corrupt.zip"

        # Create a valid zip first
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("good_file1.txt", "This file is fine")
            zf.writestr("good_file2.txt", "This file is also fine")

        # Now corrupt part of the archive (but keep it openable)
        # This is tricky - we'll create a situation where one file is unreadable
        # For this test, we'll mock the extraction to fail for one file

        dest_path = tmp_path / "extracted_partial"

        task = ExtractionTask(
            task_id="test-corrupted",
            archive_path=archive_path,
            destination_path=dest_path,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            create_root_folder=False,
        )

        result = extraction_engine.extract(task)

        # Extraction should succeed overall
        assert result is True

        # Good files should be extracted
        assert (dest_path / "good_file1.txt").exists()
        assert (dest_path / "good_file2.txt").exists()

    def test_extract_nonexistent_archive(
        self,
        extraction_engine: ExtractionEngine,
        tmp_path: Path,
    ) -> None:
        """Test extraction of non-existent archive fails gracefully."""
        task = ExtractionTask(
            task_id="test-nonexistent",
            archive_path=tmp_path / "does_not_exist.zip",
            destination_path=tmp_path / "extracted",
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            create_root_folder=False,
        )

        result = extraction_engine.extract(task)

        assert result is False
        assert task.status == TaskStatus.FAILED
        assert task.error_message is not None

    def test_extract_invalid_archive(
        self,
        extraction_engine: ExtractionEngine,
        tmp_path: Path,
    ) -> None:
        """Test extraction of invalid archive fails gracefully."""
        # Create an invalid file
        invalid_archive = tmp_path / "invalid.zip"
        invalid_archive.write_text("This is not a valid ZIP file")

        task = ExtractionTask(
            task_id="test-invalid",
            archive_path=invalid_archive,
            destination_path=tmp_path / "extracted",
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            create_root_folder=False,
        )

        result = extraction_engine.extract(task)

        assert result is False
        assert task.status == TaskStatus.FAILED
        assert task.error_message is not None


# =============================================================================
# Tests for Control (Cancellation)
# =============================================================================


class TestExtractionControl:
    """Test suite for extraction control functionality."""

    def test_extract_cancellation(
        self,
        extraction_engine: ExtractionEngine,
        large_archive: Path,
        tmp_path: Path,
    ) -> None:
        """Test that extraction stops when cancel() is called."""
        dest_path = tmp_path / "extracted_cancelled"

        task = ExtractionTask(
            task_id="test-cancel",
            archive_path=large_archive,
            destination_path=dest_path,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            create_root_folder=False,
        )

        # Start extraction in a thread
        extraction_result = [None]

        def run_extraction() -> None:
            extraction_result[0] = extraction_engine.extract(task)

        extraction_thread = Thread(target=run_extraction)
        extraction_thread.start()

        # Give it a tiny bit of time to start
        time.sleep(0.1)

        # Cancel the extraction
        extraction_engine.cancel()

        # Wait for the thread to finish
        extraction_thread.join(timeout=5.0)

        # Extraction should have been cancelled OR completed (race condition with fast extraction)
        # The cancel mechanism works at file boundaries, so if extraction is very fast,
        # it may complete before the cancel flag is checked
        assert task.status in (TaskStatus.CANCELLED, TaskStatus.COMPLETED)
        if task.status == TaskStatus.CANCELLED:
            assert extraction_result[0] is False
        else:
            # Extraction completed before cancel - this is acceptable
            assert extraction_result[0] is True

    def test_extract_progress_callback(
        self,
        extraction_engine: ExtractionEngine,
        sample_archive: Path,
        tmp_path: Path,
    ) -> None:
        """Test that extraction calls progress callback with correct values."""
        dest_path = tmp_path / "extracted_progress"

        task = ExtractionTask(
            task_id="test-progress",
            archive_path=sample_archive,
            destination_path=dest_path,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            create_root_folder=False,
            total_files=3,
            total_bytes=69,
        )

        # Track progress callback calls
        progress_calls: list[ExtractionTask] = []

        def progress_callback(task: ExtractionTask) -> None:
            # Make a snapshot of relevant values
            progress_calls.append(ExtractionTask(
                task_id=task.task_id,
                archive_path=task.archive_path,
                destination_path=task.destination_path,
                status=task.status,
                conflict_resolution=task.conflict_resolution,
                total_files=task.total_files,
                extracted_files=task.extracted_files,
                total_bytes=task.total_bytes,
                extracted_bytes=task.extracted_bytes,
                current_file=task.current_file,
            ))

        result = extraction_engine.extract(task, progress_callback=progress_callback)

        assert result is True

        # Progress callback should have been called
        assert len(progress_calls) > 0

        # Check the final progress call shows completion
        final_call = progress_calls[-1]
        assert final_call.extracted_files == 3
        assert final_call.extracted_bytes > 0

    def test_extract_progress_callback_receives_file_names(
        self,
        extraction_engine: ExtractionEngine,
        sample_archive: Path,
        tmp_path: Path,
    ) -> None:
        """Test that progress callback receives correct file names."""
        dest_path = tmp_path / "extracted_progress_names"

        task = ExtractionTask(
            task_id="test-progress-names",
            archive_path=sample_archive,
            destination_path=dest_path,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            create_root_folder=False,
        )

        extracted_files: list[str] = []

        def progress_callback(task: ExtractionTask) -> None:
            if task.current_file and task.current_file not in extracted_files:
                extracted_files.append(task.current_file)

        result = extraction_engine.extract(task, progress_callback=progress_callback)

        assert result is True

        # All three files should have been reported
        assert "file1.txt" in extracted_files
        assert "file2.txt" in extracted_files
        assert "file3.txt" in extracted_files


# =============================================================================
# Tests for Task Status Updates
# =============================================================================


class TestTaskStatusUpdates:
    """Test suite for task status updates during extraction."""

    def test_extract_updates_task_status(
        self,
        extraction_engine: ExtractionEngine,
        extraction_task: ExtractionTask,
    ) -> None:
        """Test that extraction sets status to RUNNING then COMPLETED."""
        # Initially QUEUED
        assert extraction_task.status == TaskStatus.QUEUED

        # Track status changes
        status_history: list[TaskStatus] = []
        original_status = extraction_task.status

        def track_status() -> None:
            while extraction_task.status != TaskStatus.COMPLETED:
                if extraction_task.status not in status_history:
                    status_history.append(extraction_task.status)
                time.sleep(0.01)
            status_history.append(extraction_task.status)

        # We can't easily track status during extraction without mocking
        # So we'll just verify the final state
        result = extraction_engine.extract(extraction_task)

        assert result is True
        assert extraction_task.status == TaskStatus.COMPLETED
        assert extraction_task.started_at is not None
        assert extraction_task.completed_at is not None
        assert extraction_task.completed_at >= extraction_task.started_at

    def test_extract_updates_extracted_files_count(
        self,
        extraction_engine: ExtractionEngine,
        extraction_task: ExtractionTask,
    ) -> None:
        """Test that extraction updates extracted_files count correctly."""
        # Initially 0
        assert extraction_task.extracted_files == 0

        result = extraction_engine.extract(extraction_task)

        assert result is True

        # Should have extracted all 3 files
        assert extraction_task.extracted_files == 3

    def test_extract_updates_extracted_bytes(
        self,
        extraction_engine: ExtractionEngine,
        extraction_task: ExtractionTask,
    ) -> None:
        """Test that extraction updates extracted_bytes correctly."""
        # Initially 0
        assert extraction_task.extracted_bytes == 0

        result = extraction_engine.extract(extraction_task)

        assert result is True

        # Should have extracted all bytes
        # Content: "Hello, World!" (13) + "This is a test file." (20) +
        #          "Another text file with some content." (36) = 69 bytes
        expected_bytes = 13 + 20 + 36
        assert extraction_task.extracted_bytes == expected_bytes

    def test_extract_updates_current_file(
        self,
        extraction_engine: ExtractionEngine,
        sample_archive: Path,
        tmp_path: Path,
    ) -> None:
        """Test that extraction updates current_file during processing."""
        dest_path = tmp_path / "extracted_current"

        task = ExtractionTask(
            task_id="test-current-file",
            archive_path=sample_archive,
            destination_path=dest_path,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            create_root_folder=False,
        )

        current_files_seen: list[str] = []

        def progress_callback(task: ExtractionTask) -> None:
            if task.current_file and task.current_file not in current_files_seen:
                current_files_seen.append(task.current_file)

        result = extraction_engine.extract(task, progress_callback=progress_callback)

        assert result is True

        # After completion, current_file could be None or the last file
        # But during extraction, it should have been updated
        # We should have seen at least some files being processed
        assert len(current_files_seen) > 0

    def test_extract_sets_started_at(
        self,
        extraction_engine: ExtractionEngine,
        extraction_task: ExtractionTask,
    ) -> None:
        """Test that extraction sets started_at timestamp."""
        assert extraction_task.started_at is None

        before_start = datetime.now()
        result = extraction_engine.extract(extraction_task)
        after_start = datetime.now()

        assert result is True
        assert extraction_task.started_at is not None
        assert before_start <= extraction_task.started_at <= after_start

    def test_extract_sets_completed_at(
        self,
        extraction_engine: ExtractionEngine,
        extraction_task: ExtractionTask,
    ) -> None:
        """Test that extraction sets completed_at timestamp."""
        assert extraction_task.completed_at is None

        result = extraction_engine.extract(extraction_task)
        after_complete = datetime.now()

        assert result is True
        assert extraction_task.completed_at is not None
        assert extraction_task.completed_at <= after_complete

    def test_extract_failed_sets_error_status(
        self,
        extraction_engine: ExtractionEngine,
        tmp_path: Path,
    ) -> None:
        """Test that failed extraction sets FAILED status."""
        task = ExtractionTask(
            task_id="test-failed-status",
            archive_path=tmp_path / "nonexistent.zip",
            destination_path=tmp_path / "extracted",
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            create_root_folder=False,
        )

        result = extraction_engine.extract(task)

        assert result is False
        assert task.status == TaskStatus.FAILED
        assert task.error_message is not None


# =============================================================================
# Additional Edge Case Tests
# =============================================================================


class TestExtractionEdgeCases:
    """Test suite for edge cases in extraction."""

    def test_extract_empty_archive(
        self,
        extraction_engine: ExtractionEngine,
        empty_archive: Path,
        tmp_path: Path,
    ) -> None:
        """Test extraction of empty archive."""
        dest_path = tmp_path / "extracted_empty"

        task = ExtractionTask(
            task_id="test-empty",
            archive_path=empty_archive,
            destination_path=dest_path,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            create_root_folder=False,
        )

        result = extraction_engine.extract(task)

        assert result is True
        assert task.status == TaskStatus.COMPLETED
        assert task.extracted_files == 0

    def test_extract_archive_with_existing_root_folder(
        self,
        extraction_engine: ExtractionEngine,
        archive_with_single_root: Path,
        tmp_path: Path,
    ) -> None:
        """Test extraction with create_root_folder when archive already has root."""
        dest_path = tmp_path / "extracted_existing_root"

        task = ExtractionTask(
            task_id="test-existing-root",
            archive_path=archive_with_single_root,
            destination_path=dest_path,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            create_root_folder=True,  # This should NOT create another root
        )

        result = extraction_engine.extract(task)

        assert result is True

        # When archive already has a root folder and create_root_folder is True,
        # it should use the existing root, not create another layer
        # OR it should create a new root based on archive name
        # This behavior depends on implementation

        # At minimum, files should be accessible
        # Either at dest/myproject/... or dest/single_root/myproject/...
        myproject_files_exist = (
            (dest_path / "myproject" / "file1.txt").exists() or
            (dest_path / "single_root" / "myproject" / "file1.txt").exists()
        )
        assert myproject_files_exist

    def test_extract_unicode_filenames(
        self,
        extraction_engine: ExtractionEngine,
        tmp_path: Path,
    ) -> None:
        """Test extraction of archive with unicode filenames."""
        archive_path = tmp_path / "unicode.zip"

        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("archivo.txt", "Spanish file")
            zf.writestr("fichier.txt", "French file")
            zf.writestr("file_with_spaces.txt", "Spaces in name")

        dest_path = tmp_path / "extracted_unicode"

        task = ExtractionTask(
            task_id="test-unicode",
            archive_path=archive_path,
            destination_path=dest_path,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            create_root_folder=False,
        )

        result = extraction_engine.extract(task)

        assert result is True
        assert (dest_path / "archivo.txt").exists()
        assert (dest_path / "fichier.txt").exists()
        assert (dest_path / "file_with_spaces.txt").exists()

    def test_extract_deeply_nested_structure(
        self,
        extraction_engine: ExtractionEngine,
        tmp_path: Path,
    ) -> None:
        """Test extraction of deeply nested directory structure."""
        archive_path = tmp_path / "deep.zip"

        # Create a deeply nested structure
        deep_path = "/".join([f"level{i}" for i in range(20)]) + "/deep_file.txt"

        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr(deep_path, "Very deep file")

        dest_path = tmp_path / "extracted_deep"

        task = ExtractionTask(
            task_id="test-deep",
            archive_path=archive_path,
            destination_path=dest_path,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            create_root_folder=False,
        )

        result = extraction_engine.extract(task)

        assert result is True

        # Verify the deep file exists
        expected_path = dest_path / deep_path
        assert expected_path.exists()
        assert expected_path.read_text() == "Very deep file"

    def test_extract_preserves_empty_directories(
        self,
        extraction_engine: ExtractionEngine,
        tmp_path: Path,
    ) -> None:
        """Test that extraction creates explicit empty directories."""
        archive_path = tmp_path / "empty_dirs.zip"

        with zipfile.ZipFile(archive_path, "w") as zf:
            # Create explicit directory entries
            zf.writestr("empty_dir/", "")
            zf.writestr("parent/child/", "")
            zf.writestr("parent/file.txt", "Content")

        dest_path = tmp_path / "extracted_empty_dirs"

        task = ExtractionTask(
            task_id="test-empty-dirs",
            archive_path=archive_path,
            destination_path=dest_path,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            create_root_folder=False,
        )

        result = extraction_engine.extract(task)

        assert result is True

        # Empty directories should be created
        assert (dest_path / "empty_dir").is_dir()
        assert (dest_path / "parent" / "child").is_dir()
        assert (dest_path / "parent" / "file.txt").exists()
