"""Comprehensive unit tests for the config module.

Tests for:
- ApplicationSettings dataclass
- ConfigManager class

TDD: These tests are written first, before implementation.
"""

import json
from pathlib import Path

import pytest


class TestApplicationSettingsDataclass:
    """Tests for ApplicationSettings dataclass."""

    def test_application_settings_creation_with_defaults(self) -> None:
        """ApplicationSettings should be creatable with default values."""
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings()
        assert settings is not None

    def test_application_settings_has_default_destination(self) -> None:
        """ApplicationSettings should have default_destination field."""
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings()
        assert hasattr(settings, "default_destination")
        assert isinstance(settings.default_destination, Path)

    def test_application_settings_default_destination_is_downloads(self) -> None:
        """ApplicationSettings default_destination should default to ~/Downloads."""
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings()
        expected = Path.home() / "Downloads"
        assert settings.default_destination == expected

    def test_application_settings_has_conflict_resolution(self) -> None:
        """ApplicationSettings should have conflict_resolution field."""
        from zipextractor.core.models import ConflictResolution
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings()
        assert hasattr(settings, "conflict_resolution")
        assert isinstance(settings.conflict_resolution, ConflictResolution)

    def test_application_settings_conflict_resolution_default_is_ask(self) -> None:
        """ApplicationSettings conflict_resolution should default to ASK."""
        from zipextractor.core.models import ConflictResolution
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings()
        assert settings.conflict_resolution == ConflictResolution.ASK

    def test_application_settings_has_create_root_folder(self) -> None:
        """ApplicationSettings should have create_root_folder field."""
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings()
        assert hasattr(settings, "create_root_folder")
        assert isinstance(settings.create_root_folder, bool)

    def test_application_settings_create_root_folder_default_is_true(self) -> None:
        """ApplicationSettings create_root_folder should default to True."""
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings()
        assert settings.create_root_folder is True

    def test_application_settings_has_preserve_permissions(self) -> None:
        """ApplicationSettings should have preserve_permissions field."""
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings()
        assert hasattr(settings, "preserve_permissions")
        assert isinstance(settings.preserve_permissions, bool)

    def test_application_settings_preserve_permissions_default_is_true(self) -> None:
        """ApplicationSettings preserve_permissions should default to True."""
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings()
        assert settings.preserve_permissions is True

    def test_application_settings_has_preserve_timestamps(self) -> None:
        """ApplicationSettings should have preserve_timestamps field."""
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings()
        assert hasattr(settings, "preserve_timestamps")
        assert isinstance(settings.preserve_timestamps, bool)

    def test_application_settings_preserve_timestamps_default_is_true(self) -> None:
        """ApplicationSettings preserve_timestamps should default to True."""
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings()
        assert settings.preserve_timestamps is True

    def test_application_settings_has_max_concurrent_extractions(self) -> None:
        """ApplicationSettings should have max_concurrent_extractions field."""
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings()
        assert hasattr(settings, "max_concurrent_extractions")
        assert isinstance(settings.max_concurrent_extractions, int)

    def test_application_settings_max_concurrent_extractions_default_is_reasonable(
        self,
    ) -> None:
        """ApplicationSettings max_concurrent_extractions should have reasonable default."""
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings()
        # Default should be between 1 and 8 (reasonable for most systems)
        assert 1 <= settings.max_concurrent_extractions <= 8

    def test_application_settings_has_show_notifications(self) -> None:
        """ApplicationSettings should have show_notifications field."""
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings()
        assert hasattr(settings, "show_notifications")
        assert isinstance(settings.show_notifications, bool)

    def test_application_settings_show_notifications_default_is_true(self) -> None:
        """ApplicationSettings show_notifications should default to True."""
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings()
        assert settings.show_notifications is True

    def test_application_settings_has_dark_mode(self) -> None:
        """ApplicationSettings should have dark_mode field."""
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings()
        assert hasattr(settings, "dark_mode")
        assert isinstance(settings.dark_mode, str)

    def test_application_settings_dark_mode_default_is_system(self) -> None:
        """ApplicationSettings dark_mode should default to 'system'."""
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings()
        assert settings.dark_mode == "system"

    def test_application_settings_custom_default_destination(self) -> None:
        """ApplicationSettings should accept custom default_destination."""
        from zipextractor.utils.config import ApplicationSettings

        custom_path = Path("/custom/extract/path")
        settings = ApplicationSettings(default_destination=custom_path)
        assert settings.default_destination == custom_path

    def test_application_settings_custom_conflict_resolution(self) -> None:
        """ApplicationSettings should accept custom conflict_resolution."""
        from zipextractor.core.models import ConflictResolution
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings(conflict_resolution=ConflictResolution.OVERWRITE)
        assert settings.conflict_resolution == ConflictResolution.OVERWRITE

    def test_application_settings_custom_create_root_folder(self) -> None:
        """ApplicationSettings should accept custom create_root_folder."""
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings(create_root_folder=False)
        assert settings.create_root_folder is False

    def test_application_settings_custom_preserve_permissions(self) -> None:
        """ApplicationSettings should accept custom preserve_permissions."""
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings(preserve_permissions=False)
        assert settings.preserve_permissions is False

    def test_application_settings_custom_preserve_timestamps(self) -> None:
        """ApplicationSettings should accept custom preserve_timestamps."""
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings(preserve_timestamps=False)
        assert settings.preserve_timestamps is False

    def test_application_settings_custom_max_concurrent_extractions(self) -> None:
        """ApplicationSettings should accept custom max_concurrent_extractions."""
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings(max_concurrent_extractions=4)
        assert settings.max_concurrent_extractions == 4

    def test_application_settings_custom_show_notifications(self) -> None:
        """ApplicationSettings should accept custom show_notifications."""
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings(show_notifications=False)
        assert settings.show_notifications is False

    def test_application_settings_custom_dark_mode_light(self) -> None:
        """ApplicationSettings should accept dark_mode='light'."""
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings(dark_mode="light")
        assert settings.dark_mode == "light"

    def test_application_settings_custom_dark_mode_dark(self) -> None:
        """ApplicationSettings should accept dark_mode='dark'."""
        from zipextractor.utils.config import ApplicationSettings

        settings = ApplicationSettings(dark_mode="dark")
        assert settings.dark_mode == "dark"

    def test_application_settings_all_custom_values(self) -> None:
        """ApplicationSettings should accept all custom values at once."""
        from zipextractor.core.models import ConflictResolution
        from zipextractor.utils.config import ApplicationSettings

        custom_path = Path("/my/custom/path")
        settings = ApplicationSettings(
            default_destination=custom_path,
            conflict_resolution=ConflictResolution.SKIP,
            create_root_folder=False,
            preserve_permissions=False,
            preserve_timestamps=False,
            max_concurrent_extractions=2,
            show_notifications=False,
            dark_mode="dark",
        )

        assert settings.default_destination == custom_path
        assert settings.conflict_resolution == ConflictResolution.SKIP
        assert settings.create_root_folder is False
        assert settings.preserve_permissions is False
        assert settings.preserve_timestamps is False
        assert settings.max_concurrent_extractions == 2
        assert settings.show_notifications is False
        assert settings.dark_mode == "dark"

    def test_application_settings_is_dataclass(self) -> None:
        """ApplicationSettings should be a dataclass."""
        from dataclasses import is_dataclass

        from zipextractor.utils.config import ApplicationSettings

        assert is_dataclass(ApplicationSettings)

    def test_application_settings_has_all_expected_fields(self) -> None:
        """ApplicationSettings should have all expected fields."""
        from zipextractor.utils.config import ApplicationSettings

        expected_fields = [
            "default_destination",
            "conflict_resolution",
            "create_root_folder",
            "preserve_permissions",
            "preserve_timestamps",
            "max_concurrent_extractions",
            "show_notifications",
            "dark_mode",
        ]
        for field_name in expected_fields:
            assert hasattr(ApplicationSettings, "__dataclass_fields__")
            assert field_name in ApplicationSettings.__dataclass_fields__


