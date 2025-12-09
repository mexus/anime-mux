"""Build merge plan from user selections."""

from pathlib import Path

from rich.table import Table

from .analyzer import get_track_by_identity
from .models import AnalysisResult, Episode, MergeJob, MergePlan, Track, TrackType
from .selector import SelectionResult
from .utils import console


def _get_video_track(episode: Episode) -> Track | None:
    """Get the video track from an episode."""
    for track in episode.embedded_tracks:
        if track.track_type == TrackType.VIDEO:
            return track
    return None


def _resolve_audio_tracks(
    episode: Episode,
    selection_result: SelectionResult,
    analysis: AnalysisResult,
) -> list[Track]:
    """Resolve audio tracks for an episode based on selection."""
    tracks: list[Track] = []

    for sel in selection_result.audio_selections:
        if sel.is_embedded:
            # Find embedded track by identity key
            track = get_track_by_identity(episode, sel.identifier)
            if track:
                tracks.append(track)
        else:
            # External track
            source_name = sel.identifier

            # Check for substitution
            if episode.number in selection_result.audio_substitutions:
                source_name = selection_result.audio_substitutions[episode.number]

            # Get from episode's external audio
            if source_name in episode.external_audio:
                tracks.append(episode.external_audio[source_name])

    return tracks


def _resolve_subtitle_tracks(
    episode: Episode,
    selection_result: SelectionResult,
    analysis: AnalysisResult,
) -> list[Track]:
    """Resolve subtitle tracks for an episode based on selection."""
    tracks: list[Track] = []

    for sel in selection_result.subtitle_selections:
        if sel.is_embedded:
            track = get_track_by_identity(episode, sel.identifier)
            if track:
                tracks.append(track)
        else:
            source_name = sel.identifier

            # Check for substitution
            if episode.number in selection_result.subtitle_substitutions:
                source_name = selection_result.subtitle_substitutions[episode.number]

            if source_name in episode.external_subs:
                tracks.append(episode.external_subs[source_name])

    return tracks


def build_merge_plan(
    analysis: AnalysisResult,
    selection_result: SelectionResult,
    output_dir: Path,
) -> MergePlan:
    """
    Build a merge plan from analysis and user selections.

    Args:
        analysis: The analysis result
        selection_result: User's track selections
        output_dir: Directory for output files

    Returns:
        MergePlan ready for execution
    """
    jobs: list[MergeJob] = []
    skipped = list(selection_result.skipped_episodes)

    for ep_num, episode in sorted(analysis.episodes.items()):
        if ep_num in skipped:
            continue

        # Get video track
        video_track = _get_video_track(episode)
        if not video_track:
            console.print(
                f"[yellow]Warning: No video track in episode {ep_num}, skipping.[/yellow]"
            )
            skipped.append(ep_num)
            continue

        # Resolve audio and subtitle tracks
        audio_tracks = _resolve_audio_tracks(episode, selection_result, analysis)
        subtitle_tracks = _resolve_subtitle_tracks(episode, selection_result, analysis)

        # Build output path (preserve original filename)
        output_path = output_dir / episode.video_file.name

        job = MergeJob(
            episode=episode,
            output_path=output_path,
            video_tracks=[video_track],
            audio_tracks=audio_tracks,
            subtitle_tracks=subtitle_tracks,
            preserve_attachments=True,
        )
        jobs.append(job)

    return MergePlan(
        jobs=jobs,
        output_directory=output_dir,
        skipped_episodes=skipped,
    )


def display_merge_plan(plan: MergePlan) -> None:
    """Display the merge plan for user confirmation."""
    console.print("\n" + "=" * 70)
    console.print("[bold]MERGE PLAN[/bold]", justify="center")
    console.print("=" * 70)

    console.print(f"\nOutput directory: [cyan]{plan.output_directory}[/cyan]")
    console.print(f"{len(plan.jobs)} file(s) will be created:\n")

    table = Table(show_header=True)
    table.add_column("Episode", style="cyan")
    table.add_column("Output", style="white")
    table.add_column("Audio", style="green")
    table.add_column("Subs", style="yellow")

    for job in plan.jobs:
        audio_desc = ", ".join(
            t.display_name[:20] + "..." if len(t.display_name) > 23 else t.display_name
            for t in job.audio_tracks
        ) or "-"

        sub_desc = ", ".join(
            t.display_name[:20] + "..." if len(t.display_name) > 23 else t.display_name
            for t in job.subtitle_tracks
        ) or "-"

        table.add_row(
            str(job.episode.number),
            job.output_path.name,
            audio_desc,
            sub_desc,
        )

    console.print(table)

    if plan.skipped_episodes:
        console.print(
            f"\n[yellow]Skipped episodes: {sorted(plan.skipped_episodes)}[/yellow]"
        )
