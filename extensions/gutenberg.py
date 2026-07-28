"""Project Gutenberg integration for the Spracherwerb application."""

import requests
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import json
import time

from utils.globals import Language
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
    # Gutendex's `topic=` search filter matches against bookshelf categories
    # as well as subjects (e.g. a book with no "history" in its subjects can
    # still carry the bookshelf "Category: History - Ancient") -- keeping
    # this alongside subjects lets callers actually explain a topic match.
    bookshelves: List[str]
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
            "bookshelves": self.bookshelves,
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
            bookshelves=data.get("bookshelves", []),  # absent in caches predating this field
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
    API_TIMEOUT = 15  # seconds, for the lightweight Gutendex JSON calls
    TEXT_TIMEOUT = 30  # seconds, full book texts can be several MB
    
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
        """Check if cached book data is still valid.

        ``word_count`` is only ``None`` when the text-download-and-count
        step failed (timeout, transient error, ...) or hasn't run yet --
        never because a book legitimately has no count. A cache entry with
        no word count is therefore always treated as stale, so a prior
        failure doesn't get locked in for the full CACHE_DURATION and skip
        every future retry.
        """
        if not book.last_accessed:
            return False
        if (time.time() - book.last_accessed) >= self.CACHE_DURATION:
            return False
        if book.word_count is None:
            return False
        return True
    
    def search_books(self,
                    language: Optional[str] = None,
                    search_term: Optional[str] = None,
                    author: Optional[str] = None,
                    subject: Optional[str] = None,
                    min_word_count: Optional[int] = None,
                    max_word_count: Optional[int] = None,
                    limit: Optional[int] = None) -> List[GutenbergBook]:
        """Search for books matching the given criteria.

        ``language`` accepts either a display name (e.g. "German") or an
        ISO 639-1 code ("de") -- Gutendex itself only understands codes, so
        a recognized display name is converted before the request goes out.
        Omit it to search across all languages.

        Word counts come from downloading each candidate's full text, which
        is the slow part of a search -- a book already in ``self.books``
        (from an earlier search, ``get_book``, or ``get_book_details``) is
        reused instead of being re-fetched and re-counted every time.
        """
        params = {
            "search": search_term,
            "author": author,
            "topic": subject
        }
        if language:
            params["languages"] = Language.get_language_code(language)

        logger.info(f"Gutenberg search: params={params} min_word_count={min_word_count} "
                    f"max_word_count={max_word_count} limit={limit}")

        try:
            response = requests.get(self.BASE_URL, params=params, timeout=self.API_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            logger.debug(f"Gutendex returned {len(data.get('results', []))} candidate(s) "
                         f"(of {data.get('count')} total)")

            results = []
            cache_dirty = False
            for book_data in data.get("results", []):
                cached = self.books.get(book_data.get("id"))
                if cached is not None and self._is_cache_valid(cached):
                    logger.debug(f"Book {book_data.get('id')}: cache hit, "
                                 f"word_count={cached.word_count}")
                    book = cached
                else:
                    logger.debug(f"Book {book_data.get('id')}: cache miss/stale, parsing fresh")
                    book = self._parse_book_data(book_data)
                    self.books[book.id] = book
                    cache_dirty = True

                # Apply word count filters if specified
                if min_word_count and book.word_count and book.word_count < min_word_count:
                    continue
                if max_word_count and book.word_count and book.word_count > max_word_count:
                    continue

                results.append(book)
                if limit and len(results) >= limit:
                    break

            if cache_dirty:
                self._save_cache()

            logger.info(f"Gutenberg search: returning {len(results)} book(s), "
                        f"word_counts={[b.word_count for b in results]}")

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
            response = requests.get(f"{self.BASE_URL}/{book_id}", timeout=self.API_TIMEOUT)
            response.raise_for_status()
            book_data = response.json()

            book = self._parse_book_data(book_data)
            self.books[book_id] = book
            self._save_cache()

            return book

        except Exception as e:
            logger.error(f"Error getting Gutenberg book {book_id}: {e}")
            return None

    def get_book_details(self, book_id: int) -> GutenbergBook:
        """Get full details for a book, raising if the ID is invalid.

        Unlike ``get_book()``, this does not swallow request errors -- an
        invalid ID is a caller mistake that should surface as an exception
        rather than a silent ``None``.
        """
        if book_id in self.books and self._is_cache_valid(self.books[book_id]):
            return self.books[book_id]

        response = requests.get(f"{self.BASE_URL}/{book_id}", timeout=self.API_TIMEOUT)
        response.raise_for_status()
        book = self._parse_book_data(response.json())
        self.books[book_id] = book
        self._save_cache()
        return book

    def _parse_book_data(self, data: Dict[str, Any]) -> GutenbergBook:
        """Parse raw book data into a GutenbergBook object."""
        # Gutendex's "formats" maps MIME type -> URL (e.g. "text/plain;
        # charset=utf-8" -> ".../pg2701.txt.utf-8"), so the plain-text
        # format has to be picked out by its key, not by scanning the URLs
        # themselves for the substring "text/plain" (which they never
        # contain).
        formats = data.get("formats", {})

        # Get the text URL (prefer plain text format)
        text_url = None
        for mime_type, url in formats.items():
            if "text/plain" in mime_type:
                text_url = url
                break

        # Get the download URL (prefer plain text format)
        download_url = None
        for mime_type, url in formats.items():
            if "text/plain" in mime_type:
                download_url = url
                break
        
        # Estimate word count from the text URL if available
        word_count = None
        if text_url:
            fetch_started = time.time()
            try:
                response = requests.get(text_url, timeout=self.TEXT_TIMEOUT)
                response.raise_for_status()
                word_count = len(response.text.split())
                logger.debug(f"Counted {word_count} words for book {data.get('id')} "
                             f"in {time.time() - fetch_started:.1f}s ({text_url})")
            except Exception as e:
                logger.warning(f"Error fetching text to count words for book {data.get('id')} "
                               f"after {time.time() - fetch_started:.1f}s ({text_url}): "
                               f"{type(e).__name__}: {e}")
        else:
            logger.debug(f"Book {data.get('id')} has no text/plain format in "
                         f"formats={list(formats.keys())}")
        
        # Estimate difficulty level based on word count
        difficulty_level = None
        if word_count:
            if word_count < 10000:
                difficulty_level = 1  # Beginner
            elif word_count < 30000:
                difficulty_level = 2  # Intermediate
            else:
                difficulty_level = 3  # Advanced
        
        raw_language = data.get("languages", ["en"])[0]  # Default to English if not specified
        return GutenbergBook(
            id=data["id"],
            title=data["title"],
            language=Language.get_language_name(raw_language),
            authors=[author["name"] for author in data.get("authors", [])],
            subjects=data.get("subjects", []),
            bookshelves=data.get("bookshelves", []),
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
            response = requests.get(book.text_url, timeout=self.TEXT_TIMEOUT)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Error getting book text for {book_id}: {e}")
            return None
    
    def get_available_languages(self) -> List[str]:
        """Get the display names of languages this app can search Gutenberg for.

        Gutendex (the API this client talks to) has no endpoint listing its
        supported languages -- ``{BASE_URL}/languages`` is a 404. Gutenberg
        itself carries books in dozens of languages, but this app only ever
        needs the ones it can present to the user, so this returns display
        names for ``Language``'s supported codes (all of which Gutenberg has
        books for) rather than probing a nonexistent endpoint.
        """
        return [Language.get_language_name(code) for code in Language.get_all_codes()]
    
    def get_popular_books(self, language: str, limit: int = 10) -> List[GutenbergBook]:
        """Get popular books (by download count) in a specific language."""
        try:
            response = requests.get(
                self.BASE_URL,
                params={"languages": Language.get_language_code(language), "sort": "popular"},
                timeout=self.API_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()

            results = []
            cache_dirty = False
            for book_data in data.get("results", [])[:limit]:
                cached = self.books.get(book_data.get("id"))
                if cached is not None and self._is_cache_valid(cached):
                    book = cached
                else:
                    book = self._parse_book_data(book_data)
                    self.books[book.id] = book
                    cache_dirty = True
                results.append(book)

            if cache_dirty:
                self._save_cache()

            return results

        except Exception as e:
            logger.error(f"Error getting popular books for {language}: {e}")
            return []

