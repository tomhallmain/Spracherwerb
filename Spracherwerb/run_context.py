from dataclasses import dataclass, field
from enum import Enum, auto
from time import time
from typing import Optional, Dict

class UserAction(Enum):
    """Enum representing different types of user actions."""
    NONE = auto()
    SKIP_TRACK = auto()
    SKIP_GROUPING = auto()
    PAUSE = auto()
    CANCEL = auto()
    SKIP_DELAY = auto()

@dataclass
class RunContext:
    """Manages the state of user interactions with the playback system.
    
    This class tracks various user-initiated actions and their effects on the playback system,
    allowing components like Playback, Muse, Voice, and LLM to respond appropriately to user input.
    """
    # Current user action
    user_action: UserAction = UserAction.NONE
    
    # State flags (replacing the old boolean flags in Playback)
    skip_track: bool = False
    skip_delay: bool = False
    skip_grouping: bool = False
    is_paused: bool = False
    
    # Map of interaction times for each action type
    interaction_times: Dict[UserAction, float] = field(default_factory=dict)
    
    def update_action(self, action: UserAction) -> None:
        """Update the current user action and its interaction time."""
        self.user_action = action
        self.interaction_times[action] = time()
        
        # Update the corresponding state flags
        self.skip_track = action == UserAction.SKIP_TRACK
        self.skip_delay = action == UserAction.SKIP_DELAY
        self.skip_grouping = action == UserAction.SKIP_GROUPING
        self.is_paused = action == UserAction.PAUSE
    
    def get_last_interaction_time(self, action: UserAction) -> Optional[float]:
        """Get the timestamp of the last interaction for a specific action."""
        return self.interaction_times.get(action)
    
    def reset(self) -> None:
        """Reset all state to default values."""
        self.user_action = UserAction.NONE
        self.skip_track = False
        self.skip_delay = False
        self.skip_grouping = False
        self.is_paused = False
        self.interaction_times.clear()

    def should_skip(self) -> bool:
        """Determine if the current action should be skipped based on skip flags.
        
        Returns:
            bool: True if either skip_track or skip_grouping is True, False otherwise.
        """
        return self.skip_track or self.skip_grouping 