"""Archive list widget for displaying added archives.

This module provides a list widget that displays ZIP archives with their
metadata, status, and action buttons. Falls back to a drop zone when empty.
"""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GObject, Gtk

from zipextractor.core.models import TaskStatus
from zipextractor.core.validation import get_archive_info
from zipextractor.utils.logging import get_logger

logger = get_logger(__name__)


class ArchiveRow(Gtk.ListBoxRow):
    """A row displaying archive information.

    Shows archive name, file count, size, and provides action buttons
    for removing and inspecting the archive.

    Signals:
        remove-clicked: Emitted when the remove button is clicked.
            Args: (archive_path: str)
        inspect-clicked: Emitted when the inspect button is clicked.
            Args: (archive_path: str)
    """

    __gtype_name__ = "ArchiveRow"

    __gsignals__ = {
        "remove-clicked": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "inspect-clicked": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, archive_path: Path) -> None:
        """Initialize the archive row.

        Args:
            archive_path: Path to the ZIP archive.
        """
        super().__init__()

        self._archive_path = archive_path
        self._status = TaskStatus.QUEUED
        self._file_count = 0
        self._total_size = 0

        self._load_archive_info()
        self._build_ui()

    @property
    def archive_path(self) -> Path:
        """Get the archive path."""
        return self._archive_path

    @property
    def status(self) -> TaskStatus:
        """Get the current status."""
        return self._status

    @status.setter
    def status(self, value: TaskStatus) -> None:
        """Set the status and update the display."""
        self._status = value
        self._update_status_display()

    def _load_archive_info(self) -> None:
        """Load archive metadata."""
        try:
            info = get_archive_info(self._archive_path)
            self._file_count = info.file_count
            self._total_size = info.uncompressed_size
        except Exception as e:
            logger.warning("Could not load archive info for %s: %s", self._archive_path, e)
            self._file_count = 0
            self._total_size = 0

    def _build_ui(self) -> None:
        """Build the row UI."""
        # Main container
        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_top=8,
            margin_bottom=8,
            margin_start=12,
            margin_end=12,
        )
        self.set_child(box)

        # Status icon
        self._status_icon = Gtk.Image(icon_name="package-x-generic-symbolic")
        box.append(self._status_icon)

        # Info box
        info_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
        )
        info_box.set_hexpand(True)
        box.append(info_box)

        # Archive name
        self._name_label = Gtk.Label(
            label=self._archive_path.name,
            halign=Gtk.Align.START,
            css_classes=["heading"],
        )
        self._name_label.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        info_box.append(self._name_label)

        # Details (file count and size)
        details_text = f"{self._file_count} files, {self._format_size(self._total_size)}"
        self._details_label = Gtk.Label(
            label=details_text,
            halign=Gtk.Align.START,
            css_classes=["dim-label", "caption"],
        )
        info_box.append(self._details_label)

        # Status label
        self._status_label = Gtk.Label(
            label="Ready",
            halign=Gtk.Align.START,
            css_classes=["caption"],
        )
        info_box.append(self._status_label)

        # Action buttons
        button_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=4,
        )
        box.append(button_box)

        # Inspect button
        inspect_btn = Gtk.Button(
            icon_name="find-location-symbolic",
            tooltip_text="Inspect archive contents",
            css_classes=["flat", "circular"],
        )
        inspect_btn.connect("clicked", self._on_inspect_clicked)
        button_box.append(inspect_btn)

        # Remove button
        remove_btn = Gtk.Button(
            icon_name="user-trash-symbolic",
            tooltip_text="Remove from list",
            css_classes=["flat", "circular"],
        )
        remove_btn.connect("clicked", self._on_remove_clicked)
        button_box.append(remove_btn)

        self._update_status_display()

    def _update_status_display(self) -> None:
        """Update the status icon and label based on current status."""
        status_info = {
            TaskStatus.QUEUED: ("package-x-generic-symbolic", "Ready", ""),
            TaskStatus.RUNNING: ("emblem-synchronizing-symbolic", "Extracting...", "accent"),
            TaskStatus.PAUSED: ("media-playback-pause-symbolic", "Paused", "warning"),
            TaskStatus.COMPLETED: ("emblem-ok-symbolic", "Completed", "success"),
            TaskStatus.FAILED: ("dialog-error-symbolic", "Failed", "error"),
            TaskStatus.CANCELLED: ("process-stop-symbolic", "Cancelled", "warning"),
        }

        icon, text, css_class = status_info.get(
            self._status, ("package-x-generic-symbolic", "Unknown", "")
        )

        self._status_icon.set_from_icon_name(icon)
        self._status_label.set_label(text)

        # Update CSS classes
        for cls in ["accent", "warning", "success", "error"]:
            self._status_label.remove_css_class(cls)
        if css_class:
            self._status_label.add_css_class(css_class)

    def _on_inspect_clicked(self, button: Gtk.Button) -> None:
        """Handle inspect button click."""
        self.emit("inspect-clicked", str(self._archive_path))

    def _on_remove_clicked(self, button: Gtk.Button) -> None:
        """Handle remove button click."""
        self.emit("remove-clicked", str(self._archive_path))

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format size in bytes to human-readable string."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


class ArchiveList(Gtk.Box):
    """Widget showing a list of archives or a drop zone when empty.

    This widget displays archives in a list view with metadata and actions,
    and shows a drop zone placeholder when no archives are loaded.

    Signals:
        archive-added: Emitted when an archive is added.
            Args: (archive_path: str)
        archive-removed: Emitted when an archive is removed.
            Args: (archive_path: str)
        archive-inspect: Emitted when inspect is clicked for an archive.
            Args: (archive_path: str)
        archives-changed: Emitted when the archive list changes.
            Args: (count: int)
    """

    __gtype_name__ = "ArchiveList"

    __gsignals__ = {
        "archive-added": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "archive-removed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "archive-inspect": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "archives-changed": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    def __init__(self) -> None:
        """Initialize the archive list."""
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
        )
        self.set_vexpand(True)

        self._archives: dict[str, ArchiveRow] = {}

        self._build_ui()
        self._show_empty_state()

    @property
    def archive_paths(self) -> list[Path]:
        """Get list of archive paths."""
        return [Path(p) for p in self._archives]

    @property
    def archive_count(self) -> int:
        """Get number of archives in the list."""
        return len(self._archives)

    def _build_ui(self) -> None:
        """Build the widget UI."""
        # Stack for switching between empty state and list
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_vexpand(True)
        self.append(self._stack)

        # Empty state (drop zone)
        self._empty_state = Adw.StatusPage(
            title="Drop ZIP Files Here",
            description="Or click 'Add Files' to browse",
            icon_name="folder-download-symbolic",
        )
        self._empty_state.add_css_class("card")
        self._stack.add_named(self._empty_state, "empty")

        # Archive list
        list_frame = Gtk.Frame()
        list_frame.add_css_class("card")
        self._stack.add_named(list_frame, "list")

        # Scrolled window for the list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        list_frame.set_child(scrolled)

        # List box
        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list_box.add_css_class("boxed-list")
        scrolled.set_child(self._list_box)

    def _show_empty_state(self) -> None:
        """Show the empty drop zone state."""
        self._stack.set_visible_child_name("empty")

    def _show_list_state(self) -> None:
        """Show the archive list state."""
        self._stack.set_visible_child_name("list")

    def add_archive(self, archive_path: Path) -> bool:
        """Add an archive to the list.

        Args:
            archive_path: Path to the ZIP archive.

        Returns:
            True if archive was added, False if already present.
        """
        path_str = str(archive_path)

        if path_str in self._archives:
            logger.debug("Archive already in list: %s", archive_path.name)
            return False

        # Create row
        row = ArchiveRow(archive_path)
        row.connect("remove-clicked", self._on_row_remove_clicked)
        row.connect("inspect-clicked", self._on_row_inspect_clicked)

        # Add to list
        self._list_box.append(row)
        self._archives[path_str] = row

        # Update display
        if len(self._archives) == 1:
            self._show_list_state()

        self.emit("archive-added", path_str)
        self.emit("archives-changed", len(self._archives))

        logger.info("Added archive: %s", archive_path.name)
        return True

    def remove_archive(self, archive_path: Path) -> bool:
        """Remove an archive from the list.

        Args:
            archive_path: Path to the archive to remove.

        Returns:
            True if archive was removed, False if not found.
        """
        path_str = str(archive_path)

        if path_str not in self._archives:
            return False

        row = self._archives.pop(path_str)
        self._list_box.remove(row)

        # Update display
        if len(self._archives) == 0:
            self._show_empty_state()

        self.emit("archive-removed", path_str)
        self.emit("archives-changed", len(self._archives))

        logger.info("Removed archive: %s", archive_path.name)
        return True

    def clear(self) -> None:
        """Remove all archives from the list."""
        paths = list(self._archives.keys())
        for path_str in paths:
            self.remove_archive(Path(path_str))

    def update_archive_status(self, archive_path: Path, status: TaskStatus) -> None:
        """Update the status of an archive.

        Args:
            archive_path: Path to the archive.
            status: New status for the archive.
        """
        path_str = str(archive_path)
        if path_str in self._archives:
            self._archives[path_str].status = status

    def get_row(self, archive_path: Path) -> ArchiveRow | None:
        """Get the row for an archive.

        Args:
            archive_path: Path to the archive.

        Returns:
            The ArchiveRow or None if not found.
        """
        return self._archives.get(str(archive_path))

    def _on_row_remove_clicked(self, row: ArchiveRow, path_str: str) -> None:
        """Handle remove button click on a row."""
        self.remove_archive(Path(path_str))

    def _on_row_inspect_clicked(self, row: ArchiveRow, path_str: str) -> None:
        """Handle inspect button click on a row."""
        self.emit("archive-inspect", path_str)

    def get_drop_target_widget(self) -> Gtk.Widget:
        """Get the widget to attach drop targets to.

        Returns:
            The widget for drag-drop attachment.
        """
        return self._empty_state
