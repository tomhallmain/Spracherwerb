"""Conceptual learning: one broad rule that applies across the language, shown
through examples and checked with LLM-authored multiple-choice questions.

The LLM authors the whole lesson (see concept_questions.py for the format).
It is not limited to the learner's saved translations, but gets a sample of
them and is asked to reuse the ones that fit the concept, so the rule gets
anchored in words the learner is already working on. Saved words found in a
question the learner answers correctly are recorded as reviewed.

Answers are graded locally against the validated option list -- no second
LLM call per turn, unlike GrammarPractice's free-text grading. Only the
target-language example sentences and answer explanations are given to TTS
(via `voice_text`).
"""

from __future__ import annotations

import logging
import random
import re
from typing import Any, Dict, List, Optional

from utils import translation_import
from utils.globals import Language
from utils.translations import _

from .activity_registry import ActivityRegistry
from .activity_results import ActivityStartResult, ActivityTurnResult, ModuleServices
from .activity_types import ActivityType
from .base_learning_module import BaseLearningModule
from .bilingual_phrasing import bilingual_phrase
from .concept_questions import ConceptLesson, ConceptQuestion, parse_concept_lesson
from .learning_memory import LearningMemory
from .llm_turn import ask_llm

logger = logging.getLogger(__name__)

LLM_TIMEOUT = 120.0
# A second request only follows a reply that couldn't be used; an unreachable
# LLM isn't retried, since each attempt can wait out the full timeout.
LESSON_ATTEMPTS = 2
QUESTIONS_PER_SESSION = 3
SAVED_PHRASES_LIMIT = 8
# Recently covered concepts listed to the LLM when it picks its own concept.
RECENT_CONCEPTS_LIMIT = 20

# Seeds only: phrased broadly so most can carry across languages, and the
# LLM may swap in a comparable concept when one doesn't apply to the target
# language. Once every seed for a level is covered the LLM picks freely.
_CONCEPTS_BY_LEVEL = {
    "beginner": [
        "where the verb goes in a basic statement",
        "how questions are formed",
        "how grammatical gender shows up in articles and other words",
    ],
    "intermediate": [
        "word order in subordinate clauses",
        "how case or prepositions mark a noun's role in the sentence",
        "verbs whose meaning is built from a prefix or particle",
    ],
    "advanced": [
        "how word order signals emphasis and new versus known information",
        "building new words through compounding and derivation",
        "nominal versus verbal style in formal writing",
    ],
}
_DEFAULT_LEVEL = "intermediate"

META_PHRASES = {
    'de': {
        'unavailable': 'Das Konzepttraining ist gerade nicht verfügbar.',
        'session_complete': 'Sitzung abgeschlossen: {correct} von {answered} richtig.',
    },
    'es': {
        'unavailable': 'La práctica de conceptos no está disponible en este momento.',
        'session_complete': 'Sesión completada: {correct} de {answered} correctas.',
    },
    'fr': {
        'unavailable': "La pratique des concepts n'est pas disponible pour le moment.",
        'session_complete': 'Session terminée : {correct} sur {answered} correctes.',
    },
    'it': {
        'unavailable': 'La pratica dei concetti non è disponibile al momento.',
        'session_complete': 'Sessione completata: {correct} su {answered} corrette.',
    },
}