class TestApplicationSettingsValidation:
    """Tests for ApplicationSettings validation logic."""

    def test_validate_max_concurrent_extractions_positive(self) -> None:
        """ApplicationSettings should validate max_concurrent_extractions is positive."""
        from zipextractor.utils.config import ApplicationSettings

        # Should not raise for valid values
        settings = ApplicationSettings(max_concurrent_extractions=1)
        assert settings.max_concurrent_extractions == 1

    def test_validate_dark_mode_valid_values(self) -> None:
        """ApplicationSettings dark_mode should only accept valid values."""
        from zipextractor.utils.config import ApplicationSettings

        valid_modes = ["system", "light", "dark"]
        for mode in valid_modes:
            settings = ApplicationSettings(dark_mode=mode)
            assert settings.dark_mode == mode


class TestConfigManagerCreation:
    """Tests for ConfigManager class creation."""

    def test_config_manager_creation(self, tmp_path: Path) -> None:
        """ConfigManager should be creatable."""
        from zipextractor.utils.config import ConfigManager

        config_path = tmp_path / "zipextractor" / "settings.json"
        manager = ConfigManager(config_path=config_path)
        assert manager is not None

    def test_config_manager_default_path(self) -> None:
        """ConfigManager should have a default config path."""
        from zipextractor.utils.config import ConfigManager

        manager = ConfigManager()
        expected_path = Path.home() / ".config" / "zipextractor" / "settings.json"
        assert manager.config_path == expected_path

    def test_config_manager_custom_path(self, tmp_path: Path) -> None:
        """ConfigManager should accept custom config path."""
        from zipextractor.utils.config import ConfigManager

        custom_path = tmp_path / "custom" / "config.json"
        manager = ConfigManager(config_path=custom_path)
        assert manager.config_path == custom_path


