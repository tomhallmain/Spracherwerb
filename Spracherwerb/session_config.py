from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum, auto

class SessionType(Enum):
    """Types of language learning sessions"""
    REGULAR = auto()          # Standard learning session
    FOCUSED = auto()          # Focus on specific skills
    REVIEW = auto()           # Review previous material
    ASSESSMENT = auto()       # Progress assessment
    CUSTOM = auto()           # User-defined session

class DifficultyLevel(Enum):
    """Difficulty levels for learning activities"""
    BEGINNER = auto()
    INTERMEDIATE = auto()
    ADVANCED = auto()

@dataclass
class SessionConfig:
    """Configuration for a language learning session"""
    # Session type and duration
    session_type: SessionType = SessionType.REGULAR
    duration_minutes: int = 30
    auto_start: bool = False
    
    # Learning focus areas
    learning_activities: List[str] = field(default_factory=lambda: [
        "vocabulary_builder",
        "grammar_practice",
        "conversation_practice"
    ])
    
    # Activity-specific settings
    vocabulary_difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE
    grammar_difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE
    
    # Additional settings
    custom_settings: Dict[str, Any] = field(default_factory=dict)
    
    def __init__(self, args: Optional[Dict[str, Any]] = None, placeholder: bool = False):
        """Initialize session configuration with optional arguments"""
        if args:
            self._update_from_args(args)
        self.placeholder = placeholder
    
    def _update_from_args(self, args: Dict[str, Any]) -> None:
        """Update configuration from provided arguments"""
        # Session type and duration
        if 'session_type' in args:
            self.session_type = SessionType[args['session_type'].upper()]
        if 'duration_minutes' in args:
            self.duration_minutes = int(args['duration_minutes'])
        if 'auto_start' in args:
            self.auto_start = bool(args['auto_start'])
        
        # Learning activities
        if 'learning_activities' in args:
            self.learning_activities = args['learning_activities']
        
        # Activity settings
        if 'vocabulary_difficulty' in args:
            self.vocabulary_difficulty = DifficultyLevel[args['vocabulary_difficulty'].upper()]
        if 'grammar_difficulty' in args:
            self.grammar_difficulty = DifficultyLevel[args['grammar_difficulty'].upper()]
        
        # Custom settings
        if 'custom_settings' in args:
            self.custom_settings.update(args['custom_settings'])
    
    def validate(self) -> bool:
        """Validate the session configuration"""
        # Basic validation
        if self.duration_minutes <= 0:
            return False
        if not self.learning_activities:
            return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            'session_type': self.session_type.name,
            'duration_minutes': self.duration_minutes,
            'auto_start': self.auto_start,
            'learning_activities': self.learning_activities,
            'vocabulary_difficulty': self.vocabulary_difficulty.name,
            'grammar_difficulty': self.grammar_difficulty.name,
            'custom_settings': self.custom_settings
        }
    
    def __str__(self) -> str:
        """String representation of the configuration"""
        return str(self.to_dict()) 