"""Main CLI entry point for mzip.

This module provides the command-line interface for mzip archive utility.
All commands are implemented using the click framework with rich output.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

if TYPE_CHECKING:
    from collections.abc import Sequence

    from rich.console import Console

# Version from package
__version__ = "1.0.0"


def get_console() -> Console:
    """Get rich console for output."""
    from rich.console import Console
    return Console()


def format_size(size_bytes: int) -> str:
    """Format size in bytes to human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


@click.group()
@click.version_option(version=__version__, prog_name="mzip")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """mzip - Modern archive utility for Linux.

    A comprehensive tool for working with ZIP, 7z, TAR, and other archive formats.
    Supports extraction, creation, testing, searching, and repair operations.

    Examples:

    \b
      mzip extract archive.zip             # Extract to current directory
      mzip extract archive.zip -o /tmp     # Extract to specific directory
      mzip create output.zip file1 dir1    # Create archive from files
      mzip list archive.zip                # List archive contents
      mzip test archive.zip                # Test archive integrity
      mzip info archive.zip                # Show archive information
      mzip search archive.zip "*.py"       # Search for files in archive
      mzip repair damaged.zip              # Repair corrupted archive
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


@cli.command()
@click.argument("archive", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o", "--output",
    type=click.Path(path_type=Path),
    help="Output directory (default: current directory)",
)
@click.option("-p", "--password", help="Password for encrypted archives")
@click.option(
    "-f", "--force",
    is_flag=True,
    help="Overwrite existing files without prompting",
)
@click.pass_context
def extract(
    ctx: click.Context,
    archive: Path,
    output: Path | None,
    password: str | None,
    force: bool,
) -> None:
    """Extract files from an archive.

    ARCHIVE is the path to the archive file to extract.

    Examples:

    \b
      mzip extract archive.zip
      mzip extract archive.zip -o /tmp/extracted
      mzip extract encrypted.zip -p mypassword
      mzip extract archive.7z --force
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn

    from zipextractor.core.extraction import ExtractionEngine
    from zipextractor.core.formats import detect_format
    from zipextractor.core.models import (
        ArchiveFormat,
        ConflictResolution,
        ExtractionTask,
    )
    from zipextractor.core.validation import get_archive_info

    console = get_console()
    verbose = ctx.obj.get("verbose", False)

    # Detect format
    fmt = detect_format(archive)
    if fmt is None:
        console.print(f"[red]Error:[/red] Unknown archive format: {archive.name}")
        sys.exit(1)

    if verbose:
        console.print(f"Detected format: [cyan]{fmt.name}[/cyan]")

    # Set output directory
    output_dir = output or Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Currently only ZIP is fully supported for extraction
    if fmt != ArchiveFormat.ZIP:
        console.print(
            f"[yellow]Warning:[/yellow] {fmt.name} extraction via CLI is experimental"
        )

    # Get archive info for progress
    try:
        info = get_archive_info(archive)
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to read archive: {e}")
        sys.exit(1)

    # Create extraction task
    task = ExtractionTask(
        task_id="cli_extract",
        archive_path=archive,
        destination_path=output_dir,
        conflict_resolution=(
            ConflictResolution.OVERWRITE if force else ConflictResolution.SKIP
        ),
        total_files=info.file_count,
        total_bytes=info.uncompressed_size,
    )

    # Note: password handling would need to be added to ExtractionEngine
    if password:
        console.print(
            "[yellow]Warning:[/yellow] Password support in CLI is limited"
        )

    # Extract with progress
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress_task = progress.add_task(f"Extracting {archive.name}...", total=None)

        try:
            engine = ExtractionEngine()
            success = engine.extract(task)

            progress.update(progress_task, completed=True)

            if success:
                console.print(
                    f"[green]Success:[/green] Extracted {task.extracted_files} files "
                    f"to {output_dir}"
                )
                if verbose:
                    console.print(f"  Total size: {format_size(task.extracted_bytes)}")
            else:
                error_msg = getattr(task, "error_message", "Unknown error")
                console.print(f"[red]Error:[/red] {error_msg}")
                sys.exit(1)

        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            sys.exit(1)


