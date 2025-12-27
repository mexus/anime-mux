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
    qp: Optional[int] = None  # If None, auto-calculate based on source (for h264_amf)

    def calculate_crf(
        self, width: Optional[int], height: Optional[int], bitrate: Optional[int]
    ) -> int:
        """
        Calculate optimal CRF based on resolution and bitrate.

        Base CRF by resolution:
        - 4K (2160p+): 17
        - 1080p: 19
        - 720p: 21
        - 480p: 23
        - Lower: 25

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
            base_crf = 17
            typical_bitrate = 20_000_000  # 20 Mbps typical for 4K anime
        elif h >= 1080:
            base_crf = 19
            typical_bitrate = 8_000_000  # 8 Mbps typical for 1080p anime
        elif h >= 720:
            base_crf = 21
            typical_bitrate = 4_000_000  # 4 Mbps typical for 720p anime
        elif h >= 480:
            base_crf = 23
            typical_bitrate = 2_000_000  # 2 Mbps typical for 480p
        else:
            base_crf = 25
            typical_bitrate = 1_000_000  # 1 Mbps for lower res

        # Adjust based on source bitrate
        if bitrate is not None and bitrate > 0:
            ratio = bitrate / typical_bitrate
            if ratio > 2.0:
                # Very high bitrate source - preserve more quality
                base_crf -= 2
            elif ratio > 1.5:
                # High bitrate source
                base_crf -= 1
            elif ratio < 0.5:
                # Low bitrate source - don't need to preserve as much
                base_crf += 1

        # Clamp to valid range
        return max(0, min(51, base_crf))

    def calculate_qp(
        self, width: Optional[int], height: Optional[int], bitrate: Optional[int]
    ) -> int:
        """
        Calculate optimal QP for VA-API encoder based on resolution and bitrate.

        QP (Quantization Parameter) is used by h264_vaapi instead of CRF.
        The scale is similar (0-51, lower = better quality), but hardware
        encoders tend to produce slightly lower quality than libx264's CRF
        at the same value, so we use slightly lower (better) base values.

        Base QP by resolution:
        - 4K (2160p+): 15
        - 1080p: 17
        - 720p: 19
        - 480p: 21
        - Lower: 23
        """
        if self.qp is not None:
            return self.qp

        # Use defaults if dimensions unknown
        h = height or 1080

        # Base QP by resolution (slightly lower than CRF for similar quality)
        if h >= 2160:
            base_qp = 15
            typical_bitrate = 20_000_000
        elif h >= 1080:
            base_qp = 17
            typical_bitrate = 8_000_000
        elif h >= 720:
            base_qp = 19
            typical_bitrate = 4_000_000
        elif h >= 480:
            base_qp = 21
            typical_bitrate = 2_000_000
        else:
            base_qp = 23
            typical_bitrate = 1_000_000

        # Adjust based on source bitrate
        if bitrate is not None and bitrate > 0:
            ratio = bitrate / typical_bitrate
            if ratio > 2.0:
                base_qp -= 2
            elif ratio > 1.5:
                base_qp -= 1
            elif ratio < 0.5:
                base_qp += 1

        return max(0, min(51, base_qp))


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
