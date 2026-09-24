"""Listening comprehension: hear a target-language passage, answer a question about it.

Single passage/question per session, a deliberate MVP simplification rather
than the open-ended multi-question version a full reading/listening pipeline
would eventually support. "Replay" is a typed command rather than a
dedicated UI control, since the chat-style interaction model has no button
for it yet.
"""

from __future__ import annotations

import logging
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
QUESTION_MARKER = "QUESTION:"

_REPLAY_WORDS = ("replay", "again", "repeat", "wiederholen", "encore", "otra vez", "ripeti")

_SPEED_BY_PROFICIENCY = {
    "beginner": 0.85,
    "intermediate": 1.0,
    "advanced": 1.15,
}

META_PHRASES = {
    'de': {
        'unavailable': 'Der Hörverständnistext ist gerade nicht verfügbar.',
        'instruction': 'Hör dir die Passage an und beantworte dann die Frage.',
    },
    'es': {
        'unavailable': 'El texto de comprensión auditiva no está disponible en este momento.',
        'instruction': 'Escucha el pasaje y luego responde la pregunta.',
    },
    'fr': {
        'unavailable': "Le passage d'écoute n'est pas disponible pour le moment.",
        'instruction': "Écoutez le passage, puis répondez à la question.",
    },
    'it': {
        'unavailable': "Il brano di ascolto non è disponibile al momento.",
        'instruction': "Ascolta il brano, poi rispondi alla domanda.",
    },
}


class ListeningComprehension(BaseLearningModule):
    """One LLM-generated passage + comprehension question, presented audio-first."""

    activity_type = ActivityType.LISTENING_COMPREHENSION

    def __init__(self):
        self._passage: str = ""
        self._question: str = ""
        self._audio_paths: List[str] = []
        self._replay_count: int = 0
        self._questions_answered: int = 0
        self._active: bool = False

    def start(self, services: ModuleServices) -> ActivityStartResult:
        target_language = services.session_config.target_language
        proficiency = services.session_config.proficiency_level or "intermediate"
        self._audio_paths = []
        self._replay_count = 0
        self._questions_answered = 0

        generated = self._generate_passage_and_question(services)
        if generated is None:
            self._active = False
            return ActivityStartResult(
                text_response=bilingual_phrase(
                    target_language, META_PHRASES, 'unavailable',
                    _("No listening passage is available right now -- make sure "
                      "the local LLM (Ollama) is running and try again.")),
                activity_type=self.activity_type.value,
                expects_response=False,
            )
        self._passage, self._question = generated
        self._active = True

        services.voice.set_speed(_SPEED_BY_PROFICIENCY.get(proficiency, 1.0))
        voice_path = self._speak_passage(services)

        instruction = bilingual_phrase(
            target_language, META_PHRASES, 'instruction',
            _("Listen to the passage, then answer the question below."))
        if voice_path:
            text_response = f"{instruction}\n\n{self._question}"
        else:
            # No TTS available -- this activity's content IS the audio, so
            # show the passage as text rather than leaving no way to access it.
            text_response = f"{instruction}\n\n{self._passage}\n\n{self._question}"

        return ActivityStartResult(
            text_response=text_response,
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
            voice_path = self._speak_passage(services)
            return ActivityTurnResult(
                text_response=self._question,
                activity_type=self.activity_type.value,
                is_complete=False,
                voice_response=voice_path,
            )

        self._questions_answered += 1
        self._active = False
        feedback = self._grade_answer(user_text, services)
        reveal = _("Passage: {0}").format(self._passage)
        return ActivityTurnResult(
            text_response=f"{feedback}\n\n{reveal}",
            activity_type=self.activity_type.value,
            is_complete=True,
        )

    def complete(self, services: ModuleServices) -> Dict[str, Any]:
        return {
            "audio_paths": list(self._audio_paths),
            "questions_answered": self._questions_answered,
            "replay_count": self._replay_count,
        }

    def _is_replay_request(self, user_text: str) -> bool:
        normalized = translation_import.coerce_str(user_text).casefold()
        return any(word in normalized for word in _REPLAY_WORDS)

    def _generate_passage_and_question(
        self, services: ModuleServices,
    ) -> Optional[Tuple[str, str]]:
        target_language = services.session_config.target_language
        proficiency = services.session_config.proficiency_level or "intermediate"
        try:
            system_prompt = (
                f"{self.load_activity_prompt(services)}\n\n"
                f"Write entirely in {Language.get_language_name(target_language)}, "
                f"at a {proficiency} proficiency level."
            )
        except Exception as e:
            logger.warning(f"ListeningComprehension failed to load its activity prompt: {e}")
            return None
        query = (
            "Write a short passage (3-5 sentences) about an everyday topic, then "
            f"on a new line write exactly '{QUESTION_MARKER}' followed by one "
            "comprehension question about the passage. Do not include the answer."
        )
        turn = ask_llm(services.llm, query, system_prompt=system_prompt, timeout=LLM_TIMEOUT)
        if turn is None:
            return None
        text, _context = turn
        return self._split_passage_and_question(text)

    def _split_passage_and_question(self, text: str) -> Tuple[str, str]:
        if QUESTION_MARKER in text:
            passage, _marker, question = text.partition(QUESTION_MARKER)
            passage = passage.strip()
            question = question.strip()
            if passage and question:
                return passage, question
        # Model didn't follow the format -- treat the whole thing as the
        # passage and fall back to a generic question rather than failing.
        return text.strip(), _("What was the passage about?")

    def _speak_passage(self, services: ModuleServices) -> Optional[str]:
        try:
            path = services.voice.generate_speech(self._passage, topic="listening_comprehension")
        except Exception as e:
            logger.warning(f"ListeningComprehension TTS failed: {e}")
            return None
        if path:
            self._audio_paths.append(path)
        return path

    def _grade_answer(self, user_text: str, services: ModuleServices) -> str:
        target_language = services.session_config.target_language
        grading_query = (
            f"Passage: {self._passage}\n"
            f"Question: {self._question}\n"
            f"Student's answer: {user_text}\n\n"
            "Was the student's answer correct? Reply with 'CORRECT' or "
            "'INCORRECT' on the first line, then one short sentence of "
            f"feedback in {Language.get_language_name(target_language)}."
        )
        turn = ask_llm(services.llm, grading_query, timeout=GRADE_TIMEOUT)
        if turn is None:
            return _("Could not grade your answer right now, but thanks for listening!")
        text, _context = turn
        return text


ActivityRegistry.register(ListeningComprehension)
