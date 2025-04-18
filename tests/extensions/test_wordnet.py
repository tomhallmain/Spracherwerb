"""Integration tests for the WordNet extension."""

import pytest
from pathlib import Path
import json
from extensions.wordnet import WordNet, WordInfo

class TestWordNet:
    """Integration test suite for the WordNet extension."""

    def test_initialization(self):
        """Test that the WordNet instance initializes correctly."""
        wordnet = WordNet()
        assert wordnet is not None
        assert isinstance(wordnet, WordNet)

    def test_get_word_info(self):
        """Test that word information retrieval works correctly."""
        wordnet = WordNet()
        
        # Test basic word info retrieval
        word_info = wordnet.get_word_info("happy")
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

    def test_get_synonyms(self):
        """Test that synonym retrieval works correctly."""
        wordnet = WordNet()
        
        synonyms = wordnet.get_synonyms("happy")
        assert isinstance(synonyms, list)
        assert len(synonyms) > 0
        assert all(isinstance(s, str) for s in synonyms)
        assert "joyful" in synonyms
        assert "content" in synonyms

    def test_get_antonyms(self):
        """Test that antonym retrieval works correctly."""
        wordnet = WordNet()
        
        antonyms = wordnet.get_antonyms("happy")
        assert isinstance(antonyms, list)
        assert len(antonyms) > 0
        assert all(isinstance(a, str) for a in antonyms)
        assert "sad" in antonyms
        assert "unhappy" in antonyms

    def test_get_hypernyms(self):
        """Test that hypernym retrieval works correctly."""
        wordnet = WordNet()
        
        hypernyms = wordnet.get_hypernyms("dog")
        assert isinstance(hypernyms, list)
        assert len(hypernyms) > 0
        assert all(isinstance(h, str) for h in hypernyms)
        assert "canine" in hypernyms
        assert "animal" in hypernyms

    def test_get_hyponyms(self):
        """Test that hyponym retrieval works correctly."""
        wordnet = WordNet()
        
        hyponyms = wordnet.get_hyponyms("dog")
        assert isinstance(hyponyms, list)
        assert len(hyponyms) > 0
        assert all(isinstance(h, str) for h in hyponyms)
        assert "puppy" in hyponyms
        assert "hound" in hyponyms

    def test_get_meronyms(self):
        """Test that meronym retrieval works correctly."""
        wordnet = WordNet()
        
        meronyms = wordnet.get_meronyms("tree")
        assert isinstance(meronyms, list)
        assert len(meronyms) > 0
        assert all(isinstance(m, str) for m in meronyms)
        assert "branch" in meronyms
        assert "trunk" in meronyms

    def test_get_holonyms(self):
        """Test that holonym retrieval works correctly."""
        wordnet = WordNet()
        
        holonyms = wordnet.get_holonyms("branch")
        assert isinstance(holonyms, list)
        assert len(holonyms) > 0
        assert all(isinstance(h, str) for h in holonyms)
        assert "tree" in holonyms

    def test_get_word_similarity(self):
        """Test that word similarity calculation works correctly."""
        wordnet = WordNet()
        
        # Test similar words
        similarity = wordnet.get_word_similarity("dog", "puppy")
        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0
        assert similarity > 0.5

        # Test unrelated words
        similarity = wordnet.get_word_similarity("dog", "computer")
        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0
        assert similarity < 0.5

    def test_get_related_words(self):
        """Test that related word retrieval works correctly."""
        wordnet = WordNet()
        
        related = wordnet.get_related_words("dog")
        assert isinstance(related, set)
        assert len(related) > 0
        assert all(isinstance(r, str) for r in related)
        assert "puppy" in related
        assert "canine" in related
        assert "animal" in related

    def test_cache_handling(self, temp_cache_dir):
        """Test that cache handling works correctly."""
        wordnet = WordNet()
        
        # Set up cache directory
        wordnet.CACHE_DIR = temp_cache_dir
        wordnet.CACHE_FILE = temp_cache_dir / "words.json"

        # Perform a search to populate cache
        word_info = wordnet.get_word_info("happy")
        assert word_info is not None

        # Check that cache file was created
        assert wordnet.CACHE_FILE.exists()

        # Load cache and verify contents
        cache = wordnet._load_cache()
        assert isinstance(cache, dict)
        assert len(cache) > 0

        # Test cache validation
        assert wordnet._is_cache_valid(word_info)

    def test_error_handling(self):
        """Test that error handling works correctly."""
        wordnet = WordNet()
        
        # Test invalid word
        word_info = wordnet.get_word_info("invalidword123")
        assert word_info is None

        # Test invalid synonyms
        synonyms = wordnet.get_synonyms("invalidword123")
        assert isinstance(synonyms, list)
        assert len(synonyms) == 0

        # Test invalid antonyms
        antonyms = wordnet.get_antonyms("invalidword123")
        assert isinstance(antonyms, list)
        assert len(antonyms) == 0

        # Test invalid hypernyms
        hypernyms = wordnet.get_hypernyms("invalidword123")
        assert isinstance(hypernyms, list)
        assert len(hypernyms) == 0

        # Test invalid hyponyms
        hyponyms = wordnet.get_hyponyms("invalidword123")
        assert isinstance(hyponyms, list)
        assert len(hyponyms) == 0

        # Test invalid meronyms
        meronyms = wordnet.get_meronyms("invalidword123")
        assert isinstance(meronyms, list)
        assert len(meronyms) == 0

        # Test invalid holonyms
        holonyms = wordnet.get_holonyms("invalidword123")
        assert isinstance(holonyms, list)
        assert len(holonyms) == 0

        # Test invalid word similarity
        similarity = wordnet.get_word_similarity("invalidword123", "dog")
        assert isinstance(similarity, float)
        assert similarity == 0.0

        # Test invalid related words
        related = wordnet.get_related_words("invalidword123")
        assert isinstance(related, set)
        assert len(related) == 0 