"""Tests for the Gutenberg extension."""

import pytest
from pathlib import Path
import json
from extensions.gutenberg import Gutenberg, GutenbergBook

class TestGutenberg:
    """Test suite for the Gutenberg extension."""

    def test_initialization(self, mock_gutenberg):
        """Test that the Gutenberg instance initializes correctly."""
        assert mock_gutenberg is not None
        assert isinstance(mock_gutenberg, Gutenberg)

    def test_get_available_languages(self, mock_gutenberg):
        """Test that available languages are returned correctly."""
        languages = mock_gutenberg.get_available_languages()
        assert isinstance(languages, list)
        assert len(languages) > 0
        assert all(isinstance(lang, str) for lang in languages)

    def test_search_books(self, mock_gutenberg):
        """Test that book search works correctly."""
        # Test search with language filter
        books = mock_gutenberg.search_books(
            language="German",
            min_words=1000,
            limit=5
        )
        assert isinstance(books, list)
        assert len(books) <= 5
        assert all(isinstance(book, GutenbergBook) for book in books)
        assert all(book.language == "German" for book in books)
        assert all(book.word_count >= 1000 for book in books)

        # Test search with subject filter
        books = mock_gutenberg.search_books(
            subject="history",
            min_words=1000,
            limit=5
        )
        assert isinstance(books, list)
        assert len(books) <= 5
        assert all(isinstance(book, GutenbergBook) for book in books)
        assert all("history" in book.subjects for book in books)
        assert all(book.word_count >= 1000 for book in books)

    def test_get_book_details(self, mock_gutenberg):
        """Test that book details are retrieved correctly."""
        # Get a book ID from a search
        books = mock_gutenberg.search_books(
            language="German",
            min_words=1000,
            limit=1
        )
        if books:
            book_id = books[0].id
            details = mock_gutenberg.get_book_details(book_id)
            assert isinstance(details, GutenbergBook)
            assert details.id == book_id
            assert details.title is not None
            assert details.authors is not None
            assert details.language is not None
            assert details.subjects is not None
            assert details.word_count > 0
            assert details.difficulty_level is not None

    def test_get_book_text(self, mock_gutenberg):
        """Test that book text is retrieved correctly."""
        # Get a book ID from a search
        books = mock_gutenberg.search_books(
            language="German",
            min_words=1000,
            limit=1
        )
        if books:
            book_id = books[0].id
            text = mock_gutenberg.get_book_text(book_id)
            assert isinstance(text, str)
            assert len(text) > 0

    def test_cache_handling(self, mock_gutenberg, temp_cache_dir):
        """Test that cache handling works correctly."""
        # Set up cache directory
        mock_gutenberg.cache_dir = temp_cache_dir
        mock_gutenberg.cache_file = temp_cache_dir / "gutenberg_cache.json"

        # Perform a search to populate cache
        books = mock_gutenberg.search_books(
            language="German",
            min_words=1000,
            limit=5
        )
        assert len(books) > 0

        # Check that cache file was created
        assert mock_gutenberg.cache_file.exists()

        # Load cache and verify contents
        cache = mock_gutenberg._load_cache()
        assert isinstance(cache, dict)
        assert "books" in cache
        assert len(cache["books"]) > 0

        # Test cache validation
        assert mock_gutenberg._is_cache_valid()

    def test_error_handling(self, mock_gutenberg):
        """Test that error handling works correctly."""
        # Test invalid book ID
        with pytest.raises(Exception):
            mock_gutenberg.get_book_details("invalid_id")

        # Test invalid search parameters
        books = mock_gutenberg.search_books(
            language="InvalidLanguage",
            min_words=1000000,
            limit=5
        )
        assert isinstance(books, list)
        assert len(books) == 0 