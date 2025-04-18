"""Integration tests for the Gutenberg extension."""

import pytest
from pathlib import Path
import json
from extensions.gutenberg import Gutenberg, GutenbergBook

class TestGutenberg:
    """Integration test suite for the Gutenberg extension."""

    def test_initialization(self):
        """Test that the Gutenberg instance initializes correctly."""
        gutenberg = Gutenberg()
        assert gutenberg is not None
        assert isinstance(gutenberg, Gutenberg)

    def test_get_available_languages(self):
        """Test that available languages are returned correctly."""
        gutenberg = Gutenberg()
        languages = gutenberg.get_available_languages()
        assert isinstance(languages, list)
        assert len(languages) > 0
        assert all(isinstance(lang, str) for lang in languages)
        # Verify some common languages are present
        assert "English" in languages
        assert "German" in languages
        assert "French" in languages

    def test_search_books(self):
        """Test that book search works correctly."""
        gutenberg = Gutenberg()
        
        # Test search with language filter
        books = gutenberg.search_books(
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
        books = gutenberg.search_books(
            subject="history",
            min_words=1000,
            limit=5
        )
        assert isinstance(books, list)
        assert len(books) <= 5
        assert all(isinstance(book, GutenbergBook) for book in books)
        assert all("history" in book.subjects for book in books)
        assert all(book.word_count >= 1000 for book in books)

    def test_get_book_details(self):
        """Test that book details are retrieved correctly."""
        gutenberg = Gutenberg()
        
        # First get a book ID from a search
        books = gutenberg.search_books(
            language="German",
            min_words=1000,
            limit=1
        )
        assert len(books) > 0, "No books found for testing"
        
        book_id = books[0].id
        details = gutenberg.get_book_details(book_id)
        assert isinstance(details, GutenbergBook)
        assert details.id == book_id
        assert details.title is not None
        assert details.authors is not None
        assert details.language is not None
        assert details.subjects is not None
        assert details.word_count > 0
        assert details.difficulty_level is not None

    def test_get_book_text(self):
        """Test that book text is retrieved correctly."""
        gutenberg = Gutenberg()
        
        # First get a book ID from a search
        books = gutenberg.search_books(
            language="German",
            min_words=1000,
            limit=1
        )
        assert len(books) > 0, "No books found for testing"
        
        book_id = books[0].id
        text = gutenberg.get_book_text(book_id)
        assert isinstance(text, str)
        assert len(text) > 0

    def test_error_handling(self):
        """Test that error handling works correctly."""
        gutenberg = Gutenberg()
        
        # Test invalid book ID
        with pytest.raises(Exception):
            gutenberg.get_book_details("invalid_id")

        # Test invalid search parameters
        books = gutenberg.search_books(
            language="InvalidLanguage",
            min_words=1000000,
            limit=5
        )
        assert isinstance(books, list)
        assert len(books) == 0 