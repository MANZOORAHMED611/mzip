"""Background workers for extraction operations.

This module provides worker classes that run extraction tasks in background
threads, enabling non-blocking UI updates through GLib.idle_add().
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from pathlib import Path

from gi.repository import GLib

from zipextractor.core.extraction import ExtractionEngine
from zipextractor.core.models import (
    ConflictResolution,
    ExtractionTask,
    ProgressStats,
    TaskStatus,
)
from zipextractor.core.progress import ProgressTracker
from zipextractor.utils.logging import get_logger

logger = get_logger(__name__)


class ExtractionWorker:
    """Runs extraction in a background thread with progress reporting.

    This worker handles the actual extraction operation in a separate thread,
    using GLib.idle_add() to safely report progress back to the GTK main thread.

    Example:
        >>> worker = ExtractionWorker(
        ...     task=task,
        ...     on_progress=update_progress_bar,
        ...     on_complete=show_completion,
        ...     on_error=show_error,
        ... )
        >>> worker.start()
        >>> # Later...
        >>> worker.cancel()
    """

    def __init__(
        self,
        task: ExtractionTask,
        on_progress: Callable[[ExtractionTask, ProgressStats], None],
        on_complete: Callable[[ExtractionTask, bool], None],
        on_error: Callable[[ExtractionTask, str], None],
    ) -> None:
        """Initialize the extraction worker.

        Args:
            task: The extraction task to execute.
            on_progress: Callback for progress updates (called via GLib.idle_add).
            on_complete: Callback when extraction completes (success or failure).
            on_error: Callback when an error occurs during extraction.
        """
        self._task = task
        self._on_progress = on_progress
        self._on_complete = on_complete
        self._on_error = on_error

        self._engine = ExtractionEngine()
        self._tracker = ProgressTracker()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    @property
    def task(self) -> ExtractionTask:
        """Get the current extraction task."""
        return self._task

    @property
    def is_running(self) -> bool:
        """Check if the worker is currently running."""
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start the extraction in a background thread."""
        if self.is_running:
            logger.warning("Worker already running, ignoring start request")
            return

        self._stop_event.clear()
        self._tracker.start(self._task.total_bytes)

        self._thread = threading.Thread(
            target=self._run,
            name=f"extraction-{self._task.task_id}",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "Started extraction worker for %s",
            self._task.archive_path.name,
        )

    def cancel(self) -> None:
        """Request cancellation of the extraction."""
        logger.info("Cancellation requested for task %s", self._task.task_id)
        self._stop_event.set()
        self._engine.cancel()

    def pause(self) -> None:
        """Pause the extraction."""
        logger.info("Pause requested for task %s", self._task.task_id)
        self._engine.pause()

    def resume(self) -> None:
        """Resume the extraction."""
        logger.info("Resume requested for task %s", self._task.task_id)
        self._engine.resume()

    def _run(self) -> None:
        """Execute the extraction in the background thread."""
        try:
            logger.debug("Worker thread started for %s", self._task.archive_path)

            # Run extraction with progress callback
            success = self._engine.extract(
                self._task,
                progress_callback=self._handle_progress,
            )

            # Report completion via GLib.idle_add
            GLib.idle_add(self._report_complete, success)

        except Exception as e:
            logger.exception("Unexpected error during extraction: %s", e)
            GLib.idle_add(self._report_error, str(e))

    def _handle_progress(self, task: ExtractionTask) -> None:
        """Handle progress update from extraction engine.

        This is called from the worker thread. We use GLib.idle_add to
        safely update the UI from the main thread.
        """
        # Update progress tracker for speed/ETA
        stats = self._tracker.update(task.extracted_bytes)

        # Schedule UI update on main thread
        GLib.idle_add(self._report_progress, task, stats)

    def _report_progress(
        self, task: ExtractionTask, stats: ProgressStats
    ) -> bool:
        """Report progress to callback (runs on main thread)."""
        try:
            self._on_progress(task, stats)
        except Exception as e:
            logger.exception("Error in progress callback: %s", e)
        return False  # Don't repeat

    def _report_complete(self, success: bool) -> bool:
        """Report completion to callback (runs on main thread)."""
        try:
            logger.info(
                "Extraction %s for %s",
                "completed" if success else "failed",
                self._task.archive_path.name,
            )
            self._on_complete(self._task, success)
        except Exception as e:
            logger.exception("Error in completion callback: %s", e)
        return False  # Don't repeat

    def _report_error(self, error_message: str) -> bool:
        """Report error to callback (runs on main thread)."""
        try:
            self._task.status = TaskStatus.FAILED
            self._task.error_message = error_message
            self._on_error(self._task, error_message)
        except Exception as e:
            logger.exception("Error in error callback: %s", e)
        return False  # Don't repeat


