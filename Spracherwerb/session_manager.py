import time
from typing import Optional, Dict, Any, List
from enum import Enum, auto
import logging

from utils.config import config
from utils.utils import Utils
from utils.translations import I18N
from .session_config import SessionConfig, SessionType, DifficultyLevel
from .session_context import SessionState, UserAction
from .learning_session import LearningSession

_ = I18N._
logger = logging.getLogger(__name__)


class SessionStateEnum(Enum):
    """Possible states of a language learning session"""
    NOT_STARTED = auto()
    IN_PROGRESS = auto()
    PAUSED = auto()
    COMPLETED = auto()
    CANCELLED = auto()


class LearningActivity(Enum):
    """Types of learning activities available"""
    VOCABULARY_BUILDER = auto()
    GRAMMAR_PRACTICE = auto()
    CONVERSATION_PRACTICE = auto()
    LISTENING_COMPREHENSION = auto()
    WRITING_PRACTICE = auto()
    CULTURAL_CONTEXT = auto()
    PRONUNCIATION_GUIDE = auto()
    IDIOMS_AND_EXPRESSIONS = auto()
    READING_COMPREHENSION = auto()
    SITUATIONAL_DIALOGUES = auto()
    VISUAL_VOCABULARY = auto()


class SessionManager:
    """Manages multiple language learning sessions"""
    
    def __init__(self):
        self.sessions: Dict[str, LearningSession] = {}
        self.active_session_id: Optional[str] = None
        
    def create_session(self, session_config: SessionConfig, callbacks: Optional[Dict[str, Any]] = None) -> str:
        """Create a new learning session"""
        session = LearningSession(session_config, callbacks)
        session_id = str(time.time())
        self.sessions[session_id] = session
        return session_id
        
    def start_session(self, session_id: str) -> None:
        """Start a specific learning session"""
        if session_id not in self.sessions:
            raise Exception(f"Session {session_id} not found")
            
        if self.active_session_id:
            raise Exception("Another session is already active")
            
        self.sessions[session_id].start()
        self.active_session_id = session_id
        
    def get_active_session(self) -> Optional[LearningSession]:
        """Get the currently active session"""
        if not self.active_session_id:
            return None
        return self.sessions.get(self.active_session_id)
        
    def pause_session(self) -> None:
        """Pause the active session"""
        session = self.get_active_session()
        if not session:
            raise Exception("No active session to pause")
        session.handle_user_action(UserAction.PAUSE)
        
    def resume_session(self) -> None:
        """Resume the active session"""
        session = self.get_active_session()
        if not session:
            raise Exception("No active session to resume")
        session.handle_user_action(UserAction.RESUME)
        
    def end_session(self) -> None:
        """End the active session"""
        session = self.get_active_session()
        if not session:
            raise Exception("No active session to end")
        session.handle_user_action(UserAction.STOP)
        self.active_session_id = None
        
    def cancel_session(self) -> None:
        """Cancel the active session"""
        session = self.get_active_session()
        if not session:
            raise Exception("No active session to cancel")
        session.handle_user_action(UserAction.CANCEL)
        self.active_session_id = None
        
    def skip_current_activity(self) -> None:
        """Skip the current activity in the active session"""
        session = self.get_active_session()
        if not session:
            raise Exception("No active session to skip activity in")
        session.handle_user_action(UserAction.SKIP_ACTIVITY)
        
    def get_session_progress(self) -> Optional[Dict[str, Any]]:
        """Get the progress of the active session"""
        session = self.get_active_session()
        if not session:
            return None
        return session.get_session_progress()
        
    def cleanup(self) -> None:
        """Clean up all sessions"""
        for session in self.sessions.values():
            session.cleanup()
        self.sessions.clear()
        self.active_session_id = None 