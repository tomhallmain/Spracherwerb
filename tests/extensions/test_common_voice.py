"""Tests for the Common Voice extension."""

import pytest
from pathlib import Path
import json
from extensions.common_voice import CommonVoice, VoiceSample

class TestCommonVoice:
    """Test suite for the Common Voice extension."""

    def test_initialization(self, mock_common_voice):
        """Test that the Common Voice instance initializes correctly."""
        assert mock_common_voice is not None
        assert isinstance(mock_common_voice, CommonVoice)

    def test_get_voice_samples(self, mock_common_voice):
        """Test that voice samples are retrieved correctly."""
        # Test getting voice samples with basic parameters
        samples = mock_common_voice.get_voice_samples(
            language="en",
            limit=5,
            min_duration=1.0,
            max_duration=10.0,
            min_votes=3
        )
        assert isinstance(samples, list)
        assert len(samples) <= 5
        assert all(isinstance(sample, VoiceSample) for sample in samples)
        assert all(sample.language == "en" for sample in samples)
        assert all(1.0 <= sample.duration <= 10.0 for sample in samples)
        assert all(sample.votes >= 3 for sample in samples)
        assert all(sample.audio_url is not None for sample in samples)

    def test_get_samples_by_accent(self, mock_common_voice):
        """Test that samples with specific accents are retrieved correctly."""
        accent_samples = mock_common_voice.get_samples_by_accent(
            language="en",
            accent="American",
            limit=5
        )
        assert isinstance(accent_samples, list)
        assert len(accent_samples) <= 5
        assert all(isinstance(sample, VoiceSample) for sample in accent_samples)
        assert all(sample.accent == "American" for sample in accent_samples)

    def test_get_samples_by_duration(self, mock_common_voice):
        """Test that samples within duration range are retrieved correctly."""
        duration_samples = mock_common_voice.get_samples_by_duration(
            language="en",
            min_duration=2.0,
            max_duration=5.0
        )
        assert isinstance(duration_samples, list)
        assert all(isinstance(sample, VoiceSample) for sample in duration_samples)
        assert all(2.0 <= sample.duration <= 5.0 for sample in duration_samples)

    def test_download_sample(self, mock_common_voice, temp_cache_dir):
        """Test that samples can be downloaded correctly."""
        # Get a sample to download
        samples = mock_common_voice.get_voice_samples(
            language="en",
            limit=1
        )
        if samples:
            sample = samples[0]
            output_path = mock_common_voice.download_sample(sample, temp_cache_dir)
            assert output_path is not None
            assert output_path.exists()
            assert output_path.suffix == ".mp3"

    def test_get_sample_statistics(self, mock_common_voice):
        """Test that sample statistics are calculated correctly."""
        stats = mock_common_voice.get_sample_statistics("en")
        assert isinstance(stats, dict)
        assert "total_samples" in stats
        assert "total_duration" in stats
        assert "average_duration" in stats
        assert "accents" in stats
        assert "genders" in stats
        assert "age_groups" in stats
        assert stats["total_samples"] > 0
        assert stats["total_duration"] > 0
        assert stats["average_duration"] > 0

    def test_get_available_languages(self, mock_common_voice):
        """Test that available languages are returned correctly."""
        languages = mock_common_voice.get_available_languages()
        assert isinstance(languages, list)
        assert len(languages) > 0
        assert all(isinstance(lang, str) for lang in languages)

    def test_cache_handling(self, mock_common_voice, temp_cache_dir):
        """Test that cache handling works correctly."""
        # Set up cache directory
        mock_common_voice.CACHE_DIR = temp_cache_dir
        mock_common_voice.CACHE_FILE = temp_cache_dir / "common_voice_cache.json"

        # Perform a search to populate cache
        samples = mock_common_voice.get_voice_samples(
            language="en",
            limit=5
        )
        assert len(samples) > 0

        # Check that cache file was created
        assert mock_common_voice.CACHE_FILE.exists()

        # Load cache and verify contents
        cache = mock_common_voice._load_cache()
        assert isinstance(cache, dict)
        assert len(cache) > 0

        # Test cache validation
        assert mock_common_voice._is_cache_valid(samples)

    def test_error_handling(self, mock_common_voice):
        """Test that error handling works correctly."""
        # Test invalid language
        samples = mock_common_voice.get_voice_samples(
            language="invalid",
            limit=5
        )
        assert isinstance(samples, list)
        assert len(samples) == 0

        # Test invalid duration range
        samples = mock_common_voice.get_samples_by_duration(
            language="en",
            min_duration=10.0,
            max_duration=1.0
        )
        assert isinstance(samples, list)
        assert len(samples) == 0 