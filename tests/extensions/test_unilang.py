"""Integration tests for the UniLang extension."""

import pytest
from pathlib import Path
import json
from extensions.unilang import UniLang, LanguageResource, ForumPost

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
        assert all(isinstance(res, LanguageResource) for res in resources)
        assert all(res.language == "en" for res in resources)
        assert all(res.title is not None for res in resources)
        assert all(res.description is not None for res in resources)
        assert all(res.url is not None for res in resources)
        assert all(isinstance(res.tags, list) for res in resources)

        # Test resource filtering by type
        resources = unilang.get_language_resources(
            language="en",
            resource_type="grammar",
            limit=5
        )
        assert isinstance(resources, list)
        assert len(resources) <= 5
        assert all(res.resource_type == "grammar" for res in resources)

        # Test resource filtering by difficulty
        resources = unilang.get_language_resources(
            language="en",
            difficulty="beginner",
            limit=5
        )
        assert isinstance(resources, list)
        assert len(resources) <= 5
        assert all(res.difficulty == "beginner" for res in resources)

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
        assert all(isinstance(post, ForumPost) for post in posts)
        assert all(post.language == "en" for post in posts)
        assert all(post.title is not None for post in posts)
        assert all(post.content is not None for post in posts)
        assert all(post.author is not None for post in posts)
        assert all(post.date is not None for post in posts)
        assert all(isinstance(post.tags, list) for post in posts)

        # Test forum post filtering by tag
        posts = unilang.get_forum_posts(
            language="en",
            tag="grammar",
            limit=5
        )
        assert isinstance(posts, list)
        assert len(posts) <= 5
        assert all("grammar" in post.tags for post in posts)

    def test_search_resources(self):
        """Test that resource search works correctly."""
        unilang = UniLang()
        
        # Test basic resource search
        resources = unilang.search_resources(
            query="grammar",
            language="en"
        )
        assert isinstance(resources, list)
        assert all(isinstance(res, LanguageResource) for res in resources)
        assert all(
            "grammar" in res.title.lower() or
            "grammar" in res.description.lower() or
            any("grammar" in tag.lower() for tag in res.tags)
            for res in resources
        )

        # Test search without language filter
        resources = unilang.search_resources(
            query="grammar"
        )
        assert isinstance(resources, list)
        assert all(isinstance(res, LanguageResource) for res in resources)

    def test_get_resource_categories(self):
        """Test that resource category retrieval works correctly."""
        unilang = UniLang()
        
        categories = unilang.get_resource_categories("en")
        assert isinstance(categories, dict)
        assert all(isinstance(key, str) for key in categories.keys())
        assert all(isinstance(value, int) for value in categories.values())
        assert all(value > 0 for value in categories.values())

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
        assert len(resources) > 0
        assert len(posts) > 0

        # Check that cache files were created
        assert unilang.RESOURCES_CACHE.exists()
        assert unilang.FORUM_CACHE.exists()

        # Load cache and verify contents
        resources_cache = unilang._load_cache()
        assert isinstance(resources_cache, dict)
        assert len(resources_cache) > 0

        # Test cache validation
        assert unilang._is_cache_valid(resources)

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

        # Test invalid resource type
        resources = unilang.get_language_resources(
            language="en",
            resource_type="invalid",
            limit=5
        )
        assert isinstance(resources, list)
        assert len(resources) == 0

        # Test invalid difficulty
        resources = unilang.get_language_resources(
            language="en",
            difficulty="invalid",
            limit=5
        )
        assert isinstance(resources, list)
        assert len(resources) == 0

        # Test invalid tag
        posts = unilang.get_forum_posts(
            language="en",
            tag="invalid",
            limit=5
        )
        assert isinstance(posts, list)
        assert len(posts) == 0 