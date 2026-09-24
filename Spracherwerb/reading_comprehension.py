"""Reading comprehension: a passage (Gutenberg excerpt or LLM-generated),
a few comprehension questions, and an offer to save an unknown word.

Tries a popular Gutenberg book in the target language first (a short excerpt
after stripping its standard boilerplate markers); falls back to an
LLM-generated passage on any issue -- no book found, network failure, text
too short to excerpt cleanly. Either way, a second LLM call writes the
comprehension questions, so the same grading/parsing path works regardless
of which source produced the passage. Does not target a specific
known-vocabulary ratio for the passage -- that needs vocabulary-difficulty
scoring this project doesn't have yet, so passage difficulty isn't tuned to
the learner's level beyond the proficiency instruction given to the LLM.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

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
GRADE_TIMEOUT = 45.0
QUESTIONS_PER_SESSION = 3
GUTENBERG_CANDIDATE_BOOKS = 5
EXCERPT_TARGET_WORDS = 130
_NEGATIVE_RESPONSES = {
    "no", "none", "nothing", "n/a", "nope", "",
    "nein", "keine", "nichts",
    "no sé", "nada", "ninguna",
    "non", "rien", "aucune",
    "niente", "nessuna",
}

META_PHRASES = {
    'de': {
        'unavailable': 'Der Lesetext ist gerade nicht verfügbar.',
        'instruction': 'Lies den Text und beantworte dann die Fragen.',
        'ask_unknown_word': 'Gab es ein Wort im Text, das du nicht verstanden hast? '
                             'Tippe es ein, oder sag "nein", um abzuschließen.',
    },
    'es': {
        'unavailable': 'El texto de lectura no está disponible en este momento.',
        'instruction': 'Lee el texto y luego responde las preguntas.',
        'ask_unknown_word': '¿Había alguna palabra en el texto que no entendiste? '
                             'Escríbela, o di "no" para terminar.',
    },
    'fr': {
        'unavailable': "Le texte de lecture n'est pas disponible pour le moment.",
        'instruction': 'Lisez le texte, puis répondez aux questions.',
        'ask_unknown_word': "Y avait-il un mot dans le texte que vous n'avez pas compris ? "
                             'Tapez-le, ou dites « non » pour terminer.',
    },
    'it': {
        'unavailable': 'Il testo di lettura non è disponibile al momento.',
        'instruction': 'Leggi il testo, poi rispondi alle domande.',
        'ask_unknown_word': "C'era una parola nel testo che non hai capito? "
                             'Scrivila, oppure di\' "no" per terminare.',
    },
}


class ReadingComprehension(BaseLearningModule):
    """One passage + a few graded questions, then an offer to save an unknown word."""

    activity_type = ActivityType.READING_COMPREHENSION

    def __init__(self):
        self._passage: str = ""
        self._passage_id: str = ""
        self._questions: List[str] = []
        self._question_index: int = 0
        self._questions_answered: int = 0
        self._new_words: List[str] = []
        self._phase: str = "questions"
        self._active: bool = False

    def start(self, services: ModuleServices) -> ActivityStartResult:
        target_language = services.session_config.target_language
        self._question_index = 0
        self._questions_answered = 0
        self._new_words = []
        self._phase = "questions"

        passage = self._get_passage(services)
        if passage is None:
            self._active = False
            return ActivityStartResult(
                text_response=bilingual_phrase(
                    target_language, META_PHRASES, 'unavailable',
                    _("No reading passage is available right now -- make sure "
                      "the local LLM (Ollama) is running and try again.")),
                activity_type=self.activity_type.value,
                expects_response=False,
            )
        self._passage, self._passage_id = passage

        questions = self._generate_questions(services)
        if not questions:
            self._active = False
            return ActivityStartResult(
                text_response=bilingual_phrase(
                    target_language, META_PHRASES, 'unavailable',
                    _("No reading passage is available right now -- make sure "
                      "the local LLM (Ollama) is running and try again.")),
                activity_type=self.activity_type.value,
                expects_response=False,
            )
        self._questions = questions
        self._active = True

        instruction = bilingual_phrase(
            target_language, META_PHRASES, 'instruction',
            _("Read the passage, then answer the questions below."))
        return ActivityStartResult(
            text_response=f"{instruction}\n\n{self._passage}\n\n{self._questions[0]}",
            activity_type=self.activity_type.value,
        )

    def handle_response(self, user_text: str, services: ModuleServices) -> ActivityTurnResult:
        if not self._active:
            return ActivityTurnResult(
                text_response=_("This activity has already finished."),
                activity_type=self.activity_type.value,
                is_complete=True,
            )
        if self._phase == "questions":
            return self._handle_question_response(user_text, services)
        return self._handle_unknown_word_response(user_text, services)

    def complete(self, services: ModuleServices) -> Dict[str, Any]:
        return {
            "passage_id": self._passage_id,
            "questions_answered": self._questions_answered,
            "new_words": list(self._new_words),
        }

    # -- question turns -----------------------------------------------

    def _handle_question_response(self, user_text: str, services: ModuleServices) -> ActivityTurnResult:
        target_language = services.session_config.target_language
        feedback = self._grade_question(user_text, services)
        if feedback is None:
            feedback = _("Could not check that answer right now, but let's continue.")
        self._questions_answered += 1
        self._question_index += 1

        if self._question_index < len(self._questions):
            next_question = self._questions[self._question_index]
            return ActivityTurnResult(
                text_response=f"{feedback}\n\n{next_question}",
                activity_type=self.activity_type.value,
                is_complete=False,
                feedback=feedback,
            )

        self._phase = "unknown_word"
        prompt = bilingual_phrase(
            target_language, META_PHRASES, 'ask_unknown_word',
            _("Was there a word in the passage you didn't understand? Type it, "
              "or say \"no\" to finish."))
        return ActivityTurnResult(
            text_response=f"{feedback}\n\n{prompt}",
            activity_type=self.activity_type.value,
            is_complete=False,
            feedback=feedback,
        )

    def _grade_question(self, user_text: str, services: ModuleServices) -> Optional[str]:
        target_language = services.session_config.target_language
        question = self._questions[self._question_index]
        grading_query = (
            f"Passage: {self._passage}\n"
            f"Question: {question}\n"
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

    # -- unknown-word turn ----------------------------------------------

    def _handle_unknown_word_response(self, user_text: str, services: ModuleServices) -> ActivityTurnResult:
        self._active = False
        word = translation_import.coerce_str(user_text)
        parts = []

        if word.casefold() not in _NEGATIVE_RESPONSES:
            translated = self._translate_word(word, services)
            self._new_words.append(word)
            if translated:
                self._save_new_word(word, translated, services)
                parts.append(_("Added \"{0}\" ({1}) to your translations.").format(word, translated))
            else:
                parts.append(_("Could not translate that right now, but noted \"{0}\".").format(word))

        parts.append(
            _("Session complete: {0} question(s) answered.").format(self._questions_answered))
        return ActivityTurnResult(
            text_response="\n\n".join(parts),
            activity_type=self.activity_type.value,
            is_complete=True,
        )

    def _translate_word(self, word: str, services: ModuleServices) -> Optional[str]:
        source_language, target_language = services.language_pair()
        query = (
            f"Translate the {Language.get_language_name(target_language)} word or "
            f"phrase \"{word}\" into {Language.get_language_name(source_language)}. "
            "Reply with only the translation, nothing else."
        )
        turn = ask_llm(services.llm, query, timeout=GRADE_TIMEOUT)
        if turn is None:
            return None
        text, _context = turn
        return text.strip() or None

    def _save_new_word(self, word: str, translation: str, services: ModuleServices) -> None:
        source_language, target_language = services.language_pair()
        pool = getattr(services, 'vocabulary_pool', None)
        data_manager = getattr(pool, 'data_manager', None) if pool is not None else None
        if data_manager is None:
            return
        try:
            data_manager.add_translation({
                'source_text': translation,
                'translated_text': word,
                'source_language': source_language,
                'target_language': target_language,
                'notes': 'Added from reading comprehension',
            })
        except Exception as e:
            logger.warning(f"Failed to save new word {word!r}: {e}")

    # -- passage sourcing -------------------------------------------------

    def _get_passage(self, services: ModuleServices) -> Optional[Tuple[str, str]]:
        gutenberg_result = self._get_gutenberg_excerpt(services)
        if gutenberg_result:
            return gutenberg_result
        return self._generate_passage_with_llm(services)

    def _get_gutenberg_excerpt(self, services: ModuleServices) -> Optional[Tuple[str, str]]:
        gutenberg = getattr(services, 'gutenberg', None)
        if gutenberg is None:
            return None
        target_language = services.session_config.target_language
        try:
            books = gutenberg.get_popular_books(target_language, limit=GUTENBERG_CANDIDATE_BOOKS)
        except Exception as e:
            logger.warning(f"Gutenberg lookup failed: {e}")
            return None
        for book in books:
            try:
                text = gutenberg.get_book_text(book.id)
            except Exception as e:
                logger.warning(f"Gutenberg text fetch failed for book {book.id}: {e}")
                continue
            excerpt = self._extract_excerpt(text)
            if excerpt:
                return excerpt, f"gutenberg:{book.id}"
        return None

    def _extract_excerpt(self, text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        start_idx = text.find("*** START OF")
        if start_idx != -1:
            newline_idx = text.find("\n", start_idx)
            text = text[newline_idx + 1:] if newline_idx != -1 else text[start_idx:]
        end_idx = text.find("*** END OF")
        if end_idx != -1:
            text = text[:end_idx]
        words = text.split()
        if len(words) < EXCERPT_TARGET_WORDS:
            return None
        excerpt = " ".join(words[:EXCERPT_TARGET_WORDS]).strip()
        return excerpt or None

    def _generate_passage_with_llm(self, services: ModuleServices) -> Optional[Tuple[str, str]]:
        target_language = services.session_config.target_language
        proficiency = services.session_config.proficiency_level or "intermediate"
        try:
            system_prompt = (
                f"{self.load_activity_prompt(services)}\n\n"
                f"Write entirely in {Language.get_language_name(target_language)}, "
                f"at a {proficiency} proficiency level."
            )
        except Exception as e:
            logger.warning(f"ReadingComprehension failed to load its activity prompt: {e}")
            return None
        query = (
            "Write a short reading passage (5-8 sentences) about an everyday or "
            "informational topic, suitable for the learner's level."
        )
        turn = ask_llm(services.llm, query, system_prompt=system_prompt, timeout=LLM_TIMEOUT)
        if turn is None:
            return None
        text, _context = turn
        return text.strip(), "llm-generated"

    # -- question generation ----------------------------------------------

    def _generate_questions(self, services: ModuleServices) -> List[str]:
        query = (
            f"Passage: {self._passage}\n\n"
            f"Write exactly {QUESTIONS_PER_SESSION} short comprehension questions "
            "about this passage, testing understanding of the main ideas and "
            "details, each on its own line starting with 'QUESTION 1:', "
            "'QUESTION 2:', etc. Do not include the answers."
        )
        turn = ask_llm(services.llm, query, timeout=LLM_TIMEOUT)
        if turn is None:
            return []
        text, _context = turn
        return self._parse_questions(text)

    def _parse_questions(self, text: str) -> List[str]:
        parts = re.split(r'QUESTION\s*\d+:', text, flags=re.IGNORECASE)
        questions = [p.strip() for p in parts[1:] if p.strip()]
        if not questions and text.strip():
            questions = [text.strip()]
        return questions[:QUESTIONS_PER_SESSION]


ActivityRegistry.register(ReadingComprehension)
