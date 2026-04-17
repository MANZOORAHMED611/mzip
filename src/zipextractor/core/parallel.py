"""Parallel processing module for multi-threaded archive operations.

This module provides multi-threaded extraction and compression capabilities
for improved performance on multi-core systems.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
import zipfile
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Status of a parallel task."""

    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


class ProgressCallback(Protocol):
    """Protocol for progress callbacks."""

    def __call__(
        self,
        current: int,
        total: int,
        current_file: str | None = None,
    ) -> None:
        """Report progress.

        Args:
            current: Current progress count.
            total: Total count.
            current_file: Currently processing file name.
        """
        ...


@dataclass
class TaskResult:
    """Result of a single parallel task.

    Attributes:
        file_path: Path of the processed file.
        success: Whether the task succeeded.
        error: Error message if failed.
        bytes_processed: Number of bytes processed.
        duration_ms: Duration in milliseconds.
    """

    file_path: str
    success: bool
    error: str | None = None
    bytes_processed: int = 0
    duration_ms: float = 0.0


@dataclass
class ParallelResult:
    """Result of a parallel operation.

    Attributes:
        total_files: Total number of files processed.
        successful_files: Number of successful operations.
        failed_files: Number of failed operations.
        total_bytes: Total bytes processed.
        duration_ms: Total duration in milliseconds.
        results: Individual task results.
        errors: List of error messages.
    """

    total_files: int = 0
    successful_files: int = 0
    failed_files: int = 0
    total_bytes: int = 0
    duration_ms: float = 0.0
    results: list[TaskResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_files == 0:
            return 100.0
        return (self.successful_files / self.total_files) * 100

    @property
    def throughput_mbps(self) -> float:
        """Calculate throughput in MB/s."""
        if self.duration_ms == 0:
            return 0.0
        return (self.total_bytes / (1024 * 1024)) / (self.duration_ms / 1000)


@dataclass
class WorkerConfig:
    """Configuration for parallel workers.

    Attributes:
        max_workers: Maximum number of worker threads. None for auto-detect.
        chunk_size: Size of work chunks for batch processing.
        buffer_size: I/O buffer size in bytes.
        timeout: Timeout for individual tasks in seconds.
        memory_limit_mb: Maximum memory usage per worker in MB.
    """

    max_workers: int | None = None
    chunk_size: int = 10
    buffer_size: int = 64 * 1024  # 64KB
    timeout: float | None = None
    memory_limit_mb: int = 256

    def __post_init__(self) -> None:
        """Set default max_workers based on CPU count."""
        if self.max_workers is None:
            # Use CPU count, but cap at reasonable values
            cpu_count = os.cpu_count() or 4
            self.max_workers = min(cpu_count, 16)


def get_optimal_worker_count(file_count: int | None = None) -> int:
    """Determine optimal number of worker threads.

    Args:
        file_count: Number of files to process (for scaling).

    Returns:
        Optimal number of workers.
    """
    cpu_count = os.cpu_count() or 4

    # For I/O bound operations, we can use more threads than CPUs
    # but not too many to avoid context switching overhead
    base_workers = min(cpu_count * 2, 16)

    if file_count is not None:
        # Don't use more workers than files
        return min(base_workers, file_count)

    return base_workers


def get_optimal_chunk_size(total_size: int, worker_count: int) -> int:
    """Calculate optimal chunk size for parallel processing.

    Args:
        total_size: Total data size in bytes.
        worker_count: Number of workers.

    Returns:
        Optimal chunk size in bytes.
    """
    # Aim for chunks between 1MB and 64MB
    min_chunk = 1 * 1024 * 1024  # 1MB
    max_chunk = 64 * 1024 * 1024  # 64MB

    if total_size == 0:
        return min_chunk

    # Calculate chunk size to distribute work evenly
    ideal_chunk = total_size // (worker_count * 4)  # ~4 chunks per worker

    return max(min_chunk, min(max_chunk, ideal_chunk))


class ParallelExtractor:
    """Multi-threaded archive extractor.

    Extracts files from archives using multiple threads for improved
    performance on multi-core systems.
    """

    def __init__(
        self,
        archive_path: Path,
        destination: Path,
        config: WorkerConfig | None = None,
    ) -> None:
        """Initialize parallel extractor.

        Args:
            archive_path: Path to the archive file.
            destination: Destination directory for extracted files.
            config: Worker configuration.
        """
        self.archive_path = archive_path
        self.destination = destination
        self.config = config or WorkerConfig()
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused by default
        self._lock = threading.Lock()
        self._progress_callback: ProgressCallback | None = None
        self._completed_count = 0
        self._total_count = 0

    def set_progress_callback(self, callback: ProgressCallback) -> None:
        """Set progress callback function.

        Args:
            callback: Function to call with progress updates.
        """
        self._progress_callback = callback

    def cancel(self) -> None:
        """Cancel the extraction operation."""
        self._cancel_event.set()

    def pause(self) -> None:
        """Pause the extraction operation."""
        self._pause_event.clear()

    def resume(self) -> None:
        """Resume the extraction operation."""
        self._pause_event.set()

    def _check_state(self) -> bool:
        """Check if operation should continue.

        Returns:
            True if operation should continue, False if cancelled.
        """
        if self._cancel_event.is_set():
            return False

        # Wait if paused
        self._pause_event.wait()
        return not self._cancel_event.is_set()

    def _extract_file(
        self,
        zf: zipfile.ZipFile,
        info: zipfile.ZipInfo,
    ) -> TaskResult:
        """Extract a single file from the archive.

        Args:
            zf: Open ZipFile object.
            info: ZipInfo for the file to extract.

        Returns:
            TaskResult for the extraction.
        """
        import time

        start_time = time.perf_counter()

        if not self._check_state():
            return TaskResult(
                file_path=info.filename,
                success=False,
                error="Operation cancelled",
            )

        try:
            # Create destination path
            dest_path = self.destination / info.filename

            if info.is_dir():
                dest_path.mkdir(parents=True, exist_ok=True)
                return TaskResult(
                    file_path=info.filename,
                    success=True,
                    bytes_processed=0,
                    duration_ms=(time.perf_counter() - start_time) * 1000,
                )

            # Ensure parent directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Extract with buffered I/O
            with zf.open(info) as src:
                with dest_path.open("wb") as dst:
                    bytes_written = 0
                    while True:
                        if not self._check_state():
                            return TaskResult(
                                file_path=info.filename,
                                success=False,
                                error="Operation cancelled",
                            )

                        chunk = src.read(self.config.buffer_size)
                        if not chunk:
                            break
                        dst.write(chunk)
                        bytes_written += len(chunk)

            duration_ms = (time.perf_counter() - start_time) * 1000

            # Update progress
            with self._lock:
                self._completed_count += 1
                if self._progress_callback:
                    self._progress_callback(
                        self._completed_count,
                        self._total_count,
                        info.filename,
                    )

            return TaskResult(
                file_path=info.filename,
                success=True,
                bytes_processed=bytes_written,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error("Failed to extract %s: %s", info.filename, e)
            return TaskResult(
                file_path=info.filename,
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )

    def extract_all(
        self,
        file_filter: Callable[[str], bool] | None = None,
    ) -> ParallelResult:
        """Extract all files from the archive using multiple threads.

        Args:
            file_filter: Optional filter function for file names.

        Returns:
            ParallelResult with extraction statistics.
        """
        import time

        start_time = time.perf_counter()
        result = ParallelResult()

        try:
            with zipfile.ZipFile(self.archive_path, "r") as zf:
                # Get list of files to extract
                infos = [
                    info
                    for info in zf.infolist()
                    if file_filter is None or file_filter(info.filename)
                ]

                self._total_count = len(infos)
                result.total_files = len(infos)

                if not infos:
                    return result

                # Determine worker count
                worker_count = min(
                    self.config.max_workers or get_optimal_worker_count(len(infos)),
                    len(infos),
                )

                logger.info(
                    "Extracting %d files with %d workers",
                    len(infos),
                    worker_count,
                )

                # For ZIP files, we need to be careful about thread safety
                # Python's zipfile is not thread-safe for reading different files
                # So we use a queue-based approach with worker threads each
                # opening their own ZipFile handle

                with ThreadPoolExecutor(max_workers=worker_count) as executor:
                    futures: dict[Future[TaskResult], zipfile.ZipInfo] = {}

                    for info in infos:
                        if self._cancel_event.is_set():
                            break

                        future = executor.submit(
                            self._extract_file_safe,
                            info,
                        )
                        futures[future] = info

                    # Collect results
                    for future in as_completed(futures):
                        if self._cancel_event.is_set():
                            # Cancel remaining futures
                            for f in futures:
                                f.cancel()
                            break

                        try:
                            task_result = future.result(
                                timeout=self.config.timeout
                            )
                            result.results.append(task_result)

                            if task_result.success:
                                result.successful_files += 1
                                result.total_bytes += task_result.bytes_processed
                            else:
                                result.failed_files += 1
                                if task_result.error:
                                    result.errors.append(
                                        f"{task_result.file_path}: {task_result.error}"
                                    )

                        except Exception as e:
                            info = futures[future]
                            result.failed_files += 1
                            result.errors.append(f"{info.filename}: {e}")

        except Exception as e:
            logger.error("Parallel extraction failed: %s", e)
            result.errors.append(f"Extraction failed: {e}")

        result.duration_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "Extraction complete: %d/%d files, %.2f MB/s",
            result.successful_files,
            result.total_files,
            result.throughput_mbps,
        )

        return result

    def _extract_file_safe(self, info: zipfile.ZipInfo) -> TaskResult:
        """Thread-safe file extraction with its own ZipFile handle.

        Args:
            info: ZipInfo for the file to extract.

        Returns:
            TaskResult for the extraction.
        """
        # Each thread opens its own ZipFile handle for thread safety
        with zipfile.ZipFile(self.archive_path, "r") as zf:
            return self._extract_file(zf, info)


class ParallelCompressor:
    """Multi-threaded file compressor.

    Compresses files using multiple threads for improved performance
    on multi-core systems.
    """

    def __init__(
        self,
        output_path: Path,
        config: WorkerConfig | None = None,
        compression: int = zipfile.ZIP_DEFLATED,
        compression_level: int = 6,
    ) -> None:
        """Initialize parallel compressor.

        Args:
            output_path: Path for the output archive.
            config: Worker configuration.
            compression: Compression method.
            compression_level: Compression level (0-9).
        """
        self.output_path = output_path
        self.config = config or WorkerConfig()
        self.compression = compression
        self.compression_level = compression_level
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused by default
        self._lock = threading.Lock()
        self._progress_callback: ProgressCallback | None = None
        self._completed_count = 0
        self._total_count = 0
        self._compressed_queue: queue.Queue[tuple[str, bytes]] = queue.Queue()

    def set_progress_callback(self, callback: ProgressCallback) -> None:
        """Set progress callback function.

        Args:
            callback: Function to call with progress updates.
        """
        self._progress_callback = callback

    def cancel(self) -> None:
        """Cancel the compression operation."""
        self._cancel_event.set()

    def pause(self) -> None:
        """Pause the compression operation."""
        self._pause_event.clear()

    def resume(self) -> None:
        """Resume the compression operation."""
        self._pause_event.set()

    def _check_state(self) -> bool:
        """Check if operation should continue."""
        if self._cancel_event.is_set():
            return False
        self._pause_event.wait()
        return not self._cancel_event.is_set()

    def _compress_file(
        self,
        file_path: Path,
        archive_name: str,
    ) -> TaskResult:
        """Compress a single file.

        Args:
            file_path: Path to the file to compress.
            archive_name: Name in the archive.

        Returns:
            TaskResult for the compression.
        """
        import time
        import zlib

        start_time = time.perf_counter()

        if not self._check_state():
            return TaskResult(
                file_path=str(file_path),
                success=False,
                error="Operation cancelled",
            )

        try:
            # Read and compress the file
            with file_path.open("rb") as f:
                data = f.read()

            original_size = len(data)

            # Compress the data
            if self.compression == zipfile.ZIP_DEFLATED:
                compressed = zlib.compress(data, self.compression_level)
            else:
                compressed = data

            # Queue the compressed data for writing
            self._compressed_queue.put((archive_name, compressed))

            duration_ms = (time.perf_counter() - start_time) * 1000

            # Update progress
            with self._lock:
                self._completed_count += 1
                if self._progress_callback:
                    self._progress_callback(
                        self._completed_count,
                        self._total_count,
                        archive_name,
                    )

            return TaskResult(
                file_path=str(file_path),
                success=True,
                bytes_processed=original_size,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error("Failed to compress %s: %s", file_path, e)
            return TaskResult(
                file_path=str(file_path),
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )

    def compress_files(
        self,
        files: Sequence[tuple[Path, str]],
    ) -> ParallelResult:
        """Compress multiple files into the archive.

        Note: Due to ZIP format limitations, the actual writing to the
        archive is done sequentially after parallel compression. This
        still provides speedup as compression is CPU-bound.

        Args:
            files: Sequence of (file_path, archive_name) tuples.

        Returns:
            ParallelResult with compression statistics.
        """
        import time

        start_time = time.perf_counter()
        result = ParallelResult()
        result.total_files = len(files)
        self._total_count = len(files)

        if not files:
            return result

        # Determine worker count
        worker_count = min(
            self.config.max_workers or get_optimal_worker_count(len(files)),
            len(files),
        )

        logger.info(
            "Compressing %d files with %d workers",
            len(files),
            worker_count,
        )

        # Phase 1: Compress files in parallel

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures: dict[Future[TaskResult], tuple[Path, str]] = {}

            for file_path, archive_name in files:
                if self._cancel_event.is_set():
                    break

                future = executor.submit(
                    self._compress_file,
                    file_path,
                    archive_name,
                )
                futures[future] = (file_path, archive_name)

            # Collect compression results
            for future in as_completed(futures):
                if self._cancel_event.is_set():
                    for f in futures:
                        f.cancel()
                    break

                try:
                    task_result = future.result(timeout=self.config.timeout)
                    result.results.append(task_result)

                    if task_result.success:
                        result.successful_files += 1
                        result.total_bytes += task_result.bytes_processed
                    else:
                        result.failed_files += 1
                        if task_result.error:
                            result.errors.append(
                                f"{task_result.file_path}: {task_result.error}"
                            )

                except Exception as e:
                    file_path, archive_name = futures[future]
                    result.failed_files += 1
                    result.errors.append(f"{file_path}: {e}")

        # Phase 2: Write compressed data to archive sequentially
        # (ZIP format requires sequential writes)
        try:
            with zipfile.ZipFile(
                self.output_path,
                "w",
                compression=self.compression,
                compresslevel=self.compression_level,
            ) as zf:
                while not self._compressed_queue.empty():
                    archive_name, data = self._compressed_queue.get_nowait()
                    # Write using writestr since we pre-compressed
                    zf.writestr(archive_name, data)

        except Exception as e:
            logger.error("Failed to write archive: %s", e)
            result.errors.append(f"Failed to write archive: {e}")

        result.duration_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "Compression complete: %d/%d files, %.2f MB/s",
            result.successful_files,
            result.total_files,
            result.throughput_mbps,
        )

        return result


class WorkQueue:
    """Thread-safe work queue for parallel processing.

    Provides a producer-consumer pattern for distributing work
    across multiple threads.
    """

    def __init__(self, max_size: int = 0) -> None:
        """Initialize work queue.

        Args:
            max_size: Maximum queue size. 0 for unlimited.
        """
        self._queue: queue.Queue[Any] = queue.Queue(maxsize=max_size)
        self._completed = threading.Event()

    def put(self, item: Any, timeout: float | None = None) -> bool:
        """Add item to queue.

        Args:
            item: Item to add.
            timeout: Timeout in seconds.

        Returns:
            True if item was added.
        """
        try:
            self._queue.put(item, timeout=timeout)
            return True
        except queue.Full:
            return False

    def get(self, timeout: float | None = None) -> Any | None:
        """Get item from queue.

        Args:
            timeout: Timeout in seconds.

        Returns:
            Item from queue or None if timeout.
        """
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def mark_done(self) -> None:
        """Mark current task as done."""
        self._queue.task_done()

    def mark_completed(self) -> None:
        """Mark all work as completed (no more items will be added)."""
        self._completed.set()

    @property
    def is_completed(self) -> bool:
        """Check if queue is completed and empty."""
        return self._completed.is_set() and self._queue.empty()

    def __len__(self) -> int:
        """Return approximate queue size."""
        return self._queue.qsize()


def parallel_map(
    func: Callable[[Any], Any],
    items: Sequence[Any],
    max_workers: int | None = None,
    progress_callback: ProgressCallback | None = None,
) -> Iterator[Any]:
    """Apply function to items in parallel.

    Args:
        func: Function to apply.
        items: Items to process.
        max_workers: Maximum workers. None for auto-detect.
        progress_callback: Optional progress callback.

    Yields:
        Results from function application.
    """
    if not items:
        return

    worker_count = max_workers or get_optimal_worker_count(len(items))
    completed = 0
    total = len(items)

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {executor.submit(func, item): item for item in items}

        for future in as_completed(futures):
            result = future.result()
            completed += 1

            if progress_callback:
                progress_callback(completed, total)

            yield result


def cpu_info() -> dict[str, Any]:
    """Get CPU information for performance tuning.

    Returns:
        Dictionary with CPU information.
    """
    info: dict[str, Any] = {
        "cpu_count": os.cpu_count() or 1,
        "recommended_workers": get_optimal_worker_count(),
    }

    # Try to get more detailed info on Linux
    try:
        with Path("/proc/cpuinfo").open() as f:
            cpuinfo = f.read()

        # Extract model name
        for line in cpuinfo.split("\n"):
            if line.startswith("model name"):
                info["model"] = line.split(":")[1].strip()
                break

    except (OSError, IndexError):
        pass

    return info
