"""Client helpers for wordreference.com dictionary pages (no official API).

WordReference dictionaries are bilingual pairs that include English on one
side. Lookups build URLs like ``https://www.wordreference.com/ende/dog``.
"""

from __future__ import annotations

import copy
import json
import re
import time
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup, Tag

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
        # A word carried only by the reverse-direction table is served as a
        # 404 whose body a browser still renders. Sending what a browser sends
        # is the cheap thing to try when that body comes back stripped.
        self.session.headers.update({
            'User-Agent': self.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,de;q=0.8',
            'Referer': f'{self.BASE_URL}/',
        })
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
        except requests.RequestException as exc:
            logger.error('WordReference request failed for %s: %s', url, exc)
            return None

        # A word with no entry of its own can still be answered by the page:
        # compound forms and the other editions are served with a 404, so the
        # body decides whether the lookup succeeded, not the status code.
        sections = self._parse_html(response.text, dictionary_code)
        if not sections:
            logger.warning(
                'WordReference returned no parseable sections for %s (HTTP %s)',
                url, response.status_code)
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
        """Collect every corpus on the page, not just the current WR dictionary.

        A result page carries several independently-formatted dictionaries:
        the current WordReference edition as ``table.WRD`` inside
        ``#articleWRD``, and older editions as ``div.entry`` blocks further
        down. A word can be absent from one and well covered by another, so
        both are parsed and returned as separate sections.
        """
        soup = BeautifulSoup(html, 'html.parser')
        sections: List[WordReferenceSection] = []
        article = soup.find(id='articleWRD')
        if article:
            sections.extend(self._parse_wrd_tables(article, dictionary_code))
        sections.extend(self._parse_dictionary_entries(soup))
        return sections

    def _parse_wrd_tables(self, article, dictionary_code: str) -> List[WordReferenceSection]:
        sections: List[WordReferenceSection] = []
        for table in article.find_all('table', class_='WRD'):
            data_dict = (table.get('data-dict') or dictionary_code).lower()
            title_row = table.find('tr', class_='wrtopsection')
            title = title_row.get_text(' ', strip=True) if title_row else ''

            section = WordReferenceSection(title=title)
            current_entry: Optional[WordReferenceTranslation] = None
            if self._table_columns_are_swapped(table, data_dict):
                section.entries.extend(self._parse_swapped_rows(table))
                if section.entries:
                    sections.append(section)
                continue

            for row in table.find_all('tr'):
                # Translation rows alternate between these two classes; the
                # others carry the section heading and language labels.
                row_classes = row.get('class') or []
                if 'odd' not in row_classes and 'even' not in row_classes:
                    continue
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
    def _table_columns_are_swapped(table, dictionary_code: str) -> bool:
        """True when the table runs the opposite way to the dictionary being read.

        A result page can include a table from the reverse direction, where
        the queried word appears only as one of the translations of a
        headword in the other language. The language header names each
        column, so the direction is read rather than assumed.
        """
        header = table.find('tr', class_='langHeader')
        if header is None:
            return False
        cells = header.find_all('td')
        if not cells:
            return False
        marker = cells[0].find('span', attrs={'data-ph': True})
        if marker is None:
            return False
        column_language = str(marker.get('data-ph', '')).rsplit('_', 1)[-1].lower()
        if not column_language:
            return False
        return column_language != dictionary_code[:2].lower()

    def _parse_swapped_rows(self, table) -> List[WordReferenceTranslation]:
        """Read a reverse-direction table as entries running the wanted way.

        One headword in the other language carries several translations down
        the continuation rows (``saver`` -> ``jdm, der spart`` / ``sparen``
        / ``Sparer``), so each of those becomes an entry of its own pointing
        back at the shared headword.

        Unproven against a live fetch, and possibly wrong in ways only a live
        fetch would show. It was written from saved pages, and a word that
        needs it is exactly a word whose page comes back stripped of this
        table, so nothing has yet exercised it end to end. Treat a bad
        result from a reverse-direction table as suspect here first.
        """
        entries: List[WordReferenceTranslation] = []
        gloss = ''
        for row in table.find_all('tr'):
            row_classes = row.get('class') or []
            if 'odd' not in row_classes and 'even' not in row_classes:
                continue
            cells = row.find_all('td')
            if len(cells) < 3:
                continue

            headword = self._extract_term(cells[0])
            if headword:
                gloss = headword
            term = self._extract_term(cells[2])
            if not term or not gloss:
                continue
            context = re.sub(r'\s+', ' ', cells[1].get_text(' ', strip=True)).strip()
            entries.append(WordReferenceTranslation(
                from_term=term,
                to_terms=[gloss],
                context=context,
                from_pos=self._extract_pos(cells[2]),
                to_pos=self._extract_pos(cells[0]),
            ))
        return entries

    # Register and domain labels (umg, fig, vulg, US, JAGD). They annotate a
    # translation rather than being part of it, and the import has nowhere to
    # put them, so they are dropped.
    _LABEL_SPAN_CLASSES = ('usage', 'subjarea')
    _PUNCTUATION_ONLY_RE = re.compile(r'^[\s;:,.()\[\]…/]+$')
    # Points at a conjugation table rather than forming part of the translation.
    _POINTER_GLYPH_RE = re.compile(r'[⇒→⇨➡]')

    def _parse_dictionary_entries(self, soup) -> List[WordReferenceSection]:
        """Parse the older ``div.entry`` dictionaries into one section each.

        Two layouts appear under this class and a word may be covered by
        either: a run of ``span.roman``/``span.ital`` glosses headed by
        ``strong.hw``, or sense groups headed by ``span.lemma`` whose
        translations sit in ``div.senseExample``.
        """
        sections: List[WordReferenceSection] = []
        for entry in soup.find_all('div', class_='entry'):
            parsed = self._parse_flowing_entry(entry) or self._parse_sense_entry(entry)
            if parsed is None:
                continue
            headword, glosses, examples = parsed
            entries: List[WordReferenceTranslation] = []
            if glosses:
                entries.append(
                    WordReferenceTranslation(from_term=headword, to_terms=glosses))
            for phrase, gloss in examples:
                if phrase and gloss:
                    entries.append(
                        WordReferenceTranslation(from_term=phrase, to_terms=[gloss]))
            if not entries:
                continue

            title_el = entry.find_previous('div', class_='small1')
            title = self._collapse(title_el.get_text(' ', strip=True)) if title_el else ''
            sections.append(WordReferenceSection(title=title, entries=entries))
        return sections

    def _parse_flowing_entry(self, entry):
        """Parse a ``strong.hw`` entry, or return None if this is another layout."""
        headword_el = entry.find('strong', class_='hw')
        if headword_el is None:
            return None
        headword = self._collapse(headword_el.get_text(' ', strip=True))
        if not headword:
            return None
        glosses, examples = self._walk_dictionary_entry(entry)
        return headword, glosses, examples

    def _parse_sense_entry(self, entry):
        """Parse a ``span.lemma`` entry whose senses are ``div.senseExample`` pairs.

        A translation inside a sense example belongs to that example's own
        phrase; one outside every example translates the headword itself.

        Only the example half is proven. Every page this was built from
        translates the headword solely through examples, so the branch
        collecting a translation for the headword itself has never matched
        real markup and may be looking for the wrong thing. A word from this
        edition that harvests phrases but keeps its placeholder is the
        symptom.
        """
        lemma_el = entry.find('span', class_='lemma')
        if lemma_el is None:
            return None
        headword = self._clean_text(self._abbreviated_text(lemma_el))
        if not headword:
            return None

        examples = []
        for example in entry.find_all('div', class_='senseExample'):
            phrase_el = example.find('span', class_='ex')
            translation_el = example.find('span', class_='trans')
            if phrase_el is None or translation_el is None:
                continue
            examples.append((
                self._clean_text(self._abbreviated_text(phrase_el)),
                self._clean_text(self._abbreviated_text(translation_el)),
            ))

        glosses = [
            self._abbreviated_text(translation)
            for translation in entry.find_all('span', class_='trans')
            if translation.find_parent('div', class_='senseExample') is None
        ]
        return headword, self._clean_gloss_list(glosses), examples

    @classmethod
    def _abbreviated_text(cls, element) -> str:
        """Text of *element* with each abbreviation's spelled-out form removed.

        An abbreviation nests its expansion inside itself and puts the short
        form after it, so reading all the text gives "jemand | somebodysb"
        where the entry means "sb".
        """
        clone = copy.copy(element)
        for abbreviation in clone.find_all('span', class_='abbr'):
            for expansion in abbreviation.find_all('span'):
                expansion.decompose()
        return clone.get_text(' ', strip=True)

    def _walk_dictionary_entry(self, entry):
        """Split one entry into (headword glosses, [(phrase, gloss), ...]).

        Walked in document order because an example's translation is not
        reliably nested inside it: an inline ``examplecontainer`` can close
        before its own gloss ("von der Stange" ... "off the peg"), so text
        keeps counting towards the example until a ``<br>`` or the next
        sense item ends it.
        """
        gloss_parts: List[str] = []
        examples = []
        current = None

        for node in entry.descendants:
            if isinstance(node, Tag):
                classes = node.get('class') or []
                if node.name == 'div' and 'examplecontainer' in classes:
                    current = {'phrase': [], 'gloss': []}
                    examples.append(current)
                elif node.name in ('br', 'li'):
                    current = None
                continue

            text = str(node).strip()
            if not text:
                continue
            parent = node.parent
            classes = parent.get('class') or [] if isinstance(parent, Tag) else []
            if 'hw' in classes or 'headnumber' in classes:
                continue
            if any(label in classes for label in self._LABEL_SPAN_CLASSES):
                continue
            if 'example' in classes:
                if current is not None:
                    current['phrase'].append(text)
                continue
            if 'roman' not in classes:
                # Italics carry German sense context, not a translation.
                continue
            if current is not None:
                current['gloss'].append(text)
            else:
                gloss_parts.append(text)

        return (
            self._clean_gloss_list(gloss_parts),
            [
                (self._clean_text(' '.join(ex['phrase'])),
                 self._clean_text(' '.join(ex['gloss'])))
                for ex in examples
            ],
        )

    @classmethod
    def _clean_gloss_list(cls, parts: List[str]) -> List[str]:
        """Drop separator-only fragments and de-duplicate, keeping page order."""
        glosses: List[str] = []
        seen = set()
        for part in parts:
            cleaned = cls._clean_text(part)
            if not cleaned or cls._PUNCTUATION_ONLY_RE.match(cleaned):
                continue
            if cleaned.casefold() in seen:
                continue
            seen.add(cleaned.casefold())
            glosses.append(cleaned)
        return glosses

    @classmethod
    def _clean_text(cls, text: str) -> str:
        """Tidy the punctuation left behind once label spans have been removed.

        Semicolons become commas because the import treats a source text as a
        comma-separated gloss list, and the ellipsis standing in for an
        omitted word ("off-the-peg …") carries nothing once it is on its own.
        """
        text = cls._POINTER_GLYPH_RE.sub('', text)
        text = cls._collapse(text)
        text = re.sub(r'\s*(?:…|\.\.\.)', '', text)
        text = re.sub(r'\s+([,;:.)\]])', r'\1', text)
        text = re.sub(r'([(\[])\s+', r'\1', text)
        text = re.sub(r'\(\s*\)', '', text)
        text = re.sub(r'[;:,](?:\s*[;:,])+', ',', text)
        text = text.replace(';', ',')
        return cls._collapse(text).strip(' ;:,')

    @staticmethod
    def _collapse(text: str) -> str:
        return re.sub(r'\s+', ' ', text).strip()

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
        text = WordReference._POINTER_GLYPH_RE.sub('', text)
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
