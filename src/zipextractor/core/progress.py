"""Progress tracking for extraction operations."""

from __future__ import annotations

import time

from zipextractor.core.models import ProgressStats


class ProgressTracker:
    """Tracks extraction progress and calculates speed/ETA."""

    def __init__(self, window_size: int = 10) -> None:
        """Initialize tracker with rolling window for speed averaging.

        Args:
            window_size: Number of samples to use for rolling average speed calculation.
        """
        self._start_time: float | None = None
        self._samples: list[tuple[float, int]] = []  # (timestamp, bytes)
        self._window_size = window_size
        self._total_bytes = 0
        self._extracted_bytes = 0

    def start(self, total_bytes: int) -> None:
        """Start tracking progress.

        Args:
            total_bytes: Total bytes to be extracted.
        """
        self._start_time = time.time()
        self._total_bytes = total_bytes
        self._extracted_bytes = 0
        self._samples.clear()

    def update(self, extracted_bytes: int) -> ProgressStats:
        """Update progress and return current stats.

        Args:
            extracted_bytes: Total bytes extracted so far.

        Returns:
            ProgressStats with current_speed_mbps, average_speed_mbps, eta_seconds, elapsed_seconds.
        """
        current_time = time.time()
        self._extracted_bytes = extracted_bytes

        # Add sample to rolling window
        self._samples.append((current_time, extracted_bytes))

        # Keep only window_size samples
        if len(self._samples) > self._window_size:
            self._samples = self._samples[-self._window_size :]

        # Calculate elapsed time
        elapsed_seconds = 0
        if self._start_time is not None:
            elapsed_seconds = int(current_time - self._start_time)

        # Calculate current speed (instant speed based on last two samples)
        current_speed_mbps = 0.0
        if len(self._samples) >= 2:
            recent_sample = self._samples[-1]
            previous_sample = self._samples[-2]
            time_diff = recent_sample[0] - previous_sample[0]
            bytes_diff = recent_sample[1] - previous_sample[1]
            if time_diff > 0:
                # Convert bytes/second to MB/s (1 MB = 1024 * 1024 bytes)
                current_speed_mbps = (bytes_diff / time_diff) / (1024 * 1024)

        # Calculate average speed over rolling window
        average_speed_mbps = 0.0
        if len(self._samples) >= 2:
            first_sample = self._samples[0]
            last_sample = self._samples[-1]
            time_diff = last_sample[0] - first_sample[0]
            bytes_diff = last_sample[1] - first_sample[1]
            if time_diff > 0:
                average_speed_mbps = (bytes_diff / time_diff) / (1024 * 1024)

        # Calculate ETA based on average speed
        eta_seconds = 0
        remaining_bytes = self._total_bytes - self._extracted_bytes
        if average_speed_mbps > 0 and remaining_bytes > 0:
            # Convert MB/s back to bytes/s for calculation
            average_speed_bytes = average_speed_mbps * 1024 * 1024
            eta_seconds = int(remaining_bytes / average_speed_bytes)

        return ProgressStats(
            current_speed_mbps=max(0.0, current_speed_mbps),
            average_speed_mbps=max(0.0, average_speed_mbps),
            eta_seconds=max(0, eta_seconds),
            elapsed_seconds=max(0, elapsed_seconds),
        )

    def reset(self) -> None:
        """Reset tracker state."""
        self._start_time = None
        self._samples.clear()
        self._total_bytes = 0
        self._extracted_bytes = 0