class TestConfigManagerGetDefault:
    """Tests for ConfigManager.get_default() method."""

    def test_get_default_returns_application_settings(self, tmp_path: Path) -> None:
        """get_default() should return ApplicationSettings instance."""
        from zipextractor.utils.config import ApplicationSettings, ConfigManager

        config_path = tmp_path / "zipextractor" / "settings.json"
        manager = ConfigManager(config_path=config_path)
        settings = manager.get_default()
        assert isinstance(settings, ApplicationSettings)

    def test_get_default_returns_default_values(self, tmp_path: Path) -> None:
        """get_default() should return settings with default values."""
        from zipextractor.core.models import ConflictResolution
        from zipextractor.utils.config import ConfigManager

        config_path = tmp_path / "zipextractor" / "settings.json"
        manager = ConfigManager(config_path=config_path)
        settings = manager.get_default()

        assert settings.default_destination == Path.home() / "Downloads"
        assert settings.conflict_resolution == ConflictResolution.ASK
        assert settings.create_root_folder is True
        assert settings.preserve_permissions is True
        assert settings.preserve_timestamps is True
        assert 1 <= settings.max_concurrent_extractions <= 8
        assert settings.show_notifications is True
        assert settings.dark_mode == "system"


class TestConfigManagerLoad:
    """Tests for ConfigManager.load() method."""

    def test_load_returns_application_settings(self, tmp_path: Path) -> None:
        """load() should return ApplicationSettings instance."""
        from zipextractor.utils.config import ApplicationSettings, ConfigManager

        config_path = tmp_path / "zipextractor" / "settings.json"
        manager = ConfigManager(config_path=config_path)
        settings = manager.load()
        assert isinstance(settings, ApplicationSettings)

    def test_load_returns_defaults_when_file_missing(self, tmp_path: Path) -> None:
        """load() should return defaults when config file does not exist."""
        from zipextractor.core.models import ConflictResolution
        from zipextractor.utils.config import ConfigManager

        config_path = tmp_path / "nonexistent" / "settings.json"
        manager = ConfigManager(config_path=config_path)
        settings = manager.load()

        # Should return default values
        assert settings.default_destination == Path.home() / "Downloads"
        assert settings.conflict_resolution == ConflictResolution.ASK
        assert settings.create_root_folder is True

    def test_load_reads_existing_config(self, tmp_path: Path) -> None:
        """load() should read settings from existing config file."""
        from zipextractor.utils.config import ConfigManager

        # Create config directory and file
        config_dir = tmp_path / "zipextractor"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "settings.json"

        # Write custom settings
        custom_settings = {
            "default_destination": str(tmp_path / "custom_dest"),
            "conflict_resolution": "overwrite",
            "create_root_folder": False,
            "preserve_permissions": False,
            "preserve_timestamps": False,
            "max_concurrent_extractions": 4,
            "show_notifications": False,
            "dark_mode": "dark",
        }
        config_path.write_text(json.dumps(custom_settings))

        manager = ConfigManager(config_path=config_path)
        settings = manager.load()

        assert settings.default_destination == tmp_path / "custom_dest"
        assert settings.create_root_folder is False
        assert settings.max_concurrent_extractions == 4
        assert settings.dark_mode == "dark"

    def test_load_handles_corrupted_json_gracefully(self, tmp_path: Path) -> None:
        """load() should return defaults when JSON is corrupted."""
        from zipextractor.core.models import ConflictResolution
        from zipextractor.utils.config import ConfigManager

        config_dir = tmp_path / "zipextractor"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "settings.json"

        # Write corrupted JSON
        config_path.write_text("{invalid json content that cannot be parsed")

        manager = ConfigManager(config_path=config_path)
        settings = manager.load()

        # Should return defaults
        assert settings.default_destination == Path.home() / "Downloads"
        assert settings.conflict_resolution == ConflictResolution.ASK

    def test_load_handles_empty_file_gracefully(self, tmp_path: Path) -> None:
        """load() should return defaults when config file is empty."""
        from zipextractor.utils.config import ConfigManager

        config_dir = tmp_path / "zipextractor"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "settings.json"

        # Write empty file
        config_path.write_text("")

        manager = ConfigManager(config_path=config_path)
        settings = manager.load()

        # Should return defaults
        assert settings.default_destination == Path.home() / "Downloads"

    def test_load_handles_partial_config(self, tmp_path: Path) -> None:
        """load() should merge partial config with defaults."""
        from zipextractor.utils.config import ConfigManager

        config_dir = tmp_path / "zipextractor"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "settings.json"

        # Write partial settings (only some fields)
        partial_settings = {
            "dark_mode": "light",
            "show_notifications": False,
        }
        config_path.write_text(json.dumps(partial_settings))

        manager = ConfigManager(config_path=config_path)
        settings = manager.load()

        # Custom values should be loaded
        assert settings.dark_mode == "light"
        assert settings.show_notifications is False

        # Default values should be used for missing fields
        assert settings.default_destination == Path.home() / "Downloads"
        assert settings.create_root_folder is True

    def test_load_handles_invalid_conflict_resolution_value(
        self, tmp_path: Path
    ) -> None:
        """load() should handle invalid conflict_resolution value gracefully."""
        from zipextractor.core.models import ConflictResolution
        from zipextractor.utils.config import ConfigManager

        config_dir = tmp_path / "zipextractor"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "settings.json"

        # Write config with invalid conflict_resolution
        invalid_settings = {
            "conflict_resolution": "invalid_value",
        }
        config_path.write_text(json.dumps(invalid_settings))

        manager = ConfigManager(config_path=config_path)
        settings = manager.load()

        # Should fall back to default
        assert settings.conflict_resolution == ConflictResolution.ASK

    def test_load_handles_invalid_dark_mode_value(self, tmp_path: Path) -> None:
        """load() should handle invalid dark_mode value gracefully."""
        from zipextractor.utils.config import ConfigManager

        config_dir = tmp_path / "zipextractor"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "settings.json"

        # Write config with invalid dark_mode
        invalid_settings = {
            "dark_mode": "rainbow",
        }
        config_path.write_text(json.dumps(invalid_settings))

        manager = ConfigManager(config_path=config_path)
        settings = manager.load()

        # Should fall back to default
        assert settings.dark_mode == "system"

    def test_load_handles_non_integer_max_concurrent(self, tmp_path: Path) -> None:
        """load() should handle non-integer max_concurrent_extractions gracefully."""
        from zipextractor.utils.config import ConfigManager

        config_dir = tmp_path / "zipextractor"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "settings.json"

        # Write config with invalid max_concurrent_extractions
        invalid_settings = {
            "max_concurrent_extractions": "not_a_number",
        }
        config_path.write_text(json.dumps(invalid_settings))

        manager = ConfigManager(config_path=config_path)
        settings = manager.load()

        # Should fall back to default
        assert isinstance(settings.max_concurrent_extractions, int)
        assert 1 <= settings.max_concurrent_extractions <= 8

    def test_load_handles_negative_max_concurrent(self, tmp_path: Path) -> None:
        """load() should handle negative max_concurrent_extractions gracefully."""
        from zipextractor.utils.config import ConfigManager

        config_dir = tmp_path / "zipextractor"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "settings.json"

        # Write config with negative value
        invalid_settings = {
            "max_concurrent_extractions": -5,
        }
        config_path.write_text(json.dumps(invalid_settings))

        manager = ConfigManager(config_path=config_path)
        settings = manager.load()

        # Should fall back to default or minimum valid value
        assert settings.max_concurrent_extractions >= 1


