"""CLI interface for anime-mux."""

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.prompt import Confirm, Prompt

from . import __version__
from .analyzer import analyze_series
from .executor import check_existing_outputs, execute_plan
from .planner import build_merge_plan, display_merge_plan
from .probe import check_ffprobe
from .selector import AbortError, display_analysis, select_tracks
from .utils import console

app = typer.Typer(
    name="anime-mux",
    help="Consolidate anime releases into clean MKV files",
    add_completion=False,
)


def version_callback(value: bool):
    if value:
        console.print(f"anime-mux version {__version__}")
        raise typer.Exit()


@app.command()
def main(
    directory: Path = typer.Argument(
        ...,
        help="Directory containing video files",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory (default: <directory>/output)",
    ),
    audio_dir: Optional[Path] = typer.Option(
        None,
        "--audio-dir",
        "-a",
        help="Directory to search for external audio files",
    ),
    subs_dir: Optional[Path] = typer.Option(
        None,
        "--subs-dir",
        "-s",
        help="Directory to search for external subtitle files",
    ),
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    """
    Analyze video files and interactively select tracks to keep.

    anime-mux consolidates anime releases by filtering embedded tracks
    and/or merging external audio/subtitle files into clean MKV containers.
    """
    try:
        _run(directory, output, audio_dir, subs_dir)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
        sys.exit(1)
    except AbortError as e:
        console.print(f"\n[yellow]{e}[/yellow]")
        sys.exit(1)


def _run(
    directory: Path,
    output: Optional[Path],
    audio_dir: Optional[Path],
    subs_dir: Optional[Path],
):
    """Main workflow."""
    console.print(f"\n[bold]anime-mux v{__version__}[/bold]")
    console.print("=" * 50)

    # Check ffprobe
    if not check_ffprobe():
        console.print("[red]Error: ffprobe not found. Please install ffmpeg.[/red]")
        sys.exit(1)

    # Determine output directory
    output_dir = output or (directory / "output")

    # Phase 1: Analyze
    analysis = analyze_series(directory, audio_dir, subs_dir)
    if not analysis:
        sys.exit(1)

    if not analysis.common_embedded_audio and not analysis.external_audio_sources:
        console.print("[red]No audio sources found (embedded or external).[/red]")
        sys.exit(1)

    # Phase 2: Display and select
    audio_options, sub_options = display_analysis(analysis)

    if not audio_options:
        console.print("[red]No audio tracks available for selection.[/red]")
        sys.exit(1)

    selection_result = select_tracks(analysis, audio_options, sub_options)

    # Phase 3: Build plan
    plan = build_merge_plan(analysis, selection_result, output_dir)

    if not plan.jobs:
        console.print("[yellow]No files to process after selections.[/yellow]")
        sys.exit(0)

    # Phase 4: Display plan and confirm
    display_merge_plan(plan)

    # Check for existing files and ask user what to do
    existing = check_existing_outputs(plan)
    overwrite = False

    if existing:
        console.print(
            f"\n[yellow]Warning: {len(existing)} of {len(plan.jobs)} output file(s) "
            f"already exist:[/yellow]"
        )
        for path in existing[:5]:  # Show first 5
            console.print(f"  [dim]- {path.name}[/dim]")
        if len(existing) > 5:
            console.print(f"  [dim]... and {len(existing) - 5} more[/dim]")

        console.print("\nWhat would you like to do?")
        console.print("  [cyan]o[/cyan] - Overwrite existing files")
        console.print("  [cyan]s[/cyan] - Skip existing files (process only new)")
        console.print("  [cyan]a[/cyan] - Abort")

        while True:
            choice = Prompt.ask(
                "Choice",
                choices=["o", "s", "a"],
                default="s",
            )
            if choice == "o":
                overwrite = True
                break
            elif choice == "s":
                overwrite = False
                break
            elif choice == "a":
                console.print("[yellow]Aborted.[/yellow]")
                sys.exit(0)
    else:
        if not Confirm.ask("\nProceed with merge?", default=True):
            console.print("[yellow]Aborted.[/yellow]")
            sys.exit(0)

    # Phase 5: Execute
    successful, failed, skipped = execute_plan(plan, overwrite=overwrite)

    # Summary
    console.print("\n" + "=" * 50)
    if failed == 0 and skipped == 0:
        console.print(
            f"[bold green]Complete![/bold green] "
            f"{successful} file(s) written to {output_dir}"
        )
    elif failed == 0:
        console.print(
            f"[bold green]Complete![/bold green] "
            f"{successful} file(s) written, {skipped} skipped (already existed)"
        )
    else:
        console.print(
            f"[bold yellow]Completed with errors.[/bold yellow] "
            f"{successful} succeeded, {failed} failed, {skipped} skipped."
        )
        sys.exit(1)


if __name__ == "__main__":
    app()
