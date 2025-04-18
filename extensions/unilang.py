"""Module for interacting with UniLang language learning resources."""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import json
import time
import requests
from bs4 import BeautifulSoup
import re
import os
import logging

from utils.utils import Utils

# Set up logging
logger = logging.getLogger(__name__)

@dataclass
class LanguageResource:
    """Represents a language learning resource from UniLang."""
    id: str
    title: str
    language: str
    resource_type: str
    description: str
    url: str
    difficulty: Optional[str]
    tags: List[str]
    last_accessed: Optional[float] = None


@dataclass
class ForumPost:
    """Represents a forum post from UniLang."""
    id: str
    title: str
    language: str
    author: str
    content: str
    date: str
    url: str
    tags: List[str]
    last_accessed: Optional[float] = None


class UniLang:
    """Handles interactions with UniLang language learning resources."""
    
    BASE_URL = "https://forum.unilang.org"
    RESOURCES_URL = f"{BASE_URL}/resources.php"
    CACHE_DIR = Path("cache/unilang")
    RESOURCES_CACHE = CACHE_DIR / "resources.json"
    FORUM_CACHE = CACHE_DIR / "forum.json"
    CACHE_DURATION = 86400  # 24 hours in seconds
    
    # Language code to forum ID mapping
    FORUM_IDS = {
        "en": "2",  # English
        "de": "3",  # German
        "fr": "4",  # French
        "es": "5",  # Spanish
        "it": "6",  # Italian
        "pt": "7",  # Portuguese
        "ru": "8",  # Russian
        "ja": "9",  # Japanese
        "zh": "10", # Chinese
        "ar": "11"  # Arabic
    }
    
    FORUM_IDS_ = {
        "African Indigenous Languages": 132,
        "Afrikaans": 70,
        "Ancient, Classical and Extinct Languages": 128,
        "Arabic (العربية)": 25,
        "Australian, Austronesian and Papuan Languages": 129,
        "Basque (Euskara)": 57,
        "Bosnian/Croatian/Serbian (Bosanski/Hrvatski/Српски)": 41,
        "Bulgarian (Български)": 81,
        "Catalan/Valencian (Català/Valencià)": 24,
        "Celtic Languages": 126,
        "Central and South American Indigenous Languages": 125,
        "Chinese (中文)": 50,
        "Conlang Translations": 143,
        "Conlangs": 85,
        "Creoles and Pidgins": 127,
        "Culture": 17,
        "Czech (Čeština)": 45,
        "Danish (Dansk)": 29,
        "Dutch (Nederlands)": 38,
        "English": 21,
        "Esperanto": 56,
        "Estonian (Eesti keel)": 53,
        "Faroese (Føroyskt)": 23,
        "Finnish (Suomi)": 46,
        "French (Français)": 35,
        "Frisian (Frysk/Friisk/Fräisk)": 115,
        "Games": 117,
        "General Forums": 110,
        "General Language Forum": 1,
        "Georgian (ქართული)": 22,
        "German (Deutsch)": 30,
        "Greek (Ελληνικά)": 52,
        "Hebrew (עברית)": 34,
        "Hindi/Urdu (हिन्दी/اُردو)": 71,
        "Hungarian (Magyar)": 63,
        "Icelandic (Íslenska)": 31,
        "Indonesian/Malay (Bahasa Indonesia/Bahasa Malaysia)": 60,
        "Italian (Italiano)": 54,
        "Japanese (日本語)": 49,
        "Korean (한국어)": 33,
        "Kurdish (Kurdî/کوردی)": 72,
        "Language Logs and Blogs": 119,
        "Language-specific Forums": 99,
        "Latin (Latina)": 61,
        "Latvian (Latviešu valoda)": 26,
        "Literature": 4,
        "Lithuanian (Lietuvių kalba)": 64,
        "North American Indigenous Languages": 122,
        "Norwegian (Norsk)": 59,
        "Other Languages": 142,
        "Persian/Farsi (فارسی)": 73,
        "Polish (Polski)": 58,
        "Politics and Religion": 5,
        "Portuguese (Português)": 43,
        "Romanian (Română)": 48,
        "Russian (Русский)": 44,
        "Slovak (Slovenský)": 86,
        "Slovenian (Slovenski)": 66,
        "South Asian Languages": 130,
        "South East Asian Languages": 75,
        "Spanish (Español)": 28,
        "Specific Languages": 109,
        "Swedish (Svenska)": 69,
        "Translations": 11,
        "Turkic Languages": 131,
        "Turkish (Türkçe)": 62,
        "Ukrainian (Українська)": 77,
        "Unilang - Information, Input, and Questions": 9,
        "Unilang Information": 140,
        "Uralic Languages": 93,
    }
    
    def __init__(self):
        """Initialize the UniLang client with caching."""
        logger.info("Initializing UniLang client")
        self.resources: Dict[str, List[Dict]] = {}
        self.forum_posts: Dict[str, List[Dict]] = {}
        self._load_cache()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Spracherwerb/1.0"
        })
        logger.info("UniLang client initialized successfully")
    
    def _load_cache(self):
        """Load cached data from disk."""
        try:
            logger.info("Loading UniLang cache")
            if self.RESOURCES_CACHE.exists():
                logger.debug(f"Loading resources cache from {self.RESOURCES_CACHE}")
                with open(self.RESOURCES_CACHE, 'r', encoding='utf-8') as f:
                    self.resources = json.load(f)
                logger.info(f"Loaded {sum(len(v) for v in self.resources.values())} cached resources")
            else:
                logger.warning("Resources cache file not found")
                
            if self.FORUM_CACHE.exists():
                logger.debug(f"Loading forum cache from {self.FORUM_CACHE}")
                with open(self.FORUM_CACHE, 'r', encoding='utf-8') as f:
                    self.forum_posts = json.load(f)
                logger.info(f"Loaded {sum(len(v) for v in self.forum_posts.values())} cached forum posts")
            else:
                logger.warning("Forum cache file not found")
        except Exception as e:
            logger.error(f"Error loading UniLang cache: {e}")
            self.resources = {}
            self.forum_posts = {}
    
    def _save_cache(self):
        """Save data to cache files."""
        try:
            logger.info("Saving UniLang cache")
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            
            logger.debug(f"Saving resources cache to {self.RESOURCES_CACHE}")
            with open(self.RESOURCES_CACHE, 'w', encoding='utf-8') as f:
                json.dump(self.resources, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {sum(len(v) for v in self.resources.values())} resources to cache")
            
            logger.debug(f"Saving forum cache to {self.FORUM_CACHE}")
            with open(self.FORUM_CACHE, 'w', encoding='utf-8') as f:
                json.dump(self.forum_posts, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {sum(len(v) for v in self.forum_posts.values())} forum posts to cache")
        except Exception as e:
            logger.error(f"Error saving UniLang cache: {e}")
    
    def _is_cache_valid(self, data: List[Dict]) -> bool:
        """Check if cached data is still valid."""
        if not data:
            logger.debug("Cache is empty")
            return False
        last_access = max(item.get("last_accessed", 0) for item in data)
        is_valid = (time.time() - last_access) < self.CACHE_DURATION
        logger.debug(f"Cache validity: {is_valid} (last access: {time.time() - last_access:.2f}s ago)")
        return is_valid
    
    def get_language_resources(
        self,
        language: str,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Get language learning resources for a specific language."""
        try:
            logger.info(f"Getting resources for language: {language}")
            
            # Check cache first
            if language in self.resources and self._is_cache_valid(self.resources[language]):
                logger.info(f"Using cached resources for {language}")
                resources = self.resources[language]
                if limit:
                    resources = resources[:limit]
                return resources
            
            # Fetch from website
            logger.info(f"Fetching resources from {self.RESOURCES_URL} for {language}")
            response = self.session.get(f"{self.RESOURCES_URL}?language={language}")
            response.raise_for_status()
            logger.debug(f"Response status: {response.status_code}")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            resources = []
            
            # Parse resource listings
            logger.debug("Parsing resource listings")
            for item in soup.select(".resource-item"):
                resource = {
                    "title": item.select_one(".resource-title").text.strip(),
                    "description": item.select_one(".resource-description").text.strip(),
                    "url": item.select_one("a")["href"],
                    "category": item.select_one(".resource-category").text.strip(),
                    "last_accessed": time.time()
                }
                resources.append(resource)
            
            logger.info(f"Found {len(resources)} resources for {language}")
            
            # Update cache
            self.resources[language] = resources
            self._save_cache()
            
            if limit:
                resources = resources[:limit]
                logger.info(f"Limited to {len(resources)} resources")
            
            return resources
            
        except Exception as e:
            logger.error(f"Error getting resources for {language}: {e}")
            return []
    
    def get_forum_posts(
        self,
        language: str,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Get forum posts related to a specific language."""
        try:
            logger.info(f"Getting forum posts for language: {language}")
            
            # Check cache first
            if language in self.forum_posts and self._is_cache_valid(self.forum_posts[language]):
                logger.info(f"Using cached forum posts for {language}")
                posts = self.forum_posts[language]
                if limit:
                    posts = posts[:limit]
                return posts
            
            # Get forum ID for language
            forum_id = self.FORUM_IDS.get(language)
            if not forum_id:
                logger.error(f"No forum ID found for language: {language}")
                logger.error(f"Available forum IDs: {self.FORUM_IDS}")
                return []
            
            # Fetch from website
            url = f"{self.BASE_URL}/viewforum.php?f={forum_id}"
            logger.info(f"Fetching forum posts from {url}")
            try:
                response = self.session.get(url)
                response.raise_for_status()
                logger.debug(f"Response status: {response.status_code}")
                logger.debug(f"Response headers: {response.headers}")
                logger.debug(f"Response content length: {len(response.text)}")
            except requests.exceptions.HTTPError as e:
                logger.error(f"HTTP error occurred while fetching forum posts: {e}")
                logger.error(f"Response status: {e.response.status_code if hasattr(e, 'response') else 'No response'}")
                logger.error(f"Response headers: {e.response.headers if hasattr(e, 'response') else 'No headers'}")
                logger.error(f"Response content: {e.response.text if hasattr(e, 'response') else 'No content'}")
                return []
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error occurred while fetching forum posts: {e}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            posts = []
            
            # Parse forum posts
            logger.debug("Parsing forum posts")
            topic_rows = soup.select(".topic-row")
            logger.debug(f"Found {len(topic_rows)} topic rows in HTML")
            
            for post in topic_rows:
                try:
                    title_elem = post.select_one(".topic-title")
                    author_elem = post.select_one(".topic-author")
                    date_elem = post.select_one(".topic-date")
                    link_elem = post.select_one("a")
                    
                    if not all([title_elem, author_elem, date_elem, link_elem]):
                        logger.warning(f"Missing required elements in forum post: title={title_elem}, author={author_elem}, date={date_elem}, link={link_elem}")
                        continue
                        
                    post_data = {
                        "title": title_elem.text.strip(),
                        "author": author_elem.text.strip(),
                        "date": date_elem.text.strip(),
                        "url": link_elem["href"],
                        "last_accessed": time.time()
                    }
                    posts.append(post_data)
                except Exception as e:
                    logger.error(f"Error parsing forum post: {e}")
                    continue
            
            logger.info(f"Successfully parsed {len(posts)} forum posts for {language}")
            
            # Update cache
            if posts:  # Only update cache if we successfully got posts
                self.forum_posts[language] = posts
                self._save_cache()
                logger.info(f"Updated cache with {len(posts)} forum posts for {language}")
            else:
                logger.warning(f"No forum posts found for {language}, cache not updated")
            
            if limit:
                posts = posts[:limit]
                logger.info(f"Limited to {len(posts)} posts")
            
            return posts
            
        except Exception as e:
            logger.error(f"Error getting forum posts for {language}: {e}")
            logger.error(f"Error type: {type(e)}")
            logger.error(f"Error details: {str(e)}")
            return []
    
    def search_resources(
        self,
        query: str,
        language: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Search for language learning resources."""
        try:
            logger.info(f"Searching resources for query: {query}")
            
            # Get all resources if no language specified
            if language:
                logger.info(f"Searching in language: {language}")
                resources = self.get_language_resources(language)
            else:
                logger.info("Searching across all languages")
                resources = []
                for lang in self.resources:
                    resources.extend(self.get_language_resources(lang))
            
            # Filter by query
            logger.debug("Filtering resources by query")
            results = [
                r for r in resources
                if query.lower() in r["title"].lower() or
                query.lower() in r["description"].lower()
            ]
            
            logger.info(f"Found {len(results)} matching resources")
            
            if limit:
                results = results[:limit]
                logger.info(f"Limited to {len(results)} results")
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching resources: {e}")
            return []
    
    def get_resource_categories(self, language: str) -> List[str]:
        """Get available resource categories for a language."""
        try:
            logger.info(f"Getting resource categories for language: {language}")
            resources = self.get_language_resources(language)
            categories = {r["category"] for r in resources}
            logger.info(f"Found {len(categories)} categories for {language}")
            return sorted(list(categories))
        except Exception as e:
            logger.error(f"Error getting categories for {language}: {e}")
            return [] 