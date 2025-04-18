"""Module for interacting with Tatoeba's sentence database."""

import requests
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import json
import time

from utils.utils import Utils


@dataclass
class TatoebaSentence:
    """Represents a sentence from Tatoeba with its translations and audio."""
    id: int
    text: str
    language: str
    translations: List['TatoebaSentence']
    audio_url: Optional[str] = None
    last_accessed: Optional[float] = None


class Tatoeba:
    """Handles interactions with Tatoeba's sentence database."""
    
    BASE_URL = "https://tatoeba.org/api/v0"
    CACHE_DIR = Path("cache/tatoeba")
    CACHE_FILE = CACHE_DIR / "sentences.json"
    CACHE_DURATION = 86400  # 24 hours in seconds
    
    def __init__(self):
        """Initialize the Tatoeba client with caching."""
        self.sentences: Dict[int, TatoebaSentence] = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load cached sentence data from disk."""
        try:
            if self.CACHE_FILE.exists():
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.sentences = {
                        int(sentence_id): TatoebaSentence(**sentence_data)
                        for sentence_id, sentence_data in data.items()
                    }
        except Exception as e:
            Utils.log_red(f"Error loading Tatoeba cache: {e}")
            self.sentences = {}
    
    def _save_cache(self):
        """Save sentence data to cache file."""
        try:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(
                    {str(sentence_id): sentence.__dict__ 
                     for sentence_id, sentence in self.sentences.items()},
                    f,
                    ensure_ascii=False,
                    indent=2
                )
        except Exception as e:
            Utils.log_red(f"Error saving Tatoeba cache: {e}")
    
    def _is_cache_valid(self, sentence: TatoebaSentence) -> bool:
        """Check if cached sentence data is still valid."""
        if not sentence.last_accessed:
            return False
        return (time.time() - sentence.last_accessed) < self.CACHE_DURATION
    
    def search_sentences(
        self,
        language: str,
        query: Optional[str] = None,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        has_audio: bool = False,
        limit: int = 10
    ) -> List[TatoebaSentence]:
        """Search for sentences matching the given criteria."""
        params = {
            "from": language,
            "query": query,
            "has_audio": "yes" if has_audio else "no",
            "limit": limit
        }
        
        try:
            response = requests.get(f"{self.BASE_URL}/sentences", params=params)
            response.raise_for_status()
            data = response.json()
            
            results = []
            for sentence_data in data.get("results", []):
                sentence = self._parse_sentence_data(sentence_data)
                
                # Apply length filters if specified
                if min_length and len(sentence.text) < min_length:
                    continue
                if max_length and len(sentence.text) > max_length:
                    continue
                
                results.append(sentence)
            
            return results
            
        except Exception as e:
            Utils.log_red(f"Error searching Tatoeba sentences: {e}")
            return []
    
    def get_sentence(self, sentence_id: int) -> Optional[TatoebaSentence]:
        """Get a specific sentence by ID with its translations."""
        # Check cache first
        if sentence_id in self.sentences and self._is_cache_valid(self.sentences[sentence_id]):
            return self.sentences[sentence_id]
        
        try:
            # Get the sentence
            response = requests.get(f"{self.BASE_URL}/sentences/{sentence_id}")
            response.raise_for_status()
            sentence_data = response.json()
            
            sentence = self._parse_sentence_data(sentence_data)
            
            # Get translations
            response = requests.get(f"{self.BASE_URL}/sentences/{sentence_id}/translations")
            response.raise_for_status()
            translations_data = response.json()
            
            sentence.translations = [
                self._parse_sentence_data(t_data)
                for t_data in translations_data.get("results", [])
            ]
            
            # Get audio if available
            response = requests.get(f"{self.BASE_URL}/sentences/{sentence_id}/audio")
            response.raise_for_status()
            audio_data = response.json()
            
            if audio_data.get("results"):
                sentence.audio_url = audio_data["results"][0]["url"]
            
            self.sentences[sentence_id] = sentence
            self._save_cache()
            
            return sentence
            
        except Exception as e:
            Utils.log_red(f"Error getting Tatoeba sentence {sentence_id}: {e}")
            return None
    
    def _parse_sentence_data(self, data: Dict[str, Any]) -> TatoebaSentence:
        """Parse raw sentence data into a TatoebaSentence object."""
        return TatoebaSentence(
            id=data["id"],
            text=data["text"],
            language=data["lang"],
            translations=[],
            last_accessed=time.time()
        )
    
    def get_random_sentence(
        self,
        language: str,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        has_audio: bool = False
    ) -> Optional[TatoebaSentence]:
        """Get a random sentence matching the criteria."""
        try:
            params = {
                "from": language,
                "has_audio": "yes" if has_audio else "no",
                "random": "yes"
            }
            
            response = requests.get(f"{self.BASE_URL}/sentences", params=params)
            response.raise_for_status()
            data = response.json()
            
            if not data.get("results"):
                return None
                
            sentence = self._parse_sentence_data(data["results"][0])
            
            # Apply length filters if specified
            if min_length and len(sentence.text) < min_length:
                return None
            if max_length and len(sentence.text) > max_length:
                return None
            
            return sentence
            
        except Exception as e:
            Utils.log_red(f"Error getting random Tatoeba sentence: {e}")
            return None
    
    def get_available_languages(self) -> List[str]:
        """Get a list of available languages in Tatoeba."""
        try:
            response = requests.get(f"{self.BASE_URL}/languages")
            response.raise_for_status()
            data = response.json()
            return [lang["code"] for lang in data.get("results", [])]
        except Exception as e:
            Utils.log_red(f"Error getting available languages: {e}")
            return [] 