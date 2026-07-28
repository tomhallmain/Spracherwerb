"""Grammar practice: one topic, a brief explanation, and a few graded exercises.

Topic and exercises are LLM-generated (per the spec, LLM is the only
required extension for this MVP); the dictionary hint (see dictionary_hint.py)
is an optional touch to ground an exercise in a word the learner already
knows, not a requirement -- it's skipped whenever the dictionary is
unavailable or doesn't have a part of speech for any of the candidate words.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from utils.globals import Language
from utils.translations import I18N

from .activity_registry import ActivityRegistry
from .activity_results import ActivityStartResult, ActivityTurnResult, ModuleServices
from .activity_types import ActivityType
from .base_learning_module import BaseLearningModule
from .bilingual_phrasing import bilingual_phrase
from .dictionary_hint import pick_vocabulary_hint
from .learning_memory import LearningMemory
from .llm_turn import ask_llm

_ = I18N._
logger = logging.getLogger(__name__)

LLM_TIMEOUT = 90.0
GRADE_TIMEOUT = 45.0
EXERCISES_PER_SESSION = 3
EXPLANATION_MARKER = "EXPLANATION:"
EXERCISE_MARKER_RE = re.compile(r'EXERCISE\s*\d+:', re.IGNORECASE)

_TOPICS_BY_LEVEL = {
    "beginner": [
        "present tense verb conjugation",
        "basic word order",
        "definite and indefinite articles",
    ],
    "intermediate": [
        "past tense formation",
        "modal verbs",
        "noun case and agreement",
    ],
    "advanced": [
        "subordinate and relative clauses",
        "passive voice",
        "subjunctive mood",
    ],
}
_DEFAULT_TOPICS = _TOPICS_BY_LEVEL["intermediate"]

META_PHRASES = {
    'de': {
        'unavailable': 'Die Grammatikübung ist gerade nicht verfügbar.',
        'session_complete': 'Sitzung abgeschlossen: {completed} Übung(en) bearbeitet.',
    },
    'es': {
        'unavailable': 'El ejercicio de gramática no está disponible en este momento.',
        'session_complete': 'Sesión completada: {completed} ejercicio(s) realizados.',
    },
    'fr': {
        'unavailable': "L'exercice de grammaire n'est pas disponible pour le moment.",
        'session_complete': 'Session terminée : {completed} exercice(s) effectués.',
    },
    'it': {
        'unavailable': "L'esercizio di grammatica non è disponibile al momento.",
        'session_complete': 'Sessione completata: {completed} esercizio/i svolti.',
    },
}


class GrammarPractice(BaseLearningModule):
    """One grammar topic per session: explanation, then a few graded exercises."""

    activity_type = ActivityType.GRAMMAR_PRACTICE

    def __init__(self):
        self._topic: str = ""
        self._exercises: List[str] = []
        self._exercise_index: int = 0
        self._exercises_completed: int = 0
        self._errors: List[str] = []
        self._active: bool = False

    def start(self, services: ModuleServices) -> ActivityStartResult:
        target_language = services.session_config.target_language
        proficiency = services.session_config.proficiency_level or "intermediate"
        self._topic = self._pick_topic(proficiency)
        self._exercise_index = 0
        self._exercises_completed = 0
        self._errors = []

        try:
            system_prompt = self._build_system_prompt(services)
            vocab_hint = pick_vocabulary_hint(services)
            query = (
                f"Briefly explain the grammar topic '{self._topic}' for the learner, "
                f"then write exactly {EXERCISES_PER_SESSION} short practice exercises "
                "testing it (fill-in-the-blank, correction, or short translation), "
                "each on its own line starting with 'EXERCISE 1:', 'EXERCISE 2:', "
                "etc. Do not include the answers. Start the explanation itself with "
                f"'{EXPLANATION_MARKER}'."
            )
            if vocab_hint:
                query += f" If it fits naturally, use this word the learner already knows: {vocab_hint}."
            turn = ask_llm(services.llm, query, system_prompt=system_prompt, timeout=LLM_TIMEOUT)
        except Exception as e:
            logger.warning(f"GrammarPractice failed to start: {e}")
            turn = None

        if turn is None:
            self._active = False
            return ActivityStartResult(
                text_response=bilingual_phrase(
                    target_language, META_PHRASES, 'unavailable',
                    _("Grammar practice isn't available right now -- make sure "
                      "the local LLM (Ollama) is running and try again.")),
                activity_type=self.activity_type.value,
                expects_response=False,
            )

        text, _context = turn
        explanation, self._exercises = self._parse_lesson(text)
        self._active = True
        return ActivityStartResult(
            text_response=f"{explanation}\n\n{self._exercises[0]}",
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

        feedback = self._grade_exercise(user_text, services)
        if feedback is None:
            feedback = _("Could not check that answer right now, but let's continue.")
        elif feedback.strip().upper().startswith("INCORRECT"):
            self._errors.append(user_text)
        self._exercises_completed += 1
        self._exercise_index += 1

        if self._exercise_index < len(self._exercises):
            next_exercise = self._exercises[self._exercise_index]
            return ActivityTurnResult(
                text_response=f"{feedback}\n\n{next_exercise}",
                activity_type=self.activity_type.value,
                is_complete=False,
                feedback=feedback,
            )

        self._active = False
        summary = bilingual_phrase(
            target_language, META_PHRASES, 'session_complete',
            _("Session complete: {0} exercise(s) completed.").format(self._exercises_completed),
            completed=self._exercises_completed,
        )
        return ActivityTurnResult(
            text_response=f"{feedback}\n\n{summary}",
            activity_type=self.activity_type.value,
            is_complete=True,
            feedback=feedback,
        )

    def complete(self, services: ModuleServices) -> Dict[str, Any]:
        target_language = services.session_config.target_language
        if self._topic:
            LearningMemory.update_grammar(target_language, self._topic)
        return {
            "grammar_points": [self._topic] if self._topic else [],
            "exercises_completed": self._exercises_completed,
            "errors": list(self._errors),
        }

    def _pick_topic(self, proficiency: str) -> str:
        topics = _TOPICS_BY_LEVEL.get(str(proficiency).lower(), _DEFAULT_TOPICS)
        return topics[0]

    def _build_system_prompt(self, services: ModuleServices) -> str:
        target_language = services.session_config.target_language
        proficiency = services.session_config.proficiency_level or "intermediate"
        base = self.load_activity_prompt(services)
        return (
            f"{base}\n\n"
            f"Teach and quiz entirely in {Language.get_language_name(target_language)}, "
            f"at a {proficiency} proficiency level, with explanations a learner at "
            f"that level can follow."
        )

    def _parse_lesson(self, text: str) -> Tuple[str, List[str]]:
        """Returns (explanation, [exercise, ...]). Falls back to a single
        generic exercise if the model didn't include any EXERCISE markers."""
        if EXPLANATION_MARKER in text:
            _before, _marker, text = text.partition(EXPLANATION_MARKER)

        parts = EXERCISE_MARKER_RE.split(text)
        explanation = parts[0].strip()
        exercises = [p.strip() for p in parts[1:] if p.strip()]

        if not exercises:
            exercises = [_("Use today's grammar point in a sentence of your own.")]
        return explanation, exercises[:EXERCISES_PER_SESSION]

    def _grade_exercise(self, user_text: str, services: ModuleServices) -> Optional[str]:
        target_language = services.session_config.target_language
        exercise = self._exercises[self._exercise_index]
        grading_query = (
            f"Exercise: {exercise}\n"
            f"Student's answer: {user_text}\n\n"
            "Was this answer correct? Reply with 'CORRECT' or 'INCORRECT' on "
            "the first line, then one short sentence of feedback in "
            f"{Language.get_language_name(target_language)}."
        )
        turn = ask_llm(services.llm, grading_query, timeout=GRADE_TIMEOUT)
        if turn is None:
            return None
        text, _context = turn
        return text


ActivityRegistry.register(GrammarPractice)
