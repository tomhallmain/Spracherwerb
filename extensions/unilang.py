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

from utils.utils import Utils

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
        "en": "21",  # English
        "de": "30",  # German (Deutsch)
        "fr": "35",  # French (Français)
        "es": "28",  # Spanish (Español)
        "it": "54",  # Italian (Italiano)
        "pt": "43",  # Portuguese (Português)
        "ru": "44",  # Russian (Русский)
        "ja": "49",  # Japanese (日本語)
        "zh": "50",  # Chinese (中文)
        "ar": "25",  # Arabic (العربية)
        "af": "70",  # Afrikaans
        "eu": "57",  # Basque (Euskara)
        "bs": "41",  # Bosnian/Croatian/Serbian (Bosanski/Hrvatski/Српски)
        "bg": "81",  # Bulgarian (Български)
        "ca": "24",  # Catalan/Valencian (Català/Valencià)
        "cs": "45",  # Czech (Čeština)
        "da": "29",  # Danish (Dansk)
        "nl": "38",  # Dutch (Nederlands)
        "eo": "56",  # Esperanto
        "et": "53",  # Estonian (Eesti keel)
        "fo": "23",  # Faroese (Føroyskt)
        "fi": "46",  # Finnish (Suomi)
        "fy": "115", # Frisian (Frysk/Friisk/Fräisk)
        "ka": "22",  # Georgian (ქართული)
        "el": "52",  # Greek (Ελληνικά)
        "he": "34",  # Hebrew (עברית)
        "hi": "71",  # Hindi/Urdu (हिन्दी/اُردو)
        "hu": "63",  # Hungarian (Magyar)
        "is": "31",  # Icelandic (Íslenska)
        "id": "60",  # Indonesian/Malay (Bahasa Indonesia/Bahasa Malaysia)
        "ko": "33",  # Korean (한국어)
        "ku": "72",  # Kurdish (Kurdî/کوردی)
        "la": "61",  # Latin (Latina)
        "lv": "26",  # Latvian (Latviešu valoda)
        "lt": "64",  # Lithuanian (Lietuvių kalba)
        "no": "59",  # Norwegian (Norsk)
        "fa": "73",  # Persian/Farsi (فارسی)
        "pl": "58",  # Polish (Polski)
        "ro": "48",  # Romanian (Română)
        "sk": "86",  # Slovak (Slovenský)
        "sl": "66",  # Slovenian (Slovenski)
        "sv": "69",  # Swedish (Svenska)
        "tr": "62",  # Turkish (Türkçe)
        "uk": "77",  # Ukrainian (Українська)
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
        Utils.log("Initializing UniLang client")
        self.resources: Dict[str, List[Dict]] = {}
        self.forum_posts: Dict[str, List[Dict]] = {}
        self._load_cache()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Spracherwerb/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0"
        })
        Utils.log("UniLang client initialized successfully")
    
    def _load_cache(self):
        """Load cached data from disk."""
        try:
            Utils.log("Loading UniLang cache")
            if self.RESOURCES_CACHE.exists():
                Utils.log_debug(f"Loading resources cache from {self.RESOURCES_CACHE}")
                with open(self.RESOURCES_CACHE, 'r', encoding='utf-8') as f:
                    self.resources = json.load(f)
                Utils.log(f"Loaded {sum(len(v) for v in self.resources.values())} cached resources")
            else:
                Utils.log_yellow("Resources cache file not found")
                
            if self.FORUM_CACHE.exists():
                Utils.log_debug(f"Loading forum cache from {self.FORUM_CACHE}")
                with open(self.FORUM_CACHE, 'r', encoding='utf-8') as f:
                    self.forum_posts = json.load(f)
                Utils.log(f"Loaded {sum(len(v) for v in self.forum_posts.values())} cached forum posts")
            else:
                Utils.log_yellow("Forum cache file not found")
        except Exception as e:
            Utils.log_red(f"Error loading UniLang cache: {e}")
            self.resources = {}
            self.forum_posts = {}
    
    def _save_cache(self):
        """Save data to cache files."""
        try:
            Utils.log("Saving UniLang cache")
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            
            Utils.log_debug(f"Saving resources cache to {self.RESOURCES_CACHE}")
            with open(self.RESOURCES_CACHE, 'w', encoding='utf-8') as f:
                json.dump(self.resources, f, ensure_ascii=False, indent=2)
            Utils.log(f"Saved {sum(len(v) for v in self.resources.values())} resources to cache")
            
            Utils.log_debug(f"Saving forum cache to {self.FORUM_CACHE}")
            with open(self.FORUM_CACHE, 'w', encoding='utf-8') as f:
                json.dump(self.forum_posts, f, ensure_ascii=False, indent=2)
            Utils.log(f"Saved {sum(len(v) for v in self.forum_posts.values())} forum posts to cache")
        except Exception as e:
            Utils.log_red(f"Error saving UniLang cache: {e}")
    
    def _is_cache_valid(self, data: List[Dict]) -> bool:
        """Check if cached data is still valid."""
        if not data:
            Utils.log_debug("Cache is empty")
            return False
        last_access = max(item.get("last_accessed", 0) for item in data)
        is_valid = (time.time() - last_access) < self.CACHE_DURATION
        Utils.log_debug(f"Cache validity: {is_valid} (last access: {time.time() - last_access:.2f}s ago)")
        return is_valid
    
    def get_language_resources(
        self,
        language: str,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Get language learning resources for a specific language."""
        try:
            Utils.log(f"Getting resources for language: {language}")
            
            # Check cache first
            if language in self.resources and self._is_cache_valid(self.resources[language]):
                Utils.log(f"Using cached resources for {language}")
                resources = self.resources[language]
                if limit:
                    resources = resources[:limit]
                return resources
            
            # Fetch from website
            Utils.log(f"Fetching resources from {self.RESOURCES_URL} for {language}")
            response = self.session.get(f"{self.RESOURCES_URL}?language={language}")
            response.raise_for_status()
            Utils.log_debug(f"Response status: {response.status_code}")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            resources = []
            
            # Parse resource listings
            Utils.log_debug("Parsing resource listings")
            for item in soup.select(".resource-item"):
                resource = {
                    "title": item.select_one(".resource-title").text.strip(),
                    "description": item.select_one(".resource-description").text.strip(),
                    "url": item.select_one("a")["href"],
                    "category": item.select_one(".resource-category").text.strip(),
                    "last_accessed": time.time()
                }
                resources.append(resource)
            
            Utils.log(f"Found {len(resources)} resources for {language}")
            
            # Update cache
            self.resources[language] = resources
            self._save_cache()
            
            if limit:
                resources = resources[:limit]
                Utils.log(f"Limited to {len(resources)} resources")
            
            return resources
            
        except Exception as e:
            Utils.log_red(f"Error getting resources for {language}: {e}")
            return []
    
    def get_forum_posts(
        self,
        language: str,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Get forum posts related to a specific language."""
        try:
            Utils.log(f"Getting forum posts for language: {language}")
            
            # Check cache first
            if language in self.forum_posts and self._is_cache_valid(self.forum_posts[language]):
                Utils.log(f"Using cached forum posts for {language}")
                posts = self.forum_posts[language]
                if limit:
                    posts = posts[:limit]
                return posts
            
            # Get forum ID for language
            forum_id = self.FORUM_IDS.get(language)
            if not forum_id:
                Utils.log_red(f"No forum ID found for language: {language}")
                Utils.log_red(f"Available forum IDs: {self.FORUM_IDS}")
                return []
            
            # Fetch from website
            url = f"{self.BASE_URL}/viewforum.php?f={forum_id}&start=0"
            Utils.log(f"Fetching forum posts from {url}")
            try:
                # First visit the main page to get session cookies
                self.session.get(self.BASE_URL)
                
                # Then fetch the forum page
                response = self.session.get(url)
                response.raise_for_status()
                Utils.log_debug(f"Response status: {response.status_code}")
                Utils.log_debug(f"Response headers: {response.headers}")
                Utils.log_debug(f"Response content length: {len(response.text)}")
                
                # Save response for debugging
                with open("forum_response.html", "w", encoding="utf-8") as f:
                    f.write(response.text)
                
            except requests.exceptions.HTTPError as e:
                Utils.log_red(f"HTTP error occurred while fetching forum posts: {e}")
                Utils.log_red(f"Response status: {e.response.status_code if hasattr(e, 'response') else 'No response'}")
                Utils.log_red(f"Response headers: {e.response.headers if hasattr(e, 'response') else 'No headers'}")
                Utils.log_red(f"Response content: {e.response.text if hasattr(e, 'response') else 'No content'}")
                return []
            except requests.exceptions.RequestException as e:
                Utils.log_red(f"Request error occurred while fetching forum posts: {e}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            posts = []
            
            # Parse forum posts
            Utils.log_debug("Parsing forum posts")
            
            # Find all topic rows
            topic_rows = soup.select("li.row")
            Utils.log_debug(f"Found {len(topic_rows)} topic rows in HTML")
            
            for post in topic_rows:
                try:
                    # Get the title and link
                    title_elem = post.select_one("a.topictitle")
                    if not title_elem:
                        Utils.log_yellow("No title element found in forum post")
                        continue
                    
                    # Get the author from either the responsive-hide or responsive-show div
                    author_elem = post.select_one("div.responsive-hide a.username, div.responsive-show a.username")
                    if not author_elem:
                        Utils.log_yellow("No author element found in forum post")
                        continue
                    
                    # Get the date from the lastpost span
                    date_elem = post.select_one("dd.lastpost span")
                    if not date_elem:
                        Utils.log_yellow("No date element found in forum post")
                        continue
                    
                    # Extract the date text, which is after the last <br> tag
                    date_text = date_elem.get_text().split("»")[-1].strip()
                    
                    post_data = {
                        "title": title_elem.text.strip(),
                        "author": author_elem.text.strip(),
                        "date": date_text,
                        "url": title_elem["href"],
                        "last_accessed": time.time()
                    }
                    posts.append(post_data)
                    Utils.log_debug(f"Successfully parsed post: {post_data['title']}")
                    
                    # Apply limit during parsing
                    if limit and len(posts) >= limit:
                        Utils.log(f"Reached limit of {limit} posts")
                        break
                        
                except Exception as e:
                    Utils.log_red(f"Error parsing forum post: {e}")
                    continue
            
            # Only update cache if we successfully got posts
            if posts:
                Utils.log(f"Successfully parsed {len(posts)} forum posts for {language}")
                self.forum_posts[language] = posts
                self._save_cache()
                Utils.log(f"Updated cache with {len(posts)} forum posts for {language}")
            else:
                Utils.log_yellow(f"No forum posts found for {language}, cache not updated")
                # Don't cache empty results
                return []
            
            return posts
            
        except Exception as e:
            Utils.log_red(f"Error getting forum posts for {language}: {e}")
            Utils.log_red(f"Error type: {type(e)}")
            Utils.log_red(f"Error details: {str(e)}")
            return []
    
    def search_resources(
        self,
        query: str,
        language: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Search for language learning resources."""
        try:
            Utils.log(f"Searching resources for query: {query}")
            
            # Get all resources if no language specified
            if language:
                Utils.log(f"Searching in language: {language}")
                resources = self.get_language_resources(language)
            else:
                Utils.log("Searching across all languages")
                resources = []
                for lang in self.resources:
                    resources.extend(self.get_language_resources(lang))
            
            # Filter by query
            Utils.log_debug("Filtering resources by query")
            results = [
                r for r in resources
                if query.lower() in r["title"].lower() or
                query.lower() in r["description"].lower()
            ]
            
            Utils.log(f"Found {len(results)} matching resources")
            
            if limit:
                results = results[:limit]
                Utils.log(f"Limited to {len(results)} results")
            
            return results
            
        except Exception as e:
            Utils.log_red(f"Error searching resources: {e}")
            return []
    
    def get_resource_categories(self, language: str) -> List[str]:
        """Get available resource categories for a language."""
        try:
            Utils.log(f"Getting resource categories for language: {language}")
            resources = self.get_language_resources(language)
            categories = {r["category"] for r in resources}
            Utils.log(f"Found {len(categories)} categories for {language}")
            return sorted(list(categories))
        except Exception as e:
            Utils.log_red(f"Error getting categories for {language}: {e}")
            return [] 