"""Canonical activity type identifiers for learning modules."""

from enum import Enum


class ActivityType(str, Enum):
    """Types of learning activities. Values match config JSON and module filenames."""

    VOCABULARY_BUILDER = "vocabulary_builder"
    GRAMMAR_PRACTICE = "grammar_practice"
    CONVERSATION_PRACTICE = "conversation_practice"
    LISTENING_COMPREHENSION = "listening_comprehension"
    WRITING_PRACTICE = "writing_practice"
    CULTURAL_CONTEXT = "cultural_context"
    PRONUNCIATION_GUIDE = "pronunciation_guide"
    IDIOMS_AND_EXPRESSIONS = "idioms_and_expressions"
    READING_COMPREHENSION = "reading_comprehension"
    SITUATIONAL_DIALOGUES = "situational_dialogues"
    VISUAL_VOCABULARY = "visual_vocabulary"

    @classmethod
    def from_value(cls, value: str) -> "ActivityType":
        """Resolve a string activity id to an enum member."""
        try:
            return cls(value)
        except ValueError as exc:
            valid = ", ".join(member.value for member in cls)
            raise ValueError(f"Unknown activity type {value!r}. Expected one of: {valid}") from exc

    @classmethod
    def all_values(cls) -> list[str]:
        return [member.value for member in cls]


# Backward-compatible alias used in session_manager and older code.
LearningActivity = ActivityType
