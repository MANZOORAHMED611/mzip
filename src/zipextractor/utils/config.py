"""Configuration management for ZIP Extractor.

This module provides configuration management functionality including
application settings persistence and loading.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from zipextractor.core.models import ConflictResolution

logger = logging.getLogger(__name__)


@dataclass
class ApplicationSettings:
    """Application-wide settings for ZIP Extractor.

    Attributes:
        default_destination: Default directory for extracted files.
        conflict_resolution: How to handle file conflicts during extraction.
        create_root_folder: Whether to create a root folder for extracted contents.
        preserve_permissions: Whether to preserve file permissions during extraction.
        preserve_timestamps: Whether to preserve file timestamps during extraction.
        max_concurrent_extractions: Maximum number of concurrent extraction tasks.
        show_notifications: Whether to show desktop notifications.
        dark_mode: Theme preference - "system", "light", or "dark".
    """

    default_destination: Path = field(default_factory=lambda: Path.home() / "Downloads")
    conflict_resolution: ConflictResolution = ConflictResolution.ASK
    create_root_folder: bool = True
    preserve_permissions: bool = True
    preserve_timestamps: bool = True
    max_concurrent_extractions: int = 4
    show_notifications: bool = True
    dark_mode: str = "system"


class ConfigManager:
    """Manages application configuration persistence.

    Handles loading, saving, and resetting application settings to/from
    a JSON configuration file.

    Attributes:
        CONFIG_DIR: Default configuration directory path.
        CONFIG_FILE: Configuration file name.
    """

    CONFIG_DIR: Path = Path.home() / ".config" / "zipextractor"
    CONFIG_FILE: str = "settings.json"

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize ConfigManager with optional custom config file path.

        Args:
            config_path: Optional custom configuration file path.
                        Uses default CONFIG_DIR/CONFIG_FILE if not specified.
        """
        if config_path is not None:
            self._config_file = config_path
            self._config_dir = config_path.parent
        else:
            self._config_dir = self.CONFIG_DIR
            self._config_file = self._config_dir / self.CONFIG_FILE

    @property
    def config_dir(self) -> Path:
        """Get the configuration directory path."""
        return self._config_dir

    @property
    def config_file(self) -> Path:
        """Get the configuration file path."""
        return self._config_file

    @property
    def config_path(self) -> Path:
        """Get the configuration file path (alias for config_file)."""
        return self._config_file

    def get_default(self) -> ApplicationSettings:
        """Get default application settings.

        Returns:
            ApplicationSettings with all default values.
        """
        return ApplicationSettings()

    def load(self) -> ApplicationSettings:
        """Load application settings from the configuration file.

        Returns:
            ApplicationSettings loaded from file, or defaults if file
            doesn't exist or is corrupted.
        """
        if not self._config_file.exists():
            logger.debug("Config file does not exist, returning defaults")
            return self.get_default()

        try:
            with self._config_file.open("r", encoding="utf-8") as f:
                data = json.load(f)

            return self._deserialize(data)

        except json.JSONDecodeError as e:
            logger.warning("Config file is corrupted, returning defaults: %s", e)
            return self.get_default()
        except OSError as e:
            logger.warning("Failed to read config file, returning defaults: %s", e)
            return self.get_default()
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("Invalid config data, returning defaults: %s", e)
            return self.get_default()

    def save(self, settings: ApplicationSettings) -> None:
        """Save application settings to the configuration file.

        Creates the configuration directory if it doesn't exist.

        Args:
            settings: ApplicationSettings to save.

        Raises:
            OSError: If the configuration file cannot be written.
        """
        self._ensure_config_dir_exists()

        data = self._serialize(settings)

        with self._config_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.debug("Settings saved to %s", self._config_file)

    def reset(self) -> ApplicationSettings:
        """Reset settings to defaults and save.

        Returns:
            The default ApplicationSettings after saving.
        """
        settings = self.get_default()
        self.save(settings)
        logger.info("Settings reset to defaults")
        return settings

    def _ensure_config_dir_exists(self) -> None:
        """Create the configuration directory if it doesn't exist."""
        if not self._config_dir.exists():
            self._config_dir.mkdir(parents=True, exist_ok=True)
            logger.debug("Created config directory: %s", self._config_dir)

    def _serialize(self, settings: ApplicationSettings) -> dict[str, Any]:
        """Serialize ApplicationSettings to a JSON-compatible dictionary.

        Args:
            settings: ApplicationSettings to serialize.

        Returns:
            Dictionary with JSON-serializable values.
        """
        data = asdict(settings)

        # Convert Path to string
        data["default_destination"] = str(settings.default_destination)

        # Convert Enum to string value
        data["conflict_resolution"] = settings.conflict_resolution.value

        return data

    def _deserialize(self, data: dict[str, Any]) -> ApplicationSettings:
        """Deserialize a dictionary to ApplicationSettings.

        Args:
            data: Dictionary loaded from JSON.

        Returns:
            ApplicationSettings instance.
        """
        defaults = self.get_default()

        # Parse Path
        default_destination = data.get("default_destination")
        if default_destination is not None:
            default_destination = Path(default_destination)
        else:
            default_destination = defaults.default_destination

        # Parse Enum
        conflict_resolution_value = data.get("conflict_resolution")
        if conflict_resolution_value is not None:
            try:
                conflict_resolution = ConflictResolution(conflict_resolution_value)
            except ValueError:
                logger.warning(
                    "Invalid conflict_resolution value '%s', using default",
                    conflict_resolution_value,
                )
                conflict_resolution = defaults.conflict_resolution
        else:
            conflict_resolution = defaults.conflict_resolution

        # Validate and parse boolean fields
        create_root_folder = data.get("create_root_folder", defaults.create_root_folder)
        if not isinstance(create_root_folder, bool):
            create_root_folder = defaults.create_root_folder

        preserve_permissions = data.get("preserve_permissions", defaults.preserve_permissions)
        if not isinstance(preserve_permissions, bool):
            preserve_permissions = defaults.preserve_permissions

        preserve_timestamps = data.get("preserve_timestamps", defaults.preserve_timestamps)
        if not isinstance(preserve_timestamps, bool):
            preserve_timestamps = defaults.preserve_timestamps

        show_notifications = data.get("show_notifications", defaults.show_notifications)
        if not isinstance(show_notifications, bool):
            show_notifications = defaults.show_notifications

        # Validate max_concurrent_extractions
        max_concurrent = data.get("max_concurrent_extractions", defaults.max_concurrent_extractions)
        if not isinstance(max_concurrent, int) or max_concurrent < 1:
            max_concurrent = defaults.max_concurrent_extractions

        # Validate dark_mode
        dark_mode = data.get("dark_mode", defaults.dark_mode)
        if dark_mode not in ("system", "light", "dark"):
            dark_mode = defaults.dark_mode

        return ApplicationSettings(
            default_destination=default_destination,
            conflict_resolution=conflict_resolution,
            create_root_folder=create_root_folder,
            preserve_permissions=preserve_permissions,
            preserve_timestamps=preserve_timestamps,
            max_concurrent_extractions=max_concurrent,
            show_notifications=show_notifications,
            dark_mode=dark_mode,
        )
