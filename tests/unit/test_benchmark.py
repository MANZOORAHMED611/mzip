"""Tests for benchmark module."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from zipextractor.core.benchmark import (
    BenchmarkResult,
    BenchmarkSuite,
    BenchmarkType,
    benchmark_compression_method,
    benchmark_extraction,
    benchmark_io_throughput,
    benchmark_round_trip,
    format_benchmark_report,
    generate_test_data,
    run_compression_benchmark,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def temp_dir() -> Iterator[Path]:
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_zip(temp_dir: Path) -> Path:
    """Create a sample ZIP archive for testing."""
    zip_path = temp_dir / "sample.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add some test content
        for i in range(5):
            zf.writestr(f"file_{i}.txt", f"Test content {i}\n" * 100)
    return zip_path


class TestBenchmarkResult:
    """Tests for BenchmarkResult dataclass."""

    def test_basic_result(self) -> None:
        """Test creating a basic benchmark result."""
        result = BenchmarkResult(
            name="test-benchmark",
            benchmark_type=BenchmarkType.COMPRESSION,
            input_size=10000,
            output_size=5000,
            duration_ms=100.0,
        )
        assert result.name == "test-benchmark"
        assert result.benchmark_type == BenchmarkType.COMPRESSION
        assert result.input_size == 10000
        assert result.output_size == 5000

    def test_compression_ratio(self) -> None:
        """Test compression ratio calculation."""
        result = BenchmarkResult(
            name="test",
            benchmark_type=BenchmarkType.COMPRESSION,
            input_size=10000,
            output_size=2000,
            duration_ms=100.0,
        )
        assert result.compression_ratio == 5.0

    def test_compression_ratio_zero_output(self) -> None:
        """Test compression ratio with zero output size."""
        result = BenchmarkResult(
            name="test",
            benchmark_type=BenchmarkType.COMPRESSION,
            input_size=10000,
            output_size=0,
            duration_ms=100.0,
        )
        assert result.compression_ratio == 0.0

    def test_space_saving(self) -> None:
        """Test space saving calculation."""
        result = BenchmarkResult(
            name="test",
            benchmark_type=BenchmarkType.COMPRESSION,
            input_size=10000,
            output_size=2000,
            duration_ms=100.0,
        )
        assert result.space_saving == 80.0

    def test_throughput(self) -> None:
        """Test throughput calculation."""
        result = BenchmarkResult(
            name="test",
            benchmark_type=BenchmarkType.COMPRESSION,
            input_size=10 * 1024 * 1024,  # 10 MB
            output_size=5 * 1024 * 1024,
            duration_ms=1000,  # 1 second
        )
        assert result.throughput_mbps == 10.0

    def test_throughput_zero_duration(self) -> None:
        """Test throughput with zero duration."""
        result = BenchmarkResult(
            name="test",
            benchmark_type=BenchmarkType.COMPRESSION,
            input_size=10000,
            output_size=5000,
            duration_ms=0,
        )
        assert result.throughput_mbps == 0.0

    def test_avg_duration(self) -> None:
        """Test average duration calculation."""
        result = BenchmarkResult(
            name="test",
            benchmark_type=BenchmarkType.COMPRESSION,
            input_size=10000,
            output_size=5000,
            duration_ms=300.0,
            iterations=3,
        )
        assert result.avg_duration_ms == 100.0


class TestBenchmarkSuite:
    """Tests for BenchmarkSuite dataclass."""

    def test_empty_suite(self) -> None:
        """Test empty benchmark suite."""
        suite = BenchmarkSuite(name="test-suite")
        assert suite.name == "test-suite"
        assert len(suite.results) == 0

    def test_add_result(self) -> None:
        """Test adding results to suite."""
        suite = BenchmarkSuite(name="test-suite")
        result = BenchmarkResult(
            name="test",
            benchmark_type=BenchmarkType.COMPRESSION,
            input_size=1000,
            output_size=500,
            duration_ms=10.0,
        )
        suite.add_result(result)
        assert len(suite.results) == 1

    def test_get_by_type(self) -> None:
        """Test filtering results by type."""
        suite = BenchmarkSuite(name="test-suite")
        suite.add_result(
            BenchmarkResult(
                name="compress1",
                benchmark_type=BenchmarkType.COMPRESSION,
                input_size=1000,
                output_size=500,
                duration_ms=10.0,
            )
        )
        suite.add_result(
            BenchmarkResult(
                name="extract1",
                benchmark_type=BenchmarkType.EXTRACTION,
                input_size=500,
                output_size=1000,
                duration_ms=5.0,
            )
        )

        compression_results = suite.get_by_type(BenchmarkType.COMPRESSION)
        assert len(compression_results) == 1
        assert compression_results[0].name == "compress1"

    def test_get_fastest(self) -> None:
        """Test getting fastest result."""
        suite = BenchmarkSuite(name="test-suite")
        suite.add_result(
            BenchmarkResult(
                name="slow",
                benchmark_type=BenchmarkType.COMPRESSION,
                input_size=1000,
                output_size=500,
                duration_ms=100.0,
            )
        )
        suite.add_result(
            BenchmarkResult(
                name="fast",
                benchmark_type=BenchmarkType.COMPRESSION,
                input_size=1000,
                output_size=500,
                duration_ms=10.0,
            )
        )

        fastest = suite.get_fastest(BenchmarkType.COMPRESSION)
        assert fastest is not None
        assert fastest.name == "fast"

    def test_get_best_ratio(self) -> None:
        """Test getting best compression ratio."""
        suite = BenchmarkSuite(name="test-suite")
        suite.add_result(
            BenchmarkResult(
                name="poor",
                benchmark_type=BenchmarkType.COMPRESSION,
                input_size=1000,
                output_size=900,
                duration_ms=10.0,
            )
        )
        suite.add_result(
            BenchmarkResult(
                name="good",
                benchmark_type=BenchmarkType.COMPRESSION,
                input_size=1000,
                output_size=200,
                duration_ms=10.0,
            )
        )

        best = suite.get_best_ratio(BenchmarkType.COMPRESSION)
        assert best is not None
        assert best.name == "good"

    def test_summary(self) -> None:
        """Test summary generation."""
        suite = BenchmarkSuite(name="test-suite")
        suite.add_result(
            BenchmarkResult(
                name="test1",
                benchmark_type=BenchmarkType.COMPRESSION,
                input_size=1000,
                output_size=500,
                duration_ms=10.0,
            )
        )

        summary = suite.summary()
        assert summary["total_benchmarks"] == 1
        assert summary["compression_benchmarks"] == 1
        assert summary["fastest_compression"] == "test1"


class TestGenerateTestData:
    """Tests for generate_test_data function."""

    def test_random_data(self) -> None:
        """Test generating random data."""
        data = generate_test_data(1000, "random")
        assert len(data) == 1000
        # Random data should have high entropy (not easily compressible)
        assert len(set(data)) > 100

    def test_zeros_data(self) -> None:
        """Test generating zeros data."""
        data = generate_test_data(1000, "zeros")
        assert len(data) == 1000
        assert all(b == 0 for b in data)

    def test_text_data(self) -> None:
        """Test generating text data."""
        data = generate_test_data(1000, "text")
        assert len(data) == 1000
        # Should be ASCII printable characters
        assert all(32 <= b <= 126 or b == 10 for b in data)

    def test_mixed_data(self) -> None:
        """Test generating mixed data."""
        data = generate_test_data(1000, "mixed")
        assert len(data) == 1000

    def test_invalid_pattern(self) -> None:
        """Test invalid pattern raises error."""
        with pytest.raises(ValueError, match="Unknown pattern"):
            generate_test_data(1000, "invalid")


class TestBenchmarkCompressionMethod:
    """Tests for benchmark_compression_method function."""

    def test_deflate_compression(self) -> None:
        """Test benchmarking DEFLATE compression."""
        data = generate_test_data(10000, "text")
        result = benchmark_compression_method(
            data,
            zipfile.ZIP_DEFLATED,
            level=6,
            iterations=1,
        )

        assert result.benchmark_type == BenchmarkType.COMPRESSION
        assert result.input_size == 10000
        assert result.output_size > 0
        assert result.duration_ms > 0
        assert "deflate" in result.name

    def test_store_compression(self) -> None:
        """Test benchmarking STORE (no compression)."""
        data = generate_test_data(10000, "random")
        result = benchmark_compression_method(
            data,
            zipfile.ZIP_STORED,
            level=0,
            iterations=1,
        )

        assert "store" in result.name
        # Store should have minimal compression (overhead from ZIP format)
        assert result.compression_ratio < 1.1


class TestBenchmarkExtraction:
    """Tests for benchmark_extraction function."""

    def test_extraction_benchmark(self, sample_zip: Path) -> None:
        """Test benchmarking extraction."""
        result = benchmark_extraction(sample_zip, iterations=1)

        assert result.benchmark_type == BenchmarkType.EXTRACTION
        assert result.input_size > 0
        assert result.output_size > 0
        assert result.duration_ms > 0


class TestBenchmarkRoundTrip:
    """Tests for benchmark_round_trip function."""

    def test_round_trip(self) -> None:
        """Test round-trip benchmark."""
        data = generate_test_data(10000, "text")
        result = benchmark_round_trip(
            data,
            method=zipfile.ZIP_DEFLATED,
            level=6,
            iterations=1,
        )

        assert result.benchmark_type == BenchmarkType.ROUND_TRIP
        assert result.input_size == 10000
        assert result.duration_ms > 0


class TestBenchmarkIoThroughput:
    """Tests for benchmark_io_throughput function."""

    def test_io_throughput(self) -> None:
        """Test I/O throughput benchmark."""
        # Use small size for test speed
        result = benchmark_io_throughput(
            size=1 * 1024 * 1024,  # 1MB
            iterations=1,
        )

        assert result.benchmark_type == BenchmarkType.THROUGHPUT
        assert result.input_size == 1 * 1024 * 1024
        assert result.throughput_mbps > 0


class TestRunCompressionBenchmark:
    """Tests for run_compression_benchmark function."""

    def test_basic_suite(self) -> None:
        """Test running a basic compression benchmark suite."""
        suite = run_compression_benchmark(
            data_size=10000,
            data_pattern="text",
            methods=[zipfile.ZIP_DEFLATED],
            levels=[6],
            iterations=1,
        )

        assert suite.name == "compression-benchmark"
        assert len(suite.results) >= 1
        assert "system_info" in dir(suite)

    def test_with_progress_callback(self) -> None:
        """Test benchmark with progress callback."""
        progress_calls: list[tuple[int, int, str]] = []

        def progress(current: int, total: int, name: str) -> None:
            progress_calls.append((current, total, name))

        suite = run_compression_benchmark(
            data_size=10000,
            data_pattern="text",
            methods=[zipfile.ZIP_DEFLATED],
            levels=[1, 6],
            iterations=1,
            progress_callback=progress,
        )

        assert len(suite.results) == 2
        assert len(progress_calls) == 2


class TestFormatBenchmarkReport:
    """Tests for format_benchmark_report function."""

    def test_format_report(self) -> None:
        """Test formatting benchmark report."""
        suite = BenchmarkSuite(name="test-suite")
        suite.system_info = {"cpu_count": 4}
        suite.add_result(
            BenchmarkResult(
                name="deflate-6",
                benchmark_type=BenchmarkType.COMPRESSION,
                input_size=10000,
                output_size=5000,
                duration_ms=100.0,
            )
        )

        report = format_benchmark_report(suite)

        assert "test-suite" in report
        assert "cpu_count" in report
        assert "deflate-6" in report
        assert "MB/s" in report


class TestBenchmarkType:
    """Tests for BenchmarkType enum."""

    def test_benchmark_types(self) -> None:
        """Test BenchmarkType enum values."""
        assert BenchmarkType.COMPRESSION is not None
        assert BenchmarkType.EXTRACTION is not None
        assert BenchmarkType.ROUND_TRIP is not None
        assert BenchmarkType.THROUGHPUT is not None
