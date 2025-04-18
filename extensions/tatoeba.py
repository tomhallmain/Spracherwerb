"""Module for interacting with Tatoeba's sentence database."""

import requests
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import json
import time
import random

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
    
    BASE_URL = "https://api.tatoeba.org/unstable"
    CACHE_DIR = Path("cache/tatoeba")
    CACHE_FILE = CACHE_DIR / "sentences.json"
    CACHE_DURATION = 86400  # 24 hours in seconds
    
    # List of supported languages (from Tatoeba's website)
    SUPPORTED_LANGUAGES = [
        "eng", "deu", "fra", "jpn", "spa", "ita", "por", "rus", "cmn", "kor",
        "nld", "pol", "tur", "swe", "fin", "dan", "nor", "isl", "lat", "ell",
        "hun", "ces", "slk", "bul", "ukr", "bel", "srp", "hrv", "slv", "mkd",
        "bos", "heb", "ara", "fas", "urd", "hin", "ben", "tam", "tel", "tha",
        "vie", "ind", "msa", "tgl", "epo", "ido", "ina", "nov", "vol", "qya"
    ]
    
    def __init__(self):
        """Initialize the Tatoeba client with caching."""
        self.sentences: Dict[int, TatoebaSentence] = {}
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        # Initialize default cache paths
        self.CACHE_DIR = Path("cache/tatoeba")
        self.CACHE_FILE = self.CACHE_DIR / "sentences.json"
        # Load cache after paths are set
        self._load_cache()
    
    def _load_cache(self):
        """Load cached sentence data from disk."""
        try:
            if self.CACHE_FILE.exists():
                Utils.log(f"Loading cache from {self.CACHE_FILE}")
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.sentences = {
                        int(sentence_id): TatoebaSentence(**sentence_data)
                        for sentence_id, sentence_data in data.items()
                    }
                Utils.log(f"Cache loaded successfully with {len(self.sentences)} sentences")
            else:
                Utils.log(f"No cache file found at {self.CACHE_FILE}")
        except Exception as e:
            Utils.log_red(f"Error loading Tatoeba cache: {e}")
            self.sentences = {}
    
    def _save_cache(self):
        """Save sentence data to cache file."""
        try:
            Utils.log(f"Saving cache to {self.CACHE_FILE}")
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(
                    {str(sentence_id): sentence.__dict__ 
                     for sentence_id, sentence in self.sentences.items()},
                    f,
                    ensure_ascii=False,
                    indent=2
                )
            Utils.log(f"Cache saved successfully with {len(self.sentences)} sentences")
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
        Utils.log(f"Searching sentences with params: language={language}, query={query}, limit={limit}")
        
        # First check cache for matching sentences
        cached_results = []
        for sentence in self.sentences.values():
            if sentence.language != language:
                continue
            if query and query.lower() not in sentence.text.lower():
                continue
            if min_length and len(sentence.text) < min_length:
                continue
            if max_length and len(sentence.text) > max_length:
                continue
            if has_audio and not sentence.audio_url:
                continue
            if self._is_cache_valid(sentence):
                cached_results.append(sentence)
            if len(cached_results) >= limit:
                break

        Utils.log(f"Found {len(cached_results)} cached results")

        # If we have enough cached results, return them
        if len(cached_results) >= limit:
            return cached_results[:limit]

        # Otherwise, make API request
        params = {
            "lang": language,
            "query": query,
            "limit": limit,
            "sort": "random"
        }
        
        # Add has_audio parameter if requested
        if has_audio:
            params["has_audio"] = "yes"
        
        try:
            Utils.log(f"Making API request to {self.BASE_URL}/sentences with params: {params}")
            response = self.session.get(f"{self.BASE_URL}/sentences", params=params)
            response.raise_for_status()
            data = response.json()
            
            Utils.log(f"API response status: {response.status_code}")
            if "data" in data:
                Utils.log(f"API response data length: {len(data['data'])}")
            else:
                Utils.log_red(f"No data found in API response")
                return cached_results[:limit]
            
            results = []
            for sentence_data in data.get("data", []):
                sentence = self._parse_sentence_data(sentence_data)
                
                # Apply length filters if specified
                if min_length and len(sentence.text) < min_length:
                    continue
                if max_length and len(sentence.text) > max_length:
                    continue
                
                # Apply audio filter if specified
                if has_audio and not sentence.audio_url:
                    continue
                
                # Cache the sentence
                self.sentences[sentence.id] = sentence
                results.append(sentence)
                
                # Stop if we have enough results
                if len(results) >= limit:
                    break
            
            Utils.log(f"Found {len(results)} new results from API")
            
            # Save the cache after collecting results
            self._save_cache()
            
            # Combine cached and new results
            combined_results = cached_results + results
            Utils.log(f"Returning {len(combined_results[:limit])} total results")
            return combined_results[:limit]
            
        except Exception as e:
            Utils.log_red(f"Error searching Tatoeba sentences: {e}")
            return cached_results[:limit]  # Return cached results even if API fails
    
    def get_sentence(self, sentence_id: int) -> Optional[TatoebaSentence]:
        """Get a specific sentence by ID with its translations."""
        # Check cache first
        if sentence_id in self.sentences and self._is_cache_valid(self.sentences[sentence_id]):
            return self.sentences[sentence_id]
        
        try:
            # Get the sentence
            response = self.session.get(f"{self.BASE_URL}/sentences/{sentence_id}")
            response.raise_for_status()
            sentence_data = response.json()
            
            sentence = self._parse_sentence_data(sentence_data["data"])
            
            # Get translations
            response = self.session.get(f"{self.BASE_URL}/sentences/{sentence_id}/translations")
            response.raise_for_status()
            translations_data = response.json()
            
            sentence.translations = [
                self._parse_sentence_data(t_data)
                for t_data in translations_data.get("data", [])
            ]
            
            # Get audio if available
            response = self.session.get(f"{self.BASE_URL}/sentences/{sentence_id}/audio")
            response.raise_for_status()
            audio_data = response.json()
            
            if audio_data.get("data"):
                sentence.audio_url = audio_data["data"][0]["url"]
            
            self.sentences[sentence_id] = sentence
            self._save_cache()
            
            return sentence
            
        except Exception as e:
            Utils.log_red(f"Error getting Tatoeba sentence {sentence_id}: {e}")
            return None
    
    def _parse_sentence_data(self, data: Dict[str, Any]) -> TatoebaSentence:
        """Parse raw sentence data into a TatoebaSentence object."""
        # Check for audio data in the response
        audio_url = None
        if "audios" in data and data["audios"]:
            audio_url = data["audios"][0].get("download_url")
        
        return TatoebaSentence(
            id=data["id"],
            text=data["text"],
            language=data["lang"],
            translations=[],
            audio_url=audio_url,
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
            Utils.log(f"Getting random sentence with params: language={language}, min_length={min_length}, max_length={max_length}, has_audio={has_audio}")
            
            # First, get a list of sentences
            sentences = self.search_sentences(
                language=language,
                min_length=min_length,
                max_length=max_length,
                has_audio=has_audio,
                limit=10
            )
            
            Utils.log(f"Found {len(sentences)} sentences")
            
            if not sentences:
                Utils.log_red("No sentences found matching criteria")
                return None
            
            # Randomly select one sentence
            sentence = random.choice(sentences)
            Utils.log(f"Selected random sentence: {sentence.text[:50]}...")
            return sentence
            
        except Exception as e:
            Utils.log_red(f"Error getting random Tatoeba sentence: {e}")
            return None
    
    def get_available_languages(self) -> List[str]:
        """Get a list of available languages in Tatoeba."""
        return self.SUPPORTED_LANGUAGES 