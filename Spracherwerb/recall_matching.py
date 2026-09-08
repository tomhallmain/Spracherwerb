"""Shared answer-checking and direction logic for word-recall activities.

Used by VocabularyBuilder and VisualVocabulary: both drill the same
translation-row shape (utils.translation_import), just with different
stimuli (text vs. a generated image).
"""

from utils import translation_import


def resolve_recall_direction(proficiency_level) -> str:
    """Beginner: shown the target word/image, recalls the source-language
    meaning (recognition). Everyone else: shown the source word/image gloss,
    produces the target word (production, the harder direction)."""
    level = translation_import.coerce_str(proficiency_level).lower()
    return "recall_source" if level == "beginner" else "produce_target"


def check_recall_answer(entry, user_text, target_language, direction):
    """Returns (is_correct, expected_answer_for_display)."""
    user_norm = translation_import.coerce_str(user_text).casefold()
    if direction == "produce_target":
        bare = translation_import.coerce_str(entry.get('translated_text', ''))
        displayed = translation_import.format_target_for_display(
            entry.get('translated_text', ''), entry.get('target_article', ''), target_language)
        is_correct = user_norm in (bare.casefold(), displayed.casefold())
        return is_correct, displayed
    source_text = translation_import.coerce_str(entry.get('source_text', ''))
    # source_text may have a comma protected (tagged, not literal) where it's a
    # pause within one phrase rather than a gloss separator -- splitting first
    # and restoring each part after keeps such a phrase as a single whole
    # alternative instead of tearing it apart.
    alternatives = [
        translation_import.restore_prose_commas(part).strip().casefold()
        for part in source_text.split(',') if part.strip()
    ]
    return user_norm in alternatives, translation_import.format_source_for_display(source_text)
