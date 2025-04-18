"""Integration tests for the Wiktionary extension."""

import pytest
from pathlib import Path
import json
from extensions.wiktionary import Wiktionary, WiktionaryEntry

class TestWiktionary:
    """Integration test suite for the Wiktionary extension."""

    def test_initialization(self):
        """Test that the Wiktionary instance initializes correctly."""
        wiktionary = Wiktionary()
        assert wiktionary is not None
        assert isinstance(wiktionary, Wiktionary)

    def test_get_word_entry(self):
        """Test that word entry retrieval works correctly."""
        wiktionary = Wiktionary()
        
        # Test basic word entry retrieval
        entry = wiktionary.get_word_entry(
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
        entry = wiktionary.get_word_entry(
            word="hello",
            language="en",
            include_etymology=True
        )
        assert isinstance(entry, WiktionaryEntry)
        assert entry.etymology is not None

        # Test entry with examples
        entry = wiktionary.get_word_entry(
            word="hello",
            language="en",
            include_examples=True
        )
        assert isinstance(entry, WiktionaryEntry)
        assert isinstance(entry.examples, list)
        assert len(entry.examples) > 0
        assert all(isinstance(e, str) for e in entry.examples)

    def test_get_word_forms(self):
        """Test that word form retrieval works correctly."""
        wiktionary = Wiktionary()
        
        # Test verb forms
        forms = wiktionary.get_word_forms("run", "en")
        assert isinstance(forms, dict)
        assert len(forms) > 0
        assert all(isinstance(key, str) for key in forms.keys())
        assert all(isinstance(value, list) for value in forms.values())
        assert all(isinstance(v, str) for values in forms.values() for v in values)

        # Test noun forms
        forms = wiktionary.get_word_forms("child", "en")
        assert isinstance(forms, dict)
        assert len(forms) > 0
        assert "plural" in forms

    def test_get_synonyms(self):
        """Test that synonym retrieval works correctly."""
        wiktionary = Wiktionary()
        
        synonyms = wiktionary.get_synonyms("happy", "en")
        assert isinstance(synonyms, list)
        assert len(synonyms) > 0
        assert all(isinstance(s, str) for s in synonyms)
        assert "joyful" in synonyms
        assert "content" in synonyms

    def test_get_antonyms(self):
        """Test that antonym retrieval works correctly."""
        wiktionary = Wiktionary()
        
        antonyms = wiktionary.get_antonyms("happy", "en")
        assert isinstance(antonyms, list)
        assert len(antonyms) > 0
        assert all(isinstance(a, str) for a in antonyms)
        assert "sad" in antonyms
        assert "unhappy" in antonyms

    def test_cache_handling(self, temp_cache_dir):
        """Test that cache handling works correctly."""
        wiktionary = Wiktionary()
        
        # Set up cache directory
        wiktionary.CACHE_DIR = temp_cache_dir
        wiktionary.CACHE_FILE = temp_cache_dir / "entries.json"

        # Perform a search to populate cache
        entry = wiktionary.get_word_entry("hello", "en")
        assert entry is not None

        # Check that cache file was created
        assert wiktionary.CACHE_FILE.exists()

        # Load cache and verify contents
        cache = wiktionary._load_cache()
        assert isinstance(cache, dict)
        assert len(cache) > 0

        # Test cache validation
        assert wiktionary._is_cache_valid(entry)

    def test_error_handling(self):
        """Test that error handling works correctly."""
        wiktionary = Wiktionary()
        
        # Test invalid word
        entry = wiktionary.get_word_entry("invalidword123", "en")
        assert entry is None

        # Test invalid language
        entry = wiktionary.get_word_entry("hello", "invalid")
        assert entry is None

        # Test invalid word forms
        forms = wiktionary.get_word_forms("invalidword123", "en")
        assert isinstance(forms, dict)
        assert len(forms) == 0

        # Test invalid synonyms
        synonyms = wiktionary.get_synonyms("invalidword123", "en")
        assert isinstance(synonyms, list)
        assert len(synonyms) == 0

        # Test invalid antonyms
        antonyms = wiktionary.get_antonyms("invalidword123", "en")
        assert isinstance(antonyms, list)
        assert len(antonyms) == 0 