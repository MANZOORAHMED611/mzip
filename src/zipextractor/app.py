"""ZIP Extractor Application class.

This module contains the main GTK Application class that initializes
and manages the application lifecycle.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib

if TYPE_CHECKING:
    from collections.abc import Sequence

from zipextractor import __version__
from zipextractor.utils.logging import get_logger

logger = get_logger(__name__)


class ZipExtractorApp(Adw.Application):
    """Main application class for ZIP Extractor.

    This class manages the application lifecycle, including startup,
    activation, and shutdown. It also handles command-line arguments
    and application-wide actions.
    """

    def __init__(self) -> None:
        """Initialize the ZIP Extractor application."""
        super().__init__(
            application_id="com.github.zipextractor",
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
        )

        self.set_resource_base_path("/com/github/zipextractor")

        # Connect signals
        self.connect("activate", self._on_activate)
        self.connect("startup", self._on_startup)
        self.connect("open", self._on_open)

        logger.info("ZIP Extractor %s initialized", __version__)

    def _on_startup(self, app: Adw.Application) -> None:
        """Handle application startup.

        This is called once when the application starts, before any
        windows are created. Use this for one-time initialization.

        Args:
            app: The application instance.
        """
        logger.debug("Application startup")
        self._setup_actions()

    def _on_activate(self, app: Adw.Application) -> None:
        """Handle application activation.

        This is called when the application is launched without any files,
        or when a second instance tries to launch.

        Args:
            app: The application instance.
        """
        logger.debug("Application activated")

        # Import here to avoid circular imports and speed up --help
        from zipextractor.gui.main_window import MainWindow

        # Get existing window or create new one
        window = self.get_active_window()
        if window is None:
            window = MainWindow(application=self)

        window.present()

    def _on_open(
        self,
        app: Adw.Application,
        files: Sequence[Gio.File],
        n_files: int,
        hint: str,
    ) -> None:
        """Handle opening files from command line or file manager.

        Args:
            app: The application instance.
            files: List of files to open.
            n_files: Number of files.
            hint: Hint string (unused).
        """
        logger.info("Opening %d file(s)", n_files)

        # Activate first to ensure window exists
        self._on_activate(app)

        # Get the main window and add files
        window = self.get_active_window()
        if window is not None and hasattr(window, "add_archives"):
            paths = [f.get_path() for f in files if f.get_path() is not None]
            window.add_archives(paths)

    def _setup_actions(self) -> None:
        """Set up application-wide actions."""
        # Quit action
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self._on_quit)
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Control>q"])

        # About action
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

        logger.debug("Application actions configured")

    def _on_quit(
        self, action: Gio.SimpleAction, parameter: GLib.Variant | None
    ) -> None:
        """Handle quit action.

        Args:
            action: The action that was activated.
            parameter: Action parameter (unused).
        """
        logger.info("Application quit requested")
        self.quit()

    def _on_about(
        self, action: Gio.SimpleAction, parameter: GLib.Variant | None
    ) -> None:
        """Show the about dialog.

        Args:
            action: The action that was activated.
            parameter: Action parameter (unused).
        """
        about = Adw.AboutWindow(
            transient_for=self.get_active_window(),
            application_name="ZIP Extractor",
            application_icon="zipextractor",
            version=__version__,
            developer_name="ZIP Extractor Team",
            license_type=Gio.License.GPL_3_0,
            comments="Modern ZIP archive extraction utility for Ubuntu Linux",
            website="https://github.com/zipextractor/zipextractor",
        )
        about.present()
