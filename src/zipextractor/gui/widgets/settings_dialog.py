"""Settings dialog for application preferences.

This module provides a preferences window using libadwaita's
PreferencesWindow pattern with organized settings pages.
"""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GObject, Gtk

from zipextractor.core.models import ConflictResolution
from zipextractor.utils.config import ApplicationSettings, ConfigManager
from zipextractor.utils.logging import get_logger

logger = get_logger(__name__)


class SettingsDialog(Adw.PreferencesWindow):
    """Preferences window for application settings.

    This dialog provides organized settings pages for:
    - General settings (destination, notifications)
    - Extraction settings (conflicts, permissions, etc.)
    - Appearance settings (theme)

    Signals:
        settings-changed: Emitted when settings are modified and saved.
            Args: (settings: ApplicationSettings)

    Example:
        >>> dialog = SettingsDialog(parent=main_window, config_manager=config)
        >>> dialog.connect("settings-changed", on_settings_changed)
        >>> dialog.present()
    """

    __gtype_name__ = "SettingsDialog"

    __gsignals__ = {
        "settings-changed": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
    }

    def __init__(
        self,
        parent: Gtk.Window,
        config_manager: ConfigManager,
    ) -> None:
        """Initialize the settings dialog.

        Args:
            parent: Parent window for modal behavior.
            config_manager: Configuration manager for loading/saving settings.
        """
        super().__init__(
            title="Preferences",
            transient_for=parent,
            modal=True,
            search_enabled=False,
        )

        self._config_manager = config_manager
        self._settings = config_manager.load()
        self._modified = False

        self._build_ui()

        # Connect close handler to save settings
        self.connect("close-request", self._on_close_request)

        logger.debug("Settings dialog created")

    def _build_ui(self) -> None:
        """Build the settings UI."""
        # General page
        general_page = self._build_general_page()
        self.add(general_page)

        # Extraction page
        extraction_page = self._build_extraction_page()
        self.add(extraction_page)

        # Appearance page
        appearance_page = self._build_appearance_page()
        self.add(appearance_page)

    def _build_general_page(self) -> Adw.PreferencesPage:
        """Build the general settings page."""
        page = Adw.PreferencesPage(
            title="General",
            icon_name="preferences-system-symbolic",
        )

        # Destination group
        dest_group = Adw.PreferencesGroup(
            title="Default Destination",
            description="Where extracted files are saved by default",
        )

        # Destination folder row
        self._dest_row = Adw.ActionRow(
            title="Destination Folder",
            subtitle=str(self._settings.default_destination),
        )

        dest_button = Gtk.Button(
            icon_name="folder-open-symbolic",
            valign=Gtk.Align.CENTER,
            css_classes=["flat"],
        )
        dest_button.connect("clicked", self._on_dest_button_clicked)
        self._dest_row.add_suffix(dest_button)
        self._dest_row.set_activatable_widget(dest_button)

        dest_group.add(self._dest_row)
        page.add(dest_group)

        # Notifications group
        notif_group = Adw.PreferencesGroup(
            title="Notifications",
        )

        # Use ActionRow + Switch for libadwaita 1.1 compatibility
        notif_row = Adw.ActionRow(
            title="Show Notifications",
            subtitle="Display desktop notification when extraction completes",
        )
        self._notif_switch = Gtk.Switch(
            active=self._settings.show_notifications,
            valign=Gtk.Align.CENTER,
        )
        self._notif_switch.connect("notify::active", self._on_setting_changed)
        notif_row.add_suffix(self._notif_switch)
        notif_row.set_activatable_widget(self._notif_switch)

        notif_group.add(notif_row)
        page.add(notif_group)

        return page

    def _build_extraction_page(self) -> Adw.PreferencesPage:
        """Build the extraction settings page."""
        page = Adw.PreferencesPage(
            title="Extraction",
            icon_name="archive-extract-symbolic",
        )

        # Conflict resolution group
        conflict_group = Adw.PreferencesGroup(
            title="File Conflicts",
            description="How to handle files that already exist",
        )

        # Conflict resolution combo
        self._conflict_combo = Adw.ComboRow(
            title="When files exist",
        )

        # Create string list model for combo
        conflict_options = Gtk.StringList()
        conflict_options.append("Ask me what to do")
        conflict_options.append("Overwrite existing files")
        conflict_options.append("Skip existing files")
        conflict_options.append("Rename new files")

        self._conflict_combo.set_model(conflict_options)

        # Set current selection
        conflict_map = {
            ConflictResolution.ASK: 0,
            ConflictResolution.OVERWRITE: 1,
            ConflictResolution.SKIP: 2,
            ConflictResolution.RENAME: 3,
        }
        self._conflict_combo.set_selected(
            conflict_map.get(self._settings.conflict_resolution, 0)
        )
        self._conflict_combo.connect("notify::selected", self._on_setting_changed)

        conflict_group.add(self._conflict_combo)
        page.add(conflict_group)

        # Extraction options group
        options_group = Adw.PreferencesGroup(
            title="Extraction Options",
        )

        # Create root folder - use ActionRow + Switch for libadwaita 1.1
        root_folder_row = Adw.ActionRow(
            title="Create Root Folder",
            subtitle="Extract into a folder named after the archive",
        )
        self._root_folder_switch = Gtk.Switch(
            active=self._settings.create_root_folder,
            valign=Gtk.Align.CENTER,
        )
        self._root_folder_switch.connect("notify::active", self._on_setting_changed)
        root_folder_row.add_suffix(self._root_folder_switch)
        root_folder_row.set_activatable_widget(self._root_folder_switch)
        options_group.add(root_folder_row)

        # Preserve timestamps
        timestamps_row = Adw.ActionRow(
            title="Preserve Timestamps",
            subtitle="Keep original file modification dates",
        )
        self._timestamps_switch = Gtk.Switch(
            active=self._settings.preserve_timestamps,
            valign=Gtk.Align.CENTER,
        )
        self._timestamps_switch.connect("notify::active", self._on_setting_changed)
        timestamps_row.add_suffix(self._timestamps_switch)
        timestamps_row.set_activatable_widget(self._timestamps_switch)
        options_group.add(timestamps_row)

        # Preserve permissions
        permissions_row = Adw.ActionRow(
            title="Preserve Permissions",
            subtitle="Keep original file permissions (Unix only)",
        )
        self._permissions_switch = Gtk.Switch(
            active=self._settings.preserve_permissions,
            valign=Gtk.Align.CENTER,
        )
        self._permissions_switch.connect("notify::active", self._on_setting_changed)
        permissions_row.add_suffix(self._permissions_switch)
        permissions_row.set_activatable_widget(self._permissions_switch)
        options_group.add(permissions_row)

        page.add(options_group)

        # Advanced group
        advanced_group = Adw.PreferencesGroup(
            title="Advanced",
        )

        # Max concurrent extractions - use ActionRow + SpinButton for libadwaita 1.1
        concurrent_row = Adw.ActionRow(
            title="Concurrent Extractions",
            subtitle="Maximum number of simultaneous extractions",
        )
        adjustment = Gtk.Adjustment(
            value=self._settings.max_concurrent_extractions,
            lower=1,
            upper=8,
            step_increment=1,
        )
        self._concurrent_spin = Gtk.SpinButton(
            adjustment=adjustment,
            valign=Gtk.Align.CENTER,
        )
        self._concurrent_spin.connect("value-changed", self._on_setting_changed)
        concurrent_row.add_suffix(self._concurrent_spin)
        concurrent_row.set_activatable_widget(self._concurrent_spin)

        advanced_group.add(concurrent_row)
        page.add(advanced_group)

        return page

    def _build_appearance_page(self) -> Adw.PreferencesPage:
        """Build the appearance settings page."""
        page = Adw.PreferencesPage(
            title="Appearance",
            icon_name="applications-graphics-symbolic",
        )

        # Theme group
        theme_group = Adw.PreferencesGroup(
            title="Theme",
        )

        self._theme_combo = Adw.ComboRow(
            title="Color Scheme",
            subtitle="Choose the application color scheme",
        )

        theme_options = Gtk.StringList()
        theme_options.append("Follow System")
        theme_options.append("Light")
        theme_options.append("Dark")

        self._theme_combo.set_model(theme_options)

        theme_map = {
            "system": 0,
            "light": 1,
            "dark": 2,
        }
        self._theme_combo.set_selected(
            theme_map.get(self._settings.dark_mode, 0)
        )
        self._theme_combo.connect("notify::selected", self._on_theme_changed)

        theme_group.add(self._theme_combo)
        page.add(theme_group)

        return page

    def _on_dest_button_clicked(self, button: Gtk.Button) -> None:
        """Handle destination folder button click."""
        # Use FileChooserDialog for better compatibility
        dialog = Gtk.FileChooserDialog(
            title="Select Default Destination",
            transient_for=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("_Select", Gtk.ResponseType.ACCEPT)
        dialog.set_modal(True)

        # Set initial folder if it exists
        if self._settings.default_destination.exists():
            dialog.set_current_folder(
                Gio.File.new_for_path(str(self._settings.default_destination))
            )
        dialog.connect("response", self._on_dest_folder_response)
        dialog.show()

    def _on_dest_folder_response(
        self,
        dialog: Gtk.FileChooserDialog,
        response: int,
    ) -> None:
        """Handle destination folder selection."""
        if response == Gtk.ResponseType.ACCEPT:
            folder = dialog.get_file()
            if folder and folder.get_path():
                path = Path(folder.get_path())
                self._settings.default_destination = path
                self._dest_row.set_subtitle(str(path))
                self._modified = True
                logger.debug("Default destination changed to %s", path)
        dialog.destroy()

    def _on_setting_changed(self, widget: Gtk.Widget, param: object = None) -> None:
        """Handle setting change."""
        self._modified = True
        self._update_settings_from_ui()

    def _on_theme_changed(self, widget: Adw.ComboRow, param: object) -> None:
        """Handle theme change and apply immediately."""
        self._modified = True
        self._update_settings_from_ui()

        # Apply theme immediately
        theme_values = ["system", "light", "dark"]
        selected = self._theme_combo.get_selected()
        if 0 <= selected < len(theme_values):
            self._apply_theme(theme_values[selected])

    def _apply_theme(self, theme: str) -> None:
        """Apply the selected theme."""
        style_manager = Adw.StyleManager.get_default()

        if theme == "light":
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        elif theme == "dark":
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        else:  # system
            style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)

        logger.debug("Theme applied: %s", theme)

    def _update_settings_from_ui(self) -> None:
        """Update settings object from UI state."""
        # Notifications
        self._settings.show_notifications = self._notif_switch.get_active()

        # Conflict resolution
        conflict_values = [
            ConflictResolution.ASK,
            ConflictResolution.OVERWRITE,
            ConflictResolution.SKIP,
            ConflictResolution.RENAME,
        ]
        selected = self._conflict_combo.get_selected()
        if 0 <= selected < len(conflict_values):
            self._settings.conflict_resolution = conflict_values[selected]

        # Extraction options
        self._settings.create_root_folder = self._root_folder_switch.get_active()
        self._settings.preserve_timestamps = self._timestamps_switch.get_active()
        self._settings.preserve_permissions = self._permissions_switch.get_active()

        # Concurrent extractions
        self._settings.max_concurrent_extractions = int(
            self._concurrent_spin.get_value()
        )

        # Theme
        theme_values = ["system", "light", "dark"]
        theme_selected = self._theme_combo.get_selected()
        if 0 <= theme_selected < len(theme_values):
            self._settings.dark_mode = theme_values[theme_selected]

    def _on_close_request(self, window: Adw.PreferencesWindow) -> bool:
        """Handle window close - save settings if modified."""
        if self._modified:
            self._update_settings_from_ui()
            try:
                self._config_manager.save(self._settings)
                logger.info("Settings saved")
                self.emit("settings-changed", self._settings)
            except Exception as e:
                logger.exception("Failed to save settings: %s", e)

        return False  # Allow close to proceed

    def get_settings(self) -> ApplicationSettings:
        """Get the current settings.

        Returns:
            The current ApplicationSettings object.
        """
        self._update_settings_from_ui()
        return self._settings
