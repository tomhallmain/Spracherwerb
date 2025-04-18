"""Integration tests for the GutenbergSelector extension."""

import pytest
from pathlib import Path
from extensions.gutenberg_selector import GutenbergSelector
from extensions.gutenberg import Gutenberg, GutenbergBook

class MockLLM:
    """Mock LLM class for testing."""
    
    async def generate(self, prompt: str) -> str:
        """Return a mock response based on the prompt."""
        if "German" in prompt and "beginner" in prompt:
            return "This book is suitable for beginners learning German because it has simple vocabulary and clear sentence structures."
        elif "French" in prompt and "intermediate" in prompt:
            return "This book is appropriate for intermediate French learners as it contains more complex grammar structures and vocabulary."
        elif "grammar" in prompt:
            return "This book focuses on grammar with clear explanations and examples."
        elif "vocabulary" in prompt:
            return "This book is rich in vocabulary with contextual usage examples."
        return "This book is suitable for the specified criteria."

class TestGutenbergSelector:
    """Integration test suite for the GutenbergSelector extension."""

    def test_initialization(self):
        """Test that the GutenbergSelector instance initializes correctly."""
        llm = MockLLM()
        gutenberg = Gutenberg()
        selector = GutenbergSelector(llm, gutenberg)
        assert selector is not None
        assert isinstance(selector, GutenbergSelector)
        assert selector.llm == llm
        assert selector.gutenberg == gutenberg

    async def test_find_appropriate_books(self):
        """Test that book selection works correctly for different scenarios."""
        llm = MockLLM()
        gutenberg = Gutenberg()
        selector = GutenbergSelector(llm, gutenberg)
        
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
            assert "beginner" in selection.reason.lower()
            assert "german" in selection.reason.lower()

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
            assert "intermediate" in selection.reason.lower()
            assert "french" in selection.reason.lower()

    async def test_book_selection_criteria(self):
        """Test that book selection criteria are applied correctly."""
        llm = MockLLM()
        gutenberg = Gutenberg()
        selector = GutenbergSelector(llm, gutenberg)
        
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

    async def test_error_handling(self):
        """Test that error handling works correctly."""
        llm = MockLLM()
        gutenberg = Gutenberg()
        selector = GutenbergSelector(llm, gutenberg)
        
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