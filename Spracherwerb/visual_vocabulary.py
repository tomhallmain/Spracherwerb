"""Image-mediated vocabulary recall: see a generated picture, recall the word.

Extends VocabularyBuilder's drilling loop with a generated image as the
stimulus instead of text. Generation is optional and best-effort: SD Runner
reachability is checked once at session start, and any failure (unreachable,
timed out, generation error) falls back to VocabularyBuilder-style text
prompts for that turn rather than blocking or erroring out -- see the MVP
acceptance criterion "skips gracefully when SD unavailable" in
docs/main_modules/module_specifications.md.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils import translation_import
from utils.globals import Language
from utils.translations import I18N

from .activity_registry import ActivityRegistry
from .activity_results import ActivityStartResult, ActivityTurnResult, ModuleServices
from .activity_types import ActivityType
from .base_learning_module import BaseLearningModule
from .bilingual_phrasing import bilingual_phrase
from .learning_memory import LearningMemory
from .recall_matching import check_recall_answer, resolve_recall_direction
from .vocabulary_builder import TARGET_PHRASES as TEXT_PHRASES

_ = I18N._
logger = logging.getLogger(__name__)

IMAGE_CACHE_DIR = Path("cache/visual_vocabulary")
_IMAGE_EXTENSIONS = ("png", "jpg", "jpeg", "webp")

# Only the two prompt phrasings differ when an image is shown instead of
# text; feedback/session-complete wording is identical either way, so those
# come from vocabulary_builder.TEXT_PHRASES rather than being duplicated here.
IMAGE_PHRASES = {
    'de': {
        'produce_target': 'Wie heißt das auf Deutsch?',
        'recall_source': 'Was zeigt das Bild?',
    },
    'es': {
        'produce_target': '¿Cómo se llama esto en español?',
        'recall_source': '¿Qué muestra la imagen?',
    },
    'fr': {
        'produce_target': "Comment ça s'appelle en français ?",
        'recall_source': "Que montre l'image ?",
    },
    'it': {
        'produce_target': 'Come si chiama questo in italiano?',
        'recall_source': "Cosa mostra l'immagine?",
    },
}


class VisualVocabulary(BaseLearningModule):
    """Image-mediated recall: generate/reuse an image per word, then quiz on it."""

    activity_type = ActivityType.VISUAL_VOCABULARY

    def __init__(self):
        self._queue: List[Dict[str, Any]] = []
        self._current: Optional[Dict[str, Any]] = None
        self._direction: str = "produce_target"
        self._known_before: set = set()
        self._new_words: List[str] = []
        self._reviewed_words: List[str] = []
        self._correct_count: int = 0
        self._images_generated: int = 0
        self._sd_available: bool = False

    def start(self, services: ModuleServices) -> ActivityStartResult:
        source_language, target_language = services.language_pair()
        limit = services.vocabulary_pool.default_session_limit()
        candidates = services.vocabulary_pool.get_review_candidates(
            source_language, target_language, limit=limit)
        candidates = self._prefer_probable_nouns(candidates)

        self._direction = resolve_recall_direction(services.session_config.proficiency_level)
        self._known_before = {
            word.casefold()
            for word in LearningMemory.vocabulary_learned.get(target_language, [])
        }
        self._sd_available = (
            bool(getattr(services.session_config, 'enable_visual_learning', True))
            and self._check_sd_available(services)
        )

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
        prompt_text, media_path = self._prepare_turn(self._current, services)
        return ActivityStartResult(
            text_response=prompt_text,
            activity_type=self.activity_type.value,
            media_path=media_path,
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
            feedback = bilingual_phrase(target_language, TEXT_PHRASES, 'correct', _("Correct!"))
        else:
            english_feedback = _("Not quite -- the answer was \"{0}\".").format(expected)
            feedback = bilingual_phrase(
                target_language, TEXT_PHRASES, 'incorrect', english_feedback, expected=expected)

        if self._queue:
            self._current = self._queue.pop(0)
            next_prompt, media_path = self._prepare_turn(self._current, services)
            return ActivityTurnResult(
                text_response=f"{feedback}\n\n{next_prompt}",
                activity_type=self.activity_type.value,
                is_complete=False,
                feedback=feedback,
                media_path=media_path,
            )

        self._current = None
        total = len(self._reviewed_words) + len(self._new_words)
        english_summary = _("Session complete -- reviewed {0} word(s), {1} correct.").format(
            total, self._correct_count)
        summary = bilingual_phrase(
            target_language, TEXT_PHRASES, 'session_complete', english_summary,
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
            "words_reviewed": list(self._reviewed_words) + list(self._new_words),
            "new_words": list(self._new_words),
            "reviewed_words": list(self._reviewed_words),
            "images_generated": self._images_generated,
            "accuracy": accuracy,
        }

    # -- word selection ------------------------------------------------

    def _prefer_probable_nouns(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort candidates with a stored article (probably a concrete noun) first.

        Images work best for concrete objects; a stored ``target_article``
        is this project's existing cheap signal for "probably a noun" (see
        ``translation_import.index_bare_noun_fallback``), reused here rather
        than adding a second noun-detection heuristic.
        """
        with_article = [e for e in candidates if translation_import.coerce_str(e.get('target_article'))]
        without_article = [e for e in candidates if not translation_import.coerce_str(e.get('target_article'))]
        return with_article + without_article

    # -- turn construction -----------------------------------------------

    def _prepare_turn(self, entry: Dict[str, Any], services: ModuleServices) -> Tuple[str, Optional[str]]:
        source_language, target_language = services.language_pair()
        media_path = self._get_or_generate_image(entry, target_language, services)
        prompt_text = self._build_prompt(entry, source_language, target_language, media_path is not None)
        return prompt_text, media_path

    def _build_prompt(
        self, entry: Dict[str, Any], source_language: str, target_language: str, has_image: bool,
    ) -> str:
        if has_image:
            if self._direction == "produce_target":
                english = _("What is this called in {0}?").format(
                    Language.get_language_name(target_language))
                return bilingual_phrase(target_language, IMAGE_PHRASES, 'produce_target', english)
            english = _("What does the picture show, in {0}?").format(
                Language.get_language_name(source_language))
            return bilingual_phrase(target_language, IMAGE_PHRASES, 'recall_source', english)

        # No image this turn -- fall back to VocabularyBuilder's text prompts.
        if self._direction == "produce_target":
            source_text = translation_import.coerce_str(entry.get('source_text', ''))
            english = _("Translate to {0}: {1}").format(
                Language.get_language_name(target_language), source_text)
            return bilingual_phrase(
                target_language, TEXT_PHRASES, 'produce_target', english, word=source_text)
        displayed = translation_import.format_target_for_display(
            entry.get('translated_text', ''), entry.get('target_article', ''), target_language)
        english = _("What does \"{0}\" mean?").format(displayed)
        return bilingual_phrase(
            target_language, TEXT_PHRASES, 'recall_source', english, word=displayed)

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

    # -- image generation --------------------------------------------------

    def _check_sd_available(self, services: ModuleServices) -> bool:
        sd_client = getattr(services, 'sd_client', None)
        if sd_client is None:
            return False
        try:
            return sd_client.is_reachable()
        except Exception as e:
            logger.warning(f"SD Runner reachability check failed: {e}")
            return False

    def _slug_for(self, target_language: str, entry: Dict[str, Any]) -> str:
        word = translation_import.coerce_str(entry.get('translated_text', ''))
        slug = re.sub(r'[^a-z0-9]+', '_', word.casefold()).strip('_') or 'word'
        return f"{target_language}_{slug}"

    def _find_cached_image(self, slug: str) -> Optional[str]:
        for ext in _IMAGE_EXTENSIONS:
            candidate = IMAGE_CACHE_DIR / f"{slug}.{ext}"
            if candidate.exists():
                return str(candidate)
        return None

    def _get_or_generate_image(
        self, entry: Dict[str, Any], target_language: str, services: ModuleServices,
    ) -> Optional[str]:
        if not self._sd_available:
            return None

        slug = self._slug_for(target_language, entry)
        cached = self._find_cached_image(slug)
        if cached:
            return cached

        gloss = translation_import.coerce_str(entry.get('source_text', '')).split(',')[0].strip()
        if not gloss:
            return None

        try:
            IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            image_path = services.sd_client.generate_image(
                positive_prompt=f"{gloss}, simple clear illustration, single subject, plain background",
                target_dir=str(IMAGE_CACHE_DIR),
                filename=slug,
            )
        except Exception as e:
            logger.warning(f"VisualVocabulary image generation failed for {slug!r}: {e}")
            return None

        if image_path:
            self._images_generated += 1
        return image_path


ActivityRegistry.register(VisualVocabulary)
