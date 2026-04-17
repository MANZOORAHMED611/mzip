"""Tests for GUI widget components.

Note: GTK widgets require a display to be instantiated. These tests
verify the module structure and non-GUI functionality.
"""

from __future__ import annotations

import pytest

from zipextractor.gui.widgets.archive_browser import (
    FileEntry,
    FileEntryObject,
    SortColumn,
    SortOrder,
)
from zipextractor.gui.widgets.file_preview import (
    IMAGE_EXTENSIONS,
    MAX_IMAGE_SIZE,
    MAX_TEXT_SIZE,
    TEXT_EXTENSIONS,
)


class TestFileEntry:
    """Tests for FileEntry dataclass."""

    def test_file_entry_creation(self) -> None:
        """Test creating a FileEntry."""
        entry = FileEntry(
            name="test.txt",
            path="folder/test.txt",
            is_directory=False,
            size=1024,
        )
        assert entry.name == "test.txt"
        assert entry.path == "folder/test.txt"
        assert not entry.is_directory
        assert entry.size == 1024

    def test_file_entry_directory(self) -> None:
        """Test FileEntry for a directory."""
        entry = FileEntry(
            name="folder",
            path="parent/folder",
            is_directory=True,
        )
        assert entry.is_directory
        assert entry.size == 0

    def test_file_entry_extension(self) -> None:
        """Test extension property."""
        txt_entry = FileEntry(name="file.txt", path="file.txt", is_directory=False)
        assert txt_entry.extension == ".txt"

        py_entry = FileEntry(name="script.py", path="script.py", is_directory=False)
        assert py_entry.extension == ".py"

        no_ext = FileEntry(name="README", path="README", is_directory=False)
        assert no_ext.extension == ""

        dir_entry = FileEntry(name="folder.d", path="folder.d", is_directory=True)
        assert dir_entry.extension == ""

    def test_file_entry_compressed_size(self) -> None:
        """Test compressed size attribute."""
        entry = FileEntry(
            name="data.bin",
            path="data.bin",
            is_directory=False,
            size=10000,
            compressed_size=5000,
        )
        assert entry.size == 10000
        assert entry.compressed_size == 5000


class TestSortEnums:
    """Tests for sort-related enums."""

    def test_sort_column_values(self) -> None:
        """Test SortColumn enum values."""
        assert SortColumn.NAME is not None
        assert SortColumn.SIZE is not None
        assert SortColumn.DATE is not None
        assert SortColumn.TYPE is not None

    def test_sort_order_values(self) -> None:
        """Test SortOrder enum values."""
        assert SortOrder.ASCENDING is not None
        assert SortOrder.DESCENDING is not None


class TestFilePreviewConstants:
    """Tests for file preview constants."""

    def test_max_text_size(self) -> None:
        """Test MAX_TEXT_SIZE constant."""
        assert MAX_TEXT_SIZE == 1 * 1024 * 1024  # 1 MB

    def test_max_image_size(self) -> None:
        """Test MAX_IMAGE_SIZE constant."""
        assert MAX_IMAGE_SIZE == 10 * 1024 * 1024  # 10 MB

    def test_text_extensions_include_common_types(self) -> None:
        """Test that common text extensions are included."""
        assert ".txt" in TEXT_EXTENSIONS
        assert ".md" in TEXT_EXTENSIONS
        assert ".py" in TEXT_EXTENSIONS
        assert ".js" in TEXT_EXTENSIONS
        assert ".json" in TEXT_EXTENSIONS
        assert ".xml" in TEXT_EXTENSIONS
        assert ".html" in TEXT_EXTENSIONS
        assert ".css" in TEXT_EXTENSIONS
        assert ".rs" in TEXT_EXTENSIONS
        assert ".go" in TEXT_EXTENSIONS

    def test_image_extensions_include_common_types(self) -> None:
        """Test that common image extensions are included."""
        assert ".jpg" in IMAGE_EXTENSIONS
        assert ".jpeg" in IMAGE_EXTENSIONS
        assert ".png" in IMAGE_EXTENSIONS
        assert ".gif" in IMAGE_EXTENSIONS
        assert ".svg" in IMAGE_EXTENSIONS
        assert ".webp" in IMAGE_EXTENSIONS


