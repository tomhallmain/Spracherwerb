"""Placeholder module for activities that are not implemented yet."""

from .activity_results import ActivityStartResult, ActivityTurnResult, ModuleServices
from .activity_types import ActivityType
from .base_learning_module import BaseLearningModule


class UnimplementedLearningModule(BaseLearningModule):
    """Returns a clear message until a real module replaces this registration."""

    def __init__(self, activity_type: ActivityType):
        self._activity_type = activity_type

    @property
    def activity_type(self) -> ActivityType:
        return self._activity_type

    def start(self, services: ModuleServices) -> ActivityStartResult:
        message = (
            f"The {self._activity_type.value.replace('_', ' ')} module is not "
            f"implemented yet. It is registered as a placeholder in the activity "
            f"framework."
        )
        return ActivityStartResult(
            text_response=message,
            prompt=message,
            activity_type=self._activity_type.value,
            expects_response=False,
        )

    def handle_response(
        self,
        user_text: str,
        services: ModuleServices,
    ) -> ActivityTurnResult:
        return ActivityTurnResult(
            text_response="This activity has no interactive flow yet.",
            activity_type=self._activity_type.value,
            is_complete=True,
        )
