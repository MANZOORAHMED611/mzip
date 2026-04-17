"""Tests for archive writer module."""

from __future__ import annotations

import tarfile
import tempfile
import zipfile
from pathlib import Path

import pytest

from zipextractor.core.archive_writer import (
    FORMAT_EXTENSIONS,
    ArchiveWriter,
    TarArchiveWriter,
    ZipArchiveWriter,
    get_archive_writer,
    get_writable_formats,
    suggest_extension,
)
from zipextractor.core.models import (
    ArchiveFormat,
    CompressionMethod,
    CompressionOptions,
)


class TestFormatExtensions:
    """Tests for FORMAT_EXTENSIONS mapping."""

    def test_zip_extension(self) -> None:
        """Test ZIP format has .zip extension."""
        assert FORMAT_EXTENSIONS[ArchiveFormat.ZIP] == ".zip"

    def test_tar_extension(self) -> None:
        """Test TAR format has .tar extension."""
        assert FORMAT_EXTENSIONS[ArchiveFormat.TAR] == ".tar"

    def test_tar_gz_extension(self) -> None:
        """Test TAR_GZ format has .tar.gz extension."""
        assert FORMAT_EXTENSIONS[ArchiveFormat.TAR_GZ] == ".tar.gz"

    def test_tar_bz2_extension(self) -> None:
        """Test TAR_BZ2 format has .tar.bz2 extension."""
        assert FORMAT_EXTENSIONS[ArchiveFormat.TAR_BZ2] == ".tar.bz2"

    def test_tar_xz_extension(self) -> None:
        """Test TAR_XZ format has .tar.xz extension."""
        assert FORMAT_EXTENSIONS[ArchiveFormat.TAR_XZ] == ".tar.xz"


class TestSuggestExtension:
    """Tests for suggest_extension function."""

    def test_suggest_zip_extension(self) -> None:
        """Test suggesting ZIP extension."""
        assert suggest_extension(ArchiveFormat.ZIP) == ".zip"

    def test_suggest_tar_extension(self) -> None:
        """Test suggesting TAR extension."""
        assert suggest_extension(ArchiveFormat.TAR) == ".tar"

    def test_suggest_unknown_format(self) -> None:
        """Test suggesting extension for unknown format."""
        assert suggest_extension(ArchiveFormat.UNKNOWN) == ".zip"


class TestGetWritableFormats:
    """Tests for get_writable_formats function."""

    def test_returns_list(self) -> None:
        """Test returns a list."""
        formats = get_writable_formats()
        assert isinstance(formats, list)

    def test_includes_zip(self) -> None:
        """Test includes ZIP format."""
        formats = get_writable_formats()
        assert ArchiveFormat.ZIP in formats

    def test_includes_tar_formats(self) -> None:
        """Test includes TAR formats."""
        formats = get_writable_formats()
        assert ArchiveFormat.TAR in formats
        assert ArchiveFormat.TAR_GZ in formats
        assert ArchiveFormat.TAR_BZ2 in formats
        assert ArchiveFormat.TAR_XZ in formats

    def test_excludes_read_only_formats(self) -> None:
        """Test excludes read-only formats like RAR."""
        formats = get_writable_formats()
        assert ArchiveFormat.RAR not in formats


class TestGetArchiveWriter:
    """Tests for get_archive_writer factory function."""

    def test_get_zip_writer(self) -> None:
        """Test getting ZIP writer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "test.zip"
            options = CompressionOptions(format=ArchiveFormat.ZIP)
            writer = get_archive_writer(output, options)
            assert isinstance(writer, ZipArchiveWriter)

    def test_get_tar_writer(self) -> None:
        """Test getting TAR writer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "test.tar"
            options = CompressionOptions(format=ArchiveFormat.TAR)
            writer = get_archive_writer(output, options)
            assert isinstance(writer, TarArchiveWriter)

    def test_get_tar_gz_writer(self) -> None:
        """Test getting TAR.GZ writer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "test.tar.gz"
            options = CompressionOptions(format=ArchiveFormat.TAR_GZ)
            writer = get_archive_writer(output, options)
            assert isinstance(writer, TarArchiveWriter)

    def test_unsupported_format_raises(self) -> None:
        """Test unsupported format raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "test.rar"
            options = CompressionOptions(format=ArchiveFormat.RAR)
            with pytest.raises(ValueError, match="not supported"):
                get_archive_writer(output, options)


