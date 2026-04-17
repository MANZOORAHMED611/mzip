"""Tests for format registry module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from zipextractor.core.formats import (
    FORMAT_REGISTRY,
    FormatCapability,
    FormatInfo,
    FormatRegistry,
    can_create,
    can_encrypt,
    can_extract,
    detect_format,
    get_all_extensions,
    get_format_info,
    get_format_registry,
    is_supported_archive,
)
from zipextractor.core.models import ArchiveFormat


class TestFormatCapability:
    """Tests for FormatCapability enum."""

    def test_capability_values(self) -> None:
        """Test that all expected capabilities exist."""
        assert FormatCapability.READ
        assert FormatCapability.WRITE
        assert FormatCapability.APPEND
        assert FormatCapability.DELETE
        assert FormatCapability.UPDATE
        assert FormatCapability.ENCRYPT
        assert FormatCapability.SPLIT


class TestFormatInfo:
    """Tests for FormatInfo dataclass."""

    def test_create_format_info(self) -> None:
        """Test creating FormatInfo."""
        info = FormatInfo(
            format=ArchiveFormat.ZIP,
            name="Test ZIP",
            extensions=[".zip"],
            mime_types=["application/zip"],
            magic_bytes=[b"PK\x03\x04"],
            capabilities={FormatCapability.READ, FormatCapability.WRITE},
        )
        assert info.format == ArchiveFormat.ZIP
        assert info.name == "Test ZIP"
        assert ".zip" in info.extensions
        assert FormatCapability.READ in info.capabilities


class TestFormatRegistry:
    """Tests for FormatRegistry class."""

    @pytest.fixture
    def registry(self) -> FormatRegistry:
        """Create a fresh registry."""
        return FormatRegistry()

    def test_get_format_info_zip(self, registry: FormatRegistry) -> None:
        """Test getting ZIP format info."""
        info = registry.get_format_info(ArchiveFormat.ZIP)
        assert info is not None
        assert info.name == "ZIP"
        assert ".zip" in info.extensions

    def test_get_format_info_tar(self, registry: FormatRegistry) -> None:
        """Test getting TAR format info."""
        info = registry.get_format_info(ArchiveFormat.TAR)
        assert info is not None
        assert info.name == "TAR"
        assert ".tar" in info.extensions

    def test_get_all_formats(self, registry: FormatRegistry) -> None:
        """Test getting all registered formats."""
        formats = registry.get_all_formats()
        assert len(formats) > 0
        assert any(f.format == ArchiveFormat.ZIP for f in formats)

    def test_get_writable_formats(self, registry: FormatRegistry) -> None:
        """Test getting writable formats."""
        formats = registry.get_writable_formats()
        assert len(formats) > 0
        for f in formats:
            assert FormatCapability.WRITE in f.capabilities

    def test_get_readable_formats(self, registry: FormatRegistry) -> None:
        """Test getting readable formats."""
        formats = registry.get_readable_formats()
        assert len(formats) > 0
        for f in formats:
            assert FormatCapability.READ in f.capabilities

    def test_detect_format_by_extension_zip(self, registry: FormatRegistry) -> None:
        """Test detecting ZIP by extension."""
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            f.write(b"dummy")
            path = Path(f.name)

        try:
            fmt = registry.detect_format(path)
            # May be detected by extension since magic bytes won't match
            assert fmt in (ArchiveFormat.ZIP, None)
        finally:
            path.unlink()

    def test_detect_format_by_magic_zip(self, registry: FormatRegistry) -> None:
        """Test detecting ZIP by magic bytes."""
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            f.write(b"PK\x03\x04" + b"\x00" * 100)
            path = Path(f.name)

        try:
            fmt = registry.detect_format(path)
            assert fmt == ArchiveFormat.ZIP
        finally:
            path.unlink()

    def test_detect_format_by_magic_gzip(self, registry: FormatRegistry) -> None:
        """Test detecting GZIP by magic bytes."""
        with tempfile.NamedTemporaryFile(suffix=".gz", delete=False) as f:
            f.write(b"\x1f\x8b" + b"\x00" * 100)
            path = Path(f.name)

        try:
            fmt = registry.detect_format(path)
            assert fmt == ArchiveFormat.GZ
        finally:
            path.unlink()

    def test_detect_format_by_magic_bzip2(self, registry: FormatRegistry) -> None:
        """Test detecting BZIP2 by magic bytes."""
        with tempfile.NamedTemporaryFile(suffix=".bz2", delete=False) as f:
            f.write(b"BZh" + b"\x00" * 100)
            path = Path(f.name)

        try:
            fmt = registry.detect_format(path)
            assert fmt == ArchiveFormat.BZ2
        finally:
            path.unlink()

    def test_detect_format_by_magic_7z(self, registry: FormatRegistry) -> None:
        """Test detecting 7z by magic bytes."""
        with tempfile.NamedTemporaryFile(suffix=".7z", delete=False) as f:
            f.write(b"7z\xbc\xaf'\x1c" + b"\x00" * 100)
            path = Path(f.name)

        try:
            fmt = registry.detect_format(path)
            assert fmt == ArchiveFormat.SEVEN_ZIP
        finally:
            path.unlink()

    def test_detect_format_by_magic_rar(self, registry: FormatRegistry) -> None:
        """Test detecting RAR by magic bytes."""
        with tempfile.NamedTemporaryFile(suffix=".rar", delete=False) as f:
            f.write(b"Rar!\x1a\x07\x00" + b"\x00" * 100)
            path = Path(f.name)

        try:
            fmt = registry.detect_format(path)
            assert fmt == ArchiveFormat.RAR
        finally:
            path.unlink()

    def test_detect_format_tar_gz(self, registry: FormatRegistry) -> None:
        """Test detecting TAR.GZ by extension and magic."""
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as f:
            f.write(b"\x1f\x8b" + b"\x00" * 100)
            path = Path(f.name)

        try:
            fmt = registry.detect_format(path)
            assert fmt == ArchiveFormat.TAR_GZ
        finally:
            path.unlink()

    def test_supports_capability(self, registry: FormatRegistry) -> None:
        """Test checking format capabilities."""
        assert registry.supports_capability(ArchiveFormat.ZIP, FormatCapability.READ)
        assert registry.supports_capability(ArchiveFormat.ZIP, FormatCapability.WRITE)
        assert registry.supports_capability(ArchiveFormat.ZIP, FormatCapability.ENCRYPT)

    def test_get_supported_extensions(self, registry: FormatRegistry) -> None:
        """Test getting supported extensions."""
        extensions = registry.get_supported_extensions()
        assert ".zip" in extensions
        assert ".tar" in extensions
        assert ".7z" in extensions

    def test_get_extension_for_format(self, registry: FormatRegistry) -> None:
        """Test getting extension for format."""
        ext = registry.get_extension_for_format(ArchiveFormat.ZIP)
        assert ext in (".zip", ".zipx")

    def test_get_mime_for_format(self, registry: FormatRegistry) -> None:
        """Test getting MIME type for format."""
        mime = registry.get_mime_for_format(ArchiveFormat.ZIP)
        assert "zip" in mime.lower()

    def test_register_custom_format(self, registry: FormatRegistry) -> None:
        """Test registering a custom format."""
        custom_info = FormatInfo(
            format=ArchiveFormat.UNKNOWN,
            name="Custom",
            extensions=[".custom"],
            mime_types=["application/x-custom"],
            magic_bytes=[b"CUSTOM"],
            capabilities={FormatCapability.READ},
        )
        registry.register(custom_info)

        info = registry.get_format_info(ArchiveFormat.UNKNOWN)
        assert info is not None
        assert info.name == "Custom"


class TestGlobalFunctions:
    """Tests for global convenience functions."""

    def test_get_format_registry(self) -> None:
        """Test get_format_registry returns singleton."""
        registry1 = get_format_registry()
        registry2 = get_format_registry()
        assert registry1 is registry2

    def test_detect_format_string_path(self) -> None:
        """Test detect_format with string path."""
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            f.write(b"PK\x03\x04" + b"\x00" * 100)
            path = f.name

        try:
            fmt = detect_format(path)
            assert fmt == ArchiveFormat.ZIP
        finally:
            Path(path).unlink()

    def test_get_format_info_function(self) -> None:
        """Test get_format_info function."""
        info = get_format_info(ArchiveFormat.ZIP)
        assert info is not None
        assert info.format == ArchiveFormat.ZIP

    def test_is_supported_archive_true(self) -> None:
        """Test is_supported_archive with valid archive."""
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            f.write(b"PK\x03\x04" + b"\x00" * 100)
            path = Path(f.name)

        try:
            assert is_supported_archive(path) is True
        finally:
            path.unlink()

    def test_is_supported_archive_false(self) -> None:
        """Test is_supported_archive with unsupported file."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Just text")
            path = Path(f.name)

        try:
            assert is_supported_archive(path) is False
        finally:
            path.unlink()

    def test_get_all_extensions(self) -> None:
        """Test get_all_extensions function."""
        extensions = get_all_extensions()
        assert len(extensions) > 0
        assert ".zip" in extensions

    def test_can_create(self) -> None:
        """Test can_create function."""
        assert can_create(ArchiveFormat.ZIP) is True
        assert can_create(ArchiveFormat.RAR) is False

    def test_can_extract(self) -> None:
        """Test can_extract function."""
        assert can_extract(ArchiveFormat.ZIP) is True
        assert can_extract(ArchiveFormat.RAR) is True

    def test_can_encrypt(self) -> None:
        """Test can_encrypt function."""
        assert can_encrypt(ArchiveFormat.ZIP) is True
        assert can_encrypt(ArchiveFormat.TAR) is False


