"""Integration tests for the Tatoeba extension."""

import pytest
from pathlib import Path
import json
from extensions.tatoeba import Tatoeba, TatoebaSentence

class TestTatoeba:
    """Integration test suite for the Tatoeba extension."""

    def test_initialization(self):
        """Test that the Tatoeba instance initializes correctly."""
        tatoeba = Tatoeba()
        assert tatoeba is not None
        assert isinstance(tatoeba, Tatoeba)

    def test_search_sentences(self):
        """Test that sentence search works correctly."""
        tatoeba = Tatoeba()
        
        # Test search with basic parameters
        sentences = tatoeba.search_sentences(
            language="eng",
            query="hello",
            limit=5
        )
        assert isinstance(sentences, list)
        assert len(sentences) <= 5
        assert all(isinstance(sent, TatoebaSentence) for sent in sentences)
        assert all(sent.language == "eng" for sent in sentences)
        assert all(sent.text is not None for sent in sentences)
        assert all(isinstance(sent.translations, list) for sent in sentences)

        # Test search with length filters
        sentences = tatoeba.search_sentences(
            language="eng",
            min_length=10,
            max_length=20,
            limit=5
        )
        assert isinstance(sentences, list)
        assert len(sentences) <= 5
        assert all(10 <= len(sent.text) <= 20 for sent in sentences)

        # Test search with audio filter
        sentences = tatoeba.search_sentences(
            language="eng",
            has_audio=True,
            limit=5
        )
        assert isinstance(sentences, list)
        assert len(sentences) <= 5
        assert all(sent.audio_url is not None for sent in sentences)

    def test_get_sentence(self):
        """Test that specific sentence retrieval works correctly."""
        tatoeba = Tatoeba()
        
        # Get a sentence ID from a search
        sentences = tatoeba.search_sentences(
            language="eng",
            limit=1
        )
        if sentences:
            sentence_id = sentences[0].id
            sentence = tatoeba.get_sentence(sentence_id)
            assert isinstance(sentence, TatoebaSentence)
            assert sentence.id == sentence_id
            assert sentence.text is not None
            assert sentence.language is not None
            assert isinstance(sentence.translations, list)
            assert all(isinstance(t, TatoebaSentence) for t in sentence.translations)

    def test_get_random_sentence(self):
        """Test that random sentence retrieval works correctly."""
        tatoeba = Tatoeba()
        
        # Test basic random sentence
        sentence = tatoeba.get_random_sentence(language="eng")
        assert isinstance(sentence, TatoebaSentence)
        assert sentence.language == "eng"
        assert sentence.text is not None

        # Test random sentence with length filters
        sentence = tatoeba.get_random_sentence(
            language="eng",
            min_length=10,
            max_length=20
        )
        assert isinstance(sentence, TatoebaSentence)
        assert 10 <= len(sentence.text) <= 20

        # Test random sentence with audio
        sentence = tatoeba.get_random_sentence(
            language="eng",
            has_audio=True
        )
        assert isinstance(sentence, TatoebaSentence)
        assert sentence.audio_url is not None

    def test_get_available_languages(self):
        """Test that available languages are returned correctly."""
        tatoeba = Tatoeba()
        
        languages = tatoeba.get_available_languages()
        assert isinstance(languages, list)
        assert len(languages) > 0
        assert all(isinstance(lang, str) for lang in languages)
        assert "eng" in languages
        assert "deu" in languages
        assert "fra" in languages
        assert "jpn" in languages

    def test_cache_handling(self, temp_cache_dir):
        """Test that cache handling works correctly."""
        tatoeba = Tatoeba()
        
        # Set up cache directory and file paths
        tatoeba.CACHE_DIR = temp_cache_dir
        tatoeba.CACHE_FILE = temp_cache_dir / "tatoeba_cache.json"
        
        # Clear any existing cache
        tatoeba.sentences = {}
        if tatoeba.CACHE_FILE.exists():
            tatoeba.CACHE_FILE.unlink()

        # Perform a search to populate cache
        sentences = tatoeba.search_sentences(
            language="eng",
            limit=5
        )
        assert len(sentences) > 0

        # Check that cache file was created
        assert tatoeba.CACHE_FILE.exists()

        # Load cache and verify contents
        tatoeba._load_cache()
        assert isinstance(tatoeba.sentences, dict)
        assert len(tatoeba.sentences) > 0

        # Test cache validation
        assert tatoeba._is_cache_valid(sentences[0])

    def test_error_handling(self):
        """Test that error handling works correctly."""
        tatoeba = Tatoeba()
        
        # Test invalid sentence ID
        sentence = tatoeba.get_sentence(-1)
        assert sentence is None

        # Test invalid search parameters
        sentences = tatoeba.search_sentences(
            language="invalid",
            limit=5
        )
        assert isinstance(sentences, list)
        assert len(sentences) == 0

        # Test invalid length filters
        sentences = tatoeba.search_sentences(
            language="eng",
            min_length=20,
            max_length=10,
            limit=5
        )
        assert isinstance(sentences, list)
        assert len(sentences) == 0

        # Test invalid limit
        sentences = tatoeba.search_sentences(
            language="eng",
            limit=-1
        )
        assert isinstance(sentences, list)
        assert len(sentences) == 0 