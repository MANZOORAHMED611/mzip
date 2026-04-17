"""Archive creation dialog for creating compressed archives.

This module provides a dialog for selecting files and creating archives
with various compression options.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, GObject, Gtk

from zipextractor.core.archive_writer import (
    ArchiveWriter,
    get_writable_formats,
    suggest_extension,
)
from zipextractor.core.models import (
    ArchiveFormat,
    CompressionMethod,
    CompressionOptions,
)
from zipextractor.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = get_logger(__name__)

# Format display names
FORMAT_NAMES: dict[ArchiveFormat, str] = {
    ArchiveFormat.ZIP: "ZIP Archive (.zip)",
    ArchiveFormat.TAR: "TAR Archive (.tar)",
    ArchiveFormat.TAR_GZ: "Gzipped TAR (.tar.gz)",
    ArchiveFormat.TAR_BZ2: "Bzipped TAR (.tar.bz2)",
    ArchiveFormat.TAR_XZ: "XZ TAR (.tar.xz)",
    ArchiveFormat.TAR_ZSTD: "Zstandard TAR (.tar.zst)",
    ArchiveFormat.SEVEN_ZIP: "7-Zip Archive (.7z)",
}

# Compression method display names
METHOD_NAMES: dict[CompressionMethod, str] = {
    CompressionMethod.STORE: "Store (no compression)",
    CompressionMethod.DEFLATE: "Deflate (fast)",
    CompressionMethod.BZIP2: "BZip2 (good for text)",
    CompressionMethod.LZMA: "LZMA (high compression)",
}

# Methods available per format
FORMAT_METHODS: dict[ArchiveFormat, list[CompressionMethod]] = {
    ArchiveFormat.ZIP: [
        CompressionMethod.DEFLATE,
        CompressionMethod.STORE,
        CompressionMethod.BZIP2,
        CompressionMethod.LZMA,
    ],
    ArchiveFormat.TAR: [CompressionMethod.STORE],
    ArchiveFormat.TAR_GZ: [CompressionMethod.DEFLATE],
    ArchiveFormat.TAR_BZ2: [CompressionMethod.BZIP2],
    ArchiveFormat.TAR_XZ: [CompressionMethod.LZMA],
    ArchiveFormat.TAR_ZSTD: [CompressionMethod.ZSTD],
}


class CreateArchiveDialog(Adw.Window):
    """Dialog for creating archives from files and folders.

    Allows users to:
    - Select source files/folders
    - Choose output location and format
    - Configure compression options
    - Optionally encrypt the archive

    Signals:
        archive-created: Emitted when archive is successfully created.
            Args: (output_path: str)
    """

    __gtype_name__ = "CreateArchiveDialog"

    __gsignals__ = {
        "archive-created": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(
        self,
        parent: Gtk.Window,
        initial_files: Sequence[Path] | None = None,
    ) -> None:
        """Initialize the create archive dialog.

        Args:
            parent: Parent window for modal behavior.
            initial_files: Optional list of files to pre-select.
        """
        super().__init__(
            title="Create Archive",
            transient_for=parent,
            modal=True,
            default_width=550,
            default_height=600,
            resizable=True,
        )

        self._source_files: list[Path] = list(initial_files) if initial_files else []
        self._output_path: Path | None = None
        self._is_creating = False

        self._build_ui()

        if self._source_files:
            self._update_file_list()
            self._suggest_output_name()

        logger.debug("Create archive dialog initialized")

    def _build_ui(self) -> None:
        """Build the dialog UI."""
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Header bar
        header = Adw.HeaderBar()
        main_box.append(header)

        # Cancel button
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", self._on_cancel_clicked)
        header.pack_start(cancel_btn)

        # Create button
        self._create_btn = Gtk.Button(label="Create")
        self._create_btn.add_css_class("suggested-action")
        self._create_btn.connect("clicked", self._on_create_clicked)
        self._create_btn.set_sensitive(False)
        header.pack_end(self._create_btn)

        # Scrolled content
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        main_box.append(scrolled)

        # Content box
        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=24,
            margin_top=24,
            margin_bottom=24,
            margin_start=24,
            margin_end=24,
        )
        scrolled.set_child(content_box)

        # Source files section
        self._build_source_section(content_box)

        # Output section
        self._build_output_section(content_box)

        # Compression options section
        self._build_compression_section(content_box)

        # Advanced options section
        self._build_advanced_section(content_box)

    def _build_source_section(self, parent: Gtk.Box) -> None:
        """Build source files section."""
        group = Adw.PreferencesGroup(title="Source Files")
        parent.append(group)

        # File list
        self._file_list_box = Gtk.ListBox()
        self._file_list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._file_list_box.add_css_class("boxed-list")

        # Placeholder when empty
        self._empty_label = Gtk.Label(label="No files selected")
        self._empty_label.add_css_class("dim-label")
        self._empty_label.set_margin_top(12)
        self._empty_label.set_margin_bottom(12)

        list_frame = Gtk.Frame()
        list_frame.set_child(self._file_list_box)
        group.add(list_frame)

        # Add files button
        add_btn_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_top=12,
        )
        group.add(add_btn_box)

        add_files_btn = Gtk.Button(label="Add Files")
        add_files_btn.connect("clicked", self._on_add_files_clicked)
        add_btn_box.append(add_files_btn)

        add_folder_btn = Gtk.Button(label="Add Folder")
        add_folder_btn.connect("clicked", self._on_add_folder_clicked)
        add_btn_box.append(add_folder_btn)

        clear_btn = Gtk.Button(label="Clear All")
        clear_btn.connect("clicked", self._on_clear_clicked)
        add_btn_box.append(clear_btn)

    def _build_output_section(self, parent: Gtk.Box) -> None:
        """Build output section."""
        group = Adw.PreferencesGroup(title="Output")
        parent.append(group)

        # Output location row
        self._output_row = Adw.ActionRow(
            title="Save As",
            subtitle="Select output location",
        )
        browse_btn = Gtk.Button(icon_name="folder-open-symbolic")
        browse_btn.set_valign(Gtk.Align.CENTER)
        browse_btn.connect("clicked", self._on_browse_output_clicked)
        self._output_row.add_suffix(browse_btn)
        self._output_row.set_activatable_widget(browse_btn)
        group.add(self._output_row)

        # Format selection
        self._format_row = Adw.ComboRow(title="Archive Format")
        format_model = Gtk.StringList()

        self._format_list: list[ArchiveFormat] = []
        for fmt in get_writable_formats():
            if fmt in FORMAT_NAMES:
                format_model.append(FORMAT_NAMES[fmt])
                self._format_list.append(fmt)

        self._format_row.set_model(format_model)
        self._format_row.set_selected(0)  # ZIP by default
        self._format_row.connect("notify::selected", self._on_format_changed)
        group.add(self._format_row)

    def _build_compression_section(self, parent: Gtk.Box) -> None:
        """Build compression options section."""
        group = Adw.PreferencesGroup(title="Compression")
        parent.append(group)

        # Compression method
        self._method_row = Adw.ComboRow(title="Method")
        self._update_method_options()
        self._method_row.connect("notify::selected", self._on_method_changed)
        group.add(self._method_row)

        # Compression level
        self._level_row = Adw.ActionRow(title="Compression Level")

        level_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            valign=Gtk.Align.CENTER,
        )

        self._level_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 9, 1
        )
        self._level_scale.set_value(6)
        self._level_scale.set_digits(0)
        self._level_scale.set_hexpand(True)
        self._level_scale.set_size_request(200, -1)

        # Add marks
        self._level_scale.add_mark(0, Gtk.PositionType.BOTTOM, "Fast")
        self._level_scale.add_mark(9, Gtk.PositionType.BOTTOM, "Best")

        level_box.append(self._level_scale)
        self._level_row.add_suffix(level_box)
        group.add(self._level_row)

    def _build_advanced_section(self, parent: Gtk.Box) -> None:
        """Build advanced options section."""
        expander = Adw.ExpanderRow(title="Advanced Options")
        group = Adw.PreferencesGroup()
        group.add(expander)
        parent.append(group)

        # Include hidden files
        self._hidden_switch = Adw.SwitchRow(
            title="Include Hidden Files",
            subtitle="Include files starting with a dot",
        )
        self._hidden_switch.set_active(True)
        expander.add_row(self._hidden_switch)

        # Preserve timestamps
        self._timestamps_switch = Adw.SwitchRow(
            title="Preserve Timestamps",
            subtitle="Keep original file modification times",
        )
        self._timestamps_switch.set_active(True)
        expander.add_row(self._timestamps_switch)

        # Preserve permissions
        self._permissions_switch = Adw.SwitchRow(
            title="Preserve Permissions",
            subtitle="Keep Unix file permissions",
        )
        self._permissions_switch.set_active(True)
        expander.add_row(self._permissions_switch)

    def _update_file_list(self) -> None:
        """Update the file list display."""
        # Clear existing rows
        while True:
            row = self._file_list_box.get_row_at_index(0)
            if row is None:
                break
            self._file_list_box.remove(row)

        if not self._source_files:
            self._file_list_box.append(self._empty_label)
            self._create_btn.set_sensitive(False)
            return

        for file_path in self._source_files:
            row = self._create_file_row(file_path)
            self._file_list_box.append(row)

        self._validate_can_create()

    def _create_file_row(self, file_path: Path) -> Adw.ActionRow:
        """Create a row for a file in the list."""
        # Determine icon
        if file_path.is_dir():
            icon_name = "folder-symbolic"
            subtitle = "Folder"
        else:
            icon_name = "text-x-generic-symbolic"
            try:
                size = file_path.stat().st_size
                subtitle = self._format_size(size)
            except OSError:
                subtitle = "Unknown size"

        row = Adw.ActionRow(
            title=file_path.name,
            subtitle=subtitle,
        )

        # Icon
        icon = Gtk.Image(icon_name=icon_name)
        row.add_prefix(icon)

        # Remove button
        remove_btn = Gtk.Button(icon_name="user-trash-symbolic")
        remove_btn.set_valign(Gtk.Align.CENTER)
        remove_btn.add_css_class("flat")
        remove_btn.connect("clicked", lambda _, p=file_path: self._remove_file(p))
        row.add_suffix(remove_btn)

        return row

    def _remove_file(self, file_path: Path) -> None:
        """Remove a file from the source list."""
        if file_path in self._source_files:
            self._source_files.remove(file_path)
            self._update_file_list()

    def _update_method_options(self) -> None:
        """Update compression method options based on selected format."""
        selected_idx = self._format_row.get_selected()
        if selected_idx < len(self._format_list):
            fmt = self._format_list[selected_idx]
        else:
            fmt = ArchiveFormat.ZIP

        methods = FORMAT_METHODS.get(fmt, [CompressionMethod.DEFLATE])

        method_model = Gtk.StringList()
        self._method_list: list[CompressionMethod] = []

        for method in methods:
            if method in METHOD_NAMES:
                method_model.append(METHOD_NAMES[method])
                self._method_list.append(method)

        self._method_row.set_model(method_model)
        if self._method_list:
            self._method_row.set_selected(0)

        # Enable/disable level based on method
        self._update_level_sensitivity()

    def _update_level_sensitivity(self) -> None:
        """Update compression level sensitivity."""
        selected_idx = self._method_row.get_selected()
        if selected_idx < len(self._method_list):
            method = self._method_list[selected_idx]
            # Store method doesn't use compression level
            self._level_row.set_sensitive(method != CompressionMethod.STORE)
        else:
            self._level_row.set_sensitive(True)

    def _suggest_output_name(self) -> None:
        """Suggest output filename based on source files."""
        if not self._source_files:
            return

        # Use first file/folder name as base
        base_name = self._source_files[0].stem
        if len(self._source_files) > 1:
            base_name = "archive"

        # Get current format extension
        selected_idx = self._format_row.get_selected()
        if selected_idx < len(self._format_list):
            fmt = self._format_list[selected_idx]
            ext = suggest_extension(fmt)
        else:
            ext = ".zip"

        # Suggest in same directory as first source
        output_dir = self._source_files[0].parent
        suggested = output_dir / f"{base_name}{ext}"

        self._output_path = suggested
        self._output_row.set_subtitle(str(suggested))
        self._validate_can_create()

    def _validate_can_create(self) -> None:
        """Check if archive can be created."""
        can_create = bool(self._source_files) and self._output_path is not None
        self._create_btn.set_sensitive(can_create)

    def _on_add_files_clicked(self, button: Gtk.Button) -> None:
        """Handle add files button click."""
        # Use FileChooserDialog for better compatibility
        dialog = Gtk.FileChooserDialog(
            title="Select Files",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("_Open", Gtk.ResponseType.ACCEPT)
        dialog.set_modal(True)
        dialog.set_select_multiple(True)
        dialog.connect("response", self._on_files_dialog_response)
        dialog.show()

    def _on_files_dialog_response(
        self, dialog: Gtk.FileChooserDialog, response: int
    ) -> None:
        """Handle files selection result."""
        if response == Gtk.ResponseType.ACCEPT:
            files = dialog.get_files()
            if files:
                for i in range(files.get_n_items()):
                    gfile = files.get_item(i)
                    if gfile and gfile.get_path():
                        path = Path(gfile.get_path())
                        if path not in self._source_files:
                            self._source_files.append(path)
                self._update_file_list()
                self._suggest_output_name()
        dialog.destroy()

    def _on_add_folder_clicked(self, button: Gtk.Button) -> None:
        """Handle add folder button click."""
        # Use FileChooserDialog for better compatibility
        dialog = Gtk.FileChooserDialog(
            title="Select Folder",
            transient_for=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("_Select", Gtk.ResponseType.ACCEPT)
        dialog.set_modal(True)
        dialog.connect("response", self._on_folder_dialog_response)
        dialog.show()

    def _on_folder_dialog_response(
        self, dialog: Gtk.FileChooserDialog, response: int
    ) -> None:
        """Handle folder selection result."""
        if response == Gtk.ResponseType.ACCEPT:
            gfile = dialog.get_file()
            if gfile and gfile.get_path():
                path = Path(gfile.get_path())
                if path not in self._source_files:
                    self._source_files.append(path)
                self._update_file_list()
                self._suggest_output_name()
        dialog.destroy()

    def _on_clear_clicked(self, button: Gtk.Button) -> None:
        """Handle clear all button click."""
        self._source_files.clear()
        self._update_file_list()

    def _on_browse_output_clicked(self, button: Gtk.Button) -> None:
        """Handle browse output button click."""
        # Use FileChooserDialog for better compatibility
        dialog = Gtk.FileChooserDialog(
            title="Save Archive As",
            transient_for=self,
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("_Save", Gtk.ResponseType.ACCEPT)
        dialog.set_modal(True)

        # Set initial name
        if self._output_path:
            dialog.set_current_name(self._output_path.name)

        dialog.connect("response", self._on_output_dialog_response)
        dialog.show()

    def _on_output_dialog_response(
        self, dialog: Gtk.FileChooserDialog, response: int
    ) -> None:
        """Handle output selection result."""
        if response == Gtk.ResponseType.ACCEPT:
            gfile = dialog.get_file()
            if gfile and gfile.get_path():
                self._output_path = Path(gfile.get_path())

                # Ensure correct extension
                selected_idx = self._format_row.get_selected()
                if selected_idx < len(self._format_list):
                    fmt = self._format_list[selected_idx]
                    ext = suggest_extension(fmt)
                    if not str(self._output_path).endswith(ext):
                        self._output_path = self._output_path.with_suffix(ext)

                self._output_row.set_subtitle(str(self._output_path))
                self._validate_can_create()
        dialog.destroy()

    def _on_format_changed(self, row: Adw.ComboRow, pspec: object) -> None:
        """Handle format selection change."""
        self._update_method_options()

        # Update output extension
        if self._output_path:
            selected_idx = self._format_row.get_selected()
            if selected_idx < len(self._format_list):
                fmt = self._format_list[selected_idx]
                ext = suggest_extension(fmt)
                new_path = self._output_path.with_suffix(ext)
                self._output_path = new_path
                self._output_row.set_subtitle(str(new_path))

    def _on_method_changed(self, row: Adw.ComboRow, pspec: object) -> None:
        """Handle compression method change."""
        self._update_level_sensitivity()

    def _on_cancel_clicked(self, button: Gtk.Button) -> None:
        """Handle cancel button click."""
        self.close()

    def _on_create_clicked(self, button: Gtk.Button) -> None:
        """Handle create button click."""
        if self._is_creating or not self._source_files or not self._output_path:
            return

        self._is_creating = True
        self._create_btn.set_sensitive(False)
        self._create_btn.set_label("Creating...")

        # Build compression options
        selected_format_idx = self._format_row.get_selected()
        fmt = (
            self._format_list[selected_format_idx]
            if selected_format_idx < len(self._format_list)
            else ArchiveFormat.ZIP
        )

        selected_method_idx = self._method_row.get_selected()
        method = (
            self._method_list[selected_method_idx]
            if selected_method_idx < len(self._method_list)
            else CompressionMethod.DEFLATE
        )

        level = int(self._level_scale.get_value())

        options = CompressionOptions(
            format=fmt,
            method=method,
            level=level,
            include_hidden=self._hidden_switch.get_active(),
            preserve_timestamps=self._timestamps_switch.get_active(),
            preserve_permissions=self._permissions_switch.get_active(),
        )

        # Capture output path (validated non-None above)
        output_path = self._output_path
        assert output_path is not None

        # Create archive in background thread
        def create_archive() -> tuple[bool, str]:
            try:
                writer = ArchiveWriter()
                result = writer.create(
                    self._source_files,
                    output_path,
                    options,
                )
                if result.success:
                    return True, str(self._output_path)
                return False, result.error_message or "Unknown error"
            except Exception as e:
                logger.exception("Archive creation failed: %s", e)
                return False, str(e)

        def on_complete(success: bool, message: str) -> bool:
            self._is_creating = False
            self._create_btn.set_label("Create")
            self._create_btn.set_sensitive(True)

            if success:
                self.emit("archive-created", message)
                self.close()
            else:
                self._show_error(message)

            return False  # Don't repeat

        # Run in thread
        import threading

        def run_and_callback() -> None:
            success, message = create_archive()
            GLib.idle_add(on_complete, success, message)

        thread = threading.Thread(target=run_and_callback, daemon=True)
        thread.start()

    def _show_error(self, message: str) -> None:
        """Show error dialog."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Archive Creation Failed",
            body=message,
        )
        dialog.add_response("ok", "OK")
        dialog.present()

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
