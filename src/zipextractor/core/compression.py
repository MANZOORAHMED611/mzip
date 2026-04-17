"""Compression engine for archive creation.

This module provides compression algorithms and utilities for creating
compressed archives. Supports DEFLATE, LZMA, BZIP2, and ZSTD.
"""

from __future__ import annotations

import bz2
import gzip
import lzma
import os
import time
import zlib
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from zipextractor.core.models import (
    CompressionMethod,
    CompressionOptions,
)
from zipextractor.utils.logging import get_logger

logger = get_logger(__name__)

# Buffer size for streaming compression (256KB)
BUFFER_SIZE = 256 * 1024

# Try to import optional dependencies
try:
    import zstandard as zstd

    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False
    zstd = None  # type: ignore[assignment]


@dataclass
class CompressionStats:
    """Statistics from a compression operation."""

    input_size: int = 0
    output_size: int = 0
    elapsed_time: float = 0.0

    @property
    def ratio(self) -> float:
        """Compression ratio as percentage saved."""
        if self.input_size == 0:
            return 0.0
        return ((self.input_size - self.output_size) / self.input_size) * 100.0

    @property
    def speed_mbps(self) -> float:
        """Compression speed in MB/s."""
        if self.elapsed_time <= 0:
            return 0.0
        return (self.input_size / (1024 * 1024)) / self.elapsed_time


class Compressor(ABC):
    """Abstract base class for compression algorithms."""

    @property
    @abstractmethod
    def method(self) -> CompressionMethod:
        """Return the compression method this compressor implements."""

    @abstractmethod
    def compress(self, data: bytes) -> bytes:
        """Compress data in memory.

        Args:
            data: Raw bytes to compress.

        Returns:
            Compressed bytes.
        """

    @abstractmethod
    def decompress(self, data: bytes) -> bytes:
        """Decompress data in memory.

        Args:
            data: Compressed bytes.

        Returns:
            Decompressed bytes.
        """

    def compress_stream(
        self,
        input_stream: BinaryIO,
        output_stream: BinaryIO,
        progress_callback: Callable[[int], None] | None = None,
    ) -> CompressionStats:
        """Compress data from input stream to output stream.

        Args:
            input_stream: Source data stream.
            output_stream: Destination stream for compressed data.
            progress_callback: Optional callback with bytes processed.

        Returns:
            Compression statistics.
        """
        stats = CompressionStats()
        start_time = time.monotonic()

        while True:
            chunk = input_stream.read(BUFFER_SIZE)
            if not chunk:
                break
            stats.input_size += len(chunk)
            compressed = self.compress(chunk)
            stats.output_size += len(compressed)
            output_stream.write(compressed)
            if progress_callback:
                progress_callback(len(chunk))

        stats.elapsed_time = time.monotonic() - start_time
        return stats


class StoreCompressor(Compressor):
    """No compression (store only)."""

    @property
    def method(self) -> CompressionMethod:
        return CompressionMethod.STORE

    def compress(self, data: bytes) -> bytes:
        return data

    def decompress(self, data: bytes) -> bytes:
        return data


class DeflateCompressor(Compressor):
    """DEFLATE compression (ZIP default)."""

    def __init__(self, level: int = 6) -> None:
        """Initialize DEFLATE compressor.

        Args:
            level: Compression level (0-9).
        """
        self._level = max(0, min(9, level))

    @property
    def method(self) -> CompressionMethod:
        return CompressionMethod.DEFLATE

    def compress(self, data: bytes) -> bytes:
        return zlib.compress(data, self._level)

    def decompress(self, data: bytes) -> bytes:
        return zlib.decompress(data)

    def compress_stream(
        self,
        input_stream: BinaryIO,
        output_stream: BinaryIO,
        progress_callback: Callable[[int], None] | None = None,
    ) -> CompressionStats:
        """Compress using streaming DEFLATE."""
        stats = CompressionStats()
        start_time = time.monotonic()
        compressor = zlib.compressobj(self._level)

        while True:
            chunk = input_stream.read(BUFFER_SIZE)
            if not chunk:
                break
            stats.input_size += len(chunk)
            compressed = compressor.compress(chunk)
            if compressed:
                stats.output_size += len(compressed)
                output_stream.write(compressed)
            if progress_callback:
                progress_callback(len(chunk))

        # Flush remaining data
        final = compressor.flush()
        if final:
            stats.output_size += len(final)
            output_stream.write(final)

        stats.elapsed_time = time.monotonic() - start_time
        return stats