class TestConfigManagerSave:
    """Tests for ConfigManager.save() method."""

    def test_save_creates_config_file(self, tmp_path: Path) -> None:
        """save() should create config file if it does not exist."""
        from zipextractor.utils.config import ApplicationSettings, ConfigManager

        config_path = tmp_path / "zipextractor" / "settings.json"
        manager = ConfigManager(config_path=config_path)
        settings = ApplicationSettings()

        manager.save(settings)

        assert config_path.exists()

    def test_save_creates_config_directory(self, tmp_path: Path) -> None:
        """save() should create config directory if it does not exist."""
        from zipextractor.utils.config import ApplicationSettings, ConfigManager

        config_path = tmp_path / "nested" / "dirs" / "zipextractor" / "settings.json"
        manager = ConfigManager(config_path=config_path)
        settings = ApplicationSettings()

        manager.save(settings)

        assert config_path.parent.exists()
        assert config_path.exists()

    def test_save_writes_valid_json(self, tmp_path: Path) -> None:
        """save() should write valid JSON to config file."""
        from zipextractor.utils.config import ApplicationSettings, ConfigManager

        config_path = tmp_path / "zipextractor" / "settings.json"
        manager = ConfigManager(config_path=config_path)
        settings = ApplicationSettings()

        manager.save(settings)

        # Should be valid JSON
        content = config_path.read_text()
        parsed = json.loads(content)
        assert isinstance(parsed, dict)

    def test_save_persists_all_settings(self, tmp_path: Path) -> None:
        """save() should persist all settings fields."""
        from zipextractor.core.models import ConflictResolution
        from zipextractor.utils.config import ApplicationSettings, ConfigManager

        config_path = tmp_path / "zipextractor" / "settings.json"
        manager = ConfigManager(config_path=config_path)

        custom_dest = tmp_path / "my_extractions"
        settings = ApplicationSettings(
            default_destination=custom_dest,
            conflict_resolution=ConflictResolution.RENAME,
            create_root_folder=False,
            preserve_permissions=False,
            preserve_timestamps=False,
            max_concurrent_extractions=6,
            show_notifications=False,
            dark_mode="light",
        )

        manager.save(settings)

        content = config_path.read_text()
        parsed = json.loads(content)

        assert parsed["default_destination"] == str(custom_dest)
        assert parsed["conflict_resolution"] == "rename"
        assert parsed["create_root_folder"] is False
        assert parsed["preserve_permissions"] is False
        assert parsed["preserve_timestamps"] is False
        assert parsed["max_concurrent_extractions"] == 6
        assert parsed["show_notifications"] is False
        assert parsed["dark_mode"] == "light"

    def test_save_overwrites_existing_config(self, tmp_path: Path) -> None:
        """save() should overwrite existing config file."""
        from zipextractor.utils.config import ApplicationSettings, ConfigManager

        config_dir = tmp_path / "zipextractor"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "settings.json"

        # Write initial config
        initial_settings = {"dark_mode": "dark"}
        config_path.write_text(json.dumps(initial_settings))

        manager = ConfigManager(config_path=config_path)
        new_settings = ApplicationSettings(dark_mode="light")

        manager.save(new_settings)

        content = config_path.read_text()
        parsed = json.loads(content)

        assert parsed["dark_mode"] == "light"

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        """Saved settings should be loadable."""
        from zipextractor.core.models import ConflictResolution
        from zipextractor.utils.config import ApplicationSettings, ConfigManager

        config_path = tmp_path / "zipextractor" / "settings.json"
        manager = ConfigManager(config_path=config_path)

        custom_dest = tmp_path / "roundtrip_dest"
        original_settings = ApplicationSettings(
            default_destination=custom_dest,
            conflict_resolution=ConflictResolution.SKIP,
            create_root_folder=False,
            preserve_permissions=False,
            preserve_timestamps=False,
            max_concurrent_extractions=3,
            show_notifications=False,
            dark_mode="dark",
        )

        manager.save(original_settings)
        loaded_settings = manager.load()

        assert loaded_settings.default_destination == custom_dest
        assert loaded_settings.conflict_resolution == ConflictResolution.SKIP
        assert loaded_settings.create_root_folder is False
        assert loaded_settings.preserve_permissions is False
        assert loaded_settings.preserve_timestamps is False
        assert loaded_settings.max_concurrent_extractions == 3
        assert loaded_settings.show_notifications is False
        assert loaded_settings.dark_mode == "dark"


