"""ZIP format handler.

Provides native ZIP archive handling using Python's zipfile module.
"""

from __future__ import annotations

import os
import zipfile
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


class ZipHandler(WritableHandler):
    """Handler for ZIP archives.

    Supports ZIP, JAR, WAR, APK, EPUB, DOCX, XLSX formats.
    """

    COMPRESSION_METHODS: ClassVar[dict[str, int]] = {
        "store": zipfile.ZIP_STORED,
        "stored": zipfile.ZIP_STORED,
        "deflate": zipfile.ZIP_DEFLATED,
        "deflated": zipfile.ZIP_DEFLATED,
        "bzip2": zipfile.ZIP_BZIP2,
        "lzma": zipfile.ZIP_LZMA,
    }

    @property
    def format(self) -> ArchiveFormat:
        """Get archive format."""
        return ArchiveFormat.ZIP

    @property
    def capabilities(self) -> set[FormatCapability]:
        """Get supported capabilities."""
        return {
            FormatCapability.READ,
            FormatCapability.WRITE,
            FormatCapability.APPEND,
            FormatCapability.DELETE,
            FormatCapability.UPDATE,
            FormatCapability.ENCRYPT,
        }

    def list_contents(self) -> list[FileInfo]:
        """List all files in the ZIP archive.

        Returns:
            List of FileInfo objects.
        """
        files: list[FileInfo] = []
        try:
            with zipfile.ZipFile(self._path, "r") as zf:
                for info in zf.infolist():
                    # Skip directories
                    if info.is_dir():
                        continue

                    # Convert date_time tuple to datetime
                    try:
                        modified = datetime(*info.date_time)
                    except (ValueError, TypeError):
                        modified = None

                    files.append(
                        FileInfo(
                            name=info.filename,
                            size=info.file_size,
                            compressed_size=info.compress_size,
                            is_directory=False,
                            modified=modified,
                            crc32=info.CRC,
                            compression_method=self._get_compression_name(
                                info.compress_type
                            ),
                            is_encrypted=info.flag_bits & 0x1 != 0,
                        )
                    )
        except zipfile.BadZipFile as e:
            logger.error("Invalid ZIP file: %s", e)
            raise

        return files

    def _get_compression_name(self, method: int) -> str:
        """Get compression method name from zipfile constant."""
        names = {
            zipfile.ZIP_STORED: "store",
            zipfile.ZIP_DEFLATED: "deflate",
            zipfile.ZIP_BZIP2: "bzip2",
            zipfile.ZIP_LZMA: "lzma",
        }
        return names.get(method, "unknown")

    def get_info(self) -> ArchiveInfo:
        """Get archive information.

        Returns:
            ArchiveInfo with archive details.
        """
        file_count = 0
        total_size = 0
        compressed_size = 0
        is_encrypted = False
        comment = ""

        try:
            with zipfile.ZipFile(self._path, "r") as zf:
                comment = zf.comment.decode("utf-8", errors="replace") if zf.comment else ""
                for info in zf.infolist():
                    if not info.is_dir():
                        file_count += 1
                        total_size += info.file_size
                        compressed_size += info.compress_size
                        if info.flag_bits & 0x1:
                            is_encrypted = True
        except zipfile.BadZipFile as e:
            logger.error("Invalid ZIP file: %s", e)
            raise

        return ArchiveInfo(
            path=self._path,
            format=self.format,
            file_count=file_count,
            total_size=total_size,
            compressed_size=compressed_size,
            is_encrypted=is_encrypted,
            comment=comment,
        )

    def extract_all(
        self,
        options: ExtractionOptions,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Extract all files from the ZIP archive.

        Args:
            options: Extraction options.
            progress_callback: Optional callback(filename, current, total).
        """
        options.output_path.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(self._path, "r") as zf:
                members = [m for m in zf.infolist() if not m.is_dir()]
                total = len(members)

                for i, member in enumerate(members):
                    if progress_callback:
                        progress_callback(member.filename, i, total)

                    # Extract with password if needed
                    pwd = self._password.encode() if self._password else None
                    target = options.output_path / member.filename

                    # Ensure parent directory exists
                    target.parent.mkdir(parents=True, exist_ok=True)

                    # Check overwrite
                    if target.exists() and not options.overwrite:
                        logger.debug("Skipping existing file: %s", target)
                        continue

                    # Extract
                    with zf.open(member, pwd=pwd) as src, target.open("wb") as dst:
                        dst.write(src.read())

                    # Preserve timestamps
                    if options.preserve_timestamps:
                        try:
                            mtime = datetime(*member.date_time).timestamp()
                            os.utime(target, (mtime, mtime))
                        except (ValueError, OSError):
                            pass

                    # Preserve permissions (Unix)
                    if options.preserve_permissions and member.external_attr >> 16:
                        try:
                            mode = member.external_attr >> 16
                            if mode:
                                target.chmod(mode)
                        except OSError:
                            pass

                if progress_callback:
                    progress_callback("", total, total)

        except zipfile.BadZipFile as e:
            logger.error("Invalid ZIP file: %s", e)
            raise

    def extract_files(
        self,
        files: list[str],
        options: ExtractionOptions,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Extract specific files from the ZIP archive.

        Args:
            files: List of file paths within archive.
            options: Extraction options.
            progress_callback: Optional callback(filename, current, total).
        """
        options.output_path.mkdir(parents=True, exist_ok=True)
        files_set = set(files)

        try:
            with zipfile.ZipFile(self._path, "r") as zf:
                members = [m for m in zf.infolist() if m.filename in files_set]
                total = len(members)

                for i, member in enumerate(members):
                    if progress_callback:
                        progress_callback(member.filename, i, total)

                    pwd = self._password.encode() if self._password else None
                    target = options.output_path / member.filename
                    target.parent.mkdir(parents=True, exist_ok=True)

                    if target.exists() and not options.overwrite:
                        continue

                    with zf.open(member, pwd=pwd) as src, target.open("wb") as dst:
                        dst.write(src.read())

                if progress_callback:
                    progress_callback("", total, total)

        except zipfile.BadZipFile as e:
            logger.error("Invalid ZIP file: %s", e)
            raise

    def read_file(self, file_path: str) -> bytes:
        """Read a single file from archive.

        Args:
            file_path: Path to file within archive.

        Returns:
            File contents as bytes.
        """
        try:
            with zipfile.ZipFile(self._path, "r") as zf:
                pwd = self._password.encode() if self._password else None
                return zf.read(file_path, pwd=pwd)
        except zipfile.BadZipFile as e:
            logger.error("Invalid ZIP file: %s", e)
            raise
        except KeyError as e:
            msg = f"File not found in archive: {file_path}"
            raise FileNotFoundError(msg) from e

    def test(self) -> bool:
        """Test ZIP archive integrity.

        Returns:
            True if archive is valid.
        """
        try:
            with zipfile.ZipFile(self._path, "r") as zf:
                bad_file = zf.testzip()
                if bad_file:
                    logger.warning("Corrupt file in archive: %s", bad_file)
                    return False
                return True
        except zipfile.BadZipFile as e:
            logger.warning("Invalid ZIP file: %s", e)
            return False

    def create(
        self,
        files: list[Path],
        options: CreationOptions,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Create a new ZIP archive.

        Args:
            files: Files and directories to add.
            options: Creation options.
            progress_callback: Optional callback(filename, current, total).
        """
        compression = self.COMPRESSION_METHODS.get(
            options.compression_method.lower(), zipfile.ZIP_DEFLATED
        )

        # Collect all files
        all_files = self._collect_files(files)
        total = len(all_files)

        try:
            with zipfile.ZipFile(
                self._path,
                "w",
                compression=compression,
                compresslevel=options.compression_level,
            ) as zf:
                for i, (src, arcname) in enumerate(all_files):
                    if progress_callback:
                        progress_callback(arcname, i, total)

                    zf.write(src, arcname)

                if progress_callback:
                    progress_callback("", total, total)

        except OSError as e:
            logger.error("Failed to create archive: %s", e)
            raise

    def add_files(
        self,
        files: list[Path],
        base_path: Path | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Add files to existing ZIP archive.

        Args:
            files: Files and directories to add.
            base_path: Base path for relative paths in archive.
            progress_callback: Optional callback(filename, current, total).
        """
        all_files = self._collect_files(files, base_path)
        total = len(all_files)

        try:
            with zipfile.ZipFile(self._path, "a") as zf:
                for i, (src, arcname) in enumerate(all_files):
                    if progress_callback:
                        progress_callback(arcname, i, total)

                    zf.write(src, arcname)

                if progress_callback:
                    progress_callback("", total, total)

        except OSError as e:
            logger.error("Failed to add files: %s", e)
            raise

    def delete_files(self, files: list[str]) -> None:
        """Delete files from ZIP archive.

        Creates a new archive without the specified files.

        Args:
            files: List of file paths within archive to delete.
        """
        import shutil  # noqa: PLC0415
        import tempfile  # noqa: PLC0415

        files_set = set(files)

        try:
            # Create temp archive without deleted files
            with tempfile.NamedTemporaryFile(
                suffix=".zip", delete=False
            ) as tmp:
                tmp_path = Path(tmp.name)

            with (
                zipfile.ZipFile(self._path, "r") as src_zf,
                zipfile.ZipFile(tmp_path, "w") as dst_zf,
            ):
                for item in src_zf.infolist():
                    if item.filename not in files_set:
                        data = src_zf.read(item.filename)
                        dst_zf.writestr(item, data)

            # Replace original with new archive
            shutil.move(str(tmp_path), str(self._path))

        except OSError as e:
            logger.error("Failed to delete files: %s", e)
            if tmp_path.exists():
                tmp_path.unlink()
            raise

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


# Register handler for ZIP and ZIP-based formats
register_handler(ArchiveFormat.ZIP, ZipHandler)
register_handler(ArchiveFormat.JAR, ZipHandler)
register_handler(ArchiveFormat.WAR, ZipHandler)
register_handler(ArchiveFormat.APK, ZipHandler)
register_handler(ArchiveFormat.EPUB, ZipHandler)
register_handler(ArchiveFormat.DOCX, ZipHandler)
register_handler(ArchiveFormat.XLSX, ZipHandler)
