"""Benchmarking module for performance testing.

This module provides tools for measuring compression and extraction
performance across different methods, levels, and configurations.
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

logger = logging.getLogger(__name__)


class BenchmarkType(Enum):
    """Type of benchmark to run."""

    COMPRESSION = auto()
    EXTRACTION = auto()
    ROUND_TRIP = auto()  # Compress then extract
    THROUGHPUT = auto()  # Raw I/O throughput


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run.

    Attributes:
        name: Name of the benchmark.
        benchmark_type: Type of benchmark.
        input_size: Input data size in bytes.
        output_size: Output data size in bytes.
        duration_ms: Duration in milliseconds.
        iterations: Number of iterations run.
        config: Configuration used for the benchmark.
    """

    name: str
    benchmark_type: BenchmarkType
    input_size: int
    output_size: int
    duration_ms: float
    iterations: int = 1
    config: dict[str, Any] = field(default_factory=dict)

    @property
    def compression_ratio(self) -> float:
        """Calculate compression ratio (input/output)."""
        if self.output_size == 0:
            return 0.0
        return self.input_size / self.output_size

    @property
    def space_saving(self) -> float:
        """Calculate space saving percentage."""
        if self.input_size == 0:
            return 0.0
        return ((self.input_size - self.output_size) / self.input_size) * 100

    @property
    def throughput_mbps(self) -> float:
        """Calculate throughput in MB/s."""
        if self.duration_ms == 0:
            return 0.0
        return (self.input_size / (1024 * 1024)) / (self.duration_ms / 1000)

    @property
    def avg_duration_ms(self) -> float:
        """Calculate average duration per iteration."""
        return self.duration_ms / max(self.iterations, 1)


@dataclass
class BenchmarkSuite:
    """Collection of benchmark results.

    Attributes:
        name: Name of the benchmark suite.
        results: List of benchmark results.
        system_info: System information at time of benchmark.
        timestamp: When the benchmark was run.
    """

    name: str
    results: list[BenchmarkResult] = field(default_factory=list)
    system_info: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def add_result(self, result: BenchmarkResult) -> None:
        """Add a benchmark result to the suite."""
        self.results.append(result)

    def get_by_type(self, benchmark_type: BenchmarkType) -> list[BenchmarkResult]:
        """Get results filtered by benchmark type."""
        return [r for r in self.results if r.benchmark_type == benchmark_type]

    def get_fastest(self, benchmark_type: BenchmarkType) -> BenchmarkResult | None:
        """Get the fastest result of a given type."""
        typed_results = self.get_by_type(benchmark_type)
        if not typed_results:
            return None
        return min(typed_results, key=lambda r: r.avg_duration_ms)

    def get_best_ratio(self, benchmark_type: BenchmarkType) -> BenchmarkResult | None:
        """Get the result with best compression ratio."""
        typed_results = self.get_by_type(benchmark_type)
        if not typed_results:
            return None
        return max(typed_results, key=lambda r: r.compression_ratio)

    def summary(self) -> dict[str, Any]:
        """Generate summary statistics for the suite."""
        compression_results = self.get_by_type(BenchmarkType.COMPRESSION)
        extraction_results = self.get_by_type(BenchmarkType.EXTRACTION)

        return {
            "total_benchmarks": len(self.results),
            "compression_benchmarks": len(compression_results),
            "extraction_benchmarks": len(extraction_results),
            "fastest_compression": (
                fastest_comp.name
                if (fastest_comp := self.get_fastest(BenchmarkType.COMPRESSION))
                else None
            ),
            "best_ratio": (
                best_ratio.name
                if (best_ratio := self.get_best_ratio(BenchmarkType.COMPRESSION))
                else None
            ),
            "fastest_extraction": (
                fastest_ext.name
                if (fastest_ext := self.get_fastest(BenchmarkType.EXTRACTION))
                else None
            ),
        }


