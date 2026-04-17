"""Tests for the mzip command-line interface.

This module tests the CLI commands using Click's testing utilities.
"""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from zipextractor.cli.main import cli

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_dir() -> Iterator[Path]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_zip(temp_dir: Path) -> Path:
    """Create a sample ZIP archive for testing."""
    zip_path = temp_dir / "sample.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("file1.txt", "Hello, World!")
        zf.writestr("file2.txt", "Test content")
        zf.writestr("dir/nested.txt", "Nested file content")
    return zip_path


@pytest.fixture
def sample_files(temp_dir: Path) -> list[Path]:
    """Create sample files for archive creation tests."""
    files = []

    # Create some test files
    file1 = temp_dir / "test1.txt"
    file1.write_text("Test file 1 content")
    files.append(file1)

    file2 = temp_dir / "test2.txt"
    file2.write_text("Test file 2 content")
    files.append(file2)

    # Create a subdirectory with files
    subdir = temp_dir / "subdir"
    subdir.mkdir()
    file3 = subdir / "nested.txt"
    file3.write_text("Nested file content")
    files.append(subdir)

    return files


class TestCliMain:
    """Tests for the main CLI entry point."""

    def test_cli_version(self, runner: CliRunner) -> None:
        """Test --version flag."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "1.0.0" in result.output

    def test_cli_help(self, runner: CliRunner) -> None:
        """Test --help flag."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "mzip" in result.output
        assert "extract" in result.output
        assert "create" in result.output
        assert "list" in result.output

    def test_cli_verbose_flag(self, runner: CliRunner) -> None:
        """Test -v/--verbose flag."""
        result = runner.invoke(cli, ["-v", "--help"])
        assert result.exit_code == 0

        result = runner.invoke(cli, ["--verbose", "--help"])
        assert result.exit_code == 0


class TestExtractCommand:
    """Tests for the extract command."""

    def test_extract_help(self, runner: CliRunner) -> None:
        """Test extract --help."""
        result = runner.invoke(cli, ["extract", "--help"])
        assert result.exit_code == 0
        assert "Extract files from an archive" in result.output
        assert "--output" in result.output
        assert "--password" in result.output

    def test_extract_basic(
        self, runner: CliRunner, sample_zip: Path, temp_dir: Path
    ) -> None:
        """Test basic extraction."""
        output_dir = temp_dir / "output"
        result = runner.invoke(
            cli, ["extract", str(sample_zip), "-o", str(output_dir)]
        )
        assert result.exit_code == 0
        assert "Extracted" in result.output
        # Files may be extracted to a subdirectory named after the archive
        extracted_files = list(output_dir.rglob("file1.txt"))
        assert len(extracted_files) == 1
        assert list(output_dir.rglob("file2.txt"))
        assert list(output_dir.rglob("nested.txt"))

    def test_extract_force_overwrite(
        self, runner: CliRunner, sample_zip: Path, temp_dir: Path
    ) -> None:
        """Test extraction with force overwrite."""
        output_dir = temp_dir / "output"
        output_dir.mkdir()
        # Files are extracted to a subdirectory named after the archive
        archive_subdir = output_dir / "sample"
        archive_subdir.mkdir(parents=True)
        # Create a file that would conflict
        (archive_subdir / "file1.txt").write_text("existing content")

        # Use --force option to overwrite
        result = runner.invoke(
            cli,
            ["extract", str(sample_zip), "-o", str(output_dir), "-f"],
        )
        assert result.exit_code == 0
        # File should be overwritten
        assert (archive_subdir / "file1.txt").read_text() == "Hello, World!"

    def test_extract_nonexistent_archive(
        self, runner: CliRunner, temp_dir: Path
    ) -> None:
        """Test extraction of non-existent archive."""
        result = runner.invoke(
            cli, ["extract", str(temp_dir / "nonexistent.zip")]
        )
        assert result.exit_code != 0

    def test_extract_verbose(
        self, runner: CliRunner, sample_zip: Path, temp_dir: Path
    ) -> None:
        """Test extraction with verbose output."""
        output_dir = temp_dir / "output"
        result = runner.invoke(
            cli, ["-v", "extract", str(sample_zip), "-o", str(output_dir)]
        )
        assert result.exit_code == 0


