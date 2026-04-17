"""Base archive handler interface.

Defines the abstract base class that all format handlers must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from zipextractor.utils.logging import get_logger

if TYPE_CHECKING:
    from zipextractor.core.formats import FormatCapability
    from zipextractor.core.models import ArchiveFormat, FileInfo

logger = get_logger(__name__)


@dataclass
class ExtractionOptions:
    """Options for extraction operations.

    Attributes:
        output_path: Destination directory for extraction.
        password: Password for encrypted archives.
        preserve_timestamps: Whether to preserve file timestamps.
        preserve_permissions: Whether to preserve file permissions.
        overwrite: Whether to overwrite existing files.
        selected_files: Specific files to extract (None = all).
    """

    output_path: Path
    password: str | None = None
    preserve_timestamps: bool = True
    preserve_permissions: bool = True
    overwrite: bool = False
    selected_files: list[str] | None = None


@dataclass
class CreationOptions:
    """Options for archive creation.

    Attributes:
        compression_level: Compression level (0-9).
        compression_method: Compression method name.
        password: Password for encryption.
        encrypt_filenames: Whether to encrypt filenames (7z).
        solid: Whether to use solid compression (7z).
        split_size: Split archive size in bytes (0 = no split).
    """

    compression_level: int = 6
    compression_method: str = "deflate"
    password: str | None = None
    encrypt_filenames: bool = False
    solid: bool = False
    split_size: int = 0


@dataclass
class ArchiveInfo:
    """Information about an archive.

    Attributes:
        path: Path to the archive.
        format: Archive format.
        file_count: Number of files in archive.
        total_size: Total uncompressed size.
        compressed_size: Total compressed size.
        is_encrypted: Whether archive is encrypted.
        is_split: Whether archive is split.
        comment: Archive comment.
    """

    path: Path
    format: ArchiveFormat
    file_count: int = 0
    total_size: int = 0
    compressed_size: int = 0
    is_encrypted: bool = False
    is_split: bool = False
    comment: str = ""


class ArchiveHandler(ABC):
    """Abstract base class for archive format handlers.

    All format-specific handlers must inherit from this class
    and implement the abstract methods.
    """

    def __init__(self, path: Path) -> None:
        """Initialize handler with archive path.

        Args:
            path: Path to the archive file.
        """
        self._path = path
        self._password: str | None = None

    @property
    def path(self) -> Path:
        """Get archive path."""
        return self._path

    @property
    @abstractmethod
    def format(self) -> ArchiveFormat:
        """Get the archive format this handler supports."""

    @property
    @abstractmethod
    def capabilities(self) -> set[FormatCapability]:
        """Get supported capabilities."""

    def set_password(self, password: str | None) -> None:
        """Set password for encrypted operations.

        Args:
            password: Password or None to clear.
        """
        self._password = password

    @abstractmethod
    def list_contents(self) -> list[FileInfo]:
        """List all files in the archive.

        Returns:
            List of FileInfo objects.
        """

    @abstractmethod
    def get_info(self) -> ArchiveInfo:
        """Get archive information.

        Returns:
            ArchiveInfo with archive details.
        """

    @abstractmethod
    def extract_all(
        self,
        options: ExtractionOptions,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Extract all files from archive.

        Args:
            options: Extraction options.
            progress_callback: Optional callback(filename, current, total).
        """

    @abstractmethod
    def extract_files(
        self,
        files: list[str],
        options: ExtractionOptions,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Extract specific files from archive.

        Args:
            files: List of file paths within archive.
            options: Extraction options.
            progress_callback: Optional callback(filename, current, total).
        """

    @abstractmethod
    def read_file(self, file_path: str) -> bytes:
        """Read a single file from archive without extracting.

        Args:
            file_path: Path to file within archive.

        Returns:
            File contents as bytes.
        """

    def test(self) -> bool:
        """Test archive integrity.

        Returns:
            True if archive is valid.
        """
        try:
            for _info in self.list_contents():
                pass
            return True
        except Exception as e:
            logger.warning("Archive test failed: %s", e)
            return False

    def is_encrypted(self) -> bool:
        """Check if archive is encrypted.

        Returns:
            True if archive requires password.
        """
        info = self.get_info()
        return info.is_encrypted

    def iter_contents(self) -> Iterator[FileInfo]:
        """Iterate over archive contents.

        Yields:
            FileInfo for each file in archive.
        """
        yield from self.list_contents()


class WritableHandler(ArchiveHandler):
    """Extended handler for formats that support writing."""

    @abstractmethod
    def create(
        self,
        files: list[Path],
        options: CreationOptions,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Create a new archive.

        Args:
            files: Files and directories to add.
            options: Creation options.
            progress_callback: Optional callback(filename, current, total).
        """

    @abstractmethod
    def add_files(
        self,
        files: list[Path],
        base_path: Path | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Add files to existing archive.

        Args:
            files: Files and directories to add.
            base_path: Base path for relative paths in archive.
            progress_callback: Optional callback(filename, current, total).
        """

    def delete_files(self, files: list[str]) -> None:
        """Delete files from archive.

        Args:
            files: List of file paths within archive to delete.

        Raises:
            NotImplementedError: If format doesn't support deletion.
        """
        msg = f"Delete not supported for {self.format.name}"
        raise NotImplementedError(msg)

    def update_files(
        self,
        files: list[Path],
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Update files in archive.

        Args:
            files: Files to update.
            progress_callback: Optional callback(filename, current, total).

        Raises:
            NotImplementedError: If format doesn't support update.
        """
        msg = f"Update not supported for {self.format.name}"
        raise NotImplementedError(msg)


class HandlerRegistry:
    """Registry for archive handlers.

    Maps formats to handler classes for dynamic handler instantiation.
    """

    def __init__(self) -> None:
        """Initialize handler registry."""
        self._handlers: dict[ArchiveFormat, type[ArchiveHandler]] = {}

    def register(
        self, fmt: ArchiveFormat, handler_class: type[ArchiveHandler]
    ) -> None:
        """Register a handler for a format.

        Args:
            fmt: Archive format.
            handler_class: Handler class for the format.
        """
        self._handlers[fmt] = handler_class
        logger.debug("Registered handler for %s: %s", fmt.name, handler_class.__name__)

    def get_handler(self, path: Path, fmt: ArchiveFormat | None = None) -> ArchiveHandler:
        """Get a handler instance for an archive.

        Args:
            path: Path to the archive.
            fmt: Optional format (auto-detected if not provided).

        Returns:
            Handler instance for the archive.

        Raises:
            ValueError: If format is not supported.
        """
        if fmt is None:
            from zipextractor.core.formats import detect_format  # noqa: PLC0415

            fmt = detect_format(path)
            if fmt is None:
                msg = f"Unable to detect format for: {path}"
                raise ValueError(msg)

        handler_class = self._handlers.get(fmt)
        if handler_class is None:
            msg = f"No handler registered for format: {fmt.name}"
            raise ValueError(msg)

        return handler_class(path)

    def supports_format(self, fmt: ArchiveFormat) -> bool:
        """Check if a format has a registered handler.

        Args:
            fmt: Archive format.

        Returns:
            True if handler is available.
        """
        return fmt in self._handlers

    def get_supported_formats(self) -> list[ArchiveFormat]:
        """Get list of formats with registered handlers.

        Returns:
            List of supported formats.
        """
        return list(self._handlers.keys())


# Global handler registry
_handler_registry = HandlerRegistry()


def get_handler_registry() -> HandlerRegistry:
    """Get the global handler registry.

    Returns:
        HandlerRegistry singleton.
    """
    return _handler_registry


def register_handler(fmt: ArchiveFormat, handler_class: type[ArchiveHandler]) -> None:
    """Register a handler in the global registry.

    Args:
        fmt: Archive format.
        handler_class: Handler class.
    """
    _handler_registry.register(fmt, handler_class)


def get_handler(path: Path | str, fmt: ArchiveFormat | None = None) -> ArchiveHandler:
    """Get a handler for an archive file.

    Args:
        path: Path to the archive.
        fmt: Optional format override.

    Returns:
        Handler instance.
    """
    if isinstance(path, str):
        path = Path(path)
    return _handler_registry.get_handler(path, fmt)
