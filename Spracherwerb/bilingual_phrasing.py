"""Shared helper for target-language-primary, source-language-parenthetical phrasing.

Used by activity modules that speak directly to the learner (VocabularyBuilder,
VisualVocabulary, ...): each module owns its own phrasebook of short
target-language templates, keyed by primary language tag, and calls
``bilingual_phrase`` to prefix the target-language phrasing before the
English/UI-locale text already built for that message. Modules whose target
language has no phrasebook entry just get the English text back unchanged.
"""

from utils import translation_import


def bilingual_phrase(
    target_language: str,
    phrasebook: dict,
    key: str,
    english_text: str,
    **kwargs,
) -> str:
    """Prefix a target-language phrasing (from `phrasebook`) before `english_text`.

    `phrasebook` maps primary language tag -> {key: template}, where template
    is a str.format() string filled in with `kwargs`. Falls back to
    `english_text` alone when the target language or key isn't in the book.
    """
    primary = translation_import.primary_language_tag(target_language)
    template = phrasebook.get(primary, {}).get(key)
    if not template:
        return english_text
    return f"{template.format(**kwargs)} ({english_text})"