class BZip2Compressor(Compressor):
    """BZIP2 compression (good for text)."""

    def __init__(self, level: int = 9) -> None:
        """Initialize BZIP2 compressor.

        Args:
            level: Compression level (1-9).
        """
        self._level = max(1, min(9, level))

    @property
    def method(self) -> CompressionMethod:
        return CompressionMethod.BZIP2

    def compress(self, data: bytes) -> bytes:
        return bz2.compress(data, compresslevel=self._level)

    def decompress(self, data: bytes) -> bytes:
        return bz2.decompress(data)

    def compress_stream(
        self,
        input_stream: BinaryIO,
        output_stream: BinaryIO,
        progress_callback: Callable[[int], None] | None = None,
    ) -> CompressionStats:
        """Compress using streaming BZIP2."""
        stats = CompressionStats()
        start_time = time.monotonic()
        compressor = bz2.BZ2Compressor(self._level)

        while True:
            chunk = input_stream.read(BUFFER_SIZE)
            if not chunk:
                break
            stats.input_size += len(chunk)
            compressed = compressor.compress(chunk)
            if compressed:
                stats.output_size += len(compressed)
                output_stream.write(compressed)
            if progress_callback:
                progress_callback(len(chunk))

        # Flush remaining data
        final = compressor.flush()
        if final:
            stats.output_size += len(final)
            output_stream.write(final)

        stats.elapsed_time = time.monotonic() - start_time
        return stats


class LZMACompressor(Compressor):
    """LZMA compression (high compression ratio)."""

    def __init__(self, level: int = 6) -> None:
        """Initialize LZMA compressor.

        Args:
            level: Compression level (0-9), maps to LZMA preset.
        """
        self._preset = max(0, min(9, level))

    @property
    def method(self) -> CompressionMethod:
        return CompressionMethod.LZMA

    def compress(self, data: bytes) -> bytes:
        return lzma.compress(data, preset=self._preset)

    def decompress(self, data: bytes) -> bytes:
        return lzma.decompress(data)

    def compress_stream(
        self,
        input_stream: BinaryIO,
        output_stream: BinaryIO,
        progress_callback: Callable[[int], None] | None = None,
    ) -> CompressionStats:
        """Compress using streaming LZMA."""
        stats = CompressionStats()
        start_time = time.monotonic()
        compressor = lzma.LZMACompressor(preset=self._preset)

        while True:
            chunk = input_stream.read(BUFFER_SIZE)
            if not chunk:
                break
            stats.input_size += len(chunk)
            compressed = compressor.compress(chunk)
            if compressed:
                stats.output_size += len(compressed)
                output_stream.write(compressed)
            if progress_callback:
                progress_callback(len(chunk))

        # Flush remaining data
        final = compressor.flush()
        if final:
            stats.output_size += len(final)
            output_stream.write(final)

        stats.elapsed_time = time.monotonic() - start_time
        return stats


class ZstdCompressor(Compressor):
    """Zstandard compression (fast, modern algorithm)."""

    def __init__(self, level: int = 3) -> None:
        """Initialize ZSTD compressor.

        Args:
            level: Compression level (1-22, default 3).
        """
        if not HAS_ZSTD or zstd is None:
            msg = "zstandard library not installed. Install with: pip install zstandard"
            raise ImportError(msg)
        # ZSTD level 1-22, map from 0-9 to 1-19
        self._level = max(1, min(19, level * 2 + 1))
        self._cctx = zstd.ZstdCompressor(level=self._level)
        self._dctx = zstd.ZstdDecompressor()

    @property
    def method(self) -> CompressionMethod:
        return CompressionMethod.ZSTD

    def compress(self, data: bytes) -> bytes:
        return self._cctx.compress(data)

    def decompress(self, data: bytes) -> bytes:
        return self._dctx.decompress(data)

    def compress_stream(
        self,
        input_stream: BinaryIO,
        output_stream: BinaryIO,
        progress_callback: Callable[[int], None] | None = None,
    ) -> CompressionStats:
        """Compress using streaming ZSTD."""
        stats = CompressionStats()
        start_time = time.monotonic()

        with self._cctx.stream_writer(output_stream) as compressor:
            while True:
                chunk = input_stream.read(BUFFER_SIZE)
                if not chunk:
                    break
                stats.input_size += len(chunk)
                bytes_written = compressor.write(chunk)
                stats.output_size += bytes_written
                if progress_callback:
                    progress_callback(len(chunk))

        stats.elapsed_time = time.monotonic() - start_time
        return stats


