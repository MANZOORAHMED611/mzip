"""Archive writer for creating compressed archives.

This module provides functionality for creating archives in various formats
including ZIP, TAR, TAR.GZ, TAR.BZ2, TAR.XZ, and TAR.ZSTD.
"""

from __future__ import annotations

import os
import tarfile
import time
import zipfile
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path

from zipextractor.core.compression import HAS_ZSTD
from zipextractor.core.models import (
    ArchiveFormat,
    CompressionMethod,
    CompressionOptions,
    CompressionResult,
)
from zipextractor.utils.logging import get_logger

logger = get_logger(__name__)


# Map archive formats to file extensions
FORMAT_EXTENSIONS: dict[ArchiveFormat, str] = {
    ArchiveFormat.ZIP: ".zip",
    ArchiveFormat.SEVEN_ZIP: ".7z",
    ArchiveFormat.TAR: ".tar",
    ArchiveFormat.TAR_GZ: ".tar.gz",
    ArchiveFormat.TAR_BZ2: ".tar.bz2",
    ArchiveFormat.TAR_XZ: ".tar.xz",
    ArchiveFormat.TAR_ZSTD: ".tar.zst",
    ArchiveFormat.GZIP: ".gz",
    ArchiveFormat.BZIP2: ".bz2",
    ArchiveFormat.XZ: ".xz",
    ArchiveFormat.ZSTD: ".zst",
}

# Map compression methods to ZIP compression types
ZIP_COMPRESSION_TYPES: dict[CompressionMethod, int] = {
    CompressionMethod.STORE: zipfile.ZIP_STORED,
    CompressionMethod.DEFLATE: zipfile.ZIP_DEFLATED,
    CompressionMethod.BZIP2: zipfile.ZIP_BZIP2,
    CompressionMethod.LZMA: zipfile.ZIP_LZMA,
}