class ConceptualLearning(BaseLearningModule):
    """One broad language concept per session: explanation, examples, then
    multiple-choice questions graded against the options the LLM supplied."""

    activity_type = ActivityType.CONCEPTUAL_LEARNING

    def __init__(self, rng: Optional[random.Random] = None):
        self._rng = rng or random.Random()
        self._concept: str = ""
        self._seed_concept: str = ""
        self._questions: List[ConceptQuestion] = []
        self._question_index: int = 0
        self._correct_answers: int = 0
        self._errors: List[str] = []
        self._reviewed_words: List[str] = []
        self._active: bool = False

    def start(self, services: ModuleServices) -> ActivityStartResult:
        target_language = services.session_config.target_language
        self._question_index = 0
        self._correct_answers = 0
        self._errors = []
        self._reviewed_words = []
        self._seed_concept = self._pick_seed_concept(services) or ""
        self._concept = self._seed_concept

        lesson = None
        saved_entries: List[Dict[str, Any]] = []
        try:
            saved_entries = self._saved_entries(services)
            lesson = self._request_lesson(services, saved_entries)
        except Exception as e:
            logger.warning(f"ConceptualLearning failed to start: {e}")

        if lesson is None:
            self._active = False
            return ActivityStartResult(
                text_response=bilingual_phrase(
                    target_language, META_PHRASES, 'unavailable',
                    _("Conceptual learning isn't available right now -- make sure "
                      "the local LLM (Ollama) is running and try again.")),
                activity_type=self.activity_type.value,
                expects_response=False,
            )

        # The LLM may substitute a concept that fits the language better.
        self._concept = lesson.concept or self._concept
        self._questions = lesson.questions[:QUESTIONS_PER_SESSION]
        self._tag_saved_phrases(lesson, saved_entries)
        intro = self._format_intro(lesson)

        if not self._questions:
            self._active = False
            return ActivityStartResult(
                text_response=f"{intro}\n\n{_('No practice questions could be prepared this time.')}",
                activity_type=self.activity_type.value,
                expects_response=False,
                voice_text=self._lesson_voice_text(lesson),
            )

        self._active = True
        return ActivityStartResult(
            text_response=f"{intro}\n\n{self._format_question(0)}",
            activity_type=self.activity_type.value,
            voice_text=self._lesson_voice_text(lesson),
        )

    def handle_response(self, user_text: str, services: ModuleServices) -> ActivityTurnResult:
        target_language = services.session_config.target_language
        if not self._active:
            return ActivityTurnResult(
                text_response=_("This activity has already finished."),
                activity_type=self.activity_type.value,
                is_complete=True,
            )

        question = self._questions[self._question_index]
        choice = question.match_answer(user_text)
        if choice is None:
            # Unrecognized reply: re-ask the same question without advancing.
            reprompt = _("Please answer with the number of one of the options (1-{0}).").format(
                len(question.options))
            return ActivityTurnResult(
                text_response=f"{reprompt}\n\n{self._format_question(self._question_index)}",
                activity_type=self.activity_type.value,
                voice_text="",
            )

        feedback = self._grade(question, choice, services)
        self._question_index += 1

        if self._question_index < len(self._questions):
            return ActivityTurnResult(
                text_response=f"{feedback}\n\n{self._format_question(self._question_index)}",
                activity_type=self.activity_type.value,
                feedback=feedback,
                voice_text=question.explanation,
            )

        self._active = False
        answered = self._question_index
        summary = bilingual_phrase(
            target_language, META_PHRASES, 'session_complete',
            _("Session complete: {0} of {1} correct.").format(self._correct_answers, answered),
            correct=self._correct_answers, answered=answered,
        )
        return ActivityTurnResult(
            text_response=f"{feedback}\n\n{summary}",
            activity_type=self.activity_type.value,
            is_complete=True,
            feedback=feedback,
            voice_text=question.explanation,
        )

    def complete(self, services: ModuleServices) -> Dict[str, Any]:
        target_language = services.session_config.target_language
        # The seed is the memory key when there was one: the LLM names the
        # concept in the target language, and recording that name would leave
        # the seed looking uncovered, so it would be picked again every session.
        covered_key = self._seed_concept or self._concept
        if covered_key:
            LearningMemory.update_grammar(target_language, covered_key)
        return {
            "grammar_points": [covered_key] if covered_key else [],
            "questions_answered": self._question_index,
            "correct_answers": self._correct_answers,
            "reviewed_words": list(self._reviewed_words),
            "errors": list(self._errors),
        }

    def _request_lesson(
        self,
        services: ModuleServices,
        saved_entries: List[Dict[str, Any]],
    ) -> Optional[ConceptLesson]:
        """Ask for a lesson, retrying while the reply has no usable questions.
        An explanation-only lesson is kept in case no attempt yields questions."""
        query = self._build_lesson_query(services, saved_entries)
        system_prompt = self._build_system_prompt(services)
        lesson = None
        for _attempt in range(LESSON_ATTEMPTS):
            turn = ask_llm(services.llm, query, system_prompt=system_prompt, timeout=LLM_TIMEOUT)
            if turn is None:
                break
            parsed = parse_concept_lesson(turn[0], rng=self._rng)
            if parsed is not None and (lesson is None or parsed.questions):
                lesson = parsed
            if lesson is not None and lesson.questions:
                break
        return lesson

    def _lesson_voice_text(self, lesson: ConceptLesson) -> str:
        """Only the target-language example sentences (or, with none, the
        explanation): labels and option lists aren't meant to be read aloud."""
        if lesson.examples:
            return "\n".join(example.text for example in lesson.examples)
        return lesson.explanation

    def _grade(self, question: ConceptQuestion, choice: int, services: ModuleServices) -> str:
        if choice == question.correct_index:
            self._correct_answers += 1
            self._record_reviewed(question, services)
            verdict = _("Correct!")
        else:
            self._errors.append(question.prompt)
            verdict = _("Not quite -- the answer was {0}) {1}").format(
                question.correct_index + 1, question.correct_option)
        return f"{verdict}\n{question.explanation}" if question.explanation else verdict

    def _record_reviewed(self, question: ConceptQuestion, services: ModuleServices) -> None:
        target_language = services.session_config.target_language
        pool = services.vocabulary_pool
        for phrase in question.saved_phrases:
            if phrase in self._reviewed_words:
                continue
            self._reviewed_words.append(phrase)
            if pool is not None:
                try:
                    pool.record_word_result(target_language, phrase, outcome="reviewed")
                except Exception as e:
                    logger.warning(f"Could not record reviewed word {phrase!r}: {e}")

    def _pick_seed_concept(self, services: ModuleServices) -> Optional[str]:
        """First seed for the level not yet covered, or None to let the LLM choose."""
        level = str(services.session_config.proficiency_level or _DEFAULT_LEVEL).lower()
        seeds = _CONCEPTS_BY_LEVEL.get(level, _CONCEPTS_BY_LEVEL[_DEFAULT_LEVEL])
        covered = self._covered_concepts(services)
        for seed in seeds:
            if seed not in covered:
                return seed
        return None

    def _covered_concepts(self, services: ModuleServices) -> List[str]:
        target_language = services.session_config.target_language
        return list(LearningMemory.grammar_points_covered.get(target_language, []))

    def _saved_entries(self, services: ModuleServices) -> List[Dict[str, Any]]:
        pool = services.vocabulary_pool
        if pool is None:
            return []
        source_language, target_language = services.language_pair()
        try:
            return pool.get_review_candidates(
                source_language, target_language, limit=SAVED_PHRASES_LIMIT)
        except Exception as e:
            logger.warning(f"Could not load saved translations: {e}")
            return []

    def _build_system_prompt(self, services: ModuleServices) -> str:
        target_language = services.session_config.target_language
        proficiency = services.session_config.proficiency_level or _DEFAULT_LEVEL
        base = self.load_activity_prompt(services)
        return (
            f"{base}\n\n"
            f"Write the explanation, notes, questions, and options in "
            f"{Language.get_language_name(target_language)}, at a {proficiency} "
            f"proficiency level."
        )

    def _build_lesson_query(self, services: ModuleServices, saved_entries: List[Dict[str, Any]]) -> str:
        source_language, target_language = services.language_pair()
        target_name = Language.get_language_name(target_language)
        if self._seed_concept:
            concept_line = (
                f"Teach this concept: '{self._seed_concept}'. If it doesn't apply to "
                f"{target_name}, choose a comparably broad concept that does."
            )
        else:
            recent = self._covered_concepts(services)[-RECENT_CONCEPTS_LIMIT:]
            concept_line = f"Choose one broad, widely applicable concept of {target_name} yourself."
            if recent:
                concept_line += " Avoid these, already covered: " + "; ".join(recent) + "."

        query = (
            f"{concept_line}\n\n"
            "Reply with only a JSON object with these keys:\n"
            '- "concept": short name of the concept taught\n'
            '- "explanation": a short explanation of the general rule\n'
            '- "examples": 2-4 objects {"text": example sentence, "note": one '
            "line naming the general pattern it shows}\n"
            f'- "questions": exactly {QUESTIONS_PER_SESSION} multiple-choice objects '
            '{"prompt", "options" (3-4 strings), "correct" (the exact text of the '
            'one correct option), "explanation" (why)}. Write the questions '
            "yourself and vary them -- e.g. which option follows the rule, which "
            "one breaks it, or which completes a sentence correctly. Exactly one "
            "option must be correct."
        )
        saved_lines = self._format_saved_entries(saved_entries)
        if saved_lines:
            query += (
                f"\n\nThe learner has saved these {Language.get_language_name(source_language)}"
                f"-{target_name} translations. Where one fits the concept "
                "naturally, use it word-for-word in an example or an option so "
                "the learner revisits it; don't force ones that don't fit:\n"
                + "\n".join(saved_lines)
            )
        return query

    def _format_saved_entries(self, saved_entries: List[Dict[str, Any]]) -> List[str]:
        lines = []
        for entry in saved_entries:
            target_text = translation_import.coerce_str(entry.get('translated_text', ''))
            source_text = translation_import.format_source_for_display(entry.get('source_text', ''))
            if target_text:
                lines.append(f"- {target_text} = {source_text}")
        return lines

    def _tag_saved_phrases(self, lesson: ConceptLesson, saved_entries: List[Dict[str, Any]]) -> None:
        phrases = [
            translation_import.coerce_str(entry.get('translated_text', ''))
            for entry in saved_entries
        ]
        phrases = [phrase for phrase in phrases if phrase]
        for example in lesson.examples:
            example.saved_phrases = _phrases_in(example.text, phrases)
        for question in self._questions:
            blob = "\n".join([question.prompt, *question.options])
            question.saved_phrases = _phrases_in(blob, phrases)

    def _format_intro(self, lesson: ConceptLesson) -> str:
        parts = []
        if self._concept:
            parts.append(_("Concept: {0}").format(self._concept))
        if lesson.explanation:
            parts.append(lesson.explanation)
        if lesson.examples:
            lines = [_("Examples:")]
            for example in lesson.examples:
                line = f"- {example.text}"
                if example.note:
                    line += f" -- {example.note}"
                if example.saved_phrases:
                    line += " " + _("(uses your saved words: {0})").format(", ".join(example.saved_phrases))
                lines.append(line)
            parts.append("\n".join(lines))
        return "\n\n".join(parts)

    def _format_question(self, index: int) -> str:
        question = self._questions[index]
        header = _("Question {0} of {1}: {2}").format(index + 1, len(self._questions), question.prompt)
        options = [f"{number}) {option}" for number, option in enumerate(question.options, start=1)]
        return "\n".join([header, *options])


def _phrases_in(text: str, phrases: List[str]) -> List[str]:
    """Saved phrases occurring in `text` as whole words, case-insensitively."""
    found = []
    for phrase in phrases:
        pattern = r'(?<!\w)' + re.escape(phrase) + r'(?!\w)'
        if phrase not in found and re.search(pattern, text, re.IGNORECASE):
            found.append(phrase)
    return found


ActivityRegistry.register(ConceptualLearning)
