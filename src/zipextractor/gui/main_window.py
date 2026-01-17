"""Main window for ZIP Extractor.

This module contains the main application window with the archive list,
drop zone, destination selection, and extraction controls.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

if TYPE_CHECKING:
    from collections.abc import Sequence

from zipextractor.utils.logging import get_logger

logger = get_logger(__name__)


class MainWindow(Adw.ApplicationWindow):
    """Main application window for ZIP Extractor.

    This window provides the primary interface for selecting, previewing,
    and extracting ZIP archives.
    """

    def __init__(self, application: Adw.Application) -> None:
        """Initialize the main window.

        Args:
            application: The parent application instance.
        """
        super().__init__(
            application=application,
            title="ZIP Extractor",
            default_width=800,
            default_height=600,
        )

        self._archives: list[Path] = []
        self._destination: Path = Path.home() / "Downloads"

        self._build_ui()
        self._setup_actions()
        self._setup_drag_drop()

        logger.info("Main window created")

    def _build_ui(self) -> None:
        """Build the user interface."""
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_content(main_box)

        # Header bar
        header = Adw.HeaderBar()
        main_box.append(header)

        # Add Files button
        add_button = Gtk.Button(label="Add Files")
        add_button.add_css_class("suggested-action")
        add_button.connect("clicked", self._on_add_files_clicked)
        header.pack_start(add_button)

        # Settings button
        settings_button = Gtk.Button(icon_name="emblem-system-symbolic")
        settings_button.set_tooltip_text("Settings")
        settings_button.connect("clicked", self._on_settings_clicked)
        header.pack_end(settings_button)

        # Menu button
        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic")
        menu_button.set_tooltip_text("Main menu")
        header.pack_end(menu_button)

        # Content area with toolbar view
        toolbar_view = Adw.ToolbarView()
        main_box.append(toolbar_view)

        # Content
        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
        )
        content_box.set_vexpand(True)
        toolbar_view.set_content(content_box)

        # Drop zone / archive list area
        self._drop_zone = self._create_drop_zone()
        content_box.append(self._drop_zone)

        # Destination panel
        dest_box = self._create_destination_panel()
        content_box.append(dest_box)

        # Action buttons
        action_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            halign=Gtk.Align.END,
        )
        content_box.append(action_box)

        # Status label
        self._status_label = Gtk.Label(label="No archives selected")
        self._status_label.set_halign(Gtk.Align.START)
        self._status_label.set_hexpand(True)
        self._status_label.add_css_class("dim-label")
        action_box.append(self._status_label)

        # Clear button
        clear_button = Gtk.Button(label="Clear")
        clear_button.connect("clicked", self._on_clear_clicked)
        action_box.append(clear_button)

        # Extract button
        self._extract_button = Gtk.Button(label="Extract All")
        self._extract_button.add_css_class("suggested-action")
        self._extract_button.connect("clicked", self._on_extract_clicked)
        self._extract_button.set_sensitive(False)
        action_box.append(self._extract_button)

    def _create_drop_zone(self) -> Gtk.Widget:
        """Create the drop zone widget.

        Returns:
            The drop zone widget.
        """
        # Status page as drop zone
        drop_zone = Adw.StatusPage(
            title="Drop ZIP Files Here",
            description="Or click 'Add Files' to browse",
            icon_name="folder-download-symbolic",
        )
        drop_zone.set_vexpand(True)
        drop_zone.add_css_class("card")

        return drop_zone

    def _create_destination_panel(self) -> Gtk.Widget:
        """Create the destination selection panel.

        Returns:
            The destination panel widget.
        """
        frame = Gtk.Frame()
        frame.add_css_class("card")

        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
        )
        frame.set_child(box)

        # Label
        label = Gtk.Label(label="Destination:")
        box.append(label)

        # Entry
        self._dest_entry = Gtk.Entry()
        self._dest_entry.set_text(str(self._destination))
        self._dest_entry.set_hexpand(True)
        box.append(self._dest_entry)

        # Browse button
        browse_button = Gtk.Button(label="Browse...")
        browse_button.connect("clicked", self._on_browse_clicked)
        box.append(browse_button)

        return frame

    def _setup_actions(self) -> None:
        """Set up window-specific actions."""
        # Add files action
        add_action = Gio.SimpleAction.new("add-files", None)
        add_action.connect("activate", self._on_add_files_clicked)
        self.add_action(add_action)

        # Extract action
        extract_action = Gio.SimpleAction.new("extract", None)
        extract_action.connect("activate", self._on_extract_clicked)
        self.add_action(extract_action)

        # Clear action
        clear_action = Gio.SimpleAction.new("clear", None)
        clear_action.connect("activate", self._on_clear_clicked)
        self.add_action(clear_action)

        # Keyboard shortcuts
        app = self.get_application()
        if app is not None:
            app.set_accels_for_action("win.add-files", ["<Control>o"])
            app.set_accels_for_action("win.extract", ["<Control>e"])
            app.set_accels_for_action("win.clear", ["<Control>w"])

    def _setup_drag_drop(self) -> None:
        """Set up drag-and-drop support."""
        drop_target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_drop)
        drop_target.connect("enter", self._on_drag_enter)
        drop_target.connect("leave", self._on_drag_leave)
        self._drop_zone.add_controller(drop_target)

    def _on_drop(
        self,
        drop_target: Gtk.DropTarget,
        value: Gio.File,
        x: float,
        y: float,
    ) -> bool:
        """Handle dropped files.

        Args:
            drop_target: The drop target.
            value: The dropped file.
            x: Drop x coordinate.
            y: Drop y coordinate.

        Returns:
            True if the drop was handled.
        """
        path = value.get_path()
        if path:
            self.add_archives([path])
            return True
        return False

    def _on_drag_enter(
        self,
        drop_target: Gtk.DropTarget,
        x: float,
        y: float,
    ) -> Gdk.DragAction:
        """Handle drag enter event.

        Args:
            drop_target: The drop target.
            x: Drag x coordinate.
            y: Drag y coordinate.

        Returns:
            The drag action to use.
        """
        self._drop_zone.add_css_class("drop-highlight")
        return Gdk.DragAction.COPY

    def _on_drag_leave(self, drop_target: Gtk.DropTarget) -> None:
        """Handle drag leave event.

        Args:
            drop_target: The drop target.
        """
        self._drop_zone.remove_css_class("drop-highlight")

    def _on_add_files_clicked(
        self, button: Gtk.Button | None = None, *args: object
    ) -> None:
        """Handle Add Files button click."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Select ZIP Archives")

        # File filter
        filter_store = Gio.ListStore.new(Gtk.FileFilter)
        zip_filter = Gtk.FileFilter()
        zip_filter.set_name("ZIP Archives")
        zip_filter.add_mime_type("application/zip")
        zip_filter.add_pattern("*.zip")
        filter_store.append(zip_filter)

        all_filter = Gtk.FileFilter()
        all_filter.set_name("All Files")
        all_filter.add_pattern("*")
        filter_store.append(all_filter)

        dialog.set_filters(filter_store)
        dialog.set_default_filter(zip_filter)

        dialog.open_multiple(self, None, self._on_files_selected)

    def _on_files_selected(
        self,
        dialog: Gtk.FileDialog,
        result: Gio.AsyncResult,
    ) -> None:
        """Handle file selection result.

        Args:
            dialog: The file dialog.
            result: The async result.
        """
        try:
            files = dialog.open_multiple_finish(result)
            if files:
                paths = [f.get_path() for f in files if f.get_path()]
                self.add_archives(paths)
        except GLib.Error as e:
            if e.code != Gtk.DialogError.DISMISSED:
                logger.error("File selection error: %s", e.message)

    def _on_browse_clicked(self, button: Gtk.Button) -> None:
        """Handle Browse button click."""
        dialog = Gtk.FileDialog()
        dialog.set_title("Select Destination")
        dialog.set_initial_folder(Gio.File.new_for_path(str(self._destination)))
        dialog.select_folder(self, None, self._on_folder_selected)

    def _on_folder_selected(
        self,
        dialog: Gtk.FileDialog,
        result: Gio.AsyncResult,
    ) -> None:
        """Handle folder selection result.

        Args:
            dialog: The file dialog.
            result: The async result.
        """
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                path = folder.get_path()
                if path:
                    self._destination = Path(path)
                    self._dest_entry.set_text(path)
        except GLib.Error as e:
            if e.code != Gtk.DialogError.DISMISSED:
                logger.error("Folder selection error: %s", e.message)

    def _on_clear_clicked(self, button: Gtk.Button | None = None, *args: object) -> None:
        """Handle Clear button click."""
        self._archives.clear()
        self._update_status()
        logger.info("Archive list cleared")

    def _on_extract_clicked(
        self, button: Gtk.Button | None = None, *args: object
    ) -> None:
        """Handle Extract button click."""
        if not self._archives:
            return

        logger.info(
            "Starting extraction of %d archives to %s",
            len(self._archives),
            self._destination,
        )
        # TODO: Implement extraction with progress dialog

    def _on_settings_clicked(self, button: Gtk.Button) -> None:
        """Handle Settings button click."""
        logger.debug("Settings clicked")
        # TODO: Show settings dialog

    def add_archives(self, paths: Sequence[str]) -> None:
        """Add archives to the extraction queue.

        Args:
            paths: Paths to ZIP archives to add.
        """
        for path_str in paths:
            path = Path(path_str)
            if path.suffix.lower() == ".zip" and path.is_file():
                if path not in self._archives:
                    self._archives.append(path)
                    logger.info("Added archive: %s", path.name)
            else:
                logger.warning("Skipped non-ZIP file: %s", path_str)

        self._update_status()

    def _update_status(self) -> None:
        """Update the status label and button states."""
        count = len(self._archives)
        if count == 0:
            self._status_label.set_text("No archives selected")
            self._extract_button.set_sensitive(False)
        elif count == 1:
            self._status_label.set_text(f"1 archive: {self._archives[0].name}")
            self._extract_button.set_sensitive(True)
        else:
            self._status_label.set_text(f"{count} archives selected")
            self._extract_button.set_sensitive(True)