@cli.command()
@click.argument("output", type=click.Path(path_type=Path))
@click.argument("files", nargs=-1, type=click.Path(exists=True, path_type=Path), required=True)
@click.option(
    "-f", "--format",
    "archive_format",
    type=click.Choice(["zip", "tar", "tar.gz", "tar.bz2", "tar.xz", "7z"]),
    default="zip",
    help="Archive format (default: zip)",
)
@click.option(
    "-l", "--level",
    type=click.IntRange(0, 9),
    default=6,
    help="Compression level 0-9 (default: 6)",
)
@click.option("-p", "--password", help="Password for encryption (ZIP only)")
@click.option(
    "-m", "--method",
    type=click.Choice(["deflate", "lzma", "bzip2", "store"]),
    default="deflate",
    help="Compression method (default: deflate)",
)
@click.pass_context
def create(
    ctx: click.Context,
    output: Path,
    files: Sequence[Path],
    archive_format: str,
    level: int,
    password: str | None,
    method: str,
) -> None:
    """Create a new archive from files.

    OUTPUT is the path for the new archive file.
    FILES are the files and directories to include.

    Examples:

    \b
      mzip create archive.zip file1.txt file2.txt
      mzip create backup.zip /home/user/docs -l 9
      mzip create secure.zip data/ -p mypassword
      mzip create archive.tar.gz src/ -f tar.gz
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn

    from zipextractor.core.archive_writer import ArchiveWriter
    from zipextractor.core.models import ArchiveFormat, CompressionMethod, CompressionOptions

    console = get_console()
    verbose = ctx.obj.get("verbose", False)

    # Map format string to enum
    format_map = {
        "zip": ArchiveFormat.ZIP,
        "tar": ArchiveFormat.TAR,
        "tar.gz": ArchiveFormat.TAR_GZ,
        "tar.bz2": ArchiveFormat.TAR_BZ2,
        "tar.xz": ArchiveFormat.TAR_XZ,
        "7z": ArchiveFormat.SEVEN_ZIP,
    }
    fmt = format_map.get(archive_format, ArchiveFormat.ZIP)

    # Map method string to enum
    method_map = {
        "deflate": CompressionMethod.DEFLATE,
        "lzma": CompressionMethod.LZMA,
        "bzip2": CompressionMethod.BZIP2,
        "store": CompressionMethod.STORE,
    }
    comp_method = method_map.get(method, CompressionMethod.DEFLATE)

    # Build options
    options = CompressionOptions(
        format=fmt,
        method=comp_method,
        level=level,
        password=password,
    )

    # Collect all files
    file_list = list(files)
    if verbose:
        console.print(f"Creating {fmt.name} archive with {len(file_list)} item(s)")
        console.print(f"Compression: {comp_method.name} level {level}")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress_task = progress.add_task(f"Creating {output.name}...", total=None)

        try:
            writer = ArchiveWriter()
            result = writer.create(file_list, output, options)

            progress.update(progress_task, completed=True)

            if result.success:
                console.print(
                    f"[green]Success:[/green] Created {output} "
                    f"({result.file_count} files, {format_size(result.compressed_size)})"
                )
                if verbose:
                    ratio = (
                        (1 - result.compressed_size / result.original_size) * 100
                        if result.original_size > 0
                        else 0
                    )
                    console.print(f"  Original size: {format_size(result.original_size)}")
                    console.print(f"  Compression ratio: {ratio:.1f}%")
            else:
                console.print(f"[red]Error:[/red] {result.error_message}")
                sys.exit(1)

        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            sys.exit(1)


@cli.command("list")
@click.argument("archive", type=click.Path(exists=True, path_type=Path))
@click.option("-l", "--long", "long_format", is_flag=True, help="Show detailed information")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def list_archive(
    archive: Path,
    long_format: bool,
    json_output: bool,
) -> None:
    """List contents of an archive.

    ARCHIVE is the path to the archive file.

    Examples:

    \b
      mzip list archive.zip
      mzip list archive.zip -l
      mzip list archive.zip --json
    """
    import json

    from rich.table import Table

    from zipextractor.core.formats import detect_format
    from zipextractor.core.validation import get_archive_info

    console = get_console()

    # Detect format
    fmt = detect_format(archive)
    if fmt is None:
        console.print(f"[red]Error:[/red] Unknown archive format: {archive.name}")
        sys.exit(1)

    try:
        info = get_archive_info(archive)

        if json_output:
            # JSON output
            data: dict[str, Any] = {
                "path": str(archive),
                "format": fmt.name,
                "file_count": info.file_count,
                "total_size": info.uncompressed_size,
                "compressed_size": info.file_size,
                "files": [
                    {
                        "path": f.path,
                        "size": f.size,
                        "compressed_size": f.compressed_size,
                        "is_directory": f.is_directory,
                        "modified": (
                            f.modified_time.isoformat() if f.modified_time else None
                        ),
                    }
                    for f in info.files
                ],
            }
            console.print(json.dumps(data, indent=2))
        elif long_format:
            # Detailed table view
            table = Table(title=f"Contents of {archive.name}")
            table.add_column("Size", justify="right", style="cyan")
            table.add_column("Compressed", justify="right", style="dim")
            table.add_column("Modified", style="dim")
            table.add_column("Name")

            for f in info.files:
                if f.is_directory:
                    table.add_row(
                        "-",
                        "-",
                        "-",
                        f"[blue]{f.path}/[/blue]",
                    )
                else:
                    modified = (
                        f.modified_time.strftime("%Y-%m-%d %H:%M")
                        if f.modified_time
                        else "-"
                    )
                    table.add_row(
                        format_size(f.size),
                        format_size(f.compressed_size),
                        modified,
                        f.path,
                    )

            console.print(table)
            console.print(
                f"\nTotal: {info.file_count} files, "
                f"{format_size(info.uncompressed_size)}"
            )
        else:
            # Simple list
            for f in info.files:
                if f.is_directory:
                    console.print(f"[blue]{f.path}/[/blue]")
                else:
                    console.print(f.path)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@cli.command()
@click.argument("archive", type=click.Path(exists=True, path_type=Path))
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def info(
    archive: Path,
    json_output: bool,
) -> None:
    """Show detailed information about an archive.

    ARCHIVE is the path to the archive file.

    Examples:

    \b
      mzip info archive.zip
      mzip info archive.zip --json
    """
    import json

    from rich.panel import Panel
    from rich.table import Table

    from zipextractor.core.formats import detect_format
    from zipextractor.core.validation import detect_zip_bomb, get_archive_info

    console = get_console()

    # Detect format
    fmt = detect_format(archive)
    if fmt is None:
        console.print(f"[red]Error:[/red] Unknown archive format: {archive.name}")
        sys.exit(1)

    try:
        info_data = get_archive_info(archive)
        is_bomb = detect_zip_bomb(archive)

        if json_output:
            data: dict[str, Any] = {
                "path": str(archive),
                "name": archive.name,
                "format": fmt.name,
                "file_count": info_data.file_count,
                "directory_count": sum(1 for f in info_data.files if f.is_directory),
                "total_size": info_data.uncompressed_size,
                "compressed_size": info_data.file_size,
                "compression_ratio": info_data.compression_ratio,
                "has_password": info_data.has_password,
                "is_potential_bomb": is_bomb,
            }
            console.print(json.dumps(data, indent=2))
        else:
            table = Table(show_header=False, box=None)
            table.add_column("Property", style="cyan")
            table.add_column("Value")

            dir_count = sum(1 for f in info_data.files if f.is_directory)
            file_count = info_data.file_count - dir_count

            table.add_row("Format", fmt.name)
            table.add_row("Files", str(file_count))
            table.add_row("Directories", str(dir_count))
            table.add_row("Total Size", format_size(info_data.uncompressed_size))
            table.add_row("Compressed", format_size(info_data.file_size))
            table.add_row("Ratio", f"{info_data.compression_ratio:.1f}%")
            table.add_row(
                "Encrypted",
                "[yellow]Yes[/yellow]" if info_data.has_password else "No",
            )

            if is_bomb:
                table.add_row(
                    "Warning",
                    "[red]Potential zip bomb detected![/red]",
                )

            console.print(Panel(table, title=archive.name))

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@cli.command()
@click.argument("archive", type=click.Path(exists=True, path_type=Path))
@click.option("-p", "--password", help="Password for encrypted archives")
@click.option("-v", "--verbose", "verbose_test", is_flag=True, help="Show per-file results")
@click.pass_context
def test(
    ctx: click.Context,
    archive: Path,
    password: str | None,
    verbose_test: bool,
) -> None:
    """Test archive integrity.

    ARCHIVE is the path to the archive file to test.

    Examples:

    \b
      mzip test archive.zip
      mzip test encrypted.zip -p mypassword
      mzip test archive.zip -v
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn

    from zipextractor.core.testing import TestStatus, verify_archive

    console = get_console()
    verbose = ctx.obj.get("verbose", False) or verbose_test

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress_task = progress.add_task(f"Testing {archive.name}...", total=None)

        result = verify_archive(archive, password=password)
        progress.update(progress_task, completed=True)

    # Show results
    if result.status == TestStatus.PASSED:
        console.print(
            f"[green]OK:[/green] {archive.name} - All {result.total_files} files passed"
        )
    elif result.status == TestStatus.WARNING:
        console.print(
            f"[yellow]Warning:[/yellow] {archive.name} - "
            f"{result.passed_files}/{result.total_files} files passed"
        )
    elif result.status == TestStatus.SKIPPED:
        console.print(f"[yellow]Skipped:[/yellow] {archive.name}")
        for warning in result.warnings:
            console.print(f"  {warning}")
    else:
        console.print(
            f"[red]FAILED:[/red] {archive.name} - "
            f"{result.failed_files}/{result.total_files} files failed"
        )
        sys.exit(1)

    if verbose:
        for file_result in result.file_results:
            status_icon = (
                "[green]OK[/green]" if file_result.status == TestStatus.PASSED
                else "[red]FAIL[/red]" if file_result.status == TestStatus.FAILED
                else "[yellow]WARN[/yellow]"
            )
            console.print(f"  {status_icon} {file_result.filename}")
            if file_result.message:
                console.print(f"       {file_result.message}")

    if result.errors:
        for error in result.errors:
            console.print(f"[red]Error:[/red] {error}")


