"""Integration tests for the Wikimedia Commons extension."""

import pytest
from pathlib import Path
import json
from extensions.wikimedia_commons import WikimediaCommons, MediaItem

class TestWikimediaCommons:
    """Integration test suite for the Wikimedia Commons extension."""

    def test_initialization(self):
        """Test that the Wikimedia Commons instance initializes correctly."""
        wikimedia = WikimediaCommons()
        assert wikimedia is not None
        assert isinstance(wikimedia, WikimediaCommons)

    def test_search_media(self):
        """Test that media search works correctly."""
        wikimedia = WikimediaCommons()
        
        # Test search with basic parameters
        items = wikimedia.search_media(
            query="cat",
            limit=5
        )
        assert isinstance(items, list)
        assert len(items) <= 5
        assert all(isinstance(item, MediaItem) for item in items)
        assert all(item.title is not None for item in items)
        assert all(item.url is not None for item in items)
        assert all(item.mime_type is not None for item in items)
        assert all(isinstance(item.categories, list) for item in items)
        assert all(isinstance(item.languages, list) for item in items)

        # Test search with language filter
        items = wikimedia.search_media(
            query="cat",
            language="en",
            limit=5
        )
        assert isinstance(items, list)
        assert len(items) <= 5
        assert all("en" in item.languages for item in items)

        # Test search with media type filter
        items = wikimedia.search_media(
            query="cat",
            media_type="image",
            limit=5
        )
        assert isinstance(items, list)
        assert len(items) <= 5
        assert all(item.mime_type.startswith("image/") for item in items)

    def test_get_media_by_category(self):
        """Test that category-based media retrieval works correctly."""
        wikimedia = WikimediaCommons()
        
        # Test basic category retrieval
        items = wikimedia.get_media_by_category(
            category="Cats",
            limit=5
        )
        assert isinstance(items, list)
        assert len(items) <= 5
        assert all(isinstance(item, MediaItem) for item in items)
        assert all("Cats" in item.categories for item in items)

        # Test category retrieval with language filter
        items = wikimedia.get_media_by_category(
            category="Cats",
            language="en",
            limit=5
        )
        assert isinstance(items, list)
        assert len(items) <= 5
        assert all("en" in item.languages for item in items)

        # Test category retrieval with media type filter
        items = wikimedia.get_media_by_category(
            category="Cats",
            media_type="image",
            limit=5
        )
        assert isinstance(items, list)
        assert len(items) <= 5
        assert all(item.mime_type.startswith("image/") for item in items)

    def test_download_media(self, temp_cache_dir):
        """Test that media download works correctly."""
        wikimedia = WikimediaCommons()
        
        # Get a media item to download
        items = wikimedia.search_media(
            query="cat",
            limit=1
        )
        if items:
            item = items[0]
            output_path = wikimedia.download_media(item, temp_cache_dir)
            assert output_path is not None
            assert output_path.exists()
            assert output_path.parent == temp_cache_dir

    def test_get_media_statistics(self):
        """Test that media statistics retrieval works correctly."""
        wikimedia = WikimediaCommons()
        
        stats = wikimedia.get_media_statistics("cat")
        assert isinstance(stats, dict)
        assert "total_items" in stats
        assert "media_types" in stats
        assert "languages" in stats
        assert "licenses" in stats
        assert "categories" in stats
        assert isinstance(stats["total_items"], int)
        assert isinstance(stats["media_types"], dict)
        assert isinstance(stats["languages"], dict)
        assert isinstance(stats["licenses"], dict)
        assert isinstance(stats["categories"], dict)

    def test_cache_handling(self, temp_cache_dir):
        """Test that cache handling works correctly."""
        wikimedia = WikimediaCommons()
        
        # Set up cache directory
        wikimedia.CACHE_DIR = temp_cache_dir
        wikimedia.CACHE_FILE = temp_cache_dir / "media.json"

        # Perform a search to populate cache
        items = wikimedia.search_media(
            query="cat",
            limit=5
        )
        assert len(items) > 0

        # Check that cache file was created
        assert wikimedia.CACHE_FILE.exists()

        # Load cache and verify contents
        cache = wikimedia._load_cache()
        assert isinstance(cache, dict)
        assert len(cache) > 0

        # Test cache validation
        assert wikimedia._is_cache_valid(items)

    def test_error_handling(self):
        """Test that error handling works correctly."""
        wikimedia = WikimediaCommons()
        
        # Test invalid query
        items = wikimedia.search_media(
            query="",
            limit=5
        )
        assert isinstance(items, list)
        assert len(items) == 0

        # Test invalid language
        items = wikimedia.search_media(
            query="cat",
            language="invalid",
            limit=5
        )
        assert isinstance(items, list)
        assert len(items) == 0

        # Test invalid media type
        items = wikimedia.search_media(
            query="cat",
            media_type="invalid",
            limit=5
        )
        assert isinstance(items, list)
        assert len(items) == 0

        # Test invalid category
        items = wikimedia.get_media_by_category(
            category="InvalidCategory",
            limit=5
        )
        assert isinstance(items, list)
        assert len(items) == 0 