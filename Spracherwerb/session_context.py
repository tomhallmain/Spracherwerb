from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List, Dict, Any
import time

from utils.config import config
from utils.translations import I18N

_ = I18N._


class UserAction(Enum):
    """Types of user actions that can affect a session"""
    NONE = auto()
    PAUSE = auto()
    RESUME = auto()
    STOP = auto()
    SKIP_ACTIVITY = auto()
    CANCEL = auto()


@dataclass
class SessionContext:
    """Tracks the current state of a learning session"""
    start_time: float
    activities_completed: List[Dict[str, Any]]
    vocabulary_learned: List[str]
    grammar_points_covered: List[str]
    time_spent: float
    current_activity: Optional[str] = None
    pause_time: Optional[float] = None
    end_time: Optional[float] = None
    total_time: Optional[float] = None
    last_user_action: UserAction = UserAction.NONE
    last_action_time: float = field(default_factory=time.time)
    is_paused: bool = False
    is_cancelled: bool = False
    skip_current_activity: bool = False

    def update_action(self, action: UserAction) -> None:
        """Update the current user action and its timestamp"""
        self.last_user_action = action
        self.last_action_time = time.time()
        
        if action == UserAction.PAUSE:
            self.is_paused = True
            self.pause_time = time.time()
        elif action == UserAction.RESUME:
            self.is_paused = False
            if self.pause_time is not None:
                pause_duration = time.time() - self.pause_time
                self.time_spent += pause_duration
                self.pause_time = None
        elif action == UserAction.STOP:
            self.end_time = time.time()
            self.total_time = self.end_time - self.start_time
        elif action == UserAction.SKIP_ACTIVITY:
            self.skip_current_activity = True
        elif action == UserAction.CANCEL:
            self.is_cancelled = True
            self.end_time = time.time()
            self.total_time = self.end_time - self.start_time

    def get_progress(self) -> Dict[str, Any]:
        """Get the current progress of the session"""
        return {
            'activities_completed': len(self.activities_completed),
            'vocabulary_learned': len(self.vocabulary_learned),
            'grammar_points_covered': len(self.grammar_points_covered),
            'time_spent': self.time_spent,
            'is_paused': self.is_paused,
            'current_activity': self.current_activity
        }

    def complete_activity(self, activity: str, results: Dict[str, Any]) -> None:
        """Mark an activity as completed with its results"""
        self.activities_completed.append({
            'activity': activity,
            'results': results,
            'completion_time': time.time()
        })
        
        # Update relevant metrics based on activity type
        if activity == 'vocabulary_builder':
            self.vocabulary_learned.extend(results.get('new_words', []))
        elif activity == 'grammar_practice':
            self.grammar_points_covered.extend(results.get('grammar_points', []))

    def set_current_activity(self, activity: str) -> None:
        """Set the current learning activity"""
        self.current_activity = activity
        self.skip_current_activity = False

    def should_skip_current_activity(self) -> bool:
        """Check if the current activity should be skipped"""
        return self.skip_current_activity

    def is_active(self) -> bool:
        """Check if the session is currently active"""
        return not self.is_cancelled and not self.is_paused and self.end_time is None

    def get_elapsed_time(self) -> float:
        """Get the total elapsed time of the session"""
        if self.end_time is not None:
            return self.total_time
        current_time = time.time()
        if self.is_paused and self.pause_time is not None:
            return self.time_spent
        return current_time - self.start_time 