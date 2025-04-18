"""Module for interacting with Wikimedia Commons API."""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import json
import time
import requests
from urllib.parse import quote

from utils.utils import Utils


@dataclass
class MediaItem:
    """Represents a media item from Wikimedia Commons."""
    id: str
    title: str
    description: str
    url: str
    thumbnail_url: Optional[str]
    mime_type: str
    width: Optional[int]
    height: Optional[int]
    size: Optional[int]
    categories: List[str]
    languages: List[str]
    license: str
    author: str
    last_accessed: Optional[float] = None


class WikimediaCommons:
    """Handles interactions with Wikimedia Commons API."""
    
    BASE_URL = "https://commons.wikimedia.org/w/api.php"
    CACHE_DIR = Path("cache/wikimedia_commons")
    CACHE_FILE = CACHE_DIR / "media.json"
    CACHE_DURATION = 86400  # 24 hours in seconds
    
    def __init__(self):
        """Initialize the Wikimedia Commons client with caching."""
        self.media: Dict[str, List[MediaItem]] = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load cached media items from disk."""
        try:
            if self.CACHE_FILE.exists():
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.media = {
                        query: [MediaItem(**item_data) for item_data in items]
                        for query, items in data.items()
                    }
        except Exception as e:
            Utils.log_red(f"Error loading Wikimedia Commons cache: {e}")
            self.media = {}
    
    def _save_cache(self):
        """Save media items to cache file."""
        try:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(
                    {query: [item.__dict__ for item in items]
                     for query, items in self.media.items()},
                    f,
                    ensure_ascii=False,
                    indent=2
                )
        except Exception as e:
            Utils.log_red(f"Error saving Wikimedia Commons cache: {e}")
    
    def _is_cache_valid(self, items: List[MediaItem]) -> bool:
        """Check if cached media items are still valid."""
        if not items:
            return False
        return (time.time() - max(i.last_accessed for i in items)) < self.CACHE_DURATION
    
    def search_media(
        self,
        query: str,
        language: Optional[str] = None,
        media_type: Optional[str] = None,
        limit: int = 10
    ) -> List[MediaItem]:
        """Search for media items on Wikimedia Commons."""
        cache_key = f"{query}_{language}_{media_type}"
        
        # Check cache first
        if cache_key in self.media and self._is_cache_valid(self.media[cache_key]):
            return self.media[cache_key][:limit]
        
        try:
            params = {
                "action": "query",
                "format": "json",
                "generator": "search",
                "gsrsearch": query,
                "gsrnamespace": "6",  # File namespace
                "gsrlimit": limit,
                "prop": "imageinfo|categories|langlinks",
                "iiprop": "url|size|mime|dimensions",
                "cllimit": "max",
                "lllimit": "max"
            }
            
            if language:
                params["lllang"] = language
            
            response = requests.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            items = []
            for page in data.get("query", {}).get("pages", {}).values():
                if "imageinfo" not in page:
                    continue
                
                info = page["imageinfo"][0]
                if media_type and not info["mime"].startswith(media_type):
                    continue
                
                item = MediaItem(
                    id=page["pageid"],
                    title=page["title"],
                    description=info.get("description", ""),
                    url=info["url"],
                    thumbnail_url=info.get("thumburl"),
                    mime_type=info["mime"],
                    width=info.get("width"),
                    height=info.get("height"),
                    size=info.get("size"),
                    categories=[cat["title"] for cat in page.get("categories", [])],
                    languages=[lang["lang"] for lang in page.get("langlinks", [])],
                    license=info.get("extmetadata", {}).get("License", {}).get("value", ""),
                    author=info.get("extmetadata", {}).get("Artist", {}).get("value", ""),
                    last_accessed=time.time()
                )
                items.append(item)
            
            self.media[cache_key] = items
            self._save_cache()
            
            return items
            
        except Exception as e:
            Utils.log_red(f"Error searching Wikimedia Commons: {e}")
            return []
    
    def get_media_by_category(
        self,
        category: str,
        language: Optional[str] = None,
        media_type: Optional[str] = None,
        limit: int = 10
    ) -> List[MediaItem]:
        """Get media items from a specific category."""
        try:
            params = {
                "action": "query",
                "format": "json",
                "list": "categorymembers",
                "cmtitle": f"Category:{category}",
                "cmnamespace": "6",  # File namespace
                "cmlimit": limit,
                "prop": "imageinfo|categories|langlinks",
                "iiprop": "url|size|mime|dimensions",
                "cllimit": "max",
                "lllimit": "max"
            }
            
            if language:
                params["lllang"] = language
            
            response = requests.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            items = []
            for member in data.get("query", {}).get("categorymembers", []):
                # Get detailed information for each file
                file_params = {
                    "action": "query",
                    "format": "json",
                    "titles": member["title"],
                    "prop": "imageinfo|categories|langlinks",
                    "iiprop": "url|size|mime|dimensions",
                    "cllimit": "max",
                    "lllimit": "max"
                }
                
                file_response = requests.get(self.BASE_URL, params=file_params)
                file_response.raise_for_status()
                file_data = file_response.json()
                
                page = next(iter(file_data.get("query", {}).get("pages", {}).values()))
                if "imageinfo" not in page:
                    continue
                
                info = page["imageinfo"][0]
                if media_type and not info["mime"].startswith(media_type):
                    continue
                
                item = MediaItem(
                    id=page["pageid"],
                    title=page["title"],
                    description=info.get("description", ""),
                    url=info["url"],
                    thumbnail_url=info.get("thumburl"),
                    mime_type=info["mime"],
                    width=info.get("width"),
                    height=info.get("height"),
                    size=info.get("size"),
                    categories=[cat["title"] for cat in page.get("categories", [])],
                    languages=[lang["lang"] for lang in page.get("langlinks", [])],
                    license=info.get("extmetadata", {}).get("License", {}).get("value", ""),
                    author=info.get("extmetadata", {}).get("Artist", {}).get("value", ""),
                    last_accessed=time.time()
                )
                items.append(item)
            
            return items
            
        except Exception as e:
            Utils.log_red(f"Error getting media by category: {e}")
            return []
    
    def download_media(self, item: MediaItem, output_dir: Path) -> Optional[Path]:
        """Download a media item to the specified directory."""
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            file_extension = item.mime_type.split('/')[-1]
            output_path = output_dir / f"{item.id}.{file_extension}"
            
            if output_path.exists():
                return output_path
            
            response = requests.get(item.url)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            return output_path
            
        except Exception as e:
            Utils.log_red(f"Error downloading media {item.id}: {e}")
            return None
    
    def get_media_statistics(self, query: str) -> Dict[str, Any]:
        """Get statistics about media items matching a query."""
        items = self.search_media(query, limit=1000)  # Get more items for stats
        
        if not items:
            return {}
        
        stats = {
            "total_items": len(items),
            "media_types": {},
            "languages": {},
            "licenses": {},
            "categories": {}
        }
        
        for item in items:
            stats["media_types"][item.mime_type] = stats["media_types"].get(item.mime_type, 0) + 1
            for lang in item.languages:
                stats["languages"][lang] = stats["languages"].get(lang, 0) + 1
            stats["licenses"][item.license] = stats["licenses"].get(item.license, 0) + 1
            for category in item.categories:
                stats["categories"][category] = stats["categories"].get(category, 0) + 1
        
        return stats 