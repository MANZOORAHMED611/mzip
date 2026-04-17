"""Archive search functionality.

This module provides tools to search within archives by filename,
content, size, date, and other criteria.
"""

from __future__ import annotations

import fnmatch
import re
import tarfile
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path

from zipextractor.core.formats import detect_format
from zipextractor.core.models import ArchiveFormat
from zipextractor.utils.logging import get_logger

logger = get_logger(__name__)


class SearchType(Enum):
    """Type of search to perform."""

    FILENAME = auto()  # Search by filename pattern
    CONTENT = auto()  # Search file contents
    SIZE = auto()  # Search by file size
    DATE = auto()  # Search by modification date
    EXTENSION = auto()  # Search by file extension


class SizeOperator(Enum):
    """Size comparison operators."""

    EQUAL = auto()
    GREATER = auto()
    LESS = auto()
    GREATER_EQUAL = auto()
    LESS_EQUAL = auto()
    BETWEEN = auto()


class DateOperator(Enum):
    """Date comparison operators."""

    BEFORE = auto()
    AFTER = auto()
    ON = auto()
    BETWEEN = auto()


@dataclass
class SearchCriteria:
    """Criteria for searching within archives.

    Attributes:
        pattern: Filename pattern (glob or regex).
        use_regex: Whether pattern is a regex.
        case_sensitive: Whether search is case sensitive.
        content_pattern: Pattern to search in file contents.
        extensions: List of file extensions to match.
        size_min: Minimum file size in bytes.
        size_max: Maximum file size in bytes.
        size_operator: Size comparison operator.
        date_after: Match files modified after this date.
        date_before: Match files modified before this date.
        include_directories: Whether to include directories in results.
    """

    pattern: str | None = None
    use_regex: bool = False
    case_sensitive: bool = False
    content_pattern: str | None = None
    extensions: list[str] = field(default_factory=list)
    size_min: int | None = None
    size_max: int | None = None
    size_operator: SizeOperator = SizeOperator.BETWEEN
    date_after: datetime | None = None
    date_before: datetime | None = None
    include_directories: bool = False

    def __post_init__(self) -> None:
        """Normalize extensions to lowercase with leading dot."""
        self.extensions = [
            ext.lower() if ext.startswith(".") else f".{ext.lower()}"
            for ext in self.extensions
        ]


@dataclass
class SearchResult:
    """Result of searching an archive file.

    Attributes:
        filename: Name of the matching file.
        path: Full path within archive.
        size: File size in bytes.
        compressed_size: Compressed size in bytes.
        modified: Modification timestamp.
        is_directory: Whether this is a directory.
        match_type: Type of match found.
        content_matches: List of content match locations.
    """

    filename: str
    path: str
    size: int = 0
    compressed_size: int = 0
    modified: datetime | None = None
    is_directory: bool = False
    match_type: SearchType = SearchType.FILENAME
    content_matches: list[ContentMatch] = field(default_factory=list)


@dataclass
class ContentMatch:
    """Location of content match within a file.

    Attributes:
        line_number: Line number (1-based).
        column: Column position (0-based).
        line_text: The matching line text.
        match_text: The actual matched text.
    """

    line_number: int
    column: int
    line_text: str
    match_text: str


@dataclass
class SearchSummary:
    """Summary of search results.

    Attributes:
        archive_path: Path to the searched archive.
        criteria: Search criteria used.
        results: List of matching files.
        total_files_searched: Total files examined.
        total_matches: Number of matches found.
        search_time_seconds: Time taken for search.
        errors: List of errors encountered.
    """

    archive_path: Path
    criteria: SearchCriteria
    results: list[SearchResult] = field(default_factory=list)
    total_files_searched: int = 0
    total_matches: int = 0
    search_time_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def has_matches(self) -> bool:
        """Check if any matches were found."""
        return len(self.results) > 0


