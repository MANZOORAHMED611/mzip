from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
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


class ArchiveFormat(Enum):
    """Supported archive formats."""

    ZIP = auto()
    SEVEN_ZIP = auto()
    TAR = auto()
    TAR_GZ = auto()
    TAR_BZ2 = auto()
    TAR_XZ = auto()
    TAR_ZSTD = auto()
    RAR = auto()
    GZ = auto()  # Single-file gzip
    GZIP = auto()  # Alias for GZ
    BZ2 = auto()  # Single-file bzip2
    BZIP2 = auto()  # Alias for BZ2
    XZ = auto()
    ZSTD = auto()
    LZ4 = auto()
    CAB = auto()
    ISO = auto()
    DEB = auto()
    RPM = auto()
    CPIO = auto()
    ARJ = auto()
    LZH = auto()
    # ZIP-based formats
    JAR = auto()  # Java archive
    WAR = auto()  # Web application archive
    APK = auto()  # Android package
    EPUB = auto()  # Electronic publication
    DOCX = auto()  # Word document
    XLSX = auto()  # Excel spreadsheet
    UNKNOWN = auto()


class CompressionMethod(Enum):
    """Compression algorithms."""

    STORE = auto()  # No compression
    DEFLATE = auto()  # ZIP default
    DEFLATE64 = auto()  # Enhanced deflate
    BZIP2 = auto()  # Good for text
    LZMA = auto()  # High compression
    LZMA2 = auto()  # 7z default
    ZSTD = auto()  # Fast, modern
    LZ4 = auto()  # Very fast
    PPMD = auto()  # PPMd algorithm


class EncryptionMethod(Enum):
    """Encryption algorithms."""

    NONE = auto()
    ZIPCRYPTO = auto()  # Legacy ZIP encryption (weak)
    AES_128 = auto()  # AES-128 CTR
    AES_192 = auto()  # AES-192 CTR
    AES_256 = auto()  # AES-256 CTR (recommended)

@dataclass
class ArchiveFile:
    path: str
    size: int
    compressed_size: int
    is_directory: bool
    modified_time: datetime | None = None
    crc32: int | None = None


@dataclass
class FileInfo:
    """Information about a file within an archive.

    Attributes:
        name: File path within archive.
        size: Uncompressed size in bytes.
        compressed_size: Compressed size in bytes.
        is_directory: Whether this is a directory entry.
        modified: Last modification time.
        created: Creation time (if available).
        permissions: Unix permissions (if available).
        crc32: CRC32 checksum (if available).
        compression_method: Compression method used.
        is_encrypted: Whether file is encrypted.
    """

    name: str
    size: int = 0
    compressed_size: int = 0
    is_directory: bool = False
    modified: datetime | None = None
    created: datetime | None = None
    permissions: int | None = None
    crc32: int | None = None
    compression_method: str = ""
    is_encrypted: bool = False

    @property
    def compression_ratio(self) -> float:
        """Calculate compression ratio as percentage saved."""
        if self.size == 0:
            return 0.0
        return ((self.size - self.compressed_size) / self.size) * 100.0

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


@dataclass
class CompressionOptions:
    """Options for archive compression.

    Attributes:
        format: Target archive format.
        method: Compression algorithm to use.
        level: Compression level (0-9, higher = better compression, slower).
        solid: Create solid archive (7z only, better compression).
        encrypt: Whether to encrypt the archive.
        encrypt_filenames: Encrypt filenames (7z only).
        password: Password for encryption (if encrypt=True).
        split_size: Split archive size in bytes (None = no splitting).
        threads: Number of threads (0 = auto-detect).
        include_hidden: Include hidden files.
        preserve_timestamps: Preserve file modification times.
        preserve_permissions: Preserve Unix file permissions.
        follow_symlinks: Follow symbolic links.
        base_path: Base path for relative paths in archive.
    """

    format: ArchiveFormat = ArchiveFormat.ZIP
    method: CompressionMethod = CompressionMethod.DEFLATE
    level: int = 6
    solid: bool = False
    encrypt: bool = False
    encrypt_filenames: bool = False
    password: str | None = None
    split_size: int | None = None
    threads: int = 0
    include_hidden: bool = True
    preserve_timestamps: bool = True
    preserve_permissions: bool = True
    follow_symlinks: bool = False
    base_path: Path | None = None

    def __post_init__(self) -> None:
        """Validate compression options."""
        if self.level < 0 or self.level > 9:
            msg = f"Compression level must be 0-9, got {self.level}"
            raise ValueError(msg)
        if self.encrypt and not self.password:
            msg = "Password required when encryption is enabled"
            raise ValueError(msg)
        if self.encrypt_filenames and self.format != ArchiveFormat.SEVEN_ZIP:
            msg = "Filename encryption only supported for 7z format"
            raise ValueError(msg)
        if self.solid and self.format != ArchiveFormat.SEVEN_ZIP:
            msg = "Solid archives only supported for 7z format"
            raise ValueError(msg)


@dataclass
class CompressionResult:
    """Result of a compression operation.

    Attributes:
        success: Whether compression completed successfully.
        output_path: Path to the created archive.
        original_size: Total size of input files in bytes.
        compressed_size: Size of output archive in bytes.
        file_count: Number of files compressed.
        elapsed_seconds: Time taken for compression.
        error_message: Error message if compression failed.
        split_parts: List of split archive parts (if split_size was set).
    """

    success: bool
    output_path: Path
    original_size: int = 0
    compressed_size: int = 0
    file_count: int = 0
    elapsed_seconds: float = 0.0
    error_message: str | None = None
    split_parts: list[Path] = field(default_factory=list)

    @property
    def compression_ratio(self) -> float:
        """Calculate compression ratio as percentage saved."""
        if self.original_size == 0:
            return 0.0
        return ((self.original_size - self.compressed_size) / self.original_size) * 100.0

    @property
    def compression_speed_mbps(self) -> float:
        """Calculate compression speed in MB/s."""
        if self.elapsed_seconds <= 0:
            return 0.0
        return (self.original_size / (1024 * 1024)) / self.elapsed_seconds


@dataclass
class CompressionTask:
    """Task for compressing files into an archive.

    Attributes:
        task_id: Unique identifier for the task.
        source_files: List of files/directories to compress.
        output_path: Path for the output archive.
        options: Compression options.
        status: Current task status.
        total_files: Total number of files to compress.
        compressed_files: Number of files compressed so far.
        total_bytes: Total bytes to compress.
        compressed_bytes: Bytes compressed so far.
        current_file: Currently processing file.
        created_at: When the task was created.
        started_at: When compression started.
        completed_at: When compression completed.
        error_message: Error message if failed.
    """

    task_id: str
    source_files: list[Path]
    output_path: Path
    options: CompressionOptions = field(default_factory=CompressionOptions)
    status: TaskStatus = TaskStatus.QUEUED
    total_files: int = 0
    compressed_files: int = 0
    total_bytes: int = 0
    compressed_bytes: int = 0
    current_file: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None

    @property
    def progress_percentage(self) -> float:
        """Calculate progress as percentage."""
        if self.total_bytes == 0:
            return 0.0
        return (self.compressed_bytes / self.total_bytes) * 100.0

    @property
    def is_active(self) -> bool:
        """Check if task is actively being processed or waiting to run."""
        return self.status in (TaskStatus.QUEUED, TaskStatus.RUNNING)
