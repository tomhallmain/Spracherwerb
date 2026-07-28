"""Writing practice: one free-text submission, graded by LanguageTool + LLM.

LanguageTool supplies rule-based corrections when reachable (no API key
required for the public endpoint; the module respects a configured key when
present). If LanguageTool is unavailable, or if the dictionary hint (see
dictionary_hint.py) can't find a usable part of speech for any candidate
word, the module degrades to LLM-only feedback rather than failing --
matching the MVP's "degrades gracefully if LanguageTool key missing" bar.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from utils.globals import Language
from utils.translations import I18N

from .activity_registry import ActivityRegistry
from .activity_results import ActivityStartResult, ActivityTurnResult, ModuleServices
from .activity_types import ActivityType
from .base_learning_module import BaseLearningModule
from .bilingual_phrasing import bilingual_phrase
from .dictionary_hint import pick_vocabulary_hint
from .llm_turn import ask_llm

_ = I18N._
logger = logging.getLogger(__name__)

LLM_TIMEOUT = 60.0
FEEDBACK_TIMEOUT = 45.0
MAX_CORRECTIONS_SHOWN = 5

META_PHRASES = {
    'de': {
        'unavailable': 'Die Schreibübung ist gerade nicht verfügbar.',
    },
    'es': {
        'unavailable': 'El ejercicio de escritura no está disponible en este momento.',
    },
    'fr': {
        'unavailable': "L'exercice d'écriture n'est pas disponible pour le moment.",
    },
    'it': {
        'unavailable': "L'esercizio di scrittura non è disponibile al momento.",
    },
}


class WritingPractice(BaseLearningModule):
    """One free-text submission per session, with rule-based + LLM feedback."""

    activity_type = ActivityType.WRITING_PRACTICE

    def __init__(self):
        self._submission: str = ""
        self._corrections: List[str] = []
        self._grammar_tags: List[str] = []
        self._active: bool = False

    def start(self, services: ModuleServices) -> ActivityStartResult:
        target_language = services.session_config.target_language
        self._submission = ""
        self._corrections = []
        self._grammar_tags = []

        try:
            system_prompt = self._build_system_prompt(services)
            vocab_hint = pick_vocabulary_hint(services)
            query = (
                "Give the learner a short writing prompt: ask them to write a "
                "few sentences in the target language about an everyday topic."
            )
            if vocab_hint:
                query += f" If it fits naturally, suggest they use this word they already know: {vocab_hint}."
            turn = ask_llm(services.llm, query, system_prompt=system_prompt, timeout=LLM_TIMEOUT)
        except Exception as e:
            logger.warning(f"WritingPractice failed to start: {e}")
            turn = None

        if turn is None:
            self._active = False
            return ActivityStartResult(
                text_response=bilingual_phrase(
                    target_language, META_PHRASES, 'unavailable',
                    _("Writing practice isn't available right now -- make sure "
                      "the local LLM (Ollama) is running and try again.")),
                activity_type=self.activity_type.value,
                expects_response=False,
            )

        prompt_text, _context = turn
        self._active = True
        return ActivityStartResult(
            text_response=prompt_text,
            activity_type=self.activity_type.value,
        )

    def handle_response(self, user_text: str, services: ModuleServices) -> ActivityTurnResult:
        if not self._active:
            return ActivityTurnResult(
                text_response=_("This activity has already finished."),
                activity_type=self.activity_type.value,
                is_complete=True,
            )

        self._submission = user_text
        self._active = False

        errors = self._check_with_language_tool(user_text, services)
        llm_feedback = self._get_llm_feedback(user_text, errors, services)

        parts = []
        if errors:
            parts.append(self._format_corrections(errors))
            self._corrections = [error.message for error in errors]
            self._grammar_tags = sorted({error.rule_category for error in errors if error.rule_category})
        if llm_feedback:
            parts.append(llm_feedback)
        if not parts:
            parts.append(_("Nice work -- no issues found!"))

        return ActivityTurnResult(
            text_response="\n\n".join(parts),
            activity_type=self.activity_type.value,
            is_complete=True,
        )

    def complete(self, services: ModuleServices) -> Dict[str, Any]:
        return {
            "submissions": [self._submission] if self._submission else [],
            "corrections": list(self._corrections),
            "grammar_tags": list(self._grammar_tags),
        }

    def _build_system_prompt(self, services: ModuleServices) -> str:
        target_language = services.session_config.target_language
        proficiency = services.session_config.proficiency_level or "intermediate"
        base = self.load_activity_prompt(services)
        return (
            f"{base}\n\n"
            f"Write only in {Language.get_language_name(target_language)}, at a "
            f"{proficiency} proficiency level."
        )

    def _check_with_language_tool(self, text: str, services: ModuleServices) -> list:
        language_tool = getattr(services, 'language_tool', None)
        if language_tool is None:
            return []
        target_language = services.session_config.target_language
        try:
            return language_tool.check_text(text, target_language)
        except Exception as e:
            logger.warning(f"LanguageTool check failed: {e}")
            return []

    def _format_corrections(self, errors: list) -> str:
        lines = []
        for error in errors[:MAX_CORRECTIONS_SHOWN]:
            line = f"- {error.short_message or error.message}"
            if error.replacements:
                line += f" → {', '.join(error.replacements[:3])}"
            lines.append(line)
        return _("Corrections:") + "\n" + "\n".join(lines)

    def _get_llm_feedback(self, text: str, errors: list, services: ModuleServices) -> Optional[str]:
        target_language = services.session_config.target_language
        note = ""
        if errors:
            note = (
                f" LanguageTool already flagged {len(errors)} issue(s) separately; "
                "focus your comments on content, clarity, and style instead of "
                "repeating those corrections."
            )
        query = (
            f"The learner wrote: {text}\n\n"
            f"Give brief, encouraging feedback in {Language.get_language_name(target_language)} "
            f"on their writing (content and clarity), in 1-3 sentences.{note}"
        )
        turn = ask_llm(services.llm, query, timeout=FEEDBACK_TIMEOUT)
        if turn is None:
            return None
        text_response, _context = turn
        return text_response


ActivityRegistry.register(WritingPractice)
