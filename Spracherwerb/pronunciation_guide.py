"""Pronunciation guide: TTS audio for a few vocabulary items plus concrete
articulation tips, text-first (no microphone input, nothing to grade).

Availability is gated on having vocabulary to practice (same failure mode as
VocabularyBuilder), not on the LLM -- the LLM only supplies enrichment
(articulation tips) for an item that already plays fine from TTS alone, so a
failed tips call degrades that one item to audio-only instead of failing the
whole activity. "Practicing" an item just means the learner moved past it;
there is no answer to verify since nothing captures the learner's own
pronunciation yet.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from utils import translation_import
from utils.globals import Language
from utils.translations import I18N

from .activity_registry import ActivityRegistry
from .activity_results import ActivityStartResult, ActivityTurnResult, ModuleServices
from .activity_types import ActivityType
from .base_learning_module import BaseLearningModule
from .bilingual_phrasing import bilingual_phrase
from .llm_turn import ask_llm

_ = I18N._
logger = logging.getLogger(__name__)

LLM_TIMEOUT = 45.0
ITEMS_PER_SESSION = 5
_REPLAY_WORDS = ("replay", "again", "repeat", "wiederholen", "encore", "otra vez", "ripeti")

META_PHRASES = {
    'de': {
        'instruction': 'Hör dir die Aussprache an, dann tippe irgendetwas, um '
                        'fortzufahren (oder "wiederholen", um es noch einmal zu hören).',
    },
    'es': {
        'instruction': 'Escucha la pronunciación, luego escribe algo para continuar '
                        '(o "otra vez" para escucharla de nuevo).',
    },
    'fr': {
        'instruction': "Écoutez la prononciation, puis tapez quelque chose pour "
                        'continuer (ou « encore » pour la réentendre).',
    },
    'it': {
        'instruction': "Ascolta la pronuncia, poi scrivi qualcosa per continuare "
                        '(oppure "ripeti" per riascoltarla).',
    },
}


class PronunciationGuide(BaseLearningModule):
    """A few words/phrases: TTS audio plus LLM articulation tips per item."""

    activity_type = ActivityType.PRONUNCIATION_GUIDE

    def __init__(self):
        self._queue: List[Dict[str, Any]] = []
        self._current: Optional[Dict[str, Any]] = None
        self._items_practiced: List[str] = []
        self._notes: List[str] = []
        self._audio_paths: List[str] = []
        self._replay_count: int = 0
        self._system_prompt: str = ""
        self._active: bool = False

    def start(self, services: ModuleServices) -> ActivityStartResult:
        source_language, target_language = services.language_pair()
        candidates = services.vocabulary_pool.get_review_candidates(
            source_language, target_language, limit=ITEMS_PER_SESSION)
        self._items_practiced = []
        self._notes = []
        self._audio_paths = []
        self._replay_count = 0

        if not candidates:
            self._active = False
            return ActivityStartResult(
                text_response=_(
                    "No saved vocabulary to practice yet for {0} → {1}. Add some "
                    "translations first."
                ).format(
                    Language.get_language_name(source_language),
                    Language.get_language_name(target_language),
                ),
                activity_type=self.activity_type.value,
                expects_response=False,
            )

        try:
            self._system_prompt = self._build_system_prompt(services)
        except Exception as e:
            logger.warning(f"PronunciationGuide failed to load its activity prompt: {e}")
            self._system_prompt = ""

        self._queue = candidates
        self._current = self._queue.pop(0)
        self._active = True
        text, voice_path = self._present_item(self._current, services)
        return ActivityStartResult(
            text_response=text,
            activity_type=self.activity_type.value,
            voice_response=voice_path,
        )

    def handle_response(self, user_text: str, services: ModuleServices) -> ActivityTurnResult:
        if not self._active:
            return ActivityTurnResult(
                text_response=_("This activity has already finished."),
                activity_type=self.activity_type.value,
                is_complete=True,
            )

        if self._is_replay_request(user_text):
            self._replay_count += 1
            text, voice_path = self._present_item(self._current, services, replay=True)
            return ActivityTurnResult(
                text_response=text,
                activity_type=self.activity_type.value,
                is_complete=False,
                voice_response=voice_path,
            )

        word = translation_import.coerce_str(self._current.get('translated_text', ''))
        if word:
            self._items_practiced.append(word)

        if self._queue:
            self._current = self._queue.pop(0)
            text, voice_path = self._present_item(self._current, services)
            return ActivityTurnResult(
                text_response=text,
                activity_type=self.activity_type.value,
                is_complete=False,
                voice_response=voice_path,
            )

        self._active = False
        summary = _("Session complete: {0} item(s) practiced.").format(
            len(self._items_practiced))
        return ActivityTurnResult(
            text_response=summary,
            activity_type=self.activity_type.value,
            is_complete=True,
        )

    def complete(self, services: ModuleServices) -> Dict[str, Any]:
        return {
            "items_practiced": list(self._items_practiced),
            "notes": list(self._notes),
        }

    def _build_system_prompt(self, services: ModuleServices) -> str:
        source_language, target_language = services.language_pair()
        proficiency = services.session_config.proficiency_level or "intermediate"
        base = self.load_activity_prompt(services)
        return (
            f"{base}\n\n"
            f"The learner is practicing pronunciation in "
            f"{Language.get_language_name(target_language)}, at a {proficiency} "
            f"proficiency level. For each word or phrase given, provide concrete "
            f"articulation guidance: mouth/tongue position, sounds likely to be "
            f"difficult for a speaker of {Language.get_language_name(source_language)}, "
            f"and any stress or intonation notes. Do not give generic praise or "
            f"encouragement -- only concrete, actionable pronunciation guidance, "
            f"in 2-3 sentences."
        )

    def _present_item(
        self, entry: Dict[str, Any], services: ModuleServices, replay: bool = False,
    ) -> Tuple[str, Optional[str]]:
        target_language = services.session_config.target_language
        displayed = translation_import.format_target_for_display(
            entry.get('translated_text', ''), entry.get('target_article', ''), target_language)
        voice_path = self._speak_item(displayed, services)
        instruction = bilingual_phrase(
            target_language, META_PHRASES, 'instruction',
            _("Listen to the pronunciation, then type anything to continue "
              "(or \"replay\" to hear it again)."))

        if replay:
            return f"{displayed}\n\n{instruction}", voice_path

        tips = self._get_articulation_tips(displayed, services)
        if tips:
            self._notes.append(tips)
        else:
            tips = _("(Could not fetch articulation tips right now.)")
        return f"{displayed}\n\n{tips}\n\n{instruction}", voice_path

    def _speak_item(self, text: str, services: ModuleServices) -> Optional[str]:
        try:
            path = services.voice.generate_speech(text, topic="pronunciation_guide")
        except Exception as e:
            logger.warning(f"PronunciationGuide TTS failed: {e}")
            return None
        if path:
            self._audio_paths.append(path)
        return path

    def _get_articulation_tips(self, word: str, services: ModuleServices) -> Optional[str]:
        query = f"Give concrete articulation tips for pronouncing this word or phrase: \"{word}\""
        turn = ask_llm(services.llm, query, system_prompt=self._system_prompt, timeout=LLM_TIMEOUT)
        if turn is None:
            return None
        text, _context = turn
        return text

    def _is_replay_request(self, user_text: str) -> bool:
        normalized = translation_import.coerce_str(user_text).casefold()
        return any(word in normalized for word in _REPLAY_WORDS)


ActivityRegistry.register(PronunciationGuide)
