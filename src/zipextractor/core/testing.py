"""Archive integrity testing and verification.

This module provides comprehensive integrity checking for archives,
including CRC verification, structure validation, and corruption detection.
"""

from __future__ import annotations

import hashlib
import tarfile
import zipfile
import zlib
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from zipextractor.core.formats import detect_format
from zipextractor.core.models import ArchiveFormat
from zipextractor.utils.logging import get_logger

logger = get_logger(__name__)


class TestStatus(Enum):
    """Test result status."""

    PASSED = auto()
    FAILED = auto()
    WARNING = auto()
    SKIPPED = auto()


class TestType(Enum):
    """Type of test performed."""

    STRUCTURE = auto()  # Archive structure valid
    CRC = auto()  # CRC/checksum verification
    HEADER = auto()  # Header integrity
    EXTRACTION = auto()  # Can be extracted
    PASSWORD = auto()  # Password check
    COMPRESSION = auto()  # Decompression works


@dataclass
class FileTestResult:
    """Test result for a single file.

    Attributes:
        filename: Name of the file tested.
        status: Test status.
        test_type: Type of test performed.
        message: Optional message or error.
        expected_crc: Expected CRC value.
        actual_crc: Actual computed CRC.
    """

    filename: str
    status: TestStatus
    test_type: TestType
    message: str = ""
    expected_crc: int | None = None
    actual_crc: int | None = None

    @property
    def is_ok(self) -> bool:
        """Check if test passed."""
        return self.status in (TestStatus.PASSED, TestStatus.WARNING)


@dataclass
class ArchiveTestResult:
    """Comprehensive test result for an archive.

    Attributes:
        archive_path: Path to the archive.
        format: Detected archive format.
        status: Overall test status.
        file_results: Test results for each file.
        total_files: Total number of files tested.
        passed_files: Number of files that passed.
        failed_files: Number of files that failed.
        warnings: List of warning messages.
        errors: List of error messages.
        elapsed_seconds: Time taken for testing.
    """

    archive_path: Path
    format: ArchiveFormat | None
    status: TestStatus
    file_results: list[FileTestResult] = field(default_factory=list)
    total_files: int = 0
    passed_files: int = 0
    failed_files: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    @property
    def is_valid(self) -> bool:
        """Check if archive is valid (no failures)."""
        return self.status != TestStatus.FAILED and self.failed_files == 0

    @property
    def pass_rate(self) -> float:
        """Get percentage of files that passed."""
        if self.total_files == 0:
            return 100.0
        return (self.passed_files / self.total_files) * 100.0


