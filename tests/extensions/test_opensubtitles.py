"""Integration tests for the OpenSubtitles extension."""

import pytest
from extensions.opensubtitles import OpenSubtitles, Subtitle
from utils.config import config

class TestOpenSubtitles:
    """Integration test suite for the OpenSubtitles extension."""

    @pytest.fixture
    def config(self):
        """Load test configuration."""
        return config

    @pytest.fixture
    def opensubtitles(self, config):
        """Create OpenSubtitles instance with API key from config."""
        api_key = config.api_keys.get("opensubtitles")
        if not api_key:
            pytest.skip("OpenSubtitles API key not configured")
        return OpenSubtitles(api_key)

    def test_initialization(self, opensubtitles):
        """Test that the OpenSubtitles instance initializes correctly."""
        assert opensubtitles is not None
        assert isinstance(opensubtitles, OpenSubtitles)

    def test_search_subtitles(self, opensubtitles):
        """Test that subtitle search works correctly."""
        # Test search with basic parameters
        subtitles = opensubtitles.search_subtitles(
            query="The Matrix",
            language="en",
            limit=5
        )
        assert isinstance(subtitles, list)
        assert len(subtitles) <= 5
        assert all(isinstance(sub, Subtitle) for sub in subtitles)
        assert all(sub.language == "en" for sub in subtitles)
        assert all(sub.movie_name is not None for sub in subtitles)
        assert all(sub.download_url is not None for sub in subtitles)
        assert all(sub.format is not None for sub in subtitles)
        assert all(sub.encoding is not None for sub in subtitles)
        assert all(sub.fps > 0 for sub in subtitles)

        # Test search with movie hash
        subtitles = opensubtitles.search_subtitles(
            query="The Matrix",
            language="en",
            movie_hash="1234567890",
            limit=5
        )
        assert isinstance(subtitles, list)
        assert len(subtitles) <= 5

        # Test search with IMDB ID
        subtitles = opensubtitles.search_subtitles(
            query="The Matrix",
            language="en",
            imdb_id="tt0133093",
            limit=5
        )
        assert isinstance(subtitles, list)
        assert len(subtitles) <= 5

    def test_get_subtitle(self, opensubtitles):
        """Test that specific subtitle retrieval works correctly."""
        # Get a subtitle ID from a search
        subtitles = opensubtitles.search_subtitles(
            query="The Matrix",
            language="en",
            limit=1
        )
        if subtitles:
            subtitle_id = subtitles[0].id
            subtitle = opensubtitles.get_subtitle(subtitle_id)
            assert isinstance(subtitle, Subtitle)
            assert subtitle.id == subtitle_id
            assert subtitle.movie_name is not None
            assert subtitle.language is not None
            assert subtitle.download_url is not None
            assert subtitle.format is not None
            assert subtitle.encoding is not None
            assert subtitle.fps > 0
            assert subtitle.content is not None

    def test_get_available_languages(self, opensubtitles):
        """Test that available languages are returned correctly."""
        languages = opensubtitles.get_available_languages()
        assert isinstance(languages, list)
        assert len(languages) > 0
        assert all(isinstance(lang, str) for lang in languages)
        assert "en" in languages
        assert "de" in languages

    def test_cache_handling(self, opensubtitles, temp_cache_dir):
        """Test that cache handling works correctly."""
        # Set up cache directory
        opensubtitles.CACHE_DIR = temp_cache_dir
        opensubtitles.CACHE_FILE = temp_cache_dir / "opensubtitles_cache.json"

        # Perform a search to populate cache
        subtitles = opensubtitles.search_subtitles(
            query="The Matrix",
            language="en",
            limit=5
        )
        assert len(subtitles) > 0

        # Check that cache file was created
        assert opensubtitles.CACHE_FILE.exists()

        # Load cache and verify contents
        cache = opensubtitles._load_cache()
        assert isinstance(cache, dict)
        assert len(cache) > 0

        # Test cache validation
        assert opensubtitles._is_cache_valid(subtitles[0])

    def test_error_handling(self, opensubtitles):
        """Test that error handling works correctly."""
        # Test invalid subtitle ID
        subtitle = opensubtitles.get_subtitle("invalid_id")
        assert subtitle is None

        # Test invalid search parameters
        subtitles = opensubtitles.search_subtitles(
            query="",
            language="invalid",
            limit=5
        )
        assert isinstance(subtitles, list)
        assert len(subtitles) == 0

        # Test invalid limit
        subtitles = opensubtitles.search_subtitles(
            query="The Matrix",
            language="en",
            limit=-1
        )
        assert isinstance(subtitles, list)
        assert len(subtitles) == 0 