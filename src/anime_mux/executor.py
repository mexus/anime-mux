"""Execute FFmpeg commands for merging."""

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from .models import MergeJob, MergePlan
from .utils import console


def build_ffmpeg_command(job: MergeJob, transcode_audio: bool = False) -> list[str]:
    """
    Build FFmpeg command for a merge job.

    Key considerations:
    - Use -map to select specific streams
    - Video/subtitles: stream copy (no transcoding)
    - Audio: copy as-is (or re-encode to AAC 256k if transcode_audio=True)
    - Use -disposition to set default tracks
    - Preserve attachments (fonts) from source
    """
    cmd = ["ffmpeg", "-y"]

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
        cmd.extend(
            ["-map", f"{primary_input}:t?"]
        )  # :t for attachments, ? for optional
        # Fix audio/video interleaving when attachments are mapped from a different
        # input than audio. Without this, ffmpeg may write all audio packets first,
        # causing players to appear to have no audio during video playback.
        cmd.extend(["-max_interleave_delta", "0"])

    # Video, subtitles, attachments: copy (no transcoding)
    # Audio: copy or re-encode to AAC
    cmd.extend(["-c:v", "copy"])
    if transcode_audio:
        cmd.extend(["-c:a", "aac", "-b:a", "256k"])
    else:
        cmd.extend(["-c:a", "copy"])
    cmd.extend(["-c:s", "copy"])

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


def run_ffmpeg(cmd: list[str]) -> tuple[bool, str | None]:
    """
    Run FFmpeg command with proper error handling.

    Returns:
        Tuple of (success, error_message). error_message is None on success.
    """
    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return True, None
    except subprocess.CalledProcessError as e:
        # Extract error lines from stderr
        error_lines = []
        if e.stderr:
            for line in e.stderr.split("\n"):
                if "error" in line.lower() or "invalid" in line.lower():
                    error_lines.append(line)
        return False, "\n".join(error_lines) if error_lines else "Unknown error"
    except FileNotFoundError:
        return False, "ffmpeg not found in PATH"


def _process_job(
    job: MergeJob, overwrite: bool, transcode_audio: bool, verbose: bool = False
) -> tuple[int, bool, str | None]:
    """
    Process a single merge job.

    Returns:
        Tuple of (episode_number, success, error_message)
    """
    # Check if output already exists
    if job.output_path.exists() and not overwrite:
        return job.episode.number, True, None  # None success = skipped

    # Build and execute command
    cmd = build_ffmpeg_command(job, transcode_audio=transcode_audio)
    if verbose:
        import shlex

        console.print(f"\n[dim]Episode {job.episode.number}:[/dim]")
        console.print(f"[yellow]{shlex.join(cmd)}[/yellow]\n")
    success, error = run_ffmpeg(cmd)
    return job.episode.number, success, error


def execute_plan(
    plan: MergePlan,
    overwrite: bool = False,
    transcode_audio: bool = False,
    verbose: bool = False,
) -> tuple[int, int, int]:
    """
    Execute all jobs in a merge plan using parallel processing.

    Args:
        plan: The merge plan to execute
        overwrite: If True, overwrite existing output files. If False, skip them.
        transcode_audio: If True, re-encode audio to AAC. If False, copy audio as-is.
        verbose: If True, print ffmpeg commands before executing.

    Returns:
        Tuple of (successful_count, failed_count, skipped_count)
    """
    # Create output directory
    plan.output_directory.mkdir(parents=True, exist_ok=True)

    # Calculate number of workers (half of CPU cores, minimum 1)
    # Use 1 worker if verbose to keep output readable
    num_workers = 1 if verbose else max(1, (os.cpu_count() or 2) // 2)

    console.print(
        f"\n[blue]Processing {len(plan.jobs)} files using {num_workers} workers...[/blue]"
    )

    successful = 0
    failed = 0
    skipped = 0
    errors: list[tuple[int, str]] = []  # (episode, error_msg)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Merging", total=len(plan.jobs))

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Submit all jobs
            futures = {
                executor.submit(
                    _process_job, job, overwrite, transcode_audio, verbose
                ): job
                for job in plan.jobs
            }

            # Process completed jobs as they finish
            for future in as_completed(futures):
                ep_num, success, error = future.result()

                if success is None:
                    # Skipped
                    skipped += 1
                elif success:
                    successful += 1
                else:
                    failed += 1
                    errors.append((ep_num, error or "Unknown error"))

                progress.advance(task)

    # Print errors at the end (cleaner output)
    for ep_num, error in sorted(errors):
        console.print(f"[red]Episode {ep_num} failed:[/red] [dim]{error}[/dim]")

    return successful, failed, skipped


def check_existing_outputs(plan: MergePlan) -> list[Path]:
    """Check which output files already exist."""
    existing = []
    for job in plan.jobs:
        if job.output_path.exists():
            existing.append(job.output_path)
    return existing
