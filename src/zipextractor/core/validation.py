"""Archive validation functions for ZIP Extractor.

This module provides functions to validate ZIP archives, detect potential
security threats like zip bombs and path traversal attacks, and check
system resources before extraction.
"""

from __future__ import annotations

import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from zipextractor.core.models import ArchiveFile, ArchiveInfo


def validate_archive(path: Path) -> tuple[bool, str | None]:
    """Validate that a file is a valid ZIP archive.

    Checks that the file exists, is not empty, and is a valid ZIP file
    that can be read by the zipfile module.

    Args:
        path: Path to the archive file to validate.

    Returns:
        A tuple of (is_valid, error_message).
        Returns (True, None) if the archive is valid.
        Returns (False, error_message) if the archive is invalid.

    Examples:
        >>> valid, error = validate_archive(Path("archive.zip"))
        >>> if not valid:
        ...     print(f"Invalid archive: {error}")
    """
    if not path.exists():
        return False, f"File does not exist: {path}"

    if not path.is_file():
        return False, f"Path is not a file: {path}"

    if path.stat().st_size == 0:
        return False, "File is empty"

    if not zipfile.is_zipfile(path):
        return False, "File is not a valid ZIP archive"

    try:
        with zipfile.ZipFile(path, "r") as zf:
            # Test archive integrity by reading the central directory
            bad_file = zf.testzip()
            if bad_file is not None:
                return False, f"Corrupted file in archive: {bad_file}"
    except zipfile.BadZipFile as e:
        return False, f"Bad ZIP file: {e}"
    except Exception as e:
        return False, f"Error reading archive: {e}"

    return True, None


def get_archive_info(path: Path) -> ArchiveInfo:
    """Get detailed information about a ZIP archive.

    Reads the archive metadata and returns an ArchiveInfo object with
    all fields populated, including a list of ArchiveFile objects for
    each entry in the archive.

    Args:
        path: Path to the archive file.

    Returns:
        ArchiveInfo object with all metadata fields populated.

    Raises:
        FileNotFoundError: If the archive file does not exist.
        zipfile.BadZipFile: If the file is not a valid ZIP archive.

    Examples:
        >>> info = get_archive_info(Path("archive.zip"))
        >>> print(f"Archive contains {info.file_count} files")
    """
    if not path.exists():
        raise FileNotFoundError(f"Archive not found: {path}")

    file_size = path.stat().st_size
    validation_errors: list[str] = []
    files: list[ArchiveFile] = []
    uncompressed_size = 0
    has_password = False
    compression_method = "unknown"

    try:
        with zipfile.ZipFile(path, "r") as zf:
            # Check for encrypted files
            for info in zf.infolist():
                if info.flag_bits & 0x1:  # Encrypted flag
                    has_password = True
                    break

            # Get compression method from first file
            if zf.infolist():
                first_info = zf.infolist()[0]
                compression_method = _get_compression_method_name(first_info.compress_type)

            # Build file list
            for info in zf.infolist():
                # Convert DOS datetime to Python datetime
                modified_time = None
                if info.date_time and info.date_time != (0, 0, 0, 0, 0, 0):
                    try:
                        modified_time = datetime(*info.date_time)
                    except (ValueError, TypeError):
                        pass

                archive_file = ArchiveFile(
                    path=info.filename,
                    size=info.file_size,
                    compressed_size=info.compress_size,
                    is_directory=info.is_dir(),
                    modified_time=modified_time,
                    crc32=info.CRC,
                )
                files.append(archive_file)
                uncompressed_size += info.file_size

            # Test archive integrity
            bad_file = zf.testzip()
            if bad_file is not None:
                validation_errors.append(f"Corrupted file: {bad_file}")

    except zipfile.BadZipFile as e:
        validation_errors.append(f"Bad ZIP file: {e}")
    except Exception as e:
        validation_errors.append(f"Error reading archive: {e}")

    # Detect root folder
    file_paths = [f.path for f in files]
    root_folder = detect_root_folder(file_paths)

    return ArchiveInfo(
        path=path,
        file_size=file_size,
        uncompressed_size=uncompressed_size,
        file_count=len([f for f in files if not f.is_directory]),
        compression_method=compression_method,
        has_password=has_password,
        root_folder=root_folder,
        is_valid=len(validation_errors) == 0,
        validation_errors=validation_errors,
        files=files,
    )


def _get_compression_method_name(compress_type: int) -> str:
    """Convert zipfile compression type constant to human-readable name.

    Args:
        compress_type: The compression type constant from zipfile.

    Returns:
        Human-readable compression method name.
    """
    compression_methods = {
        zipfile.ZIP_STORED: "stored",
        zipfile.ZIP_DEFLATED: "deflate",
        zipfile.ZIP_BZIP2: "bzip2",
        zipfile.ZIP_LZMA: "lzma",
    }
    return compression_methods.get(compress_type, "unknown")


