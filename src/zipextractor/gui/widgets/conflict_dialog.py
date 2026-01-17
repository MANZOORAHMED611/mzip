"""Conflict resolution dialog for file extraction conflicts.

This module provides a dialog that appears when extracting files would
overwrite existing files, allowing the user to choose how to resolve
the conflict.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GObject, Gtk

from zipextractor.core.models import ConflictResolution
from zipextractor.utils.logging import get_logger

logger = get_logger(__name__)


class ConflictDialog(Adw.Window):
    """Dialog for resolving file conflicts during extraction.

    Shows information about both the existing file and the new file,
    and provides options to overwrite, skip, or rename.

    Signals:
        resolution-selected: Emitted when user selects a resolution.
            Args: (resolution: ConflictResolution, apply_to_all: bool)
    """

    __gtype_name__ = "ConflictDialog"

    __gsignals__ = {
        "resolution-selected": (GObject.SignalFlags.RUN_FIRST, None, (int, bool)),
    }

    def __init__(
        self,
        parent: Gtk.Window,
        existing_path: Path,
        new_file_name: str,
        new_file_size: int,
        new_file_date: datetime | None = None,
    ) -> None:
        """Initialize the conflict dialog.

        Args:
            parent: Parent window for modal behavior.
            existing_path: Path to the existing file.
            new_file_name: Name of the file being extracted.
            new_file_size: Size of the new file in bytes.
            new_file_date: Modification date of the new file.
        """
        super().__init__(
            title="File Conflict",
            transient_for=parent,
            modal=True,
            default_width=450,
            resizable=False,
        )

        self._existing_path = existing_path
        self._new_file_name = new_file_name
        self._new_file_size = new_file_size
        self._new_file_date = new_file_date
        self._apply_to_all = False

        self._build_ui()

        logger.debug("Conflict dialog created for %s", new_file_name)

    def _build_ui(self) -> None:
        """Build the dialog UI."""
        # Main container
        main_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )
        self.set_content(main_box)

        # Header bar
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(False)
        header.set_show_start_title_buttons(False)
        main_box.append(header)

        # Content
        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            margin_top=16,
            margin_bottom=16,
            margin_start=16,
            margin_end=16,
        )
        main_box.append(content_box)

        # Warning header
        warning_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
        )
        content_box.append(warning_box)

        warning_icon = Gtk.Image(
            icon_name="dialog-warning-symbolic",
            pixel_size=48,
        )
        warning_icon.add_css_class("warning")
        warning_box.append(warning_icon)

        message_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
        )
        warning_box.append(message_box)

        title_label = Gtk.Label(
            label="File Already Exists",
            halign=Gtk.Align.START,
            css_classes=["heading"],
        )
        message_box.append(title_label)

        desc_label = Gtk.Label(
            label=f'A file named "{self._new_file_name}" already exists.',
            halign=Gtk.Align.START,
            wrap=True,
            css_classes=["dim-label"],
        )
        message_box.append(desc_label)

        # File comparison
        comparison_group = Adw.PreferencesGroup(title="File Comparison")
        content_box.append(comparison_group)

        # Existing file info
        existing_row = Adw.ActionRow(title="Existing File")
        existing_row.add_prefix(Gtk.Image(icon_name="document-open-symbolic"))

        existing_info = self._get_file_info(self._existing_path)
        existing_row.set_subtitle(existing_info)
        comparison_group.add(existing_row)

        # New file info
        new_row = Adw.ActionRow(title="New File (from archive)")
        new_row.add_prefix(Gtk.Image(icon_name="package-x-generic-symbolic"))

        new_info = self._format_new_file_info()
        new_row.set_subtitle(new_info)
        comparison_group.add(new_row)

        # Apply to all checkbox
        apply_all_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_top=8,
        )
        content_box.append(apply_all_box)

        self._apply_all_check = Gtk.CheckButton(
            label="Apply this action to all conflicts",
        )
        apply_all_box.append(self._apply_all_check)

        # Action buttons
        button_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_top=16,
            halign=Gtk.Align.END,
        )
        content_box.append(button_box)

        # Skip button
        skip_button = Gtk.Button(label="Skip")
        skip_button.connect("clicked", self._on_skip_clicked)
        button_box.append(skip_button)

        # Rename button
        rename_button = Gtk.Button(label="Rename")
        rename_button.connect("clicked", self._on_rename_clicked)
        button_box.append(rename_button)

        # Overwrite button
        overwrite_button = Gtk.Button(label="Overwrite")
        overwrite_button.add_css_class("destructive-action")
        overwrite_button.connect("clicked", self._on_overwrite_clicked)
        button_box.append(overwrite_button)

    def _get_file_info(self, path: Path) -> str:
        """Get information about an existing file.

        Args:
            path: Path to the file.

        Returns:
            Formatted file information string.
        """
        try:
            stat = path.stat()
            size = self._format_size(stat.st_size)
            mtime = datetime.fromtimestamp(stat.st_mtime)
            date_str = mtime.strftime("%Y-%m-%d %H:%M")
            return f"{size}, modified {date_str}"
        except Exception:
            return "Unable to read file info"

    def _format_new_file_info(self) -> str:
        """Format information about the new file.

        Returns:
            Formatted file information string.
        """
        size = self._format_size(self._new_file_size)
        if self._new_file_date:
            date_str = self._new_file_date.strftime("%Y-%m-%d %H:%M")
            return f"{size}, modified {date_str}"
        return size

    def _on_skip_clicked(self, button: Gtk.Button) -> None:
        """Handle skip button click."""
        apply_all = self._apply_all_check.get_active()
        self.emit("resolution-selected", ConflictResolution.SKIP.value, apply_all)
        self.close()

    def _on_rename_clicked(self, button: Gtk.Button) -> None:
        """Handle rename button click."""
        apply_all = self._apply_all_check.get_active()
        self.emit("resolution-selected", ConflictResolution.RENAME.value, apply_all)
        self.close()

    def _on_overwrite_clicked(self, button: Gtk.Button) -> None:
        """Handle overwrite button click."""
        apply_all = self._apply_all_check.get_active()
        self.emit("resolution-selected", ConflictResolution.OVERWRITE.value, apply_all)
        self.close()

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
