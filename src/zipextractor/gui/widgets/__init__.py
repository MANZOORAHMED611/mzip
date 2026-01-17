"""Custom GTK widgets for ZIP Extractor.

This package contains custom GTK4/libadwaita widgets used throughout
the application, including progress dialogs, settings, and archive management.
"""

from zipextractor.gui.widgets.archive_inspector import ArchiveInspector
from zipextractor.gui.widgets.archive_list import ArchiveList, ArchiveRow
from zipextractor.gui.widgets.conflict_dialog import ConflictDialog
from zipextractor.gui.widgets.progress_dialog import ProgressDialog
from zipextractor.gui.widgets.settings_dialog import SettingsDialog

__all__: list[str] = [
    "ArchiveInspector",
    "ArchiveList",
    "ArchiveRow",
    "ConflictDialog",
    "ProgressDialog",
    "SettingsDialog",
]
