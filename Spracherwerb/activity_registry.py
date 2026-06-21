"""Registry mapping activity types to learning module implementations."""

from __future__ import annotations

from typing import Callable, Dict, Type

from .activity_types import ActivityType
from .base_learning_module import ActivityNotRegisteredError, BaseLearningModule
from .unimplemented_learning_module import UnimplementedLearningModule


def _build_placeholder_class(activity_type: ActivityType) -> Type[BaseLearningModule]:
    class PlaceholderModule(BaseLearningModule):
        def start(self, services):
            return UnimplementedLearningModule(activity_type).start(services)

        def handle_response(self, user_text, services):
            return UnimplementedLearningModule(activity_type).handle_response(
                user_text,
                services,
            )

        def complete(self, services):
            return UnimplementedLearningModule(activity_type).complete(services)

    PlaceholderModule.activity_type = activity_type
    PlaceholderModule.__name__ = f"Placeholder_{activity_type.name}"
    return PlaceholderModule


class ActivityRegistry:
    """Factory registry for ``BaseLearningModule`` implementations."""

    _module_classes: Dict[ActivityType, Type[BaseLearningModule]] = {}
    _defaults_registered = False

    @classmethod
    def register(cls, module_class: Type[BaseLearningModule]) -> Type[BaseLearningModule]:
        """Register a module class. Later registrations replace earlier ones."""
        activity_type = getattr(module_class, "activity_type", None)
        if activity_type is None:
            raise TypeError(
                f"{module_class.__name__} must define activity_type class attribute"
            )
        if not isinstance(activity_type, ActivityType):
            raise TypeError(
                f"{module_class.__name__}.activity_type must be an ActivityType member"
            )
        cls._module_classes[activity_type] = module_class
        return module_class

    @classmethod
    def register_defaults(cls) -> None:
        """Register placeholder modules for every activity without an implementation."""
        if cls._defaults_registered:
            return
        for activity_type in ActivityType:
            if activity_type not in cls._module_classes:
                cls._module_classes[activity_type] = _build_placeholder_class(activity_type)
        cls._defaults_registered = True

    @classmethod
    def create(cls, activity_type: ActivityType) -> BaseLearningModule:
        cls.register_defaults()
        module_class = cls._module_classes.get(activity_type)
        if module_class is None:
            raise ActivityNotRegisteredError(
                f"No module registered for activity type {activity_type.value!r}"
            )
        return module_class()

    @classmethod
    def is_implemented(cls, activity_type: ActivityType) -> bool:
        """Return True when a non-placeholder module is registered."""
        cls.register_defaults()
        module_class = cls._module_classes.get(activity_type)
        if module_class is None:
            return False
        return not module_class.__name__.startswith("Placeholder_")

    @classmethod
    def registered_types(cls) -> list[ActivityType]:
        cls.register_defaults()
        return list(cls._module_classes.keys())

    @classmethod
    def clear(cls) -> None:
        """Reset registry state (intended for tests)."""
        cls._module_classes.clear()
        cls._defaults_registered = False

    @classmethod
    def reset_to_defaults(cls) -> None:
        """Clear and re-register placeholder modules."""
        cls.clear()
        cls.register_defaults()
