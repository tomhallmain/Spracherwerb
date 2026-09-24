"""Cultural context: one LLM-presented cultural note, plus open follow-up Q&A.

Deliberately not drill-focused, and deliberately never grades a response:
unlike grammar or vocabulary recall,
there's rarely one "correct" cultural observation to check a learner's
question or reaction against, so this module only acknowledges what the
learner says (via the LLM's own reply) rather than pretending to score it.
Capped at a few follow-up turns so an open-ended "ask anything" activity
still has a natural end.
"""

from __future__ import annotations

import logging
import random
from typing import Any, Dict

from utils import translation_import
from utils.globals import Language
from utils.translations import _

from .activity_registry import ActivityRegistry
from .activity_results import ActivityStartResult, ActivityTurnResult, ModuleServices
from .activity_types import ActivityType
from .base_learning_module import BaseLearningModule
from .bilingual_phrasing import bilingual_phrase
from .dictionary_hint import pick_vocabulary_hint
from .llm_turn import ask_llm

logger = logging.getLogger(__name__)

LLM_TIMEOUT = 60.0
MAX_FOLLOW_UP_QUESTIONS = 3

_TOPICS = [
    "holidays and celebrations",
    "everyday etiquette and manners",
    "humor and communication style",
    "food culture and dining customs",
    "family and social structure",
]

_DONE_WORDS = {
    "done", "no", "none", "nothing", "n/a", "",
    "fertig", "nein", "nichts",
    "listo", "nada", "terminado",
    "fini", "rien", "termine",
    "fatto", "basta", "niente",
}

META_PHRASES = {
    'de': {
        'unavailable': 'Der Kulturimpuls ist gerade nicht verfügbar.',
        'invite_question': 'Möchtest du eine Frage dazu stellen? Oder sag "fertig", um abzuschließen.',
    },
    'es': {
        'unavailable': 'La nota cultural no está disponible en este momento.',
        'invite_question': '¿Quieres hacer una pregunta al respecto? O di "listo" para terminar.',
    },
    'fr': {
        'unavailable': "La note culturelle n'est pas disponible pour le moment.",
        'invite_question': 'Voulez-vous poser une question à ce sujet ? Ou dites « fini » pour terminer.',
    },
    'it': {
        'unavailable': 'La nota culturale non è disponibile al momento.',
        'invite_question': 'Vuoi fare una domanda a riguardo? Oppure di\' "fatto" per terminare.',
    },
}


class CulturalContext(BaseLearningModule):
    """One cultural topic, then up to a few ungraded follow-up turns."""

    activity_type = ActivityType.CULTURAL_CONTEXT

    def __init__(self):
        self._topic: str = ""
        self._context = None
        self._questions_answered: int = 0
        self._active: bool = False
        self._system_prompt: str = ""

    def start(self, services: ModuleServices) -> ActivityStartResult:
        target_language = services.session_config.target_language
        self._topic = random.choice(_TOPICS)
        self._questions_answered = 0
        self._context = None

        try:
            self._system_prompt = self._build_system_prompt(services)
            vocab_hint = pick_vocabulary_hint(services)
            query = (
                f"Present a short, interesting cultural note about {self._topic} "
                "for the target-language culture, suited to the learner's level. "
                "Keep it to a few sentences."
            )
            if vocab_hint:
                query += (
                    f" If it fits naturally, connect the note to this word the "
                    f"learner already knows: {vocab_hint}."
                )
            turn = ask_llm(services.llm, query, system_prompt=self._system_prompt, timeout=LLM_TIMEOUT)
        except Exception as e:
            logger.warning(f"CulturalContext failed to start: {e}")
            turn = None

        if turn is None:
            self._active = False
            return ActivityStartResult(
                text_response=bilingual_phrase(
                    target_language, META_PHRASES, 'unavailable',
                    _("This cultural note isn't available right now -- make sure "
                      "the local LLM (Ollama) is running and try again.")),
                activity_type=self.activity_type.value,
                expects_response=False,
            )

        self._active = True
        response_text, self._context = turn
        prompt = self._invite_question(target_language)
        return ActivityStartResult(
            text_response=f"{response_text}\n\n{prompt}",
            activity_type=self.activity_type.value,
        )

    def handle_response(self, user_text: str, services: ModuleServices) -> ActivityTurnResult:
        target_language = services.session_config.target_language
        if not self._active:
            return ActivityTurnResult(
                text_response=_("This activity has already finished."),
                activity_type=self.activity_type.value,
                is_complete=True,
            )

        if self._is_done(user_text):
            self._active = False
            return ActivityTurnResult(
                text_response=_("Session complete: {0} question(s) discussed.").format(
                    self._questions_answered),
                activity_type=self.activity_type.value,
                is_complete=True,
            )

        self._questions_answered += 1
        turn = ask_llm(
            services.llm, user_text, system_prompt=self._system_prompt,
            context=self._context, timeout=LLM_TIMEOUT,
        )
        if turn is None:
            self._active = False
            return ActivityTurnResult(
                text_response=_("Lost the connection, but thanks for exploring this topic!"),
                activity_type=self.activity_type.value,
                is_complete=True,
            )

        response_text, self._context = turn
        if self._questions_answered >= MAX_FOLLOW_UP_QUESTIONS:
            self._active = False
            summary = _("Session complete: {0} question(s) discussed.").format(
                self._questions_answered)
            return ActivityTurnResult(
                text_response=f"{response_text}\n\n{summary}",
                activity_type=self.activity_type.value,
                is_complete=True,
            )

        prompt = self._invite_question(target_language)
        return ActivityTurnResult(
            text_response=f"{response_text}\n\n{prompt}",
            activity_type=self.activity_type.value,
            is_complete=False,
        )

    def complete(self, services: ModuleServices) -> Dict[str, Any]:
        return {
            "topics": [self._topic] if self._topic else [],
            "questions_answered": self._questions_answered,
        }

    def _build_system_prompt(self, services: ModuleServices) -> str:
        target_language = services.session_config.target_language
        proficiency = services.session_config.proficiency_level or "intermediate"
        base = self.load_activity_prompt(services)
        return (
            f"{base}\n\n"
            f"Discuss in {Language.get_language_name(target_language)}, at a "
            f"{proficiency} proficiency level. This is an informal cultural "
            f"discussion, not a test -- never grade or mark the learner's "
            f"questions or reactions as right or wrong, just respond naturally "
            f"and informatively."
        )

    def _invite_question(self, target_language: str) -> str:
        return bilingual_phrase(
            target_language, META_PHRASES, 'invite_question',
            _("Feel free to ask a follow-up question, or say \"done\" to finish."))

    def _is_done(self, user_text: str) -> bool:
        return translation_import.coerce_str(user_text).casefold() in _DONE_WORDS


ActivityRegistry.register(CulturalContext)
