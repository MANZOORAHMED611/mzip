"""RAR archive handler.

This module provides read-only support for RAR archives using rarfile.
Note: RAR is a proprietary format - only extraction is supported.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import rarfile

from zipextractor.core.formats import FormatCapability
from zipextractor.core.handlers.base_handler import (
    ArchiveHandler,
    ArchiveInfo,
    ExtractionOptions,
)
from zipextractor.core.models import ArchiveFormat, FileInfo
from zipextractor.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Configure rarfile to use unrar if available
try:
    rarfile.UNRAR_TOOL = "unrar"
except AttributeError:
    pass


class RarHandler(ArchiveHandler):
    """Handler for RAR archives.

    Supports reading RAR and RAR5 archives.
    Writing is not supported due to proprietary format.
    """

    @property
    def format(self) -> ArchiveFormat:
        """Get the archive format."""
        return ArchiveFormat.RAR

    @property
    def capabilities(self) -> set[FormatCapability]:
        """Get supported capabilities."""
        return {FormatCapability.READ}

    def list_contents(self) -> list[FileInfo]:
        """List all files in the archive.

        Returns:
            List of FileInfo objects.
        """
        files: list[FileInfo] = []

        with rarfile.RarFile(str(self._path)) as rf:
            if self._password:
                rf.setpassword(self._password)

            for info in rf.infolist():
                files.append(
                    FileInfo(
                        name=info.filename,
                        size=info.file_size,
                        compressed_size=info.compress_size,
                        is_directory=info.is_dir(),
                        is_encrypted=info.needs_password(),
                        crc32=info.CRC or 0,
                        modified=info.mtime,
                    )
                )

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
        comment = ""

        with rarfile.RarFile(str(self._path)) as rf:
            if self._password:
                rf.setpassword(self._password)

            is_encrypted = rf.needs_password()
            comment = rf.comment or ""

            for info in rf.infolist():
                if not info.is_dir():
                    file_count += 1
                    total_size += info.file_size
                    compressed_size += info.compress_size

        return ArchiveInfo(
            path=self._path,
            format=ArchiveFormat.RAR,
            file_count=file_count,
            total_size=total_size,
            compressed_size=compressed_size or self._path.stat().st_size,
            is_encrypted=is_encrypted,
            comment=comment,
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

        with rarfile.RarFile(str(self._path)) as rf:
            if password:
                rf.setpassword(password)

            members = rf.infolist()
            total = len(members)

            for i, info in enumerate(members):
                rf.extract(info, path=str(options.output_path), pwd=password)
                if progress_callback:
                    progress_callback(info.filename, i + 1, total)

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

        with rarfile.RarFile(str(self._path)) as rf:
            if password:
                rf.setpassword(password)

            for i, name in enumerate(files):
                rf.extract(name, path=str(options.output_path), pwd=password)
                if progress_callback:
                    progress_callback(name, i + 1, len(files))

    def read_file(self, file_path: str) -> bytes:
        """Read a single file from archive without extracting.

        Args:
            file_path: Path to file within archive.

        Returns:
            File contents as bytes.
        """
        with rarfile.RarFile(str(self._path)) as rf:
            if self._password:
                rf.setpassword(self._password)
            return rf.read(file_path)

    def test(self) -> bool:
        """Test archive integrity.

        Returns:
            True if archive is valid.
        """
        try:
            with rarfile.RarFile(str(self._path)) as rf:
                if self._password:
                    rf.setpassword(self._password)
                return rf.testrar() is None
        except Exception as e:
            logger.warning("RAR test failed: %s", e)
            return False
