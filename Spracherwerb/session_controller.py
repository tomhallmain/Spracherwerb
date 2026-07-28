"""Thin orchestration layer between the UI and the session/engine stack.

Owns the single active session for the running app and re-derives its
``SessionConfig`` from ``utils.config.config`` each time a session is
(re)created, so callers only need "start this activity" / "send this
message" -- not ``SessionManager``'s session-id bookkeeping.
"""

from typing import Any, Callable, Dict, Optional

from utils.config import config as app_config

from .session_config import SessionConfig
from .session_manager import SessionManager


class SessionController:
    def __init__(
        self,
        session_manager: Optional[SessionManager] = None,
        callbacks: Optional[Dict[str, Callable]] = None,
    ):
        self.session_manager = session_manager or SessionManager()
        self.callbacks = callbacks
        self._session_id: Optional[str] = None
        self._current_activity_type: Optional[str] = None

    def _build_session_config(self) -> SessionConfig:
        return SessionConfig({
            'source_language': app_config.source_language,
            'target_language': app_config.target_language,
            'proficiency_level': app_config.proficiency_level,
        })

    def _ensure_session(self) -> None:
        if self._session_id is not None:
            return
        self._session_id = self.session_manager.create_session(
            self._build_session_config(), self.callbacks)
        self.session_manager.start_session(self._session_id)

    def has_active_activity(self) -> bool:
        return self._current_activity_type is not None

    def start_activity(self, activity_type: str) -> Dict[str, Any]:
        """(Re)start the given activity, creating a session on first use.

        Switching to a new activity completes whichever one was running
        before it, so its results are recorded rather than dropped.
        """
        self._ensure_session()
        session = self.session_manager.get_active_session()
        if self._current_activity_type is not None:
            session.complete_current_activity()
        result = session.start_activity(activity_type)
        self._current_activity_type = activity_type
        return result

    def send_message(self, message: str) -> Dict[str, Any]:
        """Process one user turn against the current activity."""
        if self._current_activity_type is None:
            raise Exception("No active activity -- call start_activity first")
        session = self.session_manager.get_active_session()
        return session.process_user_response(message)

    def reset(self) -> None:
        """Drop the active session so the next activity starts fresh.

        Needed because SessionConfig snapshots source/target language at
        session-creation time; a language change mid-session would
        otherwise keep applying to the stale language pair.
        """
        if self._session_id is not None:
            self.session_manager.end_session()
        self._session_id = None
        self._current_activity_type = None
