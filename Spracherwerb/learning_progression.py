"""Learning progression management for the Spracherwerb application."""

from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from enum import Enum
import time

from utils.utils import Utils
from .learning_spot_profile import LearningSpot, LearningSpotProfile
from .learning_memory import LearningMemory


class ActivityType(Enum):
    """Types of learning activities."""
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


@dataclass
class LearningActivity:
    """Represents a learning activity with its content and progression."""
    activity_type: ActivityType
    content: str
    expected_responses: List[str]
    difficulty_level: int
    requires_media: bool
    media_generated: bool = False
    completed: bool = False
    user_responses: List[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    learning_spot: Optional[LearningSpot] = None

    def __post_init__(self):
        if self.user_responses is None:
            self.user_responses = []
        if self.start_time is None:
            self.start_time = time.time()

    def mark_completed(self):
        """Mark the activity as completed and record the end time."""
        self.completed = True
        self.end_time = time.time()
        if self.learning_spot:
            self.learning_spot.completed = True
            self.learning_spot.end_time = self.end_time

    def add_user_response(self, response: str):
        """Add a user response to the activity."""
        self.user_responses.append(response)
        if self.learning_spot:
            self.learning_spot.user_responses.append(response)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the activity to a dictionary for serialization."""
        return {
            "activity_type": self.activity_type.value,
            "content": self.content,
            "expected_responses": self.expected_responses,
            "difficulty_level": self.difficulty_level,
            "requires_media": self.requires_media,
            "media_generated": self.media_generated,
            "completed": self.completed,
            "user_responses": self.user_responses,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "learning_spot": self.learning_spot.to_dict() if self.learning_spot else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LearningActivity':
        """Create an activity from a dictionary."""
        learning_spot = None
        if data.get("learning_spot"):
            learning_spot = LearningSpot.from_dict(data["learning_spot"])
        return cls(
            activity_type=ActivityType(data["activity_type"]),
            content=data["content"],
            expected_responses=data["expected_responses"],
            difficulty_level=data["difficulty_level"],
            requires_media=data["requires_media"],
            media_generated=data.get("media_generated", False),
            completed=data.get("completed", False),
            user_responses=data.get("user_responses", []),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            learning_spot=learning_spot
        )


class LearningProgression:
    """Manages the progression of learning activities and content."""
    
    def __init__(self):
        self.completed_activities: List[LearningActivity] = []
        self.current_activity: Optional[LearningActivity] = None
        self.upcoming_activities: List[LearningActivity] = []
        self.activity_history: List[LearningActivity] = []
        self.learning_memory = LearningMemory()
        self._initialize_from_memory()

    def _initialize_from_memory(self):
        """Initialize the progression from learning memory."""
        # Load any existing activities from memory
        if hasattr(self.learning_memory, 'activity_history'):
            for activity_data in self.learning_memory.activity_history:
                activity = LearningActivity.from_dict(activity_data)
                self.activity_history.append(activity)
                if activity.completed:
                    self.completed_activities.append(activity)

    def add_activity(self, activity: LearningActivity):
        """Add a new activity to the progression."""
        self.upcoming_activities.append(activity)
        self.learning_memory.update_activity_progress(
            activity.activity_type.value,
            len(self.upcoming_activities)
        )

    def start_next_activity(self) -> Optional[LearningActivity]:
        """Start the next activity in the progression."""
        if not self.upcoming_activities:
            return None
            
        self.current_activity = self.upcoming_activities.pop(0)
        self.current_activity.start_time = time.time()
        
        # Create a learning spot for the current activity
        spot = LearningSpot(
            content=self.current_activity.content,
            activity_type=self.current_activity.activity_type.value,
            requires_response=bool(self.current_activity.expected_responses),
            media_generated=self.current_activity.media_generated
        )
        self.current_activity.learning_spot = spot
        
        return self.current_activity

    def complete_current_activity(self):
        """Complete the current activity and move it to history."""
        if self.current_activity:
            self.current_activity.mark_completed()
            self.completed_activities.append(self.current_activity)
            self.activity_history.append(self.current_activity)
            
            # Update learning memory
            self.learning_memory.update_all_learning_spots(
                self.current_activity.learning_spot,
                self.current_activity.activity_type.value
            )
            
            self.current_activity = None

    def add_user_response(self, response: str):
        """Add a user response to the current activity."""
        if self.current_activity:
            self.current_activity.add_user_response(response)
            if self.current_activity.learning_spot:
                self.current_activity.learning_spot.user_responses.append(response)

    def get_progress(self) -> Dict[str, Any]:
        """Get the current progress of the learning session."""
        return {
            "completed_count": len(self.completed_activities),
            "upcoming_count": len(self.upcoming_activities),
            "current_activity": self.current_activity.to_dict() if self.current_activity else None,
            "total_activities": len(self.activity_history),
            "session_duration": sum(
                (a.end_time - a.start_time) 
                for a in self.completed_activities 
                if a.start_time and a.end_time
            ) if self.completed_activities else 0
        }

    def adjust_difficulty(self, adjustment: int):
        """Adjust the difficulty level of upcoming activities."""
        for activity in self.upcoming_activities:
            activity.difficulty_level = max(1, min(10, activity.difficulty_level + adjustment))

    def reorder_activities(self, new_order: List[int]):
        """Reorder the upcoming activities based on the provided indices."""
        if len(new_order) != len(self.upcoming_activities):
            Utils.log_red("Invalid reorder: length mismatch")
            return
            
        reordered = [self.upcoming_activities[i] for i in new_order]
        self.upcoming_activities = reordered

    def save_progress(self):
        """Save the current progress to learning memory."""
        self.learning_memory.save() 