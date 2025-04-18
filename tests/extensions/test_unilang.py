"""Integration tests for the UniLang extension."""

import pytest
from pathlib import Path
import json
from extensions.unilang import UniLang

class TestUniLang:
    """Integration test suite for the UniLang extension."""

    def test_initialization(self):
        """Test that the UniLang instance initializes correctly."""
        unilang = UniLang()
        assert unilang is not None
        assert isinstance(unilang, UniLang)

    def test_get_language_resources(self):
        """Test that language resource retrieval works correctly."""
        unilang = UniLang()

        # Test basic resource retrieval
        resources = unilang.get_language_resources(
            language="en",
            limit=5
        )
        assert isinstance(resources, list)
        assert len(resources) <= 5
        assert all(isinstance(resource, dict) for resource in resources)
        assert all("title" in resource for resource in resources)
        assert all("description" in resource for resource in resources)
        assert all("url" in resource for resource in resources)
        assert all("category" in resource for resource in resources)

    def test_get_forum_posts(self):
        """Test that forum post retrieval works correctly."""
        unilang = UniLang()

        # Test basic forum post retrieval
        posts = unilang.get_forum_posts(
            language="en",
            limit=5
        )
        assert isinstance(posts, list)
        assert len(posts) <= 5
        assert all(isinstance(post, dict) for post in posts)
        assert all("title" in post for post in posts)
        assert all("author" in post for post in posts)
        assert all("date" in post for post in posts)
        assert all("url" in post for post in posts)

    def test_search_resources(self):
        """Test that resource search works correctly."""
        unilang = UniLang()

        # Test basic search
        results = unilang.search_resources(
            query="grammar",
            language="en",
            limit=5
        )
        assert isinstance(results, list)
        assert len(results) <= 5
        assert all(isinstance(result, dict) for result in results)
        assert all("title" in result for result in results)
        assert all("description" in result for result in results)

    def test_get_resource_categories(self):
        """Test that resource category retrieval works correctly."""
        unilang = UniLang()

        # Test getting categories
        categories = unilang.get_resource_categories("en")
        assert isinstance(categories, list)
        assert all(isinstance(category, str) for category in categories)

    def test_cache_handling(self, temp_cache_dir):
        """Test that cache handling works correctly."""
        unilang = UniLang()

        # Set up cache directory
        unilang.CACHE_DIR = temp_cache_dir
        unilang.RESOURCES_CACHE = temp_cache_dir / "resources.json"
        unilang.FORUM_CACHE = temp_cache_dir / "forum.json"

        # Perform searches to populate cache
        resources = unilang.get_language_resources("en", limit=5)
        posts = unilang.get_forum_posts("en", limit=5)

        # Verify cache files exist
        assert unilang.RESOURCES_CACHE.exists()
        assert unilang.FORUM_CACHE.exists()

        # Verify cache content
        with open(unilang.RESOURCES_CACHE, 'r', encoding='utf-8') as f:
            cached_resources = json.load(f)
            assert "en" in cached_resources
            assert len(cached_resources["en"]) <= 5

        with open(unilang.FORUM_CACHE, 'r', encoding='utf-8') as f:
            cached_posts = json.load(f)
            assert "en" in cached_posts
            assert len(cached_posts["en"]) <= 5

    def test_error_handling(self):
        """Test that error handling works correctly."""
        unilang = UniLang()

        # Test invalid language
        resources = unilang.get_language_resources(
            language="invalid",
            limit=5
        )
        assert isinstance(resources, list)
        assert len(resources) == 0

        # Test invalid duration range
        posts = unilang.get_forum_posts(
            language="invalid",
            limit=5
        )
        assert isinstance(posts, list)
        assert len(posts) == 0 