def generate_test_data(size: int, pattern: str = "random") -> bytes:
    """Generate test data for benchmarking.

    Args:
        size: Size of data to generate in bytes.
        pattern: Type of data pattern:
            - "random": Random bytes (incompressible)
            - "zeros": All zeros (highly compressible)
            - "text": Pseudo-random text (moderately compressible)
            - "mixed": Mix of patterns

    Returns:
        Generated test data.
    """
    if pattern == "random":
        return os.urandom(size)

    elif pattern == "zeros":
        return b"\x00" * size

    elif pattern == "text":
        # Generate pseudo-random text that's somewhat compressible
        import string

        chars = (string.ascii_letters + string.digits + " \n").encode()
        # Use a simple PRNG for reproducibility
        result = bytearray(size)
        seed = 42
        for i in range(size):
            seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
            result[i] = chars[seed % len(chars)]
        return bytes(result)

    elif pattern == "mixed":
        # Mix of patterns - realistic simulation
        chunk_size = size // 4
        return (
            generate_test_data(chunk_size, "text")
            + generate_test_data(chunk_size, "zeros")
            + generate_test_data(chunk_size, "random")
            + generate_test_data(size - 3 * chunk_size, "text")
        )

    else:
        raise ValueError(f"Unknown pattern: {pattern}")


def benchmark_compression_method(
    data: bytes,
    method: int,
    level: int,
    iterations: int = 3,
) -> BenchmarkResult:
    """Benchmark a specific compression method and level.

    Args:
        data: Data to compress.
        method: Compression method (zipfile.ZIP_DEFLATED, etc.).
        level: Compression level.
        iterations: Number of iterations for averaging.

    Returns:
        BenchmarkResult with timing information.
    """
    import io

    method_names = {
        zipfile.ZIP_STORED: "store",
        zipfile.ZIP_DEFLATED: "deflate",
        zipfile.ZIP_BZIP2: "bzip2",
        zipfile.ZIP_LZMA: "lzma",
    }

    name = f"{method_names.get(method, 'unknown')}-{level}"
    input_size = len(data)
    total_duration = 0.0
    output_size = 0

    for _ in range(iterations):
        start = time.perf_counter()

        # Create in-memory ZIP
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=method, compresslevel=level) as zf:
            zf.writestr("data", data)

        output_size = buffer.tell()
        total_duration += (time.perf_counter() - start) * 1000

    return BenchmarkResult(
        name=name,
        benchmark_type=BenchmarkType.COMPRESSION,
        input_size=input_size,
        output_size=output_size,
        duration_ms=total_duration,
        iterations=iterations,
        config={"method": method, "level": level},
    )


def benchmark_extraction(
    archive_path: Path,
    iterations: int = 3,
) -> BenchmarkResult:
    """Benchmark extraction from an archive.

    Args:
        archive_path: Path to the archive.
        iterations: Number of iterations.

    Returns:
        BenchmarkResult with timing information.
    """
    total_duration = 0.0
    total_size = 0

    with zipfile.ZipFile(archive_path, "r") as zf:
        # Calculate total uncompressed size
        total_size = sum(info.file_size for info in zf.infolist())

    for _ in range(iterations):
        with tempfile.TemporaryDirectory() as tmpdir:
            start = time.perf_counter()

            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(tmpdir)

            total_duration += (time.perf_counter() - start) * 1000

    return BenchmarkResult(
        name=archive_path.name,
        benchmark_type=BenchmarkType.EXTRACTION,
        input_size=archive_path.stat().st_size,
        output_size=total_size,
        duration_ms=total_duration,
        iterations=iterations,
    )


