"""Single-file compression handlers.

This module provides support for single-file compression formats:
gzip, bzip2, xz/lzma, and zstandard.
"""

from __future__ import annotations

import bz2
import gzip
import lzma
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import zstandard

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


class GzipHandler(WritableHandler):
    """Handler for gzip compressed files."""

    @property
    def format(self) -> ArchiveFormat:
        """Get the archive format."""
        return ArchiveFormat.GZ

    @property
    def capabilities(self) -> set[FormatCapability]:
        """Get supported capabilities."""
        return {FormatCapability.READ, FormatCapability.WRITE}

    def _get_output_name(self) -> str:
        """Get the decompressed output filename."""
        name = self._path.name
        if name.endswith(".gz"):
            return name[:-3]
        if name.endswith(".gzip"):
            return name[:-5]
        return name + ".out"

    def list_contents(self) -> list[FileInfo]:
        """List the single compressed file."""
        output_name = self._get_output_name()
        # Try to get uncompressed size from gzip trailer
        uncompressed_size = 0
        try:
            with gzip.open(self._path, "rb") as f:
                f.seek(0, 2)  # Seek to end
                # Size is in last 4 bytes of gzip file
                self._path.open("rb").seek(-4, 2)
        except Exception:
            pass

        return [
            FileInfo(
                name=output_name,
                size=uncompressed_size,
                compressed_size=self._path.stat().st_size,
                is_directory=False,
            )
        ]

    def get_info(self) -> ArchiveInfo:
        """Get archive information."""
        return ArchiveInfo(
            path=self._path,
            format=ArchiveFormat.GZ,
            file_count=1,
            total_size=0,
            compressed_size=self._path.stat().st_size,
        )

    def extract_all(
        self,
        options: ExtractionOptions,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Decompress the file."""
        output_name = self._get_output_name()
        output_path = options.output_path / output_name

        with gzip.open(self._path, "rb") as f_in:
            with output_path.open("wb") as f_out:
                chunk_size = 64 * 1024
                while True:
                    chunk = f_in.read(chunk_size)
                    if not chunk:
                        break
                    f_out.write(chunk)

        if progress_callback:
            progress_callback(output_name, 1, 1)

    def extract_files(
        self,
        files: list[str],
        options: ExtractionOptions,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Extract (decompress) the file."""
        self.extract_all(options, progress_callback)

    def read_file(self, file_path: str) -> bytes:
        """Read decompressed content."""
        with gzip.open(self._path, "rb") as f:
            return f.read()

    def create(
        self,
        files: list[Path],
        options: CreationOptions,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Compress a file."""
        if len(files) != 1:
            msg = "Gzip can only compress a single file"
            raise ValueError(msg)

        with files[0].open("rb") as f_in:
            with gzip.open(
                self._path, "wb", compresslevel=options.compression_level
            ) as f_out:
                chunk_size = 64 * 1024
                while True:
                    chunk = f_in.read(chunk_size)
                    if not chunk:
                        break
                    f_out.write(chunk)

        if progress_callback:
            progress_callback(files[0].name, 1, 1)

    def add_files(
        self,
        files: list[Path],
        base_path: Path | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Not supported for single-file compression."""
        msg = "Cannot add files to gzip archive"
        raise NotImplementedError(msg)


class Bzip2Handler(WritableHandler):
    """Handler for bzip2 compressed files."""

    @property
    def format(self) -> ArchiveFormat:
        """Get the archive format."""
        return ArchiveFormat.BZ2

    @property
    def capabilities(self) -> set[FormatCapability]:
        """Get supported capabilities."""
        return {FormatCapability.READ, FormatCapability.WRITE}

    def _get_output_name(self) -> str:
        """Get the decompressed output filename."""
        name = self._path.name
        if name.endswith(".bz2"):
            return name[:-4]
        if name.endswith(".bzip2"):
            return name[:-6]
        return name + ".out"

    def list_contents(self) -> list[FileInfo]:
        """List the single compressed file."""
        return [
            FileInfo(
                name=self._get_output_name(),
                size=0,
                compressed_size=self._path.stat().st_size,
                is_directory=False,
            )
        ]

    def get_info(self) -> ArchiveInfo:
        """Get archive information."""
        return ArchiveInfo(
            path=self._path,
            format=ArchiveFormat.BZ2,
            file_count=1,
            total_size=0,
            compressed_size=self._path.stat().st_size,
        )

    def extract_all(
        self,
        options: ExtractionOptions,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Decompress the file."""
        output_name = self._get_output_name()
        output_path = options.output_path / output_name

        with bz2.open(self._path, "rb") as f_in:
            with output_path.open("wb") as f_out:
                chunk_size = 64 * 1024
                while True:
                    chunk = f_in.read(chunk_size)
                    if not chunk:
                        break
                    f_out.write(chunk)

        if progress_callback:
            progress_callback(output_name, 1, 1)

    def extract_files(
        self,
        files: list[str],
        options: ExtractionOptions,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Extract (decompress) the file."""
        self.extract_all(options, progress_callback)

    def read_file(self, file_path: str) -> bytes:
        """Read decompressed content."""
        with bz2.open(self._path, "rb") as f:
            return f.read()

    def create(
        self,
        files: list[Path],
        options: CreationOptions,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Compress a file."""
        if len(files) != 1:
            msg = "Bzip2 can only compress a single file"
            raise ValueError(msg)

        with files[0].open("rb") as f_in:
            with bz2.open(
                self._path, "wb", compresslevel=options.compression_level
            ) as f_out:
                chunk_size = 64 * 1024
                while True:
                    chunk = f_in.read(chunk_size)
                    if not chunk:
                        break
                    f_out.write(chunk)

        if progress_callback:
            progress_callback(files[0].name, 1, 1)

    def add_files(
        self,
        files: list[Path],
        base_path: Path | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Not supported for single-file compression."""
        msg = "Cannot add files to bzip2 archive"
        raise NotImplementedError(msg)


class XzHandler(WritableHandler):
    """Handler for xz/lzma compressed files."""

    @property
    def format(self) -> ArchiveFormat:
        """Get the archive format."""
        return ArchiveFormat.XZ

    @property
    def capabilities(self) -> set[FormatCapability]:
        """Get supported capabilities."""
        return {FormatCapability.READ, FormatCapability.WRITE}

    def _get_output_name(self) -> str:
        """Get the decompressed output filename."""
        name = self._path.name
        if name.endswith(".xz"):
            return name[:-3]
        if name.endswith(".lzma"):
            return name[:-5]
        return name + ".out"

    def list_contents(self) -> list[FileInfo]:
        """List the single compressed file."""
        return [
            FileInfo(
                name=self._get_output_name(),
                size=0,
                compressed_size=self._path.stat().st_size,
                is_directory=False,
            )
        ]

    def get_info(self) -> ArchiveInfo:
        """Get archive information."""
        return ArchiveInfo(
            path=self._path,
            format=ArchiveFormat.XZ,
            file_count=1,
            total_size=0,
            compressed_size=self._path.stat().st_size,
        )

    def extract_all(
        self,
        options: ExtractionOptions,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Decompress the file."""
        output_name = self._get_output_name()
        output_path = options.output_path / output_name

        with lzma.open(self._path, "rb") as f_in:
            with output_path.open("wb") as f_out:
                chunk_size = 64 * 1024
                while True:
                    chunk = f_in.read(chunk_size)
                    if not chunk:
                        break
                    f_out.write(chunk)

        if progress_callback:
            progress_callback(output_name, 1, 1)

    def extract_files(
        self,
        files: list[str],
        options: ExtractionOptions,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Extract (decompress) the file."""
        self.extract_all(options, progress_callback)

    def read_file(self, file_path: str) -> bytes:
        """Read decompressed content."""
        with lzma.open(self._path, "rb") as f:
            return f.read()

    def create(
        self,
        files: list[Path],
        options: CreationOptions,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Compress a file."""
        if len(files) != 1:
            msg = "XZ can only compress a single file"
            raise ValueError(msg)

        with files[0].open("rb") as f_in:
            with lzma.open(
                self._path, "wb", preset=options.compression_level
            ) as f_out:
                chunk_size = 64 * 1024
                while True:
                    chunk = f_in.read(chunk_size)
                    if not chunk:
                        break
                    f_out.write(chunk)

        if progress_callback:
            progress_callback(files[0].name, 1, 1)

    def add_files(
        self,
        files: list[Path],
        base_path: Path | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Not supported for single-file compression."""
        msg = "Cannot add files to xz archive"
        raise NotImplementedError(msg)


class ZstdHandler(WritableHandler):
    """Handler for Zstandard compressed files."""

    @property
    def format(self) -> ArchiveFormat:
        """Get the archive format."""
        return ArchiveFormat.ZSTD

    @property
    def capabilities(self) -> set[FormatCapability]:
        """Get supported capabilities."""
        return {FormatCapability.READ, FormatCapability.WRITE}

    def _get_output_name(self) -> str:
        """Get the decompressed output filename."""
        name = self._path.name
        if name.endswith(".zst"):
            return name[:-4]
        if name.endswith(".zstd"):
            return name[:-5]
        return name + ".out"

    def list_contents(self) -> list[FileInfo]:
        """List the single compressed file."""
        return [
            FileInfo(
                name=self._get_output_name(),
                size=0,
                compressed_size=self._path.stat().st_size,
                is_directory=False,
            )
        ]

    def get_info(self) -> ArchiveInfo:
        """Get archive information."""
        return ArchiveInfo(
            path=self._path,
            format=ArchiveFormat.ZSTD,
            file_count=1,
            total_size=0,
            compressed_size=self._path.stat().st_size,
        )

    def extract_all(
        self,
        options: ExtractionOptions,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Decompress the file."""
        output_name = self._get_output_name()
        output_path = options.output_path / output_name

        dctx = zstandard.ZstdDecompressor()

        with self._path.open("rb") as f_in:
            with output_path.open("wb") as f_out:
                dctx.copy_stream(f_in, f_out)

        if progress_callback:
            progress_callback(output_name, 1, 1)

    def extract_files(
        self,
        files: list[str],
        options: ExtractionOptions,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Extract (decompress) the file."""
        self.extract_all(options, progress_callback)

    def read_file(self, file_path: str) -> bytes:
        """Read decompressed content."""
        dctx = zstandard.ZstdDecompressor()
        with self._path.open("rb") as f:
            return dctx.decompress(f.read())

    def create(
        self,
        files: list[Path],
        options: CreationOptions,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Compress a file."""
        if len(files) != 1:
            msg = "Zstd can only compress a single file"
            raise ValueError(msg)

        cctx = zstandard.ZstdCompressor(level=options.compression_level)

        with files[0].open("rb") as f_in:
            with self._path.open("wb") as f_out:
                cctx.copy_stream(f_in, f_out)

        if progress_callback:
            progress_callback(files[0].name, 1, 1)

    def add_files(
        self,
        files: list[Path],
        base_path: Path | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Not supported for single-file compression."""
        msg = "Cannot add files to zstd archive"
        raise NotImplementedError(msg)
