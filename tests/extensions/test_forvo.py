"""Integration tests for the Forvo extension."""

import pytest
from pathlib import Path
import json
from extensions.forvo import Forvo, Pronunciation
from utils.config import config

class TestForvo:
    """Integration test suite for the Forvo extension."""

    def setup_method(self):
        """Setup method to check API key availability."""
        if not config.forvo_api_key and not config.ignore_missing_api_keys:
            pytest.skip("Forvo API key not configured. Set forvo_api_key in config.json or set ignore_missing_api_keys to True.")

    def test_initialization(self):
        """Test that the Forvo instance initializes correctly."""
        forvo = Forvo()
        assert forvo is not None
        assert isinstance(forvo, Forvo)

    def test_get_pronunciations(self):
        """Test that pronunciations are retrieved correctly."""
        forvo = Forvo()
        
        # Test getting pronunciations for a word
        pronunciations = forvo.get_pronunciations(
            word="hello",
            language="en",
            limit=5
        )
        assert isinstance(pronunciations, list)
        if config.forvo_api_key:
            assert len(pronunciations) <= 5
            assert all(isinstance(pron, Pronunciation) for pron in pronunciations)
            assert all(pron.word == "hello" for pron in pronunciations)
            assert all(pron.language == "en" for pron in pronunciations)
            assert all(pron.audio_url is not None for pron in pronunciations)
        else:
            assert len(pronunciations) == 0

    def test_get_top_pronunciation(self):
        """Test that the top pronunciation is retrieved correctly."""
        forvo = Forvo()
        
        top_pron = forvo.get_top_pronunciation(
            word="hello",
            language="en"
        )
        if config.forvo_api_key:
            assert isinstance(top_pron, Pronunciation)
            assert top_pron.word == "hello"
            assert top_pron.language == "en"
            assert top_pron.audio_url is not None
            assert top_pron.votes >= 0
        else:
            assert top_pron is None

    def test_get_available_languages(self):
        """Test that available languages are returned correctly."""
        forvo = Forvo()
        
        languages = forvo.get_available_languages()
        assert isinstance(languages, list)
        if config.forvo_api_key:
            assert len(languages) > 0
            assert all(isinstance(lang, str) for lang in languages)
            # Verify some common languages are present
            assert "English" in languages
            assert "German" in languages
            assert "French" in languages
        else:
            assert len(languages) == 0

    def test_get_country_pronunciations(self):
        """Test that pronunciations from a specific country are retrieved correctly."""
        forvo = Forvo()
        
        country_prons = forvo.get_country_pronunciations(
            word="hello",
            language="en",
            country="United States"
        )
        assert isinstance(country_prons, list)
        if config.forvo_api_key:
            assert all(isinstance(pron, Pronunciation) for pron in country_prons)
            assert all(pron.country == "United States" for pron in country_prons)
        else:
            assert len(country_prons) == 0

    def test_get_user_pronunciations(self):
        """Test that pronunciations by a specific user are retrieved correctly."""
        forvo = Forvo()
        
        if not config.forvo_api_key:
            user_prons = forvo.get_user_pronunciations(
                username="test_user",
                limit=5
            )
            assert isinstance(user_prons, list)
            assert len(user_prons) == 0
            return
            
        # First get a valid username from a pronunciation
        pronunciations = forvo.get_pronunciations(
            word="hello",
            language="en",
            limit=1
        )
        assert len(pronunciations) > 0, "No pronunciations found for testing"
        
        username = pronunciations[0].username
        user_prons = forvo.get_user_pronunciations(
            username=username,
            limit=5
        )
        assert isinstance(user_prons, list)
        assert len(user_prons) <= 5
        assert all(isinstance(pron, Pronunciation) for pron in user_prons)
        assert all(pron.username == username for pron in user_prons)

    def test_error_handling(self):
        """Test that error handling works correctly."""
        forvo = Forvo()
        
        # Test invalid word
        pronunciations = forvo.get_pronunciations(
            word="",
            language="en",
            limit=5
        )
        assert isinstance(pronunciations, list)
        assert len(pronunciations) == 0

        # Test invalid language
        pronunciations = forvo.get_pronunciations(
            word="hello",
            language="invalid",
            limit=5
        )
        assert isinstance(pronunciations, list)
        assert len(pronunciations) == 0

        # Test invalid country
        pronunciations = forvo.get_country_pronunciations(
            word="hello",
            language="en",
            country="InvalidCountry"
        )
        assert isinstance(pronunciations, list)
        assert len(pronunciations) == 0 