"""Tests for the GutenbergSelector extension."""

import pytest
from pathlib import Path
import json
from extensions.gutenberg_selector import GutenbergSelector
from extensions.gutenberg import Gutenberg, GutenbergBook
from extensions.llm import LLM

class TestGutenbergSelector:
    """Test suite for the GutenbergSelector extension."""

    def test_initialization(self, mock_llm, mock_gutenberg):
        """Test that the GutenbergSelector instance initializes correctly."""
        selector = GutenbergSelector(mock_llm, mock_gutenberg)
        assert selector is not None
        assert isinstance(selector, GutenbergSelector)
        assert selector.llm == mock_llm
        assert selector.gutenberg == mock_gutenberg

    async def test_find_appropriate_books(self, mock_llm, mock_gutenberg):
        """Test that book selection works correctly for different scenarios."""
        selector = GutenbergSelector(mock_llm, mock_gutenberg)
        
        # Test case 1: Beginner German reading comprehension
        selected_books = await selector.find_appropriate_books(
            target_language="German",
            proficiency_level="beginner",
            session_type="reading_comprehension",
            learning_focus="vocabulary",
            max_books=3
        )
        assert isinstance(selected_books, list)
        assert len(selected_books) <= 3
        for selection in selected_books:
            assert isinstance(selection.book, GutenbergBook)
            assert selection.book.language == "German"
            assert selection.book.difficulty_level == "beginner"
            assert isinstance(selection.reason, str)
            assert len(selection.reason) > 0

        # Test case 2: Intermediate French grammar practice
        selected_books = await selector.find_appropriate_books(
            target_language="French",
            proficiency_level="intermediate",
            session_type="grammar_practice",
            learning_focus="grammar",
            max_books=2
        )
        assert isinstance(selected_books, list)
        assert len(selected_books) <= 2
        for selection in selected_books:
            assert isinstance(selection.book, GutenbergBook)
            assert selection.book.language == "French"
            assert selection.book.difficulty_level == "intermediate"
            assert isinstance(selection.reason, str)
            assert len(selection.reason) > 0

        # Test case 3: Advanced Spanish cultural context
        selected_books = await selector.find_appropriate_books(
            target_language="Spanish",
            proficiency_level="advanced",
            session_type="cultural_context",
            learning_focus="cultural",
            max_books=1
        )
        assert isinstance(selected_books, list)
        assert len(selected_books) <= 1
        for selection in selected_books:
            assert isinstance(selection.book, GutenbergBook)
            assert selection.book.language == "Spanish"
            assert selection.book.difficulty_level == "advanced"
            assert isinstance(selection.reason, str)
            assert len(selection.reason) > 0

    async def test_book_selection_criteria(self, mock_llm, mock_gutenberg):
        """Test that book selection criteria are applied correctly."""
        selector = GutenbergSelector(mock_llm, mock_gutenberg)
        
        # Test word count criteria
        selected_books = await selector.find_appropriate_books(
            target_language="German",
            proficiency_level="beginner",
            session_type="reading_comprehension",
            learning_focus="vocabulary",
            max_books=3,
            min_word_count=1000,
            max_word_count=5000
        )
        for selection in selected_books:
            assert 1000 <= selection.book.word_count <= 5000

        # Test subject criteria
        selected_books = await selector.find_appropriate_books(
            target_language="French",
            proficiency_level="intermediate",
            session_type="grammar_practice",
            learning_focus="grammar",
            max_books=2,
            subjects=["fiction", "literature"]
        )
        for selection in selected_books:
            assert any(subject in selection.book.subjects for subject in ["fiction", "literature"])

    async def test_selection_reasoning(self, mock_llm, mock_gutenberg):
        """Test that selection reasoning is provided and relevant."""
        selector = GutenbergSelector(mock_llm, mock_gutenberg)
        
        selected_books = await selector.find_appropriate_books(
            target_language="German",
            proficiency_level="beginner",
            session_type="reading_comprehension",
            learning_focus="vocabulary",
            max_books=1
        )
        
        if selected_books:
            reason = selected_books[0].reason
            assert isinstance(reason, str)
            assert len(reason) > 0
            # Check that the reason mentions relevant criteria
            assert "beginner" in reason.lower()
            assert "vocabulary" in reason.lower()
            assert "reading" in reason.lower()

    async def test_error_handling(self, mock_llm, mock_gutenberg):
        """Test that error handling works correctly."""
        selector = GutenbergSelector(mock_llm, mock_gutenberg)
        
        # Test invalid language
        with pytest.raises(Exception):
            await selector.find_appropriate_books(
                target_language="InvalidLanguage",
                proficiency_level="beginner",
                session_type="reading_comprehension",
                learning_focus="vocabulary",
                max_books=1
            )

        # Test invalid proficiency level
        with pytest.raises(Exception):
            await selector.find_appropriate_books(
                target_language="German",
                proficiency_level="invalid",
                session_type="reading_comprehension",
                learning_focus="vocabulary",
                max_books=1
            )

        # Test invalid session type
        with pytest.raises(Exception):
            await selector.find_appropriate_books(
                target_language="German",
                proficiency_level="beginner",
                session_type="invalid",
                learning_focus="vocabulary",
                max_books=1
            )

        # Test invalid learning focus
        with pytest.raises(Exception):
            await selector.find_appropriate_books(
                target_language="German",
                proficiency_level="beginner",
                session_type="reading_comprehension",
                learning_focus="invalid",
                max_books=1
            )

    async def test_no_books_found(self, mock_llm, mock_gutenberg):
        """Test handling of cases where no books are found."""
        selector = GutenbergSelector(mock_llm, mock_gutenberg)
        
        # Test with impossible criteria
        selected_books = await selector.find_appropriate_books(
            target_language="German",
            proficiency_level="beginner",
            session_type="reading_comprehension",
            learning_focus="vocabulary",
            max_books=3,
            min_word_count=1000000  # Impossible word count
        )
        assert isinstance(selected_books, list)
        assert len(selected_books) == 0 