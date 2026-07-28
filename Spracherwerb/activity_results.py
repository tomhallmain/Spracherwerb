"""Structured return values for learning module turn handling."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ActivityStartResult:
    """Payload returned when an activity begins."""

    text_response: str
    activity_type: str
    prompt: Optional[str] = None
    voice_response: Optional[str] = None
    media_path: Optional[str] = None
    ui_event: Optional[str] = None
    ui_payload: Optional[Dict[str, Any]] = None
    expects_response: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text_response": self.text_response,
            "prompt": self.prompt or self.text_response,
            "activity_type": self.activity_type,
            "voice_response": self.voice_response,
            "media_path": self.media_path,
            "ui_event": self.ui_event,
            "ui_payload": self.ui_payload,
            "expects_response": self.expects_response,
        }


@dataclass
class ActivityTurnResult:
    """Payload returned after each user response within an activity."""

    text_response: str
    activity_type: str
    voice_response: Optional[str] = None
    media_path: Optional[str] = None
    is_complete: bool = False
    feedback: Optional[str] = None
    ui_event: Optional[str] = None
    ui_payload: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text_response": self.text_response,
            "voice_response": self.voice_response,
            "media_path": self.media_path,
            "activity_type": self.activity_type,
            "is_complete": self.is_complete,
            "feedback": self.feedback,
            "ui_event": self.ui_event,
            "ui_payload": self.ui_payload,
        }


@dataclass
class ModuleServices:
    """Shared services passed into each learning module per turn."""

    prompter: Any
    voice: Any
    session_config: Any
    session_context: Any
    vocabulary_pool: Any = None
    sd_client: Any = None
    llm: Any = None

    def language_pair(self) -> tuple[str, str]:
        return self.session_config.source_language, self.session_config.target_language