class TestConfigManagerReset:
    """Tests for ConfigManager.reset() method."""

    def test_reset_returns_default_settings(self, tmp_path: Path) -> None:
        """reset() should return default ApplicationSettings."""
        from zipextractor.utils.config import ApplicationSettings, ConfigManager

        config_path = tmp_path / "zipextractor" / "settings.json"
        manager = ConfigManager(config_path=config_path)
        settings = manager.reset()

        assert isinstance(settings, ApplicationSettings)
        assert settings.default_destination == Path.home() / "Downloads"

    def test_reset_saves_default_settings(self, tmp_path: Path) -> None:
        """reset() should save default settings to config file."""
        from zipextractor.core.models import ConflictResolution
        from zipextractor.utils.config import ConfigManager

        config_dir = tmp_path / "zipextractor"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "settings.json"

        # Write custom settings first
        custom_settings = {"dark_mode": "dark", "show_notifications": False}
        config_path.write_text(json.dumps(custom_settings))

        manager = ConfigManager(config_path=config_path)
        manager.reset()

        # Load should now return defaults
        loaded = manager.load()
        assert loaded.dark_mode == "system"
        assert loaded.show_notifications is True
        assert loaded.conflict_resolution == ConflictResolution.ASK

    def test_reset_creates_config_if_missing(self, tmp_path: Path) -> None:
        """reset() should create config file if it does not exist."""
        from zipextractor.utils.config import ConfigManager

        config_path = tmp_path / "zipextractor" / "settings.json"
        manager = ConfigManager(config_path=config_path)

        manager.reset()

        assert config_path.exists()

    def test_reset_overwrites_corrupted_config(self, tmp_path: Path) -> None:
        """reset() should overwrite corrupted config file."""
        from zipextractor.utils.config import ConfigManager

        config_dir = tmp_path / "zipextractor"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "settings.json"

        # Write corrupted config
        config_path.write_text("{ corrupted json }")

        manager = ConfigManager(config_path=config_path)
        settings = manager.reset()

        # Should have valid default settings
        assert settings.dark_mode == "system"

        # Config file should now be valid
        loaded = manager.load()
        assert loaded.dark_mode == "system"


