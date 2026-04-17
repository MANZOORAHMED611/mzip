"""Archive repair and recovery functionality.

This module provides tools to repair corrupted archives and recover
readable files from damaged archives.
"""

from __future__ import annotations

import shutil
import struct
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import BinaryIO

from zipextractor.core.formats import detect_format
from zipextractor.core.models import ArchiveFormat
from zipextractor.utils.logging import get_logger

logger = get_logger(__name__)


class RepairStatus(Enum):
    """Status of repair operation."""

    SUCCESS = auto()  # Fully repaired
    PARTIAL = auto()  # Some files recovered
    FAILED = auto()  # Could not repair
    UNNECESSARY = auto()  # Archive was not corrupted


class DamageType(Enum):
    """Type of archive damage."""

    NONE = auto()
    HEADER = auto()  # Corrupt header
    CENTRAL_DIRECTORY = auto()  # Corrupt central directory (ZIP)
    CRC_MISMATCH = auto()  # Data corruption
    TRUNCATED = auto()  # File is incomplete
    UNKNOWN = auto()


@dataclass
class RecoveredFile:
    """Information about a recovered file.

    Attributes:
        name: Original filename.
        size: Recovered size in bytes.
        status: Recovery status.
        error: Error message if failed.
    """

    name: str
    size: int = 0
    status: RepairStatus = RepairStatus.SUCCESS
    error: str | None = None


@dataclass
class RepairResult:
    """Result of a repair operation.

    Attributes:
        status: Overall repair status.
        output_path: Path to repaired archive.
        damage_type: Type of damage detected.
        recovered_files: List of recovered files.
        lost_files: List of unrecoverable files.
        original_file_count: Number of files in original.
        recovered_file_count: Number of files recovered.
        error_message: Error message if repair failed.
    """

    status: RepairStatus
    output_path: Path | None = None
    damage_type: DamageType = DamageType.NONE
    recovered_files: list[RecoveredFile] = field(default_factory=list)
    lost_files: list[str] = field(default_factory=list)
    original_file_count: int = 0
    recovered_file_count: int = 0
    error_message: str | None = None

    @property
    def recovery_rate(self) -> float:
        """Get percentage of files recovered."""
        if self.original_file_count == 0:
            return 100.0
        return (self.recovered_file_count / self.original_file_count) * 100.0


