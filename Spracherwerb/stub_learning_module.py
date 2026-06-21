"""Minimal echo module for exercising the learning framework in tests."""

from .activity_results import ActivityStartResult, ActivityTurnResult, ModuleServices
from .activity_types import ActivityType
from .base_learning_module import BaseLearningModule


class StubLearningModule(BaseLearningModule):
    """Echoes user input and completes after a configurable number of turns."""

    activity_type = ActivityType.VOCABULARY_BUILDER
    max_turns: int = 2

    def __init__(self, max_turns: int | None = None):
        self._turn_count = 0
        if max_turns is not None:
            self.max_turns = max_turns

    def start(self, services: ModuleServices) -> ActivityStartResult:
        return ActivityStartResult(
            text_response="Stub activity started. Send a message to continue.",
            prompt="Stub activity started. Send a message to continue.",
            activity_type=self.activity_type.value,
        )

    def handle_response(
        self,
        user_text: str,
        services: ModuleServices,
    ) -> ActivityTurnResult:
        self._turn_count += 1
        is_complete = self._turn_count >= self.max_turns
        text = f"Echo: {user_text}"
        if is_complete:
            text += " (activity complete)"
        return ActivityTurnResult(
            text_response=text,
            activity_type=self.activity_type.value,
            is_complete=is_complete,
        )

    def complete(self, services: ModuleServices) -> dict:
        return {
            "new_words": [],
            "reviewed_words": [],
            "turns": self._turn_count,
            "stub": True,
        }