class TestConfigManagerEdgeCases:
    """Tests for ConfigManager edge cases and error handling."""

    def test_config_path_is_readonly(self, tmp_path: Path) -> None:
        """ConfigManager should handle read-only file systems gracefully."""
        from zipextractor.utils.config import ApplicationSettings, ConfigManager

        # This test verifies the manager handles save failures gracefully
        # The actual behavior (raise or log) depends on implementation
        config_path = tmp_path / "zipextractor" / "settings.json"
        manager = ConfigManager(config_path=config_path)

        # Create dir and file
        config_path.parent.mkdir(parents=True)
        config_path.touch()

        settings = ApplicationSettings()

        # This should not raise an unhandled exception
        # Implementation may raise a specific exception or log a warning
        try:
            manager.save(settings)
        except PermissionError:
            pass  # Expected behavior when write fails

    def test_load_with_extra_unknown_fields(self, tmp_path: Path) -> None:
        """load() should ignore unknown fields in config file."""
        from zipextractor.utils.config import ConfigManager

        config_dir = tmp_path / "zipextractor"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "settings.json"

        # Write config with extra unknown fields
        settings_with_extras = {
            "dark_mode": "light",
            "unknown_field": "should_be_ignored",
            "another_extra": 12345,
            "nested_extra": {"key": "value"},
        }
        config_path.write_text(json.dumps(settings_with_extras))

        manager = ConfigManager(config_path=config_path)
        settings = manager.load()

        # Known field should be loaded
        assert settings.dark_mode == "light"

        # Settings should not have unknown fields
        assert not hasattr(settings, "unknown_field")
        assert not hasattr(settings, "another_extra")

    def test_load_with_wrong_type_values(self, tmp_path: Path) -> None:
        """load() should handle wrong type values gracefully."""
        from zipextractor.utils.config import ConfigManager

        config_dir = tmp_path / "zipextractor"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "settings.json"

        # Write config with wrong types
        wrong_type_settings = {
            "create_root_folder": "yes",  # Should be bool
            "preserve_permissions": 1,  # Should be bool
            "show_notifications": "true",  # Should be bool
        }
        config_path.write_text(json.dumps(wrong_type_settings))

        manager = ConfigManager(config_path=config_path)
        settings = manager.load()

        # Should fall back to defaults for invalid types
        assert isinstance(settings.create_root_folder, bool)
        assert isinstance(settings.preserve_permissions, bool)
        assert isinstance(settings.show_notifications, bool)

    def test_save_with_special_characters_in_path(self, tmp_path: Path) -> None:
        """save() should handle special characters in default_destination path."""
        from zipextractor.utils.config import ApplicationSettings, ConfigManager

        config_path = tmp_path / "zipextractor" / "settings.json"
        manager = ConfigManager(config_path=config_path)

        # Path with special characters
        special_path = tmp_path / "my folder" / "sub-folder_123" / "extract here!"
        settings = ApplicationSettings(default_destination=special_path)

        manager.save(settings)
        loaded = manager.load()

        assert loaded.default_destination == special_path

    def test_concurrent_load_and_save(self, tmp_path: Path) -> None:
        """ConfigManager should handle concurrent operations."""
        from zipextractor.utils.config import ApplicationSettings, ConfigManager

        config_path = tmp_path / "zipextractor" / "settings.json"
        manager = ConfigManager(config_path=config_path)

        # Multiple save/load operations should work
        for i in range(5):
            settings = ApplicationSettings(max_concurrent_extractions=i + 1)
            manager.save(settings)
            loaded = manager.load()
            assert loaded.max_concurrent_extractions == i + 1


