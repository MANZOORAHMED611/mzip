"""7-Zip archive handler.

This module provides read and write support for 7z archives using py7zr.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import py7zr

from zipextractor.core.formats import FormatCapability
from zipextractor.core.handlers.base_handler import (
    ArchiveInfo,
    CreationOptions,
    ExtractionOptions,
    WritableHandler,
)
from zipextractor.core.models import ArchiveFormat, FileInfo
from zipextractor.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class SevenZipHandler(WritableHandler):
    """Handler for 7-Zip archives.

    Supports reading and writing 7z archives with LZMA2 compression.
    Also supports encrypted archives with AES-256.
    """

    @property
    def format(self) -> ArchiveFormat:
        """Get the archive format."""
        return ArchiveFormat.SEVEN_ZIP

    @property
    def capabilities(self) -> set[FormatCapability]:
        """Get supported capabilities."""
        return {
            FormatCapability.READ,
            FormatCapability.WRITE,
            FormatCapability.ENCRYPT,
        }

    def list_contents(self) -> list[FileInfo]:
        """List all files in the archive.

        Returns:
            List of FileInfo objects.
        """
        files: list[FileInfo] = []

        try:
            with py7zr.SevenZipFile(self._path, mode="r", password=self._password) as archive:
                is_encrypted = archive.needs_password()

                for item in archive.list():
                    files.append(
                        FileInfo(
                            name=item.filename,
                            size=item.uncompressed or 0,
                            compressed_size=item.compressed or 0,
                            is_directory=item.is_directory,
                            is_encrypted=is_encrypted,
                            crc32=item.crc32,
                            created=item.creationtime,
                        )
                    )
        except Exception as e:
            logger.error("Failed to list 7z contents: %s", e)
            raise

        return files

    def get_info(self) -> ArchiveInfo:
        """Get archive information.

        Returns:
            ArchiveInfo with archive details.
        """
        file_count = 0
        total_size = 0
        compressed_size = 0
        is_encrypted = False

        try:
            with py7zr.SevenZipFile(self._path, mode="r", password=self._password) as archive:
                is_encrypted = archive.needs_password()
                for info in archive.list():
                    if not info.is_directory:
                        file_count += 1
                        total_size += info.uncompressed or 0
                        compressed_size += info.compressed or 0
        except Exception as e:
            logger.warning("Failed to get 7z info: %s", e)

        return ArchiveInfo(
            path=self._path,
            format=ArchiveFormat.SEVEN_ZIP,
            file_count=file_count,
            total_size=total_size,
            compressed_size=compressed_size or self._path.stat().st_size,
            is_encrypted=is_encrypted,
        )

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
        password = options.password or self._password

        with py7zr.SevenZipFile(self._path, mode="r", password=password) as archive:
            archive.extractall(path=options.output_path)

            if progress_callback:
                files = archive.getnames()
                for i, name in enumerate(files):
                    progress_callback(name, i + 1, len(files))

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
        password = options.password or self._password

        with py7zr.SevenZipFile(self._path, mode="r", password=password) as archive:
            archive.extract(path=options.output_path, targets=files)

            if progress_callback:
                for i, name in enumerate(files):
                    progress_callback(name, i + 1, len(files))

    def read_file(self, file_path: str) -> bytes:
        """Read a single file from archive without extracting.

        Args:
            file_path: Path to file within archive.

        Returns:
            File contents as bytes.
        """
        with py7zr.SevenZipFile(self._path, mode="r", password=self._password) as archive:
            data = archive.read([file_path])
            if file_path in data:
                bio = data[file_path]
                return bio.read()
            msg = f"File not found in archive: {file_path}"
            raise FileNotFoundError(msg)

    def test(self) -> bool:
        """Test archive integrity.

        Returns:
            True if archive is valid.
        """
        try:
            with py7zr.SevenZipFile(self._path, mode="r", password=self._password) as archive:
                return archive.testzip() is None
        except Exception as e:
            logger.warning("7z test failed: %s", e)
            return False

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
        # Collect all files to add
        all_files: list[Path] = []
        for path in files:
            if path.is_dir():
                for root, _dirs, filenames in os.walk(path):
                    for filename in filenames:
                        all_files.append(Path(root) / filename)
            else:
                all_files.append(path)

        with py7zr.SevenZipFile(self._path, mode="w", password=options.password) as archive:
            for i, file_path in enumerate(all_files):
                archive.write(file_path, arcname=file_path.name)
                if progress_callback:
                    progress_callback(file_path.name, i + 1, len(all_files))

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
        with py7zr.SevenZipFile(self._path, mode="a") as archive:
            for i, file_path in enumerate(files):
                arcname = file_path.relative_to(base_path) if base_path else file_path.name
                archive.write(file_path, arcname=str(arcname))
                if progress_callback:
                    progress_callback(str(arcname), i + 1, len(files))
