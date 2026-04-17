"""Tests for advanced archive features (Phase 6D)."""

from __future__ import annotations

import tarfile
import tempfile
import zipfile
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from zipextractor.core.comparison import (
    CompareMethod,
    DifferenceType,
    archives_are_identical,
    compare_archives,
    generate_diff_report,
    get_added_files,
    get_modified_files,
    get_removed_files,
)
from zipextractor.core.repair import (
    DamageType,
    RepairStatus,
    ZipRepairer,
    can_repair,
    diagnose_archive,
    repair_archive,
)
from zipextractor.core.search import (
    ArchiveSearcher,
    SearchCriteria,
    SearchType,
    SizeOperator,
    find_files,
    grep_archive,
    list_by_extension,
    list_large_files,
    search_archive,
)
from zipextractor.core.split_archive import (
    ArchiveJoiner,
    ArchiveSplitter,
    is_split_archive,
    join_parts,
    split_file,
)
from zipextractor.core.testing import (
    ArchiveTester,
    TestStatus,
    TestType,
    quick_test,
    verify_archive,
)


class TestArchiveTester:
    """Tests for archive integrity testing."""

    @pytest.fixture
    def sample_zip(self) -> Iterator[Path]:
        """Create a sample ZIP file."""
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            path = Path(f.name)

        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("file1.txt", "Content of file 1")
            zf.writestr("file2.txt", "Content of file 2")
            zf.writestr("subdir/file3.txt", "Content of file 3")

        yield path
        path.unlink()

    @pytest.fixture
    def sample_tar(self) -> Iterator[Path]:
        """Create a sample TAR file."""
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as f:
            path = Path(f.name)

        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "file1.txt"
            file1.write_text("Content of file 1")

            with tarfile.open(str(path), "w") as tf:
                tf.add(str(file1), arcname="file1.txt")

        yield path
        path.unlink()

    def test_test_valid_zip(self, sample_zip: Path) -> None:
        """Test that valid ZIP passes integrity test."""
        result = verify_archive(sample_zip)
        assert result.is_valid
        assert result.status == TestStatus.PASSED
        assert result.total_files == 3
        assert result.passed_files == 3
        assert result.failed_files == 0

    def test_test_valid_tar(self, sample_tar: Path) -> None:
        """Test that valid TAR passes integrity test."""
        result = verify_archive(sample_tar)
        assert result.is_valid
        assert result.status == TestStatus.PASSED

    def test_quick_test_valid(self, sample_zip: Path) -> None:
        """Test quick_test returns True for valid archive."""
        assert quick_test(sample_zip) is True

    def test_test_crc_verification(self, sample_zip: Path) -> None:
        """Test CRC verification."""
        tester = ArchiveTester(verify_crc=True)
        result = tester.test(sample_zip)
        assert result.is_valid
        for file_result in result.file_results:
            assert file_result.test_type == TestType.CRC
            assert file_result.expected_crc is not None
            assert file_result.actual_crc is not None

    def test_test_nonexistent_file(self) -> None:
        """Test testing nonexistent file."""
        result = verify_archive(Path("/nonexistent/archive.zip"))
        assert result.status == TestStatus.FAILED

    def test_test_pass_rate(self, sample_zip: Path) -> None:
        """Test pass rate calculation."""
        result = verify_archive(sample_zip)
        assert result.pass_rate == 100.0