class GzipCompressor(Compressor):
    """GZIP compression (single file compression)."""

    def __init__(self, level: int = 6) -> None:
        """Initialize GZIP compressor.

        Args:
            level: Compression level (0-9).
        """
        self._level = max(0, min(9, level))

    @property
    def method(self) -> CompressionMethod:
        return CompressionMethod.DEFLATE  # GZIP uses DEFLATE internally

    def compress(self, data: bytes) -> bytes:
        return gzip.compress(data, compresslevel=self._level)

    def decompress(self, data: bytes) -> bytes:
        return gzip.decompress(data)


def get_compressor(method: CompressionMethod, level: int = 6) -> Compressor:
    """Get a compressor instance for the specified method.

    Args:
        method: Compression method to use.
        level: Compression level (0-9).

    Returns:
        Compressor instance.

    Raises:
        ValueError: If method is not supported.
    """
    compressors: dict[CompressionMethod, type[Compressor]] = {
        CompressionMethod.STORE: StoreCompressor,
        CompressionMethod.DEFLATE: DeflateCompressor,
        CompressionMethod.BZIP2: BZip2Compressor,
        CompressionMethod.LZMA: LZMACompressor,
        CompressionMethod.LZMA2: LZMACompressor,  # LZMA2 uses same compressor
    }

    if method == CompressionMethod.ZSTD:
        if not HAS_ZSTD:
            msg = "ZSTD compression requires zstandard library"
            raise ValueError(msg)
        return ZstdCompressor(level)

    compressor_class = compressors.get(method)
    if compressor_class is None:
        msg = f"Unsupported compression method: {method}"
        raise ValueError(msg)

    if compressor_class == StoreCompressor:
        return StoreCompressor()
    elif compressor_class == DeflateCompressor:
        return DeflateCompressor(level)
    elif compressor_class == BZip2Compressor:
        return BZip2Compressor(level)
    elif compressor_class == LZMACompressor:
        return LZMACompressor(level)
    else:
        msg = f"Unsupported compression method: {method}"
        raise ValueError(msg)


def is_method_available(method: CompressionMethod) -> bool:
    """Check if a compression method is available.

    Args:
        method: Compression method to check.

    Returns:
        True if the method is available.
    """
    if method == CompressionMethod.ZSTD:
        return HAS_ZSTD

    # Built-in methods are always available
    builtin_methods = {
        CompressionMethod.STORE,
        CompressionMethod.DEFLATE,
        CompressionMethod.BZIP2,
        CompressionMethod.LZMA,
        CompressionMethod.LZMA2,
    }
    return method in builtin_methods


def get_available_methods() -> list[CompressionMethod]:
    """Get list of available compression methods.

    Returns:
        List of available CompressionMethod values.
    """
    methods = [
        CompressionMethod.STORE,
        CompressionMethod.DEFLATE,
        CompressionMethod.BZIP2,
        CompressionMethod.LZMA,
        CompressionMethod.LZMA2,
    ]
    if HAS_ZSTD:
        methods.append(CompressionMethod.ZSTD)
    return methods