class TestZipArchiveWriter:
    """Tests for ZipArchiveWriter class."""

    def test_create_simple_zip(self) -> None:
        """Test creating a simple ZIP archive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create source file
            source = tmppath / "test.txt"
            source.write_text("Hello, World!")

            # Create archive
            output = tmppath / "test.zip"
            options = CompressionOptions(format=ArchiveFormat.ZIP)
            writer = ZipArchiveWriter(output, options)
            result = writer.create([source])

            assert result.success
            assert output.exists()
            assert result.file_count == 1
            assert result.original_size > 0

    def test_create_zip_with_multiple_files(self) -> None:
        """Test creating ZIP with multiple files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            src_dir = tmppath / "source"
            src_dir.mkdir()

            (src_dir / "file1.txt").write_text("Content 1")
            (src_dir / "file2.txt").write_text("Content 2")
            (src_dir / "subdir").mkdir()
            (src_dir / "subdir" / "file3.txt").write_text("Content 3")

            output = tmppath / "multi.zip"
            options = CompressionOptions(format=ArchiveFormat.ZIP)
            writer = ZipArchiveWriter(output, options)
            result = writer.create([src_dir])

            assert result.success
            assert result.file_count == 3

            # Verify archive contents
            with zipfile.ZipFile(output, "r") as zf:
                names = zf.namelist()
                assert len(names) == 3

    def test_create_zip_deflate_compression(self) -> None:
        """Test ZIP with DEFLATE compression."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create compressible content
            source = tmppath / "compressible.txt"
            source.write_text("A" * 10000)

            output = tmppath / "deflate.zip"
            options = CompressionOptions(
                format=ArchiveFormat.ZIP,
                method=CompressionMethod.DEFLATE,
                level=9,
            )
            writer = ZipArchiveWriter(output, options)
            result = writer.create([source])

            assert result.success
            assert result.compressed_size < result.original_size

    def test_create_zip_lzma_compression(self) -> None:
        """Test ZIP with LZMA compression."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            source = tmppath / "lzma_test.txt"
            source.write_text("B" * 10000)

            output = tmppath / "lzma.zip"
            options = CompressionOptions(
                format=ArchiveFormat.ZIP,
                method=CompressionMethod.LZMA,
            )
            writer = ZipArchiveWriter(output, options)
            result = writer.create([source])

            assert result.success
            assert result.compressed_size < result.original_size

    def test_create_zip_store_no_compression(self) -> None:
        """Test ZIP with STORE (no compression)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            source = tmppath / "store_test.txt"
            content = "Store test content"
            source.write_text(content)

            output = tmppath / "store.zip"
            options = CompressionOptions(
                format=ArchiveFormat.ZIP,
                method=CompressionMethod.STORE,
            )
            writer = ZipArchiveWriter(output, options)
            result = writer.create([source])

            assert result.success
            # STORE should have larger archive (headers + no compression)
            assert result.compressed_size >= result.original_size

    def test_create_zip_preserves_directory_structure(self) -> None:
        """Test ZIP preserves directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            src_dir = tmppath / "src"
            src_dir.mkdir()
            (src_dir / "a" / "b").mkdir(parents=True)
            (src_dir / "a" / "b" / "deep.txt").write_text("Deep file")

            output = tmppath / "deep.zip"
            options = CompressionOptions(format=ArchiveFormat.ZIP)
            writer = ZipArchiveWriter(output, options)
            result = writer.create([src_dir])

            assert result.success
            with zipfile.ZipFile(output, "r") as zf:
                names = zf.namelist()
                assert any("a/b/deep.txt" in n or "a\\b\\deep.txt" in n for n in names)

    def test_zip_writer_cancel(self) -> None:
        """Test ZIP writer can be cancelled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            output = tmppath / "cancelled.zip"
            options = CompressionOptions(format=ArchiveFormat.ZIP)
            writer = ZipArchiveWriter(output, options)

            # Cancel immediately
            writer.cancel()
            assert writer.is_cancelled

    def test_zip_writer_pause_resume(self) -> None:
        """Test ZIP writer pause and resume."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            output = tmppath / "pause.zip"
            options = CompressionOptions(format=ArchiveFormat.ZIP)
            writer = ZipArchiveWriter(output, options)

            writer.pause()
            assert writer._paused
            writer.resume()
            assert not writer._paused


