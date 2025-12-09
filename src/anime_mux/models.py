"""Data models for anime-mux."""

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional


class TrackType(Enum):
    """Type of media track."""

    VIDEO = auto()
    AUDIO = auto()
    SUBTITLE = auto()
    ATTACHMENT = auto()


class TrackSource(Enum):
    """Source of a track."""

    EMBEDDED = auto()
    EXTERNAL = auto()


@dataclass
class Track:
    """Represents a single track (audio, subtitle, etc.)."""

    index: int
    track_type: TrackType
    codec: str
    language: str
    title: Optional[str]
    source: TrackSource
    source_file: Path
    channels: Optional[int] = None
    is_forced: bool = False
    is_default: bool = False

    @property
    def display_name(self) -> str:
        """Human-readable identifier for selection menus."""
        if self.track_type == TrackType.AUDIO:
            ch = f"{self.channels}ch" if self.channels else "?ch"
            label = self.title or self.codec
            return f"{self.language} - {label} ({ch})"
        elif self.track_type == TrackType.SUBTITLE:
            label = self.title or "Untitled"
            forced = " [forced]" if self.is_forced else ""
            return f"{self.language} - {label}{forced}"
        else:
            return f"{self.track_type.name}: {self.codec}"

    @property
    def identity_key(self) -> str:
        """
        Key used to match 'same' tracks across different episode files.
        Two tracks are considered equivalent if they have the same identity_key.
        """
        if self.track_type == TrackType.AUDIO:
            return f"audio|{self.language}|{self.title or ''}|{self.channels or 0}"
        elif self.track_type == TrackType.SUBTITLE:
            return f"sub|{self.language}|{self.title or ''}|{self.is_forced}"
        else:
            return f"{self.track_type.name}|{self.codec}"


@dataclass
class Episode:
    """Represents a single episode with all its available tracks."""

    number: int
    video_file: Path
    embedded_tracks: list[Track] = field(default_factory=list)
    external_audio: dict[str, Track] = field(default_factory=dict)
    external_subs: dict[str, Track] = field(default_factory=dict)

    def get_all_audio_options(self) -> list[tuple[str, Track]]:
        """Returns all audio options as (source_name, track) pairs."""
        options = []
        for t in self.embedded_tracks:
            if t.track_type == TrackType.AUDIO:
                options.append(("embedded", t))
        for name, t in self.external_audio.items():
            options.append((name, t))
        return options

    def get_all_subtitle_options(self) -> list[tuple[str, Track]]:
        """Returns all subtitle options as (source_name, track) pairs."""
        options = []
        for t in self.embedded_tracks:
            if t.track_type == TrackType.SUBTITLE:
                options.append(("embedded", t))
        for name, t in self.external_subs.items():
            options.append((name, t))
        return options


@dataclass
class ExternalSource:
    """Represents a directory of external audio or subtitle files."""

    name: str
    source_type: TrackType
    base_path: Path
    files: dict[int, Path] = field(default_factory=dict)


@dataclass
class MergeJob:
    """Specification for producing one output file."""

    episode: Episode
    output_path: Path
    video_tracks: list[Track] = field(default_factory=list)
    audio_tracks: list[Track] = field(default_factory=list)
    subtitle_tracks: list[Track] = field(default_factory=list)
    preserve_attachments: bool = True


@dataclass
class MergePlan:
    """Complete plan for processing a series."""

    jobs: list[MergeJob]
    output_directory: Path
    skipped_episodes: list[int] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """Result of analyzing a series directory."""

    episodes: dict[int, Episode]
    common_embedded_audio: list[str]
    common_embedded_subs: list[str]
    external_audio_sources: dict[str, ExternalSource]
    external_subtitle_sources: dict[str, ExternalSource]
    missing_tracks: dict[int, list[str]]
    unmatched_external_files: list[Path]