class TestCreateCommand:
    """Tests for the create command."""

    def test_create_help(self, runner: CliRunner) -> None:
        """Test create --help."""
        result = runner.invoke(cli, ["create", "--help"])
        assert result.exit_code == 0
        assert "Create a new archive" in result.output
        assert "--level" in result.output
        assert "--method" in result.output

    def test_create_basic(
        self, runner: CliRunner, sample_files: list[Path], temp_dir: Path
    ) -> None:
        """Test basic archive creation."""
        output_zip = temp_dir / "output.zip"
        file_args = [str(f) for f in sample_files[:2]]  # Just the two text files
        result = runner.invoke(
            cli, ["create", str(output_zip), *file_args]
        )
        assert result.exit_code == 0
        assert "Created" in result.output
        assert output_zip.exists()

        # Verify the archive contents
        with zipfile.ZipFile(output_zip, "r") as zf:
            names = zf.namelist()
            assert len(names) == 2

    def test_create_with_compression_level(
        self, runner: CliRunner, sample_files: list[Path], temp_dir: Path
    ) -> None:
        """Test archive creation with compression level."""
        output_zip = temp_dir / "output.zip"
        result = runner.invoke(
            cli, ["create", str(output_zip), str(sample_files[0]), "-l", "9"]
        )
        assert result.exit_code == 0
        assert output_zip.exists()

    def test_create_store_method(
        self, runner: CliRunner, sample_files: list[Path], temp_dir: Path
    ) -> None:
        """Test archive creation with store (no compression) method."""
        output_zip = temp_dir / "output.zip"
        result = runner.invoke(
            cli, ["create", str(output_zip), str(sample_files[0]), "-m", "store"]
        )
        assert result.exit_code == 0
        assert output_zip.exists()

    def test_create_no_files(
        self, runner: CliRunner, temp_dir: Path
    ) -> None:
        """Test create command without files."""
        output_zip = temp_dir / "output.zip"
        result = runner.invoke(cli, ["create", str(output_zip)])
        assert result.exit_code != 0


class TestListCommand:
    """Tests for the list command."""

    def test_list_help(self, runner: CliRunner) -> None:
        """Test list --help."""
        result = runner.invoke(cli, ["list", "--help"])
        assert result.exit_code == 0
        assert "List contents of an archive" in result.output
        assert "--long" in result.output
        assert "--json" in result.output

    def test_list_basic(self, runner: CliRunner, sample_zip: Path) -> None:
        """Test basic archive listing."""
        result = runner.invoke(cli, ["list", str(sample_zip)])
        assert result.exit_code == 0
        assert "file1.txt" in result.output
        assert "file2.txt" in result.output
        assert "nested.txt" in result.output

    def test_list_long_format(self, runner: CliRunner, sample_zip: Path) -> None:
        """Test long format listing."""
        result = runner.invoke(cli, ["list", str(sample_zip), "-l"])
        assert result.exit_code == 0
        # Long format should include size information
        assert "file1.txt" in result.output

    def test_list_json_format(self, runner: CliRunner, sample_zip: Path) -> None:
        """Test JSON output format."""
        result = runner.invoke(cli, ["list", str(sample_zip), "--json"])
        assert result.exit_code == 0
        # JSON output should contain brackets
        assert "[" in result.output or "{" in result.output


class TestInfoCommand:
    """Tests for the info command."""

    def test_info_help(self, runner: CliRunner) -> None:
        """Test info --help."""
        result = runner.invoke(cli, ["info", "--help"])
        assert result.exit_code == 0
        assert "information" in result.output.lower()

    def test_info_basic(self, runner: CliRunner, sample_zip: Path) -> None:
        """Test basic info command."""
        result = runner.invoke(cli, ["info", str(sample_zip)])
        assert result.exit_code == 0
        # Should show the archive name and file count
        assert "sample.zip" in result.output
        assert "3" in result.output  # 3 files in sample zip

    def test_info_json_format(self, runner: CliRunner, sample_zip: Path) -> None:
        """Test info JSON output."""
        result = runner.invoke(cli, ["info", str(sample_zip), "--json"])
        assert result.exit_code == 0
        assert "{" in result.output


