"""Progress dialog for extraction operations.

This module provides a modal dialog that displays extraction progress
with file-level and overall progress bars, speed/ETA display, and
control buttons for pause/resume/cancel operations.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GObject, Gtk

from zipextractor.core.models import ExtractionTask, ProgressStats, TaskStatus
from zipextractor.utils.logging import get_logger

logger = get_logger(__name__)


class ProgressDialog(Adw.Window):
    """Modal dialog showing extraction progress.

    This dialog displays:
    - Archive name being extracted
    - Overall progress bar with percentage
    - Current file being extracted
    - Speed (MB/s) and ETA display
    - Files and bytes progress counters
    - Pause/Resume and Cancel buttons

    Signals:
        pause-clicked: Emitted when pause/resume button is clicked.
            Args: (is_paused: bool)
        cancel-clicked: Emitted when cancel button is clicked.

    Example:
        >>> dialog = ProgressDialog(parent=main_window, task=task)
        >>> dialog.connect("pause-clicked", on_pause)
        >>> dialog.connect("cancel-clicked", on_cancel)
        >>> dialog.present()
    """

    __gtype_name__ = "ProgressDialog"

    __gsignals__ = {
        "pause-clicked": (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
        "cancel-clicked": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(
        self,
        parent: Gtk.Window,
        task: ExtractionTask,
    ) -> None:
        """Initialize the progress dialog.

        Args:
            parent: Parent window for modal behavior.
            task: The extraction task to display progress for.
        """
        super().__init__(
            title="Extracting...",
            transient_for=parent,
            modal=True,
            default_width=450,
            default_height=-1,
            resizable=False,
        )

        self._task = task
        self._is_paused = False
        self._is_complete = False

        self._build_ui()
        self._update_display(task, None)

        logger.debug("Progress dialog created for %s", task.archive_path.name)

    def _build_ui(self) -> None:
        """Build the dialog UI."""
        # Main content box
        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            margin_top=24,
            margin_bottom=24,
            margin_start=24,
            margin_end=24,
        )

        # Header with archive name
        self._header = Adw.StatusPage(
            title="Extracting Archive",
            description=self._task.archive_path.name,
            icon_name="archive-extract-symbolic",
        )
        self._header.set_vexpand(False)
        content.append(self._header)

        # Progress section
        progress_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
        )

        # Overall progress
        overall_label = Gtk.Label(
            label="Overall Progress:",
            halign=Gtk.Align.START,
            css_classes=["heading"],
        )
        progress_box.append(overall_label)

        self._overall_progress = Gtk.ProgressBar(
            show_text=True,
            fraction=0.0,
        )
        progress_box.append(self._overall_progress)

        # Current file
        file_label = Gtk.Label(
            label="Current File:",
            halign=Gtk.Align.START,
            css_classes=["heading"],
            margin_top=8,
        )
        progress_box.append(file_label)

        self._current_file_label = Gtk.Label(
            label="Preparing...",
            halign=Gtk.Align.START,
            ellipsize=3,  # PANGO_ELLIPSIZE_END
            max_width_chars=50,
            css_classes=["dim-label"],
        )
        progress_box.append(self._current_file_label)

        content.append(progress_box)

        # Stats grid
        stats_grid = Gtk.Grid(
            column_spacing=24,
            row_spacing=8,
            margin_top=16,
        )

        # Files row
        files_title = Gtk.Label(
            label="Files:",
            halign=Gtk.Align.START,
            css_classes=["dim-label"],
        )
        stats_grid.attach(files_title, 0, 0, 1, 1)

        self._files_label = Gtk.Label(
            label="0 of 0",
            halign=Gtk.Align.START,
        )
        stats_grid.attach(self._files_label, 1, 0, 1, 1)

        # Size row
        size_title = Gtk.Label(
            label="Size:",
            halign=Gtk.Align.START,
            css_classes=["dim-label"],
        )
        stats_grid.attach(size_title, 0, 1, 1, 1)

        self._size_label = Gtk.Label(
            label="0 B of 0 B",
            halign=Gtk.Align.START,
        )
        stats_grid.attach(self._size_label, 1, 1, 1, 1)

        # Speed row
        speed_title = Gtk.Label(
            label="Speed:",
            halign=Gtk.Align.START,
            css_classes=["dim-label"],
        )
        stats_grid.attach(speed_title, 2, 0, 1, 1)

        self._speed_label = Gtk.Label(
            label="-- MB/s",
            halign=Gtk.Align.START,
            css_classes=["monospace"],
        )
        stats_grid.attach(self._speed_label, 3, 0, 1, 1)

        # ETA row
        eta_title = Gtk.Label(
            label="ETA:",
            halign=Gtk.Align.START,
            css_classes=["dim-label"],
        )
        stats_grid.attach(eta_title, 2, 1, 1, 1)

        self._eta_label = Gtk.Label(
            label="Calculating...",
            halign=Gtk.Align.START,
        )
        stats_grid.attach(self._eta_label, 3, 1, 1, 1)

        content.append(stats_grid)

        # Buttons
        button_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            halign=Gtk.Align.END,
            margin_top=16,
        )

        self._pause_button = Gtk.Button(
            label="Pause",
            css_classes=["pill"],
        )
        self._pause_button.connect("clicked", self._on_pause_clicked)
        button_box.append(self._pause_button)

        self._cancel_button = Gtk.Button(
            label="Cancel",
            css_classes=["pill", "destructive-action"],
        )
        self._cancel_button.connect("clicked", self._on_cancel_clicked)
        button_box.append(self._cancel_button)

        content.append(button_box)

        # Set content
        self.set_content(content)

    def update_progress(
        self, task: ExtractionTask, stats: ProgressStats | None
    ) -> None:
        """Update the progress display.

        This should be called from the main thread (via GLib.idle_add).

        Args:
            task: Updated extraction task with current progress.
            stats: Current progress statistics (speed, ETA).
        """
        if self._is_complete:
            return

        self._task = task
        self._update_display(task, stats)

    def _update_display(
        self, task: ExtractionTask, stats: ProgressStats | None
    ) -> None:
        """Internal method to update all display elements."""
        # Update progress bar
        progress = task.progress_percentage / 100.0
        self._overall_progress.set_fraction(progress)
        self._overall_progress.set_text(f"{task.progress_percentage:.1f}%")

        # Update current file
        if task.current_file:
            self._current_file_label.set_label(task.current_file)
        elif task.status == TaskStatus.COMPLETED:
            self._current_file_label.set_label("Complete!")
        elif task.status == TaskStatus.PAUSED:
            self._current_file_label.set_label("Paused")

        # Update files count
        self._files_label.set_label(
            f"{task.extracted_files} of {task.total_files}"
        )

        # Update size
        self._size_label.set_label(
            f"{self._format_bytes(task.extracted_bytes)} of "
            f"{self._format_bytes(task.total_bytes)}"
        )

        # Update speed and ETA
        if stats:
            self._speed_label.set_label(f"{stats.current_speed_mbps:.1f} MB/s")
            self._eta_label.set_label(stats.eta_formatted)

        # Update pause button based on status
        if task.status == TaskStatus.PAUSED:
            self._pause_button.set_label("Resume")
            self._is_paused = True
        elif task.status == TaskStatus.RUNNING:
            self._pause_button.set_label("Pause")
            self._is_paused = False

    def show_complete(self, success: bool, message: str) -> None:
        """Show completion state.

        Args:
            success: Whether extraction was successful.
            message: Message to display (success or error message).
        """
        self._is_complete = True

        # Update header
        if success:
            self._header.set_title("Extraction Complete")
            self._header.set_icon_name("emblem-ok-symbolic")
            self._overall_progress.add_css_class("success")
        else:
            self._header.set_title("Extraction Failed")
            self._header.set_icon_name("dialog-error-symbolic")
            self._overall_progress.add_css_class("error")

        self._header.set_description(message)

        # Update progress to complete
        self._overall_progress.set_fraction(1.0 if success else 0.0)
        self._overall_progress.set_text("Complete" if success else "Failed")

        # Update file label
        self._current_file_label.set_label(message)

        # Clear speed/ETA
        self._speed_label.set_label("--")
        self._eta_label.set_label("--")

        # Update buttons
        self._pause_button.set_sensitive(False)
        self._cancel_button.set_label("Close")
        self._cancel_button.remove_css_class("destructive-action")

        logger.info(
            "Progress dialog showing %s: %s",
            "success" if success else "failure",
            message,
        )

    def show_error(self, error_message: str) -> None:
        """Show error state.

        Args:
            error_message: The error message to display.
        """
        self.show_complete(False, error_message)

    def _on_pause_clicked(self, button: Gtk.Button) -> None:
        """Handle pause/resume button click."""
        self._is_paused = not self._is_paused
        logger.debug("Pause button clicked, paused=%s", self._is_paused)
        self.emit("pause-clicked", self._is_paused)

        # Update button label immediately for responsiveness
        button.set_label("Resume" if self._is_paused else "Pause")

    def _on_cancel_clicked(self, button: Gtk.Button) -> None:
        """Handle cancel button click."""
        if self._is_complete:
            # Just close the dialog
            self.close()
        else:
            logger.debug("Cancel button clicked")
            self.emit("cancel-clicked")

    @staticmethod
    def _format_bytes(num_bytes: int) -> str:
        """Format bytes to human-readable string."""
        if num_bytes < 1024:
            return f"{num_bytes} B"
        elif num_bytes < 1024 * 1024:
            return f"{num_bytes / 1024:.1f} KB"
        elif num_bytes < 1024 * 1024 * 1024:
            return f"{num_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"
