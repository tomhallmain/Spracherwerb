"""Shared best-effort dictionary lookup for grounding LLM prompts in real vocabulary.

Tries a handful of the learner's saved vocabulary words against the
dictionary extension (WordReference) and returns the first one with a
usable part of speech. WordReference doesn't always have a part of speech
for a given word -- that's a normal outcome here, not an error, so callers
just fall back to generic (not vocabulary-grounded) content instead of
failing.
"""

import logging
from typing import Any, Optional

from utils import translation_import

logger = logging.getLogger(__name__)


def pick_vocabulary_hint(services: Any, limit: int = 5) -> Optional[str]:
    """Returns "{target_word} ({part_of_speech})" for one vocabulary word, or None."""
    word_reference = getattr(services, 'word_reference', None)
    if word_reference is None:
        return None

    source_language, target_language = services.language_pair()
    candidates = services.vocabulary_pool.get_review_candidates(
        source_language, target_language, limit=limit)

    for entry in candidates:
        source_word = translation_import.format_source_for_display(entry.get('source_text', '')).split(',')[0].strip()
        target_word = translation_import.coerce_str(entry.get('translated_text', ''))
        if not source_word or not target_word:
            continue
        try:
            result = word_reference.lookup(source_word, source_language, target_language)
        except Exception as e:
            logger.warning(f"Dictionary lookup failed for {source_word!r}: {e}")
            continue
        pos = _first_part_of_speech(result)
        if pos:
            return f"{target_word} ({pos})"

    return None


def _first_part_of_speech(result: Any) -> Optional[str]:
    if result is None:
        return None
    for section in getattr(result, 'sections', []):
        for entry in getattr(section, 'entries', []):
            if getattr(entry, 'to_pos', None):
                return entry.to_pos
            if getattr(entry, 'from_pos', None):
                return entry.from_pos
    return None
