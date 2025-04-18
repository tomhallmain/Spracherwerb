from dataclasses import dataclass
import pickle
import gc
from typing import Optional, Dict, List, Any

from utils import Utils
from .learning_spot_profile import LearningSpot, LearningSpotProfile


@dataclass
class LearningSpotSnapshot:
    """A memory-efficient snapshot of a learning spot's essential data."""
    creation_time: float
    content: str
    was_spoken: bool
    interaction_type: str
    requires_response: bool
    media_generated: bool
    activity_type: str

    @classmethod
    def from_learning_spot(cls, spot: LearningSpot, activity_type: str) -> 'LearningSpotSnapshot':
        """Create a snapshot from a full learning spot."""
        return cls(
            creation_time=spot.timestamp,
            content=spot.content,
            was_spoken=spot.was_spoken,
            interaction_type=spot.interaction_type,
            requires_response=spot.requires_response,
            media_generated=spot.media_generated,
            activity_type=activity_type
        )


class LearningMemory:
    """Manages cross-session learning data and history."""
    
    # Class-level storage
    all_learning_spots: List[LearningSpot] = []
    last_session_spots: List[LearningSpot] = []
    current_session_spots: List[LearningSpot] = []
    max_memory_size = 1000
    max_historical_snapshots = 5000
    _historical_snapshots: Dict[float, LearningSpotSnapshot] = {}  # Keyed by creation_time
    
    # Learning progress tracking
    vocabulary_learned: Dict[str, List[str]] = {}  # language -> list of words
    grammar_points_covered: Dict[str, List[str]] = {}  # language -> list of points
    activity_progress: Dict[str, Dict[str, int]] = {}  # language -> activity_type -> count
    session_history: List[Dict[str, Any]] = []  # List of completed sessions
    
    @staticmethod
    def load():
        """Load learning memory from disk."""
        try:
            with open('learning_memory', 'rb') as f:
                swap = pickle.load(f)
                LearningMemory.all_learning_spots = list(swap.all_learning_spots)
                LearningMemory.last_session_spots = list(swap.current_session_spots)
                LearningMemory.vocabulary_learned = swap.vocabulary_learned
                LearningMemory.grammar_points_covered = swap.grammar_points_covered
                LearningMemory.activity_progress = swap.activity_progress
                LearningMemory.session_history = swap.session_history
                if hasattr(swap, '_historical_snapshots'):
                    LearningMemory._historical_snapshots = swap._historical_snapshots
        except FileNotFoundError:
            # Initialize with empty data
            LearningMemory.vocabulary_learned = {}
            LearningMemory.grammar_points_covered = {}
            LearningMemory.activity_progress = {}
            LearningMemory.session_history = []
        except Exception as e:
            Utils.log(f"Error loading learning memory: {e}")

    @staticmethod
    def save():
        """Save learning memory to disk."""
        with open('learning_memory', 'wb') as f:
            swap = LearningMemory()
            swap._historical_snapshots = LearningMemory._historical_snapshots
            swap.vocabulary_learned = LearningMemory.vocabulary_learned
            swap.grammar_points_covered = LearningMemory.grammar_points_covered
            swap.activity_progress = LearningMemory.activity_progress
            swap.session_history = LearningMemory.session_history
            pickle.dump(swap, f)

    @staticmethod
    def update_all_learning_spots(spot: LearningSpot, activity_type: str):
        """Update the learning spots list and maintain historical snapshots."""
        Utils.log_debug(f"Updating all learning spots: current count={len(LearningMemory.all_learning_spots)}, new spot creation_time={spot.timestamp}")
        
        if len(LearningMemory.all_learning_spots) > 0:
            # Clean up the previous spot if it exists
            previous_spot = LearningMemory.all_learning_spots[0]
            Utils.log_debug(f"Cleaning up previous spot: creation_time={previous_spot.timestamp}, was_spoken={previous_spot.was_spoken}")
            gc.collect()

        # Add to current spots
        LearningMemory.all_learning_spots.insert(0, spot)
        
        if len(LearningMemory.all_learning_spots) > LearningMemory.max_memory_size:
            Utils.log_debug(f"Exceeding max memory size ({LearningMemory.max_memory_size}), converting excess spots to snapshots")
            for spot in LearningMemory.all_learning_spots[LearningMemory.max_memory_size:]:
                LearningMemory._add_historical_snapshot(spot, activity_type)
            LearningMemory.all_learning_spots = LearningMemory.all_learning_spots[:LearningMemory.max_memory_size]

    @staticmethod
    def _add_historical_snapshot(spot: LearningSpot, activity_type: str):
        """Add a learning spot snapshot to historical storage."""
        snapshot = LearningSpotSnapshot.from_learning_spot(spot, activity_type)
        LearningMemory._historical_snapshots[spot.timestamp] = snapshot
        
        # Purge old snapshots if we exceed the limit
        if len(LearningMemory._historical_snapshots) > LearningMemory.max_historical_snapshots:
            oldest_times = sorted(LearningMemory._historical_snapshots.keys())[:-LearningMemory.max_historical_snapshots]
            for time_key in oldest_times:
                del LearningMemory._historical_snapshots[time_key]

    @staticmethod
    def update_current_session_spots(spot: LearningSpot):
        """Update the current session's learning spots."""
        LearningMemory.current_session_spots.insert(0, spot)
        if len(LearningMemory.current_session_spots) > LearningMemory.max_memory_size:
            LearningMemory.current_session_spots = LearningMemory.current_session_spots[:LearningMemory.max_memory_size]

    @staticmethod
    def get_previous_session_spot(idx: int = 0, creation_time: Optional[float] = None) -> Optional[LearningSpot]:
        """Get the previous learning spot at the given index."""
        Utils.log_debug(f"get_previous_session_spot called: idx={idx}, creation_time={creation_time}, list_length={len(LearningMemory.current_session_spots)}")
        
        if len(LearningMemory.current_session_spots) <= idx:
            return None
            
        if creation_time is None:
            return LearningMemory.current_session_spots[idx]
            
        base_idx = idx
        while base_idx < len(LearningMemory.current_session_spots):
            spot = LearningMemory.current_session_spots[base_idx]
            if spot.timestamp < creation_time:
                break
            base_idx += 1
            
        if base_idx >= len(LearningMemory.current_session_spots):
            return None
            
        target_idx = base_idx + idx
        if target_idx >= len(LearningMemory.current_session_spots):
            return None

        return LearningMemory.current_session_spots[target_idx]

    @staticmethod
    def update_vocabulary(language: str, word: str):
        """Update the learned vocabulary for a language."""
        if language not in LearningMemory.vocabulary_learned:
            LearningMemory.vocabulary_learned[language] = []
        if word not in LearningMemory.vocabulary_learned[language]:
            LearningMemory.vocabulary_learned[language].append(word)

    @staticmethod
    def update_grammar(language: str, grammar_point: str):
        """Update the covered grammar points for a language."""
        if language not in LearningMemory.grammar_points_covered:
            LearningMemory.grammar_points_covered[language] = []
        if grammar_point not in LearningMemory.grammar_points_covered[language]:
            LearningMemory.grammar_points_covered[language].append(grammar_point)

    @staticmethod
    def update_activity_progress(language: str, activity_type: str):
        """Update the progress for a specific activity type in a language."""
        if language not in LearningMemory.activity_progress:
            LearningMemory.activity_progress[language] = {}
        if activity_type not in LearningMemory.activity_progress[language]:
            LearningMemory.activity_progress[language][activity_type] = 0
        LearningMemory.activity_progress[language][activity_type] += 1

    @staticmethod
    def add_session_to_history(session_data: Dict[str, Any]):
        """Add a completed session to the history."""
        LearningMemory.session_history.append(session_data)
        if len(LearningMemory.session_history) > 100:  # Keep last 100 sessions
            LearningMemory.session_history = LearningMemory.session_history[-100:]

    def __init__(self):
        """Initialize a new LearningMemory instance."""
        self.vocabulary_learned = {}
        self.grammar_points_covered = {}
        self.activity_progress = {}
        self.session_history = [] 