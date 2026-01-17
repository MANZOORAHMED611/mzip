# ZIP EXTRACTOR GUI

Technical Specification Document

Version 1.0

January 2025

*Modern ZIP Archive Extraction Utility for Ubuntu Linux*

Desktop GUI Application

---

## TABLE OF CONTENTS

1. [Executive Summary](#1-executive-summary)
2. [Product Overview](#2-product-overview)
3. [System Architecture](#3-system-architecture)
4. [Technology Stack](#4-technology-stack)
5. [Data Models](#5-data-models)
6. [User Interface Specification](#6-user-interface-specification)
7. [Core Functionality](#7-core-functionality)
8. [File Operations & Processing](#8-file-operations--processing)
9. [Testing Strategy](#9-testing-strategy)
10. [Deployment & Distribution](#10-deployment--distribution)
11. [Security & Compliance](#11-security--compliance)

---

## 1. Executive Summary

### 1.1 Product Vision

ZIP Extractor GUI is a lightweight, user-friendly desktop application for Ubuntu Linux that provides intuitive ZIP archive extraction with real-time progress tracking, batch processing capabilities, and robust error handling. The application eliminates the complexity of command-line tools while providing power-user features for advanced workflows.

### 1.2 Key Objectives

1. Extract ZIP archives in under 3 seconds for files <100MB
2. Support batch extraction of up to 50 archives simultaneously
3. Provide real-time progress tracking with file-by-file granularity
4. Deliver zero-configuration installation (single .deb package)
5. Maintain memory footprint under 100MB during active extraction

### 1.3 Target Users

- **Desktop Users**: Non-technical users needing simple archive extraction
- **Power Users**: Users managing multiple archives with batch operations
- **System Administrators**: IT professionals extracting configuration archives
- **Developers**: Engineers working with source code distributions

### 1.4 Success Criteria

- Installation time < 60 seconds
- First-time user completes extraction without documentation
- 99% success rate for standard ZIP archives
- Zero data loss or corruption during extraction
- Application startup time < 2 seconds

---

## 2. Product Overview

### 2.1 Core Features

#### 2.1.1 Essential Features (MVP)
- Single-file extraction with destination selection
- Batch extraction from multiple archives
- Real-time progress bar with percentage and file count
- Automatic conflict resolution (overwrite/skip/rename)
- Archive content preview before extraction
- Drag-and-drop interface for archive selection
- Recent extractions history (last 20)
- System tray integration with notifications

#### 2.1.2 Advanced Features (Post-MVP)
- Password-protected archive support
- Multi-format support (TAR, 7Z, RAR as plugins)
- Archive creation from selected files/folders
- Scheduled extractions
- File type filters during extraction
- Custom extraction profiles (save preferred settings)
- Integration with file manager context menu

### 2.2 Non-Functional Requirements

#### 2.2.1 Performance
- Extraction speed: 50MB/s minimum on standard HDD
- UI responsiveness: < 100ms for all user interactions
- Memory usage: < 100MB during active extraction
- Startup time: < 2 seconds cold start, < 0.5s warm start

#### 2.2.2 Reliability
- 99.9% extraction success rate for valid archives
- Graceful degradation on corrupted archives
- Automatic recovery from interrupted extractions
- Transaction-based operations (rollback on failure)

#### 2.2.3 Usability
- Zero-configuration installation
- Keyboard shortcuts for all primary actions
- Accessible design (WCAG 2.1 Level AA compliance)
- Multi-language support (English, Spanish, French, German)
- Context-sensitive help system

#### 2.2.4 Compatibility
- Ubuntu 20.04 LTS and newer
- GNOME, KDE, XFCE desktop environments
- HiDPI display support
- Dark mode support (follows system theme)

---

## 3. System Architecture

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Main Window │  │ Progress     │  │ Settings     │          │
│  │  (GTK4)      │  │ Dialog       │  │ Dialog       │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼──────────────────┼──────────────────┼─────────────────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                       APPLICATION LAYER                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Extraction  │  │  Archive     │  │  Settings    │          │
│  │  Manager     │  │  Inspector   │  │  Manager     │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                  │                  │                  │
│  ┌──────┴────────┐  ┌─────┴────────┐  ┌─────┴────────┐         │
│  │  Task Queue   │  │  File        │  │  Config      │         │
│  │  Manager      │  │  Validator   │  │  Store       │         │
│  └───────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                         CORE LAYER                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  ZIP Engine  │  │  File System │  │  Security    │          │
│  │  (libzip)    │  │  Operations  │  │  Validator   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      PLATFORM LAYER                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Linux FS    │  │  GTK4/       │  │  D-Bus       │          │
│  │  API         │  │  libadwaita  │  │  Integration │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Component Descriptions

#### 3.2.1 Extraction Manager
Orchestrates the extraction process, manages worker threads, and coordinates progress updates. Implements queue-based batch processing with configurable concurrency limits.

#### 3.2.2 Archive Inspector
Reads archive metadata without extracting, validates archive integrity, detects compression methods, and calculates uncompressed size for disk space validation.

#### 3.2.3 Task Queue Manager
Manages extraction tasks with priority queuing, implements pause/resume functionality, handles task cancellation, and provides task status tracking.

#### 3.2.4 File Validator
Validates file paths for security (path traversal prevention), checks available disk space, detects file conflicts, and validates file permissions.

#### 3.2.5 Settings Manager
Persists user preferences to `~/.config/zipextractor/settings.json`, manages default extraction directory, conflict resolution preferences, and UI theme settings.

#### 3.2.6 ZIP Engine
Core extraction engine using libzip library, handles various compression methods (DEFLATE, BZIP2, LZMA), supports ZIP64 for large archives, and implements streaming extraction for memory efficiency.

---

## 4. Technology Stack

### 4.1 Core Technologies

| Component | Technology | Version | Justification |
|-----------|------------|---------|---------------|
| Programming Language | Python | 3.10+ | Rapid development, excellent library ecosystem, native Ubuntu support |
| GUI Framework | GTK4 + libadwaita | 4.12+ | Native Linux toolkit, modern UI components, GNOME integration |
| ZIP Library | libzip (via Python bindings) | 1.9+ | Battle-tested C library, excellent performance, comprehensive format support |
| Async Framework | asyncio + threading | stdlib | Built-in concurrency for UI responsiveness |
| Configuration | TOML | stdlib | Human-readable config format, native Python support |
| Logging | Python logging | stdlib | Standard logging with rotation support |

### 4.2 Development Dependencies

| Component | Technology | Purpose |
|-----------|------------|---------|
| Build System | setuptools | Package creation and distribution |
| Dependency Management | pip + requirements.txt | Reproducible environments |
| Linting | ruff | Fast Python linter and formatter |
| Type Checking | mypy | Static type analysis |
| Testing Framework | pytest | Unit and integration testing |
| Coverage | pytest-cov | Code coverage reporting |
| Documentation | Sphinx | API documentation generation |

### 4.3 Distribution & Packaging

| Component | Technology | Purpose |
|-----------|------------|---------|
| Package Format | .deb | Native Ubuntu package format |
| Build Tool | dpkg-buildpackage | Debian package builder |
| Desktop Integration | .desktop file | Application menu integration |
| Icons | SVG + PNG | Scalable icons for all resolutions |
| AppStream Metadata | .appdata.xml | Software center metadata |

---

## 5. Data Models

### 5.1 Application State

#### 5.1.1 ExtractionTask
```python
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional
from datetime import datetime

class TaskStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ConflictResolution(Enum):
    ASK = "ask"
    OVERWRITE = "overwrite"
    SKIP = "skip"
    RENAME = "rename"

@dataclass
class ExtractionTask:
    """Represents a single archive extraction task"""
    task_id: str
    archive_path: Path
    destination_path: Path
    status: TaskStatus
    conflict_resolution: ConflictResolution
    
    # Progress tracking
    total_files: int
    extracted_files: int
    total_bytes: int
    extracted_bytes: int
    current_file: Optional[str] = None
    
    # Metadata
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Error handling
    error_message: Optional[str] = None
    failed_files: list[str] = None
    
    # Options
    preserve_permissions: bool = True
    preserve_timestamps: bool = True
    create_root_folder: bool = True
    
    @property
    def progress_percentage(self) -> float:
        """Calculate extraction progress as percentage"""
        if self.total_bytes == 0:
            return 0.0
        return (self.extracted_bytes / self.total_bytes) * 100
    
    @property
    def is_active(self) -> bool:
        """Check if task is currently processing"""
        return self.status in {TaskStatus.QUEUED, TaskStatus.RUNNING}
```

#### 5.1.2 ArchiveInfo
```python
@dataclass
class ArchiveInfo:
    """Archive metadata retrieved via inspection"""
    path: Path
    file_size: int
    uncompressed_size: int
    file_count: int
    compression_method: str
    has_password: bool
    root_folder: Optional[str]
    
    # Archive validation
    is_valid: bool
    validation_errors: list[str]
    
    # File listing
    files: list['ArchiveFile']
    
    @property
    def compression_ratio(self) -> float:
        """Calculate compression ratio"""
        if self.uncompressed_size == 0:
            return 0.0
        return (1 - self.file_size / self.uncompressed_size) * 100

@dataclass
class ArchiveFile:
    """Individual file within archive"""
    path: str
    size: int
    compressed_size: int
    is_directory: bool
    modified_time: datetime
    crc32: Optional[int] = None
```

#### 5.1.3 ApplicationSettings
```python
@dataclass
class ApplicationSettings:
    """User preferences and configuration"""
    # Extraction defaults
    default_destination: Path
    default_conflict_resolution: ConflictResolution
    create_root_folder: bool
    preserve_permissions: bool
    preserve_timestamps: bool
    
    # Behavior
    confirm_before_extraction: bool
    show_completion_notification: bool
    close_window_after_extraction: bool
    remember_last_destination: bool
    
    # Performance
    max_concurrent_extractions: int
    buffer_size_mb: int
    
    # UI preferences
    window_width: int
    window_height: int
    window_maximized: bool
    show_hidden_files: bool
    dark_mode: Optional[bool]  # None = follow system
    
    # History
    max_recent_items: int
    recent_archives: list[Path]
    recent_destinations: list[Path]
    
    # Advanced
    log_level: str
    check_for_updates: bool
```

### 5.2 Configuration Files

#### 5.2.1 Settings Storage Location
- Path: `~/.config/zipextractor/settings.json`
- Format: JSON
- Permissions: 0600 (user read/write only)

#### 5.2.2 Settings Schema
```json
{
  "version": "1.0",
  "extraction": {
    "default_destination": "~/Downloads",
    "conflict_resolution": "ask",
    "create_root_folder": true,
    "preserve_permissions": true,
    "preserve_timestamps": true
  },
  "behavior": {
    "confirm_before_extraction": false,
    "show_completion_notification": true,
    "close_window_after_extraction": false,
    "remember_last_destination": true
  },
  "performance": {
    "max_concurrent_extractions": 4,
    "buffer_size_mb": 8
  },
  "ui": {
    "window_width": 800,
    "window_height": 600,
    "window_maximized": false,
    "show_hidden_files": false,
    "dark_mode": null
  },
  "history": {
    "max_recent_items": 20,
    "recent_archives": [],
    "recent_destinations": []
  },
  "advanced": {
    "log_level": "INFO",
    "check_for_updates": true
  }
}
```

#### 5.2.3 Log Files
- Location: `~/.local/share/zipextractor/logs/`
- Format: Rotating log files (max 10MB per file, 5 files retained)
- File naming: `zipextractor-YYYY-MM-DD.log`

---

## 6. User Interface Specification

### 6.1 Main Window Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ ZIP Extractor                                          [_][□][X] │
├─────────────────────────────────────────────────────────────────┤
│ File  Edit  View  Tools  Help                                   │
├─────────────────────────────────────────────────────────────────┤
│ [📁 Add Files] [📂 Add Folder] [🗑️ Clear] [⚙️ Settings]         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Drop ZIP files here or click Add Files                         │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Archive Name          │ Files │ Size   │ Status     │ [X]  │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │ project.zip           │  124  │ 45 MB  │ Ready      │ [X]  │ │
│  │ documents.zip         │   56  │ 12 MB  │ Ready      │ [X]  │ │
│  │ photos-2024.zip       │  340  │ 2.1 GB │ Ready      │ [X]  │ │
│  │                                                              │ │
│  │                                                              │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  Destination: [/home/user/Downloads          ] [Browse...]      │
│                                                                  │
│  [ ] Create folder for each archive                             │
│  [x] Overwrite existing files                                   │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  3 files • 2.16 GB total               [Extract All]  [Cancel]  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Screen Specifications

#### 6.2.1 Main Window
**Purpose**: Primary interface for file selection and extraction

**Components**:
- **Header Bar**: Application title, minimize/maximize/close buttons
- **Menu Bar**: File, Edit, View, Tools, Help menus
- **Toolbar**: Quick access buttons for common actions
- **Drop Zone**: Drag-and-drop area for archive files
- **Archive List**: Scrollable table showing queued archives
- **Destination Panel**: Destination selection and options
- **Status Bar**: Summary information and action buttons

**Dimensions**:
- Default: 800x600 pixels
- Minimum: 640x480 pixels
- Resizable: Yes
- Remembers size: Yes

**Keyboard Shortcuts**:
- `Ctrl+O`: Add files
- `Ctrl+E`: Extract all
- `Ctrl+W`: Clear list
- `Ctrl+,`: Open settings
- `Ctrl+Q`: Quit application
- `Delete`: Remove selected archive from list
- `F1`: Open help

#### 6.2.2 Progress Dialog
**Purpose**: Display real-time extraction progress

```
┌─────────────────────────────────────────────────────────┐
│ Extracting Archives...                         [_][X]   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Current: project.zip                                   │
│  File: src/components/MainWindow.py (45/124)            │
│                                                          │
│  [████████████████░░░░░░░░░░░] 68%                      │
│                                                          │
│  Speed: 42.5 MB/s                                       │
│  Remaining: 12 seconds                                  │
│  Destination: /home/user/Downloads/project/             │
│                                                          │
│  Overall Progress: 1 of 3 archives                      │
│  [████████░░░░░░░░░░░░░░░░░░░░] 33%                     │
│                                                          │
├─────────────────────────────────────────────────────────┤
│                            [Pause]  [Cancel]            │
└─────────────────────────────────────────────────────────┘
```

**Behavior**:
- Modal dialog (blocks main window)
- Updates every 200ms
- Shows current file being extracted
- Displays extraction speed (rolling 5-second average)
- Pause button suspends extraction, can be resumed
- Cancel button prompts for confirmation, then rolls back

#### 6.2.3 Archive Preview Dialog
**Purpose**: View archive contents before extraction

```
┌─────────────────────────────────────────────────────────┐
│ Archive Contents: project.zip                  [_][X]   │
├─────────────────────────────────────────────────────────┤
│ Files: 124 • Size: 45.2 MB • Compressed: 38.1 MB       │
├─────────────────────────────────────────────────────────┤
│  Name                      │ Size     │ Modified         │
│  ─────────────────────────────────────────────────────  │
│  📁 project/               │          │                  │
│    📁 src/                 │          │                  │
│      📄 main.py            │  2.4 KB  │ 2024-01-10 14:30│
│      📄 utils.py           │  1.8 KB  │ 2024-01-10 14:25│
│    📁 tests/               │          │                  │
│      📄 test_main.py       │  3.2 KB  │ 2024-01-10 15:00│
│    📄 README.md            │  1.2 KB  │ 2024-01-10 13:00│
│    📄 requirements.txt     │  0.4 KB  │ 2024-01-10 13:15│
│                                                          │
├─────────────────────────────────────────────────────────┤
│  [Select All] [Deselect All]        [Extract] [Close]  │
└─────────────────────────────────────────────────────────┘
```

**Features**:
- Tree view of archive structure
- File size and modification date display
- Checkbox selection for partial extraction
- Search/filter functionality
- Sort by name, size, or date
- Icon indicators for file types

#### 6.2.4 Settings Dialog
**Purpose**: Configure application preferences

```
┌─────────────────────────────────────────────────────────┐
│ Preferences                                    [_][X]   │
├─────────────────────────────────────────────────────────┤
│  General  │  Extraction  │  Advanced                    │
├───────────┴──────────────────────────────────────────────┤
│                                                          │
│  Extraction Settings                                    │
│  ┌────────────────────────────────────────────────────┐ │
│  │ Default destination:                               │ │
│  │ [/home/user/Downloads              ] [Browse...]   │ │
│  │                                                     │ │
│  │ [x] Remember last used destination                 │ │
│  │ [x] Create root folder for each archive            │ │
│  │ [x] Preserve file permissions                      │ │
│  │ [x] Preserve timestamps                            │ │
│  │                                                     │ │
│  │ When file exists:                                  │ │
│  │ ( ) Ask me                                         │ │
│  │ (•) Overwrite                                      │ │
│  │ ( ) Skip                                           │ │
│  │ ( ) Rename (add number suffix)                     │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  Notifications                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │ [x] Show notification when extraction completes    │ │
│  │ [ ] Close window automatically after extraction    │ │
│  │ [ ] Confirm before starting extraction             │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
├─────────────────────────────────────────────────────────┤
│                              [Reset] [Cancel] [Apply]   │
└─────────────────────────────────────────────────────────┘
```

**Tabs**:
1. **General**: Destination, conflict resolution, notifications
2. **Extraction**: Performance settings, file options
3. **Advanced**: Logging, updates, experimental features

#### 6.2.5 Error Dialog
**Purpose**: Display extraction errors with actionable information

```
┌─────────────────────────────────────────────────────────┐
│ ⚠️ Extraction Errors                            [X]     │
├─────────────────────────────────────────────────────────┤
│  Failed to extract 3 files from project.zip:            │
│                                                          │
│  ✗ src/data/large_file.bin                             │
│    Error: Insufficient disk space (need 2.3 GB)         │
│                                                          │
│  ✗ src/protected/secret.txt                            │
│    Error: Permission denied                             │
│                                                          │
│  ✗ src/corrupt/data.json                               │
│    Error: CRC32 checksum mismatch                       │
│                                                          │
│  121 of 124 files extracted successfully                │
│                                                          │
├─────────────────────────────────────────────────────────┤
│  [View Log] [Copy Details]              [Close]        │
└─────────────────────────────────────────────────────────┘
```

**Features**:
- Clear error messages with specific file names
- Actionable suggestions for resolution
- Summary of successful vs. failed extractions
- Copy to clipboard functionality for bug reports
- Link to detailed log file

### 6.3 Visual Design

#### 6.3.1 Color Scheme
- **Primary**: Adwaita Blue (#3584e4)
- **Success**: Green (#33d17a)
- **Warning**: Orange (#f6d32d)
- **Error**: Red (#e01b24)
- **Background (Light)**: #ffffff
- **Background (Dark)**: #242424
- **Text (Light)**: #2e3436
- **Text (Dark)**: #ffffff

#### 6.3.2 Typography
- **Font Family**: System default (Cantarell on GNOME)
- **Title**: 16pt Bold
- **Body**: 11pt Regular
- **Monospace**: 10pt (for file paths, technical details)

#### 6.3.3 Icons
- **Style**: Symbolic icons from Adwaita icon theme
- **Size**: 16px for toolbar, 24px for large buttons
- **Format**: SVG for scalability

#### 6.3.4 Spacing
- **Padding**: 12px standard, 6px compact
- **Margins**: 18px between major sections
- **Border Radius**: 6px for all rounded elements

---

## 7. Core Functionality

### 7.1 Archive Selection

#### 7.1.1 File Picker
```python
def select_archives() -> list[Path]:
    """
    Open GTK file chooser for archive selection
    
    Returns:
        List of selected archive paths
    """
    dialog = Gtk.FileChooserDialog(
        title="Select ZIP Archives",
        action=Gtk.FileChooserAction.OPEN,
        select_multiple=True
    )
    
    # Add ZIP file filter
    filter_zip = Gtk.FileFilter()
    filter_zip.set_name("ZIP Archives")
    filter_zip.add_mime_type("application/zip")
    filter_zip.add_pattern("*.zip")
    dialog.add_filter(filter_zip)
    
    # Add all files filter
    filter_all = Gtk.FileFilter()
    filter_all.set_name("All Files")
    filter_all.add_pattern("*")
    dialog.add_filter(filter_all)
    
    dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
    dialog.add_button("Open", Gtk.ResponseType.ACCEPT)
    
    response = dialog.run()
    files = []
    
    if response == Gtk.ResponseType.ACCEPT:
        files = dialog.get_filenames()
    
    dialog.destroy()
    return [Path(f) for f in files]
```

#### 7.1.2 Drag and Drop
```python
def setup_drag_drop(target_widget: Gtk.Widget) -> None:
    """Configure drag-and-drop for archive files"""
    
    target_widget.drag_dest_set(
        Gtk.DestDefaults.ALL,
        [Gtk.TargetEntry.new("text/uri-list", 0, 0)],
        Gdk.DragAction.COPY
    )
    
    target_widget.connect("drag-data-received", on_files_dropped)

def on_files_dropped(widget, context, x, y, data, info, time):
    """Handle dropped files"""
    uris = data.get_uris()
    paths = [Path(uri.replace("file://", "")) for uri in uris]
    
    # Filter for ZIP files only
    zip_files = [p for p in paths if p.suffix.lower() == ".zip"]
    
    if zip_files:
        add_archives_to_queue(zip_files)
    else:
        show_error("No ZIP files found in dropped items")
```

### 7.2 Archive Inspection

#### 7.2.1 Validation
```python
from zipfile import ZipFile, BadZipFile
from pathlib import Path

def validate_archive(archive_path: Path) -> tuple[bool, Optional[str]]:
    """
    Validate ZIP archive integrity
    
    Args:
        archive_path: Path to ZIP file
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not archive_path.exists():
        return False, "File not found"
    
    if not archive_path.is_file():
        return False, "Path is not a file"
    
    if archive_path.stat().st_size == 0:
        return False, "File is empty"
    
    try:
        with ZipFile(archive_path, 'r') as zf:
            # Test archive integrity
            bad_file = zf.testzip()
            if bad_file:
                return False, f"Corrupted file in archive: {bad_file}"
            
            return True, None
            
    except BadZipFile:
        return False, "Invalid ZIP file format"
    except Exception as e:
        return False, f"Validation error: {str(e)}"
```

#### 7.2.2 Metadata Extraction
```python
def get_archive_info(archive_path: Path) -> ArchiveInfo:
    """
    Extract metadata from ZIP archive
    
    Args:
        archive_path: Path to ZIP file
        
    Returns:
        ArchiveInfo object with archive details
    """
    with ZipFile(archive_path, 'r') as zf:
        files = []
        total_compressed = 0
        total_uncompressed = 0
        
        for info in zf.infolist():
            files.append(ArchiveFile(
                path=info.filename,
                size=info.file_size,
                compressed_size=info.compress_size,
                is_directory=info.is_dir(),
                modified_time=datetime(*info.date_time),
                crc32=info.CRC
            ))
            
            total_compressed += info.compress_size
            total_uncompressed += info.file_size
        
        # Detect compression method
        compression_methods = set(f.compress_type for f in zf.infolist())
        compression_str = "Mixed" if len(compression_methods) > 1 else \
                         COMPRESSION_NAMES.get(compression_methods.pop(), "Unknown")
        
        # Detect root folder
        root_folder = detect_root_folder([f.path for f in files])
        
        return ArchiveInfo(
            path=archive_path,
            file_size=archive_path.stat().st_size,
            uncompressed_size=total_uncompressed,
            file_count=len(files),
            compression_method=compression_str,
            has_password=any(f.flag_bits & 0x1 for f in zf.infolist()),
            root_folder=root_folder,
            is_valid=True,
            validation_errors=[],
            files=files
        )

def detect_root_folder(file_paths: list[str]) -> Optional[str]:
    """
    Detect if archive has a single root folder
    
    Returns:
        Root folder name if exists, None otherwise
    """
    if not file_paths:
        return None
    
    # Get first-level directories
    top_level = set()
    for path in file_paths:
        parts = path.split('/')
        if parts:
            top_level.add(parts[0])
    
    # If exactly one top-level item and it's a directory
    if len(top_level) == 1:
        return top_level.pop()
    
    return None
```

### 7.3 Extraction Engine

#### 7.3.1 Single Archive Extraction
```python
import shutil
from threading import Thread
from queue import Queue

class ExtractionEngine:
    """Core extraction engine with progress tracking"""
    
    def __init__(self):
        self.progress_queue = Queue()
        self.should_cancel = False
        self.is_paused = False
    
    def extract_archive(
        self,
        task: ExtractionTask,
        progress_callback: Optional[Callable] = None
    ) -> bool:
        """
        Extract single archive with progress tracking
        
        Args:
            task: ExtractionTask object
            progress_callback: Optional callback for progress updates
            
        Returns:
            True if successful, False otherwise
        """
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        try:
            # Validate destination
            if not self._validate_destination(task):
                return False
            
            # Check disk space
            if not self._check_disk_space(task):
                task.error_message = "Insufficient disk space"
                task.status = TaskStatus.FAILED
                return False
            
            # Perform extraction
            with ZipFile(task.archive_path, 'r') as zf:
                members = zf.namelist()
                task.total_files = len(members)
                task.total_bytes = sum(
                    zf.getinfo(m).file_size for m in members
                )
                
                for index, member in enumerate(members):
                    # Check for cancellation
                    if self.should_cancel:
                        self._rollback_extraction(task)
                        task.status = TaskStatus.CANCELLED
                        return False
                    
                    # Wait if paused
                    while self.is_paused:
                        time.sleep(0.1)
                    
                    # Extract file
                    try:
                        self._extract_member(zf, member, task)
                        
                        task.extracted_files = index + 1
                        task.current_file = member
                        
                        if progress_callback:
                            progress_callback(task)
                            
                    except Exception as e:
                        if task.failed_files is None:
                            task.failed_files = []
                        task.failed_files.append(f"{member}: {str(e)}")
            
            # Mark as completed
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            return True
            
        except Exception as e:
            task.error_message = str(e)
            task.status = TaskStatus.FAILED
            return False
    
    def _extract_member(
        self,
        zipfile: ZipFile,
        member: str,
        task: ExtractionTask
    ) -> None:
        """Extract single member with security checks"""
        
        # Security: Prevent path traversal
        member_path = Path(member)
        if member_path.is_absolute() or ".." in member_path.parts:
            raise ValueError(f"Unsafe path detected: {member}")
        
        # Determine extraction path
        if task.create_root_folder:
            root_name = task.archive_path.stem
            extract_path = task.destination_path / root_name
        else:
            extract_path = task.destination_path
        
        full_path = extract_path / member_path
        
        # Handle conflicts
        if full_path.exists():
            action = self._resolve_conflict(full_path, task)
            if action == "skip":
                return
            elif action == "rename":
                full_path = self._get_unique_path(full_path)
        
        # Extract file
        info = zipfile.getinfo(member)
        
        if info.is_dir():
            full_path.mkdir(parents=True, exist_ok=True)
        else:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            with zipfile.open(member) as source:
                with open(full_path, 'wb') as target:
                    shutil.copyfileobj(source, target)
            
            # Preserve attributes
            if task.preserve_permissions:
                mode = info.external_attr >> 16
                if mode:
                    full_path.chmod(mode)
            
            if task.preserve_timestamps:
                mod_time = time.mktime(info.date_time + (0, 0, -1))
                os.utime(full_path, (mod_time, mod_time))
        
        # Update progress
        task.extracted_bytes += info.file_size
    
    def _validate_destination(self, task: ExtractionTask) -> bool:
        """Validate destination directory"""
        dest = task.destination_path
        
        if not dest.exists():
            try:
                dest.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                task.error_message = f"Cannot create destination: {e}"
                task.status = TaskStatus.FAILED
                return False
        
        if not os.access(dest, os.W_OK):
            task.error_message = "No write permission for destination"
            task.status = TaskStatus.FAILED
            return False
        
        return True
    
    def _check_disk_space(self, task: ExtractionTask) -> bool:
        """Check if sufficient disk space available"""
        stat = shutil.disk_usage(task.destination_path)
        required = task.total_bytes * 1.1  # 10% buffer
        
        return stat.free >= required
    
    def _resolve_conflict(
        self,
        path: Path,
        task: ExtractionTask
    ) -> str:
        """
        Resolve file conflict based on settings
        
        Returns:
            "overwrite", "skip", or "rename"
        """
        if task.conflict_resolution == ConflictResolution.OVERWRITE:
            return "overwrite"
        elif task.conflict_resolution == ConflictResolution.SKIP:
            return "skip"
        elif task.conflict_resolution == ConflictResolution.RENAME:
            return "rename"
        else:  # ASK
            # In real implementation, this would show a dialog
            return "overwrite"
    
    def _get_unique_path(self, path: Path) -> Path:
        """Generate unique filename by adding number suffix"""
        counter = 1
        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        
        while True:
            new_name = f"{stem} ({counter}){suffix}"
            new_path = parent / new_name
            if not new_path.exists():
                return new_path
            counter += 1
    
    def _rollback_extraction(self, task: ExtractionTask) -> None:
        """Remove partially extracted files"""
        if task.create_root_folder:
            root_folder = task.destination_path / task.archive_path.stem
            if root_folder.exists():
                shutil.rmtree(root_folder, ignore_errors=True)
```

#### 7.3.2 Batch Processing
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

class BatchExtractionManager:
    """Manages batch extraction with concurrency control"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.engine = ExtractionEngine()
        self.active_tasks: dict[str, ExtractionTask] = {}
    
    def extract_batch(
        self,
        tasks: list[ExtractionTask],
        progress_callback: Optional[Callable] = None
    ) -> dict[str, bool]:
        """
        Extract multiple archives concurrently
        
        Args:
            tasks: List of ExtractionTask objects
            progress_callback: Optional progress callback
            
        Returns:
            Dictionary mapping task_id to success status
        """
        results = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(
                    self.engine.extract_archive,
                    task,
                    progress_callback
                ): task
                for task in tasks
            }
            
            # Process completions
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    success = future.result()
                    results[task.task_id] = success
                except Exception as e:
                    task.error_message = str(e)
                    task.status = TaskStatus.FAILED
                    results[task.task_id] = False
        
        return results
```

### 7.4 Progress Tracking

#### 7.4.1 Progress Calculator
```python
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class ProgressStats:
    """Real-time progress statistics"""
    current_speed_mbps: float
    average_speed_mbps: float
    eta_seconds: int
    elapsed_seconds: int
    
    @property
    def eta_formatted(self) -> str:
        """Format ETA as human-readable string"""
        if self.eta_seconds < 60:
            return f"{self.eta_seconds}s"
        elif self.eta_seconds < 3600:
            return f"{self.eta_seconds // 60}m {self.eta_seconds % 60}s"
        else:
            hours = self.eta_seconds // 3600
            minutes = (self.eta_seconds % 3600) // 60
            return f"{hours}h {minutes}m"

class ProgressTracker:
    """Track extraction progress with speed calculation"""
    
    def __init__(self):
        self.start_time: Optional[datetime] = None
        self.last_update: Optional[datetime] = None
        self.last_bytes: int = 0
        self.speed_samples: list[float] = []
        self.max_samples = 10
    
    def start(self) -> None:
        """Start progress tracking"""
        self.start_time = datetime.now()
        self.last_update = self.start_time
        self.last_bytes = 0
        self.speed_samples = []
    
    def update(self, extracted_bytes: int, total_bytes: int) -> ProgressStats:
        """
        Update progress and calculate statistics
        
        Args:
            extracted_bytes: Bytes extracted so far
            total_bytes: Total bytes to extract
            
        Returns:
            ProgressStats object
        """
        now = datetime.now()
        
        # Calculate current speed
        time_delta = (now - self.last_update).total_seconds()
        if time_delta > 0:
            bytes_delta = extracted_bytes - self.last_bytes
            speed_mbps = (bytes_delta / time_delta) / (1024 * 1024)
            
            # Store sample
            self.speed_samples.append(speed_mbps)
            if len(self.speed_samples) > self.max_samples:
                self.speed_samples.pop(0)
        else:
            speed_mbps = 0
        
        # Calculate average speed
        avg_speed = sum(self.speed_samples) / len(self.speed_samples) \
                   if self.speed_samples else 0
        
        # Calculate ETA
        remaining_bytes = total_bytes - extracted_bytes
        if avg_speed > 0:
            eta_seconds = int((remaining_bytes / (1024 * 1024)) / avg_speed)
        else:
            eta_seconds = 0
        
        # Calculate elapsed time
        elapsed = int((now - self.start_time).total_seconds())
        
        # Update state
        self.last_update = now
        self.last_bytes = extracted_bytes
        
        return ProgressStats(
            current_speed_mbps=speed_mbps,
            average_speed_mbps=avg_speed,
            eta_seconds=eta_seconds,
            elapsed_seconds=elapsed
        )
```

---

## 8. File Operations & Processing

### 8.1 Security Measures

#### 8.1.1 Path Traversal Prevention
```python
def is_safe_path(base_path: Path, target_path: Path) -> bool:
    """
    Check if target path is within base path (prevents path traversal)
    
    Args:
        base_path: Base directory for extraction
        target_path: Target file path to validate
        
    Returns:
        True if safe, False if potential traversal detected
    """
    try:
        # Resolve both paths to absolute
        base_resolved = base_path.resolve()
        target_resolved = target_path.resolve()
        
        # Check if target is relative to base
        return target_resolved.is_relative_to(base_resolved)
        
    except (ValueError, RuntimeError):
        return False
```

#### 8.1.2 Disk Space Validation
```python
def validate_disk_space(
    destination: Path,
    required_bytes: int,
    buffer_percentage: float = 0.1
) -> tuple[bool, int]:
    """
    Validate sufficient disk space available
    
    Args:
        destination: Extraction destination
        required_bytes: Bytes needed for extraction
        buffer_percentage: Safety buffer (default 10%)
        
    Returns:
        Tuple of (has_space, available_bytes)
    """
    stat = shutil.disk_usage(destination)
    required_with_buffer = int(required_bytes * (1 + buffer_percentage))
    
    return stat.free >= required_with_buffer, stat.free
```

#### 8.1.3 Malicious Archive Detection
```python
def detect_zip_bomb(archive_path: Path, max_ratio: float = 100.0) -> bool:
    """
    Detect potential ZIP bomb attacks
    
    Args:
        archive_path: Path to ZIP file
        max_ratio: Maximum allowed compression ratio
        
    Returns:
        True if potential bomb detected
    """
    with ZipFile(archive_path, 'r') as zf:
        compressed_size = archive_path.stat().st_size
        uncompressed_size = sum(info.file_size for info in zf.infolist())
        
        if compressed_size == 0:
            return False
        
        ratio = uncompressed_size / compressed_size
        
        # Also check for excessive nesting
        max_depth = max(len(Path(f.filename).parts) for f in zf.infolist())
        
        return ratio > max_ratio or max_depth > 50
```

### 8.2 Error Handling

#### 8.2.1 Error Categories
```python
from enum import Enum

class ExtractionErrorType(Enum):
    """Categories of extraction errors"""
    DISK_SPACE = "disk_space"
    PERMISSION = "permission"
    CORRUPTION = "corruption"
    UNSUPPORTED = "unsupported"
    NETWORK = "network"  # For future network locations
    UNKNOWN = "unknown"

@dataclass
class ExtractionError:
    """Detailed error information"""
    error_type: ExtractionErrorType
    file_path: str
    message: str
    is_recoverable: bool
    suggested_action: str
```

#### 8.2.2 Error Recovery
```python
class ErrorRecoveryManager:
    """Handle errors and attempt recovery"""
    
    def handle_extraction_error(
        self,
        error: Exception,
        file_path: str,
        task: ExtractionTask
    ) -> ExtractionError:
        """
        Analyze error and determine recovery strategy
        
        Args:
            error: The exception that occurred
            file_path: Path to file that failed
            task: Current extraction task
            
        Returns:
            ExtractionError with recovery information
        """
        # Permission errors
        if isinstance(error, PermissionError):
            return ExtractionError(
                error_type=ExtractionErrorType.PERMISSION,
                file_path=file_path,
                message="Permission denied",
                is_recoverable=False,
                suggested_action="Check destination folder permissions"
            )
        
        # Disk space errors
        elif isinstance(error, OSError) and error.errno == 28:  # ENOSPC
            return ExtractionError(
                error_type=ExtractionErrorType.DISK_SPACE,
                file_path=file_path,
                message="Insufficient disk space",
                is_recoverable=False,
                suggested_action="Free up disk space and retry"
            )
        
        # Corruption errors
        elif isinstance(error, BadZipFile):
            return ExtractionError(
                error_type=ExtractionErrorType.CORRUPTION,
                file_path=file_path,
                message="Archive is corrupted",
                is_recoverable=False,
                suggested_action="Verify archive integrity or re-download"
            )
        
        # Generic errors
        else:
            return ExtractionError(
                error_type=ExtractionErrorType.UNKNOWN,
                file_path=file_path,
                message=str(error),
                is_recoverable=True,
                suggested_action="Retry extraction"
            )
```

---

## 9. Testing Strategy

### 9.1 Test Coverage Goals

| Test Type | Target Coverage | Automation |
|-----------|----------------|------------|
| Unit Tests | 85%+ | Fully automated (pytest) |
| Integration Tests | 75%+ | Fully automated |
| UI Tests | 60%+ | Semi-automated (Dogtail) |
| Manual Tests | Critical paths | Manual QA |
| Performance Tests | Key scenarios | Automated benchmarks |

### 9.2 Unit Test Cases

#### 9.2.1 Core Functionality Tests
```python
import pytest
from pathlib import Path
from zipextractor.core import ExtractionEngine, ExtractionTask

class TestExtractionEngine:
    """Test extraction engine functionality"""
    
    @pytest.fixture
    def engine(self):
        return ExtractionEngine()
    
    @pytest.fixture
    def sample_archive(self, tmp_path):
        """Create sample ZIP archive for testing"""
        archive_path = tmp_path / "test.zip"
        with ZipFile(archive_path, 'w') as zf:
            zf.writestr("file1.txt", "content1")
            zf.writestr("dir/file2.txt", "content2")
        return archive_path
    
    def test_extract_simple_archive(self, engine, sample_archive, tmp_path):
        """Test extraction of simple archive"""
        dest = tmp_path / "extracted"
        
        task = ExtractionTask(
            task_id="test-1",
            archive_path=sample_archive,
            destination_path=dest,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            total_files=0,
            extracted_files=0,
            total_bytes=0,
            extracted_bytes=0,
            created_at=datetime.now()
        )
        
        success = engine.extract_archive(task)
        
        assert success
        assert task.status == TaskStatus.COMPLETED
        assert (dest / "test" / "file1.txt").exists()
        assert (dest / "test" / "dir" / "file2.txt").exists()
    
    def test_path_traversal_prevention(self, engine, tmp_path):
        """Test that path traversal attacks are blocked"""
        # Create malicious archive
        archive_path = tmp_path / "malicious.zip"
        with ZipFile(archive_path, 'w') as zf:
            zf.writestr("../../../etc/passwd", "malicious")
        
        task = ExtractionTask(
            task_id="test-2",
            archive_path=archive_path,
            destination_path=tmp_path / "dest",
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            total_files=0,
            extracted_files=0,
            total_bytes=0,
            extracted_bytes=0,
            created_at=datetime.now()
        )
        
        success = engine.extract_archive(task)
        
        # Should fail or skip malicious file
        assert not (Path("/etc/passwd").exists() and 
                   Path("/etc/passwd").read_text() == "malicious")
    
    def test_disk_space_check(self, engine, tmp_path):
        """Test that extraction fails when disk space insufficient"""
        # This test would require mocking disk space checks
        pass
    
    def test_conflict_resolution_overwrite(self, engine, sample_archive, tmp_path):
        """Test overwrite conflict resolution"""
        dest = tmp_path / "extracted"
        dest.mkdir()
        (dest / "test").mkdir()
        (dest / "test" / "file1.txt").write_text("existing")
        
        task = ExtractionTask(
            task_id="test-3",
            archive_path=sample_archive,
            destination_path=dest,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            total_files=0,
            extracted_files=0,
            total_bytes=0,
            extracted_bytes=0,
            created_at=datetime.now(),
            create_root_folder=True
        )
        
        engine.extract_archive(task)
        
        # File should be overwritten
        assert (dest / "test" / "file1.txt").read_text() == "content1"
    
    def test_conflict_resolution_skip(self, engine, sample_archive, tmp_path):
        """Test skip conflict resolution"""
        dest = tmp_path / "extracted"
        dest.mkdir()
        (dest / "test").mkdir()
        (dest / "test" / "file1.txt").write_text("existing")
        
        task = ExtractionTask(
            task_id="test-4",
            archive_path=sample_archive,
            destination_path=dest,
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.SKIP,
            total_files=0,
            extracted_files=0,
            total_bytes=0,
            extracted_bytes=0,
            created_at=datetime.now(),
            create_root_folder=True
        )
        
        engine.extract_archive(task)
        
        # File should NOT be overwritten
        assert (dest / "test" / "file1.txt").read_text() == "existing"
    
    def test_cancellation(self, engine, tmp_path):
        """Test that extraction can be cancelled"""
        # Create large archive
        archive_path = tmp_path / "large.zip"
        with ZipFile(archive_path, 'w') as zf:
            for i in range(1000):
                zf.writestr(f"file{i}.txt", "x" * 10000)
        
        task = ExtractionTask(
            task_id="test-5",
            archive_path=archive_path,
            destination_path=tmp_path / "dest",
            status=TaskStatus.QUEUED,
            conflict_resolution=ConflictResolution.OVERWRITE,
            total_files=0,
            extracted_files=0,
            total_bytes=0,
            extracted_bytes=0,
            created_at=datetime.now()
        )
        
        # Start extraction in thread
        import threading
        thread = threading.Thread(
            target=engine.extract_archive,
            args=(task,)
        )
        thread.start()
        
        # Cancel after short delay
        time.sleep(0.1)
        engine.should_cancel = True
        thread.join()
        
        assert task.status == TaskStatus.CANCELLED
```

#### 9.2.2 Archive Validation Tests
```python
class TestArchiveValidation:
    """Test archive validation functionality"""
    
    def test_valid_archive(self, tmp_path):
        """Test validation of valid archive"""
        archive = tmp_path / "valid.zip"
        with ZipFile(archive, 'w') as zf:
            zf.writestr("test.txt", "content")
        
        is_valid, error = validate_archive(archive)
        assert is_valid
        assert error is None
    
    def test_corrupted_archive(self, tmp_path):
        """Test detection of corrupted archive"""
        archive = tmp_path / "corrupt.zip"
        archive.write_bytes(b"not a zip file")
        
        is_valid, error = validate_archive(archive)
        assert not is_valid
        assert "Invalid ZIP" in error
    
    def test_empty_file(self, tmp_path):
        """Test detection of empty file"""
        archive = tmp_path / "empty.zip"
        archive.touch()
        
        is_valid, error = validate_archive(archive)
        assert not is_valid
        assert "empty" in error.lower()
    
    def test_nonexistent_file(self, tmp_path):
        """Test handling of nonexistent file"""
        archive = tmp_path / "nonexistent.zip"
        
        is_valid, error = validate_archive(archive)
        assert not is_valid
        assert "not found" in error.lower()
```

### 9.3 Integration Test Cases

#### 9.3.1 End-to-End Extraction Flow
```python
class TestExtractionFlow:
    """Test complete extraction workflows"""
    
    def test_single_file_extraction_flow(self, tmp_path):
        """Test complete flow: select → validate → extract → verify"""
        # Setup
        archive = create_test_archive(tmp_path, file_count=5)
        dest = tmp_path / "output"
        
        # Validate
        is_valid, _ = validate_archive(archive)
        assert is_valid
        
        # Get info
        info = get_archive_info(archive)
        assert info.file_count == 5
        
        # Create task
        task = create_extraction_task(archive, dest)
        
        # Extract
        engine = ExtractionEngine()
        success = engine.extract_archive(task)
        
        assert success
        assert task.status == TaskStatus.COMPLETED
        assert task.extracted_files == 5
        
        # Verify output
        assert dest.exists()
        assert len(list(dest.rglob("*.*"))) == 5
    
    def test_batch_extraction_flow(self, tmp_path):
        """Test batch extraction workflow"""
        # Create multiple archives
        archives = [
            create_test_archive(tmp_path, f"archive{i}.zip", 3)
            for i in range(3)
        ]
        
        dest = tmp_path / "output"
        
        # Create tasks
        tasks = [
            create_extraction_task(arch, dest)
            for arch in archives
        ]
        
        # Batch extract
        manager = BatchExtractionManager(max_workers=2)
        results = manager.extract_batch(tasks)
        
        # Verify
        assert all(results.values())
        assert len(list(dest.rglob("*.*"))) == 9  # 3 archives * 3 files
```

### 9.4 Performance Benchmarks

```python
import pytest
import time

class TestPerformance:
    """Performance benchmark tests"""
    
    @pytest.mark.benchmark
    def test_extraction_speed_small_files(self, benchmark, tmp_path):
        """Benchmark extraction of many small files"""
        archive = create_test_archive(
            tmp_path,
            file_count=1000,
            file_size=1024  # 1KB each
        )
        
        def extract():
            task = create_extraction_task(archive, tmp_path / "out")
            engine = ExtractionEngine()
            engine.extract_archive(task)
        
        result = benchmark(extract)
        
        # Should complete in under 5 seconds
        assert result.stats.mean < 5.0
    
    @pytest.mark.benchmark
    def test_extraction_speed_large_file(self, benchmark, tmp_path):
        """Benchmark extraction of single large file"""
        archive = create_test_archive(
            tmp_path,
            file_count=1,
            file_size=100 * 1024 * 1024  # 100MB
        )
        
        def extract():
            task = create_extraction_task(archive, tmp_path / "out")
            engine = ExtractionEngine()
            engine.extract_archive(task)
        
        result = benchmark(extract)
        
        # Should achieve at least 50 MB/s
        speed_mbps = (100 * 1024 * 1024) / result.stats.mean / (1024 * 1024)
        assert speed_mbps >= 50
    
    @pytest.mark.benchmark
    def test_archive_validation_speed(self, benchmark, tmp_path):
        """Benchmark archive validation performance"""
        archive = create_test_archive(tmp_path, file_count=100)
        
        result = benchmark(validate_archive, archive)
        
        # Validation should be fast
        assert result.stats.mean < 0.1  # 100ms
```

### 9.5 UI Test Cases

```python
# Using Dogtail for GTK UI testing
from dogtail.tree import root
from dogtail.utils import run

class TestUI:
    """UI interaction tests"""
    
    def test_main_window_opens(self):
        """Test main window launches successfully"""
        app = run('zipextractor')
        window = app.window('ZIP Extractor')
        assert window.showing
    
    def test_add_file_button(self):
        """Test Add Files button opens file chooser"""
        app = run('zipextractor')
        window = app.window('ZIP Extractor')
        
        add_button = window.button('Add Files')
        add_button.click()
        
        # File chooser should appear
        chooser = app.dialog('Select ZIP Archives')
        assert chooser.showing
        
        chooser.button('Cancel').click()
    
    def test_drag_drop_file(self):
        """Test drag-and-drop functionality"""
        # This would require simulating drag-drop events
        pass
    
    def test_extraction_progress_display(self):
        """Test progress dialog updates during extraction"""
        # Start extraction and verify progress dialog appears
        pass
```

---

## 10. Deployment & Distribution

### 10.1 Package Structure

```
zipextractor/
├── debian/
│   ├── control              # Package metadata
│   ├── rules                # Build rules
│   ├── changelog            # Version history
│   ├── copyright            # License information
│   └── zipextractor.desktop # Desktop entry
├── src/
│   └── zipextractor/
│       ├── __init__.py
│       ├── __main__.py      # Entry point
│       ├── core/
│       │   ├── __init__.py
│       │   ├── extraction.py
│       │   ├── validation.py
│       │   └── progress.py
│       ├── gui/
│       │   ├── __init__.py
│       │   ├── main_window.py
│       │   ├── progress_dialog.py
│       │   └── settings_dialog.py
│       └── utils/
│           ├── __init__.py
│           ├── config.py
│           └── logging.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── ui/
├── resources/
│   ├── icons/
│   │   ├── hicolor/
│   │   │   ├── 16x16/
│   │   │   ├── 32x32/
│   │   │   ├── 48x48/
│   │   │   ├── 128x128/
│   │   │   └── scalable/
│   │   └── zipextractor.svg
│   └── locale/
│       ├── en/
│       ├── es/
│       ├── fr/
│       └── de/
├── docs/
│   ├── user_guide.md
│   ├── api.md
│   └── contributing.md
├── setup.py
├── requirements.txt
├── README.md
├── LICENSE
└── CHANGELOG.md
```

### 10.2 Debian Package Configuration

#### 10.2.1 control file
```
Source: zipextractor
Section: utils
Priority: optional
Maintainer: Your Name <your.email@example.com>
Build-Depends: debhelper (>= 12),
               dh-python,
               python3-all,
               python3-setuptools,
               python3-gi,
               gir1.2-gtk-4.0,
               gir1.2-adw-1
Standards-Version: 4.5.0
Homepage: https://github.com/yourusername/zipextractor

Package: zipextractor
Architecture: all
Depends: ${python3:Depends},
         ${misc:Depends},
         python3-gi,
         gir1.2-gtk-4.0,
         gir1.2-adw-1,
         libzip4
Description: Modern ZIP archive extraction utility
 ZIP Extractor is a user-friendly desktop application for extracting
 ZIP archives on Ubuntu Linux. Features include:
  * Intuitive drag-and-drop interface
  * Batch extraction support
  * Real-time progress tracking
  * Automatic conflict resolution
  * Archive content preview
```

#### 10.2.2 Desktop Entry
```ini
[Desktop Entry]
Type=Application
Name=ZIP Extractor
GenericName=Archive Extractor
Comment=Extract ZIP archives with ease
Icon=zipextractor
Exec=zipextractor %F
Terminal=false
Categories=Utility;Archiving;GTK;
MimeType=application/zip;
Keywords=zip;extract;archive;unzip;
StartupNotify=true
```

### 10.3 Installation Process

#### 10.3.1 Build Instructions
```bash
# Install build dependencies
sudo apt-get install debhelper dh-python python3-all python3-setuptools

# Build package
cd zipextractor
dpkg-buildpackage -us -uc -b

# Install package
sudo dpkg -i ../zipextractor_1.0.0_all.deb

# Install dependencies (if needed)
sudo apt-get install -f
```

#### 10.3.2 Installation Locations
```
/usr/bin/zipextractor                    # Executable
/usr/lib/python3/dist-packages/          # Python modules
/usr/share/applications/                 # Desktop entry
/usr/share/icons/hicolor/                # Application icons
/usr/share/doc/zipextractor/             # Documentation
/usr/share/locale/                       # Translations
```

### 10.4 Update & Versioning

#### 10.4.1 Version Scheme
- Format: MAJOR.MINOR.PATCH
- Example: 1.0.0
  - MAJOR: Breaking changes
  - MINOR: New features (backward compatible)
  - PATCH: Bug fixes

#### 10.4.2 Changelog Format
```markdown
# Changelog

## [1.0.0] - 2025-01-15

### Added
- Initial release
- Single file extraction
- Batch processing
- Real-time progress tracking
- Archive preview
- Settings persistence

### Fixed
- None (initial release)

### Changed
- None (initial release)
```

---

## 11. Security & Compliance

### 11.1 Security Features

#### 11.1.1 Path Sanitization
- All file paths validated before extraction
- Path traversal attempts blocked
- Absolute paths rejected
- Symbolic links handled safely

#### 11.1.2 Resource Limits
- Maximum archive size: 10 GB
- Maximum file count: 100,000 files
- Maximum path depth: 50 levels
- Compression ratio limit: 100:1 (ZIP bomb detection)

#### 11.1.3 File Permissions
- Settings file: 0600 (user read/write only)
- Log files: 0640 (user read/write, group read)
- Extracted files: Preserve original or 0644 default

### 11.2 Data Privacy

- No telemetry or analytics
- No network communication (fully offline)
- Settings stored locally only
- No personally identifiable information collected

### 11.3 License & Copyright

- License: GPL-3.0
- Copyright: © 2025 Your Name
- Third-party libraries: Properly attributed in NOTICE file

---

## Appendix A: Configuration Example

```json
{
  "version": "1.0",
  "extraction": {
    "default_destination": "~/Downloads",
    "conflict_resolution": "ask",
    "create_root_folder": true,
    "preserve_permissions": true,
    "preserve_timestamps": true
  },
  "behavior": {
    "confirm_before_extraction": false,
    "show_completion_notification": true,
    "close_window_after_extraction": false,
    "remember_last_destination": true
  },
  "performance": {
    "max_concurrent_extractions": 4,
    "buffer_size_mb": 8
  },
  "ui": {
    "window_width": 800,
    "window_height": 600,
    "window_maximized": false,
    "show_hidden_files": false,
    "dark_mode": null
  }
}
```

---

## Appendix B: Development Roadmap

### Phase 1: MVP (v1.0) - 4-6 weeks
- Core extraction engine
- Basic GTK4 UI
- Single & batch extraction
- Progress tracking
- Settings management

### Phase 2: Polish (v1.1) - 2-3 weeks
- Archive preview
- Enhanced error handling
- System tray integration
- Keyboard shortcuts
- Accessibility improvements

### Phase 3: Advanced Features (v1.2+) - Ongoing
- Password-protected archives
- Multi-format support (plugins)
- Archive creation
- Custom profiles
- File manager integration

---

*End of Technical Specification Document*

**Estimated Development Time**: 6-10 weeks for MVP

**Complexity Level**: Medium (suitable for single developer)

**Dependencies**: Minimal (GTK4, libzip, Python standard library)