class CompressionEngine:
    """High-level compression engine for creating archives.

    Provides file collection, progress tracking, and archive creation
    using various compression methods.
    """

    def __init__(
        self,
        options: CompressionOptions | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Initialize compression engine.

        Args:
            options: Compression options (defaults to ZIP/DEFLATE).
            progress_callback: Callback with (filename, bytes_done, bytes_total).
        """
        self._options = options or CompressionOptions()
        self._progress_callback = progress_callback
        self._cancelled = False
        self._paused = False

        # Get appropriate compressor
        self._compressor = get_compressor(
            self._options.method,
            self._options.level,
        )

        logger.debug(
            "CompressionEngine initialized: format=%s, method=%s, level=%d",
            self._options.format.name,
            self._options.method.name,
            self._options.level,
        )

    def cancel(self) -> None:
        """Cancel the compression operation."""
        self._cancelled = True
        logger.info("Compression cancelled")

    def pause(self) -> None:
        """Pause the compression operation."""
        self._paused = True
        logger.debug("Compression paused")

    def resume(self) -> None:
        """Resume the compression operation."""
        self._paused = False
        logger.debug("Compression resumed")

    @property
    def is_cancelled(self) -> bool:
        """Check if compression was cancelled."""
        return self._cancelled

    @property
    def is_paused(self) -> bool:
        """Check if compression is paused."""
        return self._paused

    def collect_files(
        self,
        sources: list[Path],
        base_path: Path | None = None,
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
                # Single file
                try:
                    archive_path = source.relative_to(base)
                except ValueError:
                    archive_path = Path(source.name)
                yield source, str(archive_path)

            elif source.is_dir():
                # Directory - walk recursively
                for root, dirs, files in os.walk(source, followlinks=self._options.follow_symlinks):
                    root_path = Path(root)

                    # Filter hidden directories if needed
                    if not self._options.include_hidden:
                        dirs[:] = [d for d in dirs if not d.startswith(".")]

                    for filename in files:
                        # Skip hidden files if needed
                        if not self._options.include_hidden and filename.startswith("."):
                            continue

                        file_path = root_path / filename
                        try:
                            archive_path = file_path.relative_to(base)
                        except ValueError:
                            archive_path = file_path.relative_to(source.parent)

                        yield file_path, str(archive_path)

    def calculate_total_size(self, sources: list[Path]) -> tuple[int, int]:
        """Calculate total size and file count from sources.

        Args:
            sources: List of source paths.

        Returns:
            Tuple of (total_bytes, file_count).
        """
        total_bytes = 0
        file_count = 0

        for file_path, _ in self.collect_files(sources, self._options.base_path):
            try:
                total_bytes += file_path.stat().st_size
                file_count += 1
            except OSError as e:
                logger.warning("Could not stat file %s: %s", file_path, e)

        return total_bytes, file_count

    def compress_file(self, source: Path, destination: Path) -> CompressionStats:
        """Compress a single file.

        Args:
            source: Source file path.
            destination: Destination file path.

        Returns:
            Compression statistics.

        Raises:
            FileNotFoundError: If source file doesn't exist.
            PermissionError: If can't read source or write destination.
        """
        if not source.exists():
            msg = f"Source file not found: {source}"
            raise FileNotFoundError(msg)

        start_time = time.monotonic()
        stats = CompressionStats()

        def progress_cb(bytes_done: int) -> None:
            if self._progress_callback:
                self._progress_callback(source.name, bytes_done, stats.input_size)

        with source.open("rb") as src, destination.open("wb") as dst:
            stats = self._compressor.compress_stream(src, dst, progress_cb)

        stats.elapsed_time = time.monotonic() - start_time
        logger.debug(
            "Compressed %s: %d -> %d bytes (%.1f%% ratio, %.2f MB/s)",
            source.name,
            stats.input_size,
            stats.output_size,
            stats.ratio,
            stats.speed_mbps,
        )
        return stats

    def compress_data(self, data: bytes) -> bytes:
        """Compress data in memory.

        Args:
            data: Raw bytes to compress.

        Returns:
            Compressed bytes.
        """
        return self._compressor.compress(data)

    def decompress_data(self, data: bytes) -> bytes:
        """Decompress data in memory.

        Args:
            data: Compressed bytes.

        Returns:
            Decompressed bytes.
        """
        return self._compressor.decompress(data)


def benchmark_compression(
    data: bytes,
    methods: list[CompressionMethod] | None = None,
    levels: list[int] | None = None,
) -> dict[str, CompressionStats]:
    """Benchmark compression methods on sample data.

    Args:
        data: Sample data to compress.
        methods: Methods to test (default: all available).
        levels: Levels to test (default: [1, 6, 9]).

    Returns:
        Dictionary of "method_level" -> CompressionStats.
    """
    if methods is None:
        methods = get_available_methods()
    if levels is None:
        levels = [1, 6, 9]

    results: dict[str, CompressionStats] = {}

    for method in methods:
        if not is_method_available(method):
            continue

        for level in levels:
            try:
                compressor = get_compressor(method, level)
                start_time = time.monotonic()
                compressed = compressor.compress(data)
                elapsed = time.monotonic() - start_time

                key = f"{method.name}_{level}"
                results[key] = CompressionStats(
                    input_size=len(data),
                    output_size=len(compressed),
                    elapsed_time=elapsed,
                )
                logger.debug(
                    "Benchmark %s: %.1f%% ratio, %.2f MB/s",
                    key,
                    results[key].ratio,
                    results[key].speed_mbps,
                )
            except Exception as e:
                logger.warning("Benchmark failed for %s level %d: %s", method.name, level, e)

    return results