class ZipRepairer:
    """Repair corrupted ZIP archives.

    Attempts to recover files from damaged ZIP archives by:
    1. Scanning for local file headers
    2. Rebuilding central directory
    3. Extracting readable files
    """

    # ZIP signature constants
    LOCAL_FILE_HEADER_SIG = b"PK\x03\x04"
    CENTRAL_DIR_SIG = b"PK\x01\x02"
    END_CENTRAL_DIR_SIG = b"PK\x05\x06"

    def __init__(self) -> None:
        """Initialize repairer."""
        self._cancelled = False

    def cancel(self) -> None:
        """Cancel ongoing repair."""
        self._cancelled = True

    def diagnose(self, archive_path: Path) -> DamageType:
        """Diagnose the type of damage in a ZIP file.

        Args:
            archive_path: Path to the ZIP file.

        Returns:
            Type of damage detected.
        """
        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                # Try to read central directory
                _ = zf.namelist()
                # Try testzip
                bad_file = zf.testzip()
                if bad_file:
                    return DamageType.CRC_MISMATCH
                return DamageType.NONE
        except zipfile.BadZipFile as e:
            error_str = str(e).lower()
            if "truncated" in error_str:
                return DamageType.TRUNCATED
            if "central directory" in error_str:
                return DamageType.CENTRAL_DIRECTORY
            return DamageType.HEADER
        except Exception:
            return DamageType.UNKNOWN

    def repair(
        self,
        archive_path: Path,
        output_path: Path | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> RepairResult:
        """Attempt to repair a corrupted ZIP archive.

        Args:
            archive_path: Path to the corrupted archive.
            output_path: Path for repaired archive (default: adds .repaired suffix).
            progress_callback: Optional callback(filename, current, total).

        Returns:
            RepairResult with repair status and recovered files.
        """
        self._cancelled = False

        if output_path is None:
            output_path = archive_path.with_suffix(".repaired.zip")

        # First diagnose the damage
        damage_type = self.diagnose(archive_path)

        if damage_type == DamageType.NONE:
            # Archive is fine, just copy it
            shutil.copy2(archive_path, output_path)
            return RepairResult(
                status=RepairStatus.UNNECESSARY,
                output_path=output_path,
                damage_type=damage_type,
            )

        # Try different repair strategies based on damage type
        if damage_type == DamageType.CRC_MISMATCH:
            return self._repair_crc_errors(
                archive_path, output_path, progress_callback
            )
        elif damage_type in (DamageType.CENTRAL_DIRECTORY, DamageType.TRUNCATED):
            return self._repair_by_scanning(
                archive_path, output_path, progress_callback
            )
        else:
            return self._repair_by_scanning(
                archive_path, output_path, progress_callback
            )

    def _repair_crc_errors(
        self,
        archive_path: Path,
        output_path: Path,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> RepairResult:
        """Repair archive with CRC errors by skipping bad files.

        Args:
            archive_path: Source archive.
            output_path: Output path.
            progress_callback: Progress callback.

        Returns:
            RepairResult.
        """
        recovered: list[RecoveredFile] = []
        lost: list[str] = []

        try:
            with (
                zipfile.ZipFile(archive_path, "r") as src_zf,
                zipfile.ZipFile(output_path, "w") as dst_zf,
            ):
                members = src_zf.infolist()
                total = len(members)
                original_count = total

                for i, member in enumerate(members):
                    if self._cancelled:
                        return RepairResult(
                            status=RepairStatus.FAILED,
                            error_message="Repair cancelled",
                        )

                    if progress_callback:
                        progress_callback(member.filename, i, total)

                    try:
                        data = src_zf.read(member.filename)
                        dst_zf.writestr(member, data)
                        recovered.append(
                            RecoveredFile(
                                name=member.filename,
                                size=len(data),
                                status=RepairStatus.SUCCESS,
                            )
                        )
                    except Exception as e:
                        lost.append(member.filename)
                        recovered.append(
                            RecoveredFile(
                                name=member.filename,
                                status=RepairStatus.FAILED,
                                error=str(e),
                            )
                        )

                if progress_callback:
                    progress_callback("", total, total)

        except Exception as e:
            return RepairResult(
                status=RepairStatus.FAILED,
                damage_type=DamageType.CRC_MISMATCH,
                error_message=str(e),
            )

        recovered_count = len([r for r in recovered if r.status == RepairStatus.SUCCESS])

        return RepairResult(
            status=RepairStatus.SUCCESS if not lost else RepairStatus.PARTIAL,
            output_path=output_path,
            damage_type=DamageType.CRC_MISMATCH,
            recovered_files=recovered,
            lost_files=lost,
            original_file_count=original_count,
            recovered_file_count=recovered_count,
        )

    def _repair_by_scanning(
        self,
        archive_path: Path,
        output_path: Path,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> RepairResult:
        """Repair by scanning for local file headers.

        This is a fallback method that scans the raw file for ZIP
        local file headers and attempts to extract each file.

        Args:
            archive_path: Source archive.
            output_path: Output path.
            progress_callback: Progress callback.

        Returns:
            RepairResult.
        """
        recovered: list[RecoveredFile] = []
        lost: list[str] = []

        # First, find all local file headers
        headers = self._scan_local_headers(archive_path)

        if not headers:
            return RepairResult(
                status=RepairStatus.FAILED,
                damage_type=DamageType.HEADER,
                error_message="No valid file headers found",
            )

        total = len(headers)

        try:
            with (
                archive_path.open("rb") as src_file,
                zipfile.ZipFile(output_path, "w") as dst_zf,
            ):
                for i, (offset, filename, comp_size, uncomp_size, comp_method) in enumerate(
                    headers
                ):
                    if self._cancelled:
                        return RepairResult(
                            status=RepairStatus.FAILED,
                            error_message="Repair cancelled",
                        )

                    if progress_callback:
                        progress_callback(filename, i, total)

                    try:
                        # Read compressed data
                        src_file.seek(offset)
                        data = self._extract_local_file(
                            src_file, comp_size, uncomp_size, comp_method
                        )

                        if data is not None:
                            dst_zf.writestr(filename, data)
                            recovered.append(
                                RecoveredFile(
                                    name=filename,
                                    size=len(data),
                                    status=RepairStatus.SUCCESS,
                                )
                            )
                        else:
                            lost.append(filename)
                            recovered.append(
                                RecoveredFile(
                                    name=filename,
                                    status=RepairStatus.FAILED,
                                    error="Could not decompress",
                                )
                            )
                    except Exception as e:
                        lost.append(filename)
                        recovered.append(
                            RecoveredFile(
                                name=filename,
                                status=RepairStatus.FAILED,
                                error=str(e),
                            )
                        )

                if progress_callback:
                    progress_callback("", total, total)

        except Exception as e:
            return RepairResult(
                status=RepairStatus.FAILED,
                error_message=str(e),
            )

        recovered_count = len([r for r in recovered if r.status == RepairStatus.SUCCESS])

        return RepairResult(
            status=RepairStatus.SUCCESS if not lost else RepairStatus.PARTIAL,
            output_path=output_path,
            damage_type=DamageType.CENTRAL_DIRECTORY,
            recovered_files=recovered,
            lost_files=lost,
            original_file_count=total,
            recovered_file_count=recovered_count,
        )

    def _scan_local_headers(
        self, archive_path: Path
    ) -> list[tuple[int, str, int, int, int]]:
        """Scan file for local file headers.

        Args:
            archive_path: Path to archive.

        Returns:
            List of (data_offset, filename, comp_size, uncomp_size, comp_method).
        """
        headers: list[tuple[int, str, int, int, int]] = []

        try:
            with archive_path.open("rb") as f:
                data = f.read()

            pos = 0
            while True:
                # Find next local file header
                idx = data.find(self.LOCAL_FILE_HEADER_SIG, pos)
                if idx == -1:
                    break

                try:
                    # Parse local file header
                    # Skip signature (4) + version (2) + flags (2)
                    comp_method = struct.unpack_from("<H", data, idx + 8)[0]
                    # Skip mod time (2) + mod date (2) + crc (4)
                    comp_size = struct.unpack_from("<I", data, idx + 18)[0]
                    uncomp_size = struct.unpack_from("<I", data, idx + 22)[0]
                    name_len = struct.unpack_from("<H", data, idx + 26)[0]
                    extra_len = struct.unpack_from("<H", data, idx + 28)[0]

                    filename = data[idx + 30 : idx + 30 + name_len].decode(
                        "utf-8", errors="replace"
                    )

                    # Calculate data offset
                    data_offset = idx + 30 + name_len + extra_len

                    # Skip directories
                    if not filename.endswith("/"):
                        headers.append(
                            (data_offset, filename, comp_size, uncomp_size, comp_method)
                        )

                    pos = idx + 4

                except (struct.error, UnicodeDecodeError):
                    pos = idx + 4
                    continue

        except Exception as e:
            logger.error("Error scanning headers: %s", e)

        return headers

    def _extract_local_file(
        self,
        file_obj: BinaryIO,
        comp_size: int,
        _uncomp_size: int,
        comp_method: int,
    ) -> bytes | None:
        """Extract file data from local file header.

        Args:
            file_obj: File object positioned at data start.
            comp_size: Compressed size.
            _uncomp_size: Uncompressed size (unused but in ZIP header).
            comp_method: Compression method.

        Returns:
            Decompressed data or None on failure.
        """
        import zlib  # noqa: PLC0415

        try:
            comp_data = file_obj.read(comp_size)

            if comp_method == 0:  # Stored
                return bytes(comp_data)
            elif comp_method == 8:  # Deflate
                return bytes(zlib.decompress(comp_data, -zlib.MAX_WBITS))
            else:
                logger.warning("Unsupported compression method: %d", comp_method)
                return None

        except Exception as e:
            logger.debug("Extraction failed: %s", e)
            return None


def repair_archive(
    archive_path: Path | str,
    output_path: Path | str | None = None,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> RepairResult:
    """Repair a corrupted archive.

    Args:
        archive_path: Path to the corrupted archive.
        output_path: Path for repaired archive.
        progress_callback: Optional progress callback.

    Returns:
        RepairResult with repair status.
    """
    if isinstance(archive_path, str):
        archive_path = Path(archive_path)
    if isinstance(output_path, str):
        output_path = Path(output_path)

    fmt = detect_format(archive_path)

    if fmt == ArchiveFormat.ZIP:
        repairer = ZipRepairer()
        return repairer.repair(archive_path, output_path, progress_callback)
    else:
        return RepairResult(
            status=RepairStatus.FAILED,
            error_message=f"Repair not supported for {fmt.name if fmt else 'unknown'} format",
        )


def diagnose_archive(archive_path: Path | str) -> DamageType:
    """Diagnose damage type in an archive.

    Args:
        archive_path: Path to the archive.

    Returns:
        Type of damage detected.
    """
    if isinstance(archive_path, str):
        archive_path = Path(archive_path)

    fmt = detect_format(archive_path)

    if fmt == ArchiveFormat.ZIP:
        repairer = ZipRepairer()
        return repairer.diagnose(archive_path)

    return DamageType.UNKNOWN


def can_repair(archive_path: Path | str) -> bool:
    """Check if an archive can potentially be repaired.

    Args:
        archive_path: Path to the archive.

    Returns:
        True if repair might be possible.
    """
    damage = diagnose_archive(archive_path)
    return damage != DamageType.NONE


def recover_files(
    archive_path: Path | str,
    output_dir: Path | str,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> list[RecoveredFile]:
    """Attempt to recover files from a damaged archive.

    Unlike repair_archive, this extracts files directly to a directory
    instead of creating a new archive.

    Args:
        archive_path: Path to the damaged archive.
        output_dir: Directory to extract recovered files.
        progress_callback: Optional progress callback.

    Returns:
        List of RecoveredFile results.
    """
    if isinstance(archive_path, str):
        archive_path = Path(archive_path)
    if isinstance(output_dir, str):
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Create repaired archive in temp location
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        result = repair_archive(archive_path, tmp_path, progress_callback)

        if result.status in (RepairStatus.SUCCESS, RepairStatus.PARTIAL):
            # Extract from repaired archive
            try:
                with zipfile.ZipFile(tmp_path, "r") as zf:
                    zf.extractall(output_dir)
            except Exception as e:
                logger.error("Extraction failed: %s", e)

        return result.recovered_files

    finally:
        tmp_path.unlink(missing_ok=True)
