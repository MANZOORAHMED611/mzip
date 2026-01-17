#!/usr/bin/env python3
"""Entry point for ZIP Extractor application.

This module provides the main entry point when running the application
via `python -m zipextractor` or the installed `zipextractor` command.
"""
from __future__ import annotations

import sys


def main() -> int:
    """Main entry point for the ZIP Extractor application.

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    # Import here to avoid slow startup for --help
    from zipextractor.app import ZipExtractorApp

    app = ZipExtractorApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
