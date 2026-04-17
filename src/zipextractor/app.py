"""ZIP Extractor Application class.

This module contains the main GTK Application class that initializes
and manages the application lifecycle.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

if TYPE_CHECKING:
    from collections.abc import Sequence

from zipextractor import __version__
from zipextractor.utils.logging import get_logger

# CSS file location relative to this module
CSS_FILE = "data/style.css"

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
        self._load_css()

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
            # Auto-inspect when opening files to show contents immediately
            window.add_archives(paths, auto_inspect=True)

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

        # Open action (Ctrl+O)
        open_action = Gio.SimpleAction.new("open-archive", None)
        open_action.connect("activate", self._on_open_archive)
        self.add_action(open_action)
        self.set_accels_for_action("app.open-archive", ["<Control>o"])

        # New archive action (Ctrl+N)
        new_action = Gio.SimpleAction.new("new", None)
        new_action.connect("activate", self._on_new)
        self.add_action(new_action)
        self.set_accels_for_action("app.new", ["<Control>n"])

        # Extract all action (Ctrl+E)
        extract_action = Gio.SimpleAction.new("extract", None)
        extract_action.connect("activate", self._on_extract)
        self.add_action(extract_action)
        self.set_accels_for_action("app.extract", ["<Control>e"])

        # Extract selected action (Ctrl+Shift+E)
        extract_selected_action = Gio.SimpleAction.new("extract-selected", None)
        extract_selected_action.connect("activate", self._on_extract_selected)
        self.add_action(extract_selected_action)
        self.set_accels_for_action("app.extract-selected", ["<Control><Shift>e"])

        # Search action (Ctrl+F)
        search_action = Gio.SimpleAction.new("search", None)
        search_action.connect("activate", self._on_search)
        self.add_action(search_action)
        self.set_accels_for_action("app.search", ["<Control>f"])

        # Test archive action (Ctrl+T)
        test_action = Gio.SimpleAction.new("test", None)
        test_action.connect("activate", self._on_test)
        self.add_action(test_action)
        self.set_accels_for_action("app.test", ["<Control>t"])

        # Refresh action (F5)
        refresh_action = Gio.SimpleAction.new("refresh", None)
        refresh_action.connect("activate", self._on_refresh)
        self.add_action(refresh_action)
        self.set_accels_for_action("app.refresh", ["F5"])

        # Keyboard shortcuts help (Ctrl+?)
        shortcuts_action = Gio.SimpleAction.new("shortcuts", None)
        shortcuts_action.connect("activate", self._on_shortcuts)
        self.add_action(shortcuts_action)
        self.set_accels_for_action("app.shortcuts", ["<Control>question"])

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
            application_name="MZip",
            application_icon="mzip",
            version=__version__,
            developer_name="Green Olive Tech",
            license_type=Gio.License.GPL_3_0,
            comments="Modern archive utility for Linux",
            website="https://github.com/MANZOORAHMED611/mzip",
            copyright="Copyright 2026 Green Olive Tech",
        )
        about.present()

    def _on_open_archive(
        self, action: Gio.SimpleAction, parameter: GLib.Variant | None
    ) -> None:
        """Handle open action (Ctrl+O)."""
        window = self.get_active_window()
        if window and hasattr(window, "show_open_dialog"):
            window.show_open_dialog()
        else:
            logger.debug("Open dialog not available")

    def _on_new(
        self, action: Gio.SimpleAction, parameter: GLib.Variant | None
    ) -> None:
        """Handle new archive action (Ctrl+N)."""
        window = self.get_active_window()
        if window and hasattr(window, "show_create_dialog"):
            window.show_create_dialog()
        else:
            logger.debug("Create dialog not available")

    def _on_extract(
        self, action: Gio.SimpleAction, parameter: GLib.Variant | None
    ) -> None:
        """Handle extract all action (Ctrl+E)."""
        window = self.get_active_window()
        if window and hasattr(window, "extract_all"):
            window.extract_all()
        else:
            logger.debug("Extract not available")

    def _on_extract_selected(
        self, action: Gio.SimpleAction, parameter: GLib.Variant | None
    ) -> None:
        """Handle extract selected action (Ctrl+Shift+E)."""
        window = self.get_active_window()
        if window and hasattr(window, "extract_selected"):
            window.extract_selected()
        else:
            logger.debug("Extract selected not available")

    def _on_search(
        self, action: Gio.SimpleAction, parameter: GLib.Variant | None
    ) -> None:
        """Handle search action (Ctrl+F)."""
        window = self.get_active_window()
        if window and hasattr(window, "show_search"):
            window.show_search()
        else:
            logger.debug("Search not available")

    def _on_test(
        self, action: Gio.SimpleAction, parameter: GLib.Variant | None
    ) -> None:
        """Handle test archive action (Ctrl+T)."""
        window = self.get_active_window()
        if window and hasattr(window, "test_archive"):
            window.test_archive()
        else:
            logger.debug("Test not available")

    def _on_refresh(
        self, action: Gio.SimpleAction, parameter: GLib.Variant | None
    ) -> None:
        """Handle refresh action (F5)."""
        window = self.get_active_window()
        if window and hasattr(window, "refresh"):
            window.refresh()
        else:
            logger.debug("Refresh not available")

    def _on_shortcuts(
        self, action: Gio.SimpleAction, parameter: GLib.Variant | None
    ) -> None:
        """Show keyboard shortcuts window."""
        shortcuts_window = Gtk.ShortcutsWindow(
            transient_for=self.get_active_window(),
            modal=True,
        )

        # Create shortcuts section
        section = Gtk.ShortcutsSection(
            section_name="shortcuts",
            title="All Shortcuts",
            visible=True,
        )

        # File operations group
        file_group = Gtk.ShortcutsGroup(title="File Operations", visible=True)
        file_group.append(Gtk.ShortcutsShortcut(
            title="Open Archive",
            accelerator="<Control>o",
            visible=True,
        ))
        file_group.append(Gtk.ShortcutsShortcut(
            title="Create New Archive",
            accelerator="<Control>n",
            visible=True,
        ))
        file_group.append(Gtk.ShortcutsShortcut(
            title="Quit",
            accelerator="<Control>q",
            visible=True,
        ))
        section.append(file_group)

        # Archive operations group
        archive_group = Gtk.ShortcutsGroup(title="Archive Operations", visible=True)
        archive_group.append(Gtk.ShortcutsShortcut(
            title="Extract All",
            accelerator="<Control>e",
            visible=True,
        ))
        archive_group.append(Gtk.ShortcutsShortcut(
            title="Extract Selected",
            accelerator="<Control><Shift>e",
            visible=True,
        ))
        archive_group.append(Gtk.ShortcutsShortcut(
            title="Test Archive",
            accelerator="<Control>t",
            visible=True,
        ))
        archive_group.append(Gtk.ShortcutsShortcut(
            title="Search",
            accelerator="<Control>f",
            visible=True,
        ))
        archive_group.append(Gtk.ShortcutsShortcut(
            title="Refresh",
            accelerator="F5",
            visible=True,
        ))
        section.append(archive_group)

        shortcuts_window.add_section(section)
        shortcuts_window.present()

    def _load_css(self) -> None:
        """Load custom CSS styles for the application."""
        from pathlib import Path

        # Find CSS file relative to this module
        module_dir = Path(__file__).parent
        css_path = module_dir / CSS_FILE

        if not css_path.exists():
            logger.warning("CSS file not found: %s", css_path)
            return

        try:
            css_provider = Gtk.CssProvider()
            css_provider.load_from_path(str(css_path))

            display = Gdk.Display.get_default()
            if display:
                Gtk.StyleContext.add_provider_for_display(
                    display,
                    css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                )
                logger.debug("Custom CSS loaded from %s", css_path)
        except Exception as e:
            logger.warning("Failed to load CSS: %s", e)
