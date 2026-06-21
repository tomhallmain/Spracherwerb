"""Client helpers for wordreference.com dictionary pages (no official API).

WordReference dictionaries are bilingual pairs that include English on one
side. Lookups build URLs like ``https://www.wordreference.com/ende/dog``.
"""

from __future__ import annotations

import json
import re
import time
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from utils.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass
class WordReferenceTranslation:
    """One source sense and its target-language equivalents."""
    from_term: str
    to_terms: List[str] = field(default_factory=list)
    context: str = ''
    from_pos: Optional[str] = None
    to_pos: Optional[str] = None


@dataclass
class WordReferenceSection:
    """A table section from the WordReference results page."""
    title: str
    entries: List[WordReferenceTranslation] = field(default_factory=list)


@dataclass
class WordReferenceResult:
    """Structured lookup result for a single query."""
    word: str
    dictionary_code: str
    from_language: str
    to_language: str
    url: str
    sections: List[WordReferenceSection] = field(default_factory=list)
    last_accessed: Optional[float] = None


class WordReferenceError(Exception):
    """Raised when a lookup cannot be completed."""


class WordReference:
    """Client for wordreference.com translation pages."""

    BASE_URL = 'https://www.wordreference.com'
    CACHE_DIR = Path('cache/wordreference')
    CACHE_FILE = CACHE_DIR / 'lookups.json'
    CACHE_DURATION = 86400
    HUMAN_COOKIE = 'nginx_wr_human'
    USER_AGENT = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )

    LANGUAGE_CODES = {
        'en': 'en',
        'de': 'de',
        'fr': 'fr',
        'es': 'es',
        'it': 'it',
    }

    def __init__(self):
        self.results: Dict[str, WordReferenceResult] = {}
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.USER_AGENT})
        self.session.cookies.set(self.HUMAN_COOKIE, '1', domain='.wordreference.com')
        self._load_cache()

    @classmethod
    def dictionary_code(cls, from_language: str, to_language: str) -> Optional[str]:
        """Return the four-letter WordReference dictionary code, if supported."""
        from_code = cls.LANGUAGE_CODES.get(str(from_language).lower())
        to_code = cls.LANGUAGE_CODES.get(str(to_language).lower())
        if not from_code or not to_code or from_code == to_code:
            return None
        if 'en' not in (from_code, to_code):
            return None
        return f'{from_code}{to_code}'

    @classmethod
    def build_lookup_url(cls, word: str, from_language: str, to_language: str) -> str:
        dictionary_code = cls.dictionary_code(from_language, to_language)
        if not dictionary_code:
            raise WordReferenceError(
                f'No WordReference dictionary for {from_language} → {to_language}. '
                'Supported pairs use English on one side (en↔de/fr/es/it).'
            )
        query = quote(cls._normalize_query_word(word), safe='')
        return f'{cls.BASE_URL}/{dictionary_code}/{query}'

    @staticmethod
    def _normalize_query_word(word: str) -> str:
        text = ' '.join(str(word).strip().split())
        if not text:
            raise WordReferenceError('Lookup word cannot be empty.')
        return text.split(',')[0].strip()

    @staticmethod
    def _cache_key(word: str, from_language: str, to_language: str) -> str:
        return f'{from_language.lower()}:{to_language.lower()}:{word.casefold()}'

    def lookup(
        self,
        word: str,
        from_language: str,
        to_language: str,
        *,
        use_cache: bool = True,
    ) -> Optional[WordReferenceResult]:
        """Look up *word* from *from_language* into *to_language*."""
        query_word = self._normalize_query_word(word)
        cache_key = self._cache_key(query_word, from_language, to_language)

        if use_cache:
            cached = self.results.get(cache_key)
            if cached and self._is_cache_valid(cached):
                logger.debug('WordReference cache hit for %s', cache_key)
                return cached

        dictionary_code = self.dictionary_code(from_language, to_language)
        if not dictionary_code:
            return None

        url = self.build_lookup_url(query_word, from_language, to_language)

        try:
            response = self.session.get(url, timeout=20)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error('WordReference request failed for %s: %s', url, exc)
            return None

        sections = self._parse_html(response.text, dictionary_code)
        if not sections:
            logger.warning('WordReference returned no parseable sections for %s', url)
            return None

        result = WordReferenceResult(
            word=query_word,
            dictionary_code=dictionary_code,
            from_language=from_language,
            to_language=to_language,
            url=url,
            sections=sections,
            last_accessed=time.time(),
        )
        self.results[cache_key] = result
        self._save_cache()
        return result

    @classmethod
    def open_lookup_in_browser(
        cls,
        word: str,
        from_language: str,
        to_language: str,
    ) -> str:
        """Open a browser tab for the dictionary entry and return its URL."""
        url = cls.build_lookup_url(word, from_language, to_language)
        webbrowser.open(url)
        return url

    def open_in_browser(self, word: str, from_language: str, to_language: str) -> str:
        """Open a browser tab for *word* and return the URL."""
        return self.open_lookup_in_browser(word, from_language, to_language)

    @classmethod
    def format_result_summary(cls, result: WordReferenceResult, max_entries: int = 12) -> str:
        """Format lookup results for display in a dialog."""
        lines = [f'{result.word}  ({result.from_language} → {result.to_language})', '']
        shown = 0
        for section in result.sections:
            if shown >= max_entries:
                lines.append('…')
                break
            if section.title:
                lines.append(section.title)
            for entry in section.entries:
                if shown >= max_entries:
                    lines.append('…')
                    break
                target = ', '.join(entry.to_terms) if entry.to_terms else '—'
                context = f'  [{entry.context}]' if entry.context else ''
                pos = ''
                if entry.from_pos or entry.to_pos:
                    pos = f' ({entry.from_pos or "?"} → {entry.to_pos or "?"})'
                lines.append(f'  {entry.from_term}{pos} → {target}{context}')
                shown += 1
            lines.append('')
        lines.append(result.url)
        return '\n'.join(lines).strip()

    def _parse_html(self, html: str, dictionary_code: str) -> List[WordReferenceSection]:
        soup = BeautifulSoup(html, 'html.parser')
        article = soup.find(id='articleWRD')
        if not article:
            return []

        sections: List[WordReferenceSection] = []
        for table in article.find_all('table', class_='WRD'):
            data_dict = (table.get('data-dict') or dictionary_code).lower()
            title_row = table.find('tr', class_='wrtopsection')
            title = title_row.get_text(' ', strip=True) if title_row else ''

            section = WordReferenceSection(title=title)
            current_entry: Optional[WordReferenceTranslation] = None

            for row in table.find_all('tr', class_='odd'):
                cells = row.find_all('td')
                if len(cells) < 3:
                    continue

                from_cell, context_cell, to_cell = cells[0], cells[1], cells[2]
                from_term = self._extract_term(from_cell)
                to_term = self._extract_term(to_cell)
                context = context_cell.get_text(' ', strip=True)
                context = re.sub(r'\s+', ' ', context).strip()

                if from_term:
                    current_entry = WordReferenceTranslation(
                        from_term=from_term,
                        context=context,
                        from_pos=self._extract_pos(from_cell),
                        to_pos=self._extract_pos(to_cell),
                    )
                    if to_term:
                        current_entry.to_terms.append(to_term)
                    section.entries.append(current_entry)
                    continue

                if current_entry is None:
                    continue

                if context and not current_entry.context:
                    current_entry.context = context
                elif context:
                    extra = context if not current_entry.context else f'{current_entry.context}; {context}'
                    current_entry.context = extra

                if to_term and to_term not in current_entry.to_terms:
                    current_entry.to_terms.append(to_term)
                    if not current_entry.to_pos:
                        current_entry.to_pos = self._extract_pos(to_cell)

            if section.entries:
                sections.append(section)

        return sections

    @staticmethod
    def _extract_term(cell) -> str:
        if cell is None:
            return ''
        text = cell.get_text(' ', strip=True)
        if not text or text == '\xa0':
            return ''
        strong = cell.find('strong')
        if strong:
            text = strong.get_text(' ', strip=True)
        for em in cell.find_all('em', class_='POS2'):
            pos_text = em.get_text(strip=True)
            if text.endswith(pos_text):
                text = text[: -len(pos_text)].strip()
            else:
                text = text.replace(pos_text, '').strip()
        return re.sub(r'\s+', ' ', text).strip()

    @staticmethod
    def _extract_pos(cell) -> Optional[str]:
        if cell is None:
            return None
        em = cell.find('em', class_='POS2')
        if not em:
            return None
        return em.get('data-abbr') or em.get_text(strip=True) or None

    def _is_cache_valid(self, result: WordReferenceResult) -> bool:
        if not result.last_accessed:
            return False
        return (time.time() - result.last_accessed) < self.CACHE_DURATION

    def _load_cache(self):
        try:
            if not self.CACHE_FILE.exists():
                return
            with open(self.CACHE_FILE, 'r', encoding='utf-8') as handle:
                raw = json.load(handle)
            for key, payload in raw.items():
                sections = [
                    WordReferenceSection(
                        title=section['title'],
                        entries=[
                            WordReferenceTranslation(**entry)
                            for entry in section.get('entries', [])
                        ],
                    )
                    for section in payload.get('sections', [])
                ]
                self.results[key] = WordReferenceResult(
                    word=payload['word'],
                    dictionary_code=payload['dictionary_code'],
                    from_language=payload['from_language'],
                    to_language=payload['to_language'],
                    url=payload['url'],
                    sections=sections,
                    last_accessed=payload.get('last_accessed'),
                )
        except Exception as exc:
            logger.error('Error loading WordReference cache: %s', exc)
            self.results = {}

    def _save_cache(self):
        try:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            serializable = {}
            for key, result in self.results.items():
                serializable[key] = {
                    'word': result.word,
                    'dictionary_code': result.dictionary_code,
                    'from_language': result.from_language,
                    'to_language': result.to_language,
                    'url': result.url,
                    'last_accessed': result.last_accessed,
                    'sections': [
                        {
                            'title': section.title,
                            'entries': [entry.__dict__ for entry in section.entries],
                        }
                        for section in result.sections
                    ],
                }
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as handle:
                json.dump(serializable, handle, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.error('Error saving WordReference cache: %s', exc)