class ArchiveWriterBase(ABC):
    """Abstract base class for archive writers."""

    def __init__(
        self,
        output_path: Path,
        options: CompressionOptions,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Initialize archive writer.

        Args:
            output_path: Path for the output archive.
            options: Compression options.
            progress_callback: Callback with (filename, bytes_done, total_bytes).
        """
        self._output_path = output_path
        self._options = options
        self._progress_callback = progress_callback
        self._cancelled = False
        self._paused = False
        self._files_added = 0
        self._bytes_added = 0
        self._total_bytes = 0
        self._start_time: float = 0

    def cancel(self) -> None:
        """Cancel the archive creation."""
        self._cancelled = True

    def pause(self) -> None:
        """Pause the archive creation."""
        self._paused = True

    def resume(self) -> None:
        """Resume the archive creation."""
        self._paused = False

    @property
    def is_cancelled(self) -> bool:
        """Check if creation was cancelled."""
        return self._cancelled

    def _wait_if_paused(self) -> None:
        """Wait while paused."""
        while self._paused and not self._cancelled:
            time.sleep(0.1)

    def _report_progress(self, filename: str, bytes_done: int) -> None:
        """Report progress to callback."""
        if self._progress_callback:
            self._progress_callback(filename, bytes_done, self._total_bytes)

    @abstractmethod
    def create(self, sources: list[Path]) -> CompressionResult:
        """Create archive from source files.

        Args:
            sources: List of files/directories to include.

        Returns:
            CompressionResult with operation details.
        """

    def _collect_files(
        self, sources: list[Path], base_path: Path | None = None
    ) -> Iterator[tuple[Path, str]]:
        """Collect files from source paths.

        Args:
            sources: List of files/directories to include.
            base_path: Base path for relative paths in archive.

        Yields:
            Tuples of (absolute_path, archive_path).
        """
        base = base_path or (sources[0].parent if sources else Path.cwd())

        for source in sources:
            if not source.exists():
                logger.warning("Source path does not exist: %s", source)
                continue

            if source.is_file():
                try:
                    archive_path = source.relative_to(base)
                except ValueError:
                    archive_path = Path(source.name)
                yield source, str(archive_path)

            elif source.is_dir():
                for root, dirs, files in os.walk(
                    source, followlinks=self._options.follow_symlinks
                ):
                    root_path = Path(root)

                    if not self._options.include_hidden:
                        dirs[:] = [d for d in dirs if not d.startswith(".")]

                    for filename in files:
                        if not self._options.include_hidden and filename.startswith("."):
                            continue

                        file_path = root_path / filename
                        try:
                            archive_path = file_path.relative_to(base)
                        except ValueError:
                            archive_path = file_path.relative_to(source.parent)

                        yield file_path, str(archive_path)

    def _calculate_total_size(self, sources: list[Path]) -> tuple[int, int]:
        """Calculate total size and file count.

        Args:
            sources: List of source paths.

        Returns:
            Tuple of (total_bytes, file_count).
        """
        total_bytes = 0
        file_count = 0

        for file_path, _ in self._collect_files(sources, self._options.base_path):
            try:
                total_bytes += file_path.stat().st_size
                file_count += 1
            except OSError as e:
                logger.warning("Could not stat file %s: %s", file_path, e)

        return total_bytes, file_count


class ZipArchiveWriter(ArchiveWriterBase):
    """Writer for ZIP archives."""

    def create(self, sources: list[Path]) -> CompressionResult:
        """Create ZIP archive from source files.

        Args:
            sources: List of files/directories to include.

        Returns:
            CompressionResult with operation details.
        """
        self._start_time = time.monotonic()
        self._total_bytes, _ = self._calculate_total_size(sources)

        # Get ZIP compression type
        compression = ZIP_COMPRESSION_TYPES.get(
            self._options.method, zipfile.ZIP_DEFLATED
        )

        # Ensure output directory exists
        self._output_path.parent.mkdir(parents=True, exist_ok=True)

        original_size = 0
        try:
            with zipfile.ZipFile(
                self._output_path,
                "w",
                compression=compression,
                compresslevel=self._options.level if compression != zipfile.ZIP_STORED else None,
            ) as zf:
                for file_path, archive_path in self._collect_files(
                    sources, self._options.base_path
                ):
                    if self._cancelled:
                        logger.info("ZIP creation cancelled")
                        break

                    self._wait_if_paused()

                    try:
                        # Get file info
                        file_stat = file_path.stat()
                        file_size = file_stat.st_size
                        original_size += file_size

                        # Create ZipInfo with proper attributes
                        zip_info = zipfile.ZipInfo(archive_path)

                        # Set modification time
                        if self._options.preserve_timestamps:
                            mtime = datetime.fromtimestamp(file_stat.st_mtime)
                            zip_info.date_time = (
                                mtime.year,
                                mtime.month,
                                mtime.day,
                                mtime.hour,
                                mtime.minute,
                                mtime.second,
                            )

                        # Set Unix permissions
                        if self._options.preserve_permissions:
                            # Store Unix permissions in external_attr
                            unix_mode = file_stat.st_mode
                            zip_info.external_attr = (unix_mode & 0xFFFF) << 16

                        zip_info.compress_type = compression

                        # Write file with progress tracking
                        with file_path.open("rb") as f:
                            data = f.read()
                            zf.writestr(zip_info, data)

                        self._files_added += 1
                        self._bytes_added += file_size
                        self._report_progress(archive_path, self._bytes_added)

                        logger.debug("Added to ZIP: %s (%d bytes)", archive_path, file_size)

                    except (OSError, PermissionError) as e:
                        logger.warning("Could not add file %s: %s", file_path, e)

            elapsed = time.monotonic() - self._start_time
            compressed_size = self._output_path.stat().st_size

            logger.info(
                "Created ZIP archive: %s (%d files, %d -> %d bytes)",
                self._output_path,
                self._files_added,
                original_size,
                compressed_size,
            )

            return CompressionResult(
                success=not self._cancelled,
                output_path=self._output_path,
                original_size=original_size,
                compressed_size=compressed_size,
                file_count=self._files_added,
                elapsed_seconds=elapsed,
            )

        except Exception as e:
            logger.exception("Failed to create ZIP archive: %s", e)
            return CompressionResult(
                success=False,
                output_path=self._output_path,
                error_message=str(e),
            )


class TarArchiveWriter(ArchiveWriterBase):
    """Writer for TAR archives (including compressed variants)."""

    def _get_tar_mode(self) -> str:
        """Get the tarfile mode based on archive format."""
        mode_map: dict[ArchiveFormat, str] = {
            ArchiveFormat.TAR: "w",
            ArchiveFormat.TAR_GZ: "w:gz",
            ArchiveFormat.TAR_BZ2: "w:bz2",
            ArchiveFormat.TAR_XZ: "w:xz",
        }
        return mode_map.get(self._options.format, "w")

    def create(self, sources: list[Path]) -> CompressionResult:
        """Create TAR archive from source files.

        Args:
            sources: List of files/directories to include.

        Returns:
            CompressionResult with operation details.
        """
        self._start_time = time.monotonic()
        self._total_bytes, _ = self._calculate_total_size(sources)

        # Handle ZSTD separately (requires external library)
        if self._options.format == ArchiveFormat.TAR_ZSTD:
            return self._create_tar_zstd(sources)

        # Ensure output directory exists
        self._output_path.parent.mkdir(parents=True, exist_ok=True)

        original_size = 0
        mode = self._get_tar_mode()

        try:
            # Cast to Any to satisfy mypy with dynamic mode string
            with tarfile.open(str(self._output_path), mode) as tf:  # type: ignore[call-overload]
                for file_path, archive_path in self._collect_files(
                    sources, self._options.base_path
                ):
                    if self._cancelled:
                        logger.info("TAR creation cancelled")
                        break

                    self._wait_if_paused()

                    try:
                        file_stat = file_path.stat()
                        file_size = file_stat.st_size
                        original_size += file_size

                        # Create TarInfo with proper attributes
                        tar_info = tarfile.TarInfo(name=archive_path)
                        tar_info.size = file_size

                        if self._options.preserve_timestamps:
                            tar_info.mtime = int(file_stat.st_mtime)

                        if self._options.preserve_permissions:
                            tar_info.mode = file_stat.st_mode & 0o7777
                            tar_info.uid = file_stat.st_uid
                            tar_info.gid = file_stat.st_gid

                        # Add file
                        with file_path.open("rb") as f:
                            tf.addfile(tar_info, f)

                        self._files_added += 1
                        self._bytes_added += file_size
                        self._report_progress(archive_path, self._bytes_added)

                        logger.debug("Added to TAR: %s (%d bytes)", archive_path, file_size)

                    except (OSError, PermissionError) as e:
                        logger.warning("Could not add file %s: %s", file_path, e)

            elapsed = time.monotonic() - self._start_time
            compressed_size = self._output_path.stat().st_size

            logger.info(
                "Created TAR archive: %s (%d files, %d -> %d bytes)",
                self._output_path,
                self._files_added,
                original_size,
                compressed_size,
            )

            return CompressionResult(
                success=not self._cancelled,
                output_path=self._output_path,
                original_size=original_size,
                compressed_size=compressed_size,
                file_count=self._files_added,
                elapsed_seconds=elapsed,
            )

        except Exception as e:
            logger.exception("Failed to create TAR archive: %s", e)
            return CompressionResult(
                success=False,
                output_path=self._output_path,
                error_message=str(e),
            )

    def _create_tar_zstd(self, sources: list[Path]) -> CompressionResult:
        """Create TAR.ZSTD archive.

        Args:
            sources: List of files/directories to include.

        Returns:
            CompressionResult with operation details.
        """
        if not HAS_ZSTD:
            return CompressionResult(
                success=False,
                output_path=self._output_path,
                error_message="zstandard library not installed",
            )

        import zstandard as zstd  # noqa: PLC0415

        # Create uncompressed TAR first
        tar_path = self._output_path.with_suffix("")
        if tar_path.suffix != ".tar":
            tar_path = tar_path.with_suffix(".tar")

        # Create TAR
        self._options.format = ArchiveFormat.TAR
        temp_output = self._output_path
        self._output_path = tar_path
        tar_result = self.create(sources)
        self._output_path = temp_output

        if not tar_result.success:
            return tar_result

        # Compress with ZSTD
        try:
            cctx = zstd.ZstdCompressor(level=self._options.level * 2 + 1)

            with tar_path.open("rb") as f_in, self._output_path.open("wb") as f_out:
                cctx.copy_stream(f_in, f_out)

            # Remove temporary TAR
            tar_path.unlink()

            compressed_size = self._output_path.stat().st_size
            elapsed = time.monotonic() - self._start_time

            return CompressionResult(
                success=True,
                output_path=self._output_path,
                original_size=tar_result.original_size,
                compressed_size=compressed_size,
                file_count=tar_result.file_count,
                elapsed_seconds=elapsed,
            )

        except Exception as e:
            logger.exception("Failed to compress TAR with ZSTD: %s", e)
            # Clean up
            if tar_path.exists():
                tar_path.unlink()
            return CompressionResult(
                success=False,
                output_path=self._output_path,
                error_message=str(e),
            )


def get_archive_writer(
    output_path: Path,
    options: CompressionOptions,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> ArchiveWriterBase:
    """Get appropriate archive writer for the format.

    Args:
        output_path: Path for the output archive.
        options: Compression options.
        progress_callback: Progress callback function.

    Returns:
        Archive writer instance.

    Raises:
        ValueError: If format is not supported for writing.
    """
    format_to_writer: dict[ArchiveFormat, type[ArchiveWriterBase]] = {
        ArchiveFormat.ZIP: ZipArchiveWriter,
        ArchiveFormat.TAR: TarArchiveWriter,
        ArchiveFormat.TAR_GZ: TarArchiveWriter,
        ArchiveFormat.TAR_BZ2: TarArchiveWriter,
        ArchiveFormat.TAR_XZ: TarArchiveWriter,
        ArchiveFormat.TAR_ZSTD: TarArchiveWriter,
    }

    writer_class = format_to_writer.get(options.format)
    if writer_class is None:
        msg = f"Writing not supported for format: {options.format.name}"
        raise ValueError(msg)

    return writer_class(output_path, options, progress_callback)


def get_writable_formats() -> list[ArchiveFormat]:
    """Get list of formats that can be written.

    Returns:
        List of writable ArchiveFormat values.
    """
    formats = [
        ArchiveFormat.ZIP,
        ArchiveFormat.TAR,
        ArchiveFormat.TAR_GZ,
        ArchiveFormat.TAR_BZ2,
        ArchiveFormat.TAR_XZ,
    ]
    if HAS_ZSTD:
        formats.append(ArchiveFormat.TAR_ZSTD)
    return formats


def suggest_extension(format: ArchiveFormat) -> str:
    """Suggest file extension for archive format.

    Args:
        format: Archive format.

    Returns:
        Suggested file extension including the dot.
    """
    return FORMAT_EXTENSIONS.get(format, ".zip")


class ArchiveWriter:
    """High-level archive writer with unified interface.

    Example:
        >>> writer = ArchiveWriter()
        >>> result = writer.create(
        ...     sources=[Path("file1.txt"), Path("folder/")],
        ...     output=Path("archive.zip"),
        ...     options=CompressionOptions(format=ArchiveFormat.ZIP),
        ... )
        >>> print(f"Created archive: {result.compression_ratio:.1f}% compression")
    """

    def __init__(
        self,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Initialize archive writer.

        Args:
            progress_callback: Callback with (filename, bytes_done, total_bytes).
        """
        self._progress_callback = progress_callback
        self._current_writer: ArchiveWriterBase | None = None

    def create(
        self,
        sources: list[Path],
        output: Path,
        options: CompressionOptions | None = None,
    ) -> CompressionResult:
        """Create archive from source files.

        Args:
            sources: List of files/directories to include.
            output: Path for the output archive.
            options: Compression options (default: ZIP with DEFLATE).

        Returns:
            CompressionResult with operation details.
        """
        options = options or CompressionOptions()

        # Auto-detect format from extension if not specified
        if options.format == ArchiveFormat.ZIP:
            suffix = output.suffix.lower()
            suffixes = "".join(output.suffixes).lower()

            if suffixes.endswith(".tar.gz") or suffixes.endswith(".tgz"):
                options.format = ArchiveFormat.TAR_GZ
            elif suffixes.endswith(".tar.bz2") or suffixes.endswith(".tbz2"):
                options.format = ArchiveFormat.TAR_BZ2
            elif suffixes.endswith(".tar.xz") or suffixes.endswith(".txz"):
                options.format = ArchiveFormat.TAR_XZ
            elif suffixes.endswith(".tar.zst") or suffixes.endswith(".tzst"):
                options.format = ArchiveFormat.TAR_ZSTD
            elif suffix == ".tar":
                options.format = ArchiveFormat.TAR
            elif suffix == ".7z":
                options.format = ArchiveFormat.SEVEN_ZIP

        # Get writer and create archive
        self._current_writer = get_archive_writer(output, options, self._progress_callback)
        return self._current_writer.create(sources)

    def cancel(self) -> None:
        """Cancel archive creation."""
        if self._current_writer:
            self._current_writer.cancel()

    def pause(self) -> None:
        """Pause archive creation."""
        if self._current_writer:
            self._current_writer.pause()

    def resume(self) -> None:
        """Resume archive creation."""
        if self._current_writer:
            self._current_writer.resume()

    def add_files(
        self,
        archive: Path,
        files: list[Path],
        options: CompressionOptions | None = None,
    ) -> CompressionResult:
        """Add files to existing archive.

        Args:
            archive: Path to existing archive.
            files: Files to add.
            options: Compression options.

        Returns:
            CompressionResult with operation details.
        """
        options = options or CompressionOptions()

        if not archive.exists():
            return CompressionResult(
                success=False,
                output_path=archive,
                error_message=f"Archive not found: {archive}",
            )

        # Currently only ZIP supports adding files
        if options.format != ArchiveFormat.ZIP:
            return CompressionResult(
                success=False,
                output_path=archive,
                error_message="Adding files only supported for ZIP archives",
            )

        original_size = 0
        files_added = 0
        start_time = time.monotonic()

        try:
            with zipfile.ZipFile(archive, "a") as zf:
                for file_path in files:
                    if not file_path.exists():
                        logger.warning("File not found: %s", file_path)
                        continue

                    file_size = file_path.stat().st_size
                    original_size += file_size

                    zf.write(file_path, file_path.name)
                    files_added += 1

                    if self._progress_callback:
                        self._progress_callback(file_path.name, original_size, original_size)

            elapsed = time.monotonic() - start_time
            compressed_size = archive.stat().st_size

            return CompressionResult(
                success=True,
                output_path=archive,
                original_size=original_size,
                compressed_size=compressed_size,
                file_count=files_added,
                elapsed_seconds=elapsed,
            )

        except Exception as e:
            logger.exception("Failed to add files to archive: %s", e)
            return CompressionResult(
                success=False,
                output_path=archive,
                error_message=str(e),
            )

    def delete_files(
        self,
        archive: Path,
        entries: list[str],
    ) -> CompressionResult:
        """Delete files from archive.

        Args:
            archive: Path to archive.
            entries: Archive paths to delete.

        Returns:
            CompressionResult with operation details.

        Note:
            This creates a new archive without the specified entries.
        """
        if not archive.exists():
            return CompressionResult(
                success=False,
                output_path=archive,
                error_message=f"Archive not found: {archive}",
            )

        start_time = time.monotonic()
        entries_set = set(entries)

        # Create temporary archive without specified entries
        temp_archive = archive.with_suffix(archive.suffix + ".tmp")

        try:
            with (
                zipfile.ZipFile(archive, "r") as zf_in,
                zipfile.ZipFile(temp_archive, "w") as zf_out,
            ):
                for item in zf_in.infolist():
                    if item.filename not in entries_set:
                        data = zf_in.read(item.filename)
                        zf_out.writestr(item, data)

            # Replace original with new archive
            temp_archive.replace(archive)

            elapsed = time.monotonic() - start_time

            return CompressionResult(
                success=True,
                output_path=archive,
                file_count=len(entries),
                elapsed_seconds=elapsed,
            )

        except Exception as e:
            logger.exception("Failed to delete files from archive: %s", e)
            if temp_archive.exists():
                temp_archive.unlink()
            return CompressionResult(
                success=False,
                output_path=archive,
                error_message=str(e),
            )
