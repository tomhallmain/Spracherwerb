"""Tests for the Wiktionary extension."""

import pytest
from pathlib import Path
import json
from extensions.wiktionary import Wiktionary, WiktionaryEntry

class TestWiktionary:
    """Test suite for the Wiktionary extension."""

    def test_initialization(self, mock_wiktionary):
        """Test that the Wiktionary instance initializes correctly."""
        assert mock_wiktionary is not None
        assert isinstance(mock_wiktionary, Wiktionary)

    def test_get_word_entry(self, mock_wiktionary):
        """Test that word entry retrieval works correctly."""
        # Test basic word entry retrieval
        entry = mock_wiktionary.get_word_entry(
            word="hello",
            language="en"
        )
        assert isinstance(entry, WiktionaryEntry)
        assert entry.word == "hello"
        assert entry.language == "en"
        assert entry.part_of_speech is not None
        assert isinstance(entry.definitions, list)
        assert len(entry.definitions) > 0
        assert all(isinstance(d, str) for d in entry.definitions)

        # Test entry with etymology
        entry = mock_wiktionary.get_word_entry(
            word="hello",
            language="en",
            include_etymology=True
        )
        assert isinstance(entry, WiktionaryEntry)
        assert entry.etymology is not None

        # Test entry with examples
        entry = mock_wiktionary.get_word_entry(
            word="hello",
            language="en",
            include_examples=True
        )
        assert isinstance(entry, WiktionaryEntry)
        assert isinstance(entry.examples, list)
        assert len(entry.examples) > 0
        assert all(isinstance(e, str) for e in entry.examples)

    def test_get_word_forms(self, mock_wiktionary):
        """Test that word form retrieval works correctly."""
        # Test verb forms
        forms = mock_wiktionary.get_word_forms("run", "en")
        assert isinstance(forms, dict)
        assert len(forms) > 0
        assert all(isinstance(key, str) for key in forms.keys())
        assert all(isinstance(value, list) for value in forms.values())
        assert all(isinstance(v, str) for values in forms.values() for v in values)

        # Test noun forms
        forms = mock_wiktionary.get_word_forms("child", "en")
        assert isinstance(forms, dict)
        assert len(forms) > 0
        assert "plural" in forms

    def test_get_synonyms(self, mock_wiktionary):
        """Test that synonym retrieval works correctly."""
        synonyms = mock_wiktionary.get_synonyms("happy", "en")
        assert isinstance(synonyms, list)
        assert len(synonyms) > 0
        assert all(isinstance(s, str) for s in synonyms)
        assert "joyful" in synonyms
        assert "content" in synonyms

    def test_get_antonyms(self, mock_wiktionary):
        """Test that antonym retrieval works correctly."""
        antonyms = mock_wiktionary.get_antonyms("happy", "en")
        assert isinstance(antonyms, list)
        assert len(antonyms) > 0
        assert all(isinstance(a, str) for a in antonyms)
        assert "sad" in antonyms
        assert "unhappy" in antonyms

    def test_cache_handling(self, mock_wiktionary, temp_cache_dir):
        """Test that cache handling works correctly."""
        # Set up cache directory
        mock_wiktionary.CACHE_DIR = temp_cache_dir
        mock_wiktionary.CACHE_FILE = temp_cache_dir / "entries.json"

        # Perform a search to populate cache
        entry = mock_wiktionary.get_word_entry("hello", "en")
        assert entry is not None

        # Check that cache file was created
        assert mock_wiktionary.CACHE_FILE.exists()

        # Load cache and verify contents
        cache = mock_wiktionary._load_cache()
        assert isinstance(cache, dict)
        assert len(cache) > 0

        # Test cache validation
        assert mock_wiktionary._is_cache_valid(entry)

    def test_error_handling(self, mock_wiktionary):
        """Test that error handling works correctly."""
        # Test invalid word
        entry = mock_wiktionary.get_word_entry("invalidword123", "en")
        assert entry is None

        # Test invalid language
        entry = mock_wiktionary.get_word_entry("hello", "invalid")
        assert entry is None

        # Test invalid word forms
        forms = mock_wiktionary.get_word_forms("invalidword123", "en")
        assert isinstance(forms, dict)
        assert len(forms) == 0

        # Test invalid synonyms
        synonyms = mock_wiktionary.get_synonyms("invalidword123", "en")
        assert isinstance(synonyms, list)
        assert len(synonyms) == 0

        # Test invalid antonyms
        antonyms = mock_wiktionary.get_antonyms("invalidword123", "en")
        assert isinstance(antonyms, list)
        assert len(antonyms) == 0 