"""Archive comparison functionality.

This module provides tools to compare two archives and identify
differences in content, files added/removed/modified.
"""

from __future__ import annotations

import hashlib
import tarfile
import zipfile
import zlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path

from zipextractor.core.formats import detect_format
from zipextractor.core.models import ArchiveFormat
from zipextractor.utils.logging import get_logger

logger = get_logger(__name__)


class DifferenceType(Enum):
    """Type of difference between archives."""

    ADDED = auto()  # File exists only in second archive
    REMOVED = auto()  # File exists only in first archive
    MODIFIED = auto()  # File exists in both but differs
    UNCHANGED = auto()  # File is identical in both


class CompareMethod(Enum):
    """Method for comparing files."""

    SIZE_ONLY = auto()  # Compare by size only (fast)
    CRC = auto()  # Compare by CRC/checksum
    CONTENT = auto()  # Full content comparison (slow but accurate)
    DATE = auto()  # Compare by modification date


@dataclass
class FileDifference:
    """Information about a difference between files.

    Attributes:
        path: Path within the archive.
        diff_type: Type of difference.
        size1: Size in first archive (or None).
        size2: Size in second archive (or None).
        crc1: CRC in first archive (or None).
        crc2: CRC in second archive (or None).
        modified1: Modification date in first archive.
        modified2: Modification date in second archive.
        details: Additional details about the difference.
    """

    path: str
    diff_type: DifferenceType
    size1: int | None = None
    size2: int | None = None
    crc1: int | None = None
    crc2: int | None = None
    modified1: datetime | None = None
    modified2: datetime | None = None
    details: str = ""

    @property
    def size_diff(self) -> int:
        """Get size difference (positive if larger in archive 2)."""
        if self.size1 is None or self.size2 is None:
            return 0
        return self.size2 - self.size1


@dataclass
class ComparisonResult:
    """Result of comparing two archives.

    Attributes:
        archive1: Path to first archive.
        archive2: Path to second archive.
        method: Comparison method used.
        differences: List of file differences.
        added_files: Files only in second archive.
        removed_files: Files only in first archive.
        modified_files: Files that differ.
        unchanged_files: Files that are identical.
        total_files_archive1: Total files in first archive.
        total_files_archive2: Total files in second archive.
        comparison_time_seconds: Time taken for comparison.
        errors: List of errors encountered.
    """

    archive1: Path
    archive2: Path
    method: CompareMethod
    differences: list[FileDifference] = field(default_factory=list)
    added_files: list[str] = field(default_factory=list)
    removed_files: list[str] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    unchanged_files: list[str] = field(default_factory=list)
    total_files_archive1: int = 0
    total_files_archive2: int = 0
    comparison_time_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def are_identical(self) -> bool:
        """Check if archives are identical."""
        return (
            len(self.added_files) == 0
            and len(self.removed_files) == 0
            and len(self.modified_files) == 0
        )

    @property
    def has_differences(self) -> bool:
        """Check if any differences were found."""
        return not self.are_identical

    @property
    def total_size_diff(self) -> int:
        """Get total size difference."""
        return sum(d.size_diff for d in self.differences)


@dataclass
class ArchiveFileInfo:
    """Information about a file for comparison."""

    path: str
    size: int
    crc: int | None
    modified: datetime | None
    is_directory: bool