class TestArchiveSearch:
    """Tests for archive search functionality."""

    @pytest.fixture
    def search_zip(self) -> Iterator[Path]:
        """Create a ZIP file for search tests."""
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            path = Path(f.name)

        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("readme.txt", "This is a readme file")
            zf.writestr("data.csv", "name,value\ntest,123")
            zf.writestr("src/main.py", "print('Hello World')")
            zf.writestr("src/utils.py", "def helper(): pass")
            zf.writestr("docs/manual.txt", "User manual content")
            zf.writestr("large_file.bin", "x" * 10000)

        yield path
        path.unlink()

    def test_search_by_filename_pattern(self, search_zip: Path) -> None:
        """Test searching by filename glob pattern."""
        summary = search_archive(search_zip, pattern="*.txt")
        assert summary.has_matches
        assert summary.total_matches == 2
        paths = [r.path for r in summary.results]
        assert "readme.txt" in paths
        assert "docs/manual.txt" in paths

    def test_search_by_extension(self, search_zip: Path) -> None:
        """Test searching by file extension."""
        summary = search_archive(search_zip, extensions=[".py"])
        assert summary.total_matches == 2
        for result in summary.results:
            assert result.path.endswith(".py")

    def test_search_by_content(self, search_zip: Path) -> None:
        """Test searching file contents."""
        summary = search_archive(search_zip, content="Hello")
        assert summary.has_matches
        assert any("main.py" in r.path for r in summary.results)
        # Check content matches
        for result in summary.results:
            if "main.py" in result.path:
                assert result.match_type == SearchType.CONTENT
                assert len(result.content_matches) > 0

    def test_search_by_size(self, search_zip: Path) -> None:
        """Test searching by file size."""
        summary = search_archive(search_zip, size_min=5000)
        assert summary.has_matches
        for result in summary.results:
            assert result.size >= 5000

    def test_search_case_insensitive(self, search_zip: Path) -> None:
        """Test case insensitive search."""
        summary = search_archive(
            search_zip, pattern="README*", case_sensitive=False
        )
        assert summary.has_matches
        assert any("readme" in r.path.lower() for r in summary.results)

    def test_search_regex(self, search_zip: Path) -> None:
        """Test regex pattern search."""
        summary = search_archive(
            search_zip, pattern=r".*\.py$", use_regex=True
        )
        assert summary.total_matches == 2

    def test_find_files(self, search_zip: Path) -> None:
        """Test find_files convenience function."""
        files = find_files(search_zip, "*.csv")
        assert "data.csv" in files

    def test_list_by_extension(self, search_zip: Path) -> None:
        """Test listing files by extension."""
        result = list_by_extension(search_zip, [".txt", ".py"])
        assert ".txt" in result
        assert ".py" in result
        assert len(result[".txt"]) == 2
        assert len(result[".py"]) == 2

    def test_list_large_files(self, search_zip: Path) -> None:
        """Test listing large files."""
        results = list_large_files(search_zip, 1000)
        assert len(results) >= 1
        # Should be sorted by size descending
        if len(results) > 1:
            assert results[0].size >= results[1].size

    def test_grep_archive(self, search_zip: Path) -> None:
        """Test grep_archive function."""
        matches = list(grep_archive(search_zip, "def"))
        assert len(matches) >= 1
        for _path, content_matches in matches:
            assert len(content_matches) > 0

    def test_search_criteria_dataclass(self) -> None:
        """Test SearchCriteria normalization."""
        criteria = SearchCriteria(extensions=["txt", ".py", "CSV"])
        assert ".txt" in criteria.extensions
        assert ".py" in criteria.extensions
        assert ".csv" in criteria.extensions


class TestArchiveComparison:
    """Tests for archive comparison functionality."""

    @pytest.fixture
    def archive1(self) -> Iterator[Path]:
        """Create first archive for comparison."""
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            path = Path(f.name)

        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("common.txt", "Same content")
            zf.writestr("modified.txt", "Version 1")
            zf.writestr("removed.txt", "Will be removed")

        yield path
        path.unlink()

    @pytest.fixture
    def archive2(self) -> Iterator[Path]:
        """Create second archive for comparison."""
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            path = Path(f.name)

        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("common.txt", "Same content")
            zf.writestr("modified.txt", "Version 2 - different")
            zf.writestr("added.txt", "New file")

        yield path
        path.unlink()

    @pytest.fixture
    def identical_archive(self, archive1: Path) -> Iterator[Path]:
        """Create archive identical to archive1."""
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            path = Path(f.name)

        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("common.txt", "Same content")
            zf.writestr("modified.txt", "Version 1")
            zf.writestr("removed.txt", "Will be removed")

        yield path
        path.unlink()

    def test_compare_finds_differences(
        self, archive1: Path, archive2: Path
    ) -> None:
        """Test comparison finds all difference types."""
        result = compare_archives(archive1, archive2)

        assert result.has_differences
        assert "added.txt" in result.added_files
        assert "removed.txt" in result.removed_files
        assert "modified.txt" in result.modified_files
        assert "common.txt" in result.unchanged_files

    def test_compare_identical_archives(
        self, archive1: Path, identical_archive: Path
    ) -> None:
        """Test comparison of identical archives."""
        result = compare_archives(archive1, identical_archive)
        assert result.are_identical
        assert len(result.added_files) == 0
        assert len(result.removed_files) == 0
        assert len(result.modified_files) == 0

    def test_archives_are_identical(
        self, archive1: Path, identical_archive: Path
    ) -> None:
        """Test archives_are_identical function."""
        assert archives_are_identical(archive1, identical_archive)

    def test_archives_not_identical(
        self, archive1: Path, archive2: Path
    ) -> None:
        """Test archives_are_identical returns False for different archives."""
        assert not archives_are_identical(archive1, archive2)

    def test_get_added_files(self, archive1: Path, archive2: Path) -> None:
        """Test get_added_files function."""
        added = get_added_files(archive1, archive2)
        assert "added.txt" in added

    def test_get_removed_files(self, archive1: Path, archive2: Path) -> None:
        """Test get_removed_files function."""
        removed = get_removed_files(archive1, archive2)
        assert "removed.txt" in removed

    def test_get_modified_files(self, archive1: Path, archive2: Path) -> None:
        """Test get_modified_files function."""
        modified = get_modified_files(archive1, archive2)
        assert "modified.txt" in modified

    def test_compare_by_size(self, archive1: Path, archive2: Path) -> None:
        """Test comparison by size only."""
        result = compare_archives(
            archive1, archive2, method=CompareMethod.SIZE_ONLY
        )
        assert result.has_differences

    def test_compare_by_content(self, archive1: Path, archive2: Path) -> None:
        """Test comparison by full content."""
        result = compare_archives(
            archive1, archive2, method=CompareMethod.CONTENT
        )
        assert "modified.txt" in result.modified_files

    def test_generate_diff_report(self, archive1: Path, archive2: Path) -> None:
        """Test diff report generation."""
        result = compare_archives(archive1, archive2)
        report = generate_diff_report(result)

        assert "Archive Comparison Report" in report
        assert "Added Files" in report or "added.txt" in report
        assert "Removed Files" in report or "removed.txt" in report
        assert "Modified Files" in report or "modified.txt" in report

    def test_difference_size_diff(
        self, archive1: Path, archive2: Path
    ) -> None:
        """Test size difference calculation."""
        result = compare_archives(archive1, archive2)
        for diff in result.differences:
            if diff.diff_type == DifferenceType.MODIFIED:
                # Size diff should be calculated
                assert diff.size1 is not None
                assert diff.size2 is not None


