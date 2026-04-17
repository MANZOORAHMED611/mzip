"""Archive format registry and detection.

This module provides format detection based on file signatures (magic bytes)
and extension mapping, supporting 25+ archive formats.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from zipextractor.core.models import ArchiveFormat
from zipextractor.utils.logging import get_logger

logger = get_logger(__name__)


class FormatCapability(Enum):
    """Format capabilities."""

    READ = auto()  # Can read/extract
    WRITE = auto()  # Can create new archives
    APPEND = auto()  # Can add files to existing archive
    DELETE = auto()  # Can delete files from archive
    UPDATE = auto()  # Can update files in archive
    ENCRYPT = auto()  # Supports encryption
    SPLIT = auto()  # Supports split archives


@dataclass
class FormatInfo:
    """Information about an archive format.

    Attributes:
        format: Archive format enum value.
        name: Human-readable format name.
        extensions: List of file extensions (including dot).
        mime_types: List of MIME types.
        magic_bytes: List of magic byte signatures for detection.
        capabilities: Set of supported capabilities.
        description: Format description.
        handler_class: Name of handler class for this format.
    """

    format: ArchiveFormat
    name: str
    extensions: list[str]
    mime_types: list[str]
    magic_bytes: list[bytes]
    capabilities: set[FormatCapability]
    description: str = ""
    handler_class: str = ""
    max_file_size: int = 0  # 0 means unlimited
    compression_methods: list[str] = field(default_factory=list)


# Format registry with all supported formats
FORMAT_REGISTRY: dict[ArchiveFormat, FormatInfo] = {
    ArchiveFormat.ZIP: FormatInfo(
        format=ArchiveFormat.ZIP,
        name="ZIP",
        extensions=[".zip", ".zipx"],
        mime_types=["application/zip", "application/x-zip-compressed"],
        magic_bytes=[b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"],
        capabilities={
            FormatCapability.READ,
            FormatCapability.WRITE,
            FormatCapability.APPEND,
            FormatCapability.DELETE,
            FormatCapability.UPDATE,
            FormatCapability.ENCRYPT,
            FormatCapability.SPLIT,
        },
        description="Standard ZIP archive format",
        handler_class="ZipHandler",
        compression_methods=["store", "deflate", "bzip2", "lzma"],
    ),
    ArchiveFormat.SEVEN_ZIP: FormatInfo(
        format=ArchiveFormat.SEVEN_ZIP,
        name="7-Zip",
        extensions=[".7z"],
        mime_types=["application/x-7z-compressed"],
        magic_bytes=[b"7z\xbc\xaf'\x1c"],
        capabilities={
            FormatCapability.READ,
            FormatCapability.WRITE,
            FormatCapability.ENCRYPT,
        },
        description="7-Zip archive with LZMA2 compression",
        handler_class="SevenZipHandler",
        compression_methods=["lzma", "lzma2", "bzip2", "ppmd", "copy"],
    ),
    ArchiveFormat.RAR: FormatInfo(
        format=ArchiveFormat.RAR,
        name="RAR",
        extensions=[".rar"],
        mime_types=["application/x-rar-compressed", "application/vnd.rar"],
        magic_bytes=[b"Rar!\x1a\x07\x00", b"Rar!\x1a\x07\x01\x00"],
        capabilities={FormatCapability.READ},
        description="RAR archive (read-only)",
        handler_class="RarHandler",
        compression_methods=["rar"],
    ),
    ArchiveFormat.TAR: FormatInfo(
        format=ArchiveFormat.TAR,
        name="TAR",
        extensions=[".tar"],
        mime_types=["application/x-tar"],
        magic_bytes=[b"ustar"],  # At offset 257
        capabilities={
            FormatCapability.READ,
            FormatCapability.WRITE,
            FormatCapability.APPEND,
        },
        description="UNIX tape archive",
        handler_class="TarHandler",
        compression_methods=["none"],
    ),
    ArchiveFormat.TAR_GZ: FormatInfo(
        format=ArchiveFormat.TAR_GZ,
        name="TAR.GZ",
        extensions=[".tar.gz", ".tgz"],
        mime_types=["application/gzip", "application/x-gzip"],
        magic_bytes=[b"\x1f\x8b"],
        capabilities={
            FormatCapability.READ,
            FormatCapability.WRITE,
        },
        description="Gzip compressed TAR archive",
        handler_class="TarHandler",
        compression_methods=["gzip"],
    ),
    ArchiveFormat.TAR_BZ2: FormatInfo(
        format=ArchiveFormat.TAR_BZ2,
        name="TAR.BZ2",
        extensions=[".tar.bz2", ".tbz2", ".tbz"],
        mime_types=["application/x-bzip2"],
        magic_bytes=[b"BZ", b"BZh"],
        capabilities={
            FormatCapability.READ,
            FormatCapability.WRITE,
        },
        description="Bzip2 compressed TAR archive",
        handler_class="TarHandler",
        compression_methods=["bzip2"],
    ),
    ArchiveFormat.TAR_XZ: FormatInfo(
        format=ArchiveFormat.TAR_XZ,
        name="TAR.XZ",
        extensions=[".tar.xz", ".txz"],
        mime_types=["application/x-xz"],
        magic_bytes=[b"\xfd7zXZ\x00"],
        capabilities={
            FormatCapability.READ,
            FormatCapability.WRITE,
        },
        description="XZ/LZMA compressed TAR archive",
        handler_class="TarHandler",
        compression_methods=["xz", "lzma"],
    ),
    ArchiveFormat.TAR_ZSTD: FormatInfo(
        format=ArchiveFormat.TAR_ZSTD,
        name="TAR.ZSTD",
        extensions=[".tar.zst", ".tzst"],
        mime_types=["application/zstd"],
        magic_bytes=[b"\x28\xb5\x2f\xfd"],
        capabilities={
            FormatCapability.READ,
            FormatCapability.WRITE,
        },
        description="Zstandard compressed TAR archive",
        handler_class="TarHandler",
        compression_methods=["zstd"],
    ),
    ArchiveFormat.GZ: FormatInfo(
        format=ArchiveFormat.GZ,
        name="GZIP",
        extensions=[".gz", ".gzip"],
        mime_types=["application/gzip", "application/x-gzip"],
        magic_bytes=[b"\x1f\x8b"],
        capabilities={
            FormatCapability.READ,
            FormatCapability.WRITE,
        },
        description="Gzip compressed single file",
        handler_class="SingleFileHandler",
        compression_methods=["gzip"],
    ),
    ArchiveFormat.BZ2: FormatInfo(
        format=ArchiveFormat.BZ2,
        name="BZIP2",
        extensions=[".bz2", ".bzip2"],
        mime_types=["application/x-bzip2"],
        magic_bytes=[b"BZh"],
        capabilities={
            FormatCapability.READ,
            FormatCapability.WRITE,
        },
        description="Bzip2 compressed single file",
        handler_class="SingleFileHandler",
        compression_methods=["bzip2"],
    ),
    ArchiveFormat.XZ: FormatInfo(
        format=ArchiveFormat.XZ,
        name="XZ",
        extensions=[".xz", ".lzma"],
        mime_types=["application/x-xz", "application/x-lzma"],
        magic_bytes=[b"\xfd7zXZ\x00"],
        capabilities={
            FormatCapability.READ,
            FormatCapability.WRITE,
        },
        description="XZ/LZMA compressed single file",
        handler_class="SingleFileHandler",
        compression_methods=["xz", "lzma"],
    ),
    ArchiveFormat.ZSTD: FormatInfo(
        format=ArchiveFormat.ZSTD,
        name="ZSTD",
        extensions=[".zst", ".zstd"],
        mime_types=["application/zstd"],
        magic_bytes=[b"\x28\xb5\x2f\xfd"],
        capabilities={
            FormatCapability.READ,
            FormatCapability.WRITE,
        },
        description="Zstandard compressed single file",
        handler_class="SingleFileHandler",
        compression_methods=["zstd"],
    ),
    ArchiveFormat.JAR: FormatInfo(
        format=ArchiveFormat.JAR,
        name="JAR",
        extensions=[".jar"],
        mime_types=["application/java-archive"],
        magic_bytes=[b"PK\x03\x04"],
        capabilities={
            FormatCapability.READ,
            FormatCapability.WRITE,
            FormatCapability.APPEND,
        },
        description="Java Archive (ZIP format)",
        handler_class="ZipHandler",
        compression_methods=["store", "deflate"],
    ),
    ArchiveFormat.WAR: FormatInfo(
        format=ArchiveFormat.WAR,
        name="WAR",
        extensions=[".war"],
        mime_types=["application/java-archive"],
        magic_bytes=[b"PK\x03\x04"],
        capabilities={
            FormatCapability.READ,
            FormatCapability.WRITE,
        },
        description="Web Application Archive (ZIP format)",
        handler_class="ZipHandler",
        compression_methods=["store", "deflate"],
    ),
    ArchiveFormat.APK: FormatInfo(
        format=ArchiveFormat.APK,
        name="APK",
        extensions=[".apk"],
        mime_types=["application/vnd.android.package-archive"],
        magic_bytes=[b"PK\x03\x04"],
        capabilities={
            FormatCapability.READ,
        },
        description="Android Package (ZIP format)",
        handler_class="ZipHandler",
        compression_methods=["store", "deflate"],
    ),
    ArchiveFormat.EPUB: FormatInfo(
        format=ArchiveFormat.EPUB,
        name="EPUB",
        extensions=[".epub"],
        mime_types=["application/epub+zip"],
        magic_bytes=[b"PK\x03\x04"],
        capabilities={
            FormatCapability.READ,
        },
        description="Electronic Publication (ZIP format)",
        handler_class="ZipHandler",
        compression_methods=["store", "deflate"],
    ),
    ArchiveFormat.DOCX: FormatInfo(
        format=ArchiveFormat.DOCX,
        name="DOCX",
        extensions=[".docx"],
        mime_types=[
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ],
        magic_bytes=[b"PK\x03\x04"],
        capabilities={FormatCapability.READ},
        description="Microsoft Word Document (ZIP format)",
        handler_class="ZipHandler",
        compression_methods=["store", "deflate"],
    ),
    ArchiveFormat.XLSX: FormatInfo(
        format=ArchiveFormat.XLSX,
        name="XLSX",
        extensions=[".xlsx"],
        mime_types=[
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ],
        magic_bytes=[b"PK\x03\x04"],
        capabilities={FormatCapability.READ},
        description="Microsoft Excel Spreadsheet (ZIP format)",
        handler_class="ZipHandler",
        compression_methods=["store", "deflate"],
    ),
    ArchiveFormat.CAB: FormatInfo(
        format=ArchiveFormat.CAB,
        name="CAB",
        extensions=[".cab"],
        mime_types=["application/vnd.ms-cab-compressed"],
        magic_bytes=[b"MSCF"],
        capabilities={FormatCapability.READ},
        description="Microsoft Cabinet archive",
        handler_class="CabHandler",
        compression_methods=["mszip", "lzx", "quantum"],
    ),
    ArchiveFormat.ISO: FormatInfo(
        format=ArchiveFormat.ISO,
        name="ISO",
        extensions=[".iso"],
        mime_types=["application/x-iso9660-image"],
        magic_bytes=[],  # Complex detection required
        capabilities={FormatCapability.READ},
        description="ISO 9660 disk image",
        handler_class="IsoHandler",
        compression_methods=["none"],
    ),
    ArchiveFormat.DEB: FormatInfo(
        format=ArchiveFormat.DEB,
        name="DEB",
        extensions=[".deb"],
        mime_types=["application/vnd.debian.binary-package"],
        magic_bytes=[b"!<arch>"],
        capabilities={FormatCapability.READ},
        description="Debian package",
        handler_class="DebHandler",
        compression_methods=["gzip", "xz", "zstd"],
    ),
}


class FormatRegistry:
    """Registry for archive format handlers.

    Provides format detection from file content and extensions,
    and manages format handler instances.
    """

    def __init__(self) -> None:
        """Initialize format registry."""
        self._formats = FORMAT_REGISTRY.copy()
        self._extension_map: dict[str, ArchiveFormat] = {}
        self._mime_map: dict[str, ArchiveFormat] = {}
        self._build_maps()

    def _build_maps(self) -> None:
        """Build extension and MIME type lookup maps."""
        for fmt, info in self._formats.items():
            for ext in info.extensions:
                self._extension_map[ext.lower()] = fmt
            for mime in info.mime_types:
                self._mime_map[mime.lower()] = fmt

    def register(self, info: FormatInfo) -> None:
        """Register a new format or update existing.

        Args:
            info: Format information to register.
        """
        self._formats[info.format] = info
        for ext in info.extensions:
            self._extension_map[ext.lower()] = info.format
        for mime in info.mime_types:
            self._mime_map[mime.lower()] = info.format
        logger.debug("Registered format: %s", info.name)

    def get_format_info(self, fmt: ArchiveFormat) -> FormatInfo | None:
        """Get information about a format.

        Args:
            fmt: Archive format.

        Returns:
            FormatInfo or None if not found.
        """
        return self._formats.get(fmt)

    def get_all_formats(self) -> list[FormatInfo]:
        """Get all registered formats.

        Returns:
            List of all format information.
        """
        return list(self._formats.values())

    def get_writable_formats(self) -> list[FormatInfo]:
        """Get formats that support writing.

        Returns:
            List of writable formats.
        """
        return [
            info
            for info in self._formats.values()
            if FormatCapability.WRITE in info.capabilities
        ]

    def get_readable_formats(self) -> list[FormatInfo]:
        """Get formats that support reading.

        Returns:
            List of readable formats.
        """
        return [
            info
            for info in self._formats.values()
            if FormatCapability.READ in info.capabilities
        ]

    def detect_format(self, path: Path) -> ArchiveFormat | None:
        """Detect archive format from file.

        Uses magic bytes first, falls back to extension.

        Args:
            path: Path to the file.

        Returns:
            Detected format or None.
        """
        # Try magic bytes first
        fmt = self._detect_by_magic(path)
        if fmt:
            return fmt

        # Fall back to extension
        return self._detect_by_extension(path)

    def _detect_by_magic(self, path: Path) -> ArchiveFormat | None:  # noqa: PLR0911, PLR0912
        """Detect format by magic bytes.

        Args:
            path: Path to the file.

        Returns:
            Detected format or None.
        """
        try:
            with path.open("rb") as f:
                header = f.read(512)

            # Check TAR format (magic at offset 257)
            if len(header) > 262:
                tar_magic = header[257:262]
                if tar_magic == b"ustar":
                    return ArchiveFormat.TAR

            # Check other formats
            for fmt, info in self._formats.items():
                for magic in info.magic_bytes:
                    if header.startswith(magic):
                        # Distinguish between similar formats
                        if magic == b"PK\x03\x04":
                            # ZIP-based format - check extension for specifics
                            ext_fmt = self._detect_by_extension(path)
                            if ext_fmt in (
                                ArchiveFormat.JAR,
                                ArchiveFormat.WAR,
                                ArchiveFormat.APK,
                                ArchiveFormat.EPUB,
                                ArchiveFormat.DOCX,
                                ArchiveFormat.XLSX,
                            ):
                                return ext_fmt
                            return ArchiveFormat.ZIP
                        if magic in (b"\x1f\x8b",):
                            # Could be .gz or .tar.gz
                            ext_fmt = self._detect_by_extension(path)
                            if ext_fmt == ArchiveFormat.TAR_GZ:
                                return ArchiveFormat.TAR_GZ
                            return ArchiveFormat.GZ
                        if magic in (b"BZh", b"BZ"):
                            ext_fmt = self._detect_by_extension(path)
                            if ext_fmt == ArchiveFormat.TAR_BZ2:
                                return ArchiveFormat.TAR_BZ2
                            return ArchiveFormat.BZ2
                        if magic == b"\xfd7zXZ\x00":
                            ext_fmt = self._detect_by_extension(path)
                            if ext_fmt == ArchiveFormat.TAR_XZ:
                                return ArchiveFormat.TAR_XZ
                            return ArchiveFormat.XZ
                        if magic == b"\x28\xb5\x2f\xfd":
                            ext_fmt = self._detect_by_extension(path)
                            if ext_fmt == ArchiveFormat.TAR_ZSTD:
                                return ArchiveFormat.TAR_ZSTD
                            return ArchiveFormat.ZSTD
                        return fmt

        except OSError as e:
            logger.warning("Failed to read file for format detection: %s", e)

        return None

    def _detect_by_extension(self, path: Path) -> ArchiveFormat | None:
        """Detect format by file extension.

        Args:
            path: Path to the file.

        Returns:
            Detected format or None.
        """
        name = path.name.lower()

        # Check compound extensions first (.tar.gz, .tar.bz2, etc.)
        for ext, fmt in self._extension_map.items():
            if name.endswith(ext):
                return fmt

        # Check simple extension
        suffix = path.suffix.lower()
        return self._extension_map.get(suffix)

    def detect_format_from_mime(self, mime_type: str) -> ArchiveFormat | None:
        """Detect format from MIME type.

        Args:
            mime_type: MIME type string.

        Returns:
            Detected format or None.
        """
        return self._mime_map.get(mime_type.lower())

    def get_extension_for_format(self, fmt: ArchiveFormat) -> str:
        """Get primary extension for a format.

        Args:
            fmt: Archive format.

        Returns:
            Primary extension including dot.
        """
        info = self._formats.get(fmt)
        if info and info.extensions:
            return info.extensions[0]
        return ""

    def get_mime_for_format(self, fmt: ArchiveFormat) -> str:
        """Get primary MIME type for a format.

        Args:
            fmt: Archive format.

        Returns:
            Primary MIME type.
        """
        info = self._formats.get(fmt)
        if info and info.mime_types:
            return info.mime_types[0]
        return "application/octet-stream"

    def supports_capability(
        self, fmt: ArchiveFormat, capability: FormatCapability
    ) -> bool:
        """Check if format supports a capability.

        Args:
            fmt: Archive format.
            capability: Capability to check.

        Returns:
            True if capability is supported.
        """
        info = self._formats.get(fmt)
        if info:
            return capability in info.capabilities
        return False

    def get_supported_extensions(self) -> list[str]:
        """Get all supported file extensions.

        Returns:
            List of extensions including dots.
        """
        return list(self._extension_map.keys())

    def get_file_filter_patterns(self) -> list[str]:
        """Get glob patterns for file filters.

        Returns:
            List of patterns like "*.zip".
        """
        return [f"*{ext}" for ext in self._extension_map]


# Global registry instance
_registry = FormatRegistry()


def get_format_registry() -> FormatRegistry:
    """Get the global format registry.

    Returns:
        FormatRegistry singleton.
    """
    return _registry


def detect_format(path: Path | str) -> ArchiveFormat | None:
    """Detect archive format from file path.

    Args:
        path: Path to the archive file.

    Returns:
        Detected format or None.
    """
    if isinstance(path, str):
        path = Path(path)
    return _registry.detect_format(path)


def get_format_info(fmt: ArchiveFormat) -> FormatInfo | None:
    """Get information about a format.

    Args:
        fmt: Archive format.

    Returns:
        FormatInfo or None.
    """
    return _registry.get_format_info(fmt)


def is_supported_archive(path: Path | str) -> bool:
    """Check if file is a supported archive.

    Args:
        path: Path to check.

    Returns:
        True if file is a supported archive.
    """
    return detect_format(path) is not None


def get_all_extensions() -> list[str]:
    """Get all supported archive extensions.

    Returns:
        List of extensions.
    """
    return _registry.get_supported_extensions()


def can_create(fmt: ArchiveFormat) -> bool:
    """Check if format supports creation.

    Args:
        fmt: Archive format.

    Returns:
        True if format can be created.
    """
    return _registry.supports_capability(fmt, FormatCapability.WRITE)


def can_extract(fmt: ArchiveFormat) -> bool:
    """Check if format supports extraction.

    Args:
        fmt: Archive format.

    Returns:
        True if format can be extracted.
    """
    return _registry.supports_capability(fmt, FormatCapability.READ)


def can_encrypt(fmt: ArchiveFormat) -> bool:
    """Check if format supports encryption.

    Args:
        fmt: Archive format.

    Returns:
        True if format supports encryption.
    """
    return _registry.supports_capability(fmt, FormatCapability.ENCRYPT)
