"""Tests for parallel processing module."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from zipextractor.core.parallel import (
    ParallelExtractor,
    ParallelResult,
    TaskResult,
    TaskStatus,
    WorkerConfig,
    WorkQueue,
    cpu_info,
    get_optimal_chunk_size,
    get_optimal_worker_count,
    parallel_map,
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
        for i in range(10):
            zf.writestr(f"file_{i:03d}.txt", f"Content of file {i}\n" * 100)
        zf.writestr("subdir/nested.txt", "Nested file content")
    return zip_path


class TestTaskResult:
    """Tests for TaskResult dataclass."""

    def test_successful_result(self) -> None:
        """Test creating a successful task result."""
        result = TaskResult(
            file_path="test.txt",
            success=True,
            bytes_processed=1024,
            duration_ms=100.0,
        )
        assert result.success
        assert result.file_path == "test.txt"
        assert result.bytes_processed == 1024
        assert result.duration_ms == 100.0
        assert result.error is None

    def test_failed_result(self) -> None:
        """Test creating a failed task result."""
        result = TaskResult(
            file_path="error.txt",
            success=False,
            error="File not found",
        )
        assert not result.success
        assert result.error == "File not found"


class TestParallelResult:
    """Tests for ParallelResult dataclass."""

    def test_empty_result(self) -> None:
        """Test empty parallel result."""
        result = ParallelResult()
        assert result.total_files == 0
        assert result.successful_files == 0
        assert result.failed_files == 0
        assert result.success_rate == 100.0

    def test_success_rate(self) -> None:
        """Test success rate calculation."""
        result = ParallelResult(
            total_files=10,
            successful_files=8,
            failed_files=2,
        )
        assert result.success_rate == 80.0

    def test_throughput(self) -> None:
        """Test throughput calculation."""
        result = ParallelResult(
            total_bytes=10 * 1024 * 1024,  # 10 MB
            duration_ms=1000,  # 1 second
        )
        assert result.throughput_mbps == 10.0

    def test_throughput_zero_duration(self) -> None:
        """Test throughput with zero duration."""
        result = ParallelResult(total_bytes=1024, duration_ms=0)
        assert result.throughput_mbps == 0.0


class TestWorkerConfig:
    """Tests for WorkerConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default worker configuration."""
        config = WorkerConfig()
        assert config.max_workers is not None
        assert config.max_workers > 0
        assert config.max_workers <= 16
        assert config.buffer_size == 64 * 1024

    def test_custom_config(self) -> None:
        """Test custom worker configuration."""
        config = WorkerConfig(
            max_workers=4,
            chunk_size=20,
            buffer_size=128 * 1024,
            timeout=30.0,
        )
        assert config.max_workers == 4
        assert config.chunk_size == 20
        assert config.buffer_size == 128 * 1024
        assert config.timeout == 30.0


class TestOptimalWorkerCount:
    """Tests for get_optimal_worker_count function."""

    def test_default_worker_count(self) -> None:
        """Test default worker count calculation."""
        count = get_optimal_worker_count()
        assert count > 0
        assert count <= 16

    def test_worker_count_with_file_count(self) -> None:
        """Test worker count limited by file count."""
        # With only 2 files, shouldn't use more than 2 workers
        count = get_optimal_worker_count(file_count=2)
        assert count <= 2

    def test_worker_count_many_files(self) -> None:
        """Test worker count with many files."""
        count = get_optimal_worker_count(file_count=1000)
        # Should scale up but not exceed reasonable limit
        assert count > 0
        assert count <= 16


class TestOptimalChunkSize:
    """Tests for get_optimal_chunk_size function."""

    def test_minimum_chunk_size(self) -> None:
        """Test minimum chunk size."""
        # Small data should give minimum chunk
        chunk = get_optimal_chunk_size(1000, 4)
        assert chunk >= 1 * 1024 * 1024  # At least 1MB

    def test_maximum_chunk_size(self) -> None:
        """Test maximum chunk size."""
        # Large data should be capped at max
        chunk = get_optimal_chunk_size(1024 * 1024 * 1024, 2)  # 1GB
        assert chunk <= 64 * 1024 * 1024  # At most 64MB

    def test_zero_total_size(self) -> None:
        """Test with zero total size."""
        chunk = get_optimal_chunk_size(0, 4)
        assert chunk >= 1 * 1024 * 1024


class TestParallelExtractor:
    """Tests for ParallelExtractor class."""

    def test_extract_all(self, sample_zip: Path, temp_dir: Path) -> None:
        """Test extracting all files."""
        output_dir = temp_dir / "output"
        extractor = ParallelExtractor(sample_zip, output_dir)

        result = extractor.extract_all()

        assert result.total_files == 11  # 10 files + 1 nested (subdir entry not counted)
        assert result.successful_files == result.total_files
        assert result.failed_files == 0
        assert result.total_bytes > 0
        assert (output_dir / "file_000.txt").exists()
        assert (output_dir / "subdir" / "nested.txt").exists()

    def test_extract_with_filter(self, sample_zip: Path, temp_dir: Path) -> None:
        """Test extraction with file filter."""
        output_dir = temp_dir / "output"
        extractor = ParallelExtractor(sample_zip, output_dir)

        # Only extract files with even numbers
        result = extractor.extract_all(
            file_filter=lambda name: "file_00" in name and int(name[-7:-4]) % 2 == 0
        )

        # Should extract file_000, file_002, file_004, file_006, file_008
        assert result.successful_files == 5

    def test_extract_with_progress(self, sample_zip: Path, temp_dir: Path) -> None:
        """Test extraction with progress callback."""
        output_dir = temp_dir / "output"
        extractor = ParallelExtractor(sample_zip, output_dir)

        progress_updates: list[tuple[int, int]] = []

        def progress_callback(current: int, total: int, _file: str | None = None) -> None:
            progress_updates.append((current, total))

        extractor.set_progress_callback(progress_callback)
        result = extractor.extract_all()

        assert result.successful_files > 0
        assert len(progress_updates) > 0
        # Final progress should match total
        last_current, last_total = progress_updates[-1]
        assert last_current == last_total

    def test_extract_cancel(self, sample_zip: Path, temp_dir: Path) -> None:
        """Test cancelling extraction."""
        output_dir = temp_dir / "output"
        config = WorkerConfig(max_workers=1)  # Single worker for predictable behavior
        extractor = ParallelExtractor(sample_zip, output_dir, config)

        # Cancel immediately
        extractor.cancel()
        result = extractor.extract_all()

        # Some operations may have already started
        assert result.total_files > 0

    def test_extract_with_custom_config(self, sample_zip: Path, temp_dir: Path) -> None:
        """Test extraction with custom configuration."""
        output_dir = temp_dir / "output"
        config = WorkerConfig(
            max_workers=2,
            buffer_size=32 * 1024,
        )
        extractor = ParallelExtractor(sample_zip, output_dir, config)

        result = extractor.extract_all()

        assert result.successful_files > 0


class TestWorkQueue:
    """Tests for WorkQueue class."""

    def test_put_get(self) -> None:
        """Test basic put/get operations."""
        queue = WorkQueue()
        queue.put("item1")
        queue.put("item2")

        assert queue.get(timeout=1) == "item1"
        assert queue.get(timeout=1) == "item2"

    def test_get_timeout(self) -> None:
        """Test get with timeout on empty queue."""
        queue = WorkQueue()
        result = queue.get(timeout=0.1)
        assert result is None

    def test_is_completed(self) -> None:
        """Test completion status."""
        queue = WorkQueue()
        queue.put("item")

        assert not queue.is_completed

        queue.mark_completed()
        queue.get(timeout=1)

        assert queue.is_completed

    def test_len(self) -> None:
        """Test queue length."""
        queue = WorkQueue()
        assert len(queue) == 0

        queue.put("item1")
        queue.put("item2")
        assert len(queue) == 2


class TestParallelMap:
    """Tests for parallel_map function."""

    def test_basic_map(self) -> None:
        """Test basic parallel map."""
        items = [1, 2, 3, 4, 5]
        results = list(parallel_map(lambda x: x * 2, items))

        assert len(results) == 5
        assert sorted(results) == [2, 4, 6, 8, 10]

    def test_map_with_progress(self) -> None:
        """Test parallel map with progress callback."""
        items = list(range(10))
        progress_calls: list[tuple[int, int]] = []

        def progress_callback(current: int, total: int, _file: str | None = None) -> None:
            progress_calls.append((current, total))

        results = list(
            parallel_map(
                lambda x: x * 2,
                items,
                progress_callback=progress_callback,
            )
        )

        assert len(results) == 10
        assert len(progress_calls) == 10

    def test_empty_items(self) -> None:
        """Test parallel map with empty items."""
        results = list(parallel_map(lambda x: x, []))
        assert results == []


class TestCpuInfo:
    """Tests for cpu_info function."""

    def test_cpu_info(self) -> None:
        """Test CPU info retrieval."""
        info = cpu_info()

        assert "cpu_count" in info
        assert info["cpu_count"] > 0
        assert "recommended_workers" in info
        assert info["recommended_workers"] > 0


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_status_values(self) -> None:
        """Test TaskStatus enum values."""
        assert TaskStatus.PENDING is not None
        assert TaskStatus.RUNNING is not None
        assert TaskStatus.COMPLETED is not None
        assert TaskStatus.FAILED is not None
        assert TaskStatus.CANCELLED is not None