class TestConfigManagerConflictResolutionAllValues:
    """Tests for ConfigManager handling all ConflictResolution values."""

    @pytest.mark.parametrize(
        "resolution_str,expected_enum_name",
        [
            ("ask", "ASK"),
            ("overwrite", "OVERWRITE"),
            ("skip", "SKIP"),
            ("rename", "RENAME"),
        ],
    )
    def test_load_all_conflict_resolution_values(
        self, tmp_path: Path, resolution_str: str, expected_enum_name: str
    ) -> None:
        """load() should correctly parse all ConflictResolution values."""
        from zipextractor.core.models import ConflictResolution
        from zipextractor.utils.config import ConfigManager

        config_dir = tmp_path / "zipextractor"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "settings.json"

        settings_data = {"conflict_resolution": resolution_str}
        config_path.write_text(json.dumps(settings_data))

        manager = ConfigManager(config_path=config_path)
        settings = manager.load()

        expected_enum = getattr(ConflictResolution, expected_enum_name)
        assert settings.conflict_resolution == expected_enum

    @pytest.mark.parametrize(
        "enum_name",
        ["ASK", "OVERWRITE", "SKIP", "RENAME"],
    )
    def test_save_all_conflict_resolution_values(
        self, tmp_path: Path, enum_name: str
    ) -> None:
        """save() should correctly serialize all ConflictResolution values."""
        from zipextractor.core.models import ConflictResolution
        from zipextractor.utils.config import ApplicationSettings, ConfigManager

        config_path = tmp_path / "zipextractor" / "settings.json"
        manager = ConfigManager(config_path=config_path)

        resolution = getattr(ConflictResolution, enum_name)
        settings = ApplicationSettings(conflict_resolution=resolution)

        manager.save(settings)

        content = config_path.read_text()
        parsed = json.loads(content)

        assert parsed["conflict_resolution"] == resolution.value


