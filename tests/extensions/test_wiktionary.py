"""Integration tests for the Wiktionary extension."""

from pathlib import Path
import shutil
from extensions.wiktionary import Wiktionary, WiktionaryEntry

class TestWiktionary:
    """Integration test suite for the Wiktionary extension."""

    def setup_method(self):
        """Clear cache before each test."""
        cache_dir = Path("cache/wiktionary")
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)

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

        # Test verb forms - using "be" as it's a common irregular verb with conjugation tables
        forms = wiktionary.get_word_forms("ask", "en")
        assert forms, "Should find word forms for 'ask'"
        assert "present" in forms, "Should find present tense forms"
        assert "past" in forms, "Should find past tense forms"
        assert "past participle" in forms, "Should find past participle forms"
        
        # Verify some specific forms
        assert "ask" in forms["present"], "Should include 'ask' in present forms"
        assert "asking" in forms["present participle"], "Should include 'asking' in present participle forms"
        assert "asked" in forms["past participle"], "Should include 'asked' in past participle forms"

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
        wiktionary._load_cache()
        assert isinstance(wiktionary.entries, dict)
        assert len(wiktionary.entries) > 0

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