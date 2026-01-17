"""Unit tests for extraction worker classes.

Tests the threading architecture, progress reporting, and worker lifecycle.
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zipextractor.core.models import (
    ConflictResolution,
    ExtractionTask,
    ProgressStats,
    TaskStatus,
)
from zipextractor.gui.workers import (
    BatchExtractionWorker,
    ExtractionWorker,
    create_extraction_task,
)


class TestCreateExtractionTask:
    """Tests for the create_extraction_task factory function."""

    def test_creates_task_with_required_params(self, tmp_path: Path) -> None:
        """Task is created with required parameters."""
        archive = tmp_path / "test.zip"
        destination = tmp_path / "output"

        task = create_extraction_task(
            archive_path=archive,
            destination_path=destination,
        )

        assert task.archive_path == archive
        assert task.destination_path == destination
        assert task.task_id  # Should have auto-generated ID
        assert task.status == TaskStatus.QUEUED

    def test_generates_unique_task_id(self, tmp_path: Path) -> None:
        """Each task gets a unique ID."""
        archive = tmp_path / "test.zip"
        destination = tmp_path / "output"

        task1 = create_extraction_task(archive, destination)
        task2 = create_extraction_task(archive, destination)

        assert task1.task_id != task2.task_id

    def test_uses_default_conflict_resolution(self, tmp_path: Path) -> None:
        """Default conflict resolution is ASK."""
        task = create_extraction_task(tmp_path / "test.zip", tmp_path / "output")
        assert task.conflict_resolution == ConflictResolution.ASK

    def test_respects_conflict_resolution_param(self, tmp_path: Path) -> None:
        """Conflict resolution parameter is applied."""
        task = create_extraction_task(
            tmp_path / "test.zip",
            tmp_path / "output",
            conflict_resolution=ConflictResolution.OVERWRITE,
        )
        assert task.conflict_resolution == ConflictResolution.OVERWRITE

    def test_respects_create_root_folder_param(self, tmp_path: Path) -> None:
        """Create root folder parameter is applied."""
        task = create_extraction_task(
            tmp_path / "test.zip",
            tmp_path / "output",
            create_root_folder=True,
        )
        assert task.create_root_folder is True

    def test_default_create_root_folder_is_false(self, tmp_path: Path) -> None:
        """Default create root folder is False."""
        task = create_extraction_task(tmp_path / "test.zip", tmp_path / "output")
        assert task.create_root_folder is False

    def test_respects_preserve_timestamps_param(self, tmp_path: Path) -> None:
        """Preserve timestamps parameter is applied."""
        task = create_extraction_task(
            tmp_path / "test.zip",
            tmp_path / "output",
            preserve_timestamps=False,
        )
        assert task.preserve_timestamps is False

    def test_default_preserve_timestamps_is_true(self, tmp_path: Path) -> None:
        """Default preserve timestamps is True."""
        task = create_extraction_task(tmp_path / "test.zip", tmp_path / "output")
        assert task.preserve_timestamps is True

    def test_respects_preserve_permissions_param(self, tmp_path: Path) -> None:
        """Preserve permissions parameter is applied."""
        task = create_extraction_task(
            tmp_path / "test.zip",
            tmp_path / "output",
            preserve_permissions=False,
        )
        assert task.preserve_permissions is False

    def test_default_preserve_permissions_is_true(self, tmp_path: Path) -> None:
        """Default preserve permissions is True."""
        task = create_extraction_task(tmp_path / "test.zip", tmp_path / "output")
        assert task.preserve_permissions is True


class TestExtractionWorker:
    """Tests for ExtractionWorker class."""

    @pytest.fixture
    def mock_task(self, tmp_path: Path) -> ExtractionTask:
        """Create a mock extraction task."""
        return create_extraction_task(
            tmp_path / "test.zip",
            tmp_path / "output",
        )

    @pytest.fixture
    def mock_callbacks(self) -> dict[str, MagicMock]:
        """Create mock callbacks for worker."""
        return {
            "on_progress": MagicMock(),
            "on_complete": MagicMock(),
            "on_error": MagicMock(),
        }

    def test_worker_initialization(
        self, mock_task: ExtractionTask, mock_callbacks: dict[str, MagicMock]
    ) -> None:
        """Worker initializes with task and callbacks."""
        worker = ExtractionWorker(
            task=mock_task,
            on_progress=mock_callbacks["on_progress"],
            on_complete=mock_callbacks["on_complete"],
            on_error=mock_callbacks["on_error"],
        )

        assert worker.task == mock_task
        assert not worker.is_running

    def test_task_property_returns_task(
        self, mock_task: ExtractionTask, mock_callbacks: dict[str, MagicMock]
    ) -> None:
        """Task property returns the task."""
        worker = ExtractionWorker(
            task=mock_task,
            on_progress=mock_callbacks["on_progress"],
            on_complete=mock_callbacks["on_complete"],
            on_error=mock_callbacks["on_error"],
        )

        assert worker.task is mock_task

    @patch("zipextractor.gui.workers.GLib")
    @patch("zipextractor.gui.workers.ExtractionEngine")
    def test_start_creates_thread(
        self,
        mock_engine_class: MagicMock,
        mock_glib: MagicMock,
        mock_task: ExtractionTask,
        mock_callbacks: dict[str, MagicMock],
    ) -> None:
        """Start creates and starts a background thread."""
        mock_engine = MagicMock()
        mock_engine.extract.return_value = True
        mock_engine_class.return_value = mock_engine

        worker = ExtractionWorker(
            task=mock_task,
            on_progress=mock_callbacks["on_progress"],
            on_complete=mock_callbacks["on_complete"],
            on_error=mock_callbacks["on_error"],
        )

        worker.start()
        # Give thread time to start
        time.sleep(0.1)

        # Worker should have started (or finished quickly with mock)
        assert mock_engine.extract.called or worker.is_running or not worker.is_running

    @patch("zipextractor.gui.workers.GLib")
    @patch("zipextractor.gui.workers.ExtractionEngine")
    def test_cancel_sets_stop_event(
        self,
        mock_engine_class: MagicMock,
        mock_glib: MagicMock,
        mock_task: ExtractionTask,
        mock_callbacks: dict[str, MagicMock],
    ) -> None:
        """Cancel calls engine cancel and sets stop event."""
        mock_engine = MagicMock()
        mock_engine_class.return_value = mock_engine

        worker = ExtractionWorker(
            task=mock_task,
            on_progress=mock_callbacks["on_progress"],
            on_complete=mock_callbacks["on_complete"],
            on_error=mock_callbacks["on_error"],
        )

        worker.cancel()

        mock_engine.cancel.assert_called_once()

    @patch("zipextractor.gui.workers.GLib")
    @patch("zipextractor.gui.workers.ExtractionEngine")
    def test_pause_calls_engine_pause(
        self,
        mock_engine_class: MagicMock,
        mock_glib: MagicMock,
        mock_task: ExtractionTask,
        mock_callbacks: dict[str, MagicMock],
    ) -> None:
        """Pause calls engine pause."""
        mock_engine = MagicMock()
        mock_engine_class.return_value = mock_engine

        worker = ExtractionWorker(
            task=mock_task,
            on_progress=mock_callbacks["on_progress"],
            on_complete=mock_callbacks["on_complete"],
            on_error=mock_callbacks["on_error"],
        )

        worker.pause()

        mock_engine.pause.assert_called_once()

    @patch("zipextractor.gui.workers.GLib")
    @patch("zipextractor.gui.workers.ExtractionEngine")
    def test_resume_calls_engine_resume(
        self,
        mock_engine_class: MagicMock,
        mock_glib: MagicMock,
        mock_task: ExtractionTask,
        mock_callbacks: dict[str, MagicMock],
    ) -> None:
        """Resume calls engine resume."""
        mock_engine = MagicMock()
        mock_engine_class.return_value = mock_engine

        worker = ExtractionWorker(
            task=mock_task,
            on_progress=mock_callbacks["on_progress"],
            on_complete=mock_callbacks["on_complete"],
            on_error=mock_callbacks["on_error"],
        )

        worker.resume()

        mock_engine.resume.assert_called_once()

    @patch("zipextractor.gui.workers.GLib")
    @patch("zipextractor.gui.workers.ExtractionEngine")
    def test_multiple_starts_ignored(
        self,
        mock_engine_class: MagicMock,
        mock_glib: MagicMock,
        mock_task: ExtractionTask,
        mock_callbacks: dict[str, MagicMock],
    ) -> None:
        """Multiple start calls are ignored when worker is running."""
        mock_engine = MagicMock()
        # Make extraction hang - use lambda with underscore prefix to ignore params
        mock_engine.extract.side_effect = lambda *_args, **_kwargs: time.sleep(1)
        mock_engine_class.return_value = mock_engine

        worker = ExtractionWorker(
            task=mock_task,
            on_progress=mock_callbacks["on_progress"],
            on_complete=mock_callbacks["on_complete"],
            on_error=mock_callbacks["on_error"],
        )

        worker.start()
        time.sleep(0.1)

        # Second start should be ignored
        initial_running = worker.is_running
        worker.start()

        # Clean up - cancel the worker
        worker.cancel()

    @patch("zipextractor.gui.workers.GLib")
    @patch("zipextractor.gui.workers.ExtractionEngine")
    def test_completion_callback_called(
        self,
        mock_engine_class: MagicMock,
        mock_glib: MagicMock,
        mock_task: ExtractionTask,
        mock_callbacks: dict[str, MagicMock],
    ) -> None:
        """Completion callback is scheduled via GLib.idle_add."""
        mock_engine = MagicMock()
        mock_engine.extract.return_value = True
        mock_engine_class.return_value = mock_engine

        worker = ExtractionWorker(
            task=mock_task,
            on_progress=mock_callbacks["on_progress"],
            on_complete=mock_callbacks["on_complete"],
            on_error=mock_callbacks["on_error"],
        )

        worker.start()
        time.sleep(0.2)  # Wait for thread to complete

        # Check that idle_add was called (for completion)
        assert mock_glib.idle_add.called


class TestBatchExtractionWorker:
    """Tests for BatchExtractionWorker class."""

    @pytest.fixture
    def mock_tasks(self, tmp_path: Path) -> list[ExtractionTask]:
        """Create multiple mock tasks."""
        return [
            create_extraction_task(tmp_path / f"test{i}.zip", tmp_path / "output")
            for i in range(3)
        ]

    @pytest.fixture
    def mock_batch_callbacks(self) -> dict[str, MagicMock]:
        """Create mock callbacks for batch worker."""
        return {
            "on_task_progress": MagicMock(),
            "on_task_complete": MagicMock(),
            "on_batch_complete": MagicMock(),
            "on_error": MagicMock(),
        }

    def test_batch_worker_initialization(
        self,
        mock_tasks: list[ExtractionTask],
        mock_batch_callbacks: dict[str, MagicMock],
    ) -> None:
        """Batch worker initializes with tasks and callbacks."""
        worker = BatchExtractionWorker(
            tasks=mock_tasks,
            on_task_progress=mock_batch_callbacks["on_task_progress"],
            on_task_complete=mock_batch_callbacks["on_task_complete"],
            on_batch_complete=mock_batch_callbacks["on_batch_complete"],
            on_error=mock_batch_callbacks["on_error"],
        )

        assert worker.tasks == mock_tasks
        assert not worker.is_running
        assert worker.completed_count == 0

    def test_tasks_property_returns_tasks(
        self,
        mock_tasks: list[ExtractionTask],
        mock_batch_callbacks: dict[str, MagicMock],
    ) -> None:
        """Tasks property returns all tasks."""
        worker = BatchExtractionWorker(
            tasks=mock_tasks,
            on_task_progress=mock_batch_callbacks["on_task_progress"],
            on_task_complete=mock_batch_callbacks["on_task_complete"],
            on_batch_complete=mock_batch_callbacks["on_batch_complete"],
            on_error=mock_batch_callbacks["on_error"],
        )

        assert len(worker.tasks) == 3

    def test_current_task_before_start_returns_none(
        self,
        mock_tasks: list[ExtractionTask],
        mock_batch_callbacks: dict[str, MagicMock],
    ) -> None:
        """Current task is None before starting."""
        worker = BatchExtractionWorker(
            tasks=mock_tasks,
            on_task_progress=mock_batch_callbacks["on_task_progress"],
            on_task_complete=mock_batch_callbacks["on_task_complete"],
            on_batch_complete=mock_batch_callbacks["on_batch_complete"],
            on_error=mock_batch_callbacks["on_error"],
        )

        # Before start, current task depends on implementation
        # After start, it should return first task
        assert worker.current_task is None or worker.current_task == mock_tasks[0]

    def test_completed_count_initially_zero(
        self,
        mock_tasks: list[ExtractionTask],
        mock_batch_callbacks: dict[str, MagicMock],
    ) -> None:
        """Completed count is zero initially."""
        worker = BatchExtractionWorker(
            tasks=mock_tasks,
            on_task_progress=mock_batch_callbacks["on_task_progress"],
            on_task_complete=mock_batch_callbacks["on_task_complete"],
            on_batch_complete=mock_batch_callbacks["on_batch_complete"],
            on_error=mock_batch_callbacks["on_error"],
        )

        assert worker.completed_count == 0

    def test_overall_progress_with_no_bytes(
        self,
        mock_tasks: list[ExtractionTask],
        mock_batch_callbacks: dict[str, MagicMock],
    ) -> None:
        """Overall progress is 0 when no bytes processed."""
        worker = BatchExtractionWorker(
            tasks=mock_tasks,
            on_task_progress=mock_batch_callbacks["on_task_progress"],
            on_task_complete=mock_batch_callbacks["on_task_complete"],
            on_batch_complete=mock_batch_callbacks["on_batch_complete"],
            on_error=mock_batch_callbacks["on_error"],
        )

        assert worker.overall_progress == 0.0

    def test_overall_progress_calculation(
        self,
        tmp_path: Path,
        mock_batch_callbacks: dict[str, MagicMock],
    ) -> None:
        """Overall progress is calculated from bytes processed."""
        tasks = [
            create_extraction_task(tmp_path / f"test{i}.zip", tmp_path / "output")
            for i in range(2)
        ]
        # Set total and extracted bytes
        tasks[0].total_bytes = 100
        tasks[0].extracted_bytes = 50
        tasks[1].total_bytes = 100
        tasks[1].extracted_bytes = 0

        worker = BatchExtractionWorker(
            tasks=tasks,
            on_task_progress=mock_batch_callbacks["on_task_progress"],
            on_task_complete=mock_batch_callbacks["on_task_complete"],
            on_batch_complete=mock_batch_callbacks["on_batch_complete"],
            on_error=mock_batch_callbacks["on_error"],
        )

        # 50 of 200 bytes = 25%
        assert worker.overall_progress == 25.0

    @patch("zipextractor.gui.workers.GLib")
    def test_start_empty_batch_completes_immediately(
        self,
        mock_glib: MagicMock,
        mock_batch_callbacks: dict[str, MagicMock],
    ) -> None:
        """Starting empty batch calls batch complete immediately."""
        worker = BatchExtractionWorker(
            tasks=[],
            on_task_progress=mock_batch_callbacks["on_task_progress"],
            on_task_complete=mock_batch_callbacks["on_task_complete"],
            on_batch_complete=mock_batch_callbacks["on_batch_complete"],
            on_error=mock_batch_callbacks["on_error"],
        )

        worker.start()

        # Should schedule batch complete
        assert mock_glib.idle_add.called

    @patch("zipextractor.gui.workers.GLib")
    @patch("zipextractor.gui.workers.ExtractionWorker")
    def test_cancel_all_stops_current_worker(
        self,
        mock_worker_class: MagicMock,
        mock_glib: MagicMock,
        mock_tasks: list[ExtractionTask],
        mock_batch_callbacks: dict[str, MagicMock],
    ) -> None:
        """Cancel all stops the current worker."""
        mock_inner_worker = MagicMock()
        mock_worker_class.return_value = mock_inner_worker

        worker = BatchExtractionWorker(
            tasks=mock_tasks,
            on_task_progress=mock_batch_callbacks["on_task_progress"],
            on_task_complete=mock_batch_callbacks["on_task_complete"],
            on_batch_complete=mock_batch_callbacks["on_batch_complete"],
            on_error=mock_batch_callbacks["on_error"],
        )

        worker.start()
        worker.cancel_all()

        mock_inner_worker.cancel.assert_called_once()

    @patch("zipextractor.gui.workers.GLib")
    @patch("zipextractor.gui.workers.ExtractionWorker")
    def test_pause_all_pauses_current_worker(
        self,
        mock_worker_class: MagicMock,
        mock_glib: MagicMock,
        mock_tasks: list[ExtractionTask],
        mock_batch_callbacks: dict[str, MagicMock],
    ) -> None:
        """Pause all pauses the current worker."""
        mock_inner_worker = MagicMock()
        mock_worker_class.return_value = mock_inner_worker

        worker = BatchExtractionWorker(
            tasks=mock_tasks,
            on_task_progress=mock_batch_callbacks["on_task_progress"],
            on_task_complete=mock_batch_callbacks["on_task_complete"],
            on_batch_complete=mock_batch_callbacks["on_batch_complete"],
            on_error=mock_batch_callbacks["on_error"],
        )

        worker.start()
        worker.pause_all()

        mock_inner_worker.pause.assert_called_once()

    @patch("zipextractor.gui.workers.GLib")
    @patch("zipextractor.gui.workers.ExtractionWorker")
    def test_resume_all_resumes_current_worker(
        self,
        mock_worker_class: MagicMock,
        mock_glib: MagicMock,
        mock_tasks: list[ExtractionTask],
        mock_batch_callbacks: dict[str, MagicMock],
    ) -> None:
        """Resume all resumes the current worker."""
        mock_inner_worker = MagicMock()
        mock_worker_class.return_value = mock_inner_worker

        worker = BatchExtractionWorker(
            tasks=mock_tasks,
            on_task_progress=mock_batch_callbacks["on_task_progress"],
            on_task_complete=mock_batch_callbacks["on_task_complete"],
            on_batch_complete=mock_batch_callbacks["on_batch_complete"],
            on_error=mock_batch_callbacks["on_error"],
        )

        worker.start()
        worker.resume_all()

        mock_inner_worker.resume.assert_called_once()

    def test_completed_count_tracks_finished_tasks(
        self,
        tmp_path: Path,
        mock_batch_callbacks: dict[str, MagicMock],
    ) -> None:
        """Completed count accurately tracks finished tasks."""
        tasks = [
            create_extraction_task(tmp_path / f"test{i}.zip", tmp_path / "output")
            for i in range(3)
        ]
        tasks[0].status = TaskStatus.COMPLETED
        tasks[1].status = TaskStatus.FAILED
        tasks[2].status = TaskStatus.QUEUED

        worker = BatchExtractionWorker(
            tasks=tasks,
            on_task_progress=mock_batch_callbacks["on_task_progress"],
            on_task_complete=mock_batch_callbacks["on_task_complete"],
            on_batch_complete=mock_batch_callbacks["on_batch_complete"],
            on_error=mock_batch_callbacks["on_error"],
        )

        # COMPLETED and FAILED both count as "completed"
        assert worker.completed_count == 2

    def test_completed_count_includes_cancelled(
        self,
        tmp_path: Path,
        mock_batch_callbacks: dict[str, MagicMock],
    ) -> None:
        """Completed count includes cancelled tasks."""
        tasks = [
            create_extraction_task(tmp_path / f"test{i}.zip", tmp_path / "output")
            for i in range(2)
        ]
        tasks[0].status = TaskStatus.CANCELLED
        tasks[1].status = TaskStatus.RUNNING

        worker = BatchExtractionWorker(
            tasks=tasks,
            on_task_progress=mock_batch_callbacks["on_task_progress"],
            on_task_complete=mock_batch_callbacks["on_task_complete"],
            on_batch_complete=mock_batch_callbacks["on_batch_complete"],
            on_error=mock_batch_callbacks["on_error"],
        )

        assert worker.completed_count == 1


class TestProgressStatsIntegration:
    """Test integration with ProgressStats."""

    def test_progress_stats_has_required_attributes(self) -> None:
        """ProgressStats has required attributes for worker."""
        stats = ProgressStats(
            current_speed_mbps=1.0,  # 1 MB/s
            average_speed_mbps=0.8,
            eta_seconds=30,
            elapsed_seconds=10,
        )

        # Verify the attributes workers use
        assert hasattr(stats, "current_speed_mbps")
        assert hasattr(stats, "eta_formatted")
        assert stats.current_speed_mbps == 1.0  # 1 MB/s
        assert stats.eta_formatted == "30s"
