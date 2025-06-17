"""Project Gutenberg integration for the Spracherwerb application."""

import requests
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import json
import time

from utils.logging_setup import get_logger

logger = get_logger(__name__)

@dataclass
class GutenbergBook:
    """Represents a book from Project Gutenberg."""
    id: int
    title: str
    language: str
    authors: List[str]
    subjects: List[str]
    download_url: str
    text_url: str
    word_count: Optional[int] = None
    difficulty_level: Optional[int] = None
    last_accessed: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert the book to a dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "language": self.language,
            "authors": self.authors,
            "subjects": self.subjects,
            "download_url": self.download_url,
            "text_url": self.text_url,
            "word_count": self.word_count,
            "difficulty_level": self.difficulty_level,
            "last_accessed": self.last_accessed
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GutenbergBook':
        """Create a book from a dictionary."""
        return cls(
            id=data["id"],
            title=data["title"],
            language=data["language"],
            authors=data["authors"],
            subjects=data["subjects"],
            download_url=data["download_url"],
            text_url=data["text_url"],
            word_count=data.get("word_count"),
            difficulty_level=data.get("difficulty_level"),
            last_accessed=data.get("last_accessed")
        )


class Gutenberg:
    """Handles interactions with Project Gutenberg's API."""
    
    BASE_URL = "https://gutendex.com/books"
    CACHE_DIR = Path("cache/gutenberg")
    CACHE_FILE = CACHE_DIR / "books.json"
    CACHE_DURATION = 86400  # 24 hours in seconds
    
    def __init__(self):
        self.books: Dict[int, GutenbergBook] = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load cached book data from disk."""
        try:
            if self.CACHE_FILE.exists():
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.books = {
                        int(book_id): GutenbergBook.from_dict(book_data)
                        for book_id, book_data in data.items()
                    }
        except Exception as e:
            logger.error(f"Error loading Gutenberg cache: {e}")
            self.books = {}
    
    def _save_cache(self):
        """Save book data to cache file."""
        try:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(
                    {str(book_id): book.to_dict() for book_id, book in self.books.items()},
                    f,
                    ensure_ascii=False,
                    indent=2
                )
        except Exception as e:
            logger.error(f"Error saving Gutenberg cache: {e}")
    
    def _is_cache_valid(self, book: GutenbergBook) -> bool:
        """Check if cached book data is still valid."""
        if not book.last_accessed:
            return False
        return (time.time() - book.last_accessed) < self.CACHE_DURATION
    
    def search_books(self, 
                    language: str,
                    search_term: Optional[str] = None,
                    author: Optional[str] = None,
                    subject: Optional[str] = None,
                    min_word_count: Optional[int] = None,
                    max_word_count: Optional[int] = None) -> List[GutenbergBook]:
        """Search for books matching the given criteria."""
        params = {
            "languages": language,
            "search": search_term,
            "author": author,
            "topic": subject
        }
        
        try:
            response = requests.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for book_data in data.get("results", []):
                book = self._parse_book_data(book_data)
                
                # Apply word count filters if specified
                if min_word_count and book.word_count and book.word_count < min_word_count:
                    continue
                if max_word_count and book.word_count and book.word_count > max_word_count:
                    continue
                
                results.append(book)
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching Gutenberg books: {e}")
            return []
    
    def get_book(self, book_id: int) -> Optional[GutenbergBook]:
        """Get a specific book by ID."""
        # Check cache first
        if book_id in self.books and self._is_cache_valid(self.books[book_id]):
            return self.books[book_id]
        
        try:
            response = requests.get(f"{self.BASE_URL}/{book_id}")
            response.raise_for_status()
            book_data = response.json()
            
            book = self._parse_book_data(book_data)
            self.books[book_id] = book
            self._save_cache()
            
            return book
            
        except Exception as e:
            logger.error(f"Error getting Gutenberg book {book_id}: {e}")
            return None
    
    def _parse_book_data(self, data: Dict[str, Any]) -> GutenbergBook:
        """Parse raw book data into a GutenbergBook object."""
        # Get the text URL (prefer plain text format)
        text_url = None
        for format_data in data.get("formats", {}).values():
            if "text/plain" in format_data:
                text_url = format_data
                break
        
        # Get the download URL (prefer plain text format)
        download_url = None
        for format_data in data.get("formats", {}).values():
            if "text/plain" in format_data:
                download_url = format_data
                break
        
        # Estimate word count from the text URL if available
        word_count = None
        if text_url:
            try:
                response = requests.get(text_url)
                response.raise_for_status()
                word_count = len(response.text.split())
            except:
                pass
        
        # Estimate difficulty level based on word count
        difficulty_level = None
        if word_count:
            if word_count < 10000:
                difficulty_level = 1  # Beginner
            elif word_count < 30000:
                difficulty_level = 2  # Intermediate
            else:
                difficulty_level = 3  # Advanced
        
        return GutenbergBook(
            id=data["id"],
            title=data["title"],
            language=data.get("languages", ["en"])[0],  # Default to English if not specified
            authors=[author["name"] for author in data.get("authors", [])],
            subjects=data.get("subjects", []),
            download_url=download_url,
            text_url=text_url,
            word_count=word_count,
            difficulty_level=difficulty_level,
            last_accessed=time.time()
        )
    
    def get_book_text(self, book_id: int) -> Optional[str]:
        """Get the full text of a book."""
        book = self.get_book(book_id)
        if not book or not book.text_url:
            return None
        
        try:
            response = requests.get(book.text_url)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Error getting book text for {book_id}: {e}")
            return None
    
    def get_available_languages(self) -> List[str]:
        """Get a list of available languages in Project Gutenberg."""
        try:
            response = requests.get(f"{self.BASE_URL}/languages")
            response.raise_for_status()
            data = response.json()
            return [lang["code"] for lang in data.get("results", [])]
        except Exception as e:
            logger.error(f"Error getting available languages: {e}")
            return []
    
    def get_popular_books(self, language: str, limit: int = 10) -> List[GutenbergBook]:
        """Get popular books in a specific language."""
        try:
            response = requests.get(
                self.BASE_URL,
                params={"languages": language, "sort": "popular"}
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for book_data in data.get("results", [])[:limit]:
                book = self._parse_book_data(book_data)
                results.append(book)
            
            return results
            
        except Exception as e:
            logger.error(f"Error getting popular books for {language}: {e}")
            return []

