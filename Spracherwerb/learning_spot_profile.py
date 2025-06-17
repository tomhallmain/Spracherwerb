import random
import time
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

from utils.config import config
from utils.translations import I18N
from utils.logging_setup import get_logger

_ = I18N._

logger = get_logger(__name__)

@dataclass
class LearningSpot:
    """Represents a single learning interaction spot"""
    content: str
    timestamp: float
    was_spoken: bool = False
    interaction_type: str = "text"  # text, question, feedback, explanation
    requires_response: bool = False
    media_generated: bool = False


class LearningSpotProfile:
    """Manages decision rules for learning interactions within an activity"""
    
    # Configuration from config
    chance_feedback_after_response = config.learning_config.get("chance_feedback_after_response", 0.7)
    chance_explanation_before_question = config.learning_config.get("chance_explanation_before_question", 0.5)
    min_seconds_between_spots = config.learning_config.get("min_seconds_between_spots", 5)
    max_interactions_per_activity = config.learning_config.get("max_interactions_per_activity", 10)
    
    # Class-level history management
    _interaction_history: List[LearningSpot] = []
    _max_history = 100
    
    def __init__(
        self,
        activity_type: str,
        previous_spot: Optional[LearningSpot] = None,
        current_content: Optional[str] = None,
        get_previous_spot_callback=None,
        get_next_content_callback=None
    ):
        self.activity_type = activity_type
        self.previous_spot = previous_spot
        self.current_content = current_content
        self.creation_time = time.time()
        self.preparation_time = None
        self.get_previous_spot_callback = get_previous_spot_callback
        self.get_next_content_callback = get_next_content_callback
        
        # Update interaction history
        if current_content and (not self._interaction_history or self._interaction_history[-1].content != current_content):
            self._interaction_history.append(LearningSpot(
                content=current_content,
                timestamp=time.time()
            ))
            if len(self._interaction_history) > self._max_history:
                self._interaction_history = self._interaction_history[-self._max_history:]
        
        # Determine if this is the first interaction in the activity
        self.is_first_interaction = previous_spot is None and not self._interaction_history
        
        # For the first interaction, we should provide an introduction
        if self.is_first_interaction:
            logger.info("First interaction of activity - preparing introduction")
            self.provide_introduction = True
        else:
            self.provide_introduction = False
        
        # Determine if we should provide feedback on the previous response
        self.provide_feedback = (
            previous_spot is not None and 
            previous_spot.requires_response and 
            random.random() < self.chance_feedback_after_response
        )
        
        # Determine if we should provide an explanation before a question
        self.provide_explanation = (
            current_content is not None and 
            random.random() < self.chance_explanation_before_question
        )
        
        # Determine if we should generate media for this content
        self.generate_media = (
            current_content is not None and 
            config.enable_visual_learning and
            self._should_generate_media()
        )
        
        # Track if this spot has been prepared
        self.is_prepared = False
        self.has_already_spoken = False
        
    def _should_generate_media(self) -> bool:
        """Determine if media should be generated for this content"""
        # Higher chance for vocabulary and cultural content
        if self.activity_type in ['vocabulary_builder', 'cultural_context']:
            return random.random() < 0.8
        # Medium chance for grammar and situational dialogues
        elif self.activity_type in ['grammar_practice', 'situational_dialogues']:
            return random.random() < 0.5
        # Lower chance for other activities
        return random.random() < 0.3
        
    def get_previous_spot(self, idx: int = 0) -> Optional[LearningSpot]:
        """Get the previous spot that was actually spoken"""
        if self.get_previous_spot_callback is None:
            raise Exception("Previous spot callback was not set properly")
        return self.get_previous_spot_callback(idx=idx, creation_time=self.creation_time)
        
    def get_next_content(self) -> Optional[str]:
        """Get the next content to be presented"""
        if self.get_next_content_callback is None:
            return None
        return self.get_next_content_callback()
        
    def get_time(self) -> float:
        """Get the current time for this spot"""
        return self.creation_time if self.preparation_time is None else self.preparation_time
        
    def is_going_to_say_something(self) -> bool:
        """Determine if this spot will result in speech"""
        if self.provide_introduction or self.provide_feedback or self.provide_explanation:
            return True
            
        # Check time restriction
        no_time_restriction = self.last_spot_more_than_seconds(self.min_seconds_between_spots)
        if not no_time_restriction:
            logger.info("Time restriction applied to current spot preparation")
            return False
            
        return True
        
    def last_spot_more_than_seconds(self, seconds: float) -> bool:
        """Check if enough time has passed since the last spoken spot"""
        current_time = time.time()
        last_spot = self.get_last_spoken_spot()
        if last_spot is None:
            return True
        return (current_time - last_spot.timestamp) > seconds
        
    def get_last_spoken_spot(self) -> Optional[LearningSpot]:
        """Get the most recent spot that was actually spoken"""
        logger.debug(f"Starting get_last_spoken_spot for profile created at {self.creation_time}")
        idx = 0
        max_iterations = 100  # Failsafe to prevent infinite loops
        
        while True:
            spot = self.get_previous_spot(idx=idx)
            if spot is None:
                logger.debug(f"No spot found at index {idx}")
                return None
                
            logger.debug(f"Checking spot at index {idx}: timestamp={spot.timestamp}, was_spoken={spot.was_spoken}")
            
            if spot.was_spoken:
                logger.debug(f"Found spoken spot at index {idx}: timestamp={spot.timestamp}")
                return spot
                
            idx += 1
            if idx >= max_iterations:
                logger.error(f"Failsafe triggered: get_last_spoken_spot exceeded {max_iterations} iterations")
                return None
                
    def set_preparation_time(self) -> None:
        """Set the preparation time for this spot"""
        self.preparation_time = time.time()
        
    def mark_as_spoken(self) -> None:
        """Mark this spot as having been spoken"""
        self.has_already_spoken = True
        if self.current_content:
            for spot in self._interaction_history:
                if spot.content == self.current_content:
                    spot.was_spoken = True
                    break
                    
    def reset(self) -> None:
        """Reset the preparation state of this spot"""
        self.is_prepared = False
        self.preparation_time = None
        
    def __str__(self) -> str:
        """String representation of the spot profile"""
        out = f"Activity: {self.activity_type}\n"
        if self.current_content:
            out += f"Current Content: {self.current_content}\n"
        if self.provide_introduction:
            out += " - Providing introduction\n"
        if self.provide_feedback:
            out += " - Providing feedback\n"
        if self.provide_explanation:
            out += " - Providing explanation\n"
        if self.generate_media:
            out += " - Generating media\n"
        return out 