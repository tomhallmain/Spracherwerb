"""Module for interacting with LanguageTool's grammar and style checking API."""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import json
import time
import requests

from utils.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass
class LanguageError:
    """Represents a grammar or style error found by LanguageTool."""
    message: str
    short_message: str
    offset: int
    length: int
    replacements: List[str]
    rule_id: str
    rule_description: str
    rule_category: str
    rule_issue_type: str
    context: str
    context_offset: int
    context_length: int
    last_accessed: Optional[float] = None


class LanguageTool:
    """Handles interactions with LanguageTool's grammar and style checking API."""
    
    BASE_URL = "https://api.languagetool.org/v2"
    CACHE_DIR = Path("cache/languagetool")
    CACHE_FILE = CACHE_DIR / "checks.json"
    CACHE_DURATION = 86400  # 24 hours in seconds
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the LanguageTool client with optional API key and caching."""
        self.api_key = api_key
        self.checks: Dict[str, List[LanguageError]] = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load cached checks from disk."""
        try:
            if self.CACHE_FILE.exists():
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.checks = {
                        text: [LanguageError(**error_data) for error_data in errors]
                        for text, errors in data.items()
                    }
        except Exception as e:
            logger.error(f"Error loading LanguageTool cache: {e}")
            self.checks = {}
    
    def _save_cache(self):
        """Save checks to cache file."""
        try:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(
                    {text: [error.__dict__ for error in errors]
                     for text, errors in self.checks.items()},
                    f,
                    ensure_ascii=False,
                    indent=2
                )
        except Exception as e:
            logger.error(f"Error saving LanguageTool cache: {e}")
    
    def _is_cache_valid(self, errors: List[LanguageError]) -> bool:
        """Check if cached checks are still valid."""
        if not errors:
            return False
        return (time.time() - max(e.last_accessed for e in errors)) < self.CACHE_DURATION
    
    def check_text(
        self,
        text: str,
        language: str,
        enabled_rules: Optional[List[str]] = None,
        disabled_rules: Optional[List[str]] = None,
        enabled_categories: Optional[List[str]] = None,
        disabled_categories: Optional[List[str]] = None
    ) -> List[LanguageError]:
        """Check text for grammar and style errors."""
        # Check cache first
        if text in self.checks and self._is_cache_valid(self.checks[text]):
            return self.checks[text]
        
        try:
            params = {
                "text": text,
                "language": language,
                "enabledOnly": "false"
            }
            
            if self.api_key:
                params["apiKey"] = self.api_key
            
            if enabled_rules:
                params["enabledRules"] = ",".join(enabled_rules)
            if disabled_rules:
                params["disabledRules"] = ",".join(disabled_rules)
            if enabled_categories:
                params["enabledCategories"] = ",".join(enabled_categories)
            if disabled_categories:
                params["disabledCategories"] = ",".join(disabled_categories)
            
            response = requests.post(f"{self.BASE_URL}/check", data=params)
            response.raise_for_status()
            data = response.json()
            
            errors = []
            for match in data.get("matches", []):
                error = LanguageError(
                    message=match["message"],
                    short_message=match["shortMessage"],
                    offset=match["offset"],
                    length=match["length"],
                    replacements=match.get("replacements", []),
                    rule_id=match["rule"]["id"],
                    rule_description=match["rule"]["description"],
                    rule_category=match["rule"]["category"]["id"],
                    rule_issue_type=match["rule"]["issueType"],
                    context=match["context"]["text"],
                    context_offset=match["context"]["offset"],
                    context_length=match["context"]["length"],
                    last_accessed=time.time()
                )
                errors.append(error)
            
            self.checks[text] = errors
            self._save_cache()
            
            return errors
            
        except Exception as e:
            logger.error(f"Error checking text with LanguageTool: {e}")
            return []
    
    def get_available_languages(self) -> List[str]:
        """Get a list of available languages in LanguageTool."""
        try:
            response = requests.get(f"{self.BASE_URL}/languages")
            response.raise_for_status()
            data = response.json()
            return [lang["code"] for lang in data]
        except Exception as e:
            logger.error(f"Error getting available languages: {e}")
            return []
    
    def get_available_rules(self, language: str) -> Dict[str, Any]:
        """Get available rules for a language."""
        try:
            response = requests.get(f"{self.BASE_URL}/rules", params={"language": language})
            response.raise_for_status()
            data = response.json()
            return data
        except Exception as e:
            logger.error(f"Error getting available rules: {e}")
            return {}
    
    def get_rule_categories(self, language: str) -> List[str]:
        """Get available rule categories for a language."""
        rules = self.get_available_rules(language)
        categories = set()
        
        for rule in rules.get("rules", []):
            if "category" in rule:
                categories.add(rule["category"]["id"])
        
        return list(categories)
    
    def get_error_statistics(self, text: str, language: str) -> Dict[str, Any]:
        """Get statistics about errors in text."""
        errors = self.check_text(text, language)
        
        if not errors:
            return {}
        
        stats = {
            "total_errors": len(errors),
            "categories": {},
            "issue_types": {},
            "rules": {}
        }
        
        for error in errors:
            stats["categories"][error.rule_category] = stats["categories"].get(error.rule_category, 0) + 1
            stats["issue_types"][error.rule_issue_type] = stats["issue_types"].get(error.rule_issue_type, 0) + 1
            stats["rules"][error.rule_id] = stats["rules"].get(error.rule_id, 0) + 1
        
        return stats
    
    def get_corrected_text(self, text: str, language: str) -> str:
        """Get text with suggested corrections applied."""
        errors = self.check_text(text, language)
        if not errors:
            return text
        
        # Sort errors by offset in reverse order to avoid offset issues when applying corrections
        errors.sort(key=lambda e: e.offset, reverse=True)
        
        corrected_text = text
        for error in errors:
            if error.replacements:
                # Apply the first suggested replacement
                start = error.offset
                end = error.offset + error.length
                corrected_text = corrected_text[:start] + error.replacements[0] + corrected_text[end:]
        
        return corrected_text 