class ArchiveSearcher:
    """Search within archive files.

    Supports searching by filename patterns, file contents,
    size, date, and file extensions.
    """

    # Maximum file size to search content (prevent memory issues)
    MAX_CONTENT_SEARCH_SIZE = 10 * 1024 * 1024  # 10 MB

    def __init__(self, password: str | None = None) -> None:
        """Initialize searcher.

        Args:
            password: Password for encrypted archives.
        """
        self._password = password
        self._cancelled = False

    def cancel(self) -> None:
        """Cancel ongoing search."""
        self._cancelled = True

    def search(
        self,
        archive_path: Path,
        criteria: SearchCriteria,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> SearchSummary:
        """Search within an archive.

        Args:
            archive_path: Path to the archive.
            criteria: Search criteria.
            progress_callback: Optional callback(filename, current, total).

        Returns:
            SearchSummary with results.
        """
        import time  # noqa: PLC0415

        self._cancelled = False
        start_time = time.time()

        fmt = detect_format(archive_path)
        if fmt is None:
            return SearchSummary(
                archive_path=archive_path,
                criteria=criteria,
                errors=["Unknown archive format"],
            )

        # Route to appropriate searcher
        if fmt == ArchiveFormat.ZIP:
            summary = self._search_zip(archive_path, criteria, progress_callback)
        elif fmt in (
            ArchiveFormat.TAR,
            ArchiveFormat.TAR_GZ,
            ArchiveFormat.TAR_BZ2,
            ArchiveFormat.TAR_XZ,
        ):
            summary = self._search_tar(archive_path, fmt, criteria, progress_callback)
        else:
            summary = SearchSummary(
                archive_path=archive_path,
                criteria=criteria,
                errors=[f"Search not supported for {fmt.name}"],
            )

        summary.search_time_seconds = time.time() - start_time
        return summary

    def _search_zip(
        self,
        archive_path: Path,
        criteria: SearchCriteria,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> SearchSummary:
        """Search within a ZIP archive."""
        results: list[SearchResult] = []
        errors: list[str] = []

        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                members = zf.infolist()
                total = len(members)
                files_searched = 0

                for i, member in enumerate(members):
                    if self._cancelled:
                        break

                    if progress_callback:
                        progress_callback(member.filename, i, total)

                    # Skip directories unless requested
                    if member.is_dir() and not criteria.include_directories:
                        continue

                    files_searched += 1

                    # Check if file matches criteria
                    match_result = self._check_match_zip(zf, member, criteria)
                    if match_result:
                        results.append(match_result)

                if progress_callback:
                    progress_callback("", total, total)

        except zipfile.BadZipFile as e:
            errors.append(f"Invalid ZIP file: {e}")
        except Exception as e:
            errors.append(f"Search error: {e}")

        return SearchSummary(
            archive_path=archive_path,
            criteria=criteria,
            results=results,
            total_files_searched=files_searched,
            total_matches=len(results),
            errors=errors,
        )

    def _check_match_zip(  # noqa: PLR0911
        self,
        zf: zipfile.ZipFile,
        member: zipfile.ZipInfo,
        criteria: SearchCriteria,
    ) -> SearchResult | None:
        """Check if a ZIP member matches search criteria."""
        filename = Path(member.filename).name
        path = member.filename
        size = member.file_size
        compressed_size = member.compress_size
        is_dir = member.is_dir()

        # Parse modification time
        try:
            modified = datetime(*member.date_time)
        except (ValueError, TypeError):
            modified = None

        # Check filename pattern
        if criteria.pattern and not self._matches_pattern(
            filename, criteria.pattern, criteria.use_regex, criteria.case_sensitive
        ) and not self._matches_pattern(
            path, criteria.pattern, criteria.use_regex, criteria.case_sensitive
        ):
            return None

        # Check extension
        if criteria.extensions:
            ext = Path(filename).suffix.lower()
            if ext not in criteria.extensions:
                return None

        # Check size
        if not self._matches_size(size, criteria):
            return None

        # Check date
        if not self._matches_date(modified, criteria):
            return None

        # Check content (only for files)
        content_matches: list[ContentMatch] = []
        if criteria.content_pattern and not is_dir:
            if size <= self.MAX_CONTENT_SEARCH_SIZE:
                try:
                    pwd = self._password.encode() if self._password else None
                    data = zf.read(member.filename, pwd=pwd)
                    content_matches = self._search_content(
                        data, criteria.content_pattern, criteria.case_sensitive
                    )
                    if not content_matches:
                        return None
                except Exception:
                    # Skip files that can't be read for content search
                    return None
            else:
                # Skip large files for content search
                return None

        return SearchResult(
            filename=filename,
            path=path,
            size=size,
            compressed_size=compressed_size,
            modified=modified,
            is_directory=is_dir,
            match_type=(
                SearchType.CONTENT if content_matches else SearchType.FILENAME
            ),
            content_matches=content_matches,
        )

    def _search_tar(
        self,
        archive_path: Path,
        fmt: ArchiveFormat,
        criteria: SearchCriteria,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> SearchSummary:
        """Search within a TAR archive."""
        results: list[SearchResult] = []
        errors: list[str] = []

        mode_map = {
            ArchiveFormat.TAR: "r",
            ArchiveFormat.TAR_GZ: "r:gz",
            ArchiveFormat.TAR_BZ2: "r:bz2",
            ArchiveFormat.TAR_XZ: "r:xz",
        }
        mode = mode_map.get(fmt, "r")

        try:
            with tarfile.open(str(archive_path), mode) as tf:  # type: ignore[call-overload]
                members = tf.getmembers()
                total = len(members)
                files_searched = 0

                for i, member in enumerate(members):
                    if self._cancelled:
                        break

                    if progress_callback:
                        progress_callback(member.name, i, total)

                    # Skip directories unless requested
                    if member.isdir() and not criteria.include_directories:
                        continue

                    files_searched += 1

                    # Check if file matches criteria
                    match_result = self._check_match_tar(tf, member, criteria)
                    if match_result:
                        results.append(match_result)

                if progress_callback:
                    progress_callback("", total, total)

        except tarfile.TarError as e:
            errors.append(f"Invalid TAR file: {e}")
        except Exception as e:
            errors.append(f"Search error: {e}")

        return SearchSummary(
            archive_path=archive_path,
            criteria=criteria,
            results=results,
            total_files_searched=files_searched,
            total_matches=len(results),
            errors=errors,
        )

    def _check_match_tar(  # noqa: PLR0911
        self,
        tf: tarfile.TarFile,
        member: tarfile.TarInfo,
        criteria: SearchCriteria,
    ) -> SearchResult | None:
        """Check if a TAR member matches search criteria."""
        filename = Path(member.name).name
        path = member.name
        size = member.size
        is_dir = member.isdir()

        # Parse modification time
        try:
            modified = datetime.fromtimestamp(member.mtime)
        except (ValueError, TypeError, OSError):
            modified = None

        # Check filename pattern
        if criteria.pattern and not self._matches_pattern(
            filename, criteria.pattern, criteria.use_regex, criteria.case_sensitive
        ) and not self._matches_pattern(
            path, criteria.pattern, criteria.use_regex, criteria.case_sensitive
        ):
            return None

        # Check extension
        if criteria.extensions:
            ext = Path(filename).suffix.lower()
            if ext not in criteria.extensions:
                return None

        # Check size
        if not self._matches_size(size, criteria):
            return None

        # Check date
        if not self._matches_date(modified, criteria):
            return None

        # Check content
        content_matches: list[ContentMatch] = []
        if criteria.content_pattern and not is_dir and member.isfile():
            if size <= self.MAX_CONTENT_SEARCH_SIZE:
                try:
                    extracted = tf.extractfile(member)
                    if extracted:
                        data = extracted.read()
                        content_matches = self._search_content(
                            data, criteria.content_pattern, criteria.case_sensitive
                        )
                        if not content_matches:
                            return None
                except Exception:
                    return None
            else:
                return None

        return SearchResult(
            filename=filename,
            path=path,
            size=size,
            compressed_size=size,  # TAR doesn't store compressed size
            modified=modified,
            is_directory=is_dir,
            match_type=(
                SearchType.CONTENT if content_matches else SearchType.FILENAME
            ),
            content_matches=content_matches,
        )

    def _matches_pattern(
        self,
        text: str,
        pattern: str,
        use_regex: bool,
        case_sensitive: bool,
    ) -> bool:
        """Check if text matches pattern."""
        if use_regex:
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                return bool(re.search(pattern, text, flags))
            except re.error:
                return False
        else:
            # Use fnmatch for glob patterns
            if not case_sensitive:
                text = text.lower()
                pattern = pattern.lower()
            return fnmatch.fnmatch(text, pattern)

    def _matches_size(self, size: int, criteria: SearchCriteria) -> bool:  # noqa: PLR0911
        """Check if size matches criteria."""
        if criteria.size_min is None and criteria.size_max is None:
            return True

        if criteria.size_operator == SizeOperator.BETWEEN:
            min_ok = criteria.size_min is None or size >= criteria.size_min
            max_ok = criteria.size_max is None or size <= criteria.size_max
            return min_ok and max_ok
        if criteria.size_operator == SizeOperator.GREATER:
            return criteria.size_min is not None and size > criteria.size_min
        if criteria.size_operator == SizeOperator.LESS:
            return criteria.size_max is not None and size < criteria.size_max
        if criteria.size_operator == SizeOperator.GREATER_EQUAL:
            return criteria.size_min is not None and size >= criteria.size_min
        if criteria.size_operator == SizeOperator.LESS_EQUAL:
            return criteria.size_max is not None and size <= criteria.size_max
        if criteria.size_operator == SizeOperator.EQUAL:
            return criteria.size_min is not None and size == criteria.size_min

        return True  # type: ignore[unreachable]

    def _matches_date(
        self, modified: datetime | None, criteria: SearchCriteria
    ) -> bool:
        """Check if date matches criteria."""
        if criteria.date_after is None and criteria.date_before is None:
            return True

        if modified is None:
            return False

        after_ok = criteria.date_after is None or modified >= criteria.date_after
        before_ok = criteria.date_before is None or modified <= criteria.date_before
        return after_ok and before_ok

    def _search_content(
        self, data: bytes, pattern: str, case_sensitive: bool
    ) -> list[ContentMatch]:
        """Search for pattern in file content."""
        matches: list[ContentMatch] = []

        try:
            # Try to decode as text
            text = data.decode("utf-8", errors="replace")
        except Exception:
            return matches

        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
        except re.error:
            return matches

        lines = text.splitlines()
        for line_num, line in enumerate(lines, 1):
            for match in regex.finditer(line):
                matches.append(
                    ContentMatch(
                        line_number=line_num,
                        column=match.start(),
                        line_text=line[:200],  # Limit line length
                        match_text=match.group(),
                    )
                )

        return matches


def search_archive(
    archive_path: Path | str,
    pattern: str | None = None,
    content: str | None = None,
    extensions: list[str] | None = None,
    size_min: int | None = None,
    size_max: int | None = None,
    date_after: datetime | None = None,
    date_before: datetime | None = None,
    use_regex: bool = False,
    case_sensitive: bool = False,
    password: str | None = None,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> SearchSummary:
    """Search within an archive.

    Args:
        archive_path: Path to the archive.
        pattern: Filename pattern (glob or regex).
        content: Content pattern to search.
        extensions: File extensions to match.
        size_min: Minimum file size.
        size_max: Maximum file size.
        date_after: Match files modified after this date.
        date_before: Match files modified before this date.
        use_regex: Whether patterns are regex.
        case_sensitive: Whether search is case sensitive.
        password: Password for encrypted archives.
        progress_callback: Optional progress callback.

    Returns:
        SearchSummary with results.
    """
    if isinstance(archive_path, str):
        archive_path = Path(archive_path)

    criteria = SearchCriteria(
        pattern=pattern,
        use_regex=use_regex,
        case_sensitive=case_sensitive,
        content_pattern=content,
        extensions=extensions or [],
        size_min=size_min,
        size_max=size_max,
        date_after=date_after,
        date_before=date_before,
    )

    searcher = ArchiveSearcher(password=password)
    return searcher.search(archive_path, criteria, progress_callback)


def find_files(
    archive_path: Path | str,
    pattern: str,
    password: str | None = None,
) -> list[str]:
    """Find files matching pattern in archive.

    Args:
        archive_path: Path to the archive.
        pattern: Filename pattern (glob).
        password: Password for encrypted archives.

    Returns:
        List of matching file paths.
    """
    summary = search_archive(archive_path, pattern=pattern, password=password)
    return [r.path for r in summary.results]


def grep_archive(
    archive_path: Path | str,
    pattern: str,
    password: str | None = None,
    case_sensitive: bool = False,
) -> Iterator[tuple[str, list[ContentMatch]]]:
    """Search for pattern in archive file contents.

    Args:
        archive_path: Path to the archive.
        pattern: Content pattern (regex).
        password: Password for encrypted archives.
        case_sensitive: Whether search is case sensitive.

    Yields:
        Tuples of (filename, matches).
    """
    summary = search_archive(
        archive_path,
        content=pattern,
        use_regex=True,
        case_sensitive=case_sensitive,
        password=password,
    )

    for result in summary.results:
        if result.content_matches:
            yield result.path, result.content_matches


def list_by_extension(
    archive_path: Path | str,
    extensions: list[str],
    password: str | None = None,
) -> dict[str, list[str]]:
    """List files grouped by extension.

    Args:
        archive_path: Path to the archive.
        extensions: Extensions to look for.
        password: Password for encrypted archives.

    Returns:
        Dict mapping extension to list of file paths.
    """
    result: dict[str, list[str]] = {ext: [] for ext in extensions}

    for ext in extensions:
        summary = search_archive(
            archive_path, extensions=[ext], password=password
        )
        normalized_ext = ext.lower() if ext.startswith(".") else f".{ext.lower()}"
        result[normalized_ext] = [r.path for r in summary.results]

    return result


def list_large_files(
    archive_path: Path | str,
    min_size: int,
    password: str | None = None,
) -> list[SearchResult]:
    """List files larger than specified size.

    Args:
        archive_path: Path to the archive.
        min_size: Minimum size in bytes.
        password: Password for encrypted archives.

    Returns:
        List of SearchResult for large files.
    """
    summary = search_archive(
        archive_path,
        size_min=min_size,
        password=password,
    )
    # Sort by size descending
    return sorted(summary.results, key=lambda r: r.size, reverse=True)


def list_recent_files(
    archive_path: Path | str,
    since: datetime,
    password: str | None = None,
) -> list[SearchResult]:
    """List files modified since specified date.

    Args:
        archive_path: Path to the archive.
        since: Date threshold.
        password: Password for encrypted archives.

    Returns:
        List of SearchResult for recent files.
    """
    summary = search_archive(
        archive_path,
        date_after=since,
        password=password,
    )
    # Sort by date descending
    return sorted(
        summary.results,
        key=lambda r: r.modified or datetime.min,
        reverse=True,
    )