class TestWidgetImports:
    """Test that widget modules can be imported."""

    def test_import_archive_browser(self) -> None:
        """Test importing archive_browser module."""
        from zipextractor.gui.widgets import archive_browser

        assert hasattr(archive_browser, "ArchiveBrowser")
        assert hasattr(archive_browser, "FileEntry")
        assert hasattr(archive_browser, "FileEntryObject")

    def test_import_file_preview(self) -> None:
        """Test importing file_preview module."""
        from zipextractor.gui.widgets import file_preview

        assert hasattr(file_preview, "FilePreview")
        assert hasattr(file_preview, "MAX_TEXT_SIZE")
        assert hasattr(file_preview, "MAX_IMAGE_SIZE")

    def test_import_archive_inspector(self) -> None:
        """Test importing archive_inspector module."""
        from zipextractor.gui.widgets import archive_inspector

        assert hasattr(archive_inspector, "ArchiveInspector")
        assert hasattr(archive_inspector, "FileTreeItem")

    def test_widgets_init_exports(self) -> None:
        """Test that __init__ exports all expected widgets."""
        from zipextractor.gui import widgets

        assert hasattr(widgets, "ArchiveBrowser")
        assert hasattr(widgets, "FileEntry")
        assert hasattr(widgets, "FilePreview")
        assert hasattr(widgets, "ArchiveInspector")


class TestFileTreeItem:
    """Tests for FileTreeItem class."""

    def test_file_tree_item_creation(self) -> None:
        """Test creating a FileTreeItem."""
        from zipextractor.gui.widgets.archive_inspector import FileTreeItem

        item = FileTreeItem(
            name="document.pdf",
            is_dir=False,
            size=2048,
            path="docs/document.pdf",
        )
        assert item.name == "document.pdf"
        assert not item.is_dir
        assert item.size == 2048
        assert item.path == "docs/document.pdf"
        assert item.selected is True  # Default selected
        assert item.children == {}

    def test_file_tree_item_directory(self) -> None:
        """Test FileTreeItem for directory."""
        from zipextractor.gui.widgets.archive_inspector import FileTreeItem

        item = FileTreeItem(
            name="src",
            is_dir=True,
            path="project/src",
        )
        assert item.is_dir
        assert item.size == 0
        assert item.children == {}

    def test_file_tree_item_children(self) -> None:
        """Test adding children to FileTreeItem."""
        from zipextractor.gui.widgets.archive_inspector import FileTreeItem

        parent = FileTreeItem(name="root", is_dir=True, path="root")
        child1 = FileTreeItem(name="file1.txt", is_dir=False, size=100, path="root/file1.txt")
        child2 = FileTreeItem(name="file2.txt", is_dir=False, size=200, path="root/file2.txt")

        parent.children["file1.txt"] = child1
        parent.children["file2.txt"] = child2

        assert len(parent.children) == 2
        assert parent.children["file1.txt"].size == 100
        assert parent.children["file2.txt"].size == 200


class TestFileEntryObject:
    """Tests for FileEntryObject GObject wrapper."""

    @pytest.mark.skipif(
        True,
        reason="Requires GTK/GObject runtime",
    )
    def test_file_entry_object_creation(self) -> None:
        """Test creating FileEntryObject."""
        entry = FileEntry(
            name="test.py",
            path="src/test.py",
            is_directory=False,
            size=500,
        )
        obj = FileEntryObject(entry)
        assert obj.entry == entry
        assert obj.name == "test.py"
        assert obj.path == "src/test.py"
        assert not obj.is_directory
