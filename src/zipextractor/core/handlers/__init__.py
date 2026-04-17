"""Archive format handlers.

This package contains handlers for different archive formats.
"""

from zipextractor.core.handlers.base_handler import (
    ArchiveHandler,
    HandlerRegistry,
    get_handler,
    get_handler_registry,
    register_handler,
)
from zipextractor.core.handlers.rar_handler import RarHandler
from zipextractor.core.handlers.seven_zip_handler import SevenZipHandler
from zipextractor.core.handlers.single_file_handler import (
    Bzip2Handler,
    GzipHandler,
    XzHandler,
    ZstdHandler,
)
from zipextractor.core.handlers.tar_handler import TarHandler
from zipextractor.core.handlers.zip_handler import ZipHandler
from zipextractor.core.models import ArchiveFormat

# Register all handlers
_registry = get_handler_registry()
_registry.register(ArchiveFormat.ZIP, ZipHandler)
_registry.register(ArchiveFormat.SEVEN_ZIP, SevenZipHandler)
_registry.register(ArchiveFormat.RAR, RarHandler)
_registry.register(ArchiveFormat.TAR, TarHandler)
_registry.register(ArchiveFormat.TAR_GZ, TarHandler)
_registry.register(ArchiveFormat.TAR_BZ2, TarHandler)
_registry.register(ArchiveFormat.TAR_XZ, TarHandler)
_registry.register(ArchiveFormat.TAR_ZSTD, TarHandler)
_registry.register(ArchiveFormat.GZ, GzipHandler)
_registry.register(ArchiveFormat.BZ2, Bzip2Handler)
_registry.register(ArchiveFormat.XZ, XzHandler)
_registry.register(ArchiveFormat.ZSTD, ZstdHandler)
# ZIP-based formats use ZipHandler
_registry.register(ArchiveFormat.JAR, ZipHandler)
_registry.register(ArchiveFormat.WAR, ZipHandler)
_registry.register(ArchiveFormat.APK, ZipHandler)
_registry.register(ArchiveFormat.EPUB, ZipHandler)
_registry.register(ArchiveFormat.DOCX, ZipHandler)
_registry.register(ArchiveFormat.XLSX, ZipHandler)

__all__ = [
    "ArchiveHandler",
    "Bzip2Handler",
    "GzipHandler",
    "HandlerRegistry",
    "RarHandler",
    "SevenZipHandler",
    "TarHandler",
    "XzHandler",
    "ZipHandler",
    "ZstdHandler",
    "get_handler",
    "get_handler_registry",
    "register_handler",
]