class ArchiveComparer:
    """Compare two archive files.

    Identifies added, removed, and modified files between archives.
    """

    def __init__(
        self,
        method: CompareMethod = CompareMethod.CRC,
        password1: str | None = None,
        password2: str | None = None,
    ) -> None:
        """Initialize comparer.

        Args:
            method: Comparison method to use.
            password1: Password for first archive.
            password2: Password for second archive.
        """
        self._method = method
        self._password1 = password1
        self._password2 = password2
        self._cancelled = False

    def cancel(self) -> None:
        """Cancel ongoing comparison."""
        self._cancelled = True

    def compare(  # noqa: PLR0912, PLR0915
        self,
        archive1: Path,
        archive2: Path,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> ComparisonResult:
        """Compare two archives.

        Args:
            archive1: Path to first archive.
            archive2: Path to second archive.
            progress_callback: Optional callback(filename, current, total).

        Returns:
            ComparisonResult with differences.
        """
        import time  # noqa: PLC0415

        self._cancelled = False
        start_time = time.time()

        # Get file lists from both archives
        files1 = self._get_file_list(archive1, self._password1)
        files2 = self._get_file_list(archive2, self._password2)

        if files1 is None:
            return ComparisonResult(
                archive1=archive1,
                archive2=archive2,
                method=self._method,
                errors=[f"Could not read archive: {archive1}"],
            )

        if files2 is None:
            return ComparisonResult(
                archive1=archive1,
                archive2=archive2,
                method=self._method,
                errors=[f"Could not read archive: {archive2}"],
            )

        # Create lookup dictionaries
        dict1 = {f.path: f for f in files1}
        dict2 = {f.path: f for f in files2}

        paths1 = set(dict1.keys())
        paths2 = set(dict2.keys())

        # Find differences
        added = paths2 - paths1
        removed = paths1 - paths2
        common = paths1 & paths2

        differences: list[FileDifference] = []
        added_list: list[str] = []
        removed_list: list[str] = []
        modified_list: list[str] = []
        unchanged_list: list[str] = []

        total = len(added) + len(removed) + len(common)
        current = 0

        # Process added files
        for path in sorted(added):
            if self._cancelled:
                break
            current += 1
            if progress_callback:
                progress_callback(path, current, total)

            info = dict2[path]
            added_list.append(path)
            differences.append(
                FileDifference(
                    path=path,
                    diff_type=DifferenceType.ADDED,
                    size2=info.size,
                    crc2=info.crc,
                    modified2=info.modified,
                    details="File added",
                )
            )

        # Process removed files
        for path in sorted(removed):
            if self._cancelled:
                break
            current += 1
            if progress_callback:
                progress_callback(path, current, total)

            info = dict1[path]
            removed_list.append(path)
            differences.append(
                FileDifference(
                    path=path,
                    diff_type=DifferenceType.REMOVED,
                    size1=info.size,
                    crc1=info.crc,
                    modified1=info.modified,
                    details="File removed",
                )
            )

        # Process common files
        for path in sorted(common):
            if self._cancelled:
                break
            current += 1
            if progress_callback:
                progress_callback(path, current, total)

            info1 = dict1[path]
            info2 = dict2[path]

            is_different, detail = self._files_differ(
                info1, info2, archive1, archive2
            )

            diff = FileDifference(
                path=path,
                diff_type=DifferenceType.MODIFIED if is_different else DifferenceType.UNCHANGED,
                size1=info1.size,
                size2=info2.size,
                crc1=info1.crc,
                crc2=info2.crc,
                modified1=info1.modified,
                modified2=info2.modified,
                details=detail,
            )
            differences.append(diff)

            if is_different:
                modified_list.append(path)
            else:
                unchanged_list.append(path)

        if progress_callback:
            progress_callback("", total, total)

        result = ComparisonResult(
            archive1=archive1,
            archive2=archive2,
            method=self._method,
            differences=differences,
            added_files=added_list,
            removed_files=removed_list,
            modified_files=modified_list,
            unchanged_files=unchanged_list,
            total_files_archive1=len(files1),
            total_files_archive2=len(files2),
            comparison_time_seconds=time.time() - start_time,
        )

        return result

    def _get_file_list(
        self, archive_path: Path, password: str | None
    ) -> list[ArchiveFileInfo] | None:
        """Get list of files in archive."""
        fmt = detect_format(archive_path)
        if fmt is None:
            return None

        if fmt == ArchiveFormat.ZIP:
            return self._get_zip_files(archive_path, password)
        elif fmt in (
            ArchiveFormat.TAR,
            ArchiveFormat.TAR_GZ,
            ArchiveFormat.TAR_BZ2,
            ArchiveFormat.TAR_XZ,
        ):
            return self._get_tar_files(archive_path, fmt)

        return None

    def _get_zip_files(
        self, archive_path: Path, _password: str | None
    ) -> list[ArchiveFileInfo] | None:
        """Get file list from ZIP archive.

        Args:
            archive_path: Path to the archive.
            _password: Password (unused for listing, but may be needed for encrypted).
        """
        files: list[ArchiveFileInfo] = []

        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                for member in zf.infolist():
                    if member.is_dir():
                        continue

                    try:
                        modified = datetime(*member.date_time)
                    except (ValueError, TypeError):
                        modified = None

                    files.append(
                        ArchiveFileInfo(
                            path=member.filename,
                            size=member.file_size,
                            crc=member.CRC,
                            modified=modified,
                            is_directory=False,
                        )
                    )

        except Exception as e:
            logger.error("Error reading ZIP %s: %s", archive_path, e)
            return None

        return files

    def _get_tar_files(
        self, archive_path: Path, fmt: ArchiveFormat
    ) -> list[ArchiveFileInfo] | None:
        """Get file list from TAR archive."""
        files: list[ArchiveFileInfo] = []

        mode_map = {
            ArchiveFormat.TAR: "r",
            ArchiveFormat.TAR_GZ: "r:gz",
            ArchiveFormat.TAR_BZ2: "r:bz2",
            ArchiveFormat.TAR_XZ: "r:xz",
        }
        mode = mode_map.get(fmt, "r")

        try:
            with tarfile.open(str(archive_path), mode) as tf:  # type: ignore[call-overload]
                for member in tf.getmembers():
                    if member.isdir():
                        continue

                    try:
                        modified = datetime.fromtimestamp(member.mtime)
                    except (ValueError, TypeError, OSError):
                        modified = None

                    # TAR doesn't store CRC, compute if needed
                    crc = None
                    if self._method == CompareMethod.CRC:
                        try:
                            extracted = tf.extractfile(member)
                            if extracted:
                                data = extracted.read()
                                crc = zlib.crc32(data) & 0xFFFFFFFF
                        except Exception:
                            pass

                    files.append(
                        ArchiveFileInfo(
                            path=member.name,
                            size=member.size,
                            crc=crc,
                            modified=modified,
                            is_directory=False,
                        )
                    )

        except Exception as e:
            logger.error("Error reading TAR %s: %s", archive_path, e)
            return None

        return files

    def _files_differ(  # noqa: PLR0911, PLR0912
        self,
        info1: ArchiveFileInfo,
        info2: ArchiveFileInfo,
        archive1: Path,
        archive2: Path,
    ) -> tuple[bool, str]:
        """Check if two files differ.

        Returns:
            Tuple of (is_different, detail_message).
        """
        if self._method == CompareMethod.SIZE_ONLY:
            if info1.size != info2.size:
                return True, f"Size differs: {info1.size} vs {info2.size}"
            return False, ""

        elif self._method == CompareMethod.DATE:
            if info1.modified != info2.modified:
                return True, f"Date differs: {info1.modified} vs {info2.modified}"
            return False, ""

        elif self._method == CompareMethod.CRC:
            if info1.crc is not None and info2.crc is not None:
                if info1.crc != info2.crc:
                    return True, f"CRC differs: {info1.crc:08x} vs {info2.crc:08x}"
                return False, ""
            # Fall back to size comparison if CRC not available
            if info1.size != info2.size:
                return True, f"Size differs: {info1.size} vs {info2.size}"
            return False, ""

        elif self._method == CompareMethod.CONTENT:
            # Compare actual content
            try:
                content1 = self._read_file(archive1, info1.path, self._password1)
                content2 = self._read_file(archive2, info2.path, self._password2)

                if content1 is None or content2 is None:
                    # Can't compare, fall back to CRC/size
                    if info1.crc != info2.crc:
                        return True, "CRC differs"
                    return False, ""

                if content1 != content2:
                    # Compute hash for detail
                    hash1 = hashlib.md5(content1).hexdigest()[:8]
                    hash2 = hashlib.md5(content2).hexdigest()[:8]
                    return True, f"Content differs: {hash1}... vs {hash2}..."
                return False, ""

            except Exception as e:
                return False, f"Could not compare: {e}"

        return False, ""  # type: ignore[unreachable]

    def _read_file(
        self, archive_path: Path, file_path: str, password: str | None
    ) -> bytes | None:
        """Read file content from archive."""
        fmt = detect_format(archive_path)

        try:
            if fmt == ArchiveFormat.ZIP:
                with zipfile.ZipFile(archive_path, "r") as zf:
                    pwd = password.encode() if password else None
                    return zf.read(file_path, pwd=pwd)
            elif fmt in (
                ArchiveFormat.TAR,
                ArchiveFormat.TAR_GZ,
                ArchiveFormat.TAR_BZ2,
                ArchiveFormat.TAR_XZ,
            ):
                mode_map = {
                    ArchiveFormat.TAR: "r",
                    ArchiveFormat.TAR_GZ: "r:gz",
                    ArchiveFormat.TAR_BZ2: "r:bz2",
                    ArchiveFormat.TAR_XZ: "r:xz",
                }
                mode = mode_map.get(fmt, "r")
                with tarfile.open(str(archive_path), mode) as tf:  # type: ignore[call-overload]
                    extracted = tf.extractfile(file_path)
                    if extracted:
                        return bytes(extracted.read())
        except Exception:
            pass

        return None


def compare_archives(
    archive1: Path | str,
    archive2: Path | str,
    method: CompareMethod = CompareMethod.CRC,
    password1: str | None = None,
    password2: str | None = None,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> ComparisonResult:
    """Compare two archives.

    Args:
        archive1: Path to first archive.
        archive2: Path to second archive.
        method: Comparison method.
        password1: Password for first archive.
        password2: Password for second archive.
        progress_callback: Optional progress callback.

    Returns:
        ComparisonResult with differences.
    """
    if isinstance(archive1, str):
        archive1 = Path(archive1)
    if isinstance(archive2, str):
        archive2 = Path(archive2)

    comparer = ArchiveComparer(method, password1, password2)
    return comparer.compare(archive1, archive2, progress_callback)


def archives_are_identical(
    archive1: Path | str,
    archive2: Path | str,
    method: CompareMethod = CompareMethod.CRC,
) -> bool:
    """Quick check if two archives are identical.

    Args:
        archive1: Path to first archive.
        archive2: Path to second archive.
        method: Comparison method.

    Returns:
        True if archives contain identical files.
    """
    result = compare_archives(archive1, archive2, method)
    return result.are_identical


def get_added_files(
    archive1: Path | str,
    archive2: Path | str,
) -> list[str]:
    """Get files that were added (exist only in archive2).

    Args:
        archive1: Path to first (older) archive.
        archive2: Path to second (newer) archive.

    Returns:
        List of file paths added.
    """
    result = compare_archives(archive1, archive2)
    return result.added_files


def get_removed_files(
    archive1: Path | str,
    archive2: Path | str,
) -> list[str]:
    """Get files that were removed (exist only in archive1).

    Args:
        archive1: Path to first (older) archive.
        archive2: Path to second (newer) archive.

    Returns:
        List of file paths removed.
    """
    result = compare_archives(archive1, archive2)
    return result.removed_files


def get_modified_files(
    archive1: Path | str,
    archive2: Path | str,
    method: CompareMethod = CompareMethod.CRC,
) -> list[str]:
    """Get files that were modified.

    Args:
        archive1: Path to first archive.
        archive2: Path to second archive.
        method: Comparison method.

    Returns:
        List of file paths modified.
    """
    result = compare_archives(archive1, archive2, method)
    return result.modified_files


def generate_diff_report(result: ComparisonResult) -> str:  # noqa: PLR0912
    """Generate a human-readable diff report.

    Args:
        result: Comparison result.

    Returns:
        Formatted report string.
    """
    lines: list[str] = []

    lines.append("Archive Comparison Report")
    lines.append("=" * 50)
    lines.append(f"Archive 1: {result.archive1}")
    lines.append(f"Archive 2: {result.archive2}")
    lines.append(f"Method: {result.method.name}")
    lines.append(f"Time: {result.comparison_time_seconds:.2f}s")
    lines.append("")

    lines.append("Summary")
    lines.append("-" * 50)
    lines.append(f"Files in Archive 1: {result.total_files_archive1}")
    lines.append(f"Files in Archive 2: {result.total_files_archive2}")
    lines.append(f"Added: {len(result.added_files)}")
    lines.append(f"Removed: {len(result.removed_files)}")
    lines.append(f"Modified: {len(result.modified_files)}")
    lines.append(f"Unchanged: {len(result.unchanged_files)}")
    lines.append("")

    if result.are_identical:
        lines.append("Archives are IDENTICAL")
    else:
        if result.added_files:
            lines.append("Added Files")
            lines.append("-" * 50)
            for path in result.added_files[:20]:  # Limit output
                lines.append(f"  + {path}")
            if len(result.added_files) > 20:
                lines.append(f"  ... and {len(result.added_files) - 20} more")
            lines.append("")

        if result.removed_files:
            lines.append("Removed Files")
            lines.append("-" * 50)
            for path in result.removed_files[:20]:
                lines.append(f"  - {path}")
            if len(result.removed_files) > 20:
                lines.append(f"  ... and {len(result.removed_files) - 20} more")
            lines.append("")

        if result.modified_files:
            lines.append("Modified Files")
            lines.append("-" * 50)
            for diff in result.differences:
                if diff.diff_type == DifferenceType.MODIFIED:
                    lines.append(f"  ~ {diff.path}")
                    if diff.details:
                        lines.append(f"    {diff.details}")
                    if diff.size_diff != 0:
                        sign = "+" if diff.size_diff > 0 else ""
                        lines.append(f"    Size change: {sign}{diff.size_diff} bytes")
            lines.append("")

    if result.errors:
        lines.append("Errors")
        lines.append("-" * 50)
        for error in result.errors:
            lines.append(f"  ! {error}")

    return "\n".join(lines)
