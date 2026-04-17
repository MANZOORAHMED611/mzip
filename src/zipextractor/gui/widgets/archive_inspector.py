"""Archive inspector dialog for previewing archive contents.

This module provides a dialog that displays the contents of a ZIP archive
before extraction, including file tree, summary statistics, warnings,
and selective extraction with checkboxes.
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

    def __init__(
        self,
        name: str,
        is_dir: bool = False,
        size: int = 0,
        path: str = "",
    ) -> None:
        """Initialize file tree item."""
        self.name = name
        self.is_dir = is_dir
        self.size = size
        self.path = path
        self.children: dict[str, FileTreeItem] = {}
        self.selected = True  # Selected by default


class ArchiveInspector(Adw.Window):
    """Dialog for inspecting archive contents before extraction.

    Displays:
    - File tree with nested structure and checkboxes
    - Search/filter functionality
    - File preview panel
    - Summary: file count, total size, compression ratio
    - Warnings: password protection, zip bomb detection
    - Extract All/Selected/Cancel buttons

    Signals:
        extract-requested: Emitted when Extract All is clicked (list of all files).
        extract-selected: Emitted when Extract Selected is clicked (list of paths).
    """

    __gtype_name__ = "ArchiveInspector"

    __gsignals__ = {
        "extract-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "extract-selected": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
    }

    # Column indices for tree store
    COL_SELECTED = 0
    COL_ICON = 1
    COL_NAME = 2
    COL_SIZE = 3
    COL_TYPE = 4
    COL_PATH = 5

    def __init__(
        self,
        parent: Gtk.Window,
        archive_path: Path,
    ) -> None:
        """Initialize the archive inspector.

        Args:
            parent: Parent window for modal behavior.
            archive_path: Path to the archive to inspect.
        """
        super().__init__(
            title="Archive Inspector",
            transient_for=parent,
            modal=True,
            default_width=700,
            default_height=500,
            resizable=True,
        )

        self._archive_path = archive_path
        self._archive_info: ArchiveInfo | None = None
        self._has_warnings = False
        self._filter_text = ""
        self._root_items: dict[str, FileTreeItem] = {}

        self._build_ui()
        self._load_archive_info()

        logger.debug("Archive inspector created for %s", archive_path.name)

    def _build_ui(self) -> None:
        """Build the dialog UI."""
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Header bar with archive name as title
        header = Adw.HeaderBar()
        header.set_title_widget(Gtk.Label(label=self._archive_path.name))
        main_box.append(header)

        # Content area
        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
        )
        content_box.set_vexpand(True)
        main_box.append(content_box)

        # Warnings box (initially hidden)
        self._warnings_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )
        self._warnings_box.add_css_class("warning")
        self._warnings_box.set_visible(False)
        content_box.append(self._warnings_box)

        # Search and selection toolbar
        toolbar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6,
        )
        content_box.append(toolbar)

        # Search entry
        self._search_entry = Gtk.SearchEntry(
            placeholder_text="Filter files...",
            hexpand=True,
        )
        self._search_entry.connect("search-changed", self._on_search_changed)
        toolbar.append(self._search_entry)

        # Select All button
        select_all_btn = Gtk.Button(label="All")
        select_all_btn.set_tooltip_text("Select all files")
        select_all_btn.connect("clicked", self._on_select_all)
        toolbar.append(select_all_btn)

        # Select None button
        select_none_btn = Gtk.Button(label="None")
        select_none_btn.set_tooltip_text("Deselect all files")
        select_none_btn.connect("clicked", self._on_select_none)
        toolbar.append(select_none_btn)

        # Scrolled window for file tree
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        # Create a frame to contain the tree view
        tree_frame = Gtk.Frame()
        tree_frame.set_child(scrolled)
        content_box.append(tree_frame)

        # Create tree store and tree view with checkboxes
        self._build_tree_view(scrolled)

        # Bottom status bar with summary info
        status_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_top=8,
        )
        content_box.append(status_box)

        # Summary label (left aligned)
        self._summary_label = Gtk.Label(label="")
        self._summary_label.add_css_class("dim-label")
        self._summary_label.set_xalign(0)
        self._summary_label.set_hexpand(True)
        status_box.append(self._summary_label)

        # Selection status (right side before buttons)
        self._selection_label = Gtk.Label(label="All files selected")
        self._selection_label.add_css_class("dim-label")
        status_box.append(self._selection_label)

        # Action buttons
        button_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_top=8,
            halign=Gtk.Align.END,
        )
        content_box.append(button_box)

        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", self._on_cancel_clicked)
        button_box.append(cancel_button)

        self._extract_selected_button = Gtk.Button(label="Extract Selected")
        self._extract_selected_button.connect("clicked", self._on_extract_selected)
        button_box.append(self._extract_selected_button)

        self._extract_button = Gtk.Button(label="Extract All")
        self._extract_button.add_css_class("suggested-action")
        self._extract_button.connect("clicked", self._on_extract_clicked)
        button_box.append(self._extract_button)

    def _build_tree_view(self, scrolled: Gtk.ScrolledWindow) -> None:
        """Build the file tree view with checkboxes."""
        # Tree store: selected, icon, name, size, type, path
        self._tree_store = Gtk.TreeStore.new([bool, str, str, str, str, str])

        # Tree view
        self._tree_view = Gtk.TreeView(model=self._tree_store)
        self._tree_view.set_headers_visible(True)
        self._tree_view.set_enable_tree_lines(True)
        scrolled.set_child(self._tree_view)

        # Checkbox column
        renderer_toggle = Gtk.CellRendererToggle()
        renderer_toggle.connect("toggled", self._on_checkbox_toggled)
        column_check = Gtk.TreeViewColumn("", renderer_toggle, active=self.COL_SELECTED)
        column_check.set_min_width(30)
        self._tree_view.append_column(column_check)

        # Icon and Name column
        renderer_icon = Gtk.CellRendererPixbuf()
        renderer_text = Gtk.CellRendererText()

        column_name = Gtk.TreeViewColumn("Name")
        column_name.pack_start(renderer_icon, False)
        column_name.pack_start(renderer_text, True)
        column_name.add_attribute(renderer_icon, "icon-name", self.COL_ICON)
        column_name.add_attribute(renderer_text, "text", self.COL_NAME)
        column_name.set_expand(True)
        column_name.set_resizable(True)
        self._tree_view.append_column(column_name)

        # Size column
        renderer_size = Gtk.CellRendererText()
        renderer_size.set_property("xalign", 1.0)
        column_size = Gtk.TreeViewColumn("Size", renderer_size, text=self.COL_SIZE)
        column_size.set_min_width(80)
        self._tree_view.append_column(column_size)

        # Type column
        renderer_type = Gtk.CellRendererText()
        column_type = Gtk.TreeViewColumn("Type", renderer_type, text=self.COL_TYPE)
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

        # Build summary string: "1369 files, 0 dirs | 1.22 GB (1.22 GB compressed)"
        file_count = info.file_count
        dir_count = sum(1 for f in info.files if f.is_directory)
        compressed = self._format_size(info.file_size)
        uncompressed = self._format_size(info.uncompressed_size)

        summary = f"{file_count} files, {dir_count} dirs | {uncompressed} ({compressed} compressed)"
        self._summary_label.set_label(summary)

    def _check_warnings(self) -> None:
        """Check for and display warnings."""
        warnings: list[str] = []

        # Check for password protection
        if self._archive_info is not None and self._archive_info.has_password:
            warnings.append("Password protected")

        # Check for zip bomb
        is_bomb = detect_zip_bomb(self._archive_path)
        if is_bomb:
            warnings.append("Potential zip bomb detected")

        # Display warnings
        if warnings:
            self._has_warnings = True
            self._warnings_box.set_visible(True)

            # Add warning icon
            icon = Gtk.Image(icon_name="dialog-warning-symbolic")
            self._warnings_box.append(icon)

            # Add warning text
            warning_text = " | ".join(warnings)
            label = Gtk.Label(label=warning_text)
            label.add_css_class("warning")
            self._warnings_box.append(label)

    def _populate_file_tree(self) -> None:
        """Populate the file tree with archive contents."""
        if self._archive_info is None:
            return

        info = self._archive_info
        self._tree_store.clear()
        self._root_items.clear()

        # Build tree structure
        for file_info in info.files:
            parts = Path(file_info.path).parts
            current_level = self._root_items
            current_path = ""

            for i, part in enumerate(parts):
                is_last = i == len(parts) - 1
                is_dir = file_info.is_directory or not is_last
                current_path = f"{current_path}/{part}" if current_path else part

                if part not in current_level:
                    current_level[part] = FileTreeItem(
                        name=part,
                        is_dir=is_dir,
                        size=file_info.size if is_last else 0,
                        path=current_path,
                    )

                if is_dir:
                    current_level = current_level[part].children
                else:
                    break

        # Add items to tree store recursively
        self._add_tree_items(None, self._root_items)

        # Expand first level
        self._tree_view.expand_all()
        self._update_selection_status()

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
            # Apply filter
            if self._filter_text and not self._item_matches_filter(item):
                continue

            icon = "folder-symbolic" if item.is_dir else "text-x-generic-symbolic"
            size_str = "" if item.is_dir else self._format_size(item.size)
            type_str = "Folder" if item.is_dir else self._get_file_type(name)

            tree_iter = self._tree_store.append(
                parent,
                [item.selected, icon, name, size_str, type_str, item.path],
            )

            if item.children:
                self._add_tree_items(tree_iter, item.children)

    def _item_matches_filter(self, item: FileTreeItem) -> bool:
        """Check if item matches current filter."""
        if not self._filter_text:
            return True

        filter_lower = self._filter_text.lower()

        # Check if name matches
        if filter_lower in item.name.lower():
            return True

        # For directories, check if any child matches
        if item.is_dir:
            for child in item.children.values():
                if self._item_matches_filter(child):
                    return True

        return False

    def _show_error(self, message: str) -> None:
        """Show an error state."""
        self._summary_label.set_label(f"Error: {message}")
        self._extract_button.set_sensitive(False)
        self._extract_selected_button.set_sensitive(False)

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        """Handle search text change."""
        self._filter_text = entry.get_text().strip()
        self._tree_store.clear()
        self._add_tree_items(None, self._root_items)
        self._tree_view.expand_all()

    def _on_select_all(self, _button: Gtk.Button) -> None:
        """Select all files."""
        self._set_all_selected(self._root_items, True)
        self._refresh_tree()
        self._update_selection_status()

    def _on_select_none(self, _button: Gtk.Button) -> None:
        """Deselect all files."""
        self._set_all_selected(self._root_items, False)
        self._refresh_tree()
        self._update_selection_status()

    def _set_all_selected(
        self,
        items: dict[str, FileTreeItem],
        selected: bool,
    ) -> None:
        """Recursively set selection state for all items."""
        for item in items.values():
            item.selected = selected
            if item.children:
                self._set_all_selected(item.children, selected)

    def _on_checkbox_toggled(
        self,
        _renderer: Gtk.CellRendererToggle,
        path_str: str,
    ) -> None:
        """Handle checkbox toggle in tree view."""
        tree_path = Gtk.TreePath.new_from_string(path_str)
        tree_iter = self._tree_store.get_iter(tree_path)

        if tree_iter is None:
            return

        # Toggle the value
        current = self._tree_store.get_value(tree_iter, self.COL_SELECTED)
        new_value = not current
        item_path = self._tree_store.get_value(tree_iter, self.COL_PATH)

        # Update tree store
        self._tree_store.set_value(tree_iter, self.COL_SELECTED, new_value)

        # Update the FileTreeItem
        item = self._find_item_by_path(item_path)
        if item:
            item.selected = new_value
            # If directory, also update children
            if item.is_dir:
                self._set_all_selected(item.children, new_value)
                self._refresh_tree()

        self._update_selection_status()

    def _find_item_by_path(self, path: str) -> FileTreeItem | None:
        """Find a FileTreeItem by its path."""
        parts = path.split("/")
        current_level = self._root_items

        for part in parts[:-1]:
            if part in current_level:
                current_level = current_level[part].children
            else:
                return None

        return current_level.get(parts[-1])

    def _refresh_tree(self) -> None:
        """Refresh the tree view."""
        self._tree_store.clear()
        self._add_tree_items(None, self._root_items)
        self._tree_view.expand_all()

    def _update_selection_status(self) -> None:
        """Update the selection status label."""
        total, selected = self._count_selected(self._root_items)

        if selected == total:
            self._selection_label.set_label("All files selected")
        elif selected == 0:
            self._selection_label.set_label("No files selected")
        else:
            self._selection_label.set_label(f"{selected} of {total} files selected")

        # Enable/disable extract selected button
        self._extract_selected_button.set_sensitive(selected > 0)

    def _count_selected(
        self,
        items: dict[str, FileTreeItem],
    ) -> tuple[int, int]:
        """Count total and selected files (not directories)."""
        total = 0
        selected = 0

        for item in items.values():
            if item.is_dir:
                sub_total, sub_selected = self._count_selected(item.children)
                total += sub_total
                selected += sub_selected
            else:
                total += 1
                if item.selected:
                    selected += 1

        return total, selected

    def get_selected_paths(self) -> list[str]:
        """Get list of selected file paths.

        Returns:
            List of file paths that are selected.
        """
        paths: list[str] = []
        self._collect_selected_paths(self._root_items, paths)
        return paths

    def _collect_selected_paths(
        self,
        items: dict[str, FileTreeItem],
        paths: list[str],
    ) -> None:
        """Recursively collect selected file paths."""
        for item in items.values():
            if item.is_dir:
                self._collect_selected_paths(item.children, paths)
            elif item.selected:
                paths.append(item.path)

    def _on_cancel_clicked(self, _button: Gtk.Button) -> None:
        """Handle cancel button click."""
        self.close()

    def _on_extract_clicked(self, _button: Gtk.Button) -> None:
        """Handle extract all button click."""
        self.emit("extract-requested")
        self.close()

    def _on_extract_selected(self, _button: Gtk.Button) -> None:
        """Handle extract selected button click."""
        selected_paths = self.get_selected_paths()
        self.emit("extract-selected", selected_paths)
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
