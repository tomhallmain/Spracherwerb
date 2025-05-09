"""Integration tests for the LanguageTool extension."""

import pytest
from extensions.languagetool import LanguageTool, LanguageError
from utils.config import config

class TestLanguageTool:
    """Integration test suite for the LanguageTool extension."""

    @pytest.fixture
    def config(self):
        """Load test configuration."""
        return config

    @pytest.fixture
    def languagetool(self, config):
        """Create LanguageTool instance with API key from config."""
        api_key = config.api_keys.get("languagetool")
        if not api_key:
            pytest.skip("LanguageTool API key not configured")
        return LanguageTool(api_key)

    def test_initialization(self, languagetool):
        """Test that the LanguageTool instance initializes correctly."""
        assert languagetool is not None
        assert isinstance(languagetool, LanguageTool)

    def test_check_text(self, languagetool):
        """Test that text checking works correctly."""
        # Test with a simple text containing errors
        text = "I has a cat. They is happy."
        errors = languagetool.check_text(
            text=text,
            language="en"
        )
        assert isinstance(errors, list)
        assert len(errors) > 0
        assert all(isinstance(error, LanguageError) for error in errors)
        assert all(error.message is not None for error in errors)
        assert all(error.short_message is not None for error in errors)
        assert all(error.offset >= 0 for error in errors)
        assert all(error.length > 0 for error in errors)
        assert all(error.rule_id is not None for error in errors)
        assert all(error.rule_description is not None for error in errors)
        assert all(error.rule_category is not None for error in errors)

    def test_check_text_with_rules(self, languagetool):
        """Test that text checking with specific rules works correctly."""
        text = "I has a cat. They is happy."
        errors = languagetool.check_text(
            text=text,
            language="en",
            enabled_rules=["EN_VERB_AGREEMENT"],
            disabled_rules=["EN_A_VS_AN"]
        )
        assert isinstance(errors, list)
        assert all(error.rule_id == "EN_VERB_AGREEMENT" for error in errors)

    def test_get_available_languages(self, languagetool):
        """Test that available languages are returned correctly."""
        languages = languagetool.get_available_languages()
        assert isinstance(languages, list)
        assert len(languages) > 0
        assert all(isinstance(lang, str) for lang in languages)
        assert "en" in languages
        assert "de" in languages

    def test_get_available_rules(self, languagetool):
        """Test that available rules are returned correctly."""
        rules = languagetool.get_available_rules("en")
        assert isinstance(rules, dict)
        assert "rules" in rules
        assert len(rules["rules"]) > 0
        assert all("id" in rule for rule in rules["rules"])
        assert all("description" in rule for rule in rules["rules"])

    def test_get_rule_categories(self, languagetool):
        """Test that rule categories are returned correctly."""
        categories = languagetool.get_rule_categories("en")
        assert isinstance(categories, list)
        assert len(categories) > 0
        assert all(isinstance(cat, str) for cat in categories)
        assert "GRAMMAR" in categories
        assert "TYPOS" in categories

    def test_get_error_statistics(self, languagetool):
        """Test that error statistics are calculated correctly."""
        text = "I has a cat. They is happy."
        stats = languagetool.get_error_statistics(text, "en")
        assert isinstance(stats, dict)
        assert "total_errors" in stats
        assert "categories" in stats
        assert "issue_types" in stats
        assert "rules" in stats
        assert stats["total_errors"] > 0
        assert len(stats["categories"]) > 0
        assert len(stats["issue_types"]) > 0
        assert len(stats["rules"]) > 0

    def test_get_corrected_text(self, languagetool):
        """Test that text correction works correctly."""
        text = "I has a cat. They is happy."
        corrected = languagetool.get_corrected_text(text, "en")
        assert isinstance(corrected, str)
        assert corrected != text
        assert "I have" in corrected
        assert "They are" in corrected

    def test_cache_handling(self, languagetool, temp_cache_dir):
        """Test that cache handling works correctly."""
        # Set up cache directory
        languagetool.CACHE_DIR = temp_cache_dir
        languagetool.CACHE_FILE = temp_cache_dir / "languagetool_cache.json"

        # Perform a check to populate cache
        text = "I has a cat."
        errors = languagetool.check_text(text, "en")
        assert len(errors) > 0

        # Check that cache file was created
        assert languagetool.CACHE_FILE.exists()

        # Load cache and verify contents
        cache = languagetool._load_cache()
        assert isinstance(cache, dict)
        assert text in cache
        assert len(cache[text]) > 0

        # Test cache validation
        assert languagetool._is_cache_valid(errors)

    def test_error_handling(self, languagetool):
        """Test that error handling works correctly."""
        # Test with empty text
        errors = languagetool.check_text("", "en")
        assert isinstance(errors, list)
        assert len(errors) == 0

        # Test with invalid language
        errors = languagetool.check_text("Hello", "invalid")
        assert isinstance(errors, list)
        assert len(errors) == 0

        # Test with invalid rules
        errors = languagetool.check_text(
            "Hello",
            "en",
            enabled_rules=["INVALID_RULE"]
        )
        assert isinstance(errors, list)
        assert len(errors) == 0 