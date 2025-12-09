"""Interactive track selection."""

from dataclasses import dataclass

from rich.prompt import Prompt
from rich.table import Table

from .analyzer import get_track_by_identity
from .models import AnalysisResult, Episode, ExternalSource, Track, TrackType
from .utils import console


class AbortError(Exception):
    """User aborted the operation."""

    pass


@dataclass
class TrackSelection:
    """Represents a user's track selection."""

    # For embedded tracks: identity_key
    # For external tracks: source_name
    identifier: str
    is_embedded: bool
    display_name: str


@dataclass
class SelectionResult:
    """Result of the selection process."""

    audio_selections: list[TrackSelection]
    subtitle_selections: list[TrackSelection]
    # For episodes missing a selected source, map episode -> alternative source
    audio_substitutions: dict[int, str]
    subtitle_substitutions: dict[int, str]
    skipped_episodes: list[int]


def display_analysis(analysis: AnalysisResult) -> None:
    """Display the analysis results in a formatted table."""
    console.print("\n" + "=" * 70)
    console.print("[bold]TRACK ANALYSIS[/bold]", justify="center")
    console.print("=" * 70)

    # Audio table
    audio_table = Table(title="Available Audio Tracks", show_header=True)
    audio_table.add_column("#", style="cyan", width=3)
    audio_table.add_column("Source", style="green")
    audio_table.add_column("Track", style="white")
    audio_table.add_column("Coverage", style="yellow")

    idx = 1
    audio_options: list[tuple[str, bool, str]] = []  # (id, is_embedded, display)

    # Embedded audio
    for identity_key in analysis.common_embedded_audio:
        # Get display name from first episode
        first_ep = next(iter(analysis.episodes.values()))
        track = get_track_by_identity(first_ep, identity_key)
        display = track.display_name if track else identity_key
        audio_table.add_row(str(idx), "[embedded]", display, "all")
        audio_options.append((identity_key, True, display))
        idx += 1

    # External audio
    for name, source in analysis.external_audio_sources.items():
        ep_count = len(source.files)
        total_eps = len(analysis.episodes)
        coverage = "all" if ep_count == total_eps else f"{ep_count}/{total_eps}"
        audio_table.add_row(str(idx), name, "[external]", coverage)
        audio_options.append((name, False, name))
        idx += 1

    console.print(audio_table)

    # Subtitle table
    sub_table = Table(title="Available Subtitle Tracks", show_header=True)
    sub_table.add_column("#", style="cyan", width=3)
    sub_table.add_column("Source", style="green")
    sub_table.add_column("Track", style="white")
    sub_table.add_column("Coverage", style="yellow")

    idx = 1
    sub_options: list[tuple[str, bool, str]] = []

    # Embedded subtitles
    for identity_key in analysis.common_embedded_subs:
        first_ep = next(iter(analysis.episodes.values()))
        track = get_track_by_identity(first_ep, identity_key)
        display = track.display_name if track else identity_key
        sub_table.add_row(str(idx), "[embedded]", display, "all")
        sub_options.append((identity_key, True, display))
        idx += 1

    # External subtitles
    for name, source in analysis.external_subtitle_sources.items():
        ep_count = len(source.files)
        total_eps = len(analysis.episodes)
        coverage = "all" if ep_count == total_eps else f"{ep_count}/{total_eps}"
        sub_table.add_row(str(idx), name, "[external]", coverage)
        sub_options.append((name, False, name))
        idx += 1

    console.print(sub_table)

    return audio_options, sub_options


def _parse_selection(response: str, max_idx: int) -> list[int] | None:
    """Parse a comma-separated selection string into indices."""
    if response.strip() == "0":
        return list(range(1, max_idx + 1))  # All
    if response.strip() == "-1":
        return []  # None

    try:
        indices = [int(x.strip()) for x in response.split(",")]
        if all(1 <= i <= max_idx for i in indices):
            return indices
    except ValueError:
        pass

    return None


