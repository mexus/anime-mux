"""Validation functions for output directory and disk space."""

import os
import shutil
from pathlib import Path

from .models import MergePlan, VideoCodec


def estimate_output_size(plan: MergePlan) -> int:
    """
    Estimate total output size in bytes.

    Based on input file sizes and expected compression ratio.
    """
    total_input_size = 0

    for job in plan.jobs:
        # Collect unique source files
        source_files = {job.episode.video_file}
        for track in (
            job.video_tracks + job.audio_tracks + job.subtitle_tracks
        ):
            source_files.add(track.source_file)

        for file_path in source_files:
            if file_path.exists():
                total_input_size += file_path.stat().st_size

    # Estimate compression based on codec
    if not plan.jobs:
        return total_input_size

    codec = plan.jobs[0].video_encoding.codec
    if codec == VideoCodec.COPY:
        # Copy mode: output ≈ input (minus filtered tracks)
        # Assume 90% of input size
        return int(total_input_size * 0.9)
    elif codec in (VideoCodec.HEVC, VideoCodec.HEVC_VAAPI):
        # HEVC: ~50% compression
        return int(total_input_size * 0.5)
    else:
        # H.264: ~70% compression
        return int(total_input_size * 0.7)


def check_disk_space(plan: MergePlan) -> tuple[bool, int, int]:
    """
    Check available disk space.

    Returns:
        Tuple of (is_sufficient, available_bytes, required_bytes)
    """
    required = estimate_output_size(plan)
    usage = shutil.disk_usage(plan.output_directory)
    available = usage.free
    return available >= required, available, required


def format_bytes(bytes_value: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_value < 1024:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024
    return f"{bytes_value:.1f} PB"


def validate_output_directory(directory: Path) -> tuple[bool, str]:
    """
    Validate that output directory is writable.

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Create directory if it doesn't exist
        directory.mkdir(parents=True, exist_ok=True)

        # Try to create a temporary file to test writability
        test_file = directory / f".anime_mux_test_{os.getpid()}"
        try:
            test_file.touch()
            test_file.unlink()
            return True, ""
        except OSError as e:
            return False, f"Cannot write to {directory}: {e}"

    except OSError as e:
        return False, f"Cannot create output directory {directory}: {e}"
