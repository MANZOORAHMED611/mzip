"""Archive browser widget with file manager-style navigation.

This module provides a widget for browsing archive contents with
breadcrumb navigation, sorting, and folder-based views.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import PurePosixPath

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gio, GLib, GObject, Gtk, Pango

from zipextractor.utils.logging import get_logger

logger = get_logger(__name__)


class SortColumn(Enum):
    """Column to sort by."""

    NAME = auto()
    SIZE = auto()
    DATE = auto()
    TYPE = auto()


class SortOrder(Enum):
    """Sort order."""

    ASCENDING = auto()
    DESCENDING = auto()


@dataclass
class FileEntry:
    """Represents a file or folder in the archive.

    Attributes:
        name: File or folder name.
        path: Full path within archive.
        is_directory: Whether this is a directory.
        size: File size in bytes (0 for directories).
        compressed_size: Compressed size in bytes.
        modified: Modification timestamp.
        crc: CRC32 checksum.
    """

    name: str
    path: str
    is_directory: bool
    size: int = 0
    compressed_size: int = 0
    modified: str = ""
    crc: int = 0

    @property
    def extension(self) -> str:
        """Get file extension."""
        if self.is_directory:
            return ""
        return PurePosixPath(self.name).suffix.lower()


class ArchiveBrowser(Gtk.Box):
    """File manager-style archive browser widget.

    Features:
    - Breadcrumb navigation
    - Folder hierarchy view
    - Sorting by name, size, date, type
    - File selection (single or multiple)
    - Integration with file preview

    Signals:
        file-selected: Emitted when a file is selected (path: str)
        file-activated: Emitted when a file is double-clicked (path: str)
        directory-changed: Emitted when current directory changes (path: str)
        selection-changed: Emitted when selection changes (paths: list[str])
    """

    __gtype_name__ = "ArchiveBrowser"

    __gsignals__ = {
        "file-selected": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "file-activated": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "directory-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "selection-changed": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
    }

    def __init__(self) -> None:
        """Initialize the archive browser widget."""
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )

        # State
        self._entries: dict[str, FileEntry] = {}
        self._current_path: str = ""
        self._sort_column = SortColumn.NAME
        self._sort_order = SortOrder.ASCENDING
        self._selection_mode = Gtk.SelectionMode.SINGLE

        self._build_ui()
        logger.debug("ArchiveBrowser widget initialized")

    @property
    def current_path(self) -> str:
        """Get current directory path."""
        return self._current_path

    @property
    def selected_paths(self) -> list[str]:
        """Get list of selected file paths."""
        selection = self._list_view.get_model()
        if not isinstance(selection, Gtk.SingleSelection | Gtk.MultiSelection):
            return []

        paths = []
        if isinstance(selection, Gtk.SingleSelection):
            item = selection.get_selected_item()
            if item:
                paths.append(item.path)
        else:
            # MultiSelection
            bitset = selection.get_selection()
            model = selection.get_model()
            if model:
                iter_val = Gtk.BitsetIter()
                valid, pos = bitset.init_at(iter_val, 0)
                while valid:
                    item = model.get_item(pos)
                    if item:
                        paths.append(item.path)
                    valid, pos = iter_val.next()

        return paths

    def _build_ui(self) -> None:  # noqa: PLR0915
        """Build the widget UI."""
        # Toolbar with breadcrumb and sort options
        toolbar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6,
            margin_start=6,
            margin_end=6,
            margin_top=6,
            margin_bottom=6,
        )
        self.append(toolbar)

        # Back button
        self._back_button = Gtk.Button(icon_name="go-previous-symbolic")
        self._back_button.set_tooltip_text("Go to parent folder")
        self._back_button.connect("clicked", self._on_back_clicked)
        self._back_button.set_sensitive(False)
        toolbar.append(self._back_button)

        # Home button
        home_button = Gtk.Button(icon_name="go-home-symbolic")
        home_button.set_tooltip_text("Go to root")
        home_button.connect("clicked", self._on_home_clicked)
        toolbar.append(home_button)

        # Breadcrumb
        self._breadcrumb_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=0,
        )
        self._breadcrumb_box.set_hexpand(True)

        breadcrumb_scroll = Gtk.ScrolledWindow()
        breadcrumb_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        breadcrumb_scroll.set_child(self._breadcrumb_box)
        toolbar.append(breadcrumb_scroll)

        # Sort menu button
        sort_button = Gtk.MenuButton(icon_name="view-sort-ascending-symbolic")
        sort_button.set_tooltip_text("Sort options")
        sort_menu = self._create_sort_menu()
        sort_button.set_menu_model(sort_menu)
        toolbar.append(sort_button)

        # Separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.append(separator)

        # File list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        self.append(scrolled)

        # Create list model
        self._store = Gio.ListStore.new(FileEntryObject)

        # Selection model
        self._selection_model = Gtk.SingleSelection(model=self._store)
        self._selection_model.connect("selection-changed", self._on_selection_changed)

        # Create list view with factory
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_factory_setup)
        factory.connect("bind", self._on_factory_bind)

        self._list_view = Gtk.ListView(
            model=self._selection_model,
            factory=factory,
        )
        self._list_view.connect("activate", self._on_item_activated)
        self._list_view.add_css_class("navigation-sidebar")
        scrolled.set_child(self._list_view)

        # Status bar
        self._status_bar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_start=12,
            margin_end=12,
            margin_top=6,
            margin_bottom=6,
        )
        self.append(self._status_bar)

        self._item_count_label = Gtk.Label(label="No items")
        self._item_count_label.add_css_class("dim-label")
        self._item_count_label.set_xalign(0)
        self._status_bar.append(self._item_count_label)

        self._selection_label = Gtk.Label(label="")
        self._selection_label.add_css_class("dim-label")
        self._selection_label.set_hexpand(True)
        self._selection_label.set_xalign(1)
        self._status_bar.append(self._selection_label)

        # Set up sort actions
        self._setup_actions()

    def _create_sort_menu(self) -> Gio.Menu:
        """Create sort options menu."""
        menu = Gio.Menu()

        # Sort by section
        sort_by = Gio.Menu()
        sort_by.append("Name", "browser.sort-by-name")
        sort_by.append("Size", "browser.sort-by-size")
        sort_by.append("Date", "browser.sort-by-date")
        sort_by.append("Type", "browser.sort-by-type")
        menu.append_section("Sort By", sort_by)

        # Sort order section
        order = Gio.Menu()
        order.append("Ascending", "browser.sort-ascending")
        order.append("Descending", "browser.sort-descending")
        menu.append_section("Order", order)

        return menu

    def _setup_actions(self) -> None:
        """Set up action handlers."""
        action_group = Gio.SimpleActionGroup()

        # Sort actions
        for column in ["name", "size", "date", "type"]:
            action = Gio.SimpleAction.new(f"sort-by-{column}", None)
            action.connect("activate", self._on_sort_by, column)
            action_group.add_action(action)

        # Order actions
        asc_action = Gio.SimpleAction.new("sort-ascending", None)
        asc_action.connect("activate", self._on_sort_order, "ascending")
        action_group.add_action(asc_action)

        desc_action = Gio.SimpleAction.new("sort-descending", None)
        desc_action.connect("activate", self._on_sort_order, "descending")
        action_group.add_action(desc_action)

        self.insert_action_group("browser", action_group)

    def _on_sort_by(
        self,
        _action: Gio.SimpleAction,
        _param: GLib.Variant | None,
        column: str,
    ) -> None:
        """Handle sort column change."""
        column_map = {
            "name": SortColumn.NAME,
            "size": SortColumn.SIZE,
            "date": SortColumn.DATE,
            "type": SortColumn.TYPE,
        }
        self._sort_column = column_map.get(column, SortColumn.NAME)
        self._refresh_view()

    def _on_sort_order(
        self,
        _action: Gio.SimpleAction,
        _param: GLib.Variant | None,
        order: str,
    ) -> None:
        """Handle sort order change."""
        self._sort_order = (
            SortOrder.ASCENDING if order == "ascending" else SortOrder.DESCENDING
        )
        self._refresh_view()

    def _on_factory_setup(
        self,
        _factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Set up list item widget."""
        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_start=6,
            margin_end=6,
            margin_top=6,
            margin_bottom=6,
        )

        icon = Gtk.Image()
        icon.set_icon_size(Gtk.IconSize.NORMAL)
        box.append(icon)

        label_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        label_box.set_hexpand(True)
        box.append(label_box)

        name_label = Gtk.Label()
        name_label.set_xalign(0)
        name_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        label_box.append(name_label)

        info_label = Gtk.Label()
        info_label.set_xalign(0)
        info_label.add_css_class("dim-label")
        info_label.add_css_class("caption")
        label_box.append(info_label)

        list_item.set_child(box)

    def _on_factory_bind(
        self,
        _factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
    ) -> None:
        """Bind data to list item widget."""
        entry_obj = list_item.get_item()
        if not isinstance(entry_obj, FileEntryObject):
            return

        entry = entry_obj.entry
        box = list_item.get_child()
        if not isinstance(box, Gtk.Box):
            return

        icon = box.get_first_child()
        label_box = icon.get_next_sibling() if icon else None

        if isinstance(icon, Gtk.Image):
            if entry.is_directory:
                icon.set_from_icon_name("folder-symbolic")
            else:
                icon.set_from_icon_name(self._get_icon_for_file(entry.name))

        if isinstance(label_box, Gtk.Box):
            name_label = label_box.get_first_child()
            info_label = name_label.get_next_sibling() if name_label else None

            if isinstance(name_label, Gtk.Label):
                name_label.set_label(entry.name)

            if isinstance(info_label, Gtk.Label):
                if entry.is_directory:
                    info_label.set_label("Folder")
                else:
                    info_label.set_label(self._format_size(entry.size))

    def _on_item_activated(
        self,
        _list_view: Gtk.ListView,
        position: int,
    ) -> None:
        """Handle item double-click/activation."""
        item = self._store.get_item(position)
        if not isinstance(item, FileEntryObject):
            return

        entry = item.entry
        if entry.is_directory:
            self.navigate_to(entry.path)
        else:
            self.emit("file-activated", entry.path)

    def _on_selection_changed(
        self,
        _selection: Gtk.SingleSelection | Gtk.MultiSelection,
        _position: int,
        _n_items: int,
    ) -> None:
        """Handle selection change."""
        paths = self.selected_paths
        self.emit("selection-changed", paths)

        if paths:
            count = len(paths)
            if count == 1:
                # Emit file-selected for single selection
                self.emit("file-selected", paths[0])
                self._selection_label.set_label("1 item selected")
            else:
                self._selection_label.set_label(f"{count} items selected")
        else:
            self._selection_label.set_label("")

    def _on_back_clicked(self, _button: Gtk.Button) -> None:
        """Handle back button click."""
        if self._current_path:
            parent = str(PurePosixPath(self._current_path).parent)
            if parent == ".":
                parent = ""
            self.navigate_to(parent)

    def _on_home_clicked(self, _button: Gtk.Button) -> None:
        """Handle home button click."""
        self.navigate_to("")

    def set_entries(self, entries: list[FileEntry]) -> None:
        """Set the archive entries to display.

        Args:
            entries: List of file/folder entries.
        """
        self._entries.clear()
        for entry in entries:
            self._entries[entry.path] = entry

        # Navigate to root
        self.navigate_to("")

    def navigate_to(self, path: str) -> None:
        """Navigate to a directory.

        Args:
            path: Directory path to navigate to.
        """
        self._current_path = path
        self._back_button.set_sensitive(bool(path))
        self._update_breadcrumb()
        self._refresh_view()
        self.emit("directory-changed", path)

    def _update_breadcrumb(self) -> None:
        """Update breadcrumb navigation."""
        # Clear existing breadcrumb
        while True:
            child = self._breadcrumb_box.get_first_child()
            if child is None:
                break
            self._breadcrumb_box.remove(child)

        # Add root
        root_btn = Gtk.Button(label="Archive")
        root_btn.add_css_class("flat")
        root_btn.connect("clicked", lambda _: self.navigate_to(""))
        self._breadcrumb_box.append(root_btn)

        if self._current_path:
            parts = PurePosixPath(self._current_path).parts
            current = ""

            for part in parts:
                # Separator
                sep = Gtk.Label(label="/")
                sep.add_css_class("dim-label")
                self._breadcrumb_box.append(sep)

                # Part button
                current = f"{current}/{part}" if current else part
                path_for_btn = current  # Capture for closure

                btn = Gtk.Button(label=part)
                btn.add_css_class("flat")
                btn.connect("clicked", lambda _, p=path_for_btn: self.navigate_to(p))
                self._breadcrumb_box.append(btn)

    def _refresh_view(self) -> None:
        """Refresh the file list view."""
        # Get entries for current directory
        current_entries = self._get_entries_for_path(self._current_path)

        # Sort entries
        sorted_entries = self._sort_entries(current_entries)

        # Update store
        self._store.remove_all()
        for entry in sorted_entries:
            self._store.append(FileEntryObject(entry))

        # Update status
        folder_count = sum(1 for e in sorted_entries if e.is_directory)
        file_count = len(sorted_entries) - folder_count

        if folder_count and file_count:
            self._item_count_label.set_label(
                f"{folder_count} folders, {file_count} files"
            )
        elif folder_count:
            self._item_count_label.set_label(
                f"{folder_count} folder{'s' if folder_count > 1 else ''}"
            )
        elif file_count:
            self._item_count_label.set_label(
                f"{file_count} file{'s' if file_count > 1 else ''}"
            )
        else:
            self._item_count_label.set_label("Empty folder")

    def _get_entries_for_path(self, path: str) -> list[FileEntry]:
        """Get immediate children of a path."""
        entries = []
        seen_dirs: set[str] = set()

        prefix = f"{path}/" if path else ""

        for entry_path, entry in self._entries.items():
            # Skip if not under current path
            if path and not entry_path.startswith(prefix):
                continue
            if not path and "/" in entry_path.lstrip("/"):
                # Check if this is a nested item
                # For root, we want only top-level items
                top_part = entry_path.split("/")[0]
                if top_part not in seen_dirs:
                    # This is a subdirectory we haven't seen
                    seen_dirs.add(top_part)
                    entries.append(
                        FileEntry(
                            name=top_part,
                            path=top_part,
                            is_directory=True,
                        )
                    )
                continue

            # Get relative path
            relative = entry_path[len(prefix):] if prefix else entry_path

            # Skip self
            if not relative:
                continue

            # If contains slash, it's nested - add parent directory
            if "/" in relative:
                dir_name = relative.split("/")[0]
                dir_path = f"{prefix}{dir_name}" if prefix else dir_name
                if dir_path not in seen_dirs:
                    seen_dirs.add(dir_path)
                    entries.append(
                        FileEntry(
                            name=dir_name,
                            path=dir_path,
                            is_directory=True,
                        )
                    )
            else:
                # Direct child
                entries.append(entry)

        return entries

    def _sort_entries(self, entries: list[FileEntry]) -> list[FileEntry]:
        """Sort entries according to current sort settings."""
        # Directories always come first
        dirs = [e for e in entries if e.is_directory]
        files = [e for e in entries if not e.is_directory]

        reverse = self._sort_order == SortOrder.DESCENDING

        if self._sort_column == SortColumn.NAME:
            dirs.sort(key=lambda e: e.name.lower(), reverse=reverse)
            files.sort(key=lambda e: e.name.lower(), reverse=reverse)
        elif self._sort_column == SortColumn.SIZE:
            dirs.sort(key=lambda e: e.name.lower(), reverse=reverse)
            files.sort(key=lambda e: e.size, reverse=reverse)
        elif self._sort_column == SortColumn.DATE:
            dirs.sort(key=lambda e: e.modified, reverse=reverse)
            files.sort(key=lambda e: e.modified, reverse=reverse)
        elif self._sort_column == SortColumn.TYPE:
            dirs.sort(key=lambda e: e.name.lower(), reverse=reverse)
            files.sort(key=lambda e: (e.extension, e.name.lower()), reverse=reverse)

        return dirs + files

    @staticmethod
    def _get_icon_for_file(filename: str) -> str:
        """Get icon name for a file."""
        suffix = PurePosixPath(filename).suffix.lower()

        icon_map = {
            # Documents
            ".pdf": "x-office-document-symbolic",
            ".doc": "x-office-document-symbolic",
            ".docx": "x-office-document-symbolic",
            ".odt": "x-office-document-symbolic",
            ".txt": "text-x-generic-symbolic",
            ".md": "text-x-generic-symbolic",
            # Spreadsheets
            ".xls": "x-office-spreadsheet-symbolic",
            ".xlsx": "x-office-spreadsheet-symbolic",
            ".ods": "x-office-spreadsheet-symbolic",
            ".csv": "x-office-spreadsheet-symbolic",
            # Presentations
            ".ppt": "x-office-presentation-symbolic",
            ".pptx": "x-office-presentation-symbolic",
            ".odp": "x-office-presentation-symbolic",
            # Images
            ".jpg": "image-x-generic-symbolic",
            ".jpeg": "image-x-generic-symbolic",
            ".png": "image-x-generic-symbolic",
            ".gif": "image-x-generic-symbolic",
            ".svg": "image-x-generic-symbolic",
            ".webp": "image-x-generic-symbolic",
            # Audio
            ".mp3": "audio-x-generic-symbolic",
            ".wav": "audio-x-generic-symbolic",
            ".ogg": "audio-x-generic-symbolic",
            ".flac": "audio-x-generic-symbolic",
            # Video
            ".mp4": "video-x-generic-symbolic",
            ".mkv": "video-x-generic-symbolic",
            ".avi": "video-x-generic-symbolic",
            ".webm": "video-x-generic-symbolic",
            # Code
            ".py": "text-x-script-symbolic",
            ".js": "text-x-script-symbolic",
            ".ts": "text-x-script-symbolic",
            ".java": "text-x-script-symbolic",
            ".c": "text-x-script-symbolic",
            ".cpp": "text-x-script-symbolic",
            ".h": "text-x-script-symbolic",
            ".rs": "text-x-script-symbolic",
            ".go": "text-x-script-symbolic",
            # Archives
            ".zip": "package-x-generic-symbolic",
            ".tar": "package-x-generic-symbolic",
            ".gz": "package-x-generic-symbolic",
            ".7z": "package-x-generic-symbolic",
            ".rar": "package-x-generic-symbolic",
            # Executables
            ".exe": "application-x-executable-symbolic",
            ".sh": "application-x-executable-symbolic",
            ".bin": "application-x-executable-symbolic",
        }

        return icon_map.get(suffix, "text-x-generic-symbolic")

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

    def set_selection_mode(self, mode: Gtk.SelectionMode) -> None:
        """Set selection mode (single or multiple).

        Args:
            mode: GTK selection mode.
        """
        self._selection_mode = mode
        if mode == Gtk.SelectionMode.MULTIPLE:
            self._selection_model = Gtk.MultiSelection(model=self._store)
        else:
            self._selection_model = Gtk.SingleSelection(model=self._store)
        self._selection_model.connect("selection-changed", self._on_selection_changed)
        self._list_view.set_model(self._selection_model)

    def clear(self) -> None:
        """Clear all entries."""
        self._entries.clear()
        self._store.remove_all()
        self._current_path = ""
        self._update_breadcrumb()
        self._item_count_label.set_label("No items")


class FileEntryObject(GObject.Object):
    """GObject wrapper for FileEntry to use in Gio.ListStore."""

    __gtype_name__ = "FileEntryObject"

    def __init__(self, entry: FileEntry) -> None:
        """Initialize with a FileEntry."""
        super().__init__()
        self._entry = entry

    @property
    def entry(self) -> FileEntry:
        """Get the wrapped FileEntry."""
        return self._entry

    @property
    def path(self) -> str:
        """Get the entry path."""
        return self._entry.path

    @property
    def name(self) -> str:
        """Get the entry name."""
        return self._entry.name

    @property
    def is_directory(self) -> bool:
        """Check if entry is a directory."""
        return self._entry.is_directory
