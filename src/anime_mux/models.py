"""Data models for anime-mux."""

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional

from .constants import (
    BASE_CRF_1080P,
    BASE_CRF_4K,
    BASE_CRF_480P,
    BASE_CRF_720P,
    BASE_CRF_LOWER,
    BASE_QUALITY_1080P,
    BASE_QUALITY_4K,
    BASE_QUALITY_480P,
    BASE_QUALITY_720P,
    BASE_QUALITY_LOWER,
    HEVC_CODEC_OFFSET,
    HIGH_BITRATE_THRESHOLD,
    LOW_BITRATE_THRESHOLD,
    MAX_QUALITY_VALUE,
    MEDIUM_BITRATE_THRESHOLD,
    MIN_QUALITY_VALUE,
    TYPICAL_BITRATE_1080P,
    TYPICAL_BITRATE_4K,
    TYPICAL_BITRATE_480P,
    TYPICAL_BITRATE_720P,
    TYPICAL_BITRATE_LOWER,
)


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


class VideoCodec(Enum):
    """Supported video codecs for re-encoding."""

    COPY = auto()  # Stream copy (no re-encoding)
    H264 = auto()  # libx264 (software)
    H264_VAAPI = auto()  # h264_vaapi (Linux VA-API, works with AMD/Intel)
    HEVC = auto()  # libx265 (software)
    HEVC_VAAPI = auto()  # hevc_vaapi (Linux VA-API, works with AMD/Intel)


@dataclass
class VideoEncodingConfig:
    """Configuration for video encoding."""

    codec: VideoCodec = VideoCodec.COPY
    crf: Optional[int] = None  # If None, auto-calculate based on source (for libx264)
    quality: Optional[int] = (
        None  # If None, auto-calculate based on source (for VA-API)
    )

    def calculate_crf(
        self,
        width: Optional[int],
        height: Optional[int],
        bitrate: Optional[int],
        codec: "VideoCodec",
    ) -> int:
        """
        Calculate optimal CRF based on resolution, bitrate, and codec.

        Base CRF by resolution (for H.264):
        - 4K (2160p+): 18
        - 1080p: 20
        - 720p: 22
        - 480p: 24
        - Lower: 26

        HEVC uses +5 offset (it's more efficient, so higher CRF = same quality).

        Bitrate adjustment:
        - If source bitrate is significantly higher than typical for resolution,
          lower CRF by 1-2 to preserve quality.
        """
        if self.crf is not None:
            return self.crf

        # Use defaults if dimensions unknown
        h = height or 1080

        # Base CRF by resolution (using height as primary indicator)
        if h >= 2160:
            base_crf = BASE_CRF_4K
            typical_bitrate = TYPICAL_BITRATE_4K
        elif h >= 1080:
            base_crf = BASE_CRF_1080P
            typical_bitrate = TYPICAL_BITRATE_1080P
        elif h >= 720:
            base_crf = BASE_CRF_720P
            typical_bitrate = TYPICAL_BITRATE_720P
        elif h >= 480:
            base_crf = BASE_CRF_480P
            typical_bitrate = TYPICAL_BITRATE_480P
        else:
            base_crf = BASE_CRF_LOWER
            typical_bitrate = TYPICAL_BITRATE_LOWER

        # Adjust based on source bitrate
        if bitrate is not None and bitrate > 0:
            ratio = bitrate / typical_bitrate
            if ratio > HIGH_BITRATE_THRESHOLD:
                # Very high bitrate source - preserve more quality
                base_crf -= 2
            elif ratio > MEDIUM_BITRATE_THRESHOLD:
                # High bitrate source
                base_crf -= 1
            elif ratio < LOW_BITRATE_THRESHOLD:
                # Low bitrate source - don't need to preserve as much
                base_crf += 1

        # HEVC is ~30-50% more efficient than H.264, so we can use higher CRF
        # for equivalent quality. +5 is a conservative offset.
        if codec in (VideoCodec.HEVC, VideoCodec.HEVC_VAAPI):
            base_crf += HEVC_CODEC_OFFSET

        # Clamp to valid range
        return max(MIN_QUALITY_VALUE, min(MAX_QUALITY_VALUE, base_crf))

    def calculate_quality(
        self,
        width: Optional[int],
        height: Optional[int],
        bitrate: Optional[int],
        codec: "VideoCodec",
    ) -> int:
        """
        Calculate optimal global_quality for VA-API encoder based on resolution and bitrate.

        Used with -rc_mode CQP and -global_quality for VA-API encoders.
        Values 22-24 are recommended for 1080p HD content based on practical testing.

        Base quality by resolution (for H.264 VA-API):
        - 4K (2160p+): 20
        - 1080p: 22
        - 720p: 24
        - 480p: 26
        - Lower: 28

        HEVC uses +5 offset (it's more efficient, so higher value = same quality).
        """
        if self.quality is not None:
            return self.quality

        # Use defaults if dimensions unknown
        h = height or 1080

        # Base quality by resolution
        if h >= 2160:
            base_quality = BASE_QUALITY_4K
            typical_bitrate = TYPICAL_BITRATE_4K
        elif h >= 1080:
            base_quality = BASE_QUALITY_1080P
            typical_bitrate = TYPICAL_BITRATE_1080P
        elif h >= 720:
            base_quality = BASE_QUALITY_720P
            typical_bitrate = TYPICAL_BITRATE_720P
        elif h >= 480:
            base_quality = BASE_QUALITY_480P
            typical_bitrate = TYPICAL_BITRATE_480P
        else:
            base_quality = BASE_QUALITY_LOWER
            typical_bitrate = TYPICAL_BITRATE_LOWER

        # Adjust based on source bitrate
        if bitrate is not None and bitrate > 0:
            ratio = bitrate / typical_bitrate
            if ratio > HIGH_BITRATE_THRESHOLD:
                base_quality -= 2
            elif ratio > MEDIUM_BITRATE_THRESHOLD:
                base_quality -= 1
            elif ratio < LOW_BITRATE_THRESHOLD:
                base_quality += 1

        # HEVC is more efficient, use higher quality value for same visual quality
        if codec in (VideoCodec.HEVC, VideoCodec.HEVC_VAAPI):
            base_quality += HEVC_CODEC_OFFSET

        return max(MIN_QUALITY_VALUE, min(MAX_QUALITY_VALUE, base_quality))


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
    # Video metadata (only populated for VIDEO tracks)
    width: Optional[int] = None
    height: Optional[int] = None
    bitrate: Optional[int] = None  # bits per second

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
    video_encoding: VideoEncodingConfig = field(default_factory=VideoEncodingConfig)


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
