"""Tests for executor module."""

from pathlib import Path

from anime_mux.executor import build_ffmpeg_command
from anime_mux.models import (
    Episode,
    MergeJob,
    Track,
    TrackSource,
    TrackType,
    VideoCodec,
    VideoEncodingConfig,
)


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


class TestH264Encoding:
    """Tests for H.264 video encoding in build_ffmpeg_command."""

    def test_h264_encoding_uses_libx264(self):
        """H.264 encoding uses libx264 codec."""
        video_file = Path("/media/episode01.mkv")
        episode = Episode(number=1, video_file=video_file)

        video_track = make_video_track(video_file, index=0)
        video_track.width = 1920
        video_track.height = 1080
        video_track.bitrate = 8_000_000

        job = MergeJob(
            episode=episode,
            output_path=Path("/output/episode01.mkv"),
            video_tracks=[video_track],
            audio_tracks=[make_audio_track(video_file, index=1)],
            subtitle_tracks=[],
            preserve_attachments=False,
            video_encoding=VideoEncodingConfig(codec=VideoCodec.H264),
        )

        cmd = build_ffmpeg_command(job)

        idx_cv = cmd.index("-c:v")
        assert cmd[idx_cv + 1] == "libx264"
        assert "-crf" in cmd
        assert "-preset" in cmd
        assert "-pix_fmt" in cmd

    def test_h264_encoding_with_explicit_crf(self):
        """Explicit CRF value is used."""
        video_file = Path("/media/episode01.mkv")
        episode = Episode(number=1, video_file=video_file)

        job = MergeJob(
            episode=episode,
            output_path=Path("/output/episode01.mkv"),
            video_tracks=[make_video_track(video_file)],
            audio_tracks=[make_audio_track(video_file)],
            subtitle_tracks=[],
            preserve_attachments=False,
            video_encoding=VideoEncodingConfig(codec=VideoCodec.H264, crf=18),
        )

        cmd = build_ffmpeg_command(job)

        idx_crf = cmd.index("-crf")
        assert cmd[idx_crf + 1] == "18"

    def test_h264_encoding_auto_crf_1080p(self):
        """Auto CRF for 1080p uses correct value."""
        video_file = Path("/media/episode01.mkv")
        episode = Episode(number=1, video_file=video_file)

        video_track = make_video_track(video_file, index=0)
        video_track.width = 1920
        video_track.height = 1080
        video_track.bitrate = 8_000_000  # typical bitrate

        job = MergeJob(
            episode=episode,
            output_path=Path("/output/episode01.mkv"),
            video_tracks=[video_track],
            audio_tracks=[make_audio_track(video_file, index=1)],
            subtitle_tracks=[],
            preserve_attachments=False,
            video_encoding=VideoEncodingConfig(codec=VideoCodec.H264),
        )

        cmd = build_ffmpeg_command(job)

        idx_crf = cmd.index("-crf")
        assert cmd[idx_crf + 1] == "19"  # base CRF for 1080p

    def test_h264_encoding_preset_medium(self):
        """H.264 encoding uses medium preset."""
        video_file = Path("/media/episode01.mkv")
        episode = Episode(number=1, video_file=video_file)

        job = MergeJob(
            episode=episode,
            output_path=Path("/output/episode01.mkv"),
            video_tracks=[make_video_track(video_file)],
            audio_tracks=[make_audio_track(video_file)],
            subtitle_tracks=[],
            preserve_attachments=False,
            video_encoding=VideoEncodingConfig(codec=VideoCodec.H264),
        )

        cmd = build_ffmpeg_command(job)

        idx_preset = cmd.index("-preset")
        assert cmd[idx_preset + 1] == "medium"

    def test_h264_encoding_yuv420p_pixel_format(self):
        """H.264 encoding uses yuv420p pixel format for compatibility."""
        video_file = Path("/media/episode01.mkv")
        episode = Episode(number=1, video_file=video_file)

        job = MergeJob(
            episode=episode,
            output_path=Path("/output/episode01.mkv"),
            video_tracks=[make_video_track(video_file)],
            audio_tracks=[make_audio_track(video_file)],
            subtitle_tracks=[],
            preserve_attachments=False,
            video_encoding=VideoEncodingConfig(codec=VideoCodec.H264),
        )

        cmd = build_ffmpeg_command(job)

        idx_pix = cmd.index("-pix_fmt")
        assert cmd[idx_pix + 1] == "yuv420p"

    def test_copy_mode_no_encoding_params(self):
        """Copy mode doesn't add encoding parameters."""
        video_file = Path("/media/episode01.mkv")
        episode = Episode(number=1, video_file=video_file)

        job = MergeJob(
            episode=episode,
            output_path=Path("/output/episode01.mkv"),
            video_tracks=[make_video_track(video_file)],
            audio_tracks=[make_audio_track(video_file)],
            subtitle_tracks=[],
            preserve_attachments=False,
            video_encoding=VideoEncodingConfig(codec=VideoCodec.COPY),
        )

        cmd = build_ffmpeg_command(job)

        idx_cv = cmd.index("-c:v")
        assert cmd[idx_cv + 1] == "copy"
        assert "-crf" not in cmd
        assert "-preset" not in cmd
        assert "-pix_fmt" not in cmd

    def test_default_encoding_is_copy(self):
        """Default video encoding config uses copy mode."""
        video_file = Path("/media/episode01.mkv")
        episode = Episode(number=1, video_file=video_file)

        job = MergeJob(
            episode=episode,
            output_path=Path("/output/episode01.mkv"),
            video_tracks=[make_video_track(video_file)],
            audio_tracks=[make_audio_track(video_file)],
            subtitle_tracks=[],
            preserve_attachments=False,
            # No video_encoding specified, uses default
        )

        cmd = build_ffmpeg_command(job)

        idx_cv = cmd.index("-c:v")
        assert cmd[idx_cv + 1] == "copy"


