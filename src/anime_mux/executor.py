"""Execute FFmpeg commands for merging."""

import subprocess
from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from .models import MergeJob, MergePlan, Track
from .utils import console


def build_ffmpeg_command(job: MergeJob) -> list[str]:
    """
    Build FFmpeg command for a merge job.

    Key considerations:
    - Use -map to select specific streams
    - Use -c copy to avoid transcoding
    - Use -disposition to set default tracks
    - Preserve attachments (fonts) from source
    """
    cmd = ["ffmpeg", "-y"]  # -y to overwrite

    # Collect all input files
    input_files: list[Path] = []
    input_map: dict[Path, int] = {}

    def get_input_index(file_path: Path) -> int:
        if file_path not in input_map:
            input_map[file_path] = len(input_files)
            input_files.append(file_path)
        return input_map[file_path]

    # Register all source files
    for track in job.video_tracks + job.audio_tracks + job.subtitle_tracks:
        get_input_index(track.source_file)

    # Add inputs
    for f in input_files:
        cmd.extend(["-i", str(f)])

    # Map video tracks
    for track in job.video_tracks:
        input_idx = input_map[track.source_file]
        cmd.extend(["-map", f"{input_idx}:{track.index}"])

    # Map audio tracks
    for track in job.audio_tracks:
        input_idx = input_map[track.source_file]
        cmd.extend(["-map", f"{input_idx}:{track.index}"])

    # Map subtitle tracks
    for track in job.subtitle_tracks:
        input_idx = input_map[track.source_file]
        cmd.extend(["-map", f"{input_idx}:{track.index}"])

    # Map attachments from primary video file (fonts, etc.)
    if job.preserve_attachments:
        primary_input = input_map[job.episode.video_file]
        cmd.extend(["-map", f"{primary_input}:t?"])  # :t for attachments, ? for optional

    # Copy all codecs (no transcoding)
    cmd.extend(["-c", "copy"])

    # Set dispositions (first audio and first subtitle are default)
    if job.audio_tracks:
        cmd.extend(["-disposition:a:0", "default"])
        for i in range(1, len(job.audio_tracks)):
            cmd.extend([f"-disposition:a:{i}", "0"])

    if job.subtitle_tracks:
        cmd.extend(["-disposition:s:0", "default"])
        for i in range(1, len(job.subtitle_tracks)):
            cmd.extend([f"-disposition:s:{i}", "0"])

    # Output file
    cmd.append(str(job.output_path))

    return cmd


def run_ffmpeg(cmd: list[str], description: str) -> bool:
    """
    Run FFmpeg command with proper error handling.

    Returns:
        True if successful, False otherwise.
    """
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {description}[/red]")
        if e.stderr:
            # Filter for actual error messages
            for line in e.stderr.split("\n"):
                if "error" in line.lower() or "invalid" in line.lower():
                    console.print(f"[dim]{line}[/dim]")
        return False
    except FileNotFoundError:
        console.print("[red]Error: ffmpeg not found in PATH[/red]")
        console.print("[yellow]Install ffmpeg: https://ffmpeg.org/download.html[/yellow]")
        return False


def execute_plan(plan: MergePlan, overwrite: bool = False) -> tuple[int, int, int]:
    """
    Execute all jobs in a merge plan.

    Args:
        plan: The merge plan to execute
        overwrite: If True, overwrite existing output files. If False, skip them.

    Returns:
        Tuple of (successful_count, failed_count, skipped_count)
    """
    # Create output directory
    plan.output_directory.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[blue]Processing {len(plan.jobs)} files...[/blue]")

    successful = 0
    failed = 0
    skipped = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Merging", total=len(plan.jobs))

        for job in plan.jobs:
            progress.update(task, description=f"Ep {job.episode.number}")

            # Check if output already exists
            if job.output_path.exists() and not overwrite:
                skipped += 1
                progress.advance(task)
                continue

            # Build and execute command
            cmd = build_ffmpeg_command(job)

            if run_ffmpeg(cmd, f"Episode {job.episode.number}"):
                successful += 1
            else:
                failed += 1
                console.print(
                    f"[red]Failed to process episode {job.episode.number}[/red]"
                )

            progress.advance(task)

    return successful, failed, skipped


def check_existing_outputs(plan: MergePlan) -> list[Path]:
    """Check which output files already exist."""
    existing = []
    for job in plan.jobs:
        if job.output_path.exists():
            existing.append(job.output_path)
    return existing
