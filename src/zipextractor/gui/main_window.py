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

from zipextractor.core.models import ExtractionTask, ProgressStats, TaskStatus
from zipextractor.gui.widgets import (
    ArchiveInspector,
    ArchiveList,
    ProgressDialog,
    SettingsDialog,
)
from zipextractor.gui.workers import ExtractionWorker, create_extraction_task
from zipextractor.utils.config import ConfigManager
from zipextractor.utils.history import HistoryManager
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

        # Configuration
        self._config_manager = ConfigManager()
        self._settings = self._config_manager.load()

        # Use settings for default destination
        self._destination: Path = self._settings.default_destination

        # Extraction state
        self._current_worker: ExtractionWorker | None = None
        self._progress_dialog: ProgressDialog | None = None

        # History manager
        self._history_manager = HistoryManager()

        self._build_ui()
        self._setup_actions()
        self._setup_drag_drop()

        # Apply saved theme
        self._apply_theme(self._settings.dark_mode)

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

        # Archive list (with integrated drop zone)
        self._archive_list = ArchiveList()
        self._archive_list.connect("archive-removed", self._on_archive_removed)
        self._archive_list.connect("archive-inspect", self._on_archive_inspect)
        self._archive_list.connect("archives-changed", self._on_archives_changed)
        content_box.append(self._archive_list)

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

        # Settings action
        settings_action = Gio.SimpleAction.new("settings", None)
        settings_action.connect("activate", self._on_settings_action)
        self.add_action(settings_action)

        # Pause/Resume action
        pause_action = Gio.SimpleAction.new("pause-resume", None)
        pause_action.connect("activate", self._on_pause_resume_action)
        self.add_action(pause_action)

        # Cancel action
        cancel_action = Gio.SimpleAction.new("cancel", None)
        cancel_action.connect("activate", self._on_cancel_action)
        self.add_action(cancel_action)

        # Keyboard shortcuts
        app = self.get_application()
        if app is not None:
            app.set_accels_for_action("win.add-files", ["<Control>o"])
            app.set_accels_for_action("win.extract", ["<Control>e"])
            app.set_accels_for_action("win.clear", ["<Control>w"])
            app.set_accels_for_action("win.settings", ["<Control>comma"])
            app.set_accels_for_action("win.pause-resume", ["space"])
            app.set_accels_for_action("win.cancel", ["Escape"])

    def _setup_drag_drop(self) -> None:
        """Set up drag-and-drop support."""
        drop_target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_drop)
        drop_target.connect("enter", self._on_drag_enter)
        drop_target.connect("leave", self._on_drag_leave)
        # Attach drop target to the archive list's drop zone widget
        drop_widget = self._archive_list.get_drop_target_widget()
        drop_widget.add_controller(drop_target)

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
        self._archive_list.get_drop_target_widget().add_css_class("drop-highlight")
        return Gdk.DragAction.COPY

    def _on_drag_leave(self, drop_target: Gtk.DropTarget) -> None:
        """Handle drag leave event.

        Args:
            drop_target: The drop target.
        """
        self._archive_list.get_drop_target_widget().remove_css_class("drop-highlight")

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
        self._archive_list.clear()
        logger.info("Archive list cleared")

    def _on_extract_clicked(
        self, button: Gtk.Button | None = None, *args: object
    ) -> None:
        """Handle Extract button click."""
        archives = self._archive_list.archive_paths
        if not archives:
            return

        logger.info(
            "Starting extraction of %d archives to %s",
            len(archives),
            self._destination,
        )

        # Get destination from entry (user may have edited it)
        dest_text = self._dest_entry.get_text().strip()
        if dest_text:
            self._destination = Path(dest_text)

        # Extract first archive (batch support can be added later)
        self._start_extraction(archives[0])

    def _start_extraction(self, archive_path: Path) -> None:
        """Start extraction for a single archive.

        Args:
            archive_path: Path to the archive to extract.
        """
        # Create extraction task with current settings
        task = create_extraction_task(
            archive_path=archive_path,
            destination_path=self._destination,
            conflict_resolution=self._settings.conflict_resolution,
            create_root_folder=self._settings.create_root_folder,
            preserve_timestamps=self._settings.preserve_timestamps,
            preserve_permissions=self._settings.preserve_permissions,
        )

        # Create progress dialog
        self._progress_dialog = ProgressDialog(
            parent=self,
            task=task,
        )
        self._progress_dialog.connect("pause-clicked", self._on_pause_clicked)
        self._progress_dialog.connect("cancel-clicked", self._on_cancel_clicked)

        # Create worker
        self._current_worker = ExtractionWorker(
            task=task,
            on_progress=self._on_extraction_progress,
            on_complete=self._on_extraction_complete,
            on_error=self._on_extraction_error,
        )

        # Update archive status
        self._archive_list.update_archive_status(archive_path, TaskStatus.RUNNING)

        # Show dialog and start extraction
        self._progress_dialog.present()
        self._current_worker.start()

    def _on_extraction_progress(
        self, task: ExtractionTask, stats: ProgressStats
    ) -> None:
        """Handle extraction progress update.

        This is called from the worker via GLib.idle_add.

        Args:
            task: The extraction task with updated progress.
            stats: Current progress statistics.
        """
        if self._progress_dialog:
            self._progress_dialog.update_progress(task, stats)

    def _on_extraction_complete(self, task: ExtractionTask, success: bool) -> None:
        """Handle extraction completion.

        Args:
            task: The completed extraction task.
            success: Whether extraction was successful.
        """
        if self._progress_dialog:
            if success:
                message = f"Extracted {task.extracted_files} files successfully"
                self._progress_dialog.show_complete(True, message)

                # Send notification if enabled
                if self._settings.show_notifications:
                    self._send_notification(task)

                # Update archive status to completed
                self._archive_list.update_archive_status(
                    task.archive_path, TaskStatus.COMPLETED
                )

                # Record in history
                self._history_manager.add_extraction(
                    archive_path=task.archive_path,
                    destination_path=task.destination_path,
                    extracted_files=task.extracted_files,
                    extracted_bytes=task.extracted_bytes,
                    success=True,
                )
            else:
                message = task.error_message or "Extraction failed"
                self._progress_dialog.show_complete(False, message)

                # Update archive status to failed
                self._archive_list.update_archive_status(
                    task.archive_path, TaskStatus.FAILED
                )

                # Record failure in history
                self._history_manager.add_extraction(
                    archive_path=task.archive_path,
                    destination_path=task.destination_path,
                    extracted_files=task.extracted_files,
                    extracted_bytes=task.extracted_bytes,
                    success=False,
                    error_message=task.error_message,
                )

        self._current_worker = None
        logger.info(
            "Extraction %s: %s",
            "completed" if success else "failed",
            task.archive_path.name,
        )

    def _on_extraction_error(self, task: ExtractionTask, error: str) -> None:
        """Handle extraction error.

        Args:
            task: The failed extraction task.
            error: Error message.
        """
        if self._progress_dialog:
            self._progress_dialog.show_error(error)

        self._current_worker = None
        logger.error("Extraction error: %s", error)

    def _on_pause_clicked(
        self, dialog: ProgressDialog, is_paused: bool
    ) -> None:
        """Handle pause/resume button click.

        Args:
            dialog: The progress dialog.
            is_paused: Whether pause was requested (True) or resume (False).
        """
        if self._current_worker:
            if is_paused:
                self._current_worker.pause()
            else:
                self._current_worker.resume()

    def _on_cancel_clicked(self, dialog: ProgressDialog) -> None:
        """Handle cancel button click.

        Args:
            dialog: The progress dialog.
        """
        if self._current_worker:
            self._current_worker.cancel()

    def _on_settings_clicked(self, button: Gtk.Button) -> None:
        """Handle Settings button click."""
        self._show_settings_dialog()

    def _on_settings_action(
        self, action: Gio.SimpleAction, parameter: object
    ) -> None:
        """Handle settings action (keyboard shortcut)."""
        self._show_settings_dialog()

    def _show_settings_dialog(self) -> None:
        """Show the settings dialog."""
        logger.debug("Settings dialog opened")

        dialog = SettingsDialog(
            parent=self,
            config_manager=self._config_manager,
        )
        dialog.connect("settings-changed", self._on_settings_changed)
        dialog.present()

    def _on_pause_resume_action(
        self, action: Gio.SimpleAction, parameter: object
    ) -> None:
        """Handle pause/resume action (keyboard shortcut)."""
        if self._current_worker and self._progress_dialog:
            # Toggle pause state
            if self._current_worker.task.status == TaskStatus.PAUSED:
                self._current_worker.resume()
                logger.debug("Extraction resumed via keyboard shortcut")
            elif self._current_worker.task.status == TaskStatus.RUNNING:
                self._current_worker.pause()
                logger.debug("Extraction paused via keyboard shortcut")

    def _on_cancel_action(
        self, action: Gio.SimpleAction, parameter: object
    ) -> None:
        """Handle cancel action (keyboard shortcut)."""
        if self._current_worker:
            self._current_worker.cancel()
            logger.debug("Extraction cancelled via keyboard shortcut")
        elif self._progress_dialog:
            self._progress_dialog.close()

    def _on_settings_changed(
        self, dialog: SettingsDialog, settings: object
    ) -> None:
        """Handle settings change.

        Args:
            dialog: The settings dialog.
            settings: The updated settings object.
        """
        from zipextractor.utils.config import ApplicationSettings

        if isinstance(settings, ApplicationSettings):
            self._settings = settings
            self._destination = settings.default_destination
            self._dest_entry.set_text(str(self._destination))
            logger.info("Settings updated")

    def _apply_theme(self, theme: str) -> None:
        """Apply the specified theme.

        Args:
            theme: Theme to apply ("system", "light", or "dark").
        """
        style_manager = Adw.StyleManager.get_default()

        if theme == "light":
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        elif theme == "dark":
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        else:  # system
            style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)

    def _send_notification(self, task: ExtractionTask) -> None:
        """Send desktop notification for completed extraction.

        Args:
            task: The completed extraction task.
        """
        app = self.get_application()
        if not app:
            return

        notification = Gio.Notification.new("Extraction Complete")
        notification.set_body(
            f"Extracted {task.extracted_files} files from {task.archive_path.name}"
        )
        notification.set_icon(Gio.ThemedIcon.new("archive-extract-symbolic"))

        app.send_notification(task.task_id, notification)

    def add_archives(self, paths: Sequence[str]) -> None:
        """Add archives to the extraction queue.

        Args:
            paths: Paths to ZIP archives to add.
        """
        for path_str in paths:
            path = Path(path_str)
            if path.suffix.lower() == ".zip" and path.is_file():
                self._archive_list.add_archive(path)
            else:
                logger.warning("Skipped non-ZIP file: %s", path_str)

    def _update_status(self) -> None:
        """Update the status label and button states."""
        count = self._archive_list.archive_count
        archives = self._archive_list.archive_paths
        if count == 0:
            self._status_label.set_text("No archives selected")
            self._extract_button.set_sensitive(False)
        elif count == 1:
            self._status_label.set_text(f"1 archive: {archives[0].name}")
            self._extract_button.set_sensitive(True)
        else:
            self._status_label.set_text(f"{count} archives selected")
            self._extract_button.set_sensitive(True)

    def _on_archive_removed(self, archive_list: ArchiveList, path_str: str) -> None:
        """Handle archive removal from list.

        Args:
            archive_list: The archive list widget.
            path_str: Path of the removed archive.
        """
        logger.debug("Archive removed: %s", path_str)

    def _on_archive_inspect(self, archive_list: ArchiveList, path_str: str) -> None:
        """Handle archive inspect request.

        Args:
            archive_list: The archive list widget.
            path_str: Path of the archive to inspect.
        """
        archive_path = Path(path_str)
        logger.debug("Inspecting archive: %s", archive_path.name)

        inspector = ArchiveInspector(parent=self, archive_path=archive_path)
        inspector.connect("extract-requested", self._on_inspector_extract, archive_path)
        inspector.present()

    def _on_inspector_extract(
        self, inspector: ArchiveInspector, archive_path: Path
    ) -> None:
        """Handle extract request from inspector.

        Args:
            inspector: The archive inspector dialog.
            archive_path: Path to the archive to extract.
        """
        # Get destination from entry
        dest_text = self._dest_entry.get_text().strip()
        if dest_text:
            self._destination = Path(dest_text)

        self._start_extraction(archive_path)

    def _on_archives_changed(self, archive_list: ArchiveList, count: int) -> None:
        """Handle changes to the archive list.

        Args:
            archive_list: The archive list widget.
            count: New count of archives in the list.
        """
        self._update_status()
