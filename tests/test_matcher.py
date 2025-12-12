"""Tests for episode number extraction."""

from pathlib import Path

from anime_mux.matcher import extract_episode_numbers


class TestExtractEpisodeNumbers:
    """Tests for extract_episode_numbers function."""

    def test_empty_list(self):
        """Empty list returns empty dict."""
        assert extract_episode_numbers([]) == {}

    def test_single_file(self):
        """Single file is treated as episode 1."""
        files = [Path("/media/Movie.mkv")]
        result = extract_episode_numbers(files)
        assert result == {1: files[0]}

    def test_standard_naming(self):
        """Standard episode naming pattern."""
        files = [
            Path("/media/Series - 01.mkv"),
            Path("/media/Series - 02.mkv"),
            Path("/media/Series - 03.mkv"),
        ]
        result = extract_episode_numbers(files)
        assert result == {1: files[0], 2: files[1], 3: files[2]}

    def test_subgroup_naming(self):
        """Subgroup release naming pattern."""
        files = [
            Path("/media/[SubGroup] Series Name - 01 [1080p].mkv"),
            Path("/media/[SubGroup] Series Name - 02 [1080p].mkv"),
            Path("/media/[SubGroup] Series Name - 03 [1080p].mkv"),
        ]
        result = extract_episode_numbers(files)
        assert result == {1: files[0], 2: files[1], 3: files[2]}

    def test_season_episode_format(self):
        """S01E01 format."""
        files = [
            Path("/media/Series.S01E05.mkv"),
            Path("/media/Series.S01E06.mkv"),
            Path("/media/Series.S01E07.mkv"),
        ]
        result = extract_episode_numbers(files)
        assert result == {5: files[0], 6: files[1], 7: files[2]}

    def test_simple_numbered(self):
        """Simple numbered files."""
        files = [
            Path("/media/01.ass"),
            Path("/media/02.ass"),
            Path("/media/03.ass"),
        ]
        result = extract_episode_numbers(files)
        assert result == {1: files[0], 2: files[1], 3: files[2]}

    def test_with_resolution_number(self):
        """Episode number extraction ignores resolution like 1080."""
        files = [
            Path("/media/Series 1080p - 01.mkv"),
            Path("/media/Series 1080p - 02.mkv"),
            Path("/media/Series 1080p - 03.mkv"),
        ]
        result = extract_episode_numbers(files)
        # Should detect 01, 02, 03 - not 1080
        assert result == {1: files[0], 2: files[1], 3: files[2]}

    def test_underscore_naming(self):
        """Underscore-separated naming."""
        files = [
            Path("/media/series_ep_12_final.mkv"),
            Path("/media/series_ep_13_final.mkv"),
            Path("/media/series_ep_14_final.mkv"),
        ]
        result = extract_episode_numbers(files)
        assert result == {12: files[0], 13: files[1], 14: files[2]}

    def test_mka_audio_files(self):
        """Audio file naming with group tag."""
        files = [
            Path("/media/Series.01.[Anilibria].mka"),
            Path("/media/Series.02.[Anilibria].mka"),
            Path("/media/Series.03.[Anilibria].mka"),
        ]
        result = extract_episode_numbers(files)
        assert result == {1: files[0], 2: files[1], 3: files[2]}

    def test_non_matching_files_returns_empty(self):
        """Non-matching files return empty dict."""
        files = [
            Path("/media/Episode.01.mkv"),
            Path("/media/Different_Naming_02.mkv"),
            Path("/media/Another.03.mkv"),
        ]
        result = extract_episode_numbers(files)
        assert result == {}

    def test_duplicate_episode_numbers_returns_empty(self):
        """Duplicate episode numbers return empty dict."""
        files = [
            Path("/media/Series - 01.mkv"),
            Path("/media/Series - 01.mkv"),  # Same file twice
        ]
        result = extract_episode_numbers(files)
        # Pattern matches but duplicates, so fails
        assert result == {}

    def test_episode_zero(self):
        """Episode 0 is handled correctly."""
        files = [
            Path("/media/Series - 00.mkv"),
            Path("/media/Series - 01.mkv"),
            Path("/media/Series - 02.mkv"),
        ]
        result = extract_episode_numbers(files)
        assert result == {0: files[0], 1: files[1], 2: files[2]}

    def test_leading_zeros_normalized(self):
        """Leading zeros are normalized to integers."""
        files = [
            Path("/media/Series.001.mkv"),
            Path("/media/Series.002.mkv"),
            Path("/media/Series.010.mkv"),
        ]
        result = extract_episode_numbers(files)
        assert result == {1: files[0], 2: files[1], 10: files[2]}

    def test_case_insensitive_matching(self):
        """Pattern matching is case-insensitive."""
        files = [
            Path("/media/SERIES.01.MKV"),
            Path("/media/series.02.mkv"),
            Path("/media/Series.03.Mkv"),
        ]
        result = extract_episode_numbers(files)
        assert result == {1: files[0], 2: files[1], 3: files[2]}
