"""Split archive support for creating and extracting multi-part archives.

This module provides functionality to split large archives into smaller parts
and reassemble them for extraction.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from zipextractor.utils.logging import get_logger

logger = get_logger(__name__)

# Default split sizes
SPLIT_SIZE_CD = 700 * 1024 * 1024  # 700 MB (CD)
SPLIT_SIZE_DVD = 4700 * 1024 * 1024  # 4.7 GB (DVD)
SPLIT_SIZE_FAT32 = 4 * 1024 * 1024 * 1024 - 1  # 4 GB - 1 byte (FAT32 limit)
SPLIT_SIZE_DEFAULT = 100 * 1024 * 1024  # 100 MB


@dataclass
class SplitInfo:
    """Information about a split archive.

    Attributes:
        base_path: Base path without part suffix.
        parts: List of part file paths.
        total_size: Total size of all parts combined.
        part_count: Number of parts.
        part_size: Size of each part (last may be smaller).
    """

    base_path: Path
    parts: list[Path]
    total_size: int
    part_count: int
    part_size: int

    @property
    def is_complete(self) -> bool:
        """Check if all parts exist."""
        return all(p.exists() for p in self.parts)


@dataclass
class SplitResult:
    """Result of a split operation.

    Attributes:
        success: Whether split completed successfully.
        parts: List of created part files.
        total_size: Total bytes written.
        error_message: Error message if failed.
    """

    success: bool
    parts: list[Path]
    total_size: int = 0
    error_message: str | None = None


class ArchiveSplitter:
    """Splits files into multiple parts.

    Supports various naming conventions:
    - .001, .002, .003 (7-Zip style)
    - .z01, .z02, .zip (ZIP split archive)
    - .part1.rar, .part2.rar (RAR style)
    """

    # Naming patterns for split archives
    PATTERN_NUMERIC = "numeric"  # .001, .002, etc.
    PATTERN_ZIP = "zip"  # .z01, .z02, .zip
    PATTERN_RAR = "rar"  # .part1.rar, .part2.rar

    def __init__(
        self,
        part_size: int = SPLIT_SIZE_DEFAULT,
        pattern: str = PATTERN_NUMERIC,
    ) -> None:
        """Initialize splitter.

        Args:
            part_size: Maximum size of each part in bytes.
            pattern: Naming pattern for parts.
        """
        if part_size <= 0:
            msg = "Part size must be positive"
            raise ValueError(msg)

        self._part_size = part_size
        self._pattern = pattern
        self._cancelled = False

    @property
    def part_size(self) -> int:
        """Get configured part size."""
        return self._part_size

    def cancel(self) -> None:
        """Cancel ongoing operation."""
        self._cancelled = True

    def split(
        self,
        source: Path,
        output_dir: Path | None = None,
        progress_callback: Callable[[int, int, int], None] | None = None,
    ) -> SplitResult:
        """Split a file into multiple parts.

        Args:
            source: Source file to split.
            output_dir: Output directory for parts (default: same as source).
            progress_callback: Optional callback(part_num, bytes_written, total).

        Returns:
            SplitResult with list of created parts.
        """
        self._cancelled = False

        if not source.exists():
            return SplitResult(
                success=False, parts=[], error_message=f"Source not found: {source}"
            )

        output_dir = output_dir or source.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        total_size = source.stat().st_size
        parts: list[Path] = []
        bytes_written = 0
        part_num = 1

        try:
            with source.open("rb") as f:
                while True:
                    if self._cancelled:
                        # Clean up partial files
                        for part in parts:
                            if part.exists():
                                part.unlink()
                        return SplitResult(
                            success=False,
                            parts=[],
                            error_message="Operation cancelled",
                        )

                    chunk = f.read(self._part_size)
                    if not chunk:
                        break

                    part_path = self._get_part_path(source, output_dir, part_num)
                    part_path.write_bytes(chunk)
                    parts.append(part_path)

                    bytes_written += len(chunk)
                    if progress_callback:
                        progress_callback(part_num, bytes_written, total_size)

                    part_num += 1

            logger.info(
                "Split %s into %d parts (%d bytes each)",
                source.name,
                len(parts),
                self._part_size,
            )

            return SplitResult(
                success=True,
                parts=parts,
                total_size=bytes_written,
            )

        except OSError as e:
            # Clean up partial files
            for part in parts:
                if part.exists():
                    part.unlink()
            logger.error("Split failed: %s", e)
            return SplitResult(success=False, parts=[], error_message=str(e))

    def _get_part_path(self, source: Path, output_dir: Path, part_num: int) -> Path:
        """Get path for a part file.

        Args:
            source: Original source file.
            output_dir: Output directory.
            part_num: Part number (1-based).

        Returns:
            Path for the part file.
        """
        base_name = source.stem
        suffix = source.suffix

        if self._pattern == self.PATTERN_NUMERIC:
            return output_dir / f"{base_name}{suffix}.{part_num:03d}"
        elif self._pattern == self.PATTERN_ZIP:
            if part_num == 1:
                # First part uses original extension
                return output_dir / f"{base_name}.z01"
            else:
                return output_dir / f"{base_name}.z{part_num:02d}"
        elif self._pattern == self.PATTERN_RAR:
            return output_dir / f"{base_name}.part{part_num}.rar"
        else:
            return output_dir / f"{base_name}{suffix}.{part_num:03d}"


class ArchiveJoiner:
    """Joins split archive parts back into a single file."""

    def __init__(self) -> None:
        """Initialize joiner."""
        self._cancelled = False

    def cancel(self) -> None:
        """Cancel ongoing operation."""
        self._cancelled = True

    def detect_parts(self, first_part: Path) -> SplitInfo | None:
        """Detect all parts of a split archive.

        Args:
            first_part: Path to first part or any part.

        Returns:
            SplitInfo if parts found, None otherwise.
        """
        # Try to detect the naming pattern and find all parts
        parts = self._find_parts(first_part)
        if not parts:
            return None

        total_size = sum(p.stat().st_size for p in parts if p.exists())
        part_size = parts[0].stat().st_size if parts[0].exists() else 0

        # Determine base path (without part suffix)
        base_path = self._get_base_path(first_part)

        return SplitInfo(
            base_path=base_path,
            parts=parts,
            total_size=total_size,
            part_count=len(parts),
            part_size=part_size,
        )

    def _find_parts(self, first_part: Path) -> list[Path]:  # noqa: PLR0912
        """Find all parts of a split archive.

        Args:
            first_part: Path to any part.

        Returns:
            Sorted list of part paths.
        """
        parent = first_part.parent
        name = first_part.name

        # Try different patterns
        parts: list[Path] = []

        # Pattern: .001, .002, etc.
        if name.endswith((".001", ".002")) or ".00" in name:
            base = self._strip_numeric_suffix(name)
            for i in range(1, 1000):
                part = parent / f"{base}.{i:03d}"
                if part.exists():
                    parts.append(part)
                else:
                    break

        # Pattern: .z01, .z02, .zip
        elif ".z0" in name or name.endswith(".zip"):
            base = name.rsplit(".z", 1)[0] if ".z" in name else name.rsplit(".zip", 1)[0]
            for i in range(1, 100):
                part = parent / f"{base}.z{i:02d}"
                if part.exists():
                    parts.append(part)
                else:
                    break
            # Add final .zip if exists
            final_zip = parent / f"{base}.zip"
            if final_zip.exists() and final_zip not in parts:
                parts.append(final_zip)

        # Pattern: .part1.rar, .part2.rar
        elif ".part" in name and name.endswith(".rar"):
            base = name.split(".part")[0]
            for i in range(1, 1000):
                part = parent / f"{base}.part{i}.rar"
                if part.exists():
                    parts.append(part)
                else:
                    break

        # Fallback: try numeric suffix
        if not parts:
            parts = self._find_numeric_parts(first_part)

        return sorted(parts)

    def _find_numeric_parts(self, first_part: Path) -> list[Path]:
        """Find parts with numeric suffixes."""
        parts: list[Path] = []
        parent = first_part.parent

        # Extract base name by removing trailing numbers and dots
        name = first_part.name
        base = self._strip_numeric_suffix(name)

        for i in range(1, 10000):
            for pattern in [f"{base}.{i:03d}", f"{base}.{i:02d}", f"{base}.{i}"]:
                part = parent / pattern
                if part.exists():
                    parts.append(part)
                    break
            else:
                if i > 1:  # Found at least one part
                    break

        return parts

    def _strip_numeric_suffix(self, name: str) -> str:
        """Strip numeric suffix from filename."""
        parts = name.rsplit(".", 1)
        if len(parts) == 2 and parts[1].isdigit():
            return parts[0]
        # Handle double extension like .tar.001
        if len(parts) == 2:
            inner_parts = parts[0].rsplit(".", 1)
            if len(inner_parts) == 2:
                return parts[0]
        return name

    def _get_base_path(self, first_part: Path) -> Path:
        """Get base path without part suffix."""
        name = first_part.name
        parent = first_part.parent

        # Remove part suffix
        if ".00" in name:
            base = self._strip_numeric_suffix(name)
        elif ".z0" in name:
            base = name.rsplit(".z", 1)[0]
        elif ".part" in name:
            base = name.split(".part")[0]
        else:
            base = self._strip_numeric_suffix(name)

        return parent / base

    def join(
        self,
        parts: list[Path] | SplitInfo,
        output: Path,
        progress_callback: Callable[[int, int, int], None] | None = None,
    ) -> SplitResult:
        """Join split parts into a single file.

        Args:
            parts: List of part paths or SplitInfo object.
            output: Output file path.
            progress_callback: Optional callback(part_num, bytes_written, total).

        Returns:
            SplitResult with output path.
        """
        self._cancelled = False

        if isinstance(parts, SplitInfo):
            part_list = parts.parts
            total_size = parts.total_size
        else:
            part_list = sorted(parts)
            total_size = sum(p.stat().st_size for p in part_list if p.exists())

        if not part_list:
            return SplitResult(
                success=False, parts=[], error_message="No parts to join"
            )

        # Check all parts exist
        missing = [p for p in part_list if not p.exists()]
        if missing:
            return SplitResult(
                success=False,
                parts=[],
                error_message=f"Missing parts: {', '.join(str(p) for p in missing)}",
            )

        output.parent.mkdir(parents=True, exist_ok=True)
        bytes_written = 0

        try:
            with output.open("wb") as out_file:
                for i, part in enumerate(part_list, 1):
                    if self._cancelled:
                        output.unlink(missing_ok=True)
                        return SplitResult(
                            success=False,
                            parts=[],
                            error_message="Operation cancelled",
                        )

                    with part.open("rb") as part_file:
                        shutil.copyfileobj(part_file, out_file)

                    bytes_written += part.stat().st_size
                    if progress_callback:
                        progress_callback(i, bytes_written, total_size)

            logger.info(
                "Joined %d parts into %s (%d bytes)",
                len(part_list),
                output.name,
                bytes_written,
            )

            return SplitResult(
                success=True,
                parts=[output],
                total_size=bytes_written,
            )

        except OSError as e:
            output.unlink(missing_ok=True)
            logger.error("Join failed: %s", e)
            return SplitResult(success=False, parts=[], error_message=str(e))


def split_file(
    source: Path,
    part_size: int = SPLIT_SIZE_DEFAULT,
    output_dir: Path | None = None,
    progress_callback: Callable[[int, int, int], None] | None = None,
) -> SplitResult:
    """Split a file into multiple parts.

    Args:
        source: Source file to split.
        part_size: Maximum size of each part in bytes.
        output_dir: Output directory for parts.
        progress_callback: Optional callback(part_num, bytes_written, total).

    Returns:
        SplitResult with list of created parts.
    """
    splitter = ArchiveSplitter(part_size=part_size)
    return splitter.split(source, output_dir, progress_callback)


def join_parts(
    first_part: Path,
    output: Path | None = None,
    progress_callback: Callable[[int, int, int], None] | None = None,
) -> SplitResult:
    """Join split archive parts into a single file.

    Args:
        first_part: Path to first part or any part.
        output: Output file path (default: derived from parts).
        progress_callback: Optional callback(part_num, bytes_written, total).

    Returns:
        SplitResult with output path.
    """
    joiner = ArchiveJoiner()
    info = joiner.detect_parts(first_part)

    if info is None:
        return SplitResult(
            success=False, parts=[], error_message="Could not detect split archive parts"
        )

    if output is None:
        output = info.base_path

    return joiner.join(info, output, progress_callback)


def is_split_archive(path: Path) -> bool:
    """Check if a file is part of a split archive.

    Args:
        path: Path to check.

    Returns:
        True if file appears to be a split archive part.
    """
    name = path.name.lower()

    # Check common patterns
    patterns = [
        ".001",
        ".002",
        ".z01",
        ".z02",
        ".part1.",
        ".part2.",
    ]

    return any(pattern in name for pattern in patterns)


def get_split_parts(path: Path) -> list[Path]:
    """Get all parts of a split archive.

    Args:
        path: Path to any part.

    Returns:
        List of all part paths, or empty list if not a split archive.
    """
    joiner = ArchiveJoiner()
    info = joiner.detect_parts(path)
    return info.parts if info else []


def iter_split_chunks(
    source: Path, chunk_size: int = SPLIT_SIZE_DEFAULT
) -> Iterator[bytes]:
    """Iterate over a file in chunks.

    Args:
        source: Source file.
        chunk_size: Size of each chunk.

    Yields:
        File content in chunks.
    """
    with source.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk
