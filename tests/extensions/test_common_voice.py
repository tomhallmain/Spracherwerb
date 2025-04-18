"""Integration tests for the Common Voice extension.

NOTE: These tests are currently skipped as the Common Voice API appears to be undocumented
and potentially no longer publicly accessible. The extension should be considered for removal
or replacement with an alternative voice sample service.
"""

import pytest
from pathlib import Path
import json
from extensions.common_voice import CommonVoice, VoiceSample

class TestCommonVoice:
    """Integration test suite for the Common Voice extension."""

    @pytest.mark.skip(reason="Common Voice API appears to be undocumented and potentially no longer accessible")
    def test_initialization(self):
        """Test that the Common Voice instance initializes correctly."""
        common_voice = CommonVoice()
        assert common_voice is not None
        assert isinstance(common_voice, CommonVoice)

    @pytest.mark.skip(reason="Common Voice API appears to be undocumented and potentially no longer accessible")
    def test_get_voice_samples(self):
        """Test that voice samples are retrieved correctly."""
        common_voice = CommonVoice()
        
        # Test getting voice samples with basic parameters
        samples = common_voice.get_voice_samples(
            language="en-US",
            limit=5,
            min_duration=1.0,
            max_duration=10.0,
            min_votes=3
        )
        assert isinstance(samples, list)
        assert len(samples) <= 5
        assert all(isinstance(sample, VoiceSample) for sample in samples)
        assert all(sample.language == "en-US" for sample in samples)
        assert all(1.0 <= sample.duration <= 10.0 for sample in samples)
        assert all(sample.votes["up"] >= 3 for sample in samples)
        assert all(sample.audio_url is not None for sample in samples)

    @pytest.mark.skip(reason="Common Voice API appears to be undocumented and potentially no longer accessible")
    def test_get_samples_by_accent(self):
        """Test that samples with specific accents are retrieved correctly."""
        common_voice = CommonVoice()
        
        accent_samples = common_voice.get_samples_by_accent(
            language="en-US",
            accent="American",
            limit=5
        )
        assert isinstance(accent_samples, list)
        assert len(accent_samples) <= 5
        assert all(isinstance(sample, VoiceSample) for sample in accent_samples)
        assert all(sample.accent == "American" for sample in accent_samples)

    @pytest.mark.skip(reason="Common Voice API appears to be undocumented and potentially no longer accessible")
    def test_get_samples_by_duration(self):
        """Test that samples within duration range are retrieved correctly."""
        common_voice = CommonVoice()
        
        duration_samples = common_voice.get_samples_by_duration(
            language="en-US",
            min_duration=2.0,
            max_duration=5.0
        )
        assert isinstance(duration_samples, list)
        assert all(isinstance(sample, VoiceSample) for sample in duration_samples)
        assert all(2.0 <= sample.duration <= 5.0 for sample in duration_samples)

    @pytest.mark.skip(reason="Common Voice API appears to be undocumented and potentially no longer accessible")
    def test_download_sample(self, temp_cache_dir):
        """Test that samples can be downloaded correctly."""
        common_voice = CommonVoice()
        
        # Get a sample to download
        samples = common_voice.get_voice_samples(
            language="en-US",
            limit=1
        )
        assert len(samples) > 0, "No samples found for testing"
        
        sample = samples[0]
        output_path = common_voice.download_sample(sample, temp_cache_dir)
        assert output_path is not None
        assert output_path.exists()
        assert output_path.suffix == ".mp3"

    @pytest.mark.skip(reason="Common Voice API appears to be undocumented and potentially no longer accessible")
    def test_get_sample_statistics(self):
        """Test that sample statistics are calculated correctly."""
        common_voice = CommonVoice()
        
        stats = common_voice.get_sample_statistics("en-US")
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

    @pytest.mark.skip(reason="Common Voice API appears to be undocumented and potentially no longer accessible")
    def test_get_available_languages(self):
        """Test that available languages are returned correctly."""
        common_voice = CommonVoice()
        
        languages = common_voice.get_available_languages()
        assert isinstance(languages, list)
        assert len(languages) > 0
        assert all(isinstance(lang, str) for lang in languages)
        # Verify some common languages are present
        assert "en-US" in languages
        assert "de" in languages
        assert "fr" in languages

    @pytest.mark.skip(reason="Common Voice API appears to be undocumented and potentially no longer accessible")
    def test_error_handling(self):
        """Test that error handling works correctly."""
        common_voice = CommonVoice()
        
        # Test invalid language
        samples = common_voice.get_voice_samples(
            language="invalid",
            limit=5
        )
        assert isinstance(samples, list)
        assert len(samples) == 0

        # Test invalid duration range
        samples = common_voice.get_samples_by_duration(
            language="en-US",
            min_duration=10.0,
            max_duration=1.0
        )
        assert isinstance(samples, list)
        assert len(samples) == 0 