"""Tests for probe module."""

from pathlib import Path

from anime_mux.models import TrackSource, TrackType
from anime_mux.probe import _get_tag, parse_tracks


class TestGetTag:
    """Tests for _get_tag helper function."""

    def test_exact_match(self):
        tags = {"language": "eng"}
        assert _get_tag(tags, "language") == "eng"

    def test_uppercase_match(self):
        tags = {"LANGUAGE": "eng"}
        assert _get_tag(tags, "language") == "eng"

    def test_lowercase_match(self):
        tags = {"language": "eng"}
        assert _get_tag(tags, "LANGUAGE") == "eng"

    def test_first_key_priority(self):
        tags = {"language": "eng", "lang": "jpn"}
        assert _get_tag(tags, "language", "lang") == "eng"

    def test_fallback_key(self):
        tags = {"lang": "jpn"}
        assert _get_tag(tags, "language", "lang") == "jpn"

    def test_not_found(self):
        tags = {"other": "value"}
        assert _get_tag(tags, "language", "lang") is None

    def test_empty_tags(self):
        assert _get_tag({}, "language") is None


class TestParseTracks:
    """Tests for parse_tracks function."""

    def test_parse_video_track(self):
        probe_data = {
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "codec_name": "h264",
                    "tags": {},
                    "disposition": {"default": 1, "forced": 0},
                }
            ]
        }
        tracks = parse_tracks(probe_data, Path("/test/video.mkv"))

        assert len(tracks) == 1
        assert tracks[0].index == 0
        assert tracks[0].track_type == TrackType.VIDEO
        assert tracks[0].codec == "h264"
        assert tracks[0].source == TrackSource.EMBEDDED

    def test_parse_audio_track(self):
        probe_data = {
            "streams": [
                {
                    "index": 1,
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "channels": 2,
                    "tags": {"language": "jpn", "title": "Japanese"},
                    "disposition": {"default": 1, "forced": 0},
                }
            ]
        }
        tracks = parse_tracks(probe_data, Path("/test/video.mkv"))

        assert len(tracks) == 1
        assert tracks[0].index == 1
        assert tracks[0].track_type == TrackType.AUDIO
        assert tracks[0].codec == "aac"
        assert tracks[0].language == "jpn"
        assert tracks[0].title == "Japanese"
        assert tracks[0].channels == 2
        assert tracks[0].is_default is True

    def test_parse_subtitle_track(self):
        probe_data = {
            "streams": [
                {
                    "index": 2,
                    "codec_type": "subtitle",
                    "codec_name": "ass",
                    "tags": {"language": "eng", "title": "English Subtitles"},
                    "disposition": {"default": 0, "forced": 1},
                }
            ]
        }
        tracks = parse_tracks(probe_data, Path("/test/video.mkv"))

        assert len(tracks) == 1
        assert tracks[0].index == 2
        assert tracks[0].track_type == TrackType.SUBTITLE
        assert tracks[0].codec == "ass"
        assert tracks[0].language == "eng"
        assert tracks[0].is_forced is True
        assert tracks[0].is_default is False

    def test_parse_multiple_tracks(self):
        probe_data = {
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "codec_name": "h264",
                    "tags": {},
                    "disposition": {},
                },
                {
                    "index": 1,
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "channels": 2,
                    "tags": {"language": "jpn"},
                    "disposition": {},
                },
                {
                    "index": 2,
                    "codec_type": "audio",
                    "codec_name": "ac3",
                    "channels": 6,
                    "tags": {"language": "eng"},
                    "disposition": {},
                },
                {
                    "index": 3,
                    "codec_type": "subtitle",
                    "codec_name": "srt",
                    "tags": {"language": "eng"},
                    "disposition": {},
                },
            ]
        }
        tracks = parse_tracks(probe_data, Path("/test/video.mkv"))

        assert len(tracks) == 4
        assert tracks[0].track_type == TrackType.VIDEO
        assert tracks[1].track_type == TrackType.AUDIO
        assert tracks[1].language == "jpn"
        assert tracks[2].track_type == TrackType.AUDIO
        assert tracks[2].language == "eng"
        assert tracks[2].channels == 6
        assert tracks[3].track_type == TrackType.SUBTITLE

    def test_unknown_language_defaults_to_und(self):
        probe_data = {
            "streams": [
                {
                    "index": 0,
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "tags": {},
                    "disposition": {},
                }
            ]
        }
        tracks = parse_tracks(probe_data, Path("/test/video.mkv"))

        assert tracks[0].language == "und"

    def test_ignores_data_streams(self):
        probe_data = {
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "codec_name": "h264",
                    "tags": {},
                    "disposition": {},
                },
                {
                    "index": 1,
                    "codec_type": "data",
                    "codec_name": "bin_data",
                    "tags": {},
                    "disposition": {},
                },
            ]
        }
        tracks = parse_tracks(probe_data, Path("/test/video.mkv"))

        assert len(tracks) == 1
        assert tracks[0].track_type == TrackType.VIDEO

    def test_empty_streams(self):
        probe_data = {"streams": []}
        tracks = parse_tracks(probe_data, Path("/test/video.mkv"))
        assert tracks == []

    def test_no_streams_key(self):
        probe_data = {}
        tracks = parse_tracks(probe_data, Path("/test/video.mkv"))
        assert tracks == []


