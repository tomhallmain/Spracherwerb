"""Module for interacting with Wiktionary's dictionary database."""

import requests
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path
import json
import time
import re

from utils.utils import Utils


@dataclass
class WiktionaryEntry:
    """Represents a word entry from Wiktionary."""
    word: str
    language: str
    part_of_speech: str
    definitions: List[str]
    etymology: Optional[str] = None
    pronunciation: Optional[str] = None
    examples: List[str] = None
    related_words: List[str] = None
    last_accessed: Optional[float] = None


class Wiktionary:
    """Handles interactions with Wiktionary's dictionary database."""
    
    BASE_URL = "https://en.wiktionary.org/w/api.php"
    CACHE_DIR = Path("cache/wiktionary")
    CACHE_FILE = CACHE_DIR / "entries.json"
    CACHE_DURATION = 86400  # 24 hours in seconds
    
    def __init__(self):
        """Initialize the Wiktionary client with caching."""
        self.entries: Dict[str, WiktionaryEntry] = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load cached entry data from disk."""
        try:
            if self.CACHE_FILE.exists():
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.entries = {
                        word: WiktionaryEntry(**entry_data)
                        for word, entry_data in data.items()
                    }
        except Exception as e:
            Utils.log_red(f"Error loading Wiktionary cache: {e}")
            self.entries = {}
    
    def _save_cache(self):
        """Save entry data to cache file."""
        try:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(
                    {word: entry.__dict__ 
                     for word, entry in self.entries.items()},
                    f,
                    ensure_ascii=False,
                    indent=2
                )
        except Exception as e:
            Utils.log_red(f"Error saving Wiktionary cache: {e}")
    
    def _is_cache_valid(self, entry: WiktionaryEntry) -> bool:
        """Check if cached entry data is still valid."""
        if not entry.last_accessed:
            return False
        return (time.time() - entry.last_accessed) < self.CACHE_DURATION
    
    def get_word_entry(
        self,
        word: str,
        language: str = "en",
        include_etymology: bool = True,
        include_examples: bool = True
    ) -> Optional[WiktionaryEntry]:
        """Get a word entry from Wiktionary."""
        cache_key = f"{word}_{language}"
        
        # Check cache first
        if cache_key in self.entries and self._is_cache_valid(self.entries[cache_key]):
            return self.entries[cache_key]
        
        try:
            params = {
                "action": "parse",
                "page": word,
                "format": "json",
                "prop": "text"
            }
            
            response = requests.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            if "error" in data:
                return None
            
            content = data["parse"]["text"]["*"]
            
            # Parse the content
            entry = self._parse_wiktionary_content(
                content,
                word,
                language,
                include_etymology,
                include_examples
            )
            
            if entry:
                self.entries[cache_key] = entry
                self._save_cache()
            
            return entry
            
        except Exception as e:
            Utils.log_red(f"Error getting Wiktionary entry for {word}: {e}")
            return None
    
    def _parse_wiktionary_content(
        self,
        content: str,
        word: str,
        language: str,
        include_etymology: bool,
        include_examples: bool
    ) -> Optional[WiktionaryEntry]:
        """Parse Wiktionary page content into a WiktionaryEntry object."""
        try:
            # Find the language section
            lang_section = re.search(
                rf'<h2><span class="mw-headline" id="{language}">.*?</h2>(.*?)(?=<h2>|$)',
                content,
                re.DOTALL
            )
            
            if not lang_section:
                return None
            
            content = lang_section.group(1)
            
            # Extract part of speech
            pos_match = re.search(r'<h3><span class="mw-headline" id=".*?">(.*?)</span></h3>', content)
            part_of_speech = pos_match.group(1) if pos_match else "unknown"
            
            # Extract definitions
            definitions = []
            def_matches = re.finditer(r'<ol>.*?</ol>', content, re.DOTALL)
            for match in def_matches:
                def_items = re.finditer(r'<li>(.*?)</li>', match.group(0))
                definitions.extend(item.group(1) for item in def_items)
            
            # Extract etymology if requested
            etymology = None
            if include_etymology:
                etym_match = re.search(
                    r'<h3><span class="mw-headline" id="Etymology">.*?</h3>(.*?)(?=<h3>|$)',
                    content,
                    re.DOTALL
                )
                if etym_match:
                    etymology = re.sub(r'<[^>]+>', '', etym_match.group(1)).strip()
            
            # Extract pronunciation
            pron_match = re.search(
                r'<h3><span class="mw-headline" id="Pronunciation">.*?</h3>(.*?)(?=<h3>|$)',
                content,
                re.DOTALL
            )
            pronunciation = None
            if pron_match:
                pron_text = re.sub(r'<[^>]+>', '', pron_match.group(1)).strip()
                pronunciation = pron_text.split('\n')[0] if pron_text else None
            
            # Extract examples if requested
            examples = []
            if include_examples:
                example_matches = re.finditer(
                    r'<dl>.*?</dl>',
                    content,
                    re.DOTALL
                )
                for match in example_matches:
                    example_items = re.finditer(r'<dd>(.*?)</dd>', match.group(0))
                    examples.extend(
                        re.sub(r'<[^>]+>', '', item.group(1)).strip()
                        for item in example_items
                    )
            
            # Extract related words
            related = []
            related_matches = re.finditer(
                r'<h3><span class="mw-headline" id="Related_terms">.*?</h3>(.*?)(?=<h3>|$)',
                content,
                re.DOTALL
            )
            for match in related_matches:
                related_items = re.finditer(r'<li><a[^>]+>(.*?)</a></li>', match.group(0))
                related.extend(item.group(1) for item in related_items)
            
            return WiktionaryEntry(
                word=word,
                language=language,
                part_of_speech=part_of_speech,
                definitions=definitions,
                etymology=etymology,
                pronunciation=pronunciation,
                examples=examples,
                related_words=related,
                last_accessed=time.time()
            )
            
        except Exception as e:
            Utils.log_red(f"Error parsing Wiktionary content: {e}")
            return None
    
    def get_word_forms(self, word: str, language: str = "en") -> Dict[str, List[str]]:
        """Get different forms of a word (e.g., conjugations, declensions)."""
        entry = self.get_word_entry(word, language)
        if not entry:
            return {}
        
        forms = {}
        
        # Extract conjugation/declension tables
        table_matches = re.finditer(
            r'<table class="inflection-table">.*?</table>',
            entry.content,
            re.DOTALL
        )
        
        for table in table_matches:
            # Extract form name and values
            form_matches = re.finditer(
                r'<th[^>]*>(.*?)</th>.*?<td[^>]*>(.*?)</td>',
                table.group(0),
                re.DOTALL
            )
            
            for match in form_matches:
                form_name = re.sub(r'<[^>]+>', '', match.group(1)).strip()
                form_values = [
                    re.sub(r'<[^>]+>', '', val).strip()
                    for val in re.finditer(r'<td[^>]*>(.*?)</td>', match.group(2))
                ]
                forms[form_name] = form_values
        
        return forms
    
    def get_synonyms(self, word: str, language: str = "en") -> List[str]:
        """Get synonyms for a word."""
        entry = self.get_word_entry(word, language)
        if not entry:
            return []
        
        synonyms = []
        syn_matches = re.finditer(
            r'<h3><span class="mw-headline" id="Synonyms">.*?</h3>(.*?)(?=<h3>|$)',
            entry.content,
            re.DOTALL
        )
        
        for match in syn_matches:
            syn_items = re.finditer(r'<li><a[^>]+>(.*?)</a></li>', match.group(0))
            synonyms.extend(item.group(1) for item in syn_items)
        
        return synonyms
    
    def get_antonyms(self, word: str, language: str = "en") -> List[str]:
        """Get antonyms for a word."""
        entry = self.get_word_entry(word, language)
        if not entry:
            return []
        
        antonyms = []
        ant_matches = re.finditer(
            r'<h3><span class="mw-headline" id="Antonyms">.*?</h3>(.*?)(?=<h3>|$)',
            entry.content,
            re.DOTALL
        )
        
        for match in ant_matches:
            ant_items = re.finditer(r'<li><a[^>]+>(.*?)</a></li>', match.group(0))
            antonyms.extend(item.group(1) for item in ant_items)
        
        return antonyms 