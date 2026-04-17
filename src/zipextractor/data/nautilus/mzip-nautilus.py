#!/usr/bin/env python3
"""Nautilus extension for MZip archive manager.

This extension adds context menu items for archive operations in
GNOME Files (Nautilus).

Copyright 2026 Green Olive Tech
Licensed under GPL-3.0-or-later

Installation:
    Copy this file to ~/.local/share/nautilus-python/extensions/
    or /usr/share/nautilus-python/extensions/
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlparse

from gi.repository import GObject, Nautilus

if TYPE_CHECKING:
    from collections.abc import Sequence

# Archive extensions that MZip can handle
ARCHIVE_EXTENSIONS = {
    ".zip",
    ".7z",
    ".rar",
    ".tar",
    ".tar.gz",
    ".tgz",
    ".tar.bz2",
    ".tbz2",
    ".tbz",
    ".tar.xz",
    ".txz",
    ".gz",
    ".bz2",
    ".xz",
}

# Extensions that can be compressed
COMPRESSIBLE_EXTENSIONS = {
    ".txt",
    ".doc",
    ".docx",
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".mp3",
    ".mp4",
    ".py",
    ".js",
    ".html",
    ".css",
    ".json",
    ".xml",
    ".csv",
}


def get_file_path(file_info: Nautilus.FileInfo) -> Path | None:
    """Extract file path from Nautilus FileInfo."""
    uri = file_info.get_uri()
    if not uri:
        return None

    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None

    return Path(unquote(parsed.path))


def is_archive(file_info: Nautilus.FileInfo) -> bool:
    """Check if file is a supported archive."""
    path = get_file_path(file_info)
    if not path:
        return False

    # Check for compound extensions first (e.g., .tar.gz)
    name_lower = path.name.lower()
    return any(name_lower.endswith(ext) for ext in ARCHIVE_EXTENSIONS)


def is_directory(file_info: Nautilus.FileInfo) -> bool:
    """Check if file info represents a directory."""
    return bool(file_info.is_directory())


class MZipMenuProvider(GObject.GObject, Nautilus.MenuProvider):
    """Nautilus menu provider for MZip operations."""

    def __init__(self) -> None:
        """Initialize the menu provider."""
        super().__init__()

    def get_file_items(
        self,
        files: Sequence[Nautilus.FileInfo],
    ) -> list[Nautilus.MenuItem]:
        """Get menu items for selected files.

        Args:
            files: Selected files in Nautilus.

        Returns:
            List of menu items.
        """
        if not files:
            return []

        items: list[Nautilus.MenuItem] = []

        # Check if all selected items are archives
        all_archives = all(is_archive(f) for f in files)

        # Check if selection contains directories or files (for compression)
        has_files = any(not is_directory(f) or is_directory(f) for f in files)

        if all_archives:
            # Add archive-specific menu items
            items.extend(self._get_archive_menu_items(files))
        elif has_files:
            # Add compression menu items
            items.extend(self._get_compression_menu_items(files))

        return items

    def _get_archive_menu_items(
        self,
        files: Sequence[Nautilus.FileInfo],
    ) -> list[Nautilus.MenuItem]:
        """Get menu items for archive files."""
        items: list[Nautilus.MenuItem] = []

        # Extract Here
        extract_here = Nautilus.MenuItem(
            name="MZip::ExtractHere",
            label="Extract Here",
            tip="Extract archive contents to current directory",
            icon="extract-archive",
        )
        extract_here.connect("activate", self._on_extract_here, files)
        items.append(extract_here)

        # Extract To...
        extract_to = Nautilus.MenuItem(
            name="MZip::ExtractTo",
            label="Extract To...",
            tip="Extract archive contents to a chosen directory",
            icon="extract-archive",
        )
        extract_to.connect("activate", self._on_extract_to, files)
        items.append(extract_to)

        # Open with MZip
        open_mzip = Nautilus.MenuItem(
            name="MZip::Open",
            label="Open with MZip",
            tip="Open archive in MZip for browsing",
            icon="mzip",
        )
        open_mzip.connect("activate", self._on_open_mzip, files)
        items.append(open_mzip)

        # Test Archive (single file only)
        if len(files) == 1:
            test_archive = Nautilus.MenuItem(
                name="MZip::Test",
                label="Test Archive Integrity",
                tip="Verify archive is not corrupted",
                icon="dialog-information",
            )
            test_archive.connect("activate", self._on_test_archive, files)
            items.append(test_archive)

        return items

    def _get_compression_menu_items(
        self,
        files: Sequence[Nautilus.FileInfo],
    ) -> list[Nautilus.MenuItem]:
        """Get menu items for compressing files."""
        items: list[Nautilus.MenuItem] = []

        # Compress to ZIP
        compress_zip = Nautilus.MenuItem(
            name="MZip::CompressZip",
            label="Compress to ZIP...",
            tip="Create a ZIP archive from selected files",
            icon="package-x-generic",
        )
        compress_zip.connect("activate", self._on_compress_zip, files)
        items.append(compress_zip)

        # Compress to 7z
        compress_7z = Nautilus.MenuItem(
            name="MZip::Compress7z",
            label="Compress to 7z...",
            tip="Create a 7z archive from selected files",
            icon="package-x-generic",
        )
        compress_7z.connect("activate", self._on_compress_7z, files)
        items.append(compress_7z)

        # Compress submenu for more options
        compress_menu = Nautilus.MenuItem(
            name="MZip::CompressMenu",
            label="Compress with MZip",
            tip="More compression options",
            icon="mzip",
        )

        submenu = Nautilus.Menu()

        # TAR.GZ
        compress_tgz = Nautilus.MenuItem(
            name="MZip::CompressTgz",
            label="TAR.GZ Archive",
            tip="Create a gzip-compressed TAR archive",
        )
        compress_tgz.connect("activate", self._on_compress_tgz, files)
        submenu.append_item(compress_tgz)

        # TAR.XZ
        compress_txz = Nautilus.MenuItem(
            name="MZip::CompressTxz",
            label="TAR.XZ Archive",
            tip="Create an xz-compressed TAR archive",
        )
        compress_txz.connect("activate", self._on_compress_txz, files)
        submenu.append_item(compress_txz)

        compress_menu.set_submenu(submenu)
        items.append(compress_menu)

        return items

    def _on_extract_here(
        self,
        _menu: Nautilus.MenuItem,
        files: Sequence[Nautilus.FileInfo],
    ) -> None:
        """Handle 'Extract Here' action."""
        for file_info in files:
            path = get_file_path(file_info)
            if path:
                subprocess.Popen(
                    ["mzip", "extract", str(path), "-o", str(path.parent)],
                    start_new_session=True,
                )

    def _on_extract_to(
        self,
        _menu: Nautilus.MenuItem,
        files: Sequence[Nautilus.FileInfo],
    ) -> None:
        """Handle 'Extract To...' action."""
        paths = [str(get_file_path(f)) for f in files if get_file_path(f)]
        if paths:
            subprocess.Popen(
                ["mzip-gui", "--extract", *paths],
                start_new_session=True,
            )

    def _on_open_mzip(
        self,
        _menu: Nautilus.MenuItem,
        files: Sequence[Nautilus.FileInfo],
    ) -> None:
        """Handle 'Open with MZip' action."""
        paths = [str(get_file_path(f)) for f in files if get_file_path(f)]
        if paths:
            subprocess.Popen(
                ["mzip-gui", *paths],
                start_new_session=True,
            )

    def _on_test_archive(
        self,
        _menu: Nautilus.MenuItem,
        files: Sequence[Nautilus.FileInfo],
    ) -> None:
        """Handle 'Test Archive' action."""
        for file_info in files:
            path = get_file_path(file_info)
            if path:
                # Run in terminal to show output
                subprocess.Popen(
                    [
                        "gnome-terminal",
                        "--",
                        "bash",
                        "-c",
                        f'mzip test "{path}"; read -p "Press Enter to close..."',
                    ],
                    start_new_session=True,
                )

    def _on_compress_zip(
        self,
        _menu: Nautilus.MenuItem,
        files: Sequence[Nautilus.FileInfo],
    ) -> None:
        """Handle 'Compress to ZIP' action."""
        self._compress_files(files, "zip")

    def _on_compress_7z(
        self,
        _menu: Nautilus.MenuItem,
        files: Sequence[Nautilus.FileInfo],
    ) -> None:
        """Handle 'Compress to 7z' action."""
        self._compress_files(files, "7z")

    def _on_compress_tgz(
        self,
        _menu: Nautilus.MenuItem,
        files: Sequence[Nautilus.FileInfo],
    ) -> None:
        """Handle 'Compress to TAR.GZ' action."""
        self._compress_files(files, "tar.gz")

    def _on_compress_txz(
        self,
        _menu: Nautilus.MenuItem,
        files: Sequence[Nautilus.FileInfo],
    ) -> None:
        """Handle 'Compress to TAR.XZ' action."""
        self._compress_files(files, "tar.xz")

    def _compress_files(
        self,
        files: Sequence[Nautilus.FileInfo],
        format_ext: str,
    ) -> None:
        """Compress files to the specified format."""
        valid_paths: list[Path] = [
            p for f in files if (p := get_file_path(f)) is not None
        ]
        if not valid_paths:
            return

        # Determine output name
        first_path = valid_paths[0]
        if len(valid_paths) == 1:
            output_name = f"{first_path.stem}.{format_ext}"
        else:
            output_name = f"archive.{format_ext}"

        output_path = first_path.parent / output_name

        # Launch GUI for compression options
        path_strs = [str(p) for p in valid_paths]
        subprocess.Popen(
            ["mzip-gui", "--create", str(output_path), *path_strs],
            start_new_session=True,
        )


# Register the extension
def get_extension_types() -> list[type]:
    """Return extension types provided by this module."""
    return [MZipMenuProvider]
