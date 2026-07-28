"""Module for interacting with LibriVox's audiobook database."""

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
class Audiobook:
    """Represents an audiobook from LibriVox."""
    id: int
    title: str
    author: str
    language: str
    total_time: str
    description: str
    chapters: List['Chapter']
    last_accessed: Optional[float] = None


@dataclass
class Chapter:
    """Represents a chapter in a LibriVox audiobook."""
    id: int
    title: str
    duration: str
    audio_url: str
    text_url: Optional[str] = None
    last_accessed: Optional[float] = None


class LibriVox:
    """Handles interactions with LibriVox's audiobook database."""
    
    BASE_URL = "https://librivox.org/api/feed/audiobooks"
    CACHE_DIR = Path("cache/librivox")
    CACHE_FILE = CACHE_DIR / "audiobooks.json"
    CACHE_DURATION = 86400  # 24 hours in seconds
    REQUEST_TIMEOUT = 20  # seconds; extended=1 listings can be a large payload
    
    def __init__(self):
        """Initialize the LibriVox client with caching."""
        self.audiobooks: Dict[int, Audiobook] = {}
        self._load_cache()
    
    def _load_cache(self) -> Dict[int, Audiobook]:
        """Load cached audiobook data from disk."""
        try:
            if self.CACHE_FILE.exists():
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.audiobooks = {}
                    for book_id, book_data in data.items():
                        book_data = dict(book_data)
                        book_data["chapters"] = [
                            Chapter(**chapter_data) for chapter_data in book_data.get("chapters", [])
                        ]
                        self.audiobooks[int(book_id)] = Audiobook(**book_data)
        except Exception as e:
            logger.error(f"Error loading LibriVox cache: {e}")
            self.audiobooks = {}
        return self.audiobooks

    def _save_cache(self):
        """Save audiobook data to cache file."""
        try:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            # book.__dict__ leaves "chapters" as a list of Chapter objects,
            # which json.dump() can't serialize on its own -- that silently
            # blew up this whole dump (caught below, logged, nothing
            # written) as soon as any cached audiobook actually had
            # chapters in it.
            serializable = {}
            for book_id, book in self.audiobooks.items():
                book_dict = dict(book.__dict__)
                book_dict["chapters"] = [chapter.__dict__ for chapter in book.chapters]
                serializable[str(book_id)] = book_dict
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(
                    serializable,
                    f,
                    ensure_ascii=False,
                    indent=2
                )
        except Exception as e:
            logger.error(f"Error saving LibriVox cache: {e}")
    
    def _is_cache_valid(self, audiobook: Audiobook) -> bool:
        """Check if cached audiobook data is still valid."""
        if not audiobook.last_accessed:
            return False
        return (time.time() - audiobook.last_accessed) < self.CACHE_DURATION
    
    def search_audiobooks(
        self,
        query: Optional[str] = None,
        language: Optional[str] = None,
        author: Optional[str] = None,
        limit: int = 10
    ) -> List[Audiobook]:
        """Search for audiobooks matching the given criteria.

        LibriVox's feed API has no ``language`` filter parameter (its
        documented parameters are id/since/author/title/genre/extended/
        coverart/limit/offset -- see https://librivox.org/api/info); a
        request with ``language=`` in the query string is simply ignored
        server-side. ``language`` is therefore applied client-side against
        whatever the API returns, so a larger raw fetch is requested when
        it's set to give the filter a reasonable pool to work with.
        """
        fetch_limit = max(limit * 20, 100) if language else limit
        params = {
            "format": "json",
            "limit": fetch_limit,
            # The base listing omits "sections" (chapters) unless asked for.
            "extended": 1
        }

        if query:
            params["title"] = query
        if author:
            params["author"] = author

        try:
            response = requests.get(self.BASE_URL, params=params, timeout=self.REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()

            results = []
            for book_data in data.get("books", []):
                audiobook = self._parse_audiobook_data(book_data)
                if language and audiobook.language != language:
                    continue
                # A handful of catalog entries are index/collection pages
                # (e.g. "Fairy Tales (Index of all Fairy Tales)") with no
                # actual chapters -- not a usable audiobook for this app.
                if not audiobook.chapters:
                    continue
                self.audiobooks[audiobook.id] = audiobook
                results.append(audiobook)
                if len(results) >= limit:
                    break

            self._save_cache()

            return results

        except Exception as e:
            logger.error(f"Error searching LibriVox: {e}")
            return []
    
    def get_audiobook(self, book_id: int) -> Optional[Audiobook]:
        """Get a specific audiobook by ID with its chapters."""
        # Check cache first
        if book_id in self.audiobooks and self._is_cache_valid(self.audiobooks[book_id]):
            return self.audiobooks[book_id]

        try:
            # `{BASE_URL}/{book_id}` (no "id/") is not a valid path -- it's
            # silently treated as no filter at all and returns the default
            # listing. The documented single-record form is "id/{book_id}",
            # and "extended=1" is required for the response to include
            # "sections" (chapters) at all.
            response = requests.get(
                f"{self.BASE_URL}/id/{book_id}",
                params={"format": "json", "extended": 1},
                timeout=self.REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()

            books = data.get("books", [])
            if not books:
                return None

            audiobook = self._parse_audiobook_data(books[0])

            self.audiobooks[audiobook.id] = audiobook
            self._save_cache()

            return audiobook

        except Exception as e:
            logger.error(f"Error getting LibriVox audiobook {book_id}: {e}")
            return None

    def _parse_audiobook_data(self, data: Dict[str, Any]) -> Audiobook:
        """Parse raw audiobook data into an Audiobook object."""
        # Sections/chapters don't carry their own text source in LibriVox's
        # API -- only the book as a whole does (source text isn't split up
        # per chapter). The book's url_text_source is used for every
        # chapter as the closest available reference rather than leaving it
        # unset.
        book_text_url = data.get("url_text_source") or None

        chapters = []
        for chapter_data in data.get("sections", []):
            chapter = Chapter(
                id=int(chapter_data["id"]),
                title=chapter_data["title"],
                duration=chapter_data["playtime"],
                audio_url=chapter_data["listen_url"],
                text_url=book_text_url,
                last_accessed=time.time()
            )
            chapters.append(chapter)

        authors = data.get("authors", [])
        author_names = ", ".join(
            name for name in (
                f"{a.get('first_name', '')} {a.get('last_name', '')}".strip()
                for a in authors
            ) if name
        ) or "Unknown"

        return Audiobook(
            id=int(data["id"]),
            title=data["title"],
            author=author_names,
            language=data["language"],
            total_time=data["totaltime"],
            description=data["description"],
            chapters=chapters,
            last_accessed=time.time()
        )
    
    def get_available_languages(self) -> List[str]:
        """Get the display names of languages this app can search LibriVox for.

        LibriVox's API has no endpoint listing its supported languages --
        ``{BASE_URL}/languages`` just falls through to the regular audiobook
        feed (200 OK, but no "languages" key in the response), so the old
        ``data.get("languages", [])`` here always returned an empty list.
        This returns display names for ``Language``'s supported codes
        instead of probing a nonexistent endpoint; ``search_audiobooks
        (language=...)`` already accepts these same display names directly.
        """
        return [Language.get_language_name(code) for code in Language.get_all_codes()]
    
    def get_popular_audiobooks(
        self,
        language: Optional[str] = None,
        limit: int = 10
    ) -> List[Audiobook]:
        """Get audiobooks, optionally filtered by language.

        LibriVox's feed API has no "popular"/sort parameter (nor a
        ``language`` filter -- see the note on ``search_audiobooks``), so
        this is really "audiobooks in the API's default order", filtered by
        language client-side when requested.
        """
        try:
            fetch_limit = max(limit * 20, 100) if language else limit
            params = {
                "format": "json",
                "limit": fetch_limit
            }

            response = requests.get(self.BASE_URL, params=params, timeout=self.REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()

            results = []
            for book_data in data.get("books", []):
                audiobook = self._parse_audiobook_data(book_data)
                if language and audiobook.language != language:
                    continue
                results.append(audiobook)
                if len(results) >= limit:
                    break

            return results

        except Exception as e:
            logger.error(f"Error getting popular audiobooks: {e}")
            return [] 