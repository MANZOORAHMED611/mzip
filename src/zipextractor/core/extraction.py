"""Core extraction engine for ZIP archives.

This module provides the ExtractionEngine class that handles the actual
extraction of ZIP archives with support for progress tracking, pause/resume,
cancellation, and conflict resolution.
"""

from __future__ import annotations

import contextlib
import os
import time
import zipfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from zipextractor.core.models import (
    ConflictResolution,
    ExtractionTask,
    TaskStatus,
)
from zipextractor.core.validation import (
    get_archive_info,
    is_safe_path,
    validate_archive,
    validate_disk_space,
)


class ExtractionEngine:
    """Core extraction engine for ZIP archives.

    This class provides methods for extracting ZIP archives with support for:
    - Progress tracking via callbacks
    - Pause/resume functionality
    - Cancellation support
    - Conflict resolution strategies (overwrite, skip, rename)
    - Preservation of file permissions and timestamps

    Example:
        >>> engine = ExtractionEngine()
        >>> task = ExtractionTask(
        ...     task_id="task_001",
        ...     archive_path=Path("archive.zip"),
        ...     destination_path=Path("/tmp/extract"),
        ... )
        >>> success = engine.extract(task, progress_callback=my_callback)
    """

    def __init__(self) -> None:
        """Initialize the extraction engine."""
        self._cancelled: bool = False
        self._paused: bool = False

    def extract(
        self,
        task: ExtractionTask,
        progress_callback: Callable[[ExtractionTask], None] | None = None,
    ) -> bool:
        """Extract archive according to task configuration.

        Extracts all files from the archive specified in the task to the
        destination directory. Handles conflicts according to the task's
        conflict resolution strategy.

        Args:
            task: ExtractionTask containing archive path, destination,
                and extraction options.
            progress_callback: Optional callback function called after each
                file is extracted. Receives the updated task object.

        Returns:
            True if extraction completed successfully, False otherwise.
            On failure, task.status will be set to TaskStatus.FAILED and
            task.error_message will contain the error details.

        Note:
            Updates task.status, task.extracted_files, task.extracted_bytes,
            task.current_file, task.started_at, and task.completed_at
            during extraction.
        """
        # Reset cancellation and pause flags
        self._cancelled = False
        self._paused = False

        try:
            # Step 1: Validate archive
            is_valid, error_msg = validate_archive(task.archive_path)
            if not is_valid:
                task.status = TaskStatus.FAILED
                task.error_message = f"Archive validation failed: {error_msg}"
                return False

            # Step 2: Get archive info for total size and file count
            archive_info = get_archive_info(task.archive_path)
            if not archive_info.is_valid:
                task.status = TaskStatus.FAILED
                task.error_message = f"Invalid archive: {', '.join(archive_info.validation_errors)}"
                return False

            task.total_files = archive_info.file_count
            task.total_bytes = archive_info.uncompressed_size

            # Step 3: Check disk space
            has_space, available = validate_disk_space(
                task.destination_path, task.total_bytes
            )
            if not has_space:
                task.status = TaskStatus.FAILED
                task.error_message = (
                    f"Insufficient disk space. Required: {task.total_bytes} bytes, "
                    f"Available: {available} bytes"
                )
                return False

            # Step 4: Create destination directory
            try:
                task.destination_path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                task.status = TaskStatus.FAILED
                task.error_message = f"Failed to create destination directory: {e}"
                return False

            # Step 5: Set task as running
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()

            # Step 5.5: Determine extraction base path (handles create_root_folder)
            if task.create_root_folder:
                # Create a folder named after the archive (without extension)
                archive_name = task.archive_path.stem
                extraction_base = task.destination_path / archive_name
                extraction_base.mkdir(parents=True, exist_ok=True)
            else:
                extraction_base = task.destination_path

            # Step 6: Extract files
            with zipfile.ZipFile(task.archive_path, "r") as zf:
                members = zf.infolist()

                for member in members:
                    # Check for cancellation
                    if self._cancelled:
                        task.status = TaskStatus.CANCELLED
                        task.completed_at = datetime.now()
                        return False

                    # Handle pause
                    while self._paused:
                        task.status = TaskStatus.PAUSED
                        time.sleep(0.1)
                        if self._cancelled:
                            task.status = TaskStatus.CANCELLED
                            task.completed_at = datetime.now()
                            return False

                    # Restore running status after pause
                    if task.status == TaskStatus.PAUSED:
                        task.status = TaskStatus.RUNNING

                    # Validate path safety
                    if not is_safe_path(extraction_base, member.filename):
                        if not member.is_dir():
                            task.failed_files.append(member.filename)
                        continue

                    # Handle directories (including empty ones)
                    if member.is_dir():
                        dir_path = extraction_base / member.filename
                        with contextlib.suppress(OSError):
                            dir_path.mkdir(parents=True, exist_ok=True)
                        continue

                    task.current_file = member.filename

                    # Determine target path
                    target_path = extraction_base / member.filename

                    # Handle conflict resolution
                    if target_path.exists():
                        resolved_path = self._resolve_conflict(
                            target_path, task.conflict_resolution
                        )
                        if resolved_path is None:
                            # Skip this file
                            task.extracted_bytes += member.file_size
                            if progress_callback:
                                progress_callback(task)
                            continue
                        target_path = resolved_path

                    # Create parent directories if needed
                    try:
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                    except OSError:
                        task.failed_files.append(member.filename)
                        continue

                    # Extract the file
                    try:
                        # Read the file content from the archive
                        file_content = zf.read(member.filename)

                        # Write to the target path (which may be renamed)
                        target_path.write_bytes(file_content)

                        # Preserve timestamps if requested
                        if task.preserve_timestamps and member.date_time:
                            try:
                                mod_time = datetime(*member.date_time)
                                timestamp = mod_time.timestamp()
                                os.utime(target_path, (timestamp, timestamp))
                            except (ValueError, OSError):
                                pass

                        # Preserve permissions if requested (Unix only)
                        if task.preserve_permissions:
                            external_attr = member.external_attr >> 16
                            if external_attr != 0:
                                with contextlib.suppress(OSError):
                                    target_path.chmod(external_attr)

                        task.extracted_files += 1
                        task.extracted_bytes += member.file_size

                    except (zipfile.BadZipFile, OSError):
                        task.failed_files.append(member.filename)

                    # Call progress callback
                    if progress_callback:
                        progress_callback(task)

            # Step 7: Mark as completed
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.current_file = None
            return True

        except zipfile.BadZipFile as e:
            task.status = TaskStatus.FAILED
            task.error_message = f"Corrupted archive: {e}"
            return False
        except PermissionError as e:
            task.status = TaskStatus.FAILED
            task.error_message = f"Permission denied: {e}"
            return False
        except OSError as e:
            task.status = TaskStatus.FAILED
            task.error_message = f"I/O error: {e}"
            return False
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = f"Unexpected error: {e}"
            return False

    def cancel(self) -> None:
        """Cancel ongoing extraction.

        Sets the cancellation flag which will be checked during extraction.
        The extraction will stop at the next file boundary.
        """
        self._cancelled = True

    def pause(self) -> None:
        """Pause ongoing extraction.

        Sets the pause flag which will cause the extraction loop to wait.
        Use resume() to continue extraction.
        """
        self._paused = True

    def resume(self) -> None:
        """Resume paused extraction.

        Clears the pause flag to allow extraction to continue.
        """
        self._paused = False

    def _resolve_conflict(
        self, path: Path, resolution: ConflictResolution
    ) -> Path | None:
        """Handle file conflict based on resolution strategy.

        Determines what to do when a file already exists at the target path.

        Args:
            path: The conflicting file path.
            resolution: The conflict resolution strategy to apply.

        Returns:
            - The same path if overwriting (ConflictResolution.OVERWRITE)
            - A new unique path if renaming (ConflictResolution.RENAME)
            - None if skipping (ConflictResolution.SKIP or ConflictResolution.ASK)

        Note:
            ConflictResolution.ASK returns None as interactive prompting
            should be handled at a higher level (UI layer).
        """
        if resolution == ConflictResolution.OVERWRITE:
            return path
        elif resolution == ConflictResolution.SKIP:
            return None
        elif resolution == ConflictResolution.RENAME:
            return self._get_unique_path(path)
        else:  # ConflictResolution.ASK
            # ASK should be handled at UI level; default to skip
            return None

    def _get_unique_path(self, path: Path) -> Path:
        """Generate unique filename like 'file (1).txt'.

        Creates a unique path by appending a counter in parentheses
        before the file extension.

        Args:
            path: The original file path that has a conflict.

        Returns:
            A new unique path that doesn't exist on the filesystem.

        Example:
            >>> engine._get_unique_path(Path("/tmp/file.txt"))
            Path('/tmp/file (1).txt')  # if file.txt exists
        """
        if not path.exists():
            return path

        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        counter = 1

        while True:
            new_name = f"{stem} ({counter}){suffix}"
            new_path = parent / new_name
            if not new_path.exists():
                return new_path
            counter += 1

            # Safety limit to prevent infinite loops
            if counter > 10000:
                # Fall back to timestamp-based naming
                timestamp = int(time.time() * 1000)
                new_name = f"{stem}_{timestamp}{suffix}"
                return parent / new_name