def select_tracks(
    analysis: AnalysisResult,
    audio_options: list[tuple[str, bool, str]],
    sub_options: list[tuple[str, bool, str]],
) -> SelectionResult:
    """
    Interactively select audio and subtitle tracks.

    Args:
        analysis: The analysis result
        audio_options: List of (identifier, is_embedded, display_name) for audio
        sub_options: List of (identifier, is_embedded, display_name) for subtitles

    Returns:
        SelectionResult with all selections
    """
    console.print("\n" + "=" * 70)
    console.print("[bold]TRACK SELECTION[/bold]", justify="center")
    console.print("=" * 70)

    # Audio selection
    console.print("\n[bold]Select audio track(s) to include:[/bold]")
    console.print("  Enter number(s) separated by comma, or 0 for all")
    console.print("  First selection will be marked as default\n")

    while True:
        response = Prompt.ask("Audio selection", default="1")
        indices = _parse_selection(response, len(audio_options))
        if indices is not None and len(indices) > 0:
            break
        console.print("[red]Invalid selection. Please enter valid number(s).[/red]")

    audio_selections = [
        TrackSelection(
            identifier=audio_options[i - 1][0],
            is_embedded=audio_options[i - 1][1],
            display_name=audio_options[i - 1][2],
        )
        for i in indices
    ]

    for sel in audio_selections:
        source_type = "[embedded]" if sel.is_embedded else "[external]"
        console.print(f"  [green]>[/green] {source_type} {sel.display_name}")

    # Subtitle selection
    console.print("\n[bold]Select subtitle track(s) to include:[/bold]")
    console.print("  Enter number(s), 0 for all, or -1 for none\n")

    while True:
        response = Prompt.ask("Subtitle selection", default="1" if sub_options else "-1")
        indices = _parse_selection(response, len(sub_options))
        if indices is not None:
            break
        console.print("[red]Invalid selection. Please enter valid number(s).[/red]")

    subtitle_selections = [
        TrackSelection(
            identifier=sub_options[i - 1][0],
            is_embedded=sub_options[i - 1][1],
            display_name=sub_options[i - 1][2],
        )
        for i in indices
    ]

    if subtitle_selections:
        for sel in subtitle_selections:
            source_type = "[embedded]" if sel.is_embedded else "[external]"
            console.print(f"  [green]>[/green] {source_type} {sel.display_name}")
    else:
        console.print("  [dim]No subtitles selected[/dim]")

    # Handle gaps for external sources
    audio_subs, audio_skipped = _handle_gaps(
        analysis, audio_selections, "audio"
    )
    sub_subs, sub_skipped = _handle_gaps(
        analysis, subtitle_selections, "subtitle"
    )

    skipped = list(set(audio_skipped) | set(sub_skipped))

    return SelectionResult(
        audio_selections=audio_selections,
        subtitle_selections=subtitle_selections,
        audio_substitutions=audio_subs,
        subtitle_substitutions=sub_subs,
        skipped_episodes=skipped,
    )


def _handle_gaps(
    analysis: AnalysisResult,
    selections: list[TrackSelection],
    track_type: str,
) -> tuple[dict[int, str], list[int]]:
    """
    Handle gaps where selected external source is missing episodes.

    Returns:
        Tuple of (substitutions dict, skipped episodes list)
    """
    substitutions: dict[int, str] = {}
    skipped: list[int] = []

    all_episodes = set(analysis.episodes.keys())

    # Get the sources dict based on track type
    if track_type == "audio":
        sources = analysis.external_audio_sources
    else:
        sources = analysis.external_subtitle_sources

    for selection in selections:
        if selection.is_embedded:
            # Embedded tracks are in all episodes (by definition of common)
            continue

        source = sources.get(selection.identifier)
        if not source:
            continue

        source_episodes = set(source.files.keys())
        missing = all_episodes - source_episodes

        if not missing:
            continue

        # Find alternatives for missing episodes
        for ep_num in sorted(missing):
            alternatives = [
                name
                for name, src in sources.items()
                if name != selection.identifier and ep_num in src.files
            ]

            if alternatives:
                console.print(
                    f"\n[yellow]Episode {ep_num} is missing from [{selection.identifier}].[/yellow]"
                )
                console.print(f"Available alternatives: {alternatives}")

                while True:
                    choice = Prompt.ask(
                        f"Use which source for episode {ep_num}? (or 'skip'/'abort')",
                        default=alternatives[0] if len(alternatives) == 1 else None,
                    )

                    if choice.lower() == "skip":
                        skipped.append(ep_num)
                        break
                    elif choice.lower() == "abort":
                        raise AbortError("User aborted due to missing episode")
                    elif choice in alternatives:
                        substitutions[ep_num] = choice
                        break
                    else:
                        console.print(f"[red]Invalid choice. Options: {alternatives + ['skip', 'abort']}[/red]")
            else:
                console.print(
                    f"\n[yellow]Episode {ep_num} has no available {track_type}.[/yellow]"
                )
                while True:
                    choice = Prompt.ask(
                        f"[S]kip episode {ep_num} or [A]bort?",
                        default="s",
                    )
                    if choice.lower() in ("s", "skip"):
                        skipped.append(ep_num)
                        break
                    elif choice.lower() in ("a", "abort"):
                        raise AbortError("User aborted due to missing episode")

    return substitutions, skipped
