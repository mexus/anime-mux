"""Tests for planner module."""

from pathlib import Path

from anime_mux.models import (
    AnalysisResult,
    Episode,
    ExternalSource,
    Track,
    TrackSource,
    TrackType,
)
from anime_mux.planner import (
    _get_video_track,
    _resolve_audio_tracks,
    _resolve_subtitle_tracks,
    build_merge_plan,
)
from anime_mux.selector import SelectionResult, TrackSelection


def make_video_track(source_file: Path, index: int = 0) -> Track:
    """Helper to create video tracks for testing."""
    return Track(
        index=index,
        track_type=TrackType.VIDEO,
        codec="h264",
        language="und",
        title=None,
        source=TrackSource.EMBEDDED,
        source_file=source_file,
    )


def make_audio_track(
    source_file: Path,
    index: int = 1,
    language: str = "jpn",
    title: str | None = None,
    channels: int = 2,
    source: TrackSource = TrackSource.EMBEDDED,
) -> Track:
    """Helper to create audio tracks for testing."""
    return Track(
        index=index,
        track_type=TrackType.AUDIO,
        codec="aac",
        language=language,
        title=title,
        source=source,
        source_file=source_file,
        channels=channels,
    )


def make_sub_track(
    source_file: Path,
    index: int = 2,
    language: str = "eng",
    title: str | None = None,
    source: TrackSource = TrackSource.EMBEDDED,
    is_forced: bool = False,
) -> Track:
    """Helper to create subtitle tracks for testing."""
    return Track(
        index=index,
        track_type=TrackType.SUBTITLE,
        codec="ass",
        language=language,
        title=title,
        source=source,
        source_file=source_file,
        is_forced=is_forced,
    )


def make_episode(
    number: int,
    video_file: Path,
    audio_tracks: list[Track] | None = None,
    sub_tracks: list[Track] | None = None,
    external_audio: dict[str, Track] | None = None,
    external_subs: dict[str, Track] | None = None,
) -> Episode:
    """Helper to create episodes for testing."""
    embedded = []
    embedded.append(make_video_track(video_file))
    if audio_tracks:
        embedded.extend(audio_tracks)
    if sub_tracks:
        embedded.extend(sub_tracks)

    return Episode(
        number=number,
        video_file=video_file,
        embedded_tracks=embedded,
        external_audio=external_audio or {},
        external_subs=external_subs or {},
    )


def make_analysis(
    episodes: dict[int, Episode],
    common_audio: list[str] | None = None,
    common_subs: list[str] | None = None,
    external_audio_sources: dict[str, ExternalSource] | None = None,
    external_sub_sources: dict[str, ExternalSource] | None = None,
) -> AnalysisResult:
    """Helper to create AnalysisResult for testing."""
    return AnalysisResult(
        episodes=episodes,
        common_embedded_audio=common_audio or [],
        common_embedded_subs=common_subs or [],
        external_audio_sources=external_audio_sources or {},
        external_subtitle_sources=external_sub_sources or {},
        missing_tracks={},
        unmatched_external_files=[],
    )


def make_selection(
    audio_selections: list[TrackSelection] | None = None,
    subtitle_selections: list[TrackSelection] | None = None,
    audio_substitutions: dict[int, str] | None = None,
    subtitle_substitutions: dict[int, str] | None = None,
    skipped_episodes: list[int] | None = None,
) -> SelectionResult:
    """Helper to create SelectionResult for testing."""
    return SelectionResult(
        audio_selections=audio_selections or [],
        subtitle_selections=subtitle_selections or [],
        audio_substitutions=audio_substitutions or {},
        subtitle_substitutions=subtitle_substitutions or {},
        skipped_episodes=skipped_episodes or [],
    )


class TestGetVideoTrack:
    """Tests for _get_video_track function."""

    def test_finds_video_track(self):
        video_file = Path("/media/ep01.mkv")
        ep = make_episode(1, video_file)

        result = _get_video_track(ep)

        assert result is not None
        assert result.track_type == TrackType.VIDEO

    def test_returns_none_when_no_video(self):
        video_file = Path("/media/ep01.mkv")
        ep = Episode(
            number=1,
            video_file=video_file,
            embedded_tracks=[make_audio_track(video_file)],
        )

        result = _get_video_track(ep)

        assert result is None


