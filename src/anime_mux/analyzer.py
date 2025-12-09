"""Analyzer module - combines discovery and probing into AnalysisResult."""

from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from .discovery import (
    discover_audio_sources,
    discover_subtitle_sources,
    find_video_files,
)
from .matcher import extract_episode_numbers
from .models import AnalysisResult, Episode, ExternalSource, Track, TrackType
from .probe import parse_tracks, probe_external_file, probe_file, ProbeError
from .utils import console


def _find_common_tracks(episodes: list[Episode], track_type: TrackType) -> list[str]:
    """Find track identity_keys present in ALL episodes."""
    if not episodes:
        return []

    # Get tracks of the specified type from first episode
    first_ep = episodes[0]
    common_keys = {
        t.identity_key
        for t in first_ep.embedded_tracks
        if t.track_type == track_type
    }

    # Intersect with each subsequent episode
    for ep in episodes[1:]:
        ep_keys = {
            t.identity_key
            for t in ep.embedded_tracks
            if t.track_type == track_type
        }
        common_keys &= ep_keys

    return sorted(common_keys)


def _detect_missing_tracks(
    episodes: list[Episode], common_audio: list[str], common_subs: list[str]
) -> dict[int, list[str]]:
    """Detect which episodes are missing which tracks."""
    missing: dict[int, list[str]] = {}

    all_audio_keys = set(common_audio)
    all_sub_keys = set(common_subs)

    for ep in episodes:
        ep_audio_keys = {
            t.identity_key
            for t in ep.embedded_tracks
            if t.track_type == TrackType.AUDIO
        }
        ep_sub_keys = {
            t.identity_key
            for t in ep.embedded_tracks
            if t.track_type == TrackType.SUBTITLE
        }

        missing_audio = all_audio_keys - ep_audio_keys
        missing_subs = all_sub_keys - ep_sub_keys

        if missing_audio or missing_subs:
            missing[ep.number] = list(missing_audio | missing_subs)

    return missing


def analyze_series(
    directory: Path,
    audio_dir: Path | None = None,
    subs_dir: Path | None = None,
) -> AnalysisResult | None:
    """
    Analyze a series directory and build a complete AnalysisResult.

    Args:
        directory: Directory containing video files
        audio_dir: Optional explicit audio directory
        subs_dir: Optional explicit subtitle directory

    Returns:
        AnalysisResult or None if no videos found
    """
    # Step 1: Find video files
    console.print("[blue]Scanning for video files...[/blue]")
    video_files = find_video_files(directory)

    if not video_files:
        console.print("[red]No video files found.[/red]")
        return None

    console.print(f"Found {len(video_files)} video file(s)")

    # Step 2: Extract episode numbers
    video_map = extract_episode_numbers(video_files)
    if not video_map:
        console.print(
            "[red]Could not detect episode pattern from filenames.[/red]"
        )
        return None

    console.print(f"Detected episodes: {sorted(video_map.keys())}")

    # Step 3: Probe video files
    console.print("\n[blue]Probing video files...[/blue]")
    episodes: dict[int, Episode] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Probing", total=len(video_map))

        for ep_num, video_path in sorted(video_map.items()):
            try:
                probe_data = probe_file(video_path)
                tracks = parse_tracks(probe_data, video_path)

                episodes[ep_num] = Episode(
                    number=ep_num,
                    video_file=video_path,
                    embedded_tracks=tracks,
                )
            except ProbeError as e:
                console.print(f"[yellow]Warning: {e}[/yellow]")
                # Create episode with no embedded tracks
                episodes[ep_num] = Episode(
                    number=ep_num,
                    video_file=video_path,
                )

            progress.advance(task)

    # Step 4: Discover external sources
    console.print("\n[blue]Searching for external audio sources...[/blue]")
    external_audio = discover_audio_sources(directory, audio_dir)

    for name, source in external_audio.items():
        console.print(f"  -> Found: {name} ({len(source.files)} files)")

    console.print("\n[blue]Searching for external subtitle sources...[/blue]")
    external_subs = discover_subtitle_sources(directory, subs_dir)

    for name, source in external_subs.items():
        ep_count = len(source.files)
        all_episodes = set(episodes.keys())
        source_episodes = set(source.files.keys())
        missing = all_episodes - source_episodes
        if missing:
            console.print(
                f"  -> Found: {name} ({ep_count} files) "
                f"[yellow]missing: {sorted(missing)}[/yellow]"
            )
        else:
            console.print(f"  -> Found: {name} ({ep_count} files)")

    # Step 5: Probe external files and attach to episodes
    unmatched_files: list[Path] = []

    # Attach external audio to episodes
    for source_name, source in external_audio.items():
        for ep_num, audio_path in source.files.items():
            if ep_num in episodes:
                track = probe_external_file(audio_path, TrackType.AUDIO)
                if track:
                    episodes[ep_num].external_audio[source_name] = track
                else:
                    unmatched_files.append(audio_path)
            else:
                unmatched_files.append(audio_path)

    # Attach external subs to episodes
    for source_name, source in external_subs.items():
        for ep_num, sub_path in source.files.items():
            if ep_num in episodes:
                track = probe_external_file(sub_path, TrackType.SUBTITLE)
                if track:
                    episodes[ep_num].external_subs[source_name] = track
                else:
                    unmatched_files.append(sub_path)
            else:
                unmatched_files.append(sub_path)

    # Step 6: Find common embedded tracks
    episode_list = list(episodes.values())
    common_audio = _find_common_tracks(episode_list, TrackType.AUDIO)
    common_subs = _find_common_tracks(episode_list, TrackType.SUBTITLE)

    # Step 7: Detect missing tracks
    missing_tracks = _detect_missing_tracks(episode_list, common_audio, common_subs)

    return AnalysisResult(
        episodes=episodes,
        common_embedded_audio=common_audio,
        common_embedded_subs=common_subs,
        external_audio_sources=external_audio,
        external_subtitle_sources=external_subs,
        missing_tracks=missing_tracks,
        unmatched_external_files=unmatched_files,
    )


def get_track_by_identity(episode: Episode, identity_key: str) -> Track | None:
    """Find a track in an episode by its identity key."""
    for track in episode.embedded_tracks:
        if track.identity_key == identity_key:
            return track
    return None