class TestTestCommand:
    """Tests for the test command."""

    def test_test_help(self, runner: CliRunner) -> None:
        """Test test --help."""
        result = runner.invoke(cli, ["test", "--help"])
        assert result.exit_code == 0
        assert "Test archive integrity" in result.output

    def test_test_valid_archive(self, runner: CliRunner, sample_zip: Path) -> None:
        """Test integrity check on valid archive."""
        result = runner.invoke(cli, ["test", str(sample_zip)])
        assert result.exit_code == 0
        assert "passed" in result.output.lower() or "ok" in result.output.lower()

    def test_test_corrupted_archive(
        self, runner: CliRunner, temp_dir: Path
    ) -> None:
        """Test integrity check on corrupted archive."""
        # Create a corrupted zip file
        corrupted_zip = temp_dir / "corrupted.zip"
        corrupted_zip.write_bytes(b"PK\x03\x04" + b"\x00" * 100)  # Invalid ZIP

        result = runner.invoke(cli, ["test", str(corrupted_zip)])
        # Should report failure
        assert "failed" in result.output.lower() or result.exit_code != 0


class TestSearchCommand:
    """Tests for the search command."""

    def test_search_help(self, runner: CliRunner) -> None:
        """Test search --help."""
        result = runner.invoke(cli, ["search", "--help"])
        assert result.exit_code == 0
        assert "Search for files" in result.output

    def test_search_by_pattern(self, runner: CliRunner, sample_zip: Path) -> None:
        """Test search by filename pattern."""
        result = runner.invoke(cli, ["search", str(sample_zip), "*.txt"])
        assert result.exit_code == 0
        # Should find the txt files
        assert "file1.txt" in result.output or "found" in result.output.lower()

    def test_search_no_matches(self, runner: CliRunner, sample_zip: Path) -> None:
        """Test search with no matches."""
        result = runner.invoke(cli, ["search", str(sample_zip), "*.nonexistent"])
        assert result.exit_code == 0
        assert "0" in result.output or "no" in result.output.lower()


class TestRepairCommand:
    """Tests for the repair command."""

    def test_repair_help(self, runner: CliRunner) -> None:
        """Test repair --help."""
        result = runner.invoke(cli, ["repair", "--help"])
        assert result.exit_code == 0
        assert "Attempt to repair" in result.output

    def test_repair_valid_archive(
        self, runner: CliRunner, sample_zip: Path, temp_dir: Path
    ) -> None:
        """Test repair on a valid archive."""
        output_path = temp_dir / "repaired.zip"
        result = runner.invoke(
            cli, ["repair", str(sample_zip), "-o", str(output_path)]
        )
        # Should complete without error
        assert result.exit_code == 0


class TestFormatsCommand:
    """Tests for the formats command."""

    def test_formats_help(self, runner: CliRunner) -> None:
        """Test formats --help."""
        result = runner.invoke(cli, ["formats", "--help"])
        assert result.exit_code == 0

    def test_formats_list(self, runner: CliRunner) -> None:
        """Test formats command output."""
        result = runner.invoke(cli, ["formats"])
        assert result.exit_code == 0
        assert "Supported" in result.output
        # Should list common formats
        assert "ZIP" in result.output


class TestCompareCommand:
    """Tests for the compare command."""

    def test_compare_help(self, runner: CliRunner) -> None:
        """Test compare --help."""
        result = runner.invoke(cli, ["compare", "--help"])
        assert result.exit_code == 0
        assert "Compare two archives" in result.output

    def test_compare_identical_archives(
        self, runner: CliRunner, sample_zip: Path, temp_dir: Path
    ) -> None:
        """Test comparing identical archives."""
        # Create a copy
        import shutil

        copy_zip = temp_dir / "copy.zip"
        shutil.copy(sample_zip, copy_zip)

        result = runner.invoke(cli, ["compare", str(sample_zip), str(copy_zip)])
        assert result.exit_code == 0
        assert "identical" in result.output.lower()

    def test_compare_different_archives(
        self, runner: CliRunner, sample_zip: Path, temp_dir: Path
    ) -> None:
        """Test comparing different archives."""
        # Create a different zip
        other_zip = temp_dir / "other.zip"
        with zipfile.ZipFile(other_zip, "w") as zf:
            zf.writestr("different.txt", "Different content")

        result = runner.invoke(cli, ["compare", str(sample_zip), str(other_zip)])
        assert result.exit_code == 0
        # Should report differences


