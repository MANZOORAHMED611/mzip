from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class TaskStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ConflictResolution(Enum):
    ASK = "ask"
    OVERWRITE = "overwrite"
    SKIP = "skip"
    RENAME = "rename"

class ExtractionErrorType(Enum):
    DISK_SPACE = "disk_space"
    PERMISSION = "permission"
    CORRUPTION = "corruption"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"

@dataclass
class ArchiveFile:
    path: str
    size: int
    compressed_size: int
    is_directory: bool
    modified_time: datetime | None = None
    crc32: int | None = None

@dataclass
class ArchiveInfo:
    path: Path
    file_size: int
    uncompressed_size: int
    file_count: int
    compression_method: str = "deflate"
    has_password: bool = False
    root_folder: str | None = None
    is_valid: bool = True
    validation_errors: list[str] = field(default_factory=list)
    files: list[ArchiveFile] = field(default_factory=list)

    @property
    def compression_ratio(self) -> float:
        """Calculate compression ratio as percentage saved.

        Returns percentage of space saved: (uncompressed - compressed) / uncompressed * 100
        E.g., 1000 bytes compressed to 500 bytes = 50% compression ratio.
        """
        if self.uncompressed_size == 0:
            return 0.0
        return ((self.uncompressed_size - self.file_size) / self.uncompressed_size) * 100.0

@dataclass
class ProgressStats:
    current_speed_mbps: float = 0.0
    average_speed_mbps: float = 0.0
    eta_seconds: int = 0
    elapsed_seconds: int = 0

    @property
    def eta_formatted(self) -> str:
        if self.eta_seconds <= 0:
            return "0s"
        hours, remainder = divmod(self.eta_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

@dataclass
class ExtractionTask:
    task_id: str
    archive_path: Path
    destination_path: Path
    status: TaskStatus = TaskStatus.QUEUED
    conflict_resolution: ConflictResolution = ConflictResolution.ASK
    total_files: int = 0
    extracted_files: int = 0
    total_bytes: int = 0
    extracted_bytes: int = 0
    current_file: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    failed_files: list[str] = field(default_factory=list)
    preserve_permissions: bool = True
    preserve_timestamps: bool = True
    create_root_folder: bool = True

    @property
    def progress_percentage(self) -> float:
        if self.total_bytes == 0:
            return 0.0
        return (self.extracted_bytes / self.total_bytes) * 100.0

    @property
    def is_active(self) -> bool:
        """Check if task is actively being processed or waiting to run."""
        return self.status in (TaskStatus.QUEUED, TaskStatus.RUNNING)

@dataclass
class ExtractionError:
    error_type: ExtractionErrorType
    file_path: str
    message: str
    is_recoverable: bool = False
    suggested_action: str | None = None