class TestResolveAudioTracks:
    """Tests for _resolve_audio_tracks function."""

    def test_resolve_embedded_audio(self):
        video_file = Path("/media/ep01.mkv")
        audio_track = make_audio_track(video_file, language="jpn", title="Japanese")
        ep = make_episode(1, video_file, audio_tracks=[audio_track])
        analysis = make_analysis({1: ep}, common_audio=[audio_track.identity_key])
        selection = make_selection(
            audio_selections=[
                TrackSelection(
                    identifier=audio_track.identity_key,
                    is_embedded=True,
                    display_name="Japanese",
                )
            ]
        )

        result = _resolve_audio_tracks(ep, selection, analysis)

        assert len(result) == 1
        assert result[0].language == "jpn"

    def test_resolve_external_audio(self):
        video_file = Path("/media/ep01.mkv")
        audio_file = Path("/audio/ep01.mka")
        external_track = make_audio_track(
            audio_file, language="rus", source=TrackSource.EXTERNAL
        )
        ep = make_episode(1, video_file, external_audio={"RuDub": external_track})
        analysis = make_analysis({1: ep})
        selection = make_selection(
            audio_selections=[
                TrackSelection(
                    identifier="RuDub",
                    is_embedded=False,
                    display_name="RuDub",
                )
            ]
        )

        result = _resolve_audio_tracks(ep, selection, analysis)

        assert len(result) == 1
        assert result[0].language == "rus"
        assert result[0].source == TrackSource.EXTERNAL

    def test_resolve_multiple_audio_tracks(self):
        video_file = Path("/media/ep01.mkv")
        audio_file = Path("/audio/ep01.mka")

        jpn_track = make_audio_track(
            video_file, index=1, language="jpn", title="Japanese"
        )
        external_track = make_audio_track(
            audio_file, language="rus", source=TrackSource.EXTERNAL
        )

        ep = make_episode(
            1,
            video_file,
            audio_tracks=[jpn_track],
            external_audio={"RuDub": external_track},
        )
        analysis = make_analysis({1: ep}, common_audio=[jpn_track.identity_key])
        selection = make_selection(
            audio_selections=[
                TrackSelection(
                    identifier=jpn_track.identity_key,
                    is_embedded=True,
                    display_name="Japanese",
                ),
                TrackSelection(
                    identifier="RuDub",
                    is_embedded=False,
                    display_name="RuDub",
                ),
            ]
        )

        result = _resolve_audio_tracks(ep, selection, analysis)

        assert len(result) == 2
        assert result[0].language == "jpn"
        assert result[1].language == "rus"

    def test_audio_substitution(self):
        """Test audio source substitution for missing episodes."""
        video_file = Path("/media/ep01.mkv")
        audio_file = Path("/audio/alt/ep01.mka")

        alt_track = make_audio_track(
            audio_file, language="rus", source=TrackSource.EXTERNAL
        )
        ep = make_episode(
            1,
            video_file,
            external_audio={"AltDub": alt_track},  # Main source missing, alt available
        )
        analysis = make_analysis({1: ep})
        selection = make_selection(
            audio_selections=[
                TrackSelection(
                    identifier="MainDub",  # Requested but missing
                    is_embedded=False,
                    display_name="MainDub",
                )
            ],
            audio_substitutions={1: "AltDub"},  # Substitute with AltDub
        )

        result = _resolve_audio_tracks(ep, selection, analysis)

        assert len(result) == 1
        assert result[0].source_file == audio_file

    def test_missing_external_source_returns_empty(self):
        video_file = Path("/media/ep01.mkv")
        ep = make_episode(1, video_file)
        analysis = make_analysis({1: ep})
        selection = make_selection(
            audio_selections=[
                TrackSelection(
                    identifier="NonExistent",
                    is_embedded=False,
                    display_name="NonExistent",
                )
            ]
        )

        result = _resolve_audio_tracks(ep, selection, analysis)

        assert result == []


class TestResolveSubtitleTracks:
    """Tests for _resolve_subtitle_tracks function."""

    def test_resolve_embedded_subtitle(self):
        video_file = Path("/media/ep01.mkv")
        sub_track = make_sub_track(video_file, language="eng", title="English")
        ep = make_episode(1, video_file, sub_tracks=[sub_track])
        analysis = make_analysis({1: ep}, common_subs=[sub_track.identity_key])
        selection = make_selection(
            subtitle_selections=[
                TrackSelection(
                    identifier=sub_track.identity_key,
                    is_embedded=True,
                    display_name="English",
                )
            ]
        )

        result = _resolve_subtitle_tracks(ep, selection, analysis)

        assert len(result) == 1
        assert result[0].language == "eng"

    def test_resolve_external_subtitle(self):
        video_file = Path("/media/ep01.mkv")
        sub_file = Path("/subs/ep01.ass")
        external_sub = make_sub_track(
            sub_file, language="rus", source=TrackSource.EXTERNAL
        )
        ep = make_episode(1, video_file, external_subs={"RuSubs": external_sub})
        analysis = make_analysis({1: ep})
        selection = make_selection(
            subtitle_selections=[
                TrackSelection(
                    identifier="RuSubs",
                    is_embedded=False,
                    display_name="RuSubs",
                )
            ]
        )

        result = _resolve_subtitle_tracks(ep, selection, analysis)

        assert len(result) == 1
        assert result[0].language == "rus"
        assert result[0].source == TrackSource.EXTERNAL

    def test_subtitle_substitution(self):
        """Test subtitle source substitution for missing episodes."""
        video_file = Path("/media/ep01.mkv")
        sub_file = Path("/subs/alt/ep01.ass")

        alt_sub = make_sub_track(sub_file, language="eng", source=TrackSource.EXTERNAL)
        ep = make_episode(
            1,
            video_file,
            external_subs={"AltSubs": alt_sub},
        )
        analysis = make_analysis({1: ep})
        selection = make_selection(
            subtitle_selections=[
                TrackSelection(
                    identifier="MainSubs",
                    is_embedded=False,
                    display_name="MainSubs",
                )
            ],
            subtitle_substitutions={1: "AltSubs"},
        )

        result = _resolve_subtitle_tracks(ep, selection, analysis)

        assert len(result) == 1
        assert result[0].source_file == sub_file


