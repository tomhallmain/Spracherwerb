"""Module for interacting with Forvo's pronunciation database."""

import requests
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import json
import time

from utils.logging_setup import get_logger

logger = get_logger(__name__)

@dataclass
class Pronunciation:
    """Represents a pronunciation entry from Forvo."""
    id: int
    word: str
    language: str
    username: str
    country: str
    audio_url: str
    votes: int
    last_accessed: Optional[float] = None


class Forvo:
    """Handles interactions with Forvo's pronunciation database."""
    
    BASE_URL = "https://apifree.forvo.com"
    CACHE_DIR = Path("cache/forvo")
    CACHE_FILE = CACHE_DIR / "pronunciations.json"
    CACHE_DURATION = 86400  # 24 hours in seconds
    
    def __init__(self, api_key: str):
        """Initialize the Forvo client with API key and caching."""
        self.api_key = api_key
        self.pronunciations: Dict[str, List[Pronunciation]] = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load cached pronunciation data from disk."""
        try:
            if self.CACHE_FILE.exists():
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.pronunciations = {
                        word: [Pronunciation(**pron_data) for pron_data in pron_list]
                        for word, pron_list in data.items()
                    }
        except Exception as e:
            logger.error(f"Error loading Forvo cache: {e}")
            self.pronunciations = {}
    
    def _save_cache(self):
        """Save pronunciation data to cache file."""
        try:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(
                    {word: [pron.__dict__ for pron in pron_list]
                     for word, pron_list in self.pronunciations.items()},
                    f,
                    ensure_ascii=False,
                    indent=2
                )
        except Exception as e:
            logger.error(f"Error saving Forvo cache: {e}")
    
    def _is_cache_valid(self, pronunciations: List[Pronunciation]) -> bool:
        """Check if cached pronunciation data is still valid."""
        if not pronunciations:
            return False
        return (time.time() - max(p.last_accessed for p in pronunciations)) < self.CACHE_DURATION
    
    def get_pronunciations(
        self,
        word: str,
        language: str,
        limit: int = 5
    ) -> List[Pronunciation]:
        """Get pronunciations for a word in a specific language."""
        cache_key = f"{word}_{language}"
        
        # Check cache first
        if cache_key in self.pronunciations and self._is_cache_valid(self.pronunciations[cache_key]):
            return self.pronunciations[cache_key][:limit]
        
        try:
            params = {
                "key": self.api_key,
                "format": "json",
                "action": "word-pronunciations",
                "word": word,
                "language": language,
                "limit": limit
            }
            
            response = requests.get(f"{self.BASE_URL}/word-pronunciations", params=params)
            response.raise_for_status()
            data = response.json()
            
            pronunciations = []
            for item in data.get("items", []):
                pronunciation = Pronunciation(
                    id=item["id"],
                    word=item["word"],
                    language=item["language"],
                    username=item["username"],
                    country=item["country"],
                    audio_url=item["pathmp3"],
                    votes=item.get("num_votes", 0),
                    last_accessed=time.time()
                )
                pronunciations.append(pronunciation)
            
            self.pronunciations[cache_key] = pronunciations
            self._save_cache()
            
            return pronunciations
            
        except Exception as e:
            logger.error(f"Error getting Forvo pronunciations for {word}: {e}")
            return []
    
    def get_top_pronunciation(
        self,
        word: str,
        language: str
    ) -> Optional[Pronunciation]:
        """Get the highest-rated pronunciation for a word."""
        pronunciations = self.get_pronunciations(word, language)
        if not pronunciations:
            return None
        
        return max(pronunciations, key=lambda p: p.votes)
    
    def get_available_languages(self) -> List[str]:
        """Get a list of available languages in Forvo."""
        try:
            params = {
                "key": self.api_key,
                "format": "json",
                "action": "languages"
            }
            
            response = requests.get(f"{self.BASE_URL}/languages", params=params)
            response.raise_for_status()
            data = response.json()
            
            return [lang["code"] for lang in data.get("items", [])]
            
        except Exception as e:
            logger.error(f"Error getting available languages: {e}")
            return []
    
    def get_country_pronunciations(
        self,
        word: str,
        language: str,
        country: str
    ) -> List[Pronunciation]:
        """Get pronunciations from a specific country."""
        pronunciations = self.get_pronunciations(word, language)
        return [p for p in pronunciations if p.country.lower() == country.lower()]
    
    def get_user_pronunciations(
        self,
        username: str,
        limit: int = 10
    ) -> List[Pronunciation]:
        """Get pronunciations by a specific user."""
        try:
            params = {
                "key": self.api_key,
                "format": "json",
                "action": "user-pronunciations",
                "username": username,
                "limit": limit
            }
            
            response = requests.get(f"{self.BASE_URL}/user-pronunciations", params=params)
            response.raise_for_status()
            data = response.json()
            
            pronunciations = []
            for item in data.get("items", []):
                pronunciation = Pronunciation(
                    id=item["id"],
                    word=item["word"],
                    language=item["language"],
                    username=item["username"],
                    country=item["country"],
                    audio_url=item["pathmp3"],
                    votes=item.get("num_votes", 0),
                    last_accessed=time.time()
                )
                pronunciations.append(pronunciation)
            
            return pronunciations
            
        except Exception as e:
            logger.error(f"Error getting user pronunciations: {e}")
            return [] 