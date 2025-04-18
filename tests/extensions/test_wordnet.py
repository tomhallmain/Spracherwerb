"""Tests for the WordNet extension."""

import pytest
from pathlib import Path
import json
from extensions.wordnet import WordNet, WordInfo

class TestWordNet:
    """Test suite for the WordNet extension."""

    def test_initialization(self, mock_wordnet):
        """Test that the WordNet instance initializes correctly."""
        assert mock_wordnet is not None
        assert isinstance(mock_wordnet, WordNet)

    def test_get_word_info(self, mock_wordnet):
        """Test that word information retrieval works correctly."""
        # Test basic word info retrieval
        word_info = mock_wordnet.get_word_info("happy")
        assert isinstance(word_info, WordInfo)
        assert word_info.word == "happy"
        assert word_info.part_of_speech is not None
        assert isinstance(word_info.definitions, list)
        assert len(word_info.definitions) > 0
        assert all(isinstance(d, str) for d in word_info.definitions)
        assert isinstance(word_info.examples, list)
        assert isinstance(word_info.synonyms, list)
        assert isinstance(word_info.antonyms, list)
        assert isinstance(word_info.hypernyms, list)
        assert isinstance(word_info.hyponyms, list)
        assert isinstance(word_info.meronyms, list)
        assert isinstance(word_info.holonyms, list)

    def test_get_synonyms(self, mock_wordnet):
        """Test that synonym retrieval works correctly."""
        synonyms = mock_wordnet.get_synonyms("happy")
        assert isinstance(synonyms, list)
        assert len(synonyms) > 0
        assert all(isinstance(s, str) for s in synonyms)
        assert "joyful" in synonyms
        assert "content" in synonyms

    def test_get_antonyms(self, mock_wordnet):
        """Test that antonym retrieval works correctly."""
        antonyms = mock_wordnet.get_antonyms("happy")
        assert isinstance(antonyms, list)
        assert len(antonyms) > 0
        assert all(isinstance(a, str) for a in antonyms)
        assert "sad" in antonyms
        assert "unhappy" in antonyms

    def test_get_hypernyms(self, mock_wordnet):
        """Test that hypernym retrieval works correctly."""
        hypernyms = mock_wordnet.get_hypernyms("dog")
        assert isinstance(hypernyms, list)
        assert len(hypernyms) > 0
        assert all(isinstance(h, str) for h in hypernyms)
        assert "canine" in hypernyms
        assert "animal" in hypernyms

    def test_get_hyponyms(self, mock_wordnet):
        """Test that hyponym retrieval works correctly."""
        hyponyms = mock_wordnet.get_hyponyms("dog")
        assert isinstance(hyponyms, list)
        assert len(hyponyms) > 0
        assert all(isinstance(h, str) for h in hyponyms)
        assert "puppy" in hyponyms
        assert "hound" in hyponyms

    def test_get_meronyms(self, mock_wordnet):
        """Test that meronym retrieval works correctly."""
        meronyms = mock_wordnet.get_meronyms("tree")
        assert isinstance(meronyms, list)
        assert len(meronyms) > 0
        assert all(isinstance(m, str) for m in meronyms)
        assert "branch" in meronyms
        assert "trunk" in meronyms

    def test_get_holonyms(self, mock_wordnet):
        """Test that holonym retrieval works correctly."""
        holonyms = mock_wordnet.get_holonyms("branch")
        assert isinstance(holonyms, list)
        assert len(holonyms) > 0
        assert all(isinstance(h, str) for h in holonyms)
        assert "tree" in holonyms

    def test_get_word_similarity(self, mock_wordnet):
        """Test that word similarity calculation works correctly."""
        # Test similar words
        similarity = mock_wordnet.get_word_similarity("dog", "puppy")
        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0
        assert similarity > 0.5

        # Test unrelated words
        similarity = mock_wordnet.get_word_similarity("dog", "computer")
        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0
        assert similarity < 0.5

    def test_get_related_words(self, mock_wordnet):
        """Test that related word retrieval works correctly."""
        related = mock_wordnet.get_related_words("dog")
        assert isinstance(related, set)
        assert len(related) > 0
        assert all(isinstance(r, str) for r in related)
        assert "puppy" in related
        assert "canine" in related
        assert "animal" in related

    def test_cache_handling(self, mock_wordnet, temp_cache_dir):
        """Test that cache handling works correctly."""
        # Set up cache directory
        mock_wordnet.CACHE_DIR = temp_cache_dir
        mock_wordnet.CACHE_FILE = temp_cache_dir / "words.json"

        # Perform a search to populate cache
        word_info = mock_wordnet.get_word_info("happy")
        assert word_info is not None

        # Check that cache file was created
        assert mock_wordnet.CACHE_FILE.exists()

        # Load cache and verify contents
        cache = mock_wordnet._load_cache()
        assert isinstance(cache, dict)
        assert len(cache) > 0

        # Test cache validation
        assert mock_wordnet._is_cache_valid(word_info)

    def test_error_handling(self, mock_wordnet):
        """Test that error handling works correctly."""
        # Test invalid word
        word_info = mock_wordnet.get_word_info("invalidword123")
        assert word_info is None

        # Test invalid synonyms
        synonyms = mock_wordnet.get_synonyms("invalidword123")
        assert isinstance(synonyms, list)
        assert len(synonyms) == 0

        # Test invalid antonyms
        antonyms = mock_wordnet.get_antonyms("invalidword123")
        assert isinstance(antonyms, list)
        assert len(antonyms) == 0

        # Test invalid hypernyms
        hypernyms = mock_wordnet.get_hypernyms("invalidword123")
        assert isinstance(hypernyms, list)
        assert len(hypernyms) == 0

        # Test invalid hyponyms
        hyponyms = mock_wordnet.get_hyponyms("invalidword123")
        assert isinstance(hyponyms, list)
        assert len(hyponyms) == 0

        # Test invalid meronyms
        meronyms = mock_wordnet.get_meronyms("invalidword123")
        assert isinstance(meronyms, list)
        assert len(meronyms) == 0

        # Test invalid holonyms
        holonyms = mock_wordnet.get_holonyms("invalidword123")
        assert isinstance(holonyms, list)
        assert len(holonyms) == 0

        # Test invalid word similarity
        similarity = mock_wordnet.get_word_similarity("invalidword123", "dog")
        assert isinstance(similarity, float)
        assert similarity == 0.0

        # Test invalid related words
        related = mock_wordnet.get_related_words("invalidword123")
        assert isinstance(related, set)
        assert len(related) == 0 