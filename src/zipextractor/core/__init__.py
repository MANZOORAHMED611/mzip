"""Core functionality for ZIP Extractor.

This package contains the core extraction engine, validation logic,
progress tracking, and error handling.
"""

from zipextractor.core.extraction import ExtractionEngine
from zipextractor.core.models import (
    ArchiveFile,
    ArchiveInfo,
    ConflictResolution,
    ExtractionError,
    ExtractionErrorType,
    ExtractionTask,
    ProgressStats,
    TaskStatus,
)
from zipextractor.core.progress import ProgressTracker
from zipextractor.core.validation import (
    detect_root_folder,
    detect_zip_bomb,
    get_archive_info,
    is_safe_path,
    validate_archive,
    validate_disk_space,
)

__all__: list[str] = [
    "ArchiveFile",
    "ArchiveInfo",
    "ConflictResolution",
    "ExtractionEngine",
    "ExtractionError",
    "ExtractionErrorType",
    "ExtractionTask",
    "ProgressStats",
    "ProgressTracker",
    "TaskStatus",
    "detect_root_folder",
    "detect_zip_bomb",
    "get_archive_info",
    "is_safe_path",
    "validate_archive",
    "validate_disk_space",
]
