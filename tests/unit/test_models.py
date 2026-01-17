"""Comprehensive unit tests for core models.

Tests for:
- TaskStatus enum
- ConflictResolution enum
- ExtractionErrorType enum
- ExtractionTask dataclass
- ArchiveInfo dataclass
- ArchiveFile dataclass
- ProgressStats dataclass

TDD: These tests are written first, before implementation.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest


class TestTaskStatusEnum:
    """Tests for TaskStatus enum."""

    def test_task_status_has_queued_value(self) -> None:
        """TaskStatus should have QUEUED status."""
        from zipextractor.core.models import TaskStatus

        assert hasattr(TaskStatus, "QUEUED")
        assert TaskStatus.QUEUED.value == "queued"

    def test_task_status_has_running_value(self) -> None:
        """TaskStatus should have RUNNING status."""
        from zipextractor.core.models import TaskStatus

        assert hasattr(TaskStatus, "RUNNING")
        assert TaskStatus.RUNNING.value == "running"

    def test_task_status_has_paused_value(self) -> None:
        """TaskStatus should have PAUSED status."""
        from zipextractor.core.models import TaskStatus

        assert hasattr(TaskStatus, "PAUSED")
        assert TaskStatus.PAUSED.value == "paused"

    def test_task_status_has_completed_value(self) -> None:
        """TaskStatus should have COMPLETED status."""
        from zipextractor.core.models import TaskStatus

        assert hasattr(TaskStatus, "COMPLETED")
        assert TaskStatus.COMPLETED.value == "completed"

    def test_task_status_has_failed_value(self) -> None:
        """TaskStatus should have FAILED status."""
        from zipextractor.core.models import TaskStatus

        assert hasattr(TaskStatus, "FAILED")
        assert TaskStatus.FAILED.value == "failed"

    def test_task_status_has_cancelled_value(self) -> None:
        """TaskStatus should have CANCELLED status."""
        from zipextractor.core.models import TaskStatus

        assert hasattr(TaskStatus, "CANCELLED")
        assert TaskStatus.CANCELLED.value == "cancelled"

    def test_task_status_has_exactly_six_values(self) -> None:
        """TaskStatus should have exactly 6 status values."""
        from zipextractor.core.models import TaskStatus

        assert len(TaskStatus) == 6

    def test_task_status_values_are_unique(self) -> None:
        """TaskStatus values should all be unique."""
        from zipextractor.core.models import TaskStatus

        values = [status.value for status in TaskStatus]
        assert len(values) == len(set(values))

    def test_task_status_is_iterable(self) -> None:
        """TaskStatus should be iterable."""
        from zipextractor.core.models import TaskStatus

        statuses = list(TaskStatus)
        assert len(statuses) == 6

    def test_task_status_comparison(self) -> None:
        """TaskStatus members should be comparable by identity."""
        from zipextractor.core.models import TaskStatus

        assert TaskStatus.QUEUED == TaskStatus.QUEUED
        assert TaskStatus.QUEUED != TaskStatus.RUNNING


class TestConflictResolutionEnum:
    """Tests for ConflictResolution enum."""

    def test_conflict_resolution_has_ask_value(self) -> None:
        """ConflictResolution should have ASK option."""
        from zipextractor.core.models import ConflictResolution

        assert hasattr(ConflictResolution, "ASK")
        assert ConflictResolution.ASK.value == "ask"

    def test_conflict_resolution_has_overwrite_value(self) -> None:
        """ConflictResolution should have OVERWRITE option."""
        from zipextractor.core.models import ConflictResolution

        assert hasattr(ConflictResolution, "OVERWRITE")
        assert ConflictResolution.OVERWRITE.value == "overwrite"

    def test_conflict_resolution_has_skip_value(self) -> None:
        """ConflictResolution should have SKIP option."""
        from zipextractor.core.models import ConflictResolution

        assert hasattr(ConflictResolution, "SKIP")
        assert ConflictResolution.SKIP.value == "skip"

    def test_conflict_resolution_has_rename_value(self) -> None:
        """ConflictResolution should have RENAME option."""
        from zipextractor.core.models import ConflictResolution

        assert hasattr(ConflictResolution, "RENAME")
        assert ConflictResolution.RENAME.value == "rename"

    def test_conflict_resolution_has_exactly_four_values(self) -> None:
        """ConflictResolution should have exactly 4 options."""
        from zipextractor.core.models import ConflictResolution

        assert len(ConflictResolution) == 4

    def test_conflict_resolution_values_are_unique(self) -> None:
        """ConflictResolution values should all be unique."""
        from zipextractor.core.models import ConflictResolution

        values = [resolution.value for resolution in ConflictResolution]
        assert len(values) == len(set(values))


class TestExtractionErrorTypeEnum:
    """Tests for ExtractionErrorType enum."""

    def test_extraction_error_type_has_disk_space_value(self) -> None:
        """ExtractionErrorType should have DISK_SPACE error type."""
        from zipextractor.core.models import ExtractionErrorType

        assert hasattr(ExtractionErrorType, "DISK_SPACE")
        assert ExtractionErrorType.DISK_SPACE.value == "disk_space"

    def test_extraction_error_type_has_permission_value(self) -> None:
        """ExtractionErrorType should have PERMISSION error type."""
        from zipextractor.core.models import ExtractionErrorType

        assert hasattr(ExtractionErrorType, "PERMISSION")
        assert ExtractionErrorType.PERMISSION.value == "permission"

    def test_extraction_error_type_has_corruption_value(self) -> None:
        """ExtractionErrorType should have CORRUPTION error type."""
        from zipextractor.core.models import ExtractionErrorType

        assert hasattr(ExtractionErrorType, "CORRUPTION")
        assert ExtractionErrorType.CORRUPTION.value == "corruption"

    def test_extraction_error_type_has_unsupported_value(self) -> None:
        """ExtractionErrorType should have UNSUPPORTED error type."""
        from zipextractor.core.models import ExtractionErrorType

        assert hasattr(ExtractionErrorType, "UNSUPPORTED")
        assert ExtractionErrorType.UNSUPPORTED.value == "unsupported"

    def test_extraction_error_type_has_unknown_value(self) -> None:
        """ExtractionErrorType should have UNKNOWN error type."""
        from zipextractor.core.models import ExtractionErrorType

        assert hasattr(ExtractionErrorType, "UNKNOWN")
        assert ExtractionErrorType.UNKNOWN.value == "unknown"

    def test_extraction_error_type_has_at_least_five_values(self) -> None:
        """ExtractionErrorType should have at least 5 error types."""
        from zipextractor.core.models import ExtractionErrorType

        assert len(ExtractionErrorType) >= 5

    def test_extraction_error_type_values_are_unique(self) -> None:
        """ExtractionErrorType values should all be unique."""
        from zipextractor.core.models import ExtractionErrorType

        values = [error_type.value for error_type in ExtractionErrorType]
        assert len(values) == len(set(values))


class TestExtractionTask:
    """Tests for ExtractionTask dataclass."""

    @pytest.fixture
    def sample_task(self) -> Any:
        """Create a sample extraction task for testing."""
        from zipextractor.core.models import (
            ConflictResolution,
            ExtractionTask,
            TaskStatus,
        )

        return ExtractionTask(
            task_id="task-001",
            archive_path=Path("/home/user/archive.zip"),
            destination_path=Path("/home/user/extracted"),
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.ASK,
            total_files=100,
            extracted_files=0,
            total_bytes=1024 * 1024 * 100,  # 100 MB
            extracted_bytes=0,
            created_at=datetime.now(),
        )

    def test_extraction_task_creation(self, sample_task: Any) -> None:
        """ExtractionTask should be creatable with required fields."""
        assert sample_task.task_id == "task-001"
        assert sample_task.archive_path == Path("/home/user/archive.zip")
        assert sample_task.destination_path == Path("/home/user/extracted")

    def test_extraction_task_has_required_fields(self) -> None:
        """ExtractionTask should have all required fields."""
        from zipextractor.core.models import ExtractionTask

        required_fields = [
            "task_id",
            "archive_path",
            "destination_path",
            "status",
            "conflict_resolution",
            "total_files",
            "extracted_files",
            "total_bytes",
            "extracted_bytes",
            "created_at",
        ]
        for field in required_fields:
            assert hasattr(ExtractionTask, "__dataclass_fields__")
            assert field in ExtractionTask.__dataclass_fields__

    def test_extraction_task_has_optional_fields(self) -> None:
        """ExtractionTask should have optional fields with defaults."""
        from zipextractor.core.models import ExtractionTask

        optional_fields = [
            "current_file",
            "started_at",
            "completed_at",
            "error_message",
            "failed_files",
        ]
        for field in optional_fields:
            assert field in ExtractionTask.__dataclass_fields__

    def test_extraction_task_progress_percentage_zero_bytes(self) -> None:
        """progress_percentage should return 0.0 when total_bytes is 0."""
        from zipextractor.core.models import (
            ConflictResolution,
            ExtractionTask,
            TaskStatus,
        )

        task = ExtractionTask(
            task_id="task-002",
            archive_path=Path("/archive.zip"),
            destination_path=Path("/dest"),
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.ASK,
            total_files=0,
            extracted_files=0,
            total_bytes=0,
            extracted_bytes=0,
            created_at=datetime.now(),
        )
        assert task.progress_percentage == 0.0

    def test_extraction_task_progress_percentage_partial(self) -> None:
        """progress_percentage should calculate correctly for partial progress."""
        from zipextractor.core.models import (
            ConflictResolution,
            ExtractionTask,
            TaskStatus,
        )

        task = ExtractionTask(
            task_id="task-003",
            archive_path=Path("/archive.zip"),
            destination_path=Path("/dest"),
            status=TaskStatus.RUNNING,
            conflict_resolution=ConflictResolution.ASK,
            total_files=100,
            extracted_files=50,
            total_bytes=1000,
            extracted_bytes=500,
            created_at=datetime.now(),
        )
        assert task.progress_percentage == 50.0

    def test_extraction_task_progress_percentage_complete(self) -> None:
        """progress_percentage should return 100.0 when fully extracted."""
        from zipextractor.core.models import (
            ConflictResolution,
            ExtractionTask,
            TaskStatus,
        )

        task = ExtractionTask(
            task_id="task-004",
            archive_path=Path("/archive.zip"),
            destination_path=Path("/dest"),
            status=TaskStatus.COMPLETED,
            conflict_resolution=ConflictResolution.ASK,
            total_files=100,
            extracted_files=100,
            total_bytes=1000,
            extracted_bytes=1000,
            created_at=datetime.now(),
        )
        assert task.progress_percentage == 100.0

    def test_extraction_task_progress_percentage_returns_float(self) -> None:
        """progress_percentage should return a float."""
        from zipextractor.core.models import (
            ConflictResolution,
            ExtractionTask,
            TaskStatus,
        )

        task = ExtractionTask(
            task_id="task-005",
            archive_path=Path("/archive.zip"),
            destination_path=Path("/dest"),
            status=TaskStatus.RUNNING,
            conflict_resolution=ConflictResolution.ASK,
            total_files=100,
            extracted_files=33,
            total_bytes=1000,
            extracted_bytes=333,
            created_at=datetime.now(),
        )
        assert isinstance(task.progress_percentage, float)
        assert task.progress_percentage == pytest.approx(33.3, rel=0.01)

    def test_extraction_task_is_active_when_queued(self) -> None:
        """is_active should return True when status is QUEUED."""
        from zipextractor.core.models import (
            ConflictResolution,
            ExtractionTask,
            TaskStatus,
        )

        task = ExtractionTask(
            task_id="task-006",
            archive_path=Path("/archive.zip"),
            destination_path=Path("/dest"),
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.ASK,
            total_files=100,
            extracted_files=0,
            total_bytes=1000,
            extracted_bytes=0,
            created_at=datetime.now(),
        )
        assert task.is_active is True

    def test_extraction_task_is_active_when_running(self) -> None:
        """is_active should return True when status is RUNNING."""
        from zipextractor.core.models import (
            ConflictResolution,
            ExtractionTask,
            TaskStatus,
        )

        task = ExtractionTask(
            task_id="task-007",
            archive_path=Path("/archive.zip"),
            destination_path=Path("/dest"),
            status=TaskStatus.RUNNING,
            conflict_resolution=ConflictResolution.ASK,
            total_files=100,
            extracted_files=50,
            total_bytes=1000,
            extracted_bytes=500,
            created_at=datetime.now(),
        )
        assert task.is_active is True

    def test_extraction_task_is_not_active_when_paused(self) -> None:
        """is_active should return False when status is PAUSED."""
        from zipextractor.core.models import (
            ConflictResolution,
            ExtractionTask,
            TaskStatus,
        )

        task = ExtractionTask(
            task_id="task-008",
            archive_path=Path("/archive.zip"),
            destination_path=Path("/dest"),
            status=TaskStatus.PAUSED,
            conflict_resolution=ConflictResolution.ASK,
            total_files=100,
            extracted_files=50,
            total_bytes=1000,
            extracted_bytes=500,
            created_at=datetime.now(),
        )
        assert task.is_active is False

    def test_extraction_task_is_not_active_when_completed(self) -> None:
        """is_active should return False when status is COMPLETED."""
        from zipextractor.core.models import (
            ConflictResolution,
            ExtractionTask,
            TaskStatus,
        )

        task = ExtractionTask(
            task_id="task-009",
            archive_path=Path("/archive.zip"),
            destination_path=Path("/dest"),
            status=TaskStatus.COMPLETED,
            conflict_resolution=ConflictResolution.ASK,
            total_files=100,
            extracted_files=100,
            total_bytes=1000,
            extracted_bytes=1000,
            created_at=datetime.now(),
        )
        assert task.is_active is False

    def test_extraction_task_is_not_active_when_failed(self) -> None:
        """is_active should return False when status is FAILED."""
        from zipextractor.core.models import (
            ConflictResolution,
            ExtractionTask,
            TaskStatus,
        )

        task = ExtractionTask(
            task_id="task-010",
            archive_path=Path("/archive.zip"),
            destination_path=Path("/dest"),
            status=TaskStatus.FAILED,
            conflict_resolution=ConflictResolution.ASK,
            total_files=100,
            extracted_files=25,
            total_bytes=1000,
            extracted_bytes=250,
            created_at=datetime.now(),
            error_message="Extraction failed",
        )
        assert task.is_active is False

    def test_extraction_task_is_not_active_when_cancelled(self) -> None:
        """is_active should return False when status is CANCELLED."""
        from zipextractor.core.models import (
            ConflictResolution,
            ExtractionTask,
            TaskStatus,
        )

        task = ExtractionTask(
            task_id="task-011",
            archive_path=Path("/archive.zip"),
            destination_path=Path("/dest"),
            status=TaskStatus.CANCELLED,
            conflict_resolution=ConflictResolution.ASK,
            total_files=100,
            extracted_files=25,
            total_bytes=1000,
            extracted_bytes=250,
            created_at=datetime.now(),
        )
        assert task.is_active is False

    def test_extraction_task_default_optional_fields(self) -> None:
        """Optional fields should have sensible defaults."""
        from zipextractor.core.models import (
            ConflictResolution,
            ExtractionTask,
            TaskStatus,
        )

        task = ExtractionTask(
            task_id="task-012",
            archive_path=Path("/archive.zip"),
            destination_path=Path("/dest"),
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.ASK,
            total_files=100,
            extracted_files=0,
            total_bytes=1000,
            extracted_bytes=0,
            created_at=datetime.now(),
        )
        assert task.current_file is None
        assert task.started_at is None
        assert task.completed_at is None
        assert task.error_message is None

    def test_extraction_task_with_current_file(self) -> None:
        """ExtractionTask should accept current_file parameter."""
        from zipextractor.core.models import (
            ConflictResolution,
            ExtractionTask,
            TaskStatus,
        )

        task = ExtractionTask(
            task_id="task-013",
            archive_path=Path("/archive.zip"),
            destination_path=Path("/dest"),
            status=TaskStatus.RUNNING,
            conflict_resolution=ConflictResolution.ASK,
            total_files=100,
            extracted_files=50,
            total_bytes=1000,
            extracted_bytes=500,
            created_at=datetime.now(),
            current_file="subdir/file.txt",
        )
        assert task.current_file == "subdir/file.txt"

    def test_extraction_task_with_error_message(self) -> None:
        """ExtractionTask should accept error_message parameter."""
        from zipextractor.core.models import (
            ConflictResolution,
            ExtractionTask,
            TaskStatus,
        )

        task = ExtractionTask(
            task_id="task-014",
            archive_path=Path("/archive.zip"),
            destination_path=Path("/dest"),
            status=TaskStatus.FAILED,
            conflict_resolution=ConflictResolution.ASK,
            total_files=100,
            extracted_files=25,
            total_bytes=1000,
            extracted_bytes=250,
            created_at=datetime.now(),
            error_message="Permission denied",
        )
        assert task.error_message == "Permission denied"

    def test_extraction_task_with_timestamps(self) -> None:
        """ExtractionTask should accept started_at and completed_at."""
        from zipextractor.core.models import (
            ConflictResolution,
            ExtractionTask,
            TaskStatus,
        )

        created = datetime(2024, 1, 1, 10, 0, 0)
        started = datetime(2024, 1, 1, 10, 0, 1)
        completed = datetime(2024, 1, 1, 10, 0, 30)

        task = ExtractionTask(
            task_id="task-015",
            archive_path=Path("/archive.zip"),
            destination_path=Path("/dest"),
            status=TaskStatus.COMPLETED,
            conflict_resolution=ConflictResolution.ASK,
            total_files=100,
            extracted_files=100,
            total_bytes=1000,
            extracted_bytes=1000,
            created_at=created,
            started_at=started,
            completed_at=completed,
        )
        assert task.created_at == created
        assert task.started_at == started
        assert task.completed_at == completed


class TestArchiveInfo:
    """Tests for ArchiveInfo dataclass."""

    def test_archive_info_creation(self) -> None:
        """ArchiveInfo should be creatable with required fields."""
        from zipextractor.core.models import ArchiveInfo

        info = ArchiveInfo(
            path=Path("/archive.zip"),
            file_size=1024 * 1024,
            uncompressed_size=1024 * 1024 * 2,
            file_count=50,
            compression_method="DEFLATE",
            has_password=False,
            root_folder="archive",
            is_valid=True,
            validation_errors=[],
            files=[],
        )
        assert info.path == Path("/archive.zip")
        assert info.file_size == 1024 * 1024
        assert info.file_count == 50

    def test_archive_info_has_required_fields(self) -> None:
        """ArchiveInfo should have all required fields."""
        from zipextractor.core.models import ArchiveInfo

        required_fields = [
            "path",
            "file_size",
            "uncompressed_size",
            "file_count",
            "compression_method",
            "has_password",
            "root_folder",
            "is_valid",
            "validation_errors",
            "files",
        ]
        for field in required_fields:
            assert hasattr(ArchiveInfo, "__dataclass_fields__")
            assert field in ArchiveInfo.__dataclass_fields__

    def test_archive_info_compression_ratio_normal(self) -> None:
        """compression_ratio should calculate correctly for normal archives."""
        from zipextractor.core.models import ArchiveInfo

        info = ArchiveInfo(
            path=Path("/archive.zip"),
            file_size=500,
            uncompressed_size=1000,
            file_count=10,
            compression_method="DEFLATE",
            has_password=False,
            root_folder=None,
            is_valid=True,
            validation_errors=[],
            files=[],
        )
        # Compression ratio = (1 - 500/1000) * 100 = 50%
        assert info.compression_ratio == 50.0

    def test_archive_info_compression_ratio_zero_uncompressed(self) -> None:
        """compression_ratio should return 0.0 when uncompressed_size is 0."""
        from zipextractor.core.models import ArchiveInfo

        info = ArchiveInfo(
            path=Path("/empty.zip"),
            file_size=0,
            uncompressed_size=0,
            file_count=0,
            compression_method="STORE",
            has_password=False,
            root_folder=None,
            is_valid=True,
            validation_errors=[],
            files=[],
        )
        assert info.compression_ratio == 0.0

    def test_archive_info_compression_ratio_no_compression(self) -> None:
        """compression_ratio should return 0.0 when file_size equals uncompressed_size."""
        from zipextractor.core.models import ArchiveInfo

        info = ArchiveInfo(
            path=Path("/stored.zip"),
            file_size=1000,
            uncompressed_size=1000,
            file_count=10,
            compression_method="STORE",
            has_password=False,
            root_folder=None,
            is_valid=True,
            validation_errors=[],
            files=[],
        )
        assert info.compression_ratio == 0.0

    def test_archive_info_compression_ratio_high_compression(self) -> None:
        """compression_ratio should handle high compression correctly."""
        from zipextractor.core.models import ArchiveInfo

        info = ArchiveInfo(
            path=Path("/highly_compressed.zip"),
            file_size=100,
            uncompressed_size=1000,
            file_count=10,
            compression_method="DEFLATE",
            has_password=False,
            root_folder=None,
            is_valid=True,
            validation_errors=[],
            files=[],
        )
        # Compression ratio = (1 - 100/1000) * 100 = 90%
        assert info.compression_ratio == 90.0

    def test_archive_info_compression_ratio_returns_float(self) -> None:
        """compression_ratio should return a float."""
        from zipextractor.core.models import ArchiveInfo

        info = ArchiveInfo(
            path=Path("/archive.zip"),
            file_size=333,
            uncompressed_size=1000,
            file_count=10,
            compression_method="DEFLATE",
            has_password=False,
            root_folder=None,
            is_valid=True,
            validation_errors=[],
            files=[],
        )
        assert isinstance(info.compression_ratio, float)
        assert info.compression_ratio == pytest.approx(66.7, rel=0.01)

    def test_archive_info_with_password(self) -> None:
        """ArchiveInfo should support password-protected archives."""
        from zipextractor.core.models import ArchiveInfo

        info = ArchiveInfo(
            path=Path("/protected.zip"),
            file_size=1000,
            uncompressed_size=2000,
            file_count=5,
            compression_method="DEFLATE",
            has_password=True,
            root_folder=None,
            is_valid=True,
            validation_errors=[],
            files=[],
        )
        assert info.has_password is True

    def test_archive_info_with_validation_errors(self) -> None:
        """ArchiveInfo should store validation errors."""
        from zipextractor.core.models import ArchiveInfo

        errors = ["CRC mismatch in file1.txt", "Invalid header"]
        info = ArchiveInfo(
            path=Path("/corrupted.zip"),
            file_size=1000,
            uncompressed_size=2000,
            file_count=5,
            compression_method="DEFLATE",
            has_password=False,
            root_folder=None,
            is_valid=False,
            validation_errors=errors,
            files=[],
        )
        assert info.is_valid is False
        assert len(info.validation_errors) == 2
        assert "CRC mismatch in file1.txt" in info.validation_errors

    def test_archive_info_with_root_folder(self) -> None:
        """ArchiveInfo should store root folder information."""
        from zipextractor.core.models import ArchiveInfo

        info = ArchiveInfo(
            path=Path("/project.zip"),
            file_size=1000,
            uncompressed_size=2000,
            file_count=50,
            compression_method="DEFLATE",
            has_password=False,
            root_folder="project-v1.0",
            is_valid=True,
            validation_errors=[],
            files=[],
        )
        assert info.root_folder == "project-v1.0"

    def test_archive_info_root_folder_can_be_none(self) -> None:
        """ArchiveInfo root_folder should accept None."""
        from zipextractor.core.models import ArchiveInfo

        info = ArchiveInfo(
            path=Path("/flat.zip"),
            file_size=1000,
            uncompressed_size=2000,
            file_count=10,
            compression_method="DEFLATE",
            has_password=False,
            root_folder=None,
            is_valid=True,
            validation_errors=[],
            files=[],
        )
        assert info.root_folder is None


class TestArchiveFile:
    """Tests for ArchiveFile dataclass."""

    def test_archive_file_creation(self) -> None:
        """ArchiveFile should be creatable with required fields."""
        from zipextractor.core.models import ArchiveFile

        file = ArchiveFile(
            path="docs/readme.txt",
            size=1024,
            compressed_size=512,
            is_directory=False,
            modified_time=datetime(2024, 1, 15, 10, 30, 0),
        )
        assert file.path == "docs/readme.txt"
        assert file.size == 1024
        assert file.compressed_size == 512

    def test_archive_file_has_required_fields(self) -> None:
        """ArchiveFile should have all required fields."""
        from zipextractor.core.models import ArchiveFile

        required_fields = [
            "path",
            "size",
            "compressed_size",
            "is_directory",
            "modified_time",
        ]
        for field in required_fields:
            assert hasattr(ArchiveFile, "__dataclass_fields__")
            assert field in ArchiveFile.__dataclass_fields__

    def test_archive_file_is_directory_true(self) -> None:
        """ArchiveFile should represent directories."""
        from zipextractor.core.models import ArchiveFile

        directory = ArchiveFile(
            path="docs/",
            size=0,
            compressed_size=0,
            is_directory=True,
            modified_time=datetime(2024, 1, 15, 10, 30, 0),
        )
        assert directory.is_directory is True
        assert directory.size == 0

    def test_archive_file_is_directory_false(self) -> None:
        """ArchiveFile should represent regular files."""
        from zipextractor.core.models import ArchiveFile

        file = ArchiveFile(
            path="docs/readme.txt",
            size=1024,
            compressed_size=512,
            is_directory=False,
            modified_time=datetime(2024, 1, 15, 10, 30, 0),
        )
        assert file.is_directory is False

    def test_archive_file_with_crc32(self) -> None:
        """ArchiveFile should accept optional crc32 parameter."""
        from zipextractor.core.models import ArchiveFile

        file = ArchiveFile(
            path="data.bin",
            size=2048,
            compressed_size=1024,
            is_directory=False,
            modified_time=datetime(2024, 1, 15, 10, 30, 0),
            crc32=0xDEADBEEF,
        )
        assert file.crc32 == 0xDEADBEEF

    def test_archive_file_crc32_default_none(self) -> None:
        """ArchiveFile crc32 should default to None."""
        from zipextractor.core.models import ArchiveFile

        file = ArchiveFile(
            path="file.txt",
            size=100,
            compressed_size=50,
            is_directory=False,
            modified_time=datetime(2024, 1, 15, 10, 30, 0),
        )
        assert file.crc32 is None

    def test_archive_file_modified_time(self) -> None:
        """ArchiveFile should store modified_time correctly."""
        from zipextractor.core.models import ArchiveFile

        timestamp = datetime(2023, 6, 15, 14, 30, 45)
        file = ArchiveFile(
            path="old_file.txt",
            size=100,
            compressed_size=50,
            is_directory=False,
            modified_time=timestamp,
        )
        assert file.modified_time == timestamp
        assert file.modified_time.year == 2023
        assert file.modified_time.month == 6

    def test_archive_file_nested_path(self) -> None:
        """ArchiveFile should handle deeply nested paths."""
        from zipextractor.core.models import ArchiveFile

        file = ArchiveFile(
            path="level1/level2/level3/level4/deep_file.txt",
            size=100,
            compressed_size=50,
            is_directory=False,
            modified_time=datetime(2024, 1, 15, 10, 30, 0),
        )
        assert file.path == "level1/level2/level3/level4/deep_file.txt"

    def test_archive_file_unicode_path(self) -> None:
        """ArchiveFile should handle unicode characters in paths."""
        from zipextractor.core.models import ArchiveFile

        file = ArchiveFile(
            path="documents/resume_resume.txt",
            size=100,
            compressed_size=50,
            is_directory=False,
            modified_time=datetime(2024, 1, 15, 10, 30, 0),
        )
        assert file.path == "documents/resume_resume.txt"


class TestProgressStats:
    """Tests for ProgressStats dataclass."""

    def test_progress_stats_creation(self) -> None:
        """ProgressStats should be creatable with required fields."""
        from zipextractor.core.models import ProgressStats

        stats = ProgressStats(
            current_speed_mbps=10.5,
            average_speed_mbps=8.3,
            eta_seconds=120,
            elapsed_seconds=60,
        )
        assert stats.current_speed_mbps == 10.5
        assert stats.average_speed_mbps == 8.3
        assert stats.eta_seconds == 120
        assert stats.elapsed_seconds == 60

    def test_progress_stats_has_required_fields(self) -> None:
        """ProgressStats should have all required fields."""
        from zipextractor.core.models import ProgressStats

        required_fields = [
            "current_speed_mbps",
            "average_speed_mbps",
            "eta_seconds",
            "elapsed_seconds",
        ]
        for field in required_fields:
            assert hasattr(ProgressStats, "__dataclass_fields__")
            assert field in ProgressStats.__dataclass_fields__

    def test_progress_stats_eta_formatted_seconds_only(self) -> None:
        """eta_formatted should return seconds format for < 60 seconds."""
        from zipextractor.core.models import ProgressStats

        stats = ProgressStats(
            current_speed_mbps=10.0,
            average_speed_mbps=10.0,
            eta_seconds=45,
            elapsed_seconds=30,
        )
        assert stats.eta_formatted == "45s"

    def test_progress_stats_eta_formatted_zero_seconds(self) -> None:
        """eta_formatted should handle 0 seconds."""
        from zipextractor.core.models import ProgressStats

        stats = ProgressStats(
            current_speed_mbps=10.0,
            average_speed_mbps=10.0,
            eta_seconds=0,
            elapsed_seconds=100,
        )
        assert stats.eta_formatted == "0s"

    def test_progress_stats_eta_formatted_minutes_and_seconds(self) -> None:
        """eta_formatted should return minutes and seconds for < 1 hour."""
        from zipextractor.core.models import ProgressStats

        stats = ProgressStats(
            current_speed_mbps=5.0,
            average_speed_mbps=5.0,
            eta_seconds=185,  # 3 minutes and 5 seconds
            elapsed_seconds=60,
        )
        assert stats.eta_formatted == "3m 5s"

    def test_progress_stats_eta_formatted_exact_minutes(self) -> None:
        """eta_formatted should handle exact minutes."""
        from zipextractor.core.models import ProgressStats

        stats = ProgressStats(
            current_speed_mbps=5.0,
            average_speed_mbps=5.0,
            eta_seconds=180,  # exactly 3 minutes
            elapsed_seconds=60,
        )
        assert stats.eta_formatted == "3m 0s"

    def test_progress_stats_eta_formatted_one_minute(self) -> None:
        """eta_formatted should handle exactly 60 seconds as 1 minute."""
        from zipextractor.core.models import ProgressStats

        stats = ProgressStats(
            current_speed_mbps=5.0,
            average_speed_mbps=5.0,
            eta_seconds=60,
            elapsed_seconds=30,
        )
        assert stats.eta_formatted == "1m 0s"

    def test_progress_stats_eta_formatted_hours_and_minutes(self) -> None:
        """eta_formatted should return hours and minutes for >= 1 hour."""
        from zipextractor.core.models import ProgressStats

        stats = ProgressStats(
            current_speed_mbps=1.0,
            average_speed_mbps=1.0,
            eta_seconds=3723,  # 1 hour, 2 minutes, 3 seconds
            elapsed_seconds=300,
        )
        assert stats.eta_formatted == "1h 2m"

    def test_progress_stats_eta_formatted_exact_hour(self) -> None:
        """eta_formatted should handle exact hours."""
        from zipextractor.core.models import ProgressStats

        stats = ProgressStats(
            current_speed_mbps=1.0,
            average_speed_mbps=1.0,
            eta_seconds=3600,  # exactly 1 hour
            elapsed_seconds=300,
        )
        assert stats.eta_formatted == "1h 0m"

    def test_progress_stats_eta_formatted_multiple_hours(self) -> None:
        """eta_formatted should handle multiple hours."""
        from zipextractor.core.models import ProgressStats

        stats = ProgressStats(
            current_speed_mbps=0.5,
            average_speed_mbps=0.5,
            eta_seconds=7500,  # 2 hours and 5 minutes
            elapsed_seconds=600,
        )
        assert stats.eta_formatted == "2h 5m"

    def test_progress_stats_eta_formatted_large_value(self) -> None:
        """eta_formatted should handle large time values."""
        from zipextractor.core.models import ProgressStats

        stats = ProgressStats(
            current_speed_mbps=0.1,
            average_speed_mbps=0.1,
            eta_seconds=36000,  # 10 hours
            elapsed_seconds=1000,
        )
        assert stats.eta_formatted == "10h 0m"

    def test_progress_stats_eta_formatted_returns_string(self) -> None:
        """eta_formatted should return a string."""
        from zipextractor.core.models import ProgressStats

        stats = ProgressStats(
            current_speed_mbps=10.0,
            average_speed_mbps=10.0,
            eta_seconds=100,
            elapsed_seconds=50,
        )
        assert isinstance(stats.eta_formatted, str)

    def test_progress_stats_speed_values(self) -> None:
        """ProgressStats should accept various speed values."""
        from zipextractor.core.models import ProgressStats

        # Very fast
        stats_fast = ProgressStats(
            current_speed_mbps=100.0,
            average_speed_mbps=95.5,
            eta_seconds=5,
            elapsed_seconds=10,
        )
        assert stats_fast.current_speed_mbps == 100.0

        # Very slow
        stats_slow = ProgressStats(
            current_speed_mbps=0.01,
            average_speed_mbps=0.005,
            eta_seconds=86400,
            elapsed_seconds=100,
        )
        assert stats_slow.current_speed_mbps == 0.01

    def test_progress_stats_zero_speed(self) -> None:
        """ProgressStats should handle zero speed."""
        from zipextractor.core.models import ProgressStats

        stats = ProgressStats(
            current_speed_mbps=0.0,
            average_speed_mbps=0.0,
            eta_seconds=0,
            elapsed_seconds=60,
        )
        assert stats.current_speed_mbps == 0.0
        assert stats.average_speed_mbps == 0.0


class TestModelsIntegration:
    """Integration tests for models working together."""

    def test_archive_info_with_archive_files(self) -> None:
        """ArchiveInfo should work with a list of ArchiveFile objects."""
        from zipextractor.core.models import ArchiveFile, ArchiveInfo

        files = [
            ArchiveFile(
                path="readme.txt",
                size=1024,
                compressed_size=512,
                is_directory=False,
                modified_time=datetime(2024, 1, 15, 10, 0, 0),
            ),
            ArchiveFile(
                path="src/",
                size=0,
                compressed_size=0,
                is_directory=True,
                modified_time=datetime(2024, 1, 15, 10, 0, 0),
            ),
            ArchiveFile(
                path="src/main.py",
                size=2048,
                compressed_size=1024,
                is_directory=False,
                modified_time=datetime(2024, 1, 15, 10, 0, 0),
                crc32=0x12345678,
            ),
        ]

        info = ArchiveInfo(
            path=Path("/project.zip"),
            file_size=1536,
            uncompressed_size=3072,
            file_count=3,
            compression_method="DEFLATE",
            has_password=False,
            root_folder=None,
            is_valid=True,
            validation_errors=[],
            files=files,
        )

        assert len(info.files) == 3
        assert info.files[0].path == "readme.txt"
        assert info.files[1].is_directory is True
        assert info.files[2].crc32 == 0x12345678

    def test_extraction_task_with_all_status_transitions(self) -> None:
        """ExtractionTask should handle all status values correctly."""
        from zipextractor.core.models import (
            ConflictResolution,
            ExtractionTask,
            TaskStatus,
        )

        base_kwargs = {
            "task_id": "task-transition",
            "archive_path": Path("/archive.zip"),
            "destination_path": Path("/dest"),
            "conflict_resolution": ConflictResolution.OVERWRITE,
            "total_files": 100,
            "extracted_files": 50,
            "total_bytes": 1000,
            "extracted_bytes": 500,
            "created_at": datetime.now(),
        }

        for status in TaskStatus:
            task = ExtractionTask(status=status, **base_kwargs)
            assert task.status == status
            # Verify is_active is consistent
            expected_active = status in {TaskStatus.QUEUED, TaskStatus.RUNNING}
            assert task.is_active == expected_active

    def test_all_conflict_resolutions_with_extraction_task(self) -> None:
        """ExtractionTask should accept all ConflictResolution values."""
        from zipextractor.core.models import (
            ConflictResolution,
            ExtractionTask,
            TaskStatus,
        )

        base_kwargs = {
            "task_id": "task-conflict",
            "archive_path": Path("/archive.zip"),
            "destination_path": Path("/dest"),
            "status": TaskStatus.QUEUED,
            "total_files": 10,
            "extracted_files": 0,
            "total_bytes": 1000,
            "extracted_bytes": 0,
            "created_at": datetime.now(),
        }

        for resolution in ConflictResolution:
            task = ExtractionTask(conflict_resolution=resolution, **base_kwargs)
            assert task.conflict_resolution == resolution
