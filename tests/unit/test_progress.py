"""Unit tests for ProgressTracker class.

Tests for:
- ProgressTracker initialization
- Speed calculation
- ETA calculation
- Edge cases

TDD: These tests are written first, before implementation.
"""

import time

import pytest

from zipextractor.core.models import ProgressStats
from zipextractor.core.progress import ProgressTracker


class TestProgressTrackerCreation:
    """Tests for ProgressTracker initialization."""

    def test_progress_tracker_creation(self) -> None:
        """ProgressTracker should be creatable with no arguments."""
        tracker = ProgressTracker()
        assert tracker is not None
        assert isinstance(tracker, ProgressTracker)

    def test_progress_start_initializes(self) -> None:
        """start() should initialize start time and zero counters."""
        tracker = ProgressTracker()
        total_bytes = 100 * 1024 * 1024  # 100 MB

        tracker.start(total_bytes)

        assert tracker._start_time is not None
        assert tracker._extracted_bytes == 0
        assert tracker._total_bytes == total_bytes
        assert tracker._samples == []


class TestProgressSpeedCalculation:
    """Tests for speed calculation functionality."""

    def test_progress_update_calculates_speed(self) -> None:
        """update() should calculate correct MB/s speed."""
        tracker = ProgressTracker()
        total_bytes = 100 * 1024 * 1024  # 100 MB
        tracker.start(total_bytes)

        # Simulate time passing by manipulating samples directly
        start_time = time.time()
        tracker._start_time = start_time - 2  # 2 seconds ago

        # Add first sample (at t=0, 0 bytes)
        tracker._samples.append((start_time - 1, 0))

        # Update with 10 MB processed (should calculate ~10 MB/s)
        bytes_processed = 10 * 1024 * 1024  # 10 MB
        stats = tracker.update(bytes_processed)

        # Speed should be approximately 10 MB/s
        assert stats.current_speed_mbps == pytest.approx(10.0, rel=0.2)

    def test_progress_update_returns_progress_stats(self) -> None:
        """update() should return a ProgressStats object."""
        tracker = ProgressTracker()
        tracker.start(10240)

        stats = tracker.update(1024)

        assert isinstance(stats, ProgressStats)
        assert hasattr(stats, "current_speed_mbps")
        assert hasattr(stats, "average_speed_mbps")
        assert hasattr(stats, "eta_seconds")
        assert hasattr(stats, "elapsed_seconds")

    def test_progress_rolling_average(self) -> None:
        """update() should use samples for rolling average speed."""
        tracker = ProgressTracker(window_size=5)
        total_bytes = 100 * 1024 * 1024  # 100 MB
        tracker.start(total_bytes)

        base_time = time.time()
        tracker._start_time = base_time - 10

        # Simulate multiple updates with 1 second intervals
        for i in range(10):
            # Manually set up samples to simulate time progression
            tracker._samples = []
            for j in range(min(i + 1, 5)):
                sample_time = base_time - (min(i + 1, 5) - j)
                sample_bytes = (i - min(i, 4) + j + 1) * 1024 * 1024
                tracker._samples.append((sample_time, sample_bytes))

            extracted = (i + 1) * 1024 * 1024
            stats = tracker.update(extracted)

        # After many updates, should only have window_size samples
        assert len(tracker._samples) <= 5

        # Average speed should be based on the samples
        if len(tracker._samples) >= 2:
            first = tracker._samples[0]
            last = tracker._samples[-1]
            time_diff = last[0] - first[0]
            bytes_diff = last[1] - first[1]
            if time_diff > 0:
                expected_avg = (bytes_diff / time_diff) / (1024 * 1024)
                assert stats.average_speed_mbps == pytest.approx(expected_avg, rel=0.1)


class TestProgressETACalculation:
    """Tests for ETA calculation functionality."""

    def test_progress_eta_calculation(self) -> None:
        """update() should calculate accurate remaining time estimate."""
        tracker = ProgressTracker()
        total_bytes = 100 * 1024 * 1024  # 100 MB
        tracker.start(total_bytes)

        base_time = time.time()
        tracker._start_time = base_time - 5

        # Set up samples: 40 MB at t-1, current will be 50 MB
        tracker._samples = [
            (base_time - 1, 40 * 1024 * 1024),
        ]

        extracted = 50 * 1024 * 1024  # 50 MB
        stats = tracker.update(extracted)

        # With ~10 MB/s speed and 50 MB remaining, ETA should be ~5 seconds
        assert stats.eta_seconds >= 0
        # ETA should be reasonable
        assert stats.eta_seconds < 3600

    def test_progress_eta_zero_speed(self) -> None:
        """update() should handle zero speed gracefully."""
        tracker = ProgressTracker()
        tracker.start(1000)

        # First update with 0 bytes - no previous sample, so no speed calculation
        stats = tracker.update(0)

        # Should not crash, ETA should be 0 or a reasonable value
        assert stats.eta_seconds >= 0
        assert isinstance(stats.eta_seconds, int)