def benchmark_round_trip(
    data: bytes,
    method: int = zipfile.ZIP_DEFLATED,
    level: int = 6,
    iterations: int = 3,
) -> BenchmarkResult:
    """Benchmark compression followed by extraction.

    Args:
        data: Data to compress and extract.
        method: Compression method.
        level: Compression level.
        iterations: Number of iterations.

    Returns:
        BenchmarkResult with timing information.
    """
    import io

    method_names = {
        zipfile.ZIP_STORED: "store",
        zipfile.ZIP_DEFLATED: "deflate",
        zipfile.ZIP_BZIP2: "bzip2",
        zipfile.ZIP_LZMA: "lzma",
    }

    name = f"roundtrip-{method_names.get(method, 'unknown')}-{level}"
    input_size = len(data)
    total_duration = 0.0
    compressed_size = 0

    for _ in range(iterations):
        start = time.perf_counter()

        # Compress
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=method, compresslevel=level) as zf:
            zf.writestr("data", data)
        compressed_size = buffer.tell()

        # Extract
        buffer.seek(0)
        with zipfile.ZipFile(buffer, "r") as zf:
            extracted = zf.read("data")

        total_duration += (time.perf_counter() - start) * 1000

        # Verify
        if extracted != data:
            logger.warning("Data mismatch in round-trip benchmark!")

    return BenchmarkResult(
        name=name,
        benchmark_type=BenchmarkType.ROUND_TRIP,
        input_size=input_size,
        output_size=compressed_size,
        duration_ms=total_duration,
        iterations=iterations,
        config={"method": method, "level": level},
    )


def benchmark_io_throughput(
    size: int = 100 * 1024 * 1024,  # 100MB
    iterations: int = 3,
) -> BenchmarkResult:
    """Benchmark raw I/O throughput.

    Args:
        size: Size of data to write/read.
        iterations: Number of iterations.

    Returns:
        BenchmarkResult with throughput information.
    """
    data = generate_test_data(size, "random")
    total_duration = 0.0

    for _ in range(iterations):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = Path(f.name)

        try:
            start = time.perf_counter()

            # Write
            with temp_path.open("wb") as f:
                f.write(data)

            # Read
            with temp_path.open("rb") as f:
                _ = f.read()

            total_duration += (time.perf_counter() - start) * 1000

        finally:
            temp_path.unlink()

    return BenchmarkResult(
        name="io-throughput",
        benchmark_type=BenchmarkType.THROUGHPUT,
        input_size=size,
        output_size=size,
        duration_ms=total_duration,
        iterations=iterations,
    )


