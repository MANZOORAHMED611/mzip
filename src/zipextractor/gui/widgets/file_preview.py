"""File preview widget for displaying archive file contents.

This module provides a widget that can preview text files, images,
and code with syntax highlighting from within archives.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, GdkPixbuf, Gtk, Pango

from zipextractor.utils.logging import get_logger

logger = get_logger(__name__)

# Maximum file size to preview (1 MB for text, 10 MB for images)
MAX_TEXT_SIZE = 1 * 1024 * 1024
MAX_IMAGE_SIZE = 10 * 1024 * 1024

# File extensions that can be previewed as text
TEXT_EXTENSIONS = {
    # Plain text
    ".txt", ".md", ".rst", ".log", ".csv", ".tsv",
    # Configuration
    ".json", ".yaml", ".yml", ".xml", ".toml", ".ini", ".cfg", ".conf",
    ".properties", ".env",
    # Code - Python
    ".py", ".pyi", ".pyw",
    # Code - Web
    ".html", ".htm", ".css", ".scss", ".sass", ".less",
    ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte",
    # Code - Systems
    ".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".hxx",
    ".rs", ".go", ".java", ".kt", ".scala", ".swift",
    # Code - Scripting
    ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd",
    ".rb", ".php", ".pl", ".pm", ".lua", ".r",
    # Code - Data
    ".sql", ".graphql", ".proto",
    # Documents
    ".tex", ".bib", ".sty",
    # Other
    ".gitignore", ".dockerignore", ".editorconfig",
    "Makefile", "Dockerfile", "Vagrantfile",
}

# File extensions for images
IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
    ".svg", ".ico", ".tiff", ".tif",
}

# Syntax highlighting colors (Adwaita-compatible)
SYNTAX_COLORS = {
    "keyword": "#1c71d8",  # Blue
    "string": "#26a269",   # Green
    "comment": "#5e5c64",  # Gray
    "number": "#c64600",   # Orange
    "function": "#613583", # Purple
    "type": "#a51d2d",     # Red
}


class FilePreview(Gtk.Box):
    """Widget for previewing file contents from archives.

    Supports:
    - Text files with optional syntax highlighting
    - Images (PNG, JPEG, GIF, etc.)
    - Binary file info display

    Properties:
        filename: The name of the currently previewed file.
        file_type: The detected type of the file.
    """

    __gtype_name__ = "FilePreview"

    def __init__(self) -> None:
        """Initialize the file preview widget."""
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )

        self._current_filename: str | None = None
        self._current_type: str = "unknown"

        self._build_ui()
        self._show_placeholder()

        logger.debug("FilePreview widget initialized")

    @property
    def filename(self) -> str | None:
        """Get the currently previewed filename."""
        return self._current_filename

    @property
    def file_type(self) -> str:
        """Get the detected file type."""
        return self._current_type

    def _build_ui(self) -> None:  # noqa: PLR0915
        """Build the widget UI."""
        # Header with file info
        self._header = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_start=12,
            margin_end=12,
            margin_top=8,
            margin_bottom=8,
        )
        self.append(self._header)

        # File icon
        self._file_icon = Gtk.Image(icon_name="text-x-generic-symbolic")
        self._header.append(self._file_icon)

        # File name and info
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info_box.set_hexpand(True)
        self._header.append(info_box)

        self._filename_label = Gtk.Label(
            label="No file selected",
            xalign=0,
            ellipsize=Pango.EllipsizeMode.MIDDLE,
        )
        self._filename_label.add_css_class("heading")
        info_box.append(self._filename_label)

        self._info_label = Gtk.Label(
            label="",
            xalign=0,
        )
        self._info_label.add_css_class("dim-label")
        self._info_label.add_css_class("caption")
        info_box.append(self._info_label)

        # Separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.append(separator)

        # Content area (stack for different preview types)
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_vexpand(True)
        self.append(self._stack)

        # Placeholder page
        self._placeholder = Adw.StatusPage(
            icon_name="document-open-symbolic",
            title="No Preview",
            description="Select a file to preview its contents",
        )
        self._stack.add_named(self._placeholder, "placeholder")

        # Text preview page
        text_scrolled = Gtk.ScrolledWindow()
        text_scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self._text_view = Gtk.TextView()
        self._text_view.set_editable(False)
        self._text_view.set_cursor_visible(False)
        self._text_view.set_monospace(True)
        self._text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._text_view.set_left_margin(12)
        self._text_view.set_right_margin(12)
        self._text_view.set_top_margin(12)
        self._text_view.set_bottom_margin(12)
        text_scrolled.set_child(self._text_view)
        self._stack.add_named(text_scrolled, "text")

        # Image preview page
        image_scrolled = Gtk.ScrolledWindow()
        image_scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        # Use a box to center the image
        image_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )
        image_scrolled.set_child(image_box)

        self._image = Gtk.Picture()
        self._image.set_can_shrink(True)
        self._image.set_keep_aspect_ratio(True)
        image_box.append(self._image)
        self._stack.add_named(image_scrolled, "image")

        # Binary info page
        self._binary_page = Adw.StatusPage(
            icon_name="application-x-executable-symbolic",
            title="Binary File",
            description="This file cannot be previewed",
        )
        self._stack.add_named(self._binary_page, "binary")

        # Error page
        self._error_page = Adw.StatusPage(
            icon_name="dialog-error-symbolic",
            title="Preview Error",
            description="Could not load file preview",
        )
        self._stack.add_named(self._error_page, "error")

        # Too large page
        self._large_page = Adw.StatusPage(
            icon_name="dialog-warning-symbolic",
            title="File Too Large",
            description="This file is too large to preview",
        )
        self._stack.add_named(self._large_page, "large")

    def _show_placeholder(self) -> None:
        """Show the placeholder state."""
        self._current_filename = None
        self._current_type = "unknown"
        self._filename_label.set_label("No file selected")
        self._info_label.set_label("")
        self._file_icon.set_from_icon_name("text-x-generic-symbolic")
        self._stack.set_visible_child_name("placeholder")

    def clear(self) -> None:
        """Clear the preview and show placeholder."""
        self._show_placeholder()

    def preview_data(
        self,
        filename: str,
        data: bytes,
        size: int | None = None,
    ) -> None:
        """Preview file data.

        Args:
            filename: The filename (used for type detection).
            data: The file content bytes.
            size: Original file size (if different from data length).
        """
        self._current_filename = filename
        actual_size = size if size is not None else len(data)

        # Update header
        self._filename_label.set_label(filename)
        self._info_label.set_label(self._format_size(actual_size))

        # Detect file type and preview accordingly
        file_type = self._detect_type(filename)
        self._current_type = file_type

        # Set appropriate icon
        self._file_icon.set_from_icon_name(self._get_icon_for_type(file_type))

        try:
            if file_type == "text":
                if actual_size > MAX_TEXT_SIZE:
                    self._show_large_warning(actual_size, MAX_TEXT_SIZE)
                else:
                    self._preview_text(filename, data)
            elif file_type == "image":
                if actual_size > MAX_IMAGE_SIZE:
                    self._show_large_warning(actual_size, MAX_IMAGE_SIZE)
                else:
                    self._preview_image(data)
            else:
                self._show_binary_info(filename, actual_size)
        except Exception as e:
            logger.exception("Preview error for %s: %s", filename, e)
            self._show_error(str(e))

    def preview_file(self, file_path: Path) -> None:
        """Preview a file from the filesystem.

        Args:
            file_path: Path to the file to preview.
        """
        try:
            size = file_path.stat().st_size
            data = file_path.read_bytes()
            self.preview_data(file_path.name, data, size)
        except Exception as e:
            logger.exception("Failed to read file %s: %s", file_path, e)
            self._show_error(str(e))

    def _detect_type(self, filename: str) -> str:
        """Detect file type from filename."""
        suffix = Path(filename).suffix.lower()
        name_lower = filename.lower()

        # Check for special files without extensions
        if name_lower in {"makefile", "dockerfile", "vagrantfile", "gemfile"}:
            return "text"

        if suffix in TEXT_EXTENSIONS:
            return "text"
        if suffix in IMAGE_EXTENSIONS:
            return "image"

        # Try MIME type
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type:
            if mime_type.startswith("text/"):
                return "text"
            if mime_type.startswith("image/"):
                return "image"

        return "binary"

    def _get_icon_for_type(self, file_type: str) -> str:
        """Get icon name for file type."""
        icons = {
            "text": "text-x-generic-symbolic",
            "image": "image-x-generic-symbolic",
            "binary": "application-x-executable-symbolic",
        }
        return icons.get(file_type, "text-x-generic-symbolic")

    def _preview_text(self, filename: str, data: bytes) -> None:
        """Preview text file."""
        # Try to decode as UTF-8, fallback to latin-1
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = data.decode("latin-1")
            except UnicodeDecodeError:
                text = data.decode("utf-8", errors="replace")

        # Apply syntax highlighting if applicable
        buffer = self._text_view.get_buffer()
        suffix = Path(filename).suffix.lower()

        if self._should_highlight(suffix):
            self._apply_highlighting(buffer, text, suffix)
        else:
            buffer.set_text(text)

        self._stack.set_visible_child_name("text")

    def _should_highlight(self, suffix: str) -> bool:
        """Check if syntax highlighting should be applied."""
        highlight_extensions = {
            ".py", ".js", ".ts", ".jsx", ".tsx",
            ".json", ".xml", ".html", ".css",
            ".c", ".cpp", ".h", ".hpp",
            ".rs", ".go", ".java", ".kt",
            ".sh", ".bash", ".sql",
        }
        return suffix in highlight_extensions

    def _apply_highlighting(
        self,
        buffer: Gtk.TextBuffer,
        text: str,
        suffix: str,
    ) -> None:
        """Apply basic syntax highlighting to text.

        This is a simplified highlighter - for full highlighting,
        consider using GtkSourceView.
        """
        # For now, just set plain text
        # Full syntax highlighting would require GtkSourceView
        buffer.set_text(text)

        # Create tags for highlighting
        tag_table = buffer.get_tag_table()

        # Create or get comment tag
        comment_tag = tag_table.lookup("comment")
        if comment_tag is None:
            comment_tag = buffer.create_tag(
                "comment",
                foreground=SYNTAX_COLORS["comment"],
                style=Pango.Style.ITALIC,
            )

        # Create or get string tag
        string_tag = tag_table.lookup("string")
        if string_tag is None:
            string_tag = buffer.create_tag(
                "string",
                foreground=SYNTAX_COLORS["string"],
            )

        # Apply basic highlighting for common patterns
        self._highlight_comments(buffer, text, suffix)
        self._highlight_strings(buffer, text)

    def _highlight_comments(
        self,
        buffer: Gtk.TextBuffer,
        text: str,
        suffix: str,
    ) -> None:
        """Highlight comment patterns."""
        comment_tag = buffer.get_tag_table().lookup("comment")
        if not comment_tag:
            return

        lines = text.split("\n")
        offset = 0

        # Determine comment prefix
        if suffix in {".py", ".sh", ".bash", ".yaml", ".yml", ".toml"}:
            comment_prefix = "#"
        elif suffix in {".c", ".cpp", ".h", ".hpp", ".js", ".ts", ".java", ".go", ".rs"}:
            comment_prefix = "//"
        elif suffix == ".sql":
            comment_prefix = "--"
        else:
            return

        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith(comment_prefix):
                # Find start of comment
                comment_start = line.find(comment_prefix)
                start_iter = buffer.get_iter_at_offset(offset + comment_start)
                end_iter = buffer.get_iter_at_offset(offset + len(line))
                buffer.apply_tag(comment_tag, start_iter, end_iter)
            offset += len(line) + 1  # +1 for newline

    def _highlight_strings(self, buffer: Gtk.TextBuffer, text: str) -> None:
        """Highlight string literals."""
        string_tag = buffer.get_tag_table().lookup("string")
        if not string_tag:
            return

        # Simple string detection (not perfect but handles common cases)
        in_string = False
        string_char = None
        string_start = 0

        for i, char in enumerate(text):
            if not in_string:
                if char in {'"', "'"}:
                    in_string = True
                    string_char = char
                    string_start = i
            elif char == string_char and (i == 0 or text[i - 1] != "\\"):
                # End of string
                start_iter = buffer.get_iter_at_offset(string_start)
                end_iter = buffer.get_iter_at_offset(i + 1)
                buffer.apply_tag(string_tag, start_iter, end_iter)
                in_string = False
                string_char = None

    def _preview_image(self, data: bytes) -> None:
        """Preview image file."""
        try:
            # Load image from bytes
            loader = GdkPixbuf.PixbufLoader()
            loader.write(data)
            loader.close()

            pixbuf = loader.get_pixbuf()
            if pixbuf:
                # Create texture from pixbuf
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                self._image.set_paintable(texture)

                # Update info with image dimensions
                width = pixbuf.get_width()
                height = pixbuf.get_height()
                self._info_label.set_label(
                    f"{self._format_size(len(data))} - {width}x{height} pixels"
                )

                self._stack.set_visible_child_name("image")
            else:
                self._show_error("Failed to load image")
        except Exception as e:
            logger.exception("Image preview error: %s", e)
            self._show_error(str(e))

    def _show_binary_info(self, filename: str, size: int) -> None:
        """Show binary file info."""
        suffix = Path(filename).suffix.lower()

        # Determine file type description
        type_desc = self._get_binary_description(suffix)

        self._binary_page.set_title(type_desc)
        self._binary_page.set_description(
            f"Size: {self._format_size(size)}\n"
            f"This file type cannot be previewed as text or image."
        )
        self._stack.set_visible_child_name("binary")

    def _get_binary_description(self, suffix: str) -> str:
        """Get description for binary file type."""
        descriptions = {
            ".pdf": "PDF Document",
            ".doc": "Word Document",
            ".docx": "Word Document",
            ".xls": "Excel Spreadsheet",
            ".xlsx": "Excel Spreadsheet",
            ".ppt": "PowerPoint",
            ".pptx": "PowerPoint",
            ".zip": "ZIP Archive",
            ".tar": "TAR Archive",
            ".gz": "Gzipped File",
            ".7z": "7-Zip Archive",
            ".rar": "RAR Archive",
            ".exe": "Executable",
            ".dll": "Library",
            ".so": "Shared Object",
            ".dylib": "Dynamic Library",
            ".o": "Object File",
            ".pyc": "Python Bytecode",
            ".class": "Java Class",
            ".wasm": "WebAssembly",
            ".db": "Database",
            ".sqlite": "SQLite Database",
        }
        return descriptions.get(suffix, "Binary File")

    def _show_error(self, message: str) -> None:
        """Show error state."""
        self._error_page.set_description(message)
        self._stack.set_visible_child_name("error")

    def _show_large_warning(self, actual_size: int, max_size: int) -> None:
        """Show file too large warning."""
        self._large_page.set_description(
            f"File size: {self._format_size(actual_size)}\n"
            f"Maximum preview size: {self._format_size(max_size)}"
        )
        self._stack.set_visible_child_name("large")

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