class TestFormatRegistryData:
    """Tests for format registry data."""

    def test_zip_format_registered(self) -> None:
        """Test ZIP format is properly registered."""
        info = FORMAT_REGISTRY.get(ArchiveFormat.ZIP)
        assert info is not None
        assert info.name == "ZIP"
        assert FormatCapability.ENCRYPT in info.capabilities

    def test_seven_zip_format_registered(self) -> None:
        """Test 7z format is properly registered."""
        info = FORMAT_REGISTRY.get(ArchiveFormat.SEVEN_ZIP)
        assert info is not None
        assert info.name == "7-Zip"

    def test_rar_format_read_only(self) -> None:
        """Test RAR format is read-only."""
        info = FORMAT_REGISTRY.get(ArchiveFormat.RAR)
        assert info is not None
        assert FormatCapability.READ in info.capabilities
        assert FormatCapability.WRITE not in info.capabilities

    def test_tar_variants_registered(self) -> None:
        """Test all TAR variants are registered."""
        for fmt in (
            ArchiveFormat.TAR,
            ArchiveFormat.TAR_GZ,
            ArchiveFormat.TAR_BZ2,
            ArchiveFormat.TAR_XZ,
            ArchiveFormat.TAR_ZSTD,
        ):
            info = FORMAT_REGISTRY.get(fmt)
            assert info is not None, f"Missing format: {fmt}"
