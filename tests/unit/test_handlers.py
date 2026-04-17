"""Tests for archive handlers module."""

from __future__ import annotations

import tarfile
import tempfile
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from zipextractor.core.formats import FormatCapability
from zipextractor.core.handlers import TarHandler, ZipHandler
from zipextractor.core.handlers.base_handler import (
    ArchiveInfo,
    CreationOptions,
    ExtractionOptions,
    HandlerRegistry,
    get_handler,
    get_handler_registry,
)
from zipextractor.core.models import ArchiveFormat


class TestHandlerRegistry:
    """Tests for HandlerRegistry class."""

    @pytest.fixture
    def registry(self) -> HandlerRegistry:
        """Create handler registry."""
        return get_handler_registry()

    def test_supports_zip(self, registry: HandlerRegistry) -> None:
        """Test ZIP format is supported."""
        assert registry.supports_format(ArchiveFormat.ZIP)

    def test_supports_tar(self, registry: HandlerRegistry) -> None:
        """Test TAR format is supported."""
        assert registry.supports_format(ArchiveFormat.TAR)

    def test_get_supported_formats(self, registry: HandlerRegistry) -> None:
        """Test getting supported formats."""
        formats = registry.get_supported_formats()
        assert ArchiveFormat.ZIP in formats
        assert ArchiveFormat.TAR in formats

    def test_get_handler_for_zip(self, registry: HandlerRegistry) -> None:
        """Test getting handler for ZIP file."""
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            with zipfile.ZipFile(f.name, "w") as zf:
                zf.writestr("test.txt", "Hello")
            path = Path(f.name)

        try:
            handler = registry.get_handler(path)
            assert isinstance(handler, ZipHandler)
        finally:
            path.unlink()

    def test_get_handler_for_tar(self, registry: HandlerRegistry) -> None:
        """Test getting handler for TAR file."""
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as f:
            path = Path(f.name)

        try:
            with tarfile.open(str(path), "w") as tf:
                # Add a dummy file
                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    tmp.write(b"test content")
                    tmp_path = Path(tmp.name)
                tf.add(str(tmp_path), arcname="test.txt")
                tmp_path.unlink()

            handler = registry.get_handler(path)
            assert isinstance(handler, TarHandler)
        finally:
            path.unlink()


class TestZipHandler:
    """Tests for ZipHandler class."""

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

    def test_format_property(self) -> None:
        """Test format property returns ZIP."""
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            with zipfile.ZipFile(f.name, "w") as zf:
                zf.writestr("test.txt", "test")
            path = Path(f.name)

        try:
            handler = ZipHandler(path)
            assert handler.format == ArchiveFormat.ZIP
        finally:
            path.unlink()

    def test_capabilities(self) -> None:
        """Test capabilities include read, write, encrypt."""
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            with zipfile.ZipFile(f.name, "w") as zf:
                zf.writestr("test.txt", "test")
            path = Path(f.name)

        try:
            handler = ZipHandler(path)
            caps = handler.capabilities
            assert FormatCapability.READ in caps
            assert FormatCapability.WRITE in caps
            assert FormatCapability.ENCRYPT in caps
        finally:
            path.unlink()

    def test_list_contents(self, sample_zip: Path) -> None:
        """Test listing ZIP contents."""
        handler = ZipHandler(sample_zip)
        contents = handler.list_contents()

        assert len(contents) == 3
        names = [f.name for f in contents]
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "subdir/file3.txt" in names

    def test_get_info(self, sample_zip: Path) -> None:
        """Test getting archive info."""
        handler = ZipHandler(sample_zip)
        info = handler.get_info()

        assert isinstance(info, ArchiveInfo)
        assert info.file_count == 3
        assert info.total_size > 0
        assert info.is_encrypted is False

    def test_read_file(self, sample_zip: Path) -> None:
        """Test reading a file from archive."""
        handler = ZipHandler(sample_zip)
        content = handler.read_file("file1.txt")

        assert content == b"Content of file 1"

    def test_read_file_not_found(self, sample_zip: Path) -> None:
        """Test reading non-existent file raises error."""
        handler = ZipHandler(sample_zip)

        with pytest.raises(FileNotFoundError):
            handler.read_file("nonexistent.txt")

    def test_test_archive(self, sample_zip: Path) -> None:
        """Test archive integrity check."""
        handler = ZipHandler(sample_zip)
        assert handler.test() is True

    def test_extract_all(self, sample_zip: Path) -> None:
        """Test extracting all files."""
        handler = ZipHandler(sample_zip)

        with tempfile.TemporaryDirectory() as tmpdir:
            options = ExtractionOptions(output_path=Path(tmpdir))
            handler.extract_all(options)

            assert (Path(tmpdir) / "file1.txt").exists()
            assert (Path(tmpdir) / "file2.txt").exists()
            assert (Path(tmpdir) / "subdir" / "file3.txt").exists()

    def test_extract_files_selective(self, sample_zip: Path) -> None:
        """Test extracting specific files."""
        handler = ZipHandler(sample_zip)

        with tempfile.TemporaryDirectory() as tmpdir:
            options = ExtractionOptions(output_path=Path(tmpdir))
            handler.extract_files(["file1.txt"], options)

            assert (Path(tmpdir) / "file1.txt").exists()
            assert not (Path(tmpdir) / "file2.txt").exists()

    def test_create_archive(self) -> None:
        """Test creating a new ZIP archive."""
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as out,
        ):
            # Create test files
            test_file1 = Path(tmpdir) / "test1.txt"
            test_file1.write_text("Test content 1")
            test_file2 = Path(tmpdir) / "test2.txt"
            test_file2.write_text("Test content 2")

            output_path = Path(out.name)
            handler = ZipHandler(output_path)
            handler.create([test_file1, test_file2], CreationOptions())

            # Verify archive was created
            assert output_path.exists()

            # Verify contents
            with zipfile.ZipFile(output_path, "r") as zf:
                names = zf.namelist()
                assert "test1.txt" in names
                assert "test2.txt" in names

            output_path.unlink()

    def test_add_files(self, sample_zip: Path) -> None:
        """Test adding files to existing archive."""
        handler = ZipHandler(sample_zip)

        with tempfile.TemporaryDirectory() as tmpdir:
            new_file = Path(tmpdir) / "new_file.txt"
            new_file.write_text("New content")

            handler.add_files([new_file])

            contents = handler.list_contents()
            names = [f.name for f in contents]
            assert "new_file.txt" in names

    def test_delete_files(self, sample_zip: Path) -> None:
        """Test deleting files from archive."""
        handler = ZipHandler(sample_zip)

        handler.delete_files(["file1.txt"])

        contents = handler.list_contents()
        names = [f.name for f in contents]
        assert "file1.txt" not in names
        assert "file2.txt" in names