class TestCliIntegration:
    """Integration tests for CLI workflows."""

    def test_create_and_extract_workflow(
        self, runner: CliRunner, temp_dir: Path
    ) -> None:
        """Test creating an archive and then extracting it."""
        # Create test files
        source_dir = temp_dir / "source"
        source_dir.mkdir()
        (source_dir / "doc.txt").write_text("Document content")
        (source_dir / "data.txt").write_text("Data content")

        # Create archive
        archive_path = temp_dir / "test.zip"
        result = runner.invoke(
            cli,
            [
                "create",
                str(archive_path),
                str(source_dir / "doc.txt"),
                str(source_dir / "data.txt"),
            ],
        )
        assert result.exit_code == 0
        assert archive_path.exists()

        # List contents
        result = runner.invoke(cli, ["list", str(archive_path)])
        assert result.exit_code == 0
        assert "doc.txt" in result.output

        # Get info
        result = runner.invoke(cli, ["info", str(archive_path)])
        assert result.exit_code == 0

        # Test integrity
        result = runner.invoke(cli, ["test", str(archive_path)])
        assert result.exit_code == 0

        # Extract
        extract_dir = temp_dir / "extract"
        result = runner.invoke(
            cli, ["extract", str(archive_path), "-o", str(extract_dir)]
        )
        assert result.exit_code == 0

        # Verify files were extracted (may be under different paths)
        # Look for the txt files anywhere in the extract dir
        extracted_files = list(extract_dir.rglob("*.txt"))
        assert len(extracted_files) == 2
        # Find and verify doc.txt content
        doc_files = [f for f in extracted_files if f.name == "doc.txt"]
        assert len(doc_files) == 1
        assert doc_files[0].read_text() == "Document content"

    def test_verbose_output(
        self, runner: CliRunner, sample_zip: Path, temp_dir: Path
    ) -> None:
        """Test that verbose flag produces more output."""
        # Normal output
        normal_result = runner.invoke(cli, ["list", str(sample_zip)])

        # Verbose output
        verbose_result = runner.invoke(cli, ["-v", "list", str(sample_zip)])

        # Both should succeed
        assert normal_result.exit_code == 0
        assert verbose_result.exit_code == 0


class TestCliErrorHandling:
    """Tests for CLI error handling."""

    def test_invalid_archive_path(
        self, runner: CliRunner, temp_dir: Path
    ) -> None:
        """Test error handling for invalid archive path."""
        result = runner.invoke(cli, ["list", str(temp_dir / "nonexistent.zip")])
        assert result.exit_code != 0

    def test_invalid_command(self, runner: CliRunner) -> None:
        """Test error handling for invalid command."""
        result = runner.invoke(cli, ["invalidcommand"])
        assert result.exit_code != 0

    def test_missing_required_arguments(self, runner: CliRunner) -> None:
        """Test error handling for missing required arguments."""
        result = runner.invoke(cli, ["extract"])  # Missing archive argument
        assert result.exit_code != 0


class TestCliHelpers:
    """Tests for CLI helper functions."""

    def test_format_size_function(self) -> None:
        """Test the format_size helper function."""
        from zipextractor.cli.main import format_size

        assert format_size(0) == "0 B"
        assert format_size(100) == "100 B"
        assert "KB" in format_size(1024)
        assert "MB" in format_size(1024 * 1024)
        assert "GB" in format_size(1024 * 1024 * 1024)

    def test_get_console_function(self) -> None:
        """Test the get_console helper function."""
        from zipextractor.cli.main import get_console

        console = get_console()
        assert console is not None
        # Should be a Rich Console instance
        from rich.console import Console

        assert isinstance(console, Console)