class TestProgressEdgeCases:
    """Tests for edge cases in ProgressTracker."""

    def test_progress_update_with_zero_bytes(self) -> None:
        """update() should handle zero bytes extracted."""
        tracker = ProgressTracker()
        tracker.start(1000)

        stats = tracker.update(0)

        assert stats.current_speed_mbps >= 0
        assert stats.average_speed_mbps >= 0
        assert stats.eta_seconds >= 0
        assert stats.elapsed_seconds >= 0

    def test_progress_multiple_updates(self) -> None:
        """update() should handle multiple sequential updates correctly."""
        tracker = ProgressTracker()
        total_bytes = 100 * 1024 * 1024  # 100 MB
        tracker.start(total_bytes)

        # Simulate multiple updates
        for i in range(1, 11):
            extracted = i * 10 * 1024 * 1024  # 10 MB increments
            stats = tracker.update(extracted)

            # Each update should produce valid stats
            assert stats.current_speed_mbps >= 0
            assert stats.average_speed_mbps >= 0
            assert stats.elapsed_seconds >= 0

        # After all updates, we should have samples
        assert len(tracker._samples) > 0

    def test_progress_reset(self) -> None:
        """reset() should reset the tracker state."""
        tracker = ProgressTracker()
        tracker.start(100 * 1024 * 1024)

        # Perform some updates
        tracker.update(50 * 1024 * 1024)

        # Verify state was modified
        assert len(tracker._samples) > 0
        assert tracker._extracted_bytes > 0

        # Reset the tracker
        tracker.reset()

        # State should be reset
        assert tracker._extracted_bytes == 0
        assert tracker._samples == []
        assert tracker._start_time is None
        assert tracker._total_bytes == 0


class TestProgressTrackerAttributes:
    """Tests for ProgressTracker attributes and configuration."""

    def test_progress_tracker_has_window_size(self) -> None:
        """ProgressTracker should have configurable window_size."""
        tracker = ProgressTracker(window_size=20)

        assert tracker._window_size == 20

    def test_progress_tracker_default_window_size(self) -> None:
        """ProgressTracker should have reasonable default window_size."""
        tracker = ProgressTracker()

        # Default should be 10 based on implementation
        assert tracker._window_size == 10

    def test_progress_tracker_has_start_time_initially_none(self) -> None:
        """ProgressTracker should have _start_time as None before start()."""
        tracker = ProgressTracker()

        assert tracker._start_time is None

    def test_progress_tracker_has_samples_initially_empty(self) -> None:
        """ProgressTracker should have empty _samples before start()."""
        tracker = ProgressTracker()

        assert tracker._samples == []


class TestProgressStatsElapsedTime:
    """Tests for elapsed time calculation."""

    def test_progress_elapsed_seconds_calculation(self) -> None:
        """update() should calculate elapsed seconds correctly."""
        tracker = ProgressTracker()
        tracker.start(100 * 1024 * 1024)

        # Simulate 5 seconds elapsed
        tracker._start_time = time.time() - 5
        stats = tracker.update(50 * 1024 * 1024)

        assert stats.elapsed_seconds == pytest.approx(5, abs=1)

    def test_progress_elapsed_seconds_increases(self) -> None:
        """elapsed_seconds should increase with each update."""
        tracker = ProgressTracker()
        tracker.start(100 * 1024 * 1024)

        base_time = time.time()
        elapsed_values = []

        for i in range(3):
            tracker._start_time = base_time - ((i + 1) * 2)
            stats = tracker.update((i + 1) * 10 * 1024 * 1024)
            elapsed_values.append(stats.elapsed_seconds)

        # Each elapsed time should be greater than previous
        for i in range(1, len(elapsed_values)):
            assert elapsed_values[i] >= elapsed_values[i - 1]


class TestProgressTrackerIntegration:
    """Integration tests for ProgressTracker with realistic scenarios."""

    def test_full_extraction_simulation(self) -> None:
        """Simulate a complete extraction process."""
        tracker = ProgressTracker()
        total_bytes = 50 * 1024 * 1024  # 50 MB
        tracker.start(total_bytes)

        # Simulate extraction in 10% increments
        for percent in range(10, 110, 10):
            extracted = int(total_bytes * percent / 100)
            stats = tracker.update(extracted)

            # Stats should always be valid
            assert stats.current_speed_mbps >= 0
            assert stats.average_speed_mbps >= 0
            assert stats.eta_seconds >= 0
            assert stats.elapsed_seconds >= 0

            # Progress should be tracked
            assert tracker._extracted_bytes == extracted

    def test_restart_tracking(self) -> None:
        """Tracker should support restarting for a new extraction."""
        tracker = ProgressTracker()

        # First extraction
        tracker.start(10 * 1024 * 1024)
        tracker.update(5 * 1024 * 1024)
        assert tracker._extracted_bytes == 5 * 1024 * 1024

        # Start new extraction (reset happens in start)
        tracker.start(20 * 1024 * 1024)
        assert tracker._extracted_bytes == 0
        assert tracker._total_bytes == 20 * 1024 * 1024
        assert tracker._samples == []
