"""Tests for the Wikimedia Commons extension."""

import pytest
from pathlib import Path
import json
from extensions.wikimedia_commons import WikimediaCommons, MediaItem

class TestWikimediaCommons:
    """Test suite for the Wikimedia Commons extension."""

    def test_initialization(self, mock_wikimedia_commons):
        """Test that the Wikimedia Commons instance initializes correctly."""
        assert mock_wikimedia_commons is not None
        assert isinstance(mock_wikimedia_commons, WikimediaCommons)

    def test_search_media(self, mock_wikimedia_commons):
        """Test that media search works correctly."""
        # Test search with basic parameters
        items = mock_wikimedia_commons.search_media(
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
        items = mock_wikimedia_commons.search_media(
            query="cat",
            language="en",
            limit=5
        )
        assert isinstance(items, list)
        assert len(items) <= 5
        assert all("en" in item.languages for item in items)

        # Test search with media type filter
        items = mock_wikimedia_commons.search_media(
            query="cat",
            media_type="image",
            limit=5
        )
        assert isinstance(items, list)
        assert len(items) <= 5
        assert all(item.mime_type.startswith("image/") for item in items)

    def test_get_media_by_category(self, mock_wikimedia_commons):
        """Test that category-based media retrieval works correctly."""
        # Test basic category retrieval
        items = mock_wikimedia_commons.get_media_by_category(
            category="Cats",
            limit=5
        )
        assert isinstance(items, list)
        assert len(items) <= 5
        assert all(isinstance(item, MediaItem) for item in items)
        assert all("Cats" in item.categories for item in items)

        # Test category retrieval with language filter
        items = mock_wikimedia_commons.get_media_by_category(
            category="Cats",
            language="en",
            limit=5
        )
        assert isinstance(items, list)
        assert len(items) <= 5
        assert all("en" in item.languages for item in items)

        # Test category retrieval with media type filter
        items = mock_wikimedia_commons.get_media_by_category(
            category="Cats",
            media_type="image",
            limit=5
        )
        assert isinstance(items, list)
        assert len(items) <= 5
        assert all(item.mime_type.startswith("image/") for item in items)

    def test_download_media(self, mock_wikimedia_commons, temp_cache_dir):
        """Test that media download works correctly."""
        # Get a media item to download
        items = mock_wikimedia_commons.search_media(
            query="cat",
            limit=1
        )
        if items:
            item = items[0]
            output_path = mock_wikimedia_commons.download_media(item, temp_cache_dir)
            assert output_path is not None
            assert output_path.exists()
            assert output_path.parent == temp_cache_dir

    def test_get_media_statistics(self, mock_wikimedia_commons):
        """Test that media statistics retrieval works correctly."""
        stats = mock_wikimedia_commons.get_media_statistics("cat")
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

    def test_cache_handling(self, mock_wikimedia_commons, temp_cache_dir):
        """Test that cache handling works correctly."""
        # Set up cache directory
        mock_wikimedia_commons.CACHE_DIR = temp_cache_dir
        mock_wikimedia_commons.CACHE_FILE = temp_cache_dir / "media.json"

        # Perform a search to populate cache
        items = mock_wikimedia_commons.search_media(
            query="cat",
            limit=5
        )
        assert len(items) > 0

        # Check that cache file was created
        assert mock_wikimedia_commons.CACHE_FILE.exists()

        # Load cache and verify contents
        cache = mock_wikimedia_commons._load_cache()
        assert isinstance(cache, dict)
        assert len(cache) > 0

        # Test cache validation
        assert mock_wikimedia_commons._is_cache_valid(items)

    def test_error_handling(self, mock_wikimedia_commons):
        """Test that error handling works correctly."""
        # Test invalid query
        items = mock_wikimedia_commons.search_media(
            query="",
            limit=5
        )
        assert isinstance(items, list)
        assert len(items) == 0

        # Test invalid language
        items = mock_wikimedia_commons.search_media(
            query="cat",
            language="invalid",
            limit=5
        )
        assert isinstance(items, list)
        assert len(items) == 0

        # Test invalid media type
        items = mock_wikimedia_commons.search_media(
            query="cat",
            media_type="invalid",
            limit=5
        )
        assert isinstance(items, list)
        assert len(items) == 0

        # Test invalid category
        items = mock_wikimedia_commons.get_media_by_category(
            category="InvalidCategory",
            limit=5
        )
        assert isinstance(items, list)
        assert len(items) == 0 