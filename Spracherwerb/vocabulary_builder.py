"""Vocabulary recall activity: flashcard-style review of the user's translations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from utils import translation_import
from utils.globals import Language
from utils.translations import _

from .activity_registry import ActivityRegistry
from .activity_results import ActivityStartResult, ActivityTurnResult, ModuleServices
from .activity_types import ActivityType
from .base_learning_module import BaseLearningModule
from .bilingual_phrasing import bilingual_phrase
from .learning_memory import LearningMemory
from .recall_matching import check_recall_answer, resolve_recall_direction

# Short target-language phrasings for the languages translation_import already
# special-cases for article detection (_ARTICLE_PREFIXES_BY_LANGUAGE). Paired
# with an English gloss in parentheses (see bilingual_phrasing.bilingual_phrase)
# so the session reads immersively without leaving an unfamiliar target
# language illegible. Unlisted target languages just get the English-only
# fallback text. Not underscore-prefixed: VisualVocabulary reuses this for
# its own text-only fallback (same feedback/prompt wording, no image).
TARGET_PHRASES = {
    'de': {
        'produce_target': 'Wie sagt man „{word}“ auf Deutsch?',
        'recall_source': 'Was bedeutet „{word}“?',
        'correct': 'Richtig!',
        'incorrect': 'Nicht ganz -- die Antwort war „{expected}“.',
        'session_complete': 'Sitzung abgeschlossen: {correct} von {total} richtig.',
    },
    'es': {
        'produce_target': '¿Cómo se dice «{word}» en español?',
        'recall_source': '¿Qué significa «{word}»?',
        'correct': '¡Correcto!',
        'incorrect': 'No exactamente -- la respuesta era «{expected}».',
        'session_complete': 'Sesión completada: {correct} de {total} correctas.',
    },
    'fr': {
        'produce_target': 'Comment dit-on « {word} » en français ?',
        'recall_source': 'Que signifie « {word} » ?',
        'correct': 'Correct !',
        'incorrect': 'Pas tout à fait -- la réponse était « {expected} ».',
        'session_complete': 'Session terminée : {correct} sur {total} correctes.',
    },
    'it': {
        'produce_target': 'Come si dice «{word}» in italiano?',
        'recall_source': 'Cosa significa «{word}»?',
        'correct': 'Corretto!',
        'incorrect': 'Non esattamente -- la risposta era «{expected}».',
        'session_complete': 'Sessione completata: {correct} su {total} corrette.',
    },
}


class VocabularyBuilder(BaseLearningModule):
    """Active recall drilling over the user's structured translations store.

    Direction is proficiency-based: beginners are shown the target-language
    word and recall its source-language meaning (recognition); everyone else
    is shown the source word and must produce the target word (production,
    the harder direction).
    """

    activity_type = ActivityType.VOCABULARY_BUILDER

    def __init__(self):
        self._queue: List[Dict[str, Any]] = []
        self._current: Optional[Dict[str, Any]] = None
        self._direction: str = "produce_target"
        self._known_before: set = set()
        self._new_words: List[str] = []
        self._reviewed_words: List[str] = []
        self._correct_count: int = 0

    def start(self, services: ModuleServices) -> ActivityStartResult:
        source_language, target_language = services.language_pair()
        limit = services.vocabulary_pool.default_session_limit()
        candidates = services.vocabulary_pool.get_review_candidates(
            source_language, target_language, limit=limit)

        self._direction = resolve_recall_direction(services.session_config.proficiency_level)
        self._known_before = {
            word.casefold()
            for word in LearningMemory.vocabulary_learned.get(target_language, [])
        }

        if not candidates:
            return ActivityStartResult(
                text_response=_(
                    "No saved vocabulary to review yet for {0} → {1}. Add some "
                    "translations first."
                ).format(
                    Language.get_language_name(source_language),
                    Language.get_language_name(target_language),
                ),
                activity_type=self.activity_type.value,
                expects_response=False,
            )

        self._queue = candidates
        self._current = self._queue.pop(0)
        return ActivityStartResult(
            text_response=self._build_prompt(self._current, target_language),
            activity_type=self.activity_type.value,
        )

    def handle_response(self, user_text: str, services: ModuleServices) -> ActivityTurnResult:
        if self._current is None:
            return ActivityTurnResult(
                text_response=_("This activity has already finished."),
                activity_type=self.activity_type.value,
                is_complete=True,
            )

        source_language, target_language = services.language_pair()
        is_correct, expected = check_recall_answer(
            self._current, user_text, target_language, self._direction)
        self._record_result(self._current, is_correct, target_language, services)

        if is_correct:
            feedback = bilingual_phrase(target_language, TARGET_PHRASES, 'correct', _("Correct!"))
        else:
            english_feedback = _("Not quite -- the answer was \"{0}\".").format(expected)
            feedback = bilingual_phrase(
                target_language, TARGET_PHRASES, 'incorrect', english_feedback, expected=expected)

        if self._queue:
            self._current = self._queue.pop(0)
            next_prompt = self._build_prompt(self._current, target_language)
            return ActivityTurnResult(
                text_response=f"{feedback}\n\n{next_prompt}",
                activity_type=self.activity_type.value,
                is_complete=False,
                feedback=feedback,
            )

        self._current = None
        total = len(self._reviewed_words) + len(self._new_words)
        english_summary = _("Session complete -- reviewed {0} word(s), {1} correct.").format(
            total, self._correct_count)
        summary = bilingual_phrase(
            target_language, TARGET_PHRASES, 'session_complete', english_summary,
            total=total, correct=self._correct_count)
        return ActivityTurnResult(
            text_response=f"{feedback}\n\n{summary}",
            activity_type=self.activity_type.value,
            is_complete=True,
            feedback=feedback,
        )

    def complete(self, services: ModuleServices) -> Dict[str, Any]:
        total = len(self._reviewed_words) + len(self._new_words)
        accuracy = (self._correct_count / total) if total else 0.0
        return {
            "new_words": list(self._new_words),
            "reviewed_words": list(self._reviewed_words),
            "accuracy": accuracy,
        }

    def _build_prompt(self, entry: Dict[str, Any], target_language: str) -> str:
        if self._direction == "produce_target":
            source_text = translation_import.format_source_for_display(entry.get('source_text', ''))
            english = _("Translate to {0}: {1}").format(
                Language.get_language_name(target_language), source_text)
            return bilingual_phrase(
                target_language, TARGET_PHRASES, 'produce_target', english, word=source_text)
        displayed = translation_import.format_target_for_display(
            entry.get('translated_text', ''), entry.get('target_article', ''), target_language)
        english = _("What does \"{0}\" mean?").format(displayed)
        return bilingual_phrase(
            target_language, TARGET_PHRASES, 'recall_source', english, word=displayed)

    def _record_result(
        self,
        entry: Dict[str, Any],
        is_correct: bool,
        target_language: str,
        services: ModuleServices,
    ) -> None:
        word = translation_import.coerce_str(entry.get('translated_text', ''))
        if not word:
            return
        if word.casefold() in self._known_before:
            self._reviewed_words.append(word)
        else:
            self._new_words.append(word)
        if is_correct:
            self._correct_count += 1
        services.vocabulary_pool.record_word_result(
            target_language, word, outcome="correct" if is_correct else "reviewed")


ActivityRegistry.register(VocabularyBuilder)