class TestTarArchiveWriter:
    """Tests for TarArchiveWriter class."""

    def test_create_simple_tar(self) -> None:
        """Test creating a simple TAR archive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            source = tmppath / "test.txt"
            source.write_text("Hello, TAR!")

            output = tmppath / "test.tar"
            options = CompressionOptions(format=ArchiveFormat.TAR)
            writer = TarArchiveWriter(output, options)
            result = writer.create([source])

            assert result.success
            assert output.exists()
            assert result.file_count == 1

    def test_create_tar_gz(self) -> None:
        """Test creating TAR.GZ archive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            source = tmppath / "gzip_test.txt"
            source.write_text("C" * 10000)

            output = tmppath / "test.tar.gz"
            options = CompressionOptions(format=ArchiveFormat.TAR_GZ)
            writer = TarArchiveWriter(output, options)
            result = writer.create([source])

            assert result.success
            assert result.compressed_size < result.original_size

            # Verify it's valid gzipped tar
            with tarfile.open(output, "r:gz") as tf:
                members = tf.getmembers()
                assert len(members) == 1

    def test_create_tar_bz2(self) -> None:
        """Test creating TAR.BZ2 archive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            source = tmppath / "bz2_test.txt"
            source.write_text("D" * 10000)

            output = tmppath / "test.tar.bz2"
            options = CompressionOptions(format=ArchiveFormat.TAR_BZ2)
            writer = TarArchiveWriter(output, options)
            result = writer.create([source])

            assert result.success
            assert result.compressed_size < result.original_size

    def test_create_tar_xz(self) -> None:
        """Test creating TAR.XZ archive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            source = tmppath / "xz_test.txt"
            source.write_text("E" * 10000)

            output = tmppath / "test.tar.xz"
            options = CompressionOptions(format=ArchiveFormat.TAR_XZ)
            writer = TarArchiveWriter(output, options)
            result = writer.create([source])

            assert result.success
            assert result.compressed_size < result.original_size

    def test_create_tar_multiple_files(self) -> None:
        """Test creating TAR with multiple files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            src_dir = tmppath / "source"
            src_dir.mkdir()

            (src_dir / "file1.txt").write_text("One")
            (src_dir / "file2.txt").write_text("Two")

            output = tmppath / "multi.tar"
            options = CompressionOptions(format=ArchiveFormat.TAR)
            writer = TarArchiveWriter(output, options)
            result = writer.create([src_dir])

            assert result.success
            assert result.file_count == 2

    def test_tar_preserves_directory_structure(self) -> None:
        """Test TAR preserves directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            src_dir = tmppath / "src"
            (src_dir / "deep" / "path").mkdir(parents=True)
            (src_dir / "deep" / "path" / "file.txt").write_text("content")

            output = tmppath / "structure.tar"
            options = CompressionOptions(format=ArchiveFormat.TAR)
            writer = TarArchiveWriter(output, options)
            result = writer.create([src_dir])

            assert result.success
            with tarfile.open(output, "r") as tf:
                names = tf.getnames()
                assert any("deep/path/file.txt" in n for n in names)