class ArchiveTester:
    """Comprehensive archive integrity tester.

    Tests archive structure, CRC checksums, and extraction capability.
    """

    def __init__(
        self,
        password: str | None = None,
        verify_crc: bool = True,
        test_extraction: bool = False,
    ) -> None:
        """Initialize tester.

        Args:
            password: Password for encrypted archives.
            verify_crc: Whether to verify CRC checksums.
            test_extraction: Whether to test full extraction.
        """
        self._password = password
        self._verify_crc = verify_crc
        self._test_extraction = test_extraction
        self._cancelled = False

    def cancel(self) -> None:
        """Cancel ongoing test."""
        self._cancelled = True

    def test(
        self,
        archive_path: Path,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> ArchiveTestResult:
        """Test archive integrity.

        Args:
            archive_path: Path to the archive.
            progress_callback: Optional callback(filename, current, total).

        Returns:
            ArchiveTestResult with detailed results.
        """
        import time  # noqa: PLC0415

        self._cancelled = False
        start_time = time.time()

        # Detect format
        fmt = detect_format(archive_path)
        if fmt is None:
            return ArchiveTestResult(
                archive_path=archive_path,
                format=None,
                status=TestStatus.FAILED,
                errors=["Unknown archive format"],
            )

        # Route to appropriate tester
        if fmt == ArchiveFormat.ZIP:
            result = self._test_zip(archive_path, progress_callback)
        elif fmt in (
            ArchiveFormat.TAR,
            ArchiveFormat.TAR_GZ,
            ArchiveFormat.TAR_BZ2,
            ArchiveFormat.TAR_XZ,
        ):
            result = self._test_tar(archive_path, fmt, progress_callback)
        else:
            result = ArchiveTestResult(
                archive_path=archive_path,
                format=fmt,
                status=TestStatus.SKIPPED,
                warnings=[f"Testing not supported for {fmt.name}"],
            )

        result.elapsed_seconds = time.time() - start_time
        return result

    def _test_zip(
        self,
        archive_path: Path,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> ArchiveTestResult:
        """Test ZIP archive integrity.

        Args:
            archive_path: Path to ZIP file.
            progress_callback: Progress callback.

        Returns:
            Test result.
        """
        file_results: list[FileTestResult] = []
        warnings: list[str] = []
        errors: list[str] = []

        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                # First, test structure with built-in test
                bad_file = zf.testzip()
                if bad_file:
                    errors.append(f"Corrupt file detected: {bad_file}")

                members = [m for m in zf.infolist() if not m.is_dir()]
                total = len(members)

                for i, member in enumerate(members):
                    if self._cancelled:
                        return ArchiveTestResult(
                            archive_path=archive_path,
                            format=ArchiveFormat.ZIP,
                            status=TestStatus.FAILED,
                            errors=["Test cancelled"],
                        )

                    if progress_callback:
                        progress_callback(member.filename, i, total)

                    result = self._test_zip_member(zf, member)
                    file_results.append(result)

                if progress_callback:
                    progress_callback("", total, total)

        except zipfile.BadZipFile as e:
            return ArchiveTestResult(
                archive_path=archive_path,
                format=ArchiveFormat.ZIP,
                status=TestStatus.FAILED,
                errors=[f"Invalid ZIP file: {e}"],
            )
        except Exception as e:
            return ArchiveTestResult(
                archive_path=archive_path,
                format=ArchiveFormat.ZIP,
                status=TestStatus.FAILED,
                errors=[f"Test error: {e}"],
            )

        # Calculate summary
        passed = sum(1 for r in file_results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in file_results if r.status == TestStatus.FAILED)

        overall_status = (
            TestStatus.PASSED
            if failed == 0 and not errors
            else TestStatus.FAILED
            if failed > 0 or errors
            else TestStatus.WARNING
        )

        return ArchiveTestResult(
            archive_path=archive_path,
            format=ArchiveFormat.ZIP,
            status=overall_status,
            file_results=file_results,
            total_files=len(file_results),
            passed_files=passed,
            failed_files=failed,
            warnings=warnings,
            errors=errors,
        )

    def _test_zip_member(  # noqa: PLR0911
        self, zf: zipfile.ZipFile, member: zipfile.ZipInfo
    ) -> FileTestResult:
        """Test a single ZIP file member.

        Args:
            zf: Open ZipFile object.
            member: ZipInfo for the member to test.

        Returns:
            FileTestResult for this member.
        """
        try:
            # Check if encrypted
            is_encrypted = member.flag_bits & 0x1

            if is_encrypted and not self._password:
                return FileTestResult(
                    filename=member.filename,
                    status=TestStatus.SKIPPED,
                    test_type=TestType.PASSWORD,
                    message="Encrypted, no password provided",
                )

            # Read and compute CRC
            pwd = self._password.encode() if self._password else None

            if self._verify_crc:
                data = zf.read(member.filename, pwd=pwd)
                actual_crc = zlib.crc32(data) & 0xFFFFFFFF

                if actual_crc != member.CRC:
                    return FileTestResult(
                        filename=member.filename,
                        status=TestStatus.FAILED,
                        test_type=TestType.CRC,
                        message="CRC mismatch",
                        expected_crc=member.CRC,
                        actual_crc=actual_crc,
                    )

                return FileTestResult(
                    filename=member.filename,
                    status=TestStatus.PASSED,
                    test_type=TestType.CRC,
                    expected_crc=member.CRC,
                    actual_crc=actual_crc,
                )
            else:
                # Just try to read
                zf.read(member.filename, pwd=pwd)
                return FileTestResult(
                    filename=member.filename,
                    status=TestStatus.PASSED,
                    test_type=TestType.EXTRACTION,
                )

        except RuntimeError as e:
            if "password" in str(e).lower():
                return FileTestResult(
                    filename=member.filename,
                    status=TestStatus.FAILED,
                    test_type=TestType.PASSWORD,
                    message="Wrong password or encryption error",
                )
            return FileTestResult(
                filename=member.filename,
                status=TestStatus.FAILED,
                test_type=TestType.EXTRACTION,
                message=str(e),
            )
        except Exception as e:
            return FileTestResult(
                filename=member.filename,
                status=TestStatus.FAILED,
                test_type=TestType.EXTRACTION,
                message=str(e),
            )

    def _test_tar(
        self,
        archive_path: Path,
        fmt: ArchiveFormat,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> ArchiveTestResult:
        """Test TAR archive integrity.

        Args:
            archive_path: Path to TAR file.
            fmt: Specific TAR format (TAR, TAR.GZ, etc.).
            progress_callback: Progress callback.

        Returns:
            Test result.
        """
        file_results: list[FileTestResult] = []
        errors: list[str] = []

        # Determine open mode
        mode_map = {
            ArchiveFormat.TAR: "r",
            ArchiveFormat.TAR_GZ: "r:gz",
            ArchiveFormat.TAR_BZ2: "r:bz2",
            ArchiveFormat.TAR_XZ: "r:xz",
        }
        mode = mode_map.get(fmt, "r")

        try:
            with tarfile.open(str(archive_path), mode) as tf:  # type: ignore[call-overload]
                members = [m for m in tf.getmembers() if m.isfile()]
                total = len(members)

                for i, member in enumerate(members):
                    if self._cancelled:
                        return ArchiveTestResult(
                            archive_path=archive_path,
                            format=fmt,
                            status=TestStatus.FAILED,
                            errors=["Test cancelled"],
                        )

                    if progress_callback:
                        progress_callback(member.name, i, total)

                    result = self._test_tar_member(tf, member)
                    file_results.append(result)

                if progress_callback:
                    progress_callback("", total, total)

        except tarfile.TarError as e:
            return ArchiveTestResult(
                archive_path=archive_path,
                format=fmt,
                status=TestStatus.FAILED,
                errors=[f"Invalid TAR file: {e}"],
            )
        except Exception as e:
            return ArchiveTestResult(
                archive_path=archive_path,
                format=fmt,
                status=TestStatus.FAILED,
                errors=[f"Test error: {e}"],
            )

        passed = sum(1 for r in file_results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in file_results if r.status == TestStatus.FAILED)

        overall_status = (
            TestStatus.PASSED
            if failed == 0 and not errors
            else TestStatus.FAILED
        )

        return ArchiveTestResult(
            archive_path=archive_path,
            format=fmt,
            status=overall_status,
            file_results=file_results,
            total_files=len(file_results),
            passed_files=passed,
            failed_files=failed,
            errors=errors,
        )

    def _test_tar_member(
        self, tf: tarfile.TarFile, member: tarfile.TarInfo
    ) -> FileTestResult:
        """Test a single TAR file member.

        Args:
            tf: Open TarFile object.
            member: TarInfo for the member to test.

        Returns:
            FileTestResult for this member.
        """
        try:
            # TAR doesn't store CRC, just test extraction
            extracted = tf.extractfile(member)
            if extracted:
                # Read entire file to verify decompression
                _ = extracted.read()
                return FileTestResult(
                    filename=member.name,
                    status=TestStatus.PASSED,
                    test_type=TestType.EXTRACTION,
                )
            else:
                return FileTestResult(
                    filename=member.name,
                    status=TestStatus.WARNING,
                    test_type=TestType.EXTRACTION,
                    message="Could not extract file object",
                )
        except Exception as e:
            return FileTestResult(
                filename=member.name,
                status=TestStatus.FAILED,
                test_type=TestType.EXTRACTION,
                message=str(e),
            )


def verify_archive(
    archive_path: Path | str,
    password: str | None = None,
    verify_crc: bool = True,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> ArchiveTestResult:
    """Test archive integrity.

    Args:
        archive_path: Path to the archive.
        password: Password for encrypted archives.
        verify_crc: Whether to verify CRC checksums.
        progress_callback: Optional callback(filename, current, total).

    Returns:
        ArchiveTestResult with detailed results.
    """
    if isinstance(archive_path, str):
        archive_path = Path(archive_path)

    tester = ArchiveTester(password=password, verify_crc=verify_crc)
    return tester.test(archive_path, progress_callback)


def quick_test(archive_path: Path | str) -> bool:
    """Quick test if archive is valid.

    Args:
        archive_path: Path to the archive.

    Returns:
        True if archive appears valid.
    """
    result = verify_archive(archive_path, verify_crc=False)
    return result.is_valid


def compute_file_hash(file_path: Path, algorithm: str = "sha256") -> str:
    """Compute hash of a file.

    Args:
        file_path: Path to the file.
        algorithm: Hash algorithm (md5, sha1, sha256, sha512).

    Returns:
        Hex digest of the hash.
    """
    hasher = hashlib.new(algorithm)
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_checksum(file_path: Path, expected_hash: str, algorithm: str = "sha256") -> bool:
    """Verify file checksum.

    Args:
        file_path: Path to the file.
        expected_hash: Expected hash value.
        algorithm: Hash algorithm used.

    Returns:
        True if checksums match.
    """
    actual_hash = compute_file_hash(file_path, algorithm)
    return actual_hash.lower() == expected_hash.lower()
