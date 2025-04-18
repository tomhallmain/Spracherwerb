"""Module for automatically selecting appropriate books from Project Gutenberg for language learning."""

import json
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

from extensions.llm import LLM, LLMResult
from extensions.gutenberg import Gutenberg, GutenbergBook
from utils.config import config


@dataclass
class BookSelection:
    """Represents a selected book and the reason for its selection."""
    book: GutenbergBook
    reason: str


class GutenbergSelector:
    """Handles automatic selection of appropriate books from Project Gutenberg."""
    
    def __init__(self, llm: LLM, gutenberg: Gutenberg):
        """Initialize the selector with LLM and Gutenberg instances."""
        self.llm = llm
        self.gutenberg = gutenberg
        self.prompts_dir = Path(config.get("prompts_directory", "prompts"))
        
    def find_appropriate_books(
        self,
        target_language: str,
        proficiency_level: str,
        session_type: str,
        learning_focus: str,
        max_books: int = 3
    ) -> List[BookSelection]:
        """Find appropriate books for a language learning session."""
        # Generate search query using LLM
        search_query = self._generate_search_query(
            target_language,
            proficiency_level,
            session_type,
            learning_focus
        )
        
        # Perform search
        search_results = self._perform_search(search_query)
        
        # Select appropriate books
        selected_books = self._select_books(
            search_results,
            target_language,
            proficiency_level,
            session_type,
            learning_focus,
            max_books
        )
        
        return selected_books
    
    def _generate_search_query(
        self,
        target_language: str,
        proficiency_level: str,
        session_type: str,
        learning_focus: str
    ) -> Dict[str, Any]:
        """Generate a search query using the LLM."""
        # Load the search prompt template
        prompt_path = self.prompts_dir / "gutenberg_search.txt"
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
        
        # Format the prompt
        prompt = prompt_template.format(
            target_language=target_language,
            proficiency_level=proficiency_level,
            session_type=session_type,
            learning_focus=learning_focus
        )
        
        # Get search query from LLM
        result: LLMResult = self.llm.ask(prompt, json_key="search_query")
        if not result or not result.content:
            raise Exception("Failed to generate search query")
            
        return json.loads(result.content)
    
    def _perform_search(self, search_query: Dict[str, Any]) -> List[GutenbergBook]:
        """Perform the search using the Gutenberg API."""
        books = []
        for term in search_query["search_terms"]:
            results = self.gutenberg.search_books(
                language=search_query["language"],
                search_term=term
            )
            books.extend(results)
        
        # Remove duplicates
        unique_books = {book.id: book for book in books}.values()
        return list(unique_books)
    
    def _select_books(
        self,
        search_results: List[GutenbergBook],
        target_language: str,
        proficiency_level: str,
        session_type: str,
        learning_focus: str,
        max_books: int
    ) -> List[BookSelection]:
        """Select appropriate books from search results using the LLM."""
        # Load the selection prompt template
        prompt_path = self.prompts_dir / "gutenberg_selection.txt"
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
        
        # Format the search results for the prompt
        search_results_str = json.dumps([
            {
                "id": book.id,
                "title": book.title,
                "authors": book.authors,
                "subjects": book.subjects,
                "word_count": book.word_count
            }
            for book in search_results
        ], indent=2)
        
        # Format the prompt
        prompt = prompt_template.format(
            target_language=target_language,
            proficiency_level=proficiency_level,
            session_type=session_type,
            learning_focus=learning_focus,
            search_results=search_results_str
        )
        
        # Get book selection from LLM
        result: LLMResult = self.llm.ask(prompt, json_key="selection")
        if not result or not result.content:
            raise Exception("Failed to select books")
            
        selection = json.loads(result.content)
        
        # Map selected book IDs to actual GutenbergBook objects
        selected_books = []
        for book_info in selection["selected_books"]:
            book = next(
                (b for b in search_results if b.id == book_info["id"]),
                None
            )
            if book:
                selected_books.append(BookSelection(
                    book=book,
                    reason=book_info["reason"]
                ))
        
        return selected_books[:max_books]