class TestVideoEncodingConfig:
    """Tests for VideoEncodingConfig CRF calculation."""

    def test_explicit_crf_returned(self):
        """Explicit CRF value is returned without calculation."""
        config = VideoEncodingConfig(codec=VideoCodec.H264, crf=18)
        assert config.calculate_crf(1920, 1080, 10_000_000) == 18

    def test_4k_base_crf(self):
        """4K resolution uses CRF 17."""
        config = VideoEncodingConfig(codec=VideoCodec.H264)
        crf = config.calculate_crf(3840, 2160, None)
        assert crf == 17

    def test_1080p_base_crf(self):
        """1080p resolution uses CRF 19."""
        config = VideoEncodingConfig(codec=VideoCodec.H264)
        crf = config.calculate_crf(1920, 1080, None)
        assert crf == 19

    def test_720p_base_crf(self):
        """720p resolution uses CRF 21."""
        config = VideoEncodingConfig(codec=VideoCodec.H264)
        crf = config.calculate_crf(1280, 720, None)
        assert crf == 21

    def test_480p_base_crf(self):
        """480p resolution uses CRF 23."""
        config = VideoEncodingConfig(codec=VideoCodec.H264)
        crf = config.calculate_crf(854, 480, None)
        assert crf == 23

    def test_low_res_base_crf(self):
        """Low resolution (<480p) uses CRF 25."""
        config = VideoEncodingConfig(codec=VideoCodec.H264)
        crf = config.calculate_crf(640, 360, None)
        assert crf == 25

    def test_high_bitrate_lowers_crf(self):
        """Very high bitrate source lowers CRF by 2."""
        config = VideoEncodingConfig(codec=VideoCodec.H264)
        # 1080p with very high bitrate (20 Mbps = 2.5x typical 8 Mbps)
        crf = config.calculate_crf(1920, 1080, 20_000_000)
        assert crf == 17  # base 19 - 2

    def test_moderately_high_bitrate_lowers_crf(self):
        """Moderately high bitrate source lowers CRF by 1."""
        config = VideoEncodingConfig(codec=VideoCodec.H264)
        # 1080p with high bitrate (13 Mbps = 1.6x typical)
        crf = config.calculate_crf(1920, 1080, 13_000_000)
        assert crf == 18  # base 19 - 1

    def test_low_bitrate_raises_crf(self):
        """Low bitrate source raises CRF by 1."""
        config = VideoEncodingConfig(codec=VideoCodec.H264)
        # 1080p with low bitrate (3 Mbps = 0.375x typical)
        crf = config.calculate_crf(1920, 1080, 3_000_000)
        assert crf == 20  # base 19 + 1

    def test_typical_bitrate_uses_base_crf(self):
        """Typical bitrate uses base CRF unchanged."""
        config = VideoEncodingConfig(codec=VideoCodec.H264)
        # 1080p with typical bitrate (8 Mbps)
        crf = config.calculate_crf(1920, 1080, 8_000_000)
        assert crf == 19  # base, no adjustment

    def test_crf_clamped_minimum(self):
        """CRF is clamped to minimum 0."""
        config = VideoEncodingConfig(codec=VideoCodec.H264)
        # 4K with extremely high bitrate
        crf = config.calculate_crf(3840, 2160, 100_000_000)
        assert crf >= 0

    def test_crf_clamped_maximum(self):
        """CRF is clamped to maximum 51."""
        config = VideoEncodingConfig(codec=VideoCodec.H264)
        # Very low res with very low bitrate
        crf = config.calculate_crf(320, 240, 100_000)
        assert crf <= 51

    def test_none_dimensions_uses_defaults(self):
        """None dimensions use 1080p defaults."""
        config = VideoEncodingConfig(codec=VideoCodec.H264)
        crf = config.calculate_crf(None, None, None)
        assert crf == 19  # 1080p default
