# MZip

Modern ZIP archive extraction utility for Ubuntu Linux with both GUI and CLI interfaces. Complete at v1.0.0.

## Tech Stack
- **Language:** Python 3.10+
- **GUI:** PyGObject (GTK) 3.42.0+
- **CLI:** Click 8.1.0+, Rich (progress/output)
- **Archive libs:** py7zr, rarfile, zstandard
- **Testing:** pytest 7.4.0+
- **Linting:** Ruff, Black, mypy (strict mode)
- **Packaging:** setuptools via pyproject.toml

## Supported Formats
ZIP, 7Z, RAR, ZSTD

## Build & Run
```bash
pip install -e ".[dev]"   # Install in editable mode with dev deps
mzip --help               # CLI usage
mzip-gui                  # Launch GTK GUI
pytest                    # Run tests
pytest --cov              # Run tests with coverage
ruff check .              # Lint
black --check .           # Format check
mypy .                    # Type check (strict)
```

## Key Patterns
- Dual interface: GTK GUI and Rich CLI share the same extraction backend
- Parallel extraction for multi-file archives
- Progress tracking callbacks shared between GUI and CLI
- Format detection is content-based (magic bytes), not extension-based

## Code Quality Requirements
- 85%+ test coverage required
- mypy strict mode with no ignores
- Ruff and Black must pass with zero warnings
- All public functions require type hints and docstrings

## Gotchas
- RAR extraction requires `unrar` system package installed (`sudo apt install unrar`)
- GTK imports fail headless; tests that touch GUI need display mocking or Xvfb
- ZSTD files can be standalone compressed files or tar.zst; handle both
- Parallel extraction thread count should respect system core count
- pyproject.toml is the single source of truth for version and dependencies
