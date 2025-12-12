"""Tests for executor module."""

from pathlib import Path

from anime_mux.executor import build_ffmpeg_command
from anime_mux.models import Episode, MergeJob, Track, TrackSource, TrackType


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
    source: TrackSource = TrackSource.EMBEDDED,
) -> Track:
    """Helper to create audio tracks for testing."""
    return Track(
        index=index,
        track_type=TrackType.AUDIO,
        codec="aac",
        language=language,
        title=None,
        source=source,
        source_file=source_file,
        channels=2,
    )


def make_sub_track(
    source_file: Path,
    index: int = 2,
    language: str = "eng",
    source: TrackSource = TrackSource.EMBEDDED,
) -> Track:
    """Helper to create subtitle tracks for testing."""
    return Track(
        index=index,
        track_type=TrackType.SUBTITLE,
        codec="ass",
        language=language,
        title=None,
        source=source,
        source_file=source_file,
    )


class TestBuildFfmpegCommand:
    """Tests for build_ffmpeg_command function."""

    def test_basic_video_audio_copy(self):
        """Basic command with video and audio, copy mode."""
        video_file = Path("/media/episode01.mkv")
        episode = Episode(number=1, video_file=video_file)

        job = MergeJob(
            episode=episode,
            output_path=Path("/output/episode01.mkv"),
            video_tracks=[make_video_track(video_file, index=0)],
            audio_tracks=[make_audio_track(video_file, index=1)],
            subtitle_tracks=[],
            preserve_attachments=False,
        )

        cmd = build_ffmpeg_command(job)

        assert cmd[0] == "ffmpeg"
        assert "-y" in cmd
        assert "-i" in cmd
        assert str(video_file) in cmd
        assert "-map" in cmd
        assert "0:0" in cmd  # video
        assert "0:1" in cmd  # audio
        assert "-c:v" in cmd
        assert "copy" in cmd
        assert "-c:a" in cmd
        # Audio should be copy (not transcode)
        idx_ca = cmd.index("-c:a")
        assert cmd[idx_ca + 1] == "copy"
        assert str(job.output_path) == cmd[-1]

    def test_transcode_audio_to_aac(self):
        """Audio transcoding to AAC 256k."""
        video_file = Path("/media/episode01.mkv")
        episode = Episode(number=1, video_file=video_file)

        job = MergeJob(
            episode=episode,
            output_path=Path("/output/episode01.mkv"),
            video_tracks=[make_video_track(video_file)],
            audio_tracks=[make_audio_track(video_file)],
            subtitle_tracks=[],
            preserve_attachments=False,
        )

        cmd = build_ffmpeg_command(job, transcode_audio=True)

        idx_ca = cmd.index("-c:a")
        assert cmd[idx_ca + 1] == "aac"
        assert "-b:a" in cmd
        idx_ba = cmd.index("-b:a")
        assert cmd[idx_ba + 1] == "256k"

    def test_multiple_audio_tracks(self):
        """Multiple audio tracks with correct dispositions."""
        video_file = Path("/media/episode01.mkv")
        episode = Episode(number=1, video_file=video_file)

        job = MergeJob(
            episode=episode,
            output_path=Path("/output/episode01.mkv"),
            video_tracks=[make_video_track(video_file, index=0)],
            audio_tracks=[
                make_audio_track(video_file, index=1, language="jpn"),
                make_audio_track(video_file, index=2, language="eng"),
            ],
            subtitle_tracks=[],
            preserve_attachments=False,
        )

        cmd = build_ffmpeg_command(job)

        # Both audio tracks should be mapped
        assert "0:1" in cmd
        assert "0:2" in cmd

        # First audio track should be default
        assert "-disposition:a:0" in cmd
        idx_disp0 = cmd.index("-disposition:a:0")
        assert cmd[idx_disp0 + 1] == "default"

        # Second audio track should have disposition cleared
        assert "-disposition:a:1" in cmd
        idx_disp1 = cmd.index("-disposition:a:1")
        assert cmd[idx_disp1 + 1] == "0"

    def test_subtitle_tracks(self):
        """Subtitle tracks are mapped and copied."""
        video_file = Path("/media/episode01.mkv")
        episode = Episode(number=1, video_file=video_file)

        job = MergeJob(
            episode=episode,
            output_path=Path("/output/episode01.mkv"),
            video_tracks=[make_video_track(video_file, index=0)],
            audio_tracks=[make_audio_track(video_file, index=1)],
            subtitle_tracks=[make_sub_track(video_file, index=2)],
            preserve_attachments=False,
        )

        cmd = build_ffmpeg_command(job)

        assert "0:2" in cmd
        assert "-c:s" in cmd
        idx_cs = cmd.index("-c:s")
        assert cmd[idx_cs + 1] == "copy"

        # Subtitle should be default
        assert "-disposition:s:0" in cmd
        idx_disp = cmd.index("-disposition:s:0")
        assert cmd[idx_disp + 1] == "default"

    def test_multiple_subtitle_tracks(self):
        """Multiple subtitle tracks with correct dispositions."""
        video_file = Path("/media/episode01.mkv")
        episode = Episode(number=1, video_file=video_file)

        job = MergeJob(
            episode=episode,
            output_path=Path("/output/episode01.mkv"),
            video_tracks=[make_video_track(video_file, index=0)],
            audio_tracks=[make_audio_track(video_file, index=1)],
            subtitle_tracks=[
                make_sub_track(video_file, index=2, language="eng"),
                make_sub_track(video_file, index=3, language="rus"),
            ],
            preserve_attachments=False,
        )

        cmd = build_ffmpeg_command(job)

        # First subtitle default, second cleared
        assert "-disposition:s:0" in cmd
        assert "-disposition:s:1" in cmd
        idx_disp1 = cmd.index("-disposition:s:1")
        assert cmd[idx_disp1 + 1] == "0"

    def test_external_audio_file(self):
        """External audio from separate file."""
        video_file = Path("/media/episode01.mkv")
        audio_file = Path("/audio/episode01.mka")
        episode = Episode(number=1, video_file=video_file)

        job = MergeJob(
            episode=episode,
            output_path=Path("/output/episode01.mkv"),
            video_tracks=[make_video_track(video_file, index=0)],
            audio_tracks=[
                make_audio_track(audio_file, index=0, source=TrackSource.EXTERNAL)
            ],
            subtitle_tracks=[],
            preserve_attachments=False,
        )

        cmd = build_ffmpeg_command(job)

        # Both files should be inputs
        assert str(video_file) in cmd
        assert str(audio_file) in cmd

        # Video from input 0, audio from input 1
        assert "0:0" in cmd  # video
        assert "1:0" in cmd  # audio from second input

    def test_external_subtitle_file(self):
        """External subtitle from separate file."""
        video_file = Path("/media/episode01.mkv")
        sub_file = Path("/subs/episode01.ass")
        episode = Episode(number=1, video_file=video_file)

        job = MergeJob(
            episode=episode,
            output_path=Path("/output/episode01.mkv"),
            video_tracks=[make_video_track(video_file, index=0)],
            audio_tracks=[make_audio_track(video_file, index=1)],
            subtitle_tracks=[
                make_sub_track(sub_file, index=0, source=TrackSource.EXTERNAL)
            ],
            preserve_attachments=False,
        )

        cmd = build_ffmpeg_command(job)

        assert str(video_file) in cmd
        assert str(sub_file) in cmd
        assert "1:0" in cmd  # subtitle from second input

    def test_preserve_attachments(self):
        """Attachments are preserved from video file."""
        video_file = Path("/media/episode01.mkv")
        episode = Episode(number=1, video_file=video_file)

        job = MergeJob(
            episode=episode,
            output_path=Path("/output/episode01.mkv"),
            video_tracks=[make_video_track(video_file)],
            audio_tracks=[make_audio_track(video_file)],
            subtitle_tracks=[],
            preserve_attachments=True,
        )

        cmd = build_ffmpeg_command(job)

        # Should map attachments with optional flag
        assert "0:t?" in cmd
        # Should include interleave fix
        assert "-max_interleave_delta" in cmd
        assert "0" in cmd[cmd.index("-max_interleave_delta") + 1]

    def test_preserve_attachments_with_external_audio(self):
        """Attachments preserved when audio is from external file."""
        video_file = Path("/media/episode01.mkv")
        audio_file = Path("/audio/episode01.mka")
        episode = Episode(number=1, video_file=video_file)

        job = MergeJob(
            episode=episode,
            output_path=Path("/output/episode01.mkv"),
            video_tracks=[make_video_track(video_file, index=0)],
            audio_tracks=[
                make_audio_track(audio_file, index=0, source=TrackSource.EXTERNAL)
            ],
            subtitle_tracks=[],
            preserve_attachments=True,
        )

        cmd = build_ffmpeg_command(job)

        # Attachments should come from video file (input 0)
        assert "0:t?" in cmd
        # Interleave fix is critical when audio is from different input
        assert "-max_interleave_delta" in cmd

    def test_no_attachments_when_disabled(self):
        """No attachment mapping when preserve_attachments is False."""
        video_file = Path("/media/episode01.mkv")
        episode = Episode(number=1, video_file=video_file)

        job = MergeJob(
            episode=episode,
            output_path=Path("/output/episode01.mkv"),
            video_tracks=[make_video_track(video_file)],
            audio_tracks=[make_audio_track(video_file)],
            subtitle_tracks=[],
            preserve_attachments=False,
        )

        cmd = build_ffmpeg_command(job)

        # Should not have attachment mapping
        assert "0:t?" not in cmd
        assert "-max_interleave_delta" not in cmd

    def test_mixed_sources(self):
        """Video, external audio, and external subtitle from different files."""
        video_file = Path("/media/episode01.mkv")
        audio_file = Path("/audio/episode01.mka")
        sub_file = Path("/subs/episode01.ass")
        episode = Episode(number=1, video_file=video_file)

        job = MergeJob(
            episode=episode,
            output_path=Path("/output/episode01.mkv"),
            video_tracks=[make_video_track(video_file, index=0)],
            audio_tracks=[
                make_audio_track(audio_file, index=0, source=TrackSource.EXTERNAL)
            ],
            subtitle_tracks=[
                make_sub_track(sub_file, index=0, source=TrackSource.EXTERNAL)
            ],
            preserve_attachments=True,
        )

        cmd = build_ffmpeg_command(job)

        # All three files should be inputs
        inputs = [cmd[i + 1] for i, x in enumerate(cmd) if x == "-i"]
        assert len(inputs) == 3
        assert str(video_file) in inputs
        assert str(audio_file) in inputs
        assert str(sub_file) in inputs

    def test_output_path_is_last(self):
        """Output path is always the last argument."""
        video_file = Path("/media/episode01.mkv")
        output_path = Path("/output/episode01.mkv")
        episode = Episode(number=1, video_file=video_file)

        job = MergeJob(
            episode=episode,
            output_path=output_path,
            video_tracks=[make_video_track(video_file)],
            audio_tracks=[make_audio_track(video_file)],
            subtitle_tracks=[],
            preserve_attachments=False,
        )

        cmd = build_ffmpeg_command(job)

        assert cmd[-1] == str(output_path)

    def test_no_audio_tracks(self):
        """Command works with no audio tracks (edge case)."""
        video_file = Path("/media/episode01.mkv")
        episode = Episode(number=1, video_file=video_file)

        job = MergeJob(
            episode=episode,
            output_path=Path("/output/episode01.mkv"),
            video_tracks=[make_video_track(video_file)],
            audio_tracks=[],
            subtitle_tracks=[],
            preserve_attachments=False,
        )

        cmd = build_ffmpeg_command(job)

        # Should still have video codec settings
        assert "-c:v" in cmd
        assert "-c:a" in cmd  # Audio codec still present (for any audio)
        # No audio disposition should be set
        assert "-disposition:a:0" not in cmd

    def test_no_subtitle_tracks(self):
        """Command works with no subtitle tracks."""
        video_file = Path("/media/episode01.mkv")
        episode = Episode(number=1, video_file=video_file)

        job = MergeJob(
            episode=episode,
            output_path=Path("/output/episode01.mkv"),
            video_tracks=[make_video_track(video_file)],
            audio_tracks=[make_audio_track(video_file)],
            subtitle_tracks=[],
            preserve_attachments=False,
        )

        cmd = build_ffmpeg_command(job)

        # No subtitle disposition should be set
        assert "-disposition:s:0" not in cmd

    def test_same_file_not_duplicated_in_inputs(self):
        """Same source file is not added multiple times as input."""
        video_file = Path("/media/episode01.mkv")
        episode = Episode(number=1, video_file=video_file)

        job = MergeJob(
            episode=episode,
            output_path=Path("/output/episode01.mkv"),
            video_tracks=[make_video_track(video_file, index=0)],
            audio_tracks=[
                make_audio_track(video_file, index=1),
                make_audio_track(video_file, index=2),
            ],
            subtitle_tracks=[
                make_sub_track(video_file, index=3),
            ],
            preserve_attachments=False,
        )

        cmd = build_ffmpeg_command(job)

        # Count -i occurrences
        input_count = cmd.count("-i")
        assert input_count == 1

        # All mappings should reference input 0
        mappings = [cmd[i + 1] for i, x in enumerate(cmd) if x == "-map"]
        for m in mappings:
            assert m.startswith("0:")
