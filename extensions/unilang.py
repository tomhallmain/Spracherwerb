"""Module for interacting with UniLang language learning resources."""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import json
import time
import requests
from bs4 import BeautifulSoup
import re

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
    RESOURCES_URL = "https://unilang.org/resources.php"
    CACHE_DIR = Path("cache/unilang")
    RESOURCES_CACHE = CACHE_DIR / "resources.json"
    FORUM_CACHE = CACHE_DIR / "forum.json"
    CACHE_DURATION = 86400  # 24 hours in seconds
    
    def __init__(self):
        """Initialize the UniLang client with caching."""
        self.resources: Dict[str, List[LanguageResource]] = {}
        self.forum_posts: Dict[str, List[ForumPost]] = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load cached data from disk."""
        try:
            if self.RESOURCES_CACHE.exists():
                with open(self.RESOURCES_CACHE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.resources = {
                        lang: [LanguageResource(**resource_data) for resource_data in resources]
                        for lang, resources in data.items()
                    }
            
            if self.FORUM_CACHE.exists():
                with open(self.FORUM_CACHE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.forum_posts = {
                        lang: [ForumPost(**post_data) for post_data in posts]
                        for lang, posts in data.items()
                    }
        except Exception as e:
            Utils.log_red(f"Error loading UniLang cache: {e}")
            self.resources = {}
            self.forum_posts = {}
    
    def _save_cache(self):
        """Save data to cache files."""
        try:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            
            with open(self.RESOURCES_CACHE, 'w', encoding='utf-8') as f:
                json.dump(
                    {lang: [resource.__dict__ for resource in resources]
                     for lang, resources in self.resources.items()},
                    f,
                    ensure_ascii=False,
                    indent=2
                )
            
            with open(self.FORUM_CACHE, 'w', encoding='utf-8') as f:
                json.dump(
                    {lang: [post.__dict__ for post in posts]
                     for lang, posts in self.forum_posts.items()},
                    f,
                    ensure_ascii=False,
                    indent=2
                )
        except Exception as e:
            Utils.log_red(f"Error saving UniLang cache: {e}")
    
    def _is_cache_valid(self, items: List[Any]) -> bool:
        """Check if cached items are still valid."""
        if not items:
            return False
        return (time.time() - max(i.last_accessed for i in items)) < self.CACHE_DURATION
    
    def get_language_resources(
        self,
        language: str,
        resource_type: Optional[str] = None,
        difficulty: Optional[str] = None
    ) -> List[LanguageResource]:
        """Get language learning resources for a specific language."""
        cache_key = language
        
        # Check cache first
        if cache_key in self.resources and self._is_cache_valid(self.resources[cache_key]):
            resources = self.resources[cache_key]
        else:
            try:
                response = requests.get(self.RESOURCES_URL, params={"lang": language})
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                
                resources = []
                for item in soup.find_all('div', class_='resource-item'):
                    title_elem = item.find('h3')
                    if not title_elem:
                        continue
                    
                    resource = LanguageResource(
                        id=item.get('id', ''),
                        title=title_elem.text.strip(),
                        language=language,
                        resource_type=item.get('data-type', ''),
                        description=item.find('p', class_='description').text.strip() if item.find('p', class_='description') else '',
                        url=item.find('a')['href'] if item.find('a') else '',
                        difficulty=item.get('data-difficulty'),
                        tags=[tag.text.strip() for tag in item.find_all('span', class_='tag')],
                        last_accessed=time.time()
                    )
                    resources.append(resource)
                
                self.resources[cache_key] = resources
                self._save_cache()
                
            except Exception as e:
                Utils.log_red(f"Error getting UniLang resources for {language}: {e}")
                return []
        
        # Apply filters
        if resource_type:
            resources = [r for r in resources if r.resource_type == resource_type]
        if difficulty:
            resources = [r for r in resources if r.difficulty == difficulty]
        
        return resources
    
    def get_forum_posts(
        self,
        language: str,
        limit: int = 10,
        tag: Optional[str] = None
    ) -> List[ForumPost]:
        """Get forum posts for a specific language."""
        cache_key = language
        
        # Check cache first
        if cache_key in self.forum_posts and self._is_cache_valid(self.forum_posts[cache_key]):
            posts = self.forum_posts[cache_key]
        else:
            try:
                response = requests.get(f"{self.BASE_URL}/viewforum.php", params={"f": language})
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                
                posts = []
                for item in soup.find_all('div', class_='forum-post'):
                    post = ForumPost(
                        id=item.get('id', ''),
                        title=item.find('h3').text.strip(),
                        language=language,
                        author=item.find('span', class_='author').text.strip(),
                        content=item.find('div', class_='content').text.strip(),
                        date=item.find('span', class_='date').text.strip(),
                        url=item.find('a')['href'] if item.find('a') else '',
                        tags=[tag.text.strip() for tag in item.find_all('span', class_='tag')],
                        last_accessed=time.time()
                    )
                    posts.append(post)
                
                self.forum_posts[cache_key] = posts
                self._save_cache()
                
            except Exception as e:
                Utils.log_red(f"Error getting UniLang forum posts for {language}: {e}")
                return []
        
        # Apply filters
        if tag:
            posts = [p for p in posts if tag in p.tags]
        
        return posts[:limit]
    
    def search_resources(
        self,
        query: str,
        language: Optional[str] = None
    ) -> List[LanguageResource]:
        """Search for language learning resources."""
        all_resources = []
        if language:
            all_resources.extend(self.get_language_resources(language))
        else:
            for lang in self.resources.keys():
                all_resources.extend(self.get_language_resources(lang))
        
        query = query.lower()
        return [
            r for r in all_resources
            if query in r.title.lower() or
               query in r.description.lower() or
               any(query in tag.lower() for tag in r.tags)
        ]
    
    def get_resource_categories(self, language: str) -> Dict[str, int]:
        """Get categories and counts of resources for a language."""
        resources = self.get_language_resources(language)
        categories = {}
        
        for resource in resources:
            if resource.resource_type:
                categories[resource.resource_type] = categories.get(resource.resource_type, 0) + 1
        
        return categories 