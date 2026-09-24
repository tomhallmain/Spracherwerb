"""Idioms and expressions: a few idioms with meaning/examples, then an
ungraded practice turn.

Deliberately has no scored quiz -- reliably judging whether a free-text
sentence "correctly" uses an idiom is fuzzy in the same way cultural
judgments are (an idiom can be used well in many different, equally valid
ways), so this module only gives encouraging commentary on a practice
attempt rather than pretending to score it. `complete()` reports
`idioms_studied` only; there is no score key.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from utils import translation_import
from utils.globals import Language
from utils.translations import _

from .activity_registry import ActivityRegistry
from .activity_results import ActivityStartResult, ActivityTurnResult, ModuleServices
from .activity_types import ActivityType
from .base_learning_module import BaseLearningModule
from .bilingual_phrasing import bilingual_phrase
from .llm_turn import ask_llm

logger = logging.getLogger(__name__)

LLM_TIMEOUT = 90.0
FEEDBACK_TIMEOUT = 45.0
IDIOMS_PER_SESSION = 3
IDIOM_MARKER_RE = re.compile(r'IDIOM\s*\d+:', re.IGNORECASE)

_DONE_WORDS = {
    "done", "no", "none", "nothing", "n/a", "",
    "fertig", "nein", "nichts",
    "listo", "nada", "terminado",
    "fini", "rien", "termine",
    "fatto", "basta", "niente",
}

META_PHRASES = {
    'de': {
        'unavailable': 'Die Redewendungen sind gerade nicht verfügbar.',
        'invite_practice': 'Versuch, eine dieser Redewendungen in einem eigenen Satz zu '
                            'verwenden, oder sag "fertig", um abzuschließen.',
    },
    'es': {
        'unavailable': 'Las expresiones idiomáticas no están disponibles en este momento.',
        'invite_practice': 'Intenta usar una de estas expresiones en tu propia frase, '
                            'o di "listo" para terminar.',
    },
    'fr': {
        'unavailable': "Les expressions idiomatiques ne sont pas disponibles pour le moment.",
        'invite_practice': 'Essayez d\'utiliser une de ces expressions dans votre propre '
                            'phrase, ou dites « fini » pour terminer.',
    },
    'it': {
        'unavailable': 'Le espressioni idiomatiche non sono disponibili al momento.',
        'invite_practice': 'Prova a usare una di queste espressioni in una tua frase, '
                            'oppure di\' "fatto" per terminare.',
    },
}


class IdiomsAndExpressions(BaseLearningModule):
    """A few idioms with meaning/examples, then one ungraded practice turn."""

    activity_type = ActivityType.IDIOMS_AND_EXPRESSIONS

    def __init__(self):
        self._idioms_studied: List[str] = []
        self._active: bool = False

    def start(self, services: ModuleServices) -> ActivityStartResult:
        target_language = services.session_config.target_language
        self._idioms_studied = []

        try:
            system_prompt = self._build_system_prompt(services)
            query = self._build_intro_query(services)
            turn = ask_llm(services.llm, query, system_prompt=system_prompt, timeout=LLM_TIMEOUT)
        except Exception as e:
            logger.warning(f"IdiomsAndExpressions failed to start: {e}")
            turn = None

        if turn is None:
            self._active = False
            return ActivityStartResult(
                text_response=bilingual_phrase(
                    target_language, META_PHRASES, 'unavailable',
                    _("Idiom practice isn't available right now -- make sure "
                      "the local LLM (Ollama) is running and try again.")),
                activity_type=self.activity_type.value,
                expects_response=False,
            )

        text, _context = turn
        self._idioms_studied = self._parse_idiom_titles(text)
        self._active = True
        prompt = bilingual_phrase(
            target_language, META_PHRASES, 'invite_practice',
            _("Try using one of these idioms in a sentence of your own, or "
              "say \"done\" to finish."))
        return ActivityStartResult(
            text_response=f"{text}\n\n{prompt}",
            activity_type=self.activity_type.value,
        )

    def handle_response(self, user_text: str, services: ModuleServices) -> ActivityTurnResult:
        if not self._active:
            return ActivityTurnResult(
                text_response=_("This activity has already finished."),
                activity_type=self.activity_type.value,
                is_complete=True,
            )

        self._active = False
        if self._is_done(user_text):
            return ActivityTurnResult(
                text_response=_("Session complete: {0} idiom(s) studied.").format(
                    len(self._idioms_studied)),
                activity_type=self.activity_type.value,
                is_complete=True,
            )

        feedback = self._acknowledge_attempt(user_text, services)
        if feedback is None:
            feedback = _("Nice try! Idioms take practice to feel natural -- keep at it.")
        return ActivityTurnResult(
            text_response=feedback,
            activity_type=self.activity_type.value,
            is_complete=True,
        )

    def complete(self, services: ModuleServices) -> Dict[str, Any]:
        return {
            "idioms_studied": list(self._idioms_studied),
        }

    def _build_system_prompt(self, services: ModuleServices) -> str:
        target_language = services.session_config.target_language
        proficiency = services.session_config.proficiency_level or "intermediate"
        base = self.load_activity_prompt(services)
        return (
            f"{base}\n\n"
            f"Teach in {Language.get_language_name(target_language)}, at a "
            f"{proficiency} proficiency level."
        )

    def _build_intro_query(self, services: ModuleServices) -> str:
        source_language, target_language = services.language_pair()
        return (
            f"Introduce exactly {IDIOMS_PER_SESSION} common idioms or fixed "
            f"expressions in {Language.get_language_name(target_language)}. For "
            "each one, on its own line starting with 'IDIOM 1:', 'IDIOM 2:', "
            "etc., give: the idiom itself, its literal meaning, its figurative "
            "meaning, a comparable expression in "
            f"{Language.get_language_name(source_language)} if one exists, and "
            "one example sentence."
        )

    def _parse_idiom_titles(self, text: str) -> List[str]:
        parts = IDIOM_MARKER_RE.split(text)
        titles = []
        for part in parts[1:]:
            first_line = part.strip().split("\n")[0].strip()
            for sep in (" - ", ": ", " — "):
                if sep in first_line:
                    first_line = first_line.split(sep)[0].strip()
                    break
            if first_line:
                titles.append(first_line)
        return titles[:IDIOMS_PER_SESSION]

    def _acknowledge_attempt(self, user_text: str, services: ModuleServices):
        target_language = services.session_config.target_language
        query = (
            f"The learner tried to use one of these idioms in their own "
            f"sentence: {user_text}\n\n"
            "Give brief, encouraging feedback in "
            f"{Language.get_language_name(target_language)} on their attempt "
            "(1-2 sentences). Do not grade it as right or wrong -- just react "
            "naturally, and only gently note anything that reads unnaturally."
        )
        turn = ask_llm(services.llm, query, timeout=FEEDBACK_TIMEOUT)
        if turn is None:
            return None
        text, _context = turn
        return text

    def _is_done(self, user_text: str) -> bool:
        return translation_import.coerce_str(user_text).casefold() in _DONE_WORDS


ActivityRegistry.register(IdiomsAndExpressions)
