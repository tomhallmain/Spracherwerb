"""Tests for the LibriVox extension."""

import pytest
from pathlib import Path
import json
from extensions.librivox import LibriVox, Audiobook, Chapter

class TestLibriVox:
    """Test suite for the LibriVox extension."""

    def test_initialization(self, mock_librivox):
        """Test that the LibriVox instance initializes correctly."""
        assert mock_librivox is not None
        assert isinstance(mock_librivox, LibriVox)

    def test_search_audiobooks(self, mock_librivox):
        """Test that audiobook search works correctly."""
        # Test search with language filter
        books = mock_librivox.search_audiobooks(
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
        books = mock_librivox.search_audiobooks(
            author="Goethe",
            limit=5
        )
        assert isinstance(books, list)
        assert len(books) <= 5
        assert all(isinstance(book, Audiobook) for book in books)
        assert all("Goethe" in book.author for book in books)

    def test_get_audiobook(self, mock_librivox):
        """Test that specific audiobook retrieval works correctly."""
        # Get a book ID from a search
        books = mock_librivox.search_audiobooks(
            language="German",
            limit=1
        )
        if books:
            book_id = books[0].id
            book = mock_librivox.get_audiobook(book_id)
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

    def test_get_available_languages(self, mock_librivox):
        """Test that available languages are returned correctly."""
        languages = mock_librivox.get_available_languages()
        assert isinstance(languages, list)
        assert len(languages) > 0
        assert all(isinstance(lang, str) for lang in languages)
        assert "German" in languages
        assert "English" in languages

    def test_get_popular_audiobooks(self, mock_librivox):
        """Test that popular audiobooks are retrieved correctly."""
        # Test without language filter
        books = mock_librivox.get_popular_audiobooks(limit=5)
        assert isinstance(books, list)
        assert len(books) <= 5
        assert all(isinstance(book, Audiobook) for book in books)

        # Test with language filter
        books = mock_librivox.get_popular_audiobooks(
            language="German",
            limit=5
        )
        assert isinstance(books, list)
        assert len(books) <= 5
        assert all(isinstance(book, Audiobook) for book in books)
        assert all(book.language == "German" for book in books)

    def test_chapter_attributes(self, mock_librivox):
        """Test that chapter attributes are correctly populated."""
        # Get a book with chapters
        books = mock_librivox.search_audiobooks(
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

    def test_cache_handling(self, mock_librivox, temp_cache_dir):
        """Test that cache handling works correctly."""
        # Set up cache directory
        mock_librivox.CACHE_DIR = temp_cache_dir
        mock_librivox.CACHE_FILE = temp_cache_dir / "librivox_cache.json"

        # Perform a search to populate cache
        books = mock_librivox.search_audiobooks(
            language="German",
            limit=5
        )
        assert len(books) > 0

        # Check that cache file was created
        assert mock_librivox.CACHE_FILE.exists()

        # Load cache and verify contents
        cache = mock_librivox._load_cache()
        assert isinstance(cache, dict)
        assert len(cache) > 0

        # Test cache validation
        assert mock_librivox._is_cache_valid(books[0])

    def test_error_handling(self, mock_librivox):
        """Test that error handling works correctly."""
        # Test invalid book ID
        book = mock_librivox.get_audiobook(-1)
        assert book is None

        # Test invalid search parameters
        books = mock_librivox.search_audiobooks(
            language="InvalidLanguage",
            limit=5
        )
        assert isinstance(books, list)
        assert len(books) == 0

        # Test invalid limit
        books = mock_librivox.search_audiobooks(limit=-1)
        assert isinstance(books, list)
        assert len(books) == 0 