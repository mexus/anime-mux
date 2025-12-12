"""Tests for analyzer module."""

from pathlib import Path


from anime_mux.analyzer import _find_common_tracks, get_track_by_identity
from anime_mux.models import Episode, Track, TrackSource, TrackType


def make_audio_track(
    language: str, title: str | None = None, channels: int = 2
) -> Track:
    """Helper to create audio tracks for testing."""
    return Track(
        index=0,
        track_type=TrackType.AUDIO,
        codec="aac",
        language=language,
        title=title,
        source=TrackSource.EMBEDDED,
        source_file=Path("/test/video.mkv"),
        channels=channels,
    )


def make_sub_track(
    language: str, title: str | None = None, is_forced: bool = False
) -> Track:
    """Helper to create subtitle tracks for testing."""
    return Track(
        index=0,
        track_type=TrackType.SUBTITLE,
        codec="ass",
        language=language,
        title=title,
        source=TrackSource.EMBEDDED,
        source_file=Path("/test/video.mkv"),
        is_forced=is_forced,
    )


class TestFindCommonTracks:
    """Tests for _find_common_tracks function."""

    def test_empty_episodes(self):
        result = _find_common_tracks([], TrackType.AUDIO)
        assert result == []

    def test_single_episode(self):
        ep = Episode(
            number=1,
            video_file=Path("/test/ep01.mkv"),
            embedded_tracks=[
                make_audio_track("jpn"),
                make_audio_track("eng"),
            ],
        )
        result = _find_common_tracks([ep], TrackType.AUDIO)
        assert len(result) == 2

    def test_common_tracks_found(self):
        jpn_track = make_audio_track("jpn", "Japanese")
        eng_track = make_audio_track("eng", "English")

        ep1 = Episode(
            number=1,
            video_file=Path("/test/ep01.mkv"),
            embedded_tracks=[jpn_track, eng_track],
        )
        ep2 = Episode(
            number=2,
            video_file=Path("/test/ep02.mkv"),
            embedded_tracks=[
                make_audio_track("jpn", "Japanese"),
                make_audio_track("eng", "English"),
            ],
        )

        result = _find_common_tracks([ep1, ep2], TrackType.AUDIO)
        assert len(result) == 2
        assert jpn_track.identity_key in result
        assert eng_track.identity_key in result

    def test_no_common_tracks(self):
        ep1 = Episode(
            number=1,
            video_file=Path("/test/ep01.mkv"),
            embedded_tracks=[make_audio_track("jpn")],
        )
        ep2 = Episode(
            number=2,
            video_file=Path("/test/ep02.mkv"),
            embedded_tracks=[make_audio_track("eng")],
        )

        result = _find_common_tracks([ep1, ep2], TrackType.AUDIO)
        assert result == []

    def test_partial_common_tracks(self):
        jpn_track = make_audio_track("jpn", "Japanese")

        ep1 = Episode(
            number=1,
            video_file=Path("/test/ep01.mkv"),
            embedded_tracks=[
                jpn_track,
                make_audio_track("eng", "English"),
            ],
        )
        ep2 = Episode(
            number=2,
            video_file=Path("/test/ep02.mkv"),
            embedded_tracks=[
                make_audio_track("jpn", "Japanese"),
                make_audio_track("rus", "Russian"),
            ],
        )

        result = _find_common_tracks([ep1, ep2], TrackType.AUDIO)
        assert len(result) == 1
        assert jpn_track.identity_key in result

    def test_filters_by_track_type(self):
        ep = Episode(
            number=1,
            video_file=Path("/test/ep01.mkv"),
            embedded_tracks=[
                make_audio_track("jpn"),
                make_sub_track("eng"),
            ],
        )

        audio_result = _find_common_tracks([ep], TrackType.AUDIO)
        sub_result = _find_common_tracks([ep], TrackType.SUBTITLE)

        assert len(audio_result) == 1
        assert len(sub_result) == 1


class TestGetTrackByIdentity:
    """Tests for get_track_by_identity function."""

    def test_finds_track(self):
        jpn_track = make_audio_track("jpn", "Japanese")
        eng_track = make_audio_track("eng", "English")

        ep = Episode(
            number=1,
            video_file=Path("/test/ep01.mkv"),
            embedded_tracks=[jpn_track, eng_track],
        )

        result = get_track_by_identity(ep, jpn_track.identity_key)
        assert result is not None
        assert result.language == "jpn"

    def test_not_found(self):
        ep = Episode(
            number=1,
            video_file=Path("/test/ep01.mkv"),
            embedded_tracks=[make_audio_track("jpn")],
        )

        result = get_track_by_identity(ep, "nonexistent|key")
        assert result is None

    def test_empty_tracks(self):
        ep = Episode(
            number=1,
            video_file=Path("/test/ep01.mkv"),
            embedded_tracks=[],
        )

        result = get_track_by_identity(ep, "any|key")
        assert result is None


class TestTrackIdentityKey:
    """Tests for Track.identity_key property."""

    def test_audio_identity_key(self):
        track = make_audio_track("jpn", "Japanese", channels=2)
        assert track.identity_key == "audio|jpn|Japanese|2"

    def test_audio_identity_key_no_title(self):
        track = make_audio_track("jpn", None, channels=6)
        assert track.identity_key == "audio|jpn||6"

    def test_subtitle_identity_key(self):
        track = make_sub_track("eng", "English Subtitles", is_forced=False)
        assert track.identity_key == "sub|eng|English Subtitles|False"

    def test_subtitle_identity_key_forced(self):
        track = make_sub_track("eng", "Signs", is_forced=True)
        assert track.identity_key == "sub|eng|Signs|True"

    def test_same_tracks_have_same_key(self):
        track1 = make_audio_track("jpn", "Japanese", channels=2)
        track2 = make_audio_track("jpn", "Japanese", channels=2)
        assert track1.identity_key == track2.identity_key

    def test_different_language_different_key(self):
        track1 = make_audio_track("jpn", "Japanese")
        track2 = make_audio_track("eng", "Japanese")
        assert track1.identity_key != track2.identity_key

    def test_different_channels_different_key(self):
        track1 = make_audio_track("jpn", "Japanese", channels=2)
        track2 = make_audio_track("jpn", "Japanese", channels=6)
        assert track1.identity_key != track2.identity_key