class TestVideoMetadataExtraction:
    """Tests for video metadata extraction in parse_tracks."""

    def test_parse_video_dimensions(self):
        """Video tracks have width and height extracted."""
        probe_data = {
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "tags": {},
                    "disposition": {},
                }
            ]
        }
        tracks = parse_tracks(probe_data, Path("/test/video.mkv"))

        assert len(tracks) == 1
        assert tracks[0].width == 1920
        assert tracks[0].height == 1080

    def test_parse_video_bitrate_from_stream(self):
        """Video bitrate extracted from stream when available."""
        probe_data = {
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "bit_rate": "8000000",
                    "tags": {},
                    "disposition": {},
                }
            ]
        }
        tracks = parse_tracks(probe_data, Path("/test/video.mkv"))

        assert tracks[0].bitrate == 8000000

    def test_parse_video_bitrate_fallback_to_format(self):
        """Video bitrate falls back to format level when stream has none."""
        probe_data = {
            "format": {"bit_rate": "10000000"},
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "tags": {},
                    "disposition": {},
                }
            ],
        }
        tracks = parse_tracks(probe_data, Path("/test/video.mkv"))

        assert tracks[0].bitrate == 10000000

    def test_parse_video_stream_bitrate_preferred_over_format(self):
        """Stream-level bitrate is preferred over format-level."""
        probe_data = {
            "format": {"bit_rate": "20000000"},
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "bit_rate": "8000000",
                    "tags": {},
                    "disposition": {},
                }
            ],
        }
        tracks = parse_tracks(probe_data, Path("/test/video.mkv"))

        assert tracks[0].bitrate == 8000000

    def test_parse_video_no_bitrate(self):
        """Video bitrate is None when unavailable."""
        probe_data = {
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "tags": {},
                    "disposition": {},
                }
            ]
        }
        tracks = parse_tracks(probe_data, Path("/test/video.mkv"))

        assert tracks[0].bitrate is None

    def test_audio_track_no_video_metadata(self):
        """Audio tracks don't have video metadata populated."""
        probe_data = {
            "streams": [
                {
                    "index": 1,
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "channels": 2,
                    "tags": {},
                    "disposition": {},
                }
            ]
        }
        tracks = parse_tracks(probe_data, Path("/test/video.mkv"))

        assert tracks[0].width is None
        assert tracks[0].height is None
        assert tracks[0].bitrate is None

    def test_parse_invalid_bitrate_string(self):
        """Invalid bitrate string gracefully handled."""
        probe_data = {
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "bit_rate": "N/A",
                    "tags": {},
                    "disposition": {},
                }
            ],
            "format": {"bit_rate": "5000000"},
        }
        tracks = parse_tracks(probe_data, Path("/test/video.mkv"))

        # Falls back to format bitrate
        assert tracks[0].bitrate == 5000000

    def test_parse_4k_video(self):
        """4K video dimensions are parsed correctly."""
        probe_data = {
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "codec_name": "hevc",
                    "width": 3840,
                    "height": 2160,
                    "bit_rate": "20000000",
                    "tags": {},
                    "disposition": {},
                }
            ]
        }
        tracks = parse_tracks(probe_data, Path("/test/video.mkv"))

        assert tracks[0].width == 3840
        assert tracks[0].height == 2160
        assert tracks[0].bitrate == 20000000
