"""Abstract base class for skill-specific learning modules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Dict, Optional

from .activity_results import ActivityStartResult, ActivityTurnResult, ModuleServices
from .activity_types import ActivityType


class BaseLearningModule(ABC):
    """Contract implemented by each activity module under ``Spracherwerb/``."""

    activity_type: ClassVar[ActivityType]

    @abstractmethod
    def start(self, services: ModuleServices) -> ActivityStartResult:
        """Prepare the first interaction for this activity."""

    @abstractmethod
    def handle_response(
        self,
        user_text: str,
        services: ModuleServices,
    ) -> ActivityTurnResult:
        """Handle one user turn and produce the next system message."""

    def complete(self, services: ModuleServices) -> Dict[str, Any]:
        """Return normalized results merged into session activity metrics."""
        return {}

    def suggest_next_difficulty(self, services: ModuleServices) -> Optional[int]:
        """Optional hook for ``LearningProgression`` difficulty adjustment."""
        return None

    def activity_prompt_name(self) -> str:
        """Default prompt file stem under ``prompts/activities/``."""
        return self.activity_type.value

    def load_activity_prompt(self, services: ModuleServices) -> str:
        """Load the module prompt template for the session target language."""
        prompt_name = self.activity_prompt_name()
        language_code = services.session_config.target_language
        return services.prompter.get_prompt(prompt_name, language_code)


class ActivityNotRegisteredError(LookupError):
    """Raised when no module is registered for an activity type."""