class BatchExtractionWorker:
    """Manages extraction of multiple archives sequentially.

    This worker processes a list of extraction tasks one at a time,
    reporting progress for each task and overall batch progress.

    Example:
        >>> worker = BatchExtractionWorker(
        ...     tasks=task_list,
        ...     on_task_progress=update_task_progress,
        ...     on_task_complete=mark_task_done,
        ...     on_batch_complete=show_summary,
        ... )
        >>> worker.start()
    """

    def __init__(
        self,
        tasks: list[ExtractionTask],
        on_task_progress: Callable[[ExtractionTask, ProgressStats, int, int], None],
        on_task_complete: Callable[[ExtractionTask, bool, int, int], None],
        on_batch_complete: Callable[[list[ExtractionTask]], None],
        on_error: Callable[[ExtractionTask, str], None],
    ) -> None:
        """Initialize the batch extraction worker.

        Args:
            tasks: List of extraction tasks to process.
            on_task_progress: Callback for individual task progress.
                Args: (task, stats, task_index, total_tasks)
            on_task_complete: Callback when a task completes.
                Args: (task, success, task_index, total_tasks)
            on_batch_complete: Callback when all tasks complete.
                Args: (all_tasks)
            on_error: Callback when an error occurs.
        """
        self._tasks = tasks
        self._on_task_progress = on_task_progress
        self._on_task_complete = on_task_complete
        self._on_batch_complete = on_batch_complete
        self._on_error = on_error

        self._current_worker: ExtractionWorker | None = None
        self._current_index = 0
        self._cancelled = False
        self._paused = False

    @property
    def tasks(self) -> list[ExtractionTask]:
        """Get the list of tasks."""
        return self._tasks

    @property
    def current_task(self) -> ExtractionTask | None:
        """Get the currently executing task."""
        if 0 <= self._current_index < len(self._tasks):
            return self._tasks[self._current_index]
        return None

    @property
    def completed_count(self) -> int:
        """Get the number of completed tasks."""
        return sum(
            1 for t in self._tasks
            if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
        )

    @property
    def overall_progress(self) -> float:
        """Get overall batch progress as percentage (0-100)."""
        if not self._tasks:
            return 0.0

        total_bytes = sum(t.total_bytes for t in self._tasks)
        extracted_bytes = sum(t.extracted_bytes for t in self._tasks)

        if total_bytes == 0:
            return 0.0

        return (extracted_bytes / total_bytes) * 100

    @property
    def is_running(self) -> bool:
        """Check if the batch is currently running."""
        return self._current_worker is not None and self._current_worker.is_running

    def start(self) -> None:
        """Start processing the batch."""
        if not self._tasks:
            logger.warning("No tasks to process")
            GLib.idle_add(self._report_batch_complete)
            return

        self._cancelled = False
        self._paused = False
        self._current_index = 0
        self._start_next_task()

    def cancel_all(self) -> None:
        """Cancel all remaining extractions."""
        logger.info("Batch cancellation requested")
        self._cancelled = True
        if self._current_worker:
            self._current_worker.cancel()

    def pause_all(self) -> None:
        """Pause the current extraction."""
        logger.info("Batch pause requested")
        self._paused = True
        if self._current_worker:
            self._current_worker.pause()

    def resume_all(self) -> None:
        """Resume the paused extraction."""
        logger.info("Batch resume requested")
        self._paused = False
        if self._current_worker:
            self._current_worker.resume()

    def _start_next_task(self) -> None:
        """Start extraction of the next task in the queue."""
        if self._cancelled:
            logger.info("Batch cancelled, marking remaining tasks")
            for i in range(self._current_index, len(self._tasks)):
                self._tasks[i].status = TaskStatus.CANCELLED
            GLib.idle_add(self._report_batch_complete)
            return

        if self._current_index >= len(self._tasks):
            logger.info("Batch complete, all tasks processed")
            GLib.idle_add(self._report_batch_complete)
            return

        task = self._tasks[self._current_index]
        logger.info(
            "Starting task %d of %d: %s",
            self._current_index + 1,
            len(self._tasks),
            task.archive_path.name,
        )

        self._current_worker = ExtractionWorker(
            task=task,
            on_progress=self._handle_task_progress,
            on_complete=self._handle_task_complete,
            on_error=self._handle_task_error,
        )
        self._current_worker.start()

    def _handle_task_progress(
        self, task: ExtractionTask, stats: ProgressStats
    ) -> None:
        """Handle progress update from current task."""
        try:
            self._on_task_progress(
                task, stats, self._current_index, len(self._tasks)
            )
        except Exception as e:
            logger.exception("Error in task progress callback: %s", e)

    def _handle_task_complete(self, task: ExtractionTask, success: bool) -> None:
        """Handle completion of current task."""
        try:
            self._on_task_complete(
                task, success, self._current_index, len(self._tasks)
            )
        except Exception as e:
            logger.exception("Error in task complete callback: %s", e)

        # Move to next task
        self._current_index += 1
        self._current_worker = None

        # Start next task (on main thread to avoid race conditions)
        GLib.idle_add(self._start_next_task)

    def _handle_task_error(self, task: ExtractionTask, error: str) -> None:
        """Handle error in current task."""
        try:
            self._on_error(task, error)
        except Exception as e:
            logger.exception("Error in task error callback: %s", e)

        # Move to next task despite error
        self._current_index += 1
        self._current_worker = None
        GLib.idle_add(self._start_next_task)

    def _report_batch_complete(self) -> bool:
        """Report batch completion to callback."""
        try:
            self._on_batch_complete(self._tasks)
        except Exception as e:
            logger.exception("Error in batch complete callback: %s", e)
        return False


def create_extraction_task(
    archive_path: Path,
    destination_path: Path,
    conflict_resolution: ConflictResolution | None = None,
    create_root_folder: bool = False,
    preserve_timestamps: bool = True,
    preserve_permissions: bool = True,
) -> ExtractionTask:
    """Factory function to create an ExtractionTask with auto-generated ID.

    Args:
        archive_path: Path to the ZIP archive.
        destination_path: Path to extract files to.
        conflict_resolution: How to handle file conflicts.
        create_root_folder: Whether to create a root folder for extraction.
        preserve_timestamps: Whether to preserve file timestamps.
        preserve_permissions: Whether to preserve file permissions.

    Returns:
        A new ExtractionTask instance.
    """
    from zipextractor.core.models import ConflictResolution as CR

    return ExtractionTask(
        task_id=str(uuid.uuid4()),
        archive_path=archive_path,
        destination_path=destination_path,
        status=TaskStatus.QUEUED,
        conflict_resolution=conflict_resolution or CR.ASK,
        create_root_folder=create_root_folder,
        preserve_timestamps=preserve_timestamps,
        preserve_permissions=preserve_permissions,
    )
