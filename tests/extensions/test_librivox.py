"""Integration tests for the LibriVox extension."""

import pytest
from pathlib import Path
import json
from extensions.librivox import LibriVox, Audiobook, Chapter

class TestLibriVox:
    """Integration test suite for the LibriVox extension."""

    def test_initialization(self):
        """Test that the LibriVox instance initializes correctly."""
        librivox = LibriVox()
        assert librivox is not None
        assert isinstance(librivox, LibriVox)

    def test_search_audiobooks(self):
        """Test that audiobook search works correctly."""
        librivox = LibriVox()
        
        # Test search with language filter
        books = librivox.search_audiobooks(
            language="German",
            limit=5
        )
        assert isinstance(books, list)
        assert len(books) <= 5
        assert all(isinstance(book, Audiobook) for book in books)
        assert all(book.language == "German" for book in books)
        assert all(book.title is not None for book in books)
        assert all(book.author is not None for book in books)
        assert all(book.chapters is not None for book in books)

        # Test search with author filter
        books = librivox.search_audiobooks(
            author="Goethe",
            limit=5
        )
        assert isinstance(books, list)
        assert len(books) <= 5
        assert all(isinstance(book, Audiobook) for book in books)
        assert all("Goethe" in book.author for book in books)

    def test_get_audiobook(self):
        """Test that specific audiobook retrieval works correctly."""
        librivox = LibriVox()
        
        # Get a book ID from a search
        books = librivox.search_audiobooks(
            language="German",
            limit=1
        )
        if books:
            book_id = books[0].id
            book = librivox.get_audiobook(book_id)
            assert isinstance(book, Audiobook)
            assert book.id == book_id
            assert book.title is not None
            assert book.author is not None
            assert book.language is not None
            assert book.total_time is not None
            assert book.description is not None
            assert isinstance(book.chapters, list)
            assert len(book.chapters) > 0
            assert all(isinstance(chapter, Chapter) for chapter in book.chapters)

    def test_get_available_languages(self):
        """Test that available languages are returned correctly."""
        librivox = LibriVox()
        
        languages = librivox.get_available_languages()
        assert isinstance(languages, list)
        assert len(languages) > 0
        assert all(isinstance(lang, str) for lang in languages)
        assert "German" in languages
        assert "English" in languages

    def test_get_popular_audiobooks(self):
        """Test that popular audiobooks are retrieved correctly."""
        librivox = LibriVox()
        
        # Test without language filter
        books = librivox.get_popular_audiobooks(limit=5)
        assert isinstance(books, list)
        assert len(books) <= 5
        assert all(isinstance(book, Audiobook) for book in books)

        # Test with language filter
        books = librivox.get_popular_audiobooks(
            language="German",
            limit=5
        )
        assert isinstance(books, list)
        assert len(books) <= 5
        assert all(isinstance(book, Audiobook) for book in books)
        assert all(book.language == "German" for book in books)

    def test_chapter_attributes(self):
        """Test that chapter attributes are correctly populated."""
        librivox = LibriVox()
        
        # Get a book with chapters
        books = librivox.search_audiobooks(
            language="German",
            limit=1
        )
        if books:
            book = books[0]
            chapter = book.chapters[0]
            assert isinstance(chapter, Chapter)
            assert chapter.id is not None
            assert chapter.title is not None
            assert chapter.duration is not None
            assert chapter.audio_url is not None
            assert chapter.text_url is not None

    def test_cache_handling(self, temp_cache_dir):
        """Test that cache handling works correctly."""
        librivox = LibriVox()
        
        # Set up cache directory
        librivox.CACHE_DIR = temp_cache_dir
        librivox.CACHE_FILE = temp_cache_dir / "librivox_cache.json"

        # Perform a search to populate cache
        books = librivox.search_audiobooks(
            language="German",
            limit=5
        )
        assert len(books) > 0

        # Check that cache file was created
        assert librivox.CACHE_FILE.exists()

        # Load cache and verify contents
        cache = librivox._load_cache()
        assert isinstance(cache, dict)
        assert len(cache) > 0

        # Test cache validation
        assert librivox._is_cache_valid(books[0])

    def test_error_handling(self):
        """Test that error handling works correctly."""
        librivox = LibriVox()
        
        # Test invalid book ID
        book = librivox.get_audiobook(-1)
        assert book is None

        # Test invalid search parameters
        books = librivox.search_audiobooks(
            language="InvalidLanguage",
            limit=5
        )
        assert isinstance(books, list)
        assert len(books) == 0

        # Test invalid limit
        books = librivox.search_audiobooks(limit=-1)
        assert isinstance(books, list)
        assert len(books) == 0 