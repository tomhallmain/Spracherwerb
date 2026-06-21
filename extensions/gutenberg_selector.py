"""Module for automatically selecting appropriate books from Project Gutenberg for language learning."""

import json
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

from extensions.llm import LLM, LLMResult, LLMResponseException
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
        prompts_directory = getattr(config, "prompts_directory", "prompts")
        self.prompts_dir = Path(prompts_directory)

    @staticmethod
    def _parse_json_response(result: Optional[LLMResult], action: str) -> Dict[str, Any]:
        if result is None or result.response is None or str(result.response).strip() == "":
            raise LLMResponseException(f"Failed to {action}: empty LLM response")
        text = str(result.response).strip()
        if text.startswith("```"):
            text = text.replace("```", "").strip()
            if text.lower().startswith("json"):
                text = text[4:].strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMResponseException(f"Failed to {action}: invalid JSON in LLM response") from exc
        if not isinstance(payload, dict):
            raise LLMResponseException(f"Failed to {action}: expected JSON object")
        return payload

    def find_appropriate_books(
        self,
        target_language: str,
        proficiency_level: str,
        session_type: str,
        learning_focus: str,
        max_books: int = 3
    ) -> List[BookSelection]:
        """Find appropriate books for a language learning session."""
        search_query = self._generate_search_query(
            target_language,
            proficiency_level,
            session_type,
            learning_focus
        )
        search_results = self._perform_search(search_query)
        return self._select_books(
            search_results,
            target_language,
            proficiency_level,
            session_type,
            learning_focus,
            max_books
        )

    def _generate_search_query(
        self,
        target_language: str,
        proficiency_level: str,
        session_type: str,
        learning_focus: str
    ) -> Dict[str, Any]:
        prompt_path = self.prompts_dir / "gutenberg_search.txt"
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()

        prompt = prompt_template.format(
            target_language=target_language,
            proficiency_level=proficiency_level,
            session_type=session_type,
            learning_focus=learning_focus
        )

        result = self.llm.ask(prompt)
        return self._parse_json_response(result, "generate search query")

    def _perform_search(self, search_query: Dict[str, Any]) -> List[GutenbergBook]:
        books = []
        for term in search_query.get("search_terms", []):
            results = self.gutenberg.search_books(
                language=search_query.get("language"),
                search_term=term
            )
            books.extend(results)

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
        prompt_path = self.prompts_dir / "gutenberg_selection.txt"
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()

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

        prompt = prompt_template.format(
            target_language=target_language,
            proficiency_level=proficiency_level,
            session_type=session_type,
            learning_focus=learning_focus,
            search_results=search_results_str
        )

        result = self.llm.ask(prompt)
        selection = self._parse_json_response(result, "select books")

        selected_books = []
        for book_info in selection.get("selected_books", []):
            book = next(
                (b for b in search_results if b.id == book_info.get("id")),
                None
            )
            if book:
                selected_books.append(BookSelection(
                    book=book,
                    reason=book_info.get("reason", "")
                ))

        return selected_books[:max_books]
