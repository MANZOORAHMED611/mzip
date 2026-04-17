"""Tests for compression engine and archive writer."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pytest

from zipextractor.core.compression import (
    BUFFER_SIZE,
    BZip2Compressor,
    CompressionEngine,
    CompressionStats,
    DeflateCompressor,
    GzipCompressor,
    LZMACompressor,
    StoreCompressor,
    benchmark_compression,
    get_available_methods,
    get_compressor,
    is_method_available,
)
from zipextractor.core.models import (
    ArchiveFormat,
    CompressionMethod,
    CompressionOptions,
)


class TestCompressionStats:
    """Tests for CompressionStats dataclass."""

    def test_compression_stats_creation(self) -> None:
        """Test creating compression stats with default values."""
        stats = CompressionStats()
        assert stats.input_size == 0
        assert stats.output_size == 0
        assert stats.elapsed_time == 0.0

    def test_compression_stats_with_values(self) -> None:
        """Test creating compression stats with custom values."""
        stats = CompressionStats(
            input_size=1000,
            output_size=500,
            elapsed_time=1.5,
        )
        assert stats.input_size == 1000
        assert stats.output_size == 500
        assert stats.elapsed_time == 1.5

    def test_compression_ratio_calculation(self) -> None:
        """Test compression ratio is calculated correctly."""
        stats = CompressionStats(input_size=1000, output_size=500)
        assert stats.ratio == 50.0

    def test_compression_ratio_zero_input(self) -> None:
        """Test compression ratio with zero input returns 0."""
        stats = CompressionStats(input_size=0, output_size=0)
        assert stats.ratio == 0.0

    def test_compression_speed_calculation(self) -> None:
        """Test compression speed is calculated correctly."""
        # 1MB in 1 second = 1 MB/s
        stats = CompressionStats(
            input_size=1024 * 1024,
            output_size=512 * 1024,
            elapsed_time=1.0,
        )
        assert stats.speed_mbps == 1.0

    def test_compression_speed_zero_time(self) -> None:
        """Test compression speed with zero time returns 0."""
        stats = CompressionStats(input_size=1000, elapsed_time=0)
        assert stats.speed_mbps == 0.0


class TestStoreCompressor:
    """Tests for StoreCompressor (no compression)."""

    def test_store_compressor_method(self) -> None:
        """Test store compressor reports correct method."""
        compressor = StoreCompressor()
        assert compressor.method == CompressionMethod.STORE

    def test_store_compressor_compress(self) -> None:
        """Test store compressor returns data unchanged."""
        compressor = StoreCompressor()
        data = b"Hello, World!"
        compressed = compressor.compress(data)
        assert compressed == data

    def test_store_compressor_decompress(self) -> None:
        """Test store compressor decompress returns data unchanged."""
        compressor = StoreCompressor()
        data = b"Hello, World!"
        decompressed = compressor.decompress(data)
        assert decompressed == data

    def test_store_compressor_roundtrip(self) -> None:
        """Test store compressor compress/decompress roundtrip."""
        compressor = StoreCompressor()
        data = b"Test data for roundtrip"
        compressed = compressor.compress(data)
        decompressed = compressor.decompress(compressed)
        assert decompressed == data


class TestDeflateCompressor:
    """Tests for DeflateCompressor."""

    def test_deflate_compressor_method(self) -> None:
        """Test deflate compressor reports correct method."""
        compressor = DeflateCompressor()
        assert compressor.method == CompressionMethod.DEFLATE

    def test_deflate_compressor_compress(self) -> None:
        """Test deflate compressor compresses data."""
        compressor = DeflateCompressor()
        # Repetitive data compresses well
        data = b"AAAAAAAAAA" * 100
        compressed = compressor.compress(data)
        assert len(compressed) < len(data)

    def test_deflate_compressor_decompress(self) -> None:
        """Test deflate compressor decompresses data."""
        compressor = DeflateCompressor()
        data = b"Test data for deflate"
        compressed = compressor.compress(data)
        decompressed = compressor.decompress(compressed)
        assert decompressed == data

    def test_deflate_compressor_level_0(self) -> None:
        """Test deflate compressor with level 0 (no compression)."""
        compressor = DeflateCompressor(level=0)
        data = b"Test data"
        compressed = compressor.compress(data)
        decompressed = compressor.decompress(compressed)
        assert decompressed == data

    def test_deflate_compressor_level_9(self) -> None:
        """Test deflate compressor with level 9 (max compression)."""
        compressor = DeflateCompressor(level=9)
        data = b"AAAAAAAAAA" * 100
        compressed = compressor.compress(data)
        assert len(compressed) < len(data)

    def test_deflate_compressor_stream(self) -> None:
        """Test deflate compressor with streaming."""
        compressor = DeflateCompressor()
        data = b"Stream test data" * 100
        input_stream = io.BytesIO(data)
        output_stream = io.BytesIO()

        stats = compressor.compress_stream(input_stream, output_stream)

        assert stats.input_size == len(data)
        assert stats.output_size > 0
        assert stats.output_size < len(data)


class TestBZip2Compressor:
    """Tests for BZip2Compressor."""

    def test_bzip2_compressor_method(self) -> None:
        """Test bzip2 compressor reports correct method."""
        compressor = BZip2Compressor()
        assert compressor.method == CompressionMethod.BZIP2

    def test_bzip2_compressor_compress(self) -> None:
        """Test bzip2 compressor compresses data."""
        compressor = BZip2Compressor()
        data = b"AAAAAAAAAA" * 100
        compressed = compressor.compress(data)
        assert len(compressed) < len(data)

    def test_bzip2_compressor_decompress(self) -> None:
        """Test bzip2 compressor decompresses data."""
        compressor = BZip2Compressor()
        data = b"Test data for bzip2"
        compressed = compressor.compress(data)
        decompressed = compressor.decompress(compressed)
        assert decompressed == data

    def test_bzip2_compressor_roundtrip(self) -> None:
        """Test bzip2 compressor compress/decompress roundtrip."""
        compressor = BZip2Compressor()
        data = b"Roundtrip test for bzip2 compression"
        compressed = compressor.compress(data)
        decompressed = compressor.decompress(compressed)
        assert decompressed == data


class TestLZMACompressor:
    """Tests for LZMACompressor."""

    def test_lzma_compressor_method(self) -> None:
        """Test LZMA compressor reports correct method."""
        compressor = LZMACompressor()
        assert compressor.method == CompressionMethod.LZMA

    def test_lzma_compressor_compress(self) -> None:
        """Test LZMA compressor compresses data."""
        compressor = LZMACompressor()
        data = b"AAAAAAAAAA" * 100
        compressed = compressor.compress(data)
        assert len(compressed) < len(data)

    def test_lzma_compressor_decompress(self) -> None:
        """Test LZMA compressor decompresses data."""
        compressor = LZMACompressor()
        data = b"Test data for LZMA"
        compressed = compressor.compress(data)
        decompressed = compressor.decompress(compressed)
        assert decompressed == data

    def test_lzma_compressor_high_compression(self) -> None:
        """Test LZMA achieves high compression on repetitive data."""
        compressor = LZMACompressor(level=9)
        data = b"ABCDEFGHIJ" * 1000
        compressed = compressor.compress(data)
        ratio = (len(data) - len(compressed)) / len(data) * 100
        # LZMA should achieve at least 80% compression on repetitive data
        assert ratio > 80


class TestGzipCompressor:
    """Tests for GzipCompressor."""

    def test_gzip_compressor_method(self) -> None:
        """Test gzip compressor reports DEFLATE method."""
        compressor = GzipCompressor()
        assert compressor.method == CompressionMethod.DEFLATE

    def test_gzip_compressor_compress(self) -> None:
        """Test gzip compressor compresses data."""
        compressor = GzipCompressor()
        data = b"AAAAAAAAAA" * 100
        compressed = compressor.compress(data)
        assert len(compressed) < len(data)

    def test_gzip_compressor_decompress(self) -> None:
        """Test gzip compressor decompresses data."""
        compressor = GzipCompressor()
        data = b"Test data for gzip"
        compressed = compressor.compress(data)
        decompressed = compressor.decompress(compressed)
        assert decompressed == data


class TestGetCompressor:
    """Tests for get_compressor factory function."""

    def test_get_store_compressor(self) -> None:
        """Test getting store compressor."""
        compressor = get_compressor(CompressionMethod.STORE)
        assert isinstance(compressor, StoreCompressor)

    def test_get_deflate_compressor(self) -> None:
        """Test getting deflate compressor."""
        compressor = get_compressor(CompressionMethod.DEFLATE)
        assert isinstance(compressor, DeflateCompressor)

    def test_get_bzip2_compressor(self) -> None:
        """Test getting bzip2 compressor."""
        compressor = get_compressor(CompressionMethod.BZIP2)
        assert isinstance(compressor, BZip2Compressor)

    def test_get_lzma_compressor(self) -> None:
        """Test getting LZMA compressor."""
        compressor = get_compressor(CompressionMethod.LZMA)
        assert isinstance(compressor, LZMACompressor)

    def test_get_lzma2_compressor(self) -> None:
        """Test getting LZMA2 compressor (same as LZMA)."""
        compressor = get_compressor(CompressionMethod.LZMA2)
        assert isinstance(compressor, LZMACompressor)

    def test_get_compressor_with_level(self) -> None:
        """Test getting compressor with custom level."""
        compressor = get_compressor(CompressionMethod.DEFLATE, level=9)
        assert isinstance(compressor, DeflateCompressor)


class TestIsMethodAvailable:
    """Tests for is_method_available function."""

    def test_store_is_available(self) -> None:
        """Test STORE method is always available."""
        assert is_method_available(CompressionMethod.STORE)

    def test_deflate_is_available(self) -> None:
        """Test DEFLATE method is always available."""
        assert is_method_available(CompressionMethod.DEFLATE)

    def test_bzip2_is_available(self) -> None:
        """Test BZIP2 method is always available."""
        assert is_method_available(CompressionMethod.BZIP2)

    def test_lzma_is_available(self) -> None:
        """Test LZMA method is always available."""
        assert is_method_available(CompressionMethod.LZMA)


class TestGetAvailableMethods:
    """Tests for get_available_methods function."""

    def test_available_methods_includes_builtin(self) -> None:
        """Test available methods includes all builtin methods."""
        methods = get_available_methods()
        assert CompressionMethod.STORE in methods
        assert CompressionMethod.DEFLATE in methods
        assert CompressionMethod.BZIP2 in methods
        assert CompressionMethod.LZMA in methods

    def test_available_methods_returns_list(self) -> None:
        """Test available methods returns a list."""
        methods = get_available_methods()
        assert isinstance(methods, list)
        assert len(methods) >= 4


class TestCompressionEngine:
    """Tests for CompressionEngine class."""

    def test_engine_initialization_defaults(self) -> None:
        """Test engine initialization with defaults."""
        engine = CompressionEngine()
        assert not engine.is_cancelled
        assert not engine.is_paused

    def test_engine_initialization_with_options(self) -> None:
        """Test engine initialization with custom options."""
        options = CompressionOptions(
            method=CompressionMethod.LZMA,
            level=9,
        )
        engine = CompressionEngine(options=options)
        assert not engine.is_cancelled

    def test_engine_cancel(self) -> None:
        """Test engine cancel functionality."""
        engine = CompressionEngine()
        engine.cancel()
        assert engine.is_cancelled

    def test_engine_pause_resume(self) -> None:
        """Test engine pause and resume functionality."""
        engine = CompressionEngine()
        assert not engine.is_paused
        engine.pause()
        assert engine.is_paused
        engine.resume()
        assert not engine.is_paused

    def test_engine_compress_data(self) -> None:
        """Test engine compress_data method."""
        engine = CompressionEngine()
        data = b"Test data" * 100
        compressed = engine.compress_data(data)
        assert len(compressed) < len(data)

    def test_engine_decompress_data(self) -> None:
        """Test engine decompress_data method."""
        engine = CompressionEngine()
        data = b"Test data" * 100
        compressed = engine.compress_data(data)
        decompressed = engine.decompress_data(compressed)
        assert decompressed == data

    def test_engine_collect_files_single_file(self) -> None:
        """Test engine collects single file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello")

            engine = CompressionEngine()
            files = list(engine.collect_files([test_file]))

            assert len(files) == 1
            assert files[0][0] == test_file
            assert "test.txt" in files[0][1]

    def test_engine_collect_files_directory(self) -> None:
        """Test engine collects files from directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file1.txt").write_text("content1")
            (tmppath / "file2.txt").write_text("content2")
            (tmppath / "subdir").mkdir()
            (tmppath / "subdir" / "file3.txt").write_text("content3")

            engine = CompressionEngine()
            files = list(engine.collect_files([tmppath]))

            assert len(files) == 3
            names = [f[1] for f in files]
            assert any("file1.txt" in n for n in names)
            assert any("file2.txt" in n for n in names)
            assert any("file3.txt" in n for n in names)

    def test_engine_calculate_total_size(self) -> None:
        """Test engine calculates total size correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "file1.txt").write_text("12345")  # 5 bytes
            (tmppath / "file2.txt").write_text("1234567890")  # 10 bytes

            engine = CompressionEngine()
            total_bytes, file_count = engine.calculate_total_size([tmppath])

            assert total_bytes == 15
            assert file_count == 2

    def test_engine_compress_file(self) -> None:
        """Test engine compresses a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            source = tmppath / "source.txt"
            dest = tmppath / "compressed.bin"
            source.write_text("A" * 1000)

            engine = CompressionEngine()
            stats = engine.compress_file(source, dest)

            assert dest.exists()
            assert stats.input_size == 1000
            assert stats.output_size < stats.input_size

    def test_engine_compress_file_not_found(self) -> None:
        """Test engine raises error for non-existent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            source = tmppath / "nonexistent.txt"
            dest = tmppath / "output.bin"

            engine = CompressionEngine()
            with pytest.raises(FileNotFoundError):
                engine.compress_file(source, dest)