class TestArchiveWriter:
    """Tests for high-level ArchiveWriter class."""

    def test_create_auto_detect_zip(self) -> None:
        """Test auto-detecting ZIP format from extension."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            source = tmppath / "test.txt"
            source.write_text("content")

            output = tmppath / "auto.zip"
            writer = ArchiveWriter()
            result = writer.create([source], output)

            assert result.success
            assert zipfile.is_zipfile(output)

    def test_create_auto_detect_tar_gz(self) -> None:
        """Test auto-detecting TAR.GZ format from extension."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            source = tmppath / "test.txt"
            source.write_text("content")

            output = tmppath / "auto.tar.gz"
            writer = ArchiveWriter()
            result = writer.create([source], output)

            assert result.success
            assert tarfile.is_tarfile(output)

    def test_create_auto_detect_tgz(self) -> None:
        """Test auto-detecting TGZ format from extension."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            source = tmppath / "test.txt"
            source.write_text("content")

            output = tmppath / "auto.tgz"
            writer = ArchiveWriter()
            result = writer.create([source], output)

            assert result.success

    def test_create_with_progress_callback(self) -> None:
        """Test create with progress callback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            source = tmppath / "progress.txt"
            source.write_text("Progress test content")

            output = tmppath / "progress.zip"

            progress_calls: list[tuple[str, int, int]] = []

            def progress_cb(filename: str, done: int, total: int) -> None:
                progress_calls.append((filename, done, total))

            writer = ArchiveWriter(progress_callback=progress_cb)
            result = writer.create([source], output)

            assert result.success
            assert len(progress_calls) > 0

    def test_cancel_archive_creation(self) -> None:
        """Test cancelling archive creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            output = tmppath / "cancel.zip"

            writer = ArchiveWriter()
            writer.cancel()  # Cancel before starting

    def test_add_files_to_zip(self) -> None:
        """Test adding files to existing ZIP archive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create initial archive
            file1 = tmppath / "file1.txt"
            file1.write_text("File 1")

            archive = tmppath / "addto.zip"
            writer = ArchiveWriter()
            writer.create([file1], archive)

            # Add another file
            file2 = tmppath / "file2.txt"
            file2.write_text("File 2")

            result = writer.add_files(archive, [file2])
            assert result.success

            # Verify archive has both files
            with zipfile.ZipFile(archive, "r") as zf:
                names = zf.namelist()
                assert len(names) == 2

    def test_add_files_nonexistent_archive(self) -> None:
        """Test adding files to non-existent archive fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            file1 = tmppath / "file.txt"
            file1.write_text("content")

            archive = tmppath / "nonexistent.zip"
            writer = ArchiveWriter()
            result = writer.add_files(archive, [file1])

            assert not result.success
            assert "not found" in result.error_message.lower()

    def test_delete_files_from_zip(self) -> None:
        """Test deleting files from ZIP archive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create archive with multiple files
            file1 = tmppath / "keep.txt"
            file2 = tmppath / "delete.txt"
            file1.write_text("Keep this")
            file2.write_text("Delete this")

            archive = tmppath / "delete_test.zip"
            writer = ArchiveWriter()
            writer.create([file1, file2], archive)

            # Delete one file
            result = writer.delete_files(archive, ["delete.txt"])
            assert result.success

            # Verify file was removed
            with zipfile.ZipFile(archive, "r") as zf:
                names = zf.namelist()
                assert "delete.txt" not in names
                assert len(names) == 1

    def test_delete_files_nonexistent_archive(self) -> None:
        """Test deleting files from non-existent archive fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            archive = tmppath / "nonexistent.zip"
            writer = ArchiveWriter()
            result = writer.delete_files(archive, ["file.txt"])

            assert not result.success
            assert "not found" in result.error_message.lower()


class TestArchiveWriterOptions:
    """Tests for archive writer with various options."""

    def test_exclude_hidden_files(self) -> None:
        """Test excluding hidden files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            src_dir = tmppath / "src"
            src_dir.mkdir()

            (src_dir / "visible.txt").write_text("visible")
            (src_dir / ".hidden").write_text("hidden")

            output = tmppath / "no_hidden.zip"
            options = CompressionOptions(
                format=ArchiveFormat.ZIP,
                include_hidden=False,
            )
            writer = ZipArchiveWriter(output, options)
            result = writer.create([src_dir])

            assert result.success
            assert result.file_count == 1

            with zipfile.ZipFile(output, "r") as zf:
                names = zf.namelist()
                assert not any(".hidden" in n for n in names)

    def test_include_hidden_files(self) -> None:
        """Test including hidden files (default)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            src_dir = tmppath / "src"
            src_dir.mkdir()

            (src_dir / "visible.txt").write_text("visible")
            (src_dir / ".hidden").write_text("hidden")

            output = tmppath / "with_hidden.zip"
            options = CompressionOptions(
                format=ArchiveFormat.ZIP,
                include_hidden=True,
            )
            writer = ZipArchiveWriter(output, options)
            result = writer.create([src_dir])

            assert result.success
            assert result.file_count == 2

    def test_compression_result_properties(self) -> None:
        """Test CompressionResult has expected properties."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            source = tmppath / "props.txt"
            source.write_text("A" * 10000)

            output = tmppath / "props.zip"
            writer = ArchiveWriter()
            result = writer.create([source], output)

            assert result.success
            assert result.output_path == output
            assert result.original_size == 10000
            assert result.compressed_size > 0
            assert result.file_count == 1
            assert result.elapsed_seconds >= 0
            assert result.compression_ratio > 0