def run_compression_benchmark(
    data_size: int = 10 * 1024 * 1024,  # 10MB
    data_pattern: str = "mixed",
    methods: Sequence[int] | None = None,
    levels: Sequence[int] | None = None,
    iterations: int = 3,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> BenchmarkSuite:
    """Run a comprehensive compression benchmark suite.

    Args:
        data_size: Size of test data.
        data_pattern: Type of test data pattern.
        methods: Compression methods to test.
        levels: Compression levels to test.
        iterations: Iterations per benchmark.
        progress_callback: Optional progress callback(current, total, name).

    Returns:
        BenchmarkSuite with all results.
    """
    from zipextractor.core.parallel import cpu_info

    suite = BenchmarkSuite(
        name="compression-benchmark",
        system_info=cpu_info(),
    )

    # Default methods and levels
    if methods is None:
        methods = [
            zipfile.ZIP_STORED,
            zipfile.ZIP_DEFLATED,
            zipfile.ZIP_BZIP2,
            zipfile.ZIP_LZMA,
        ]

    if levels is None:
        levels = [1, 5, 9]

    # Generate test data
    logger.info("Generating %d bytes of '%s' test data", data_size, data_pattern)
    data = generate_test_data(data_size, data_pattern)

    # Calculate total benchmarks for progress
    total_benchmarks = sum(
        len(levels) if m != zipfile.ZIP_STORED else 1
        for m in methods
    )
    current = 0

    for method in methods:
        method_levels = levels if method != zipfile.ZIP_STORED else [0]

        for level in method_levels:
            current += 1
            name = f"Benchmarking method={method}, level={level}"

            if progress_callback:
                progress_callback(current, total_benchmarks, name)

            logger.info(name)

            try:
                result = benchmark_compression_method(
                    data, method, level, iterations
                )
                suite.add_result(result)

                logger.info(
                    "  %s: %.2f MB/s, ratio=%.2f, time=%.0fms",
                    result.name,
                    result.throughput_mbps,
                    result.compression_ratio,
                    result.avg_duration_ms,
                )

            except Exception as e:
                logger.error("Benchmark failed: %s", e)

    return suite


def run_extraction_benchmark(
    archive_paths: Sequence[Path],
    iterations: int = 3,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> BenchmarkSuite:
    """Run extraction benchmarks on provided archives.

    Args:
        archive_paths: Paths to archives to benchmark.
        iterations: Iterations per benchmark.
        progress_callback: Optional progress callback.

    Returns:
        BenchmarkSuite with results.
    """
    from zipextractor.core.parallel import cpu_info

    suite = BenchmarkSuite(
        name="extraction-benchmark",
        system_info=cpu_info(),
    )

    total = len(archive_paths)

    for i, archive_path in enumerate(archive_paths, 1):
        if progress_callback:
            progress_callback(i, total, str(archive_path))

        logger.info("Benchmarking extraction: %s", archive_path)

        try:
            result = benchmark_extraction(archive_path, iterations)
            suite.add_result(result)

            logger.info(
                "  %s: %.2f MB/s, time=%.0fms",
                result.name,
                result.throughput_mbps,
                result.avg_duration_ms,
            )

        except Exception as e:
            logger.error("Extraction benchmark failed: %s", e)

    return suite


def run_parallel_benchmark(
    data_size: int = 50 * 1024 * 1024,  # 50MB
    file_count: int = 100,
    worker_counts: Sequence[int] | None = None,
    iterations: int = 3,
) -> BenchmarkSuite:
    """Benchmark parallel processing performance.

    Args:
        data_size: Total data size to process.
        file_count: Number of files to create.
        worker_counts: Worker counts to test.
        iterations: Iterations per benchmark.

    Returns:
        BenchmarkSuite with parallel performance results.
    """
    from zipextractor.core.parallel import (
        ParallelExtractor,
        WorkerConfig,
        cpu_info,
        get_optimal_worker_count,
    )

    suite = BenchmarkSuite(
        name="parallel-benchmark",
        system_info=cpu_info(),
    )

    if worker_counts is None:
        max_workers = get_optimal_worker_count()
        worker_counts = [1, 2, 4, max_workers]
        # Remove duplicates and sort
        worker_counts = sorted(set(worker_counts))

    # Create test files
    file_size = data_size // file_count

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create a test archive with multiple files
        archive_path = tmpdir_path / "test.zip"
        logger.info("Creating test archive with %d files", file_count)

        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for i in range(file_count):
                data = generate_test_data(file_size, "text")
                zf.writestr(f"file_{i:04d}.dat", data)

        # Benchmark with different worker counts
        for worker_count in worker_counts:
            logger.info("Benchmarking with %d workers", worker_count)

            total_duration = 0.0

            for _ in range(iterations):
                extract_dir = tmpdir_path / f"extract_{worker_count}"

                config = WorkerConfig(max_workers=worker_count)
                extractor = ParallelExtractor(
                    archive_path,
                    extract_dir,
                    config,
                )

                start = time.perf_counter()
                extractor.extract_all()
                total_duration += (time.perf_counter() - start) * 1000

                # Clean up
                import shutil

                if extract_dir.exists():
                    shutil.rmtree(extract_dir)

            benchmark_result = BenchmarkResult(
                name=f"parallel-{worker_count}-workers",
                benchmark_type=BenchmarkType.EXTRACTION,
                input_size=archive_path.stat().st_size,
                output_size=data_size,
                duration_ms=total_duration,
                iterations=iterations,
                config={"workers": worker_count},
            )
            suite.add_result(benchmark_result)

            logger.info(
                "  %d workers: %.2f MB/s, time=%.0fms",
                worker_count,
                benchmark_result.throughput_mbps,
                benchmark_result.avg_duration_ms,
            )

    return suite


def format_benchmark_report(suite: BenchmarkSuite) -> str:
    """Format benchmark results as a readable report.

    Args:
        suite: BenchmarkSuite to format.

    Returns:
        Formatted report string.
    """
    lines = [
        f"Benchmark Report: {suite.name}",
        "=" * 60,
        "",
        "System Information:",
    ]

    for key, value in suite.system_info.items():
        lines.append(f"  {key}: {value}")

    lines.append("")
    lines.append(f"Total benchmarks: {len(suite.results)}")
    lines.append("")

    # Group by type
    for btype in BenchmarkType:
        results = suite.get_by_type(btype)
        if not results:
            continue

        lines.append(f"{btype.name} Results:")
        lines.append("-" * 40)

        for result in sorted(results, key=lambda r: r.avg_duration_ms):
            lines.append(f"  {result.name}:")
            lines.append(f"    Throughput: {result.throughput_mbps:.2f} MB/s")
            lines.append(f"    Time: {result.avg_duration_ms:.0f} ms (avg)")
            if result.benchmark_type == BenchmarkType.COMPRESSION:
                lines.append(f"    Ratio: {result.compression_ratio:.2f}x")
                lines.append(f"    Space saving: {result.space_saving:.1f}%")

        lines.append("")

    # Summary
    summary = suite.summary()
    lines.append("Summary:")
    lines.append("-" * 40)

    if summary["fastest_compression"]:
        lines.append(f"  Fastest compression: {summary['fastest_compression']}")
    if summary["best_ratio"]:
        lines.append(f"  Best compression ratio: {summary['best_ratio']}")
    if summary["fastest_extraction"]:
        lines.append(f"  Fastest extraction: {summary['fastest_extraction']}")

    return "\n".join(lines)


def compare_with_external(
    data_size: int = 10 * 1024 * 1024,
    tools: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Compare mzip performance with external tools.

    Args:
        data_size: Size of test data.
        tools: List of external tools to compare.

    Returns:
        Comparison results.
    """
    import shutil
    import subprocess

    if tools is None:
        tools = ["zip", "7z", "gzip"]

    results: dict[str, Any] = {"mzip": {}, "external": {}}

    # Generate test data
    data = generate_test_data(data_size, "mixed")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Write test file
        test_file = tmpdir_path / "testdata"
        test_file.write_bytes(data)

        # Benchmark mzip
        import io

        start = time.perf_counter()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            zf.write(test_file, "testdata")
        mzip_time = (time.perf_counter() - start) * 1000
        mzip_size = buffer.tell()

        results["mzip"] = {
            "time_ms": mzip_time,
            "size": mzip_size,
            "throughput_mbps": (data_size / (1024 * 1024)) / (mzip_time / 1000),
        }

        # Benchmark external tools
        for tool in tools:
            if not shutil.which(tool):
                logger.warning("Tool not found: %s", tool)
                continue

            try:
                output_file = tmpdir_path / f"output.{tool}"

                if tool == "zip":
                    cmd = ["zip", "-6", str(output_file), str(test_file)]
                elif tool == "7z":
                    cmd = ["7z", "a", "-mx=6", str(output_file), str(test_file)]
                elif tool == "gzip":
                    cmd = ["gzip", "-6", "-k", str(test_file)]
                    output_file = tmpdir_path / "testdata.gz"
                else:
                    continue

                start = time.perf_counter()
                subprocess.run(cmd, capture_output=True, check=True)
                tool_time = (time.perf_counter() - start) * 1000

                tool_size = output_file.stat().st_size if output_file.exists() else 0

                results["external"][tool] = {
                    "time_ms": tool_time,
                    "size": tool_size,
                    "throughput_mbps": (
                        (data_size / (1024 * 1024)) / (tool_time / 1000)
                        if tool_time > 0
                        else 0
                    ),
                }

            except Exception as e:
                logger.error("Failed to benchmark %s: %s", tool, e)

    return results