def detect_root_folder(file_paths: list[str]) -> str | None:
    """Detect if all files share a common root folder.

    Checks if all file paths in the archive share a single common
    root folder. This is useful for determining if the archive
    was created from a single directory.

    Args:
        file_paths: List of file paths from the archive.

    Returns:
        The common root folder name if all files share one,
        None otherwise or if the archive is empty.

    Examples:
        >>> detect_root_folder(["project/src/main.py", "project/README.md"])
        'project'
        >>> detect_root_folder(["src/main.py", "README.md"])
        None
    """
    if not file_paths:
        return None

    # Extract first path component for each file
    root_folders = set()
    for path in file_paths:
        # Normalize path separators and get first component
        normalized = path.replace("\\", "/").strip("/")
        if not normalized:
            continue

        parts = normalized.split("/")
        if len(parts) > 0:
            root_folders.add(parts[0])

    # Check if there's exactly one root folder and all paths are under it
    if len(root_folders) == 1:
        root = next(iter(root_folders))
        # Verify all paths actually start with this root folder
        # (not just files at the root level)
        all_under_root = all(
            path.replace("\\", "/").strip("/").startswith(root + "/")
            or path.replace("\\", "/").strip("/") == root
            for path in file_paths
            if path.replace("\\", "/").strip("/")
        )
        if all_under_root:
            return root

    return None


def detect_zip_bomb(path: Path, max_ratio: float = 100.0) -> bool:
    """Detect potential zip bomb by checking compression ratio.

    A zip bomb is a malicious archive designed to crash or render
    unusable the system when unpacked. This function detects potential
    zip bombs by checking if the compression ratio exceeds a threshold.

    Args:
        path: Path to the archive file.
        max_ratio: Maximum allowed compression ratio (uncompressed/compressed).
            Default is 100.0, meaning uncompressed size cannot exceed
            100x the compressed size.

    Returns:
        True if the archive is potentially a zip bomb (ratio exceeds max_ratio),
        False otherwise.

    Examples:
        >>> if detect_zip_bomb(Path("suspicious.zip")):
        ...     print("Warning: Potential zip bomb detected!")
    """
    if not path.exists():
        return False

    try:
        compressed_size = path.stat().st_size
        if compressed_size == 0:
            return False

        with zipfile.ZipFile(path, "r") as zf:
            uncompressed_size = sum(info.file_size for info in zf.infolist())

        if uncompressed_size == 0:
            return False

        ratio = uncompressed_size / compressed_size
        return ratio > max_ratio

    except (zipfile.BadZipFile, OSError):
        return False


def is_safe_path(base_path: Path, target_path: str) -> bool:
    """Check if a target path is safe from path traversal attacks.

    Validates that the target path, when resolved relative to the base path,
    remains within the base path. This prevents malicious archives from
    writing files outside the intended extraction directory using
    path traversal sequences like '../'.

    Args:
        base_path: The base directory where extraction should occur.
        target_path: The target path from the archive to validate.

    Returns:
        True if the path is safe (stays within base_path),
        False if the path is dangerous (escapes base_path or is absolute).

    Examples:
        >>> is_safe_path(Path("/extract"), "subdir/file.txt")
        True
        >>> is_safe_path(Path("/extract"), "../etc/passwd")
        False
        >>> is_safe_path(Path("/extract"), "/etc/passwd")
        False
    """
    # Check for absolute paths
    if Path(target_path).is_absolute():
        return False

    # Normalize and check for path traversal
    # Replace backslashes for Windows-style paths
    normalized = target_path.replace("\\", "/")

    # Check for explicit path traversal sequences
    if ".." in normalized.split("/"):
        return False

    # Resolve the full path and check if it's within base_path
    try:
        base_resolved = base_path.resolve()
        # Join and resolve the target path
        target_resolved = (base_path / target_path).resolve()

        # Check if target is under base path
        # Using os.path.commonpath for reliable comparison
        try:
            common = Path(os.path.commonpath([base_resolved, target_resolved]))
            return common == base_resolved
        except ValueError:
            # Different drives on Windows
            return False

    except (OSError, ValueError):
        return False


def validate_disk_space(
    dest: Path, required_bytes: int, buffer: float = 0.1
) -> tuple[bool, int]:
    """Validate that sufficient disk space is available for extraction.

    Checks the available disk space at the destination path and compares
    it against the required bytes plus a safety buffer.

    Args:
        dest: Destination path for extraction.
        required_bytes: Number of bytes needed for extraction.
        buffer: Safety buffer as a fraction of required bytes.
            Default is 0.1 (10% extra space required).

    Returns:
        A tuple of (has_space, available_bytes).
        Returns (True, available) if there is enough disk space.
        Returns (False, available) if there is insufficient disk space.

    Examples:
        >>> has_space, available = validate_disk_space(Path("/tmp"), 1000000)
        >>> if not has_space:
        ...     print(f"Need more space, only {available} bytes available")
    """
    # Find the mount point by traversing up to an existing directory
    check_path = dest
    while not check_path.exists():
        parent = check_path.parent
        if parent == check_path:
            # Reached root and nothing exists
            break
        check_path = parent

    try:
        usage = shutil.disk_usage(check_path)
        available = usage.free
    except OSError:
        # If we can't determine disk space, assume it's available
        # but return 0 to indicate uncertainty
        return True, 0

    required_with_buffer = int(required_bytes * (1 + buffer))

    if available >= required_with_buffer:
        return True, available
    else:
        return False, available
