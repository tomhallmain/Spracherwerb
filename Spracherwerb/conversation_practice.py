"""Open-ended conversation practice with an LLM-driven tutor persona.

The tutor's own dialogue comes back from the LLM already in the target
language (instructed via the system prompt), so unlike VocabularyBuilder/
VisualVocabulary there's no fixed phrasebook for the conversation content
itself -- only the meta messages (unavailable / session-complete) are
bilingual-templated the same way.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

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

MAX_TURNS = 10
LLM_TIMEOUT = 60.0

_FAREWELL_WORDS = (
    "bye", "goodbye", "quit", "stop", "end conversation",
    "tschüss", "auf wiedersehen", "adios", "adiós", "au revoir", "arrivederci",
)

META_PHRASES = {
    'de': {
        'unavailable': 'Der Gesprächspartner ist gerade nicht erreichbar.',
        'session_complete': 'Sitzung abgeschlossen nach {turns} Runde(n).',
    },
    'es': {
        'unavailable': 'El compañero de conversación no está disponible en este momento.',
        'session_complete': 'Sesión completada después de {turns} turno(s).',
    },
    'fr': {
        'unavailable': "Le partenaire de conversation n'est pas disponible pour le moment.",
        'session_complete': 'Session terminée après {turns} tour(s).',
    },
    'it': {
        'unavailable': 'Il partner di conversazione non è disponibile al momento.',
        'session_complete': 'Sessione completata dopo {turns} turno/i.',
    },
}


class ConversationPractice(BaseLearningModule):
    """Multi-turn dialogue with the LLM playing a tutor persona in the target language.

    Ends when the turn limit is hit or the learner's message contains a
    farewell word (a plain substring check, not real intent detection --
    kept intentionally simple rather than adding real NLU for an MVP).
    """

    activity_type = ActivityType.CONVERSATION_PRACTICE

    def __init__(self):
        self._context = None
        self._turn_count = 0
        self._active = False
        self._system_prompt = ""

    def start(self, services: ModuleServices) -> ActivityStartResult:
        target_language = services.session_config.target_language
        self._turn_count = 0
        self._context = None

        try:
            self._system_prompt = self._build_system_prompt(services)
            turn = ask_llm(
                services.llm,
                "Start the conversation now: greet the learner briefly and ask an "
                "opening question to get the conversation going.",
                system_prompt=self._system_prompt,
                timeout=LLM_TIMEOUT,
            )
        except Exception as e:
            logger.warning(f"ConversationPractice failed to start: {e}")
            turn = None

        if turn is None:
            self._active = False
            return ActivityStartResult(
                text_response=bilingual_phrase(
                    target_language, META_PHRASES, 'unavailable',
                    _("The conversation partner isn't available right now -- make "
                      "sure the local LLM (Ollama) is running and try again.")),
                activity_type=self.activity_type.value,
                expects_response=False,
            )

        self._active = True
        response_text, self._context = turn
        return ActivityStartResult(
            text_response=response_text,
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

        self._turn_count += 1
        turn = ask_llm(
            services.llm, user_text, system_prompt=self._system_prompt,
            context=self._context, timeout=LLM_TIMEOUT,
        )
        if turn is None:
            self._active = False
            return ActivityTurnResult(
                text_response=bilingual_phrase(
                    target_language, META_PHRASES, 'unavailable',
                    _("Lost the connection to the conversation partner.")),
                activity_type=self.activity_type.value,
                is_complete=True,
            )

        response_text, self._context = turn
        should_end = self._turn_count >= MAX_TURNS or self._user_said_farewell(user_text)
        if should_end:
            self._active = False
            summary = bilingual_phrase(
                target_language, META_PHRASES, 'session_complete',
                _("Session complete after {0} turn(s).").format(self._turn_count),
                turns=self._turn_count,
            )
            response_text = f"{response_text}\n\n{summary}"
        return ActivityTurnResult(
            text_response=response_text,
            activity_type=self.activity_type.value,
            is_complete=should_end,
        )

    def complete(self, services: ModuleServices) -> Dict[str, Any]:
        return {
            "turns": self._turn_count,
            "corrections": [],
            "new_vocab": [],
        }

    def _build_system_prompt(self, services: ModuleServices) -> str:
        target_language = services.session_config.target_language
        proficiency = services.session_config.proficiency_level or "intermediate"
        base = self.load_activity_prompt(services)
        return (
            f"{base}\n\n"
            f"Respond only in {Language.get_language_name(target_language)}, at a "
            f"{proficiency} proficiency level. If the learner makes a significant "
            f"grammar or vocabulary error, gently correct it as part of your "
            f"natural reply before continuing the conversation. Keep each reply "
            f"to a few sentences."
        )

    def _user_said_farewell(self, user_text: str) -> bool:
        normalized = translation_import.coerce_str(user_text).casefold()
        return any(word in normalized for word in _FAREWELL_WORDS)


ActivityRegistry.register(ConversationPractice)
