"""Tests for the Forvo extension."""

import pytest
from pathlib import Path
import json
from extensions.forvo import Forvo, Pronunciation

class TestForvo:
    """Test suite for the Forvo extension."""

    def test_initialization(self, mock_forvo):
        """Test that the Forvo instance initializes correctly."""
        assert mock_forvo is not None
        assert isinstance(mock_forvo, Forvo)

    def test_get_pronunciations(self, mock_forvo):
        """Test that pronunciations are retrieved correctly."""
        # Test getting pronunciations for a word
        pronunciations = mock_forvo.get_pronunciations(
            word="hello",
            language="en",
            limit=5
        )
        assert isinstance(pronunciations, list)
        assert len(pronunciations) <= 5
        assert all(isinstance(pron, Pronunciation) for pron in pronunciations)
        assert all(pron.word == "hello" for pron in pronunciations)
        assert all(pron.language == "en" for pron in pronunciations)
        assert all(pron.audio_url is not None for pron in pronunciations)

    def test_get_top_pronunciation(self, mock_forvo):
        """Test that the top pronunciation is retrieved correctly."""
        top_pron = mock_forvo.get_top_pronunciation(
            word="hello",
            language="en"
        )
        assert isinstance(top_pron, Pronunciation)
        assert top_pron.word == "hello"
        assert top_pron.language == "en"
        assert top_pron.audio_url is not None
        assert top_pron.votes >= 0

    def test_get_available_languages(self, mock_forvo):
        """Test that available languages are returned correctly."""
        languages = mock_forvo.get_available_languages()
        assert isinstance(languages, list)
        assert len(languages) > 0
        assert all(isinstance(lang, str) for lang in languages)

    def test_get_country_pronunciations(self, mock_forvo):
        """Test that pronunciations from a specific country are retrieved correctly."""
        country_prons = mock_forvo.get_country_pronunciations(
            word="hello",
            language="en",
            country="United States"
        )
        assert isinstance(country_prons, list)
        assert all(isinstance(pron, Pronunciation) for pron in country_prons)
        assert all(pron.country == "United States" for pron in country_prons)

    def test_get_user_pronunciations(self, mock_forvo):
        """Test that pronunciations by a specific user are retrieved correctly."""
        user_prons = mock_forvo.get_user_pronunciations(
            username="test_user",
            limit=5
        )
        assert isinstance(user_prons, list)
        assert len(user_prons) <= 5
        assert all(isinstance(pron, Pronunciation) for pron in user_prons)
        assert all(pron.username == "test_user" for pron in user_prons)

    def test_cache_handling(self, mock_forvo, temp_cache_dir):
        """Test that cache handling works correctly."""
        # Set up cache directory
        mock_forvo.CACHE_DIR = temp_cache_dir
        mock_forvo.CACHE_FILE = temp_cache_dir / "forvo_cache.json"

        # Perform a search to populate cache
        pronunciations = mock_forvo.get_pronunciations(
            word="hello",
            language="en",
            limit=5
        )
        assert len(pronunciations) > 0

        # Check that cache file was created
        assert mock_forvo.CACHE_FILE.exists()

        # Load cache and verify contents
        cache = mock_forvo._load_cache()
        assert isinstance(cache, dict)
        assert len(cache) > 0

        # Test cache validation
        assert mock_forvo._is_cache_valid(pronunciations)

    def test_error_handling(self, mock_forvo):
        """Test that error handling works correctly."""
        # Test invalid word
        pronunciations = mock_forvo.get_pronunciations(
            word="",
            language="en",
            limit=5
        )
        assert isinstance(pronunciations, list)
        assert len(pronunciations) == 0

        # Test invalid language
        pronunciations = mock_forvo.get_pronunciations(
            word="hello",
            language="invalid",
            limit=5
        )
        assert isinstance(pronunciations, list)
        assert len(pronunciations) == 0 