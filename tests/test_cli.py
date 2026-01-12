"""Tests for CLI module."""

import pytest
from typer.testing import CliRunner

from anime_mux.cli import app
from anime_mux.constants import VALID_VIDEO_CODECS

runner = CliRunner()


class TestCLIValidation:
    """Test CLI argument validation."""

    def test_version_flag(self):
        """Test --version flag."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "anime-mux version" in result.stdout

    def test_help(self):
        """Test --help."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        # Typer outputs help to stdout, check for key content
        assert "anime-mux" in result.stdout
        assert "Analyze video files" in result.stdout

    def test_invalid_video_codec(self, tmp_path):
        """Test invalid video codec rejection."""
        result = runner.invoke(app, [str(tmp_path), "--video-codec", "invalid"])
        assert result.exit_code == 1
        assert "Invalid video codec" in result.stdout

    @pytest.mark.parametrize("codec", VALID_VIDEO_CODECS)
    def test_valid_video_codecs(self, tmp_path, codec):
        """Test all valid video codecs are accepted."""
        # Will fail at ffprobe check, but that's after validation
        result = runner.invoke(app, [str(tmp_path), "--video-codec", codec])
        # Should not fail on codec validation
        assert "Invalid video codec" not in result.stdout

    def test_crf_out_of_range(self, tmp_path):
        """Test CRF value validation."""
        result = runner.invoke(app, [str(tmp_path), "--crf", "52"])
        assert result.exit_code == 1
        assert "between 0 and 51" in result.stdout

    def test_crf_negative(self, tmp_path):
        """Test CRF negative value validation."""
        result = runner.invoke(app, [str(tmp_path), "--crf", "-1"])
        assert result.exit_code == 1
        assert "between 0 and 51" in result.stdout

    def test_quality_out_of_range(self, tmp_path):
        """Test quality value validation."""
        result = runner.invoke(app, [str(tmp_path), "--quality", "-1"])
        assert result.exit_code == 1
        assert "between 0 and 51" in result.stdout

    def test_quality_too_high(self, tmp_path):
        """Test quality value validation."""
        result = runner.invoke(app, [str(tmp_path), "--quality", "100"])
        assert result.exit_code == 1
        assert "between 0 and 51" in result.stdout

    def test_crf_warning_with_copy_codec(self, tmp_path):
        """Test warning when using CRF with copy codec."""
        result = runner.invoke(app, [str(tmp_path), "--video-codec", "copy", "--crf", "20"])
        # Will fail at ffprobe, but warning should appear
        assert "ignored when --video-codec is 'copy'" in result.stdout

    def test_quality_warning_with_copy_codec(self, tmp_path):
        """Test warning when using quality with copy codec."""
        result = runner.invoke(app, [str(tmp_path), "--video-codec", "copy", "--quality", "20"])
        # Will fail at ffprobe, but warning should appear
        assert "ignored when --video-codec is 'copy'" in result.stdout

    def test_crf_warning_with_vaapi(self, tmp_path):
        """Test warning when using CRF with VA-API codec."""
        result = runner.invoke(
            app, [str(tmp_path), "--video-codec", "h264-vaapi", "--crf", "20"]
        )
        # Will fail at ffprobe, but warning should appear
        assert "Use --quality for VA-API" in result.stdout

    def test_quality_warning_with_cpu_codec(self, tmp_path):
        """Test warning when using quality with CPU codec."""
        result = runner.invoke(app, [str(tmp_path), "--video-codec", "h264", "--quality", "20"])
        # Will fail at ffprobe, but warning should appear
        assert "Use --crf for CPU encoding" in result.stdout

    def test_directory_must_exist(self):
        """Test that non-existent directory is rejected."""
        result = runner.invoke(app, ["/nonexistent/path/anime"])
        # Typer exits with code 2 for invalid paths
        assert result.exit_code == 2


class TestCLIMisc:
    """Test CLI miscellaneous functionality."""

    def test_log_file_option(self, tmp_path):
        """Test that --log-file option is recognized."""
        log_file = tmp_path / "test.log"
        result = runner.invoke(
            app, [str(tmp_path), "--log-file", str(log_file)]
        )
        # Will fail at ffprobe, but option should be parsed
        assert "log-file" not in result.stdout  # No error about unknown option

    def test_verbose_option(self, tmp_path):
        """Test that -V option is recognized."""
        result = runner.invoke(app, [str(tmp_path), "--verbose"])
        # Will fail at ffprobe, but option should be parsed
        assert "verbose" not in result.stdout  # No error about unknown option

    def test_transcode_audio_option(self, tmp_path):
        """Test that -t option is recognized."""
        result = runner.invoke(app, [str(tmp_path), "--transcode-audio"])
        # Will fail at ffprobe, but option should be parsed
        assert "transcode" not in result.stdout  # No error about unknown option
