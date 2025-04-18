"""Integration tests for the WordNet extension."""

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
        # Check that the original word is in the synonyms list
        assert "happy" in synonyms
        # Check that we have some common synonyms
        common_synonyms = ["glad", "content", "pleased", "joyful", "cheerful"]
        assert any(syn in synonyms for syn in common_synonyms)

    def test_get_antonyms(self):
        """Test that antonym retrieval works correctly."""
        wordnet = WordNet()
        
        antonyms = wordnet.get_antonyms("happy")
        assert isinstance(antonyms, list)
        assert len(antonyms) > 0
        assert all(isinstance(a, str) for a in antonyms)
        # Check for common antonyms
        common_antonyms = ["sad", "unhappy", "miserable", "depressed"]
        assert any(ant in antonyms for ant in common_antonyms)

    def test_get_hypernyms(self):
        """Test that hypernym retrieval works correctly."""
        wordnet = WordNet()
        
        hypernyms = wordnet.get_hypernyms("dog")
        assert isinstance(hypernyms, list)
        assert len(hypernyms) > 0
        assert all(isinstance(h, str) for h in hypernyms)
        
        # Check for common hypernyms
        common_hypernyms = ["canine", "animal", "mammal", "creature"]
        assert any(h in hypernyms for h in common_hypernyms)

    def test_get_hyponyms(self):
        """Test that hyponym retrieval works correctly."""
        wordnet = WordNet()
        
        hyponyms = wordnet.get_hyponyms("dog")
        assert isinstance(hyponyms, list)
        assert len(hyponyms) > 0
        assert all(isinstance(h, str) for h in hyponyms)
        
        # Check for common hyponyms
        common_hyponyms = ["puppy", "hound", "pug", "dalmatian", "terrier"]
        assert any(h in hyponyms for h in common_hyponyms)

    def test_get_meronyms(self):
        """Test that meronym retrieval works correctly."""
        wordnet = WordNet()
        
        meronyms = wordnet.get_meronyms("tree")
        assert isinstance(meronyms, list)
        assert len(meronyms) > 0
        assert all(isinstance(m, str) for m in meronyms)
        
        # Check for tree-related parts
        tree_parts = ["trunk", "limb", "crown", "root", "bark", "leaf", "branch"]
        assert any(part in meronyms for part in tree_parts)

    def test_get_holonyms(self):
        """Test that holonym retrieval works correctly."""
        wordnet = WordNet()
        
        holonyms = wordnet.get_holonyms("branch")
        assert isinstance(holonyms, list)
        assert len(holonyms) > 0
        assert all(isinstance(h, str) for h in holonyms)
        
        # Check for branch-related wholes
        branch_wholes = ["tree", "plant", "shrub", "bush", "furcation"]
        assert any(whole in holonyms for whole in branch_wholes), f"Found branch wholes: {holonyms}"

    def test_get_word_similarity(self):
        """Test that word similarity calculation works correctly."""
        wordnet = WordNet()
        
        # Test similar words
        similarity = wordnet.get_word_similarity("dog", "puppy")
        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0
        assert similarity >= 0.4  # Should be similar
        
        # Test very similar words (synonyms)
        similarity = wordnet.get_word_similarity("happy", "joyful")
        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0
        assert similarity >= 0.3  # Synonyms should be similar
        
        # Test unrelated words
        similarity = wordnet.get_word_similarity("dog", "computer")
        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0
        assert similarity < 0.3  # Unrelated words should have low similarity
        
        # Test identical words
        similarity = wordnet.get_word_similarity("dog", "dog")
        assert isinstance(similarity, float)
        assert similarity == 1.0  # Identical words should have maximum similarity

    def test_get_related_words(self):
        """Test that related word retrieval works correctly."""
        wordnet = WordNet()
        
        related = wordnet.get_related_words("dog")
        assert isinstance(related, set)
        assert len(related) > 0
        assert all(isinstance(r, str) for r in related)
        
        # Check for common related words
        common_related = {"puppy", "canine", "animal", "pet", "mammal"}
        assert any(word in related for word in common_related), f"Found related words: {related}"
        
        # Test with raw results
        raw_related = wordnet.get_related_words("dog", cleaned=False)
        assert isinstance(raw_related, set)
        assert len(raw_related) > 0
        assert all(isinstance(r, str) for r in raw_related)
        assert any('.' in word for word in raw_related)  # Should contain synset format

    def test_cleaned_relations(self):
        """Test that the get_cleaned_relations method works correctly."""
        wordnet = WordNet()
        
        word_info = wordnet.get_word_info("dog")
        assert word_info is not None
        
        cleaned_relations = word_info.get_cleaned_relations()
        assert isinstance(cleaned_relations, dict)
        assert all(key in cleaned_relations for key in [
            'synonyms', 'antonyms', 'hypernyms', 'hyponyms', 
            'meronyms', 'holonyms'
        ])
        
        # Check that all lists contain strings
        for relation_type, words in cleaned_relations.items():
            assert isinstance(words, list)
            assert all(isinstance(word, str) for word in words)
            assert all('.' not in word for word in words)  # No synset format

    def test_cache_handling(self, temp_cache_dir):
        """Test that cache handling works correctly."""
        wordnet = WordNet()
        
        # Set up cache directory
        wordnet.CACHE_DIR = temp_cache_dir
        wordnet.CACHE_FILE = temp_cache_dir / "words.json"
        
        # Ensure cache directory exists
        wordnet.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        # Perform a search to populate cache
        word_info = wordnet.get_word_info("happy")
        assert word_info is not None
        
        # Explicitly save the cache
        wordnet._save_cache()
        
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