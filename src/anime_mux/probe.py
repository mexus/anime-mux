"""FFprobe wrapper for media file analysis."""

import json
import subprocess
import sys
from pathlib import Path

from .models import Track, TrackSource, TrackType
from .utils import console


class ProbeError(Exception):
    """Error during media probing."""

    pass


def check_ffprobe() -> bool:
    """Check if ffprobe is available."""
    try:
        subprocess.run(
            ["ffprobe", "-version"],
            capture_output=True,
            check=True,
        )
        return True
    except FileNotFoundError:
        return False
    except subprocess.CalledProcessError:
        return False


def probe_file(file_path: Path) -> dict:
    """
    Run ffprobe and return parsed JSON.

    Raises:
        ProbeError: If ffprobe fails or returns invalid output
    """
    try:
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(file_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except FileNotFoundError:
        console.print("[red]Error: ffprobe not found. Please install ffmpeg.[/red]")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        raise ProbeError(f"ffprobe failed for {file_path.name}: {e}")
    except json.JSONDecodeError as e:
        raise ProbeError(f"Invalid ffprobe output for {file_path.name}: {e}")


def _get_tag(tags: dict, *keys: str) -> str | None:
    """Get a tag value, trying multiple key variations."""
    for k in keys:
        if k in tags:
            return tags[k]
        if k.upper() in tags:
            return tags[k.upper()]
        if k.lower() in tags:
            return tags[k.lower()]
    return None


def parse_tracks(probe_data: dict, source_file: Path) -> list[Track]:
    """Convert ffprobe output to Track objects."""
    tracks = []

    for stream in probe_data.get("streams", []):
        codec_type = stream.get("codec_type")

        if codec_type == "video":
            track_type = TrackType.VIDEO
        elif codec_type == "audio":
            track_type = TrackType.AUDIO
        elif codec_type == "subtitle":
            track_type = TrackType.SUBTITLE
        elif codec_type == "attachment":
            track_type = TrackType.ATTACHMENT
        else:
            continue

        tags = stream.get("tags", {})
        disposition = stream.get("disposition", {})

        track = Track(
            index=stream["index"],
            track_type=track_type,
            codec=stream.get("codec_name", "unknown"),
            language=_get_tag(tags, "language", "lang") or "und",
            title=_get_tag(tags, "title", "name"),
            source=TrackSource.EMBEDDED,
            source_file=source_file,
            channels=stream.get("channels") if codec_type == "audio" else None,
            is_forced=disposition.get("forced", 0) == 1,
            is_default=disposition.get("default", 0) == 1,
        )
        tracks.append(track)

    return tracks


def probe_external_file(file_path: Path, track_type: TrackType) -> Track | None:
    """
    Probe an external audio or subtitle file and return a Track.

    Returns None if probing fails.
    """
    try:
        probe_data = probe_file(file_path)
    except ProbeError:
        return None

    streams = probe_data.get("streams", [])
    if not streams:
        return None

    # Find the first stream of the expected type
    expected_codec_type = "audio" if track_type == TrackType.AUDIO else "subtitle"

    for stream in streams:
        if stream.get("codec_type") == expected_codec_type:
            tags = stream.get("tags", {})
            disposition = stream.get("disposition", {})

            return Track(
                index=stream["index"],
                track_type=track_type,
                codec=stream.get("codec_name", "unknown"),
                language=_get_tag(tags, "language", "lang") or "und",
                title=_get_tag(tags, "title", "name"),
                source=TrackSource.EXTERNAL,
                source_file=file_path,
                channels=stream.get("channels")
                if track_type == TrackType.AUDIO
                else None,
                is_forced=disposition.get("forced", 0) == 1,
                is_default=disposition.get("default", 0) == 1,
            )

    return None