class TestSplitArchive:
    """Tests for split archive functionality."""

    @pytest.fixture
    def large_file(self) -> Iterator[Path]:
        """Create a file large enough to split."""
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            # Write 500KB of data
            f.write(b"x" * (500 * 1024))
            path = Path(f.name)

        yield path
        path.unlink()

    def test_split_file_basic(self, large_file: Path) -> None:
        """Test basic file splitting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = split_file(
                large_file, part_size=100 * 1024, output_dir=Path(tmpdir)
            )

            assert result.success
            assert len(result.parts) == 5
            assert result.total_size == 500 * 1024

            # Verify all parts exist
            for part in result.parts:
                assert part.exists()

    def test_split_and_join(self, large_file: Path) -> None:
        """Test splitting and rejoining produces identical file."""
        original_content = large_file.read_bytes()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Split
            split_result = split_file(
                large_file, part_size=100 * 1024, output_dir=Path(tmpdir)
            )
            assert split_result.success

            # Join
            output = Path(tmpdir) / "rejoined.bin"
            join_result = join_parts(split_result.parts[0], output)

            assert join_result.success
            assert output.exists()
            assert output.read_bytes() == original_content

    def test_detect_split_parts(self, large_file: Path) -> None:
        """Test detecting split archive parts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            split_result = split_file(
                large_file, part_size=100 * 1024, output_dir=Path(tmpdir)
            )

            joiner = ArchiveJoiner()
            info = joiner.detect_parts(split_result.parts[0])

            assert info is not None
            assert info.part_count == 5
            assert info.is_complete

    def test_is_split_archive(self, large_file: Path) -> None:
        """Test is_split_archive detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            split_result = split_file(
                large_file, part_size=100 * 1024, output_dir=Path(tmpdir)
            )

            assert is_split_archive(split_result.parts[0])
            assert not is_split_archive(large_file)

    def test_split_patterns(self, large_file: Path) -> None:
        """Test different naming patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            splitter = ArchiveSplitter(
                part_size=200 * 1024, pattern=ArchiveSplitter.PATTERN_NUMERIC
            )
            result = splitter.split(large_file, Path(tmpdir))

            assert result.success
            # Check numeric pattern
            assert any(".001" in str(p) for p in result.parts)

    def test_split_cancel(self, large_file: Path) -> None:
        """Test that splitter has cancel method."""
        # Test that the cancel method exists and can be called
        splitter = ArchiveSplitter(part_size=50 * 1024)
        # Should not raise
        splitter.cancel()
        assert splitter._cancelled is True