class TestCompressionOptions:
    """Tests for CompressionOptions dataclass."""

    def test_options_default_values(self) -> None:
        """Test options has sensible defaults."""
        options = CompressionOptions()
        assert options.format == ArchiveFormat.ZIP
        assert options.method == CompressionMethod.DEFLATE
        assert options.level == 6
        assert not options.encrypt
        assert options.password is None

    def test_options_validates_level(self) -> None:
        """Test options validates compression level."""
        with pytest.raises(ValueError, match="level must be 0-9"):
            CompressionOptions(level=10)

        with pytest.raises(ValueError, match="level must be 0-9"):
            CompressionOptions(level=-1)

    def test_options_requires_password_for_encryption(self) -> None:
        """Test options requires password when encrypt=True."""
        with pytest.raises(ValueError, match="Password required"):
            CompressionOptions(encrypt=True)

    def test_options_encryption_with_password(self) -> None:
        """Test options allows encryption with password."""
        options = CompressionOptions(
            encrypt=True,
            password="secret123",
        )
        assert options.encrypt
        assert options.password == "secret123"

    def test_options_filename_encryption_requires_7z(self) -> None:
        """Test filename encryption only for 7z format."""
        with pytest.raises(ValueError, match=r"[Ff]ilename encryption"):
            CompressionOptions(
                format=ArchiveFormat.ZIP,
                encrypt=True,
                encrypt_filenames=True,
                password="secret",
            )

    def test_options_solid_archive_requires_7z(self) -> None:
        """Test solid archives only for 7z format."""
        with pytest.raises(ValueError, match="Solid archives"):
            CompressionOptions(
                format=ArchiveFormat.ZIP,
                solid=True,
            )


