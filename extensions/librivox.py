"""Module for interacting with LibriVox's audiobook database."""

import requests
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import json
import time

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
    
    def __init__(self):
        """Initialize the LibriVox client with caching."""
        self.audiobooks: Dict[int, Audiobook] = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load cached audiobook data from disk."""
        try:
            if self.CACHE_FILE.exists():
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.audiobooks = {
                        int(book_id): Audiobook(**book_data)
                        for book_id, book_data in data.items()
                    }
        except Exception as e:
            logger.error(f"Error loading LibriVox cache: {e}")
            self.audiobooks = {}
    
    def _save_cache(self):
        """Save audiobook data to cache file."""
        try:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(
                    {str(book_id): book.__dict__ 
                     for book_id, book in self.audiobooks.items()},
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
        """Search for audiobooks matching the given criteria."""
        params = {
            "format": "json",
            "limit": limit
        }
        
        if query:
            params["title"] = query
        if language:
            params["language"] = language
        if author:
            params["author"] = author
        
        try:
            response = requests.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for book_data in data.get("books", []):
                audiobook = self._parse_audiobook_data(book_data)
                results.append(audiobook)
            
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
            response = requests.get(f"{self.BASE_URL}/{book_id}")
            response.raise_for_status()
            data = response.json()
            
            audiobook = self._parse_audiobook_data(data)
            
            self.audiobooks[book_id] = audiobook
            self._save_cache()
            
            return audiobook
            
        except Exception as e:
            logger.error(f"Error getting LibriVox audiobook {book_id}: {e}")
            return None
    
    def _parse_audiobook_data(self, data: Dict[str, Any]) -> Audiobook:
        """Parse raw audiobook data into an Audiobook object."""
        chapters = []
        for chapter_data in data.get("sections", []):
            chapter = Chapter(
                id=chapter_data["id"],
                title=chapter_data["title"],
                duration=chapter_data["playtime"],
                audio_url=chapter_data["url_audio_file"],
                text_url=chapter_data.get("url_text_source"),
                last_accessed=time.time()
            )
            chapters.append(chapter)
        
        return Audiobook(
            id=data["id"],
            title=data["title"],
            author=data["author"],
            language=data["language"],
            total_time=data["totaltime"],
            description=data["description"],
            chapters=chapters,
            last_accessed=time.time()
        )
    
    def get_available_languages(self) -> List[str]:
        """Get a list of available languages in LibriVox."""
        try:
            response = requests.get(f"{self.BASE_URL}/languages")
            response.raise_for_status()
            data = response.json()
            return [lang["name"] for lang in data.get("languages", [])]
        except Exception as e:
            logger.error(f"Error getting available languages: {e}")
            return []
    
    def get_popular_audiobooks(
        self,
        language: Optional[str] = None,
        limit: int = 10
    ) -> List[Audiobook]:
        """Get popular audiobooks, optionally filtered by language."""
        try:
            params = {
                "format": "json",
                "limit": limit,
                "sort": "popular"
            }
            
            if language:
                params["language"] = language
            
            response = requests.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for book_data in data.get("books", []):
                audiobook = self._parse_audiobook_data(book_data)
                results.append(audiobook)
            
            return results
            
        except Exception as e:
            logger.error(f"Error getting popular audiobooks: {e}")
            return [] 