class TestBuildMergePlan:
    """Tests for build_merge_plan function."""

    def test_basic_merge_plan(self):
        video_file = Path("/media/ep01.mkv")
        audio_track = make_audio_track(video_file, language="jpn", title="Japanese")
        sub_track = make_sub_track(video_file, language="eng", title="English")

        ep = make_episode(
            1, video_file, audio_tracks=[audio_track], sub_tracks=[sub_track]
        )
        analysis = make_analysis(
            {1: ep},
            common_audio=[audio_track.identity_key],
            common_subs=[sub_track.identity_key],
        )
        selection = make_selection(
            audio_selections=[
                TrackSelection(
                    identifier=audio_track.identity_key,
                    is_embedded=True,
                    display_name="Japanese",
                )
            ],
            subtitle_selections=[
                TrackSelection(
                    identifier=sub_track.identity_key,
                    is_embedded=True,
                    display_name="English",
                )
            ],
        )
        output_dir = Path("/output")

        plan = build_merge_plan(analysis, selection, output_dir)

        assert len(plan.jobs) == 1
        assert plan.output_directory == output_dir
        assert plan.jobs[0].episode.number == 1
        assert len(plan.jobs[0].video_tracks) == 1
        assert len(plan.jobs[0].audio_tracks) == 1
        assert len(plan.jobs[0].subtitle_tracks) == 1
        assert plan.jobs[0].output_path == output_dir / "ep01.mkv"

    def test_multiple_episodes(self):
        episodes = {}
        for i in range(1, 4):
            video_file = Path(f"/media/ep{i:02d}.mkv")
            audio = make_audio_track(video_file, language="jpn", title="Japanese")
            episodes[i] = make_episode(i, video_file, audio_tracks=[audio])

        # All episodes have same audio identity
        first_audio = list(episodes.values())[0].embedded_tracks[1]
        analysis = make_analysis(episodes, common_audio=[first_audio.identity_key])
        selection = make_selection(
            audio_selections=[
                TrackSelection(
                    identifier=first_audio.identity_key,
                    is_embedded=True,
                    display_name="Japanese",
                )
            ]
        )
        output_dir = Path("/output")

        plan = build_merge_plan(analysis, selection, output_dir)

        assert len(plan.jobs) == 3
        assert [j.episode.number for j in plan.jobs] == [1, 2, 3]

    def test_skipped_episodes(self):
        episodes = {}
        for i in range(1, 4):
            video_file = Path(f"/media/ep{i:02d}.mkv")
            audio = make_audio_track(video_file, language="jpn", title="Japanese")
            episodes[i] = make_episode(i, video_file, audio_tracks=[audio])

        first_audio = list(episodes.values())[0].embedded_tracks[1]
        analysis = make_analysis(episodes, common_audio=[first_audio.identity_key])
        selection = make_selection(
            audio_selections=[
                TrackSelection(
                    identifier=first_audio.identity_key,
                    is_embedded=True,
                    display_name="Japanese",
                )
            ],
            skipped_episodes=[2],
        )
        output_dir = Path("/output")

        plan = build_merge_plan(analysis, selection, output_dir)

        assert len(plan.jobs) == 2
        assert [j.episode.number for j in plan.jobs] == [1, 3]
        assert 2 in plan.skipped_episodes

    def test_preserve_attachments_default_true(self):
        video_file = Path("/media/ep01.mkv")
        audio_track = make_audio_track(video_file)
        ep = make_episode(1, video_file, audio_tracks=[audio_track])
        analysis = make_analysis({1: ep}, common_audio=[audio_track.identity_key])
        selection = make_selection(
            audio_selections=[
                TrackSelection(
                    identifier=audio_track.identity_key,
                    is_embedded=True,
                    display_name="Audio",
                )
            ]
        )

        plan = build_merge_plan(analysis, selection, Path("/output"))

        assert plan.jobs[0].preserve_attachments is True

    def test_output_path_preserves_filename(self):
        video_file = Path("/media/[SubGroup] Series - 01 [1080p].mkv")
        audio_track = make_audio_track(video_file)
        ep = make_episode(1, video_file, audio_tracks=[audio_track])
        analysis = make_analysis({1: ep}, common_audio=[audio_track.identity_key])
        selection = make_selection(
            audio_selections=[
                TrackSelection(
                    identifier=audio_track.identity_key,
                    is_embedded=True,
                    display_name="Audio",
                )
            ]
        )
        output_dir = Path("/output")

        plan = build_merge_plan(analysis, selection, output_dir)

        expected = output_dir / "[SubGroup] Series - 01 [1080p].mkv"
        assert plan.jobs[0].output_path == expected

    def test_external_audio_in_plan(self):
        video_file = Path("/media/ep01.mkv")
        audio_file = Path("/audio/ep01.mka")
        external_track = make_audio_track(
            audio_file, language="rus", source=TrackSource.EXTERNAL
        )
        ep = make_episode(1, video_file, external_audio={"RuDub": external_track})
        analysis = make_analysis({1: ep})
        selection = make_selection(
            audio_selections=[
                TrackSelection(
                    identifier="RuDub",
                    is_embedded=False,
                    display_name="RuDub",
                )
            ]
        )

        plan = build_merge_plan(analysis, selection, Path("/output"))

        assert len(plan.jobs[0].audio_tracks) == 1
        assert plan.jobs[0].audio_tracks[0].source == TrackSource.EXTERNAL

    def test_no_subtitles_selected(self):
        video_file = Path("/media/ep01.mkv")
        audio_track = make_audio_track(video_file)
        sub_track = make_sub_track(video_file)
        ep = make_episode(
            1, video_file, audio_tracks=[audio_track], sub_tracks=[sub_track]
        )
        analysis = make_analysis(
            {1: ep},
            common_audio=[audio_track.identity_key],
            common_subs=[sub_track.identity_key],
        )
        selection = make_selection(
            audio_selections=[
                TrackSelection(
                    identifier=audio_track.identity_key,
                    is_embedded=True,
                    display_name="Audio",
                )
            ],
            subtitle_selections=[],  # No subtitles selected
        )

        plan = build_merge_plan(analysis, selection, Path("/output"))

        assert plan.jobs[0].subtitle_tracks == []

    def test_jobs_sorted_by_episode_number(self):
        # Create episodes out of order
        episodes = {}
        for i in [3, 1, 2]:
            video_file = Path(f"/media/ep{i:02d}.mkv")
            audio = make_audio_track(video_file, language="jpn", title="Japanese")
            episodes[i] = make_episode(i, video_file, audio_tracks=[audio])

        first_audio = list(episodes.values())[0].embedded_tracks[1]
        analysis = make_analysis(episodes, common_audio=[first_audio.identity_key])
        selection = make_selection(
            audio_selections=[
                TrackSelection(
                    identifier=first_audio.identity_key,
                    is_embedded=True,
                    display_name="Japanese",
                )
            ]
        )

        plan = build_merge_plan(analysis, selection, Path("/output"))

        # Jobs should be sorted
        episode_numbers = [j.episode.number for j in plan.jobs]
        assert episode_numbers == [1, 2, 3]

    def test_mixed_embedded_and_external(self):
        """Test plan with both embedded audio and external subtitles."""
        video_file = Path("/media/ep01.mkv")
        sub_file = Path("/subs/ep01.ass")

        audio_track = make_audio_track(video_file, language="jpn", title="Japanese")
        external_sub = make_sub_track(
            sub_file, language="eng", source=TrackSource.EXTERNAL
        )

        ep = make_episode(
            1,
            video_file,
            audio_tracks=[audio_track],
            external_subs={"EngSubs": external_sub},
        )
        analysis = make_analysis({1: ep}, common_audio=[audio_track.identity_key])
        selection = make_selection(
            audio_selections=[
                TrackSelection(
                    identifier=audio_track.identity_key,
                    is_embedded=True,
                    display_name="Japanese",
                )
            ],
            subtitle_selections=[
                TrackSelection(
                    identifier="EngSubs",
                    is_embedded=False,
                    display_name="EngSubs",
                )
            ],
        )

        plan = build_merge_plan(analysis, selection, Path("/output"))

        assert len(plan.jobs[0].audio_tracks) == 1
        assert plan.jobs[0].audio_tracks[0].source == TrackSource.EMBEDDED
        assert len(plan.jobs[0].subtitle_tracks) == 1
        assert plan.jobs[0].subtitle_tracks[0].source == TrackSource.EXTERNAL
