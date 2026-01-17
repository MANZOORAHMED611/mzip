"""Archive inspector dialog for previewing archive contents.

This module provides a dialog that displays the contents of a ZIP archive
before extraction, including file tree, summary statistics, and warnings.
"""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GObject, Gtk

from zipextractor.core.models import ArchiveInfo
from zipextractor.core.validation import (
    detect_zip_bomb,
    get_archive_info,
    validate_archive,
)
from zipextractor.utils.logging import get_logger

logger = get_logger(__name__)


class FileTreeItem:
    """Represents an item in the file tree."""

    def __init__(self, name: str, is_dir: bool = False, size: int = 0) -> None:
        """Initialize file tree item."""
        self.name = name
        self.is_dir = is_dir
        self.size = size
        self.children: dict[str, FileTreeItem] = {}


class ArchiveInspector(Adw.Window):
    """Dialog for inspecting archive contents before extraction.

    Displays:
    - File tree with nested structure
    - Summary: file count, total size, compression ratio
    - Warnings: password protection, zip bomb detection
    - Extract/Cancel buttons

    Signals:
        extract-requested: Emitted when Extract button is clicked.
    """

    __gtype_name__ = "ArchiveInspector"

    __gsignals__ = {
        "extract-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, parent: Gtk.Window, archive_path: Path) -> None:
        """Initialize the archive inspector.

        Args:
            parent: Parent window for modal behavior.
            archive_path: Path to the ZIP archive to inspect.
        """
        super().__init__(
            title="Archive Inspector",
            transient_for=parent,
            modal=True,
            default_width=600,
            default_height=500,
            resizable=True,
        )

        self._archive_path = archive_path
        self._archive_info: ArchiveInfo | None = None
        self._has_warnings = False

        self._build_ui()
        self._load_archive_info()

        logger.debug("Archive inspector created for %s", archive_path.name)

    def _build_ui(self) -> None:
        """Build the dialog UI."""
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Header bar
        header = Adw.HeaderBar()
        main_box.append(header)

        # Title with archive name
        title_label = Gtk.Label(label=self._archive_path.name)
        title_label.add_css_class("heading")
        header.set_title_widget(title_label)

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
        main_box.append(content_box)

        # Summary group
        summary_group = Adw.PreferencesGroup(title="Summary")
        content_box.append(summary_group)

        # Summary rows
        self._file_count_row = Adw.ActionRow(title="Files")
        summary_group.add(self._file_count_row)

        self._size_row = Adw.ActionRow(title="Total Size")
        summary_group.add(self._size_row)

        self._compression_row = Adw.ActionRow(title="Compression Ratio")
        summary_group.add(self._compression_row)

        # Warnings group (initially hidden)
        self._warnings_group = Adw.PreferencesGroup(title="Warnings")
        self._warnings_group.set_visible(False)
        content_box.append(self._warnings_group)

        # File tree
        tree_group = Adw.PreferencesGroup(title="Contents")
        content_box.append(tree_group)

        # Scrolled window for file tree
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(200)
        scrolled.set_vexpand(True)

        # Create a frame to contain the tree view
        tree_frame = Gtk.Frame()
        tree_frame.set_child(scrolled)
        tree_group.add(tree_frame)

        # Create tree store and tree view
        self._build_tree_view(scrolled)

        # Action buttons
        button_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            halign=Gtk.Align.END,
            margin_top=12,
        )
        content_box.append(button_box)

        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", self._on_cancel_clicked)
        button_box.append(cancel_button)

        self._extract_button = Gtk.Button(label="Extract")
        self._extract_button.add_css_class("suggested-action")
        self._extract_button.connect("clicked", self._on_extract_clicked)
        button_box.append(self._extract_button)

    def _build_tree_view(self, scrolled: Gtk.ScrolledWindow) -> None:
        """Build the file tree view."""
        # Tree store: icon, name, size, type
        self._tree_store = Gtk.TreeStore.new([str, str, str, str])

        # Tree view
        self._tree_view = Gtk.TreeView(model=self._tree_store)
        self._tree_view.set_headers_visible(True)
        self._tree_view.set_enable_tree_lines(True)
        scrolled.set_child(self._tree_view)

        # Icon and Name column
        renderer_icon = Gtk.CellRendererPixbuf()
        renderer_text = Gtk.CellRendererText()

        column_name = Gtk.TreeViewColumn("Name")
        column_name.pack_start(renderer_icon, False)
        column_name.pack_start(renderer_text, True)
        column_name.add_attribute(renderer_icon, "icon-name", 0)
        column_name.add_attribute(renderer_text, "text", 1)
        column_name.set_expand(True)
        column_name.set_resizable(True)
        self._tree_view.append_column(column_name)

        # Size column
        renderer_size = Gtk.CellRendererText()
        renderer_size.set_property("xalign", 1.0)
        column_size = Gtk.TreeViewColumn("Size", renderer_size, text=2)
        column_size.set_min_width(80)
        self._tree_view.append_column(column_size)

        # Type column
        renderer_type = Gtk.CellRendererText()
        column_type = Gtk.TreeViewColumn("Type", renderer_type, text=3)
        column_type.set_min_width(80)
        self._tree_view.append_column(column_type)

    def _load_archive_info(self) -> None:
        """Load and display archive information."""
        try:
            # Validate archive first
            is_valid, message = validate_archive(self._archive_path)
            if not is_valid:
                self._show_error(message or "Unknown validation error")
                return

            # Get archive info
            self._archive_info = get_archive_info(self._archive_path)

            # Update summary
            self._update_summary()

            # Check for warnings
            self._check_warnings()

            # Populate file tree
            self._populate_file_tree()

        except Exception as e:
            logger.exception("Failed to load archive info: %s", e)
            self._show_error(str(e))

    def _update_summary(self) -> None:
        """Update summary display with archive info."""
        if self._archive_info is None:
            return

        info = self._archive_info

        # File count
        file_count = info.file_count
        dir_count = sum(1 for f in info.files if f.is_directory)
        self._file_count_row.set_subtitle(
            f"{file_count} files, {dir_count} directories"
        )

        # Total size
        compressed = self._format_size(info.file_size)
        uncompressed = self._format_size(info.uncompressed_size)
        self._size_row.set_subtitle(f"{uncompressed} ({compressed} compressed)")

        # Compression ratio
        ratio = info.compression_ratio
        self._compression_row.set_subtitle(f"{ratio:.1f}%")

    def _check_warnings(self) -> None:
        """Check for and display warnings."""
        warnings: list[tuple[str, str, str]] = []

        # Check for password protection
        if self._archive_info is not None and self._archive_info.has_password:
            warnings.append(("dialog-password-symbolic", "Password Protected",
                            "This archive requires a password to extract"))

        # Check for zip bomb
        is_bomb = detect_zip_bomb(self._archive_path)
        if is_bomb:
            warnings.append(("dialog-warning-symbolic", "Potential Zip Bomb",
                           "High compression ratio detected - archive may be malicious"))

        # Display warnings
        if warnings:
            self._has_warnings = True
            self._warnings_group.set_visible(True)

            for icon, title, description in warnings:
                row = Adw.ActionRow(
                    title=title,
                    subtitle=description,
                )
                icon_widget = Gtk.Image(icon_name=icon)
                icon_widget.add_css_class("warning")
                row.add_prefix(icon_widget)
                self._warnings_group.add(row)

    def _populate_file_tree(self) -> None:
        """Populate the file tree with archive contents."""
        if self._archive_info is None:
            return

        info = self._archive_info
        self._tree_store.clear()

        # Build tree structure
        root_items: dict[str, FileTreeItem] = {}

        for file_info in info.files:
            parts = Path(file_info.path).parts
            current_level = root_items

            for i, part in enumerate(parts):
                is_last = i == len(parts) - 1
                is_dir = file_info.is_directory or not is_last

                if part not in current_level:
                    current_level[part] = FileTreeItem(
                        name=part,
                        is_dir=is_dir,
                        size=file_info.size if is_last else 0,
                    )

                if is_dir:
                    current_level = current_level[part].children
                else:
                    break

        # Add items to tree store recursively
        self._add_tree_items(None, root_items)

        # Expand first level
        self._tree_view.expand_all()

    def _add_tree_items(
        self,
        parent: Gtk.TreeIter | None,
        items: dict[str, FileTreeItem],
    ) -> None:
        """Recursively add items to the tree store."""
        # Sort: directories first, then files
        sorted_items = sorted(
            items.items(),
            key=lambda x: (not x[1].is_dir, x[0].lower()),
        )

        for name, item in sorted_items:
            icon = "folder-symbolic" if item.is_dir else "text-x-generic-symbolic"
            size_str = "" if item.is_dir else self._format_size(item.size)
            type_str = "Folder" if item.is_dir else self._get_file_type(name)

            tree_iter = self._tree_store.append(parent, [icon, name, size_str, type_str])

            if item.children:
                self._add_tree_items(tree_iter, item.children)

    def _show_error(self, message: str) -> None:
        """Show an error state."""
        self._file_count_row.set_subtitle("Error")
        self._size_row.set_subtitle(message)
        self._compression_row.set_visible(False)
        self._extract_button.set_sensitive(False)

    def _on_cancel_clicked(self, button: Gtk.Button) -> None:
        """Handle cancel button click."""
        self.close()

    def _on_extract_clicked(self, button: Gtk.Button) -> None:
        """Handle extract button click."""
        self.emit("extract-requested")
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

    @staticmethod
    def _get_file_type(filename: str) -> str:
        """Get a human-readable file type from filename."""
        suffix = Path(filename).suffix.lower()

        type_map = {
            ".txt": "Text",
            ".md": "Markdown",
            ".json": "JSON",
            ".xml": "XML",
            ".html": "HTML",
            ".css": "CSS",
            ".js": "JavaScript",
            ".py": "Python",
            ".rs": "Rust",
            ".go": "Go",
            ".java": "Java",
            ".c": "C Source",
            ".cpp": "C++ Source",
            ".h": "Header",
            ".jpg": "Image",
            ".jpeg": "Image",
            ".png": "Image",
            ".gif": "Image",
            ".svg": "SVG",
            ".pdf": "PDF",
            ".doc": "Document",
            ".docx": "Document",
            ".xls": "Spreadsheet",
            ".xlsx": "Spreadsheet",
            ".zip": "Archive",
            ".tar": "Archive",
            ".gz": "Archive",
        }

        return type_map.get(suffix, "File")