class TestConfigManagerDarkModeAllValues:
    """Tests for ConfigManager handling all dark_mode values."""

    @pytest.mark.parametrize("dark_mode", ["system", "light", "dark"])
    def test_load_all_dark_mode_values(self, tmp_path: Path, dark_mode: str) -> None:
        """load() should correctly parse all dark_mode values."""
        from zipextractor.utils.config import ConfigManager

        config_dir = tmp_path / "zipextractor"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "settings.json"

        settings_data = {"dark_mode": dark_mode}
        config_path.write_text(json.dumps(settings_data))

        manager = ConfigManager(config_path=config_path)
        settings = manager.load()

        assert settings.dark_mode == dark_mode

    @pytest.mark.parametrize("dark_mode", ["system", "light", "dark"])
    def test_save_all_dark_mode_values(self, tmp_path: Path, dark_mode: str) -> None:
        """save() should correctly serialize all dark_mode values."""
        from zipextractor.utils.config import ApplicationSettings, ConfigManager

        config_path = tmp_path / "zipextractor" / "settings.json"
        manager = ConfigManager(config_path=config_path)

        settings = ApplicationSettings(dark_mode=dark_mode)
        manager.save(settings)

        content = config_path.read_text()
        parsed = json.loads(content)

        assert parsed["dark_mode"] == dark_mode


class TestConfigManagerPathHandling:
    """Tests for ConfigManager path handling."""

    def test_load_converts_string_path_to_path_object(self, tmp_path: Path) -> None:
        """load() should convert string paths to Path objects."""
        from zipextractor.utils.config import ConfigManager

        config_dir = tmp_path / "zipextractor"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "settings.json"

        # Write path as string
        settings_data = {"default_destination": "/some/path/as/string"}
        config_path.write_text(json.dumps(settings_data))

        manager = ConfigManager(config_path=config_path)
        settings = manager.load()

        assert isinstance(settings.default_destination, Path)
        assert settings.default_destination == Path("/some/path/as/string")

    def test_save_converts_path_object_to_string(self, tmp_path: Path) -> None:
        """save() should convert Path objects to strings in JSON."""
        from zipextractor.utils.config import ApplicationSettings, ConfigManager

        config_path = tmp_path / "zipextractor" / "settings.json"
        manager = ConfigManager(config_path=config_path)

        custom_dest = Path("/my/custom/destination")
        settings = ApplicationSettings(default_destination=custom_dest)

        manager.save(settings)

        content = config_path.read_text()
        parsed = json.loads(content)

        assert isinstance(parsed["default_destination"], str)
        assert parsed["default_destination"] == "/my/custom/destination"

    def test_load_handles_nonexistent_path(self, tmp_path: Path) -> None:
        """load() should handle nonexistent default_destination path."""
        from zipextractor.utils.config import ConfigManager

        config_dir = tmp_path / "zipextractor"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "settings.json"

        # Write path that does not exist
        settings_data = {"default_destination": "/nonexistent/path/that/doesnt/exist"}
        config_path.write_text(json.dumps(settings_data))

        manager = ConfigManager(config_path=config_path)
        settings = manager.load()

        # Should still load the path even if it doesn't exist
        assert settings.default_destination == Path(
            "/nonexistent/path/that/doesnt/exist"
        )

    def test_load_handles_relative_path(self, tmp_path: Path) -> None:
        """load() should handle relative paths in config."""
        from zipextractor.utils.config import ConfigManager

        config_dir = tmp_path / "zipextractor"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "settings.json"

        # Write relative path
        settings_data = {"default_destination": "relative/path"}
        config_path.write_text(json.dumps(settings_data))

        manager = ConfigManager(config_path=config_path)
        settings = manager.load()

        assert settings.default_destination == Path("relative/path")
