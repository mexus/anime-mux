"""Execute FFmpeg commands for merging."""

import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from .models import MergeJob, MergePlan, VideoCodec
from .probe import get_duration
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

    # Video codec handling
    if job.video_encoding.codec == VideoCodec.COPY:
        cmd.extend(["-c:v", "copy"])
    elif job.video_encoding.codec == VideoCodec.H264:
        cmd.extend(["-c:v", "libx264"])

        # Calculate CRF based on first video track's metadata
        if job.video_tracks:
            video_track = job.video_tracks[0]
            crf = job.video_encoding.calculate_crf(
                width=video_track.width,
                height=video_track.height,
                bitrate=video_track.bitrate,
            )
        else:
            # Fallback if no video track metadata
            crf = job.video_encoding.crf if job.video_encoding.crf else 19

        cmd.extend(["-crf", str(crf)])
        cmd.extend(["-preset", "medium"])
        # Ensure output is compatible with most players
        cmd.extend(["-pix_fmt", "yuv420p"])
    elif job.video_encoding.codec == VideoCodec.H264_AMF:
        cmd.extend(["-c:v", "h264_amf"])

        # Calculate QP based on first video track's metadata
        if job.video_tracks:
            video_track = job.video_tracks[0]
            qp = job.video_encoding.calculate_qp(
                width=video_track.width,
                height=video_track.height,
                bitrate=video_track.bitrate,
            )
        else:
            # Fallback if no video track metadata
            qp = job.video_encoding.qp if job.video_encoding.qp else 17

        # Use constant QP mode with quality-enhancing options
        cmd.extend(["-rc", "cqp"])
        cmd.extend(["-qp_i", str(qp), "-qp_p", str(qp)])
        cmd.extend(["-quality", "quality"])
        # Enable quality enhancement features (only work in VBR modes, but set for future)
        cmd.extend(["-preanalysis", "true"])
        # Ensure output is compatible with most players
        cmd.extend(["-pix_fmt", "yuv420p"])

    # Audio: copy or re-encode to AAC
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


def run_ffmpeg_with_progress(
    cmd: list[str],
    duration_seconds: float,
    progress: Progress,
    task_id: TaskID,
) -> tuple[bool, str | None]:
    """
    Run FFmpeg command with real-time progress updates.

    Args:
        cmd: FFmpeg command to run
        duration_seconds: Total duration of the video in seconds
        progress: Rich Progress instance
        task_id: Task ID for progress updates

    Returns:
        Tuple of (success, error_message). error_message is None on success.
    """
    # Add progress output to FFmpeg command
    # Insert before output file (last argument)
    cmd_with_progress = cmd[:-1] + ["-progress", "pipe:1", "-nostats", cmd[-1]]

    try:
        process = subprocess.Popen(
            cmd_with_progress,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

        # Parse progress output
        out_time_pattern = re.compile(r"out_time_us=(\d+)")
        error_output = []

        stdout = process.stdout
        assert stdout is not None, "stdout should be available with PIPE"

        while True:
            line = stdout.readline()
            if not line and process.poll() is not None:
                break

            # Parse out_time_us (microseconds)
            match = out_time_pattern.match(line)
            if match:
                out_time_us = int(match.group(1))
                out_time_seconds = out_time_us / 1_000_000
                # Update progress (percentage)
                percent = min(100, (out_time_seconds / duration_seconds) * 100)
                progress.update(task_id, completed=percent)

        # Capture any remaining stderr
        _, stderr = process.communicate()
        if stderr:
            for line in stderr.split("\n"):
                if "error" in line.lower() or "invalid" in line.lower():
                    error_output.append(line)

        if process.returncode != 0:
            return False, "\n".join(error_output) if error_output else "Unknown error"

        # Mark as complete
        progress.update(task_id, completed=100)
        return True, None

    except FileNotFoundError:
        return False, "ffmpeg not found in PATH"
    except Exception as e:
        return False, str(e)


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

    # Calculate number of workers
    # - 1 worker if verbose (to keep output readable)
    # - 1 worker if video encoding (encoder already uses multiple threads internally)
    # - Otherwise, half of CPU cores for stream-copy operations (I/O bound)
    is_encoding_video = plan.jobs and plan.jobs[0].video_encoding.codec in (
        VideoCodec.H264,
        VideoCodec.H264_AMF,
    )
    if verbose or is_encoding_video:
        num_workers = 1
    else:
        num_workers = max(1, (os.cpu_count() or 2) // 2)

    console.print(
        f"\n[blue]Processing {len(plan.jobs)} files using {num_workers} workers...[/blue]"
    )

    # Use different execution paths for encoding vs copying
    if is_encoding_video and not verbose:
        return _execute_with_progress(plan, overwrite, transcode_audio)
    else:
        return _execute_parallel(plan, overwrite, transcode_audio, verbose, num_workers)


def _execute_with_progress(
    plan: MergePlan,
    overwrite: bool,
    transcode_audio: bool,
) -> tuple[int, int, int]:
    """Execute jobs sequentially with per-file progress (for encoding)."""
    successful = 0
    failed = 0
    skipped = 0
    errors: list[tuple[int, str]] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        for i, job in enumerate(plan.jobs):
            # Check if output already exists
            if job.output_path.exists() and not overwrite:
                skipped += 1
                continue

            # Get duration for progress calculation
            duration = get_duration(job.episode.video_file)
            if duration is None or duration <= 0:
                duration = 1.0  # Fallback to avoid division by zero

            # Create task for this file
            task_desc = f"[{i + 1}/{len(plan.jobs)}] {job.output_path.name}"
            task_id = progress.add_task(task_desc, total=100)

            # Build and execute command with progress
            cmd = build_ffmpeg_command(job, transcode_audio=transcode_audio)
            success, error = run_ffmpeg_with_progress(cmd, duration, progress, task_id)

            # Update task to show completion status
            if success:
                successful += 1
                progress.update(task_id, description=f"[green]✓[/green] {task_desc}")
            else:
                failed += 1
                errors.append((job.episode.number, error or "Unknown error"))
                progress.update(task_id, description=f"[red]✗[/red] {task_desc}")

    # Print errors at the end
    for ep_num, error in sorted(errors):
        console.print(f"[red]Episode {ep_num} failed:[/red] [dim]{error}[/dim]")

    return successful, failed, skipped


def _execute_parallel(
    plan: MergePlan,
    overwrite: bool,
    transcode_audio: bool,
    verbose: bool,
    num_workers: int,
) -> tuple[int, int, int]:
    """Execute jobs in parallel (for stream-copy operations)."""
    successful = 0
    failed = 0
    skipped = 0
    errors: list[tuple[int, str]] = []

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
