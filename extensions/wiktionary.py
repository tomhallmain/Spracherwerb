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
    content: Optional[str] = None  # Store the raw content for further parsing


class Wiktionary:
    """Handles interactions with Wiktionary's dictionary database."""
    
    BASE_URL = "https://en.wiktionary.org/w/api.php"
    CACHE_DIR = Path("cache/wiktionary")
    CACHE_FILE = CACHE_DIR / "entries.json"
    CACHE_DURATION = 86400  # 24 hours in seconds
    
    def __init__(self):
        """Initialize the Wiktionary client with caching."""
        Utils.log("Initializing Wiktionary client")
        self.entries: Dict[str, WiktionaryEntry] = {}
        self._load_cache()
        Utils.log("Wiktionary client initialized successfully")
    
    def _load_cache(self):
        """Load cached entry data from disk."""
        try:
            Utils.log("Loading Wiktionary cache")
            if self.CACHE_FILE.exists():
                Utils.log_debug(f"Loading cache from {self.CACHE_FILE}")
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.entries = {
                        word: WiktionaryEntry(**entry_data)
                        for word, entry_data in data.items()
                    }
                Utils.log(f"Loaded {len(self.entries)} entries from cache")
            else:
                Utils.log_yellow("Cache file not found")
        except Exception as e:
            Utils.log_red(f"Error loading Wiktionary cache: {e}")
            self.entries = {}
    
    def _save_cache(self):
        """Save entry data to cache file."""
        try:
            Utils.log("Saving Wiktionary cache")
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(
                    {word: entry.__dict__ 
                     for word, entry in self.entries.items()},
                    f,
                    ensure_ascii=False,
                    indent=2
                )
            Utils.log(f"Saved {len(self.entries)} entries to cache")
        except Exception as e:
            Utils.log_red(f"Error saving Wiktionary cache: {e}")
    
    def _is_cache_valid(self, entry: WiktionaryEntry) -> bool:
        """Check if cached entry data is still valid."""
        if not entry.last_accessed:
            Utils.log_debug("Entry has no last_accessed timestamp")
            return False
        is_valid = (time.time() - entry.last_accessed) < self.CACHE_DURATION
        Utils.log_debug(f"Cache validity: {is_valid} (last access: {time.time() - entry.last_accessed:.2f}s ago)")
        return is_valid
    
    def get_word_entry(
        self,
        word: str,
        language: str = "en",
        include_etymology: bool = True,
        include_examples: bool = True
    ) -> Optional[WiktionaryEntry]:
        """Get a word entry from Wiktionary."""
        cache_key = f"{word}_{language}"
        Utils.log(f"Getting word entry for {word} in {language}")
        
        # Check cache first
        if cache_key in self.entries and self._is_cache_valid(self.entries[cache_key]):
            Utils.log(f"Using cached entry for {word}")
            return self.entries[cache_key]
        
        # Validate language
        if not language or not language.isalpha() or len(language) != 2:
            Utils.log_yellow(f"Invalid language code: {language}")
            return None
        
        try:
            # First get the page content
            params = {
                "action": "parse",
                "format": "json",
                "page": word,
                "prop": "text",
                "disabletoc": "true",
                "disableeditsection": "true",
                "disablelimitreport": "true"
            }
            
            # Log the complete URL with all parameters
            query_string = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
            complete_url = f"{self.BASE_URL}?{query_string}"
            Utils.log(f"Complete API URL: {complete_url}")
            
            Utils.log(f"Fetching entry from {self.BASE_URL}")
            response = requests.get(self.BASE_URL, params=params)
            response.raise_for_status()
            Utils.log_debug(f"Response status: {response.status_code}")
            
            data = response.json()
            Utils.log_debug(f"Response data: {data}")
            
            # Get the parsed content
            if "parse" not in data or "text" not in data["parse"]:
                Utils.log_yellow(f"No content found for {word}")
                return None
                
            content = data["parse"]["text"]["*"]
            if not content:
                Utils.log_yellow(f"No content found for {word}")
                return None
            
            Utils.log_debug(f"Retrieved content length: {len(content)}")
            
            # Parse the content
            entry = self._parse_wiktionary_content(
                content,
                word,
                language,
                include_etymology,
                include_examples
            )
            
            if entry:
                Utils.log(f"Successfully parsed entry for {word}")
                self.entries[cache_key] = entry
                self._save_cache()
            else:
                Utils.log_yellow(f"No valid entry found for {word}")
            
            return entry
            
        except Exception as e:
            Utils.log_red(f"Error getting Wiktionary entry for {word}: {e}")
            Utils.log_red(f"Error type: {type(e)}")
            Utils.log_red(f"Error details: {str(e)}")
            return None
    
    def _find_part_of_speech(self, content: str) -> str:
        """
        Find the first valid part of speech in the content by checking all parts of speech
        and returning the one that appears earliest in the content.

        NOTE: For the secondary languages, the IDs for their part of speech titles
        have _{index} appended to them, so they should not interfere with this test.
        """
        Utils.log_debug("Looking for part of speech in content")
        
        # List of valid parts of speech to look for
        valid_parts = ["Noun", "Verb", "Adjective", "Adverb", "Pronoun", 
                      "Preposition", "Conjunction", "Interjection", "Article"]
        
        earliest_match = None
        earliest_position = float('inf')
        
        # Check all parts of speech and find the earliest one
        for part in valid_parts:
            # Try h3 first
            h3_matches = re.finditer(
                rf'<h3[^>]*id="{part}"[^>]*>.*?</h3>',
                content,
                re.DOTALL
            )
            for match in h3_matches:
                if match.start() < earliest_position:
                    earliest_position = match.start()
                    earliest_match = part
                    Utils.log_debug(f"Found earlier part of speech '{part}' in h3 at position {earliest_position}")
            
            # Then try h4
            h4_matches = re.finditer(
                rf'<h4[^>]*id="{part}"[^>]*>.*?</h4>',
                content,
                re.DOTALL
            )
            for match in h4_matches:
                if match.start() < earliest_position:
                    earliest_position = match.start()
                    earliest_match = part
                    Utils.log_debug(f"Found earlier part of speech '{part}' in h4 at position {earliest_position}")
        
        if earliest_match:
            Utils.log_debug(f"Earliest part of speech found: '{earliest_match}' at position {earliest_position}")
            return earliest_match.lower()
        
        Utils.log_yellow("No valid part of speech found")
        return "unknown"

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
            Utils.log_debug(f"Parsing content for {word}")
            
            # Find the language section
            lang_section = re.search(
                rf'<h2[^>]*>English</h2>(.*?)(?=<h2>|$)',
                content,
                re.DOTALL
            )
            
            if not lang_section:
                Utils.log_yellow(f"No {language} section found for {word}")
                return None
            
            content = lang_section.group(1)
            Utils.log_debug(f"Found {language} section for {word}")
            
            # Find the part of speech
            part_of_speech = self._find_part_of_speech(content)
            Utils.log_debug(f"Part of speech: {part_of_speech}")
            
            # Extract definitions
            definitions = []
            def_matches = re.finditer(r'<li>(.*?)(?=</li>|<h3>|<h4>|$)', content, re.DOTALL)
            for match in def_matches:
                definition = re.sub(r'<[^>]+>', '', match.group(1)).strip()
                if definition and not definition.startswith(('(', '→', 'For quotations')):
                    definitions.append(definition)
            Utils.log_debug(f"Found {len(definitions)} definitions")
            
            # Extract etymology if requested
            etymology = None
            if include_etymology:
                etym_match = re.search(
                    r'<h3[^>]*>Etymology</h3>(.*?)(?=<h3>|$)',
                    content,
                    re.DOTALL
                )
                if etym_match:
                    etymology = re.sub(r'<[^>]+>', '', etym_match.group(1)).strip()
                    Utils.log_debug("Found etymology")
            
            # Extract examples if requested
            examples = []
            if include_examples:
                example_matches = re.finditer(
                    r'<dd>(.*?)(?=</dd>|<h3>|<h4>|$)',
                    content,
                    re.DOTALL
                )
                for match in example_matches:
                    example = re.sub(r'<[^>]+>', '', match.group(1)).strip()
                    if example:
                        examples.append(example)
                Utils.log_debug(f"Found {len(examples)} examples")
            
            entry = WiktionaryEntry(
                word=word,
                language=language,
                part_of_speech=part_of_speech,
                definitions=definitions,
                etymology=etymology,
                pronunciation=None,  # We'll need to parse this from the content
                examples=examples,
                related_words=[],
                last_accessed=time.time(),
                content=content  # Store the raw content
            )
            
            Utils.log(f"Successfully created WiktionaryEntry for {word}")
            return entry
            
        except Exception as e:
            Utils.log_red(f"Error parsing Wiktionary content for {word}: {e}")
            Utils.log_red(f"Error type: {type(e)}")
            Utils.log_red(f"Error details: {str(e)}")
            return None
    
    def get_word_forms(self, word: str, language: str = "en") -> Dict[str, List[str]]:
        """Get different forms of a word (e.g., conjugations, declensions)."""
        Utils.log(f"Getting word forms for {word} in {language}")
        entry = self.get_word_entry(word, language)
        if not entry or not entry.content:
            Utils.log_yellow(f"No entry found for {word}, cannot get word forms")
            return {}

        forms = {}

        # For English verbs, look for form designations in <i> elements
        if language == "en" and entry.part_of_speech.lower() == "verb":
            Utils.log_debug(f"Looking for verb forms in content of length {len(entry.content)}")
            
            # Look for present tense forms (excluding present participle)
            present_forms = list(re.finditer(
                r'<i>([^<]*present(?! participle)[^<]*)</i>.*?<b[^>]*>.*?<a[^>]*>(.*?)</a>',
                entry.content,
                re.DOTALL
            ))
            if present_forms:
                Utils.log_debug(f"Found {len(present_forms)} present tense forms")
                forms["present"] = [word]  # Start with the base form
                for match in present_forms:
                    form_type = match.group(1).strip()
                    form = re.sub(r'<[^>]+>', '', match.group(2)).strip()
                    if form and form != word:  # Don't add the base form again if it's found
                        forms["present"].append(form)
                        Utils.log_debug(f"Found present form: {form} ({form_type})")
                        Utils.log_debug(f"Full match: {match.group(0)}")
            else:
                Utils.log_debug("No present tense forms found")
                forms["present"] = [word]  # Still include the base form
                # Log a sample of the content to help debug
                sample = entry.content[:500] + "..." if len(entry.content) > 500 else entry.content
                Utils.log_debug(f"Content sample: {sample}")
            
            # Look for present participle forms
            present_participle_forms = list(re.finditer(
                r'<i>([^<]*present participle[^<]*)</i>.*?<b[^>]*>.*?<a[^>]*>(.*?)</a>',
                entry.content,
                re.DOTALL
            ))
            if present_participle_forms:
                Utils.log_debug(f"Found {len(present_participle_forms)} present participle forms")
                forms["present participle"] = []
                for match in present_participle_forms:
                    form_type = match.group(1).strip()
                    form = re.sub(r'<[^>]+>', '', match.group(2)).strip()
                    if form:
                        forms["present participle"].append(form)
                        Utils.log_debug(f"Found present participle form: {form} ({form_type})")
                        Utils.log_debug(f"Full match: {match.group(0)}")
            else:
                Utils.log_debug("No present participle forms found")
            
            # Look for past tense forms
            past_forms = list(re.finditer(
                r'<i>([^<]*past(?! participle)[^<]*)</i>.*?<b[^>]*>.*?<a[^>]*>(.*?)</a>',
                entry.content,
                re.DOTALL
            ))
            if past_forms:
                Utils.log_debug(f"Found {len(past_forms)} past tense forms")
                forms["past"] = []
                for match in past_forms:
                    form_type = match.group(1).strip()
                    form = re.sub(r'<[^>]+>', '', match.group(2)).strip()
                    if form:
                        forms["past"].append(form)
                        Utils.log_debug(f"Found past form: {form} ({form_type})")
                        Utils.log_debug(f"Full match: {match.group(0)}")
            else:
                Utils.log_debug("No past tense forms found")
            
            # Look for past participle forms
            past_participle_forms = list(re.finditer(
                r'<i>([^<]*past participle[^<]*)</i>.*?<b[^>]*>.*?<a[^>]*>(.*?)</a>',
                entry.content,
                re.DOTALL
            ))
            if past_participle_forms:
                Utils.log_debug(f"Found {len(past_participle_forms)} past participle forms")
                forms["past participle"] = []
                for match in past_participle_forms:
                    form_type = match.group(1).strip()
                    form = re.sub(r'<[^>]+>', '', match.group(2)).strip()
                    if form:
                        forms["past participle"].append(form)
                        Utils.log_debug(f"Found past participle form: {form} ({form_type})")
                        Utils.log_debug(f"Full match: {match.group(0)}")
            else:
                Utils.log_debug("No past participle forms found")
        
        # Log the final results
        if forms:
            Utils.log(f"Found {len(forms)} word forms for {word}:")
            for form_type, form_list in forms.items():
                Utils.log(f"  {form_type}: {form_list}")
        else:
            Utils.log_yellow(f"No word forms found for {word}")
            Utils.log_debug(f"Word part of speech: {entry.part_of_speech}")
        
        return forms
    
    def get_synonyms(self, word: str, language: str = "en") -> List[str]:
        """Get synonyms for a word."""
        Utils.log(f"Getting synonyms for {word} in {language}")
        entry = self.get_word_entry(word, language)
        if not entry:
            Utils.log_yellow(f"No entry found for {word}, cannot get synonyms")
            return []
        
        synonyms = []
        # Look for all synonyms in spans with nyms synonym class
        syn_matches = re.finditer(
            r'<span class="nyms synonym">.*?<span class="Latn" lang="en"><a[^>]*>(.*?)</a></span>(?:, <span class="Latn" lang="en"><a[^>]*>(.*?)</a></span>)*',
            entry.content,
            re.DOTALL
        )
        
        for match in syn_matches:
            # Extract all synonyms from the matched text
            syn_text = match.group(0)
            # Find all individual synonyms in this match
            syn_items = re.finditer(
                r'<span class="Latn" lang="en"><a[^>]*>(.*?)</a></span>',
                syn_text
            )
            for item in syn_items:
                synonym = item.group(1).strip()
                if synonym and synonym not in synonyms:  # Avoid duplicates
                    synonyms.append(synonym)
                    Utils.log_debug(f"Found synonym: {synonym}")
        
        Utils.log(f"Found {len(synonyms)} synonyms for {word}")
        return synonyms
    
    def get_antonyms(self, word: str, language: str = "en") -> List[str]:
        """Get antonyms for a word."""
        Utils.log(f"Getting antonyms for {word} in {language}")
        entry = self.get_word_entry(word, language)
        if not entry:
            Utils.log_yellow(f"No entry found for {word}, cannot get antonyms")
            return []
        
        antonyms = []
        # Look for all antonyms in spans with nyms antonym class
        ant_matches = re.finditer(
            r'<span class="nyms antonym">.*?<span class="Latn" lang="en"><a[^>]*>(.*?)</a></span>(?:, <span class="Latn" lang="en"><a[^>]*>(.*?)</a></span>)*',
            entry.content,
            re.DOTALL
        )
        
        for match in ant_matches:
            # Extract all antonyms from the matched text
            ant_text = match.group(0)
            # Find all individual antonyms in this match
            ant_items = re.finditer(
                r'<span class="Latn" lang="en"><a[^>]*>(.*?)</a></span>',
                ant_text
            )
            for item in ant_items:
                antonym = item.group(1).strip()
                if antonym and antonym not in antonyms:  # Avoid duplicates
                    antonyms.append(antonym)
                    Utils.log_debug(f"Found antonym: {antonym}")
        
        Utils.log(f"Found {len(antonyms)} antonyms for {word}")
        return antonyms 