@cli.command()
@click.argument("archive", type=click.Path(exists=True, path_type=Path))
@click.argument("pattern")
@click.option("-c", "--content", is_flag=True, help="Search file contents (not just names)")
@click.option("-i", "--ignore-case", is_flag=True, help="Case-insensitive search")
@click.option("-p", "--password", help="Password for encrypted archives")
@click.pass_context
def search(
    ctx: click.Context,
    archive: Path,
    pattern: str,
    content: bool,
    ignore_case: bool,
    password: str | None,
) -> None:
    """Search for files in an archive.

    ARCHIVE is the path to the archive file.
    PATTERN is a glob pattern (for names) or text (for content search).

    Examples:

    \b
      mzip search archive.zip "*.py"
      mzip search archive.zip "*.txt" -i
      mzip search archive.zip "TODO" -c
    """
    from zipextractor.core.search import search_archive

    console = get_console()
    verbose = ctx.obj.get("verbose", False)

    try:
        result = search_archive(
            archive,
            pattern=pattern if not content else None,
            content=pattern if content else None,
            case_sensitive=not ignore_case,
            password=password,
        )

        if not result.has_matches:
            console.print(f"No matches found for '{pattern}'")
            return

        console.print(f"Found {result.total_matches} match(es):\n")

        for match in result.results:
            console.print(f"  [cyan]{match.path}[/cyan]")
            if verbose:
                console.print(f"    Size: {format_size(match.size)}")

            if content and match.content_matches:
                for content_match in match.content_matches[:5]:
                    line_text = content_match.line_text
                    line_preview = line_text[:80] + "..." if len(line_text) > 80 else line_text
                    console.print(
                        f"    Line {content_match.line_number}: {line_preview}"
                    )
                if len(match.content_matches) > 5:
                    remaining = len(match.content_matches) - 5
                    console.print(f"    ... and {remaining} more matches")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@cli.command()
@click.argument("archive", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o", "--output",
    type=click.Path(path_type=Path),
    help="Output path for repaired archive",
)
@click.pass_context
def repair(
    ctx: click.Context,
    archive: Path,
    output: Path | None,
) -> None:
    """Attempt to repair a corrupted archive.

    ARCHIVE is the path to the damaged archive file.

    Examples:

    \b
      mzip repair damaged.zip
      mzip repair damaged.zip -o fixed.zip
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn

    from zipextractor.core.repair import RepairStatus, repair_archive

    console = get_console()
    verbose = ctx.obj.get("verbose", False)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress_task = progress.add_task(f"Repairing {archive.name}...", total=None)

        result = repair_archive(archive, output)
        progress.update(progress_task, completed=True)

    if result.status == RepairStatus.SUCCESS:
        console.print(
            f"[green]Success:[/green] Repaired archive saved to {result.output_path}"
        )
        console.print(
            f"  Recovered {result.recovered_file_count}/{result.original_file_count} files"
        )
    elif result.status == RepairStatus.PARTIAL:
        console.print(
            f"[yellow]Partial:[/yellow] Some files recovered to {result.output_path}"
        )
        console.print(
            f"  Recovered {result.recovered_file_count}/{result.original_file_count} files"
        )
        if result.lost_files and verbose:
            console.print("  Lost files:")
            for lost in result.lost_files[:10]:
                console.print(f"    - {lost}")
            if len(result.lost_files) > 10:
                console.print(f"    ... and {len(result.lost_files) - 10} more")
        sys.exit(1)
    elif result.status == RepairStatus.UNNECESSARY:
        console.print("[green]OK:[/green] Archive is not corrupted, no repair needed")
    else:
        console.print("[red]Failed:[/red] Could not repair archive")
        if result.error_message:
            console.print(f"  {result.error_message}")
        sys.exit(1)


@cli.command()
def formats() -> None:
    """List supported archive formats.

    Shows all archive formats that mzip can read and/or write.
    """
    from rich.table import Table

    from zipextractor.core.models import ArchiveFormat

    console = get_console()

    table = Table(title="Supported Archive Formats")
    table.add_column("Format", style="cyan")
    table.add_column("Extensions")
    table.add_column("Read", justify="center")
    table.add_column("Write", justify="center")
    table.add_column("Encrypt", justify="center")

    # Format information
    formats_info = [
        (ArchiveFormat.ZIP, ".zip", True, True, True),
        (ArchiveFormat.SEVEN_ZIP, ".7z", True, True, True),
        (ArchiveFormat.RAR, ".rar", True, False, False),
        (ArchiveFormat.TAR, ".tar", True, True, False),
        (ArchiveFormat.TAR_GZ, ".tar.gz, .tgz", True, True, False),
        (ArchiveFormat.TAR_BZ2, ".tar.bz2, .tbz2", True, True, False),
        (ArchiveFormat.TAR_XZ, ".tar.xz, .txz", True, True, False),
        (ArchiveFormat.GZIP, ".gz", True, False, False),
        (ArchiveFormat.BZIP2, ".bz2", True, False, False),
        (ArchiveFormat.XZ, ".xz", True, False, False),
    ]

    for fmt, ext, can_read, can_write, can_encrypt in formats_info:
        table.add_row(
            fmt.name,
            ext,
            "[green]Yes[/green]" if can_read else "[dim]No[/dim]",
            "[green]Yes[/green]" if can_write else "[dim]No[/dim]",
            "[green]Yes[/green]" if can_encrypt else "[dim]No[/dim]",
        )

    console.print(table)


@cli.command()
@click.argument("archive1", type=click.Path(exists=True, path_type=Path))
@click.argument("archive2", type=click.Path(exists=True, path_type=Path))
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def compare(
    archive1: Path,
    archive2: Path,
    json_output: bool,
) -> None:
    """Compare two archives.

    Shows files that are added, removed, or modified between two archives.

    Examples:

    \b
      mzip compare old.zip new.zip
      mzip compare v1.zip v2.zip --json
    """
    import json

    from rich.table import Table

    from zipextractor.core.comparison import compare_archives

    console = get_console()

    try:
        result = compare_archives(archive1, archive2)

        if json_output:
            data: dict[str, Any] = {
                "archive1": str(archive1),
                "archive2": str(archive2),
                "identical": result.are_identical,
                "added": result.added_files,
                "removed": result.removed_files,
                "modified": result.modified_files,
                "unchanged": len(result.unchanged_files),
            }
            console.print(json.dumps(data, indent=2))
        else:
            if result.are_identical:
                console.print("[green]Archives are identical[/green]")
                return

            table = Table(title="Archive Comparison")
            table.add_column("Status", style="bold")
            table.add_column("File")

            for path in result.added_files:
                table.add_row("[green]Added[/green]", path)

            for path in result.removed_files:
                table.add_row("[red]Removed[/red]", path)

            for path in result.modified_files:
                table.add_row("[yellow]Modified[/yellow]", path)

            console.print(table)
            console.print(
                f"\nSummary: {len(result.added_files)} added, "
                f"{len(result.removed_files)} removed, "
                f"{len(result.modified_files)} modified, "
                f"{len(result.unchanged_files)} unchanged"
            )

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@cli.command()
@click.option(
    "-s", "--size",
    type=int,
    default=10,
    help="Test data size in MB",
)
@click.option(
    "-p", "--pattern",
    type=click.Choice(["random", "zeros", "text", "mixed"]),
    default="mixed",
    help="Test data pattern",
)
@click.option(
    "-i", "--iterations",
    type=int,
    default=3,
    help="Iterations per benchmark",
)
@click.option(
    "--parallel/--no-parallel",
    default=False,
    help="Include parallel processing benchmark",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output results in JSON format",
)
@click.pass_context
def benchmark(
    ctx: click.Context,
    size: int,
    pattern: str,
    iterations: int,
    parallel: bool,
    json_output: bool,
) -> None:
    """Run performance benchmarks.

    Tests compression and extraction performance with various methods.

    Examples:

    \b
      mzip benchmark
      mzip benchmark --size 50 --pattern text
      mzip benchmark --parallel --iterations 5
    """
    import json as json_module

    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table

    from zipextractor.core.benchmark import (
        BenchmarkType,
        run_compression_benchmark,
        run_parallel_benchmark,
    )
    from zipextractor.core.parallel import cpu_info

    console = get_console()
    verbose = ctx.obj.get("verbose", False)

    data_size = size * 1024 * 1024  # Convert to bytes

    console.print(f"[bold]Running benchmarks with {size}MB {pattern} data[/bold]\n")

    # Show system info
    info = cpu_info()
    if verbose:
        console.print(f"CPU: {info.get('model', 'Unknown')}")
        console.print(f"Cores: {info['cpu_count']}")
        console.print(f"Recommended workers: {info['recommended_workers']}")
        console.print()

    all_results: list[dict[str, Any]] = []

    # Run compression benchmarks
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Running compression benchmarks...", total=None)

        def progress_callback(_current: int, _total: int, name: str) -> None:
            progress.update(task, description=f"Benchmarking: {name}")

        suite = run_compression_benchmark(
            data_size=data_size,
            data_pattern=pattern,
            iterations=iterations,
            progress_callback=progress_callback,
        )

    if json_output:
        for result in suite.results:
            all_results.append({
                "name": result.name,
                "type": result.benchmark_type.name,
                "throughput_mbps": round(result.throughput_mbps, 2),
                "ratio": round(result.compression_ratio, 2),
                "time_ms": round(result.avg_duration_ms, 1),
            })
    else:
        # Display compression results
        table = Table(title="Compression Benchmarks")
        table.add_column("Method", style="cyan")
        table.add_column("Throughput", justify="right")
        table.add_column("Ratio", justify="right")
        table.add_column("Time (ms)", justify="right")
        table.add_column("Space Saved", justify="right")

        for result in sorted(suite.results, key=lambda r: -r.throughput_mbps):
            table.add_row(
                result.name,
                f"{result.throughput_mbps:.2f} MB/s",
                f"{result.compression_ratio:.2f}x",
                f"{result.avg_duration_ms:.0f}",
                f"{result.space_saving:.1f}%",
            )

        console.print(table)
        console.print()

    # Run parallel benchmarks if requested
    if parallel:
        console.print("[bold]Running parallel extraction benchmarks...[/bold]\n")

        parallel_suite = run_parallel_benchmark(
            data_size=data_size,
            file_count=50,
            iterations=iterations,
        )

        if json_output:
            for result in parallel_suite.results:
                all_results.append({
                    "name": result.name,
                    "type": "PARALLEL",
                    "throughput_mbps": round(result.throughput_mbps, 2),
                    "time_ms": round(result.avg_duration_ms, 1),
                    "workers": result.config.get("workers", 0),
                })
        else:
            table = Table(title="Parallel Extraction Benchmarks")
            table.add_column("Workers", style="cyan", justify="right")
            table.add_column("Throughput", justify="right")
            table.add_column("Time (ms)", justify="right")
            table.add_column("Speedup", justify="right")

            results = sorted(
                parallel_suite.results,
                key=lambda r: r.config.get("workers", 0)
            )
            baseline_time = results[0].avg_duration_ms if results else 1

            for result in results:
                workers = result.config.get("workers", 0)
                avg_time = result.avg_duration_ms
                speedup = baseline_time / avg_time if avg_time > 0 else 0

                table.add_row(
                    str(workers),
                    f"{result.throughput_mbps:.2f} MB/s",
                    f"{result.avg_duration_ms:.0f}",
                    f"{speedup:.2f}x",
                )

            console.print(table)
            console.print()

    # Output JSON if requested
    if json_output:
        console.print(json_module.dumps(all_results, indent=2))
    else:
        # Summary
        fastest = suite.get_fastest(BenchmarkType.COMPRESSION)
        best_ratio = suite.get_best_ratio(BenchmarkType.COMPRESSION)

        console.print("[bold]Summary:[/bold]")
        if fastest:
            throughput = fastest.throughput_mbps
            console.print(f"  Fastest: [green]{fastest.name}[/green] ({throughput:.2f} MB/s)")
        if best_ratio:
            ratio = best_ratio.compression_ratio
            console.print(f"  Best ratio: [green]{best_ratio.name}[/green] ({ratio:.2f}x)")


if __name__ == "__main__":
    cli()
