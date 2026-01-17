"""Extraction history tracking and persistence.

This module provides functionality for tracking completed extractions
and persisting the history to disk for display in the UI.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from zipextractor.utils.logging import get_logger

logger = get_logger(__name__)

# Default history location
DEFAULT_HISTORY_DIR = Path.home() / ".local" / "share" / "zipextractor"
DEFAULT_HISTORY_FILE = DEFAULT_HISTORY_DIR / "history.json"
MAX_HISTORY_ENTRIES = 50


@dataclass
class ExtractionRecord:
    """Record of a completed extraction operation.

    Attributes:
        archive_name: Name of the extracted archive.
        archive_path: Full path to the archive file.
        destination_path: Path where files were extracted.
        extracted_files: Number of files extracted.
        extracted_bytes: Total bytes extracted.
        timestamp: When the extraction completed.
        success: Whether extraction was successful.
        error_message: Error message if extraction failed.
    """

    archive_name: str
    archive_path: str
    destination_path: str
    extracted_files: int
    extracted_bytes: int
    timestamp: str
    success: bool = True
    error_message: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ExtractionRecord:
        """Create an ExtractionRecord from a dictionary.

        Args:
            data: Dictionary with record data.

        Returns:
            ExtractionRecord instance.
        """
        # Extract and validate numeric values
        extracted_files_val = data.get("extracted_files", 0)
        extracted_bytes_val = data.get("extracted_bytes", 0)

        # Safe conversion to int
        if isinstance(extracted_files_val, (int, float)):
            extracted_files = int(extracted_files_val)
        else:
            extracted_files = 0

        if isinstance(extracted_bytes_val, (int, float)):
            extracted_bytes = int(extracted_bytes_val)
        else:
            extracted_bytes = 0

        return cls(
            archive_name=str(data.get("archive_name", "")),
            archive_path=str(data.get("archive_path", "")),
            destination_path=str(data.get("destination_path", "")),
            extracted_files=extracted_files,
            extracted_bytes=extracted_bytes,
            timestamp=str(data.get("timestamp", "")),
            success=bool(data.get("success", True)),
            error_message=str(data["error_message"]) if data.get("error_message") else None,
        )

    def to_dict(self) -> dict[str, object]:
        """Convert record to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the record.
        """
        return asdict(self)


@dataclass
class ExtractionHistory:
    """Container for extraction history with persistence.

    Manages a list of ExtractionRecord entries and handles
    loading/saving to JSON file.

    Attributes:
        records: List of extraction records, newest first.
        history_file: Path to the history JSON file.
    """

    records: list[ExtractionRecord] = field(default_factory=list)
    history_file: Path = field(default=DEFAULT_HISTORY_FILE)

    def add_record(
        self,
        archive_path: Path,
        destination_path: Path,
        extracted_files: int,
        extracted_bytes: int,
        success: bool = True,
        error_message: str | None = None,
    ) -> ExtractionRecord:
        """Add a new extraction record.

        Args:
            archive_path: Path to the archive that was extracted.
            destination_path: Path where files were extracted.
            extracted_files: Number of files extracted.
            extracted_bytes: Total bytes extracted.
            success: Whether extraction was successful.
            error_message: Error message if extraction failed.

        Returns:
            The created ExtractionRecord.
        """
        record = ExtractionRecord(
            archive_name=archive_path.name,
            archive_path=str(archive_path),
            destination_path=str(destination_path),
            extracted_files=extracted_files,
            extracted_bytes=extracted_bytes,
            timestamp=datetime.now().isoformat(),
            success=success,
            error_message=error_message,
        )

        # Insert at beginning (newest first)
        self.records.insert(0, record)

        # Trim to max entries
        if len(self.records) > MAX_HISTORY_ENTRIES:
            self.records = self.records[:MAX_HISTORY_ENTRIES]

        logger.debug("Added extraction record: %s", archive_path.name)
        return record

    def get_recent(self, count: int = 10) -> list[ExtractionRecord]:
        """Get the most recent extraction records.

        Args:
            count: Maximum number of records to return.

        Returns:
            List of most recent ExtractionRecord entries.
        """
        return self.records[:count]

    def clear(self) -> None:
        """Clear all history records."""
        self.records.clear()
        logger.info("Extraction history cleared")

    def load(self) -> None:
        """Load history from disk.

        Silently handles missing or corrupt files.
        """
        if not self.history_file.exists():
            logger.debug("No history file found at %s", self.history_file)
            return

        try:
            with self.history_file.open("r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                self.records = [ExtractionRecord.from_dict(r) for r in data]
                logger.info("Loaded %d history records", len(self.records))
        except json.JSONDecodeError as e:
            logger.warning("Could not parse history file: %s", e)
            self.records = []
        except Exception as e:
            logger.warning("Could not load history: %s", e)
            self.records = []

    def save(self) -> None:
        """Save history to disk.

        Creates the history directory if it doesn't exist.
        """
        try:
            # Ensure directory exists
            self.history_file.parent.mkdir(parents=True, exist_ok=True)

            # Write history
            with self.history_file.open("w", encoding="utf-8") as f:
                json.dump(
                    [r.to_dict() for r in self.records],
                    f,
                    indent=2,
                    ensure_ascii=False,
                )

            logger.debug("Saved %d history records", len(self.records))
        except Exception as e:
            logger.exception("Could not save history: %s", e)


class HistoryManager:
    """Singleton manager for extraction history.

    Provides a global access point for the extraction history,
    handling loading and saving automatically.

    Example:
        >>> manager = HistoryManager()
        >>> manager.add_extraction(archive_path, dest_path, 10, 1024)
        >>> recent = manager.get_recent(5)
    """

    _instance: HistoryManager | None = None
    _history: ExtractionHistory | None = None

    def __new__(cls) -> HistoryManager:
        """Create or return the singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._history = ExtractionHistory()
            cls._history.load()
        return cls._instance

    @property
    def history(self) -> ExtractionHistory:
        """Get the extraction history instance."""
        if self._history is None:
            self._history = ExtractionHistory()
            self._history.load()
        return self._history

    def add_extraction(
        self,
        archive_path: Path,
        destination_path: Path,
        extracted_files: int,
        extracted_bytes: int,
        success: bool = True,
        error_message: str | None = None,
    ) -> ExtractionRecord:
        """Add an extraction record and save history.

        Args:
            archive_path: Path to the archive that was extracted.
            destination_path: Path where files were extracted.
            extracted_files: Number of files extracted.
            extracted_bytes: Total bytes extracted.
            success: Whether extraction was successful.
            error_message: Error message if extraction failed.

        Returns:
            The created ExtractionRecord.
        """
        record = self.history.add_record(
            archive_path=archive_path,
            destination_path=destination_path,
            extracted_files=extracted_files,
            extracted_bytes=extracted_bytes,
            success=success,
            error_message=error_message,
        )
        self.history.save()
        return record

    def get_recent(self, count: int = 10) -> list[ExtractionRecord]:
        """Get recent extraction records.

        Args:
            count: Maximum number of records to return.

        Returns:
            List of recent ExtractionRecord entries.
        """
        return self.history.get_recent(count)

    def clear_history(self) -> None:
        """Clear all history and save."""
        self.history.clear()
        self.history.save()