class TestTarHandler:
    """Tests for TarHandler class."""

    @pytest.fixture
    def sample_tar(self) -> Iterator[Path]:
        """Create a sample TAR file."""
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as f:
            path = Path(f.name)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            file1 = Path(tmpdir) / "file1.txt"
            file1.write_text("Content of file 1")
            file2 = Path(tmpdir) / "file2.txt"
            file2.write_text("Content of file 2")

            with tarfile.open(str(path), "w") as tf:
                tf.add(str(file1), arcname="file1.txt")
                tf.add(str(file2), arcname="file2.txt")

        yield path
        path.unlink()

    def test_format_property(self, sample_tar: Path) -> None:
        """Test format property returns TAR."""
        handler = TarHandler(sample_tar)
        assert handler.format == ArchiveFormat.TAR

    def test_capabilities(self, sample_tar: Path) -> None:
        """Test capabilities include read, write, append."""
        handler = TarHandler(sample_tar)
        caps = handler.capabilities
        assert FormatCapability.READ in caps
        assert FormatCapability.WRITE in caps
        assert FormatCapability.APPEND in caps

    def test_list_contents(self, sample_tar: Path) -> None:
        """Test listing TAR contents."""
        handler = TarHandler(sample_tar)
        contents = handler.list_contents()

        assert len(contents) == 2
        names = [f.name for f in contents]
        assert "file1.txt" in names
        assert "file2.txt" in names

    def test_get_info(self, sample_tar: Path) -> None:
        """Test getting archive info."""
        handler = TarHandler(sample_tar)
        info = handler.get_info()

        assert isinstance(info, ArchiveInfo)
        assert info.file_count == 2
        assert info.total_size > 0

    def test_read_file(self, sample_tar: Path) -> None:
        """Test reading a file from archive."""
        handler = TarHandler(sample_tar)
        content = handler.read_file("file1.txt")

        assert content == b"Content of file 1"

    def test_extract_all(self, sample_tar: Path) -> None:
        """Test extracting all files."""
        handler = TarHandler(sample_tar)

        with tempfile.TemporaryDirectory() as tmpdir:
            options = ExtractionOptions(output_path=Path(tmpdir))
            handler.extract_all(options)

            assert (Path(tmpdir) / "file1.txt").exists()
            assert (Path(tmpdir) / "file2.txt").exists()

    def test_create_tar(self) -> None:
        """Test creating a new TAR archive."""
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as out,
        ):
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Test content")

            output_path = Path(out.name)
            handler = TarHandler(output_path, ArchiveFormat.TAR)
            handler.create([test_file], CreationOptions())

            assert output_path.exists()

            with tarfile.open(str(output_path), "r") as tf:
                names = tf.getnames()
                assert "test.txt" in names

            output_path.unlink()

    def test_create_tar_gz(self) -> None:
        """Test creating a TAR.GZ archive."""
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as out,
        ):
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Test content")

            output_path = Path(out.name)
            handler = TarHandler(output_path, ArchiveFormat.TAR_GZ)
            handler.create([test_file], CreationOptions())

            assert output_path.exists()

            with tarfile.open(str(output_path), "r:gz") as tf:
                names = tf.getnames()
                assert "test.txt" in names

            output_path.unlink()


class TestGetHandler:
    """Tests for get_handler function."""

    def test_get_handler_zip(self) -> None:
        """Test getting handler for ZIP file."""
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            with zipfile.ZipFile(f.name, "w") as zf:
                zf.writestr("test.txt", "test")
            path = Path(f.name)

        try:
            handler = get_handler(path)
            assert isinstance(handler, ZipHandler)
        finally:
            path.unlink()

    def test_get_handler_string_path(self) -> None:
        """Test getting handler with string path."""
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            with zipfile.ZipFile(f.name, "w") as zf:
                zf.writestr("test.txt", "test")
            path = f.name

        try:
            handler = get_handler(path)
            assert isinstance(handler, ZipHandler)
        finally:
            Path(path).unlink()

    def test_get_handler_unsupported_format(self) -> None:
        """Test getting handler for unsupported format raises error."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Just text")
            path = Path(f.name)

        try:
            with pytest.raises(ValueError):
                get_handler(path)
        finally:
            path.unlink()