class TestBenchmarkCompression:
    """Tests for benchmark_compression function."""

    def test_benchmark_returns_dict(self) -> None:
        """Test benchmark returns a dictionary."""
        data = b"Test data for benchmark" * 100
        results = benchmark_compression(data)
        assert isinstance(results, dict)

    def test_benchmark_tests_deflate(self) -> None:
        """Test benchmark includes deflate results."""
        data = b"Test data for benchmark" * 100
        results = benchmark_compression(
            data,
            methods=[CompressionMethod.DEFLATE],
            levels=[6],
        )
        assert "DEFLATE_6" in results

    def test_benchmark_results_have_stats(self) -> None:
        """Test benchmark results contain CompressionStats."""
        data = b"Test data for benchmark" * 100
        results = benchmark_compression(
            data,
            methods=[CompressionMethod.DEFLATE],
            levels=[1],
        )
        stats = results.get("DEFLATE_1")
        assert stats is not None
        assert isinstance(stats, CompressionStats)
        assert stats.input_size == len(data)
        assert stats.output_size > 0


class TestBufferSize:
    """Tests for buffer size constant."""

    def test_buffer_size_is_reasonable(self) -> None:
        """Test buffer size is a reasonable value."""
        # Should be at least 64KB
        assert BUFFER_SIZE >= 64 * 1024
        # Should not exceed 1MB
        assert BUFFER_SIZE <= 1024 * 1024
