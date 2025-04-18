"""Module for interacting with Mozilla's Common Voice dataset."""

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
    """Handles interactions with the Common Voice dataset."""
    
    BASE_URL = "https://commonvoice.mozilla.org/api/v1"
    CACHE_DIR = Path("cache/common_voice")
    CACHE_FILE = CACHE_DIR / "samples.json"
    CACHE_DURATION = 86400  # 24 hours in seconds
    
    def __init__(self):
        """Initialize the Common Voice client with caching."""
        self.samples: Dict[str, List[VoiceSample]] = {}
        self._load_cache()
    
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
        """Get a list of available languages in Common Voice."""
        try:
            response = requests.get(f"{self.BASE_URL}/languages")
            response.raise_for_status()
            data = response.json()
            return [lang["code"] for lang in data]
        except Exception as e:
            Utils.log_red(f"Error getting available languages: {e}")
            return []
    
    def get_voice_samples(
        self,
        language: str,
        limit: int = 10,
        min_duration: float = 1.0,
        max_duration: float = 10.0,
        min_votes: int = 3
    ) -> List[VoiceSample]:
        """Get voice samples for a specific language."""
        cache_key = language
        
        # Check cache first
        if cache_key in self.samples and self._is_cache_valid(self.samples[cache_key]):
            return self.samples[cache_key][:limit]
        
        try:
            params = {
                "language": language,
                "limit": limit,
                "min_duration": min_duration,
                "max_duration": max_duration,
                "min_votes": min_votes
            }
            
            response = requests.get(f"{self.BASE_URL}/samples", params=params)
            response.raise_for_status()
            data = response.json()
            
            samples = []
            for item in data.get("items", []):
                sample = VoiceSample(
                    id=item["id"],
                    text=item["text"],
                    language=item["language"],
                    accent=item.get("accent"),
                    age=item.get("age"),
                    gender=item.get("gender"),
                    duration=float(item["duration"]),
                    audio_url=item["audio_url"],
                    votes=item.get("votes", {}),
                    last_accessed=time.time()
                )
                samples.append(sample)
            
            self.samples[cache_key] = samples
            self._save_cache()
            
            return samples
            
        except Exception as e:
            Utils.log_red(f"Error getting Common Voice samples for {language}: {e}")
            return []
    
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
    
    def get_sample_statistics(self, language: str) -> Dict[str, Any]:
        """Get statistics about voice samples for a language."""
        samples = self.get_voice_samples(language, limit=1000)  # Get more samples for stats
        
        if not samples:
            return {}
        
        stats = {
            "total_samples": len(samples),
            "total_duration": sum(s.duration for s in samples),
            "average_duration": sum(s.duration for s in samples) / len(samples),
            "accents": {},
            "genders": {},
            "age_groups": {}
        }
        
        for sample in samples:
            if sample.accent:
                stats["accents"][sample.accent] = stats["accents"].get(sample.accent, 0) + 1
            if sample.gender:
                stats["genders"][sample.gender] = stats["genders"].get(sample.gender, 0) + 1
            if sample.age:
                stats["age_groups"][sample.age] = stats["age_groups"].get(sample.age, 0) + 1
        
        return stats 