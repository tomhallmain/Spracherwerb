"""Module for interacting with Mozilla's Common Voice dataset.

NOTE: This extension is currently non-functional as the Common Voice API appears to be undocumented
and potentially no longer publicly accessible. This extension should be considered for removal
or replacement with an alternative voice sample service.
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import json
import time
import requests
import os
import csv
from io import StringIO

from utils.utils import Utils


@dataclass
class VoiceSample:
    """Represents a voice sample from Common Voice."""
    id: str
    text: str
    language: str
    accent: Optional[str]
    age: Optional[str]
    gender: Optional[str]
    duration: float
    audio_url: str
    votes: Dict[str, int]
    last_accessed: Optional[float] = None


class CommonVoice:
    """Handles interactions with Mozilla's Common Voice database."""
    
    BASE_URL = "https://commonvoice.mozilla.org/api/v2"
    CACHE_DIR = Path("cache/common_voice")
    CACHE_FILE = CACHE_DIR / "samples.json"
    CACHE_DURATION = 86400  # 24 hours in seconds
    
    def __init__(self):
        """Initialize the Common Voice client with caching."""
        self.samples: Dict[str, VoiceSample] = {}
        self._load_cache()
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Spracherwerb/1.0"
        })
    
    def _load_cache(self):
        """Load cached voice samples from disk."""
        try:
            if self.CACHE_FILE.exists():
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.samples = {
                        lang: [VoiceSample(**sample_data) for sample_data in samples]
                        for lang, samples in data.items()
                    }
        except Exception as e:
            Utils.log_red(f"Error loading Common Voice cache: {e}")
            self.samples = {}
    
    def _save_cache(self):
        """Save voice samples to cache file."""
        try:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(
                    {lang: [sample.__dict__ for sample in samples]
                     for lang, samples in self.samples.items()},
                    f,
                    ensure_ascii=False,
                    indent=2
                )
        except Exception as e:
            Utils.log_red(f"Error saving Common Voice cache: {e}")
    
    def _is_cache_valid(self, samples: List[VoiceSample]) -> bool:
        """Check if cached voice samples are still valid."""
        if not samples:
            return False
        return (time.time() - max(s.last_accessed for s in samples)) < self.CACHE_DURATION
    
    def get_available_languages(self) -> List[str]:
        """Get a list of available languages."""
        try:
            response = self.session.get(f"{self.BASE_URL}/languages")
            response.raise_for_status()
            data = response.json()
            return [lang["code"] for lang in data.get("data", [])]
        except Exception as e:
            Utils.log_red(f"Error getting available languages: {e}")
            return []
    
    def get_voice_samples(
        self,
        language: str = "en-US",
        limit: int = 10,
        min_duration: float = 1.0,
        max_duration: float = 10.0,
        min_votes: int = 3
    ) -> List[VoiceSample]:
        """Get voice samples matching the given criteria."""
        try:
            params = {
                "language": language,
                "limit": limit,
                "min_duration": min_duration,
                "max_duration": max_duration,
                "min_votes": min_votes
            }
            
            response = self.session.get(f"{self.BASE_URL}/samples", params=params)
            response.raise_for_status()
            data = response.json()
            print(data)
            
            results = []
            for sample_data in data.get("data", []):
                sample = self._parse_sample_data(sample_data)
                self.samples[sample.id] = sample
                results.append(sample)
            
            self._save_cache()
            return results
            
        except Exception as e:
            Utils.log_red(f"Error getting Common Voice samples for {language}: {e}")
            return []
    
    def _parse_sample_data(self, data: Dict) -> VoiceSample:
        """Parse sample data from API response."""
        return VoiceSample(
            id=data["id"],
            text=data["text"],
            language=data["language"],
            accent=data.get("accent"),
            age=data.get("age"),
            gender=data.get("gender"),
            duration=float(data["duration"]),
            audio_url=data["audio_url"],
            votes={
                "up": data.get("votes_up", 0),
                "down": data.get("votes_down", 0)
            }
        )
    
    def get_samples_by_accent(
        self,
        language: str,
        accent: str,
        limit: int = 5
    ) -> List[VoiceSample]:
        """Get voice samples with a specific accent."""
        samples = self.get_voice_samples(language, limit=100)  # Get more samples to filter
        return [s for s in samples if s.accent and s.accent.lower() == accent.lower()][:limit]
    
    def get_samples_by_duration(
        self,
        language: str,
        min_duration: float,
        max_duration: float
    ) -> List[VoiceSample]:
        """Get voice samples within a specific duration range."""
        samples = self.get_voice_samples(language, limit=100)  # Get more samples to filter
        return [s for s in samples if min_duration <= s.duration <= max_duration]
    
    def download_sample(self, sample: VoiceSample, output_dir: Path) -> Optional[Path]:
        """Download a voice sample to the specified directory."""
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{sample.id}.mp3"
            
            if output_path.exists():
                return output_path
            
            response = requests.get(sample.audio_url)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            return output_path
            
        except Exception as e:
            Utils.log_red(f"Error downloading sample {sample.id}: {e}")
            return None
    
    def get_sample_statistics(self, language: str = "en-US") -> Dict[str, Any]:
        """Get statistics about available samples for a language."""
        try:
            response = self.session.get(f"{self.BASE_URL}/languages/{language}/statistics")
            response.raise_for_status()
            data = response.json()
            
            return {
                "total_samples": data.get("total_samples", 0),
                "total_duration": data.get("total_duration", 0),
                "average_duration": data.get("average_duration", 0),
                "accents": data.get("accents", {}),
                "genders": data.get("genders", {}),
                "age_groups": data.get("age_groups", {})
            }
        except Exception as e:
            Utils.log_red(f"Error getting statistics for {language}: {e}")
            return {} 