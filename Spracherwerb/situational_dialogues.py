"""Situational dialogues: goal-oriented role-play in a fixed scenario.

Structurally close to ConversationPractice (LLM dialogue, farewell/turn-limit
ending), plus: a scenario picked from a small hardcoded catalog in this file
(not an external scenario data file), the goal stated up front, completion
tied to the LLM signalling the goal was met (a marker in its own reply,
stripped before display -- the same technique GrammarPractice/
ListeningComprehension use for CORRECT/INCORRECT), and an optional scene
image via SD Runner (see image_hint.py, shared with VisualVocabulary).
"""

from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import Any, Dict, Optional

from utils import translation_import
from utils.globals import Language
from utils.translations import I18N

from . import image_hint
from .activity_registry import ActivityRegistry
from .activity_results import ActivityStartResult, ActivityTurnResult, ModuleServices
from .activity_types import ActivityType
from .base_learning_module import BaseLearningModule
from .llm_turn import ask_llm

_ = I18N._
logger = logging.getLogger(__name__)

MAX_TURNS = 8
LLM_TIMEOUT = 60.0
GOAL_MARKER = "[GOAL MET]"
IMAGE_CACHE_DIR = Path("cache/situational_dialogues")

_FAREWELL_WORDS = (
    "bye", "goodbye", "quit", "stop", "end conversation",
    "tschüss", "auf wiedersehen", "adios", "adiós", "au revoir", "arrivederci",
)

_SCENARIOS = [
    {
        "id": "buy_train_ticket",
        "title": "Buying a train ticket",
        "setup": "You are a ticket agent at a train station. The learner wants "
                 "to buy a ticket to another city.",
        "goal": "Successfully request and receive a ticket, including a "
                "destination and a time.",
    },
    {
        "id": "ask_directions",
        "title": "Asking for directions",
        "setup": "You are a friendly local the learner has stopped on the "
                 "street. The learner is lost and needs directions to a "
                 "nearby landmark such as a train station, museum, or pharmacy.",
        "goal": "Successfully ask for and understand directions to a specific place.",
    },
    {
        "id": "order_at_restaurant",
        "title": "Ordering at a restaurant",
        "setup": "You are a waiter at a restaurant. The learner wants to order "
                 "food and a drink.",
        "goal": "Successfully order a meal and a drink.",
    },
]


class SituationalDialogues(BaseLearningModule):
    """One fixed-goal role-play scenario per session, played out via the LLM."""

    activity_type = ActivityType.SITUATIONAL_DIALOGUES

    def __init__(self):
        self._scenario: Optional[Dict[str, str]] = None
        self._context = None
        self._turn_count = 0
        self._goal_met = False
        self._active = False
        self._system_prompt = ""

    def start(self, services: ModuleServices) -> ActivityStartResult:
        target_language = services.session_config.target_language
        self._scenario = self._pick_scenario(services)
        self._turn_count = 0
        self._context = None
        self._goal_met = False

        try:
            self._system_prompt = self._build_system_prompt(services)
            turn = ask_llm(
                services.llm,
                "Start the role-play now: briefly set the scene in character "
                "and speak your first line.",
                system_prompt=self._system_prompt,
                timeout=LLM_TIMEOUT,
            )
        except Exception as e:
            logger.warning(f"SituationalDialogues failed to start: {e}")
            turn = None

        if turn is None:
            self._active = False
            return ActivityStartResult(
                text_response=_(
                    "This role-play isn't available right now -- make sure the "
                    "local LLM (Ollama) is running and try again."),
                activity_type=self.activity_type.value,
                expects_response=False,
            )

        self._active = True
        response_text, self._context = turn
        response_text = self._strip_goal_marker(response_text)

        intro = _("Scenario: {0}\nYour goal: {1}").format(
            self._scenario["title"], self._scenario["goal"])
        media_path = self._maybe_generate_scene_image(services)

        return ActivityStartResult(
            text_response=f"{intro}\n\n{response_text}",
            activity_type=self.activity_type.value,
            media_path=media_path,
        )

    def handle_response(self, user_text: str, services: ModuleServices) -> ActivityTurnResult:
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
                text_response=_("Lost the connection to the role-play partner."),
                activity_type=self.activity_type.value,
                is_complete=True,
            )

        response_text, self._context = turn
        goal_met = GOAL_MARKER in response_text
        response_text = self._strip_goal_marker(response_text)

        should_end = goal_met or self._turn_count >= MAX_TURNS or self._user_said_farewell(user_text)
        if should_end:
            self._active = False
            self._goal_met = goal_met
            summary = (
                _("Goal achieved!") if goal_met
                else _("Session complete after {0} turn(s).").format(self._turn_count)
            )
            response_text = f"{response_text}\n\n{summary}"
        return ActivityTurnResult(
            text_response=response_text,
            activity_type=self.activity_type.value,
            is_complete=should_end,
        )

    def complete(self, services: ModuleServices) -> Dict[str, Any]:
        scenario_id = self._scenario["id"] if self._scenario else None
        return {
            "scenario_id": scenario_id,
            "goals_met": [scenario_id] if self._goal_met and scenario_id else [],
            "turns": self._turn_count,
        }

    def _pick_scenario(self, services: ModuleServices) -> Dict[str, str]:
        return random.choice(_SCENARIOS)

    def _build_system_prompt(self, services: ModuleServices) -> str:
        target_language = services.session_config.target_language
        proficiency = services.session_config.proficiency_level or "intermediate"
        base = self.load_activity_prompt(services)
        return (
            f"{base}\n\n"
            f"Scenario: {self._scenario['setup']}\n"
            f"The learner's goal: {self._scenario['goal']}\n\n"
            f"Speak only in {Language.get_language_name(target_language)}, at a "
            f"{proficiency} proficiency level, staying in character for the "
            f"scenario. If the learner makes a significant error, gently "
            f"correct it as part of your natural in-character reply. As soon "
            f"as the learner has clearly achieved their goal, end your reply "
            f"with the exact text '{GOAL_MARKER}' on its own line."
        )

    def _strip_goal_marker(self, text: str) -> str:
        return text.replace(GOAL_MARKER, "").strip()

    def _user_said_farewell(self, user_text: str) -> bool:
        normalized = translation_import.coerce_str(user_text).casefold()
        return any(word in normalized for word in _FAREWELL_WORDS)

    def _maybe_generate_scene_image(self, services: ModuleServices) -> Optional[str]:
        if not image_hint.is_sd_available(services):
            return None
        slug = self._scenario["id"]
        cached = image_hint.find_cached_image(IMAGE_CACHE_DIR, slug)
        if cached:
            return cached
        prompt = f"{self._scenario['setup']}, simple clear illustration, plain background"
        return image_hint.request_generation(services, IMAGE_CACHE_DIR, slug, prompt)


ActivityRegistry.register(SituationalDialogues)
