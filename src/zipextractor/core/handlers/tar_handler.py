"""TAR format handler.

Provides handling for TAR archives and compressed variants (tar.gz, tar.bz2, etc.).
"""

from __future__ import annotations

import contextlib
import os
import tarfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import ClassVar

from zipextractor.core.formats import FormatCapability
from zipextractor.core.handlers.base_handler import (
    ArchiveInfo,
    CreationOptions,
    ExtractionOptions,
    WritableHandler,
    register_handler,
)
from zipextractor.core.models import ArchiveFormat, FileInfo
from zipextractor.utils.logging import get_logger

logger = get_logger(__name__)


class TarHandler(WritableHandler):
    """Handler for TAR archives and compressed variants.

    Supports TAR, TAR.GZ, TAR.BZ2, TAR.XZ, and TAR.ZSTD.
    """

    FORMAT_MODES: ClassVar[dict[ArchiveFormat, str]] = {
        ArchiveFormat.TAR: "",
        ArchiveFormat.TAR_GZ: ":gz",
        ArchiveFormat.TAR_BZ2: ":bz2",
        ArchiveFormat.TAR_XZ: ":xz",
    }

    def __init__(self, path: Path, archive_format: ArchiveFormat | None = None) -> None:
        """Initialize TAR handler.

        Args:
            path: Path to the archive file.
            archive_format: Specific TAR variant (auto-detected if None).
        """
        super().__init__(path)
        self._archive_format = archive_format or self._detect_variant()

    def _detect_variant(self) -> ArchiveFormat:  # noqa: PLR0911
        """Detect TAR variant from extension or content."""
        name = self._path.name.lower()

        if name.endswith((".tar.gz", ".tgz")):
            return ArchiveFormat.TAR_GZ
        if name.endswith((".tar.bz2", ".tbz2", ".tbz")):
            return ArchiveFormat.TAR_BZ2
        if name.endswith((".tar.xz", ".txz")):
            return ArchiveFormat.TAR_XZ
        if name.endswith((".tar.zst", ".tzst")):
            return ArchiveFormat.TAR_ZSTD

        # Check magic bytes
        try:
            with self._path.open("rb") as f:
                header = f.read(6)
                if header.startswith(b"\x1f\x8b"):
                    return ArchiveFormat.TAR_GZ
                if header.startswith(b"BZ"):
                    return ArchiveFormat.TAR_BZ2
                if header.startswith(b"\xfd7zXZ"):
                    return ArchiveFormat.TAR_XZ
                if header.startswith(b"\x28\xb5\x2f\xfd"):
                    return ArchiveFormat.TAR_ZSTD
        except OSError:
            pass

        return ArchiveFormat.TAR

    @property
    def format(self) -> ArchiveFormat:
        """Get archive format."""
        return self._archive_format

    @property
    def capabilities(self) -> set[FormatCapability]:
        """Get supported capabilities."""
        caps = {FormatCapability.READ, FormatCapability.WRITE}
        if self._archive_format == ArchiveFormat.TAR:
            caps.add(FormatCapability.APPEND)
        return caps

    def _get_open_mode(self, write: bool = False) -> str:
        """Get tarfile open mode string."""
        mode = "w" if write else "r"

        if self._archive_format == ArchiveFormat.TAR:
            return mode
        if self._archive_format == ArchiveFormat.TAR_GZ:
            return f"{mode}:gz"
        if self._archive_format == ArchiveFormat.TAR_BZ2:
            return f"{mode}:bz2"
        if self._archive_format == ArchiveFormat.TAR_XZ:
            return f"{mode}:xz"
        if self._archive_format == ArchiveFormat.TAR_ZSTD:
            # ZSTD requires special handling
            return mode

        return mode

    def _open_archive(self, mode: str = "r") -> tarfile.TarFile:
        """Open the archive with appropriate compression.

        Args:
            mode: Open mode ('r', 'w', 'a').

        Returns:
            Open TarFile object.
        """
        if self._archive_format == ArchiveFormat.TAR_ZSTD:
            return self._open_zstd_archive(mode)

        full_mode = self._get_open_mode(write="w" in mode or "a" in mode)
        if "a" in mode:
            # Append only works for plain tar
            full_mode = "a"

        return tarfile.open(str(self._path), full_mode)  # type: ignore[call-overload, no-any-return]

    def _open_zstd_archive(self, mode: str) -> tarfile.TarFile:
        """Open ZSTD compressed TAR archive.

        Args:
            mode: Open mode.

        Returns:
            TarFile wrapping ZSTD stream.
        """
        try:
            import zstandard as zstd  # noqa: PLC0415
        except ImportError as e:
            msg = "zstandard library required for .tar.zst files"
            raise ImportError(msg) from e

        if "w" in mode:
            # Writing ZSTD compressed tar
            self._zstd_file_w = self._path.open("wb")
            self._zstd_compressor = zstd.ZstdCompressor(level=3)
            self._zstd_writer = self._zstd_compressor.stream_writer(self._zstd_file_w)
            return tarfile.open(mode="w|", fileobj=self._zstd_writer)
        else:
            # Reading ZSTD compressed tar
            self._zstd_file_r = self._path.open("rb")
            dctx = zstd.ZstdDecompressor()
            self._zstd_reader = dctx.stream_reader(self._zstd_file_r)
            return tarfile.open(mode="r|", fileobj=self._zstd_reader)

    def list_contents(self) -> list[FileInfo]:
        """List all files in the TAR archive.

        Returns:
            List of FileInfo objects.
        """
        files: list[FileInfo] = []

        try:
            with self._open_archive("r") as tf:
                for member in tf.getmembers():
                    if member.isdir():
                        continue

                    modified = None
                    if member.mtime:
                        with contextlib.suppress(ValueError, OSError):
                            modified = datetime.fromtimestamp(member.mtime)

                    files.append(
                        FileInfo(
                            name=member.name,
                            size=member.size,
                            compressed_size=member.size,  # TAR doesn't store compressed size
                            is_directory=False,
                            modified=modified,
                            permissions=member.mode,
                        )
                    )
        except tarfile.TarError as e:
            logger.error("Invalid TAR file: %s", e)
            raise

        return files

    def get_info(self) -> ArchiveInfo:
        """Get archive information.

        Returns:
            ArchiveInfo with archive details.
        """
        file_count = 0
        total_size = 0

        try:
            with self._open_archive("r") as tf:
                for member in tf.getmembers():
                    if not member.isdir():
                        file_count += 1
                        total_size += member.size
        except tarfile.TarError as e:
            logger.error("Invalid TAR file: %s", e)
            raise

        # Get compressed size from file
        compressed_size = self._path.stat().st_size if self._path.exists() else 0

        return ArchiveInfo(
            path=self._path,
            format=self._archive_format,
            file_count=file_count,
            total_size=total_size,
            compressed_size=compressed_size,
        )

    def extract_all(
        self,
        options: ExtractionOptions,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Extract all files from the TAR archive.

        Args:
            options: Extraction options.
            progress_callback: Optional callback(filename, current, total).
        """
        options.output_path.mkdir(parents=True, exist_ok=True)

        try:
            with self._open_archive("r") as tf:
                members = [m for m in tf.getmembers() if not m.isdir()]
                total = len(members)

                for i, member in enumerate(members):
                    if progress_callback:
                        progress_callback(member.name, i, total)

                    # Validate path (security)
                    target = options.output_path / member.name
                    if not self._is_safe_path(options.output_path, target):
                        logger.warning("Skipping unsafe path: %s", member.name)
                        continue

                    # Check overwrite
                    if target.exists() and not options.overwrite:
                        logger.debug("Skipping existing file: %s", target)
                        continue

                    # Ensure parent directory exists
                    target.parent.mkdir(parents=True, exist_ok=True)

                    # Extract file
                    if member.isfile():
                        extracted = tf.extractfile(member)
                        if extracted:
                            with target.open("wb") as f:
                                f.write(extracted.read())

                            # Preserve timestamps
                            if options.preserve_timestamps and member.mtime:
                                with contextlib.suppress(OSError):
                                    os.utime(target, (member.mtime, member.mtime))

                            # Preserve permissions
                            if options.preserve_permissions and member.mode:
                                with contextlib.suppress(OSError):
                                    target.chmod(member.mode)

                if progress_callback:
                    progress_callback("", total, total)

        except tarfile.TarError as e:
            logger.error("Failed to extract: %s", e)
            raise

    def extract_files(
        self,
        files: list[str],
        options: ExtractionOptions,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Extract specific files from the TAR archive.

        Args:
            files: List of file paths within archive.
            options: Extraction options.
            progress_callback: Optional callback(filename, current, total).
        """
        options.output_path.mkdir(parents=True, exist_ok=True)
        files_set = set(files)

        try:
            with self._open_archive("r") as tf:
                members = [m for m in tf.getmembers() if m.name in files_set]
                total = len(members)

                for i, member in enumerate(members):
                    if progress_callback:
                        progress_callback(member.name, i, total)

                    target = options.output_path / member.name

                    if not self._is_safe_path(options.output_path, target):
                        continue

                    if target.exists() and not options.overwrite:
                        continue

                    target.parent.mkdir(parents=True, exist_ok=True)

                    if member.isfile():
                        extracted = tf.extractfile(member)
                        if extracted:
                            with target.open("wb") as f:
                                f.write(extracted.read())

                if progress_callback:
                    progress_callback("", total, total)

        except tarfile.TarError as e:
            logger.error("Failed to extract: %s", e)
            raise

    def read_file(self, file_path: str) -> bytes:
        """Read a single file from archive.

        Args:
            file_path: Path to file within archive.

        Returns:
            File contents as bytes.
        """
        try:
            with self._open_archive("r") as tf:
                member = tf.getmember(file_path)
                extracted = tf.extractfile(member)
                if extracted:
                    return extracted.read()
                msg = f"Cannot read file: {file_path}"
                raise ValueError(msg)
        except tarfile.TarError as e:
            logger.error("Failed to read file: %s", e)
            raise
        except KeyError as e:
            msg = f"File not found in archive: {file_path}"
            raise FileNotFoundError(msg) from e

    def create(
        self,
        files: list[Path],
        options: CreationOptions,  # noqa: ARG002
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Create a new TAR archive.

        Args:
            files: Files and directories to add.
            options: Creation options.
            progress_callback: Optional callback(filename, current, total).
        """
        all_files = self._collect_files(files)
        total = len(all_files)

        try:
            with self._open_archive("w") as tf:
                for i, (src, arcname) in enumerate(all_files):
                    if progress_callback:
                        progress_callback(arcname, i, total)

                    tf.add(str(src), arcname=arcname)

                if progress_callback:
                    progress_callback("", total, total)

            # Close ZSTD resources if used
            self._close_zstd_resources()

        except (tarfile.TarError, OSError) as e:
            logger.error("Failed to create archive: %s", e)
            raise

    def add_files(
        self,
        files: list[Path],
        base_path: Path | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Add files to existing TAR archive.

        Note: Append only works for uncompressed TAR files.

        Args:
            files: Files and directories to add.
            base_path: Base path for relative paths in archive.
            progress_callback: Optional callback(filename, current, total).
        """
        if self._archive_format != ArchiveFormat.TAR:
            msg = "Cannot append to compressed TAR archives"
            raise NotImplementedError(msg)

        all_files = self._collect_files(files, base_path)
        total = len(all_files)

        try:
            with tarfile.open(str(self._path), "a") as tf:
                for i, (src, arcname) in enumerate(all_files):
                    if progress_callback:
                        progress_callback(arcname, i, total)

                    tf.add(str(src), arcname=arcname)

                if progress_callback:
                    progress_callback("", total, total)

        except tarfile.TarError as e:
            logger.error("Failed to add files: %s", e)
            raise

    def _close_zstd_resources(self) -> None:
        """Close ZSTD compression resources if open."""
        if hasattr(self, "_zstd_writer") and self._zstd_writer:
            self._zstd_writer.close()  # type: ignore[no-untyped-call]
        if hasattr(self, "_zstd_reader") and self._zstd_reader:
            self._zstd_reader.close()  # type: ignore[no-untyped-call]
        if hasattr(self, "_zstd_file_w") and self._zstd_file_w:
            self._zstd_file_w.close()
        if hasattr(self, "_zstd_file_r") and self._zstd_file_r:
            self._zstd_file_r.close()

    def _is_safe_path(self, base: Path, target: Path) -> bool:
        """Check if target path is safe (within base directory).

        Args:
            base: Base extraction directory.
            target: Target file path.

        Returns:
            True if path is safe.
        """
        try:
            target.resolve().relative_to(base.resolve())
            return True
        except ValueError:
            return False

    def _collect_files(
        self, sources: list[Path], base_path: Path | None = None
    ) -> list[tuple[Path, str]]:
        """Collect all files from sources.

        Args:
            sources: List of files and directories.
            base_path: Base path for relative archive names.

        Returns:
            List of (source_path, archive_name) tuples.
        """
        result: list[tuple[Path, str]] = []

        for source in sources:
            if source.is_file():
                if base_path:
                    try:
                        arcname = str(source.relative_to(base_path))
                    except ValueError:
                        arcname = source.name
                else:
                    arcname = source.name
                result.append((source, arcname))
            elif source.is_dir():
                for root, _dirs, files in os.walk(source):
                    root_path = Path(root)
                    for fname in files:
                        file_path = root_path / fname
                        if base_path:
                            try:
                                arcname = str(file_path.relative_to(base_path))
                            except ValueError:
                                arcname = str(file_path.relative_to(source.parent))
                        else:
                            arcname = str(file_path.relative_to(source.parent))
                        result.append((file_path, arcname))

        return result


# Register handler for TAR formats
register_handler(ArchiveFormat.TAR, TarHandler)
register_handler(ArchiveFormat.TAR_GZ, TarHandler)
register_handler(ArchiveFormat.TAR_BZ2, TarHandler)
register_handler(ArchiveFormat.TAR_XZ, TarHandler)
register_handler(ArchiveFormat.TAR_ZSTD, TarHandler)