class TestArchiveRepair:
    """Tests for archive repair functionality."""

    @pytest.fixture
    def valid_zip(self) -> Iterator[Path]:
        """Create a valid ZIP file."""
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            path = Path(f.name)

        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("file1.txt", "Content 1")
            zf.writestr("file2.txt", "Content 2")

        yield path
        path.unlink()

    @pytest.fixture
    def corrupted_zip(self) -> Iterator[Path]:
        """Create a corrupted ZIP file (truncated)."""
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            path = Path(f.name)

        # Create valid ZIP
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("file1.txt", "Content 1")
            zf.writestr("file2.txt", "Content 2")

        # Truncate to corrupt
        content = path.read_bytes()
        path.write_bytes(content[: len(content) // 2])

        yield path
        path.unlink()

    def test_diagnose_valid_zip(self, valid_zip: Path) -> None:
        """Test diagnosing valid archive."""
        damage = diagnose_archive(valid_zip)
        assert damage == DamageType.NONE

    def test_diagnose_corrupted_zip(self, corrupted_zip: Path) -> None:
        """Test diagnosing corrupted archive."""
        damage = diagnose_archive(corrupted_zip)
        assert damage != DamageType.NONE

    def test_can_repair_valid(self, valid_zip: Path) -> None:
        """Test can_repair returns False for valid archive."""
        assert can_repair(valid_zip) is False

    def test_can_repair_corrupted(self, corrupted_zip: Path) -> None:
        """Test can_repair returns True for corrupted archive."""
        assert can_repair(corrupted_zip) is True

    def test_repair_valid_archive(self, valid_zip: Path) -> None:
        """Test repairing already valid archive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "repaired.zip"
            result = repair_archive(valid_zip, output)

            assert result.status == RepairStatus.UNNECESSARY
            assert result.output_path == output

    def test_repair_corrupted_archive(self, corrupted_zip: Path) -> None:
        """Test repairing corrupted archive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "repaired.zip"
            result = repair_archive(corrupted_zip, output)

            # May succeed partially or fail depending on corruption
            assert result.status in (
                RepairStatus.SUCCESS,
                RepairStatus.PARTIAL,
                RepairStatus.FAILED,
            )

    def test_repairer_cancel(self, valid_zip: Path) -> None:
        """Test that repairer has cancel method."""
        # Test that the cancel method exists and can be called
        repairer = ZipRepairer()
        # Should not raise
        repairer.cancel()
        assert repairer._cancelled is True

    def test_repair_result_recovery_rate(self) -> None:
        """Test recovery rate calculation."""
        from zipextractor.core.repair import RepairResult

        result = RepairResult(
            status=RepairStatus.PARTIAL,
            original_file_count=10,
            recovered_file_count=7,
        )
        assert result.recovery_rate == 70.0

    def test_repair_result_empty_archive(self) -> None:
        """Test recovery rate for empty archive."""
        from zipextractor.core.repair import RepairResult

        result = RepairResult(
            status=RepairStatus.SUCCESS,
            original_file_count=0,
            recovered_file_count=0,
        )
        assert result.recovery_rate == 100.0


class TestSearchCriteria:
    """Tests for search criteria functionality."""

    def test_size_operator_between(self) -> None:
        """Test BETWEEN size operator."""
        criteria = SearchCriteria(
            size_min=100,
            size_max=1000,
            size_operator=SizeOperator.BETWEEN,
        )
        searcher = ArchiveSearcher()
        assert searcher._matches_size(500, criteria)
        assert not searcher._matches_size(50, criteria)
        assert not searcher._matches_size(2000, criteria)

    def test_size_operator_greater(self) -> None:
        """Test GREATER size operator."""
        criteria = SearchCriteria(
            size_min=100,
            size_operator=SizeOperator.GREATER,
        )
        searcher = ArchiveSearcher()
        assert searcher._matches_size(200, criteria)
        assert not searcher._matches_size(50, criteria)

    def test_size_operator_less(self) -> None:
        """Test LESS size operator."""
        criteria = SearchCriteria(
            size_max=100,
            size_operator=SizeOperator.LESS,
        )
        searcher = ArchiveSearcher()
        assert searcher._matches_size(50, criteria)
        assert not searcher._matches_size(200, criteria)

    def test_date_matching(self) -> None:
        """Test date range matching."""
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)

        criteria = SearchCriteria(
            date_after=yesterday,
            date_before=tomorrow,
        )
        searcher = ArchiveSearcher()
        assert searcher._matches_date(now, criteria)
        assert not searcher._matches_date(now - timedelta(days=10), criteria)
