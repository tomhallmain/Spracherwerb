"""Module for interacting with OpenSubtitles API."""

import requests
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import json
import time
import re
import base64
import gzip
import io

from utils.utils import Utils


@dataclass
class Subtitle:
    """Represents a subtitle entry from OpenSubtitles."""
    id: str
    movie_name: str
    language: str
    download_url: str
    format: str
    encoding: str
    fps: float
    content: Optional[str] = None
    last_accessed: Optional[float] = None


class OpenSubtitles:
    """Handles interactions with OpenSubtitles API."""
    
    BASE_URL = "https://api.opensubtitles.com/api/v1"
    CACHE_DIR = Path("cache/opensubtitles")
    CACHE_FILE = CACHE_DIR / "subtitles.json"
    CACHE_DURATION = 86400  # 24 hours in seconds
    
    def __init__(self, api_key: str):
        """Initialize the OpenSubtitles client with API key and caching."""
        self.api_key = api_key
        self.headers = {
            "Api-Key": api_key,
            "Content-Type": "application/json"
        }
        self.subtitles: Dict[str, Subtitle] = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load cached subtitle data from disk."""
        try:
            if self.CACHE_FILE.exists():
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.subtitles = {
                        sub_id: Subtitle(**sub_data)
                        for sub_id, sub_data in data.items()
                    }
        except Exception as e:
            Utils.log_red(f"Error loading OpenSubtitles cache: {e}")
            self.subtitles = {}
    
    def _save_cache(self):
        """Save subtitle data to cache file."""
        try:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(
                    {sub_id: sub.__dict__ 
                     for sub_id, sub in self.subtitles.items()},
                    f,
                    ensure_ascii=False,
                    indent=2
                )
        except Exception as e:
            Utils.log_red(f"Error saving OpenSubtitles cache: {e}")
    
    def _is_cache_valid(self, subtitle: Subtitle) -> bool:
        """Check if cached subtitle data is still valid."""
        if not subtitle.last_accessed:
            return False
        return (time.time() - subtitle.last_accessed) < self.CACHE_DURATION
    
    def search_subtitles(
        self,
        query: str,
        language: str,
        movie_hash: Optional[str] = None,
        imdb_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Subtitle]:
        """Search for subtitles matching the given criteria."""
        params = {
            "query": query,
            "languages": language,
            "limit": limit
        }
        
        if movie_hash:
            params["moviehash"] = movie_hash
        if imdb_id:
            params["imdb_id"] = imdb_id
        
        try:
            response = requests.get(
                f"{self.BASE_URL}/subtitles",
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for sub_data in data.get("data", []):
                subtitle = self._parse_subtitle_data(sub_data)
                results.append(subtitle)
            
            return results
            
        except Exception as e:
            Utils.log_red(f"Error searching OpenSubtitles: {e}")
            return []
    
    def get_subtitle(self, subtitle_id: str) -> Optional[Subtitle]:
        """Get a specific subtitle by ID with its content."""
        # Check cache first
        if subtitle_id in self.subtitles and self._is_cache_valid(self.subtitles[subtitle_id]):
            return self.subtitles[subtitle_id]
        
        try:
            # Get the subtitle
            response = requests.get(
                f"{self.BASE_URL}/subtitles/{subtitle_id}",
                headers=self.headers
            )
            response.raise_for_status()
            sub_data = response.json()
            
            subtitle = self._parse_subtitle_data(sub_data["data"])
            
            # Download the content
            download_response = requests.get(subtitle.download_url)
            download_response.raise_for_status()
            
            # Handle gzipped content
            if subtitle.format == "srt":
                content = download_response.text
            else:  # Handle other formats if needed
                content = self._decompress_content(download_response.content)
            
            subtitle.content = content
            self.subtitles[subtitle_id] = subtitle
            self._save_cache()
            
            return subtitle
            
        except Exception as e:
            Utils.log_red(f"Error getting OpenSubtitles subtitle {subtitle_id}: {e}")
            return None
    
    def _parse_subtitle_data(self, data: Dict[str, Any]) -> Subtitle:
        """Parse raw subtitle data into a Subtitle object."""
        return Subtitle(
            id=data["id"],
            movie_name=data["attributes"]["movie_name"],
            language=data["attributes"]["language"],
            download_url=data["attributes"]["url"],
            format=data["attributes"]["format"],
            encoding=data["attributes"]["encoding"],
            fps=float(data["attributes"]["fps"]),
            last_accessed=time.time()
        )
    
    def _decompress_content(self, content: bytes) -> str:
        """Decompress gzipped subtitle content."""
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(content)) as f:
                return f.read().decode('utf-8')
        except Exception as e:
            Utils.log_red(f"Error decompressing subtitle content: {e}")
            return ""
    
    def get_available_languages(self) -> List[str]:
        """Get a list of available languages in OpenSubtitles."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/languages",
                headers=self.headers
            )
            response.raise_for_status()
            data = response.json()
            return [lang["language_code"] for lang in data.get("data", [])]
        except Exception as e:
            Utils.log_red(f"Error getting available languages: {e}")
            return [] 