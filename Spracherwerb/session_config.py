from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum, auto

from utils.config import config


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
    
    # Language settings (default from app config)
    source_language: str = field(default_factory=lambda: getattr(config, "source_language", None) or "en")
    target_language: str = field(default_factory=lambda: getattr(config, "target_language", None) or "de")
    proficiency_level: str = field(default_factory=lambda: getattr(config, "proficiency_level", None) or "intermediate")
    enable_visual_learning: bool = field(default_factory=lambda: getattr(config, "enable_visual_learning", True))
    enable_pronunciation_practice: bool = field(default_factory=lambda: getattr(config, "enable_pronunciation_practice", True))
    
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
        self.session_type = SessionType.REGULAR
        self.duration_minutes = 30
        self.auto_start = False
        self.source_language = getattr(config, "source_language", None) or "en"
        self.target_language = getattr(config, "target_language", None) or "de"
        self.proficiency_level = getattr(config, "proficiency_level", None) or "intermediate"
        self.enable_visual_learning = getattr(config, "enable_visual_learning", True)
        self.enable_pronunciation_practice = getattr(config, "enable_pronunciation_practice", True)
        self.learning_activities = [
            "vocabulary_builder",
            "grammar_practice",
            "conversation_practice",
        ]
        self.vocabulary_difficulty = DifficultyLevel.INTERMEDIATE
        self.grammar_difficulty = DifficultyLevel.INTERMEDIATE
        self.custom_settings = {}
        self.placeholder = placeholder
        if args:
            self._update_from_args(args)
    
    def _update_from_args(self, args: Dict[str, Any]) -> None:
        """Update configuration from provided arguments"""
        if 'session_type' in args:
            self.session_type = SessionType[args['session_type'].upper()]
        if 'duration_minutes' in args:
            self.duration_minutes = int(args['duration_minutes'])
        if 'auto_start' in args:
            self.auto_start = bool(args['auto_start'])
        if 'source_language' in args:
            self.source_language = args['source_language']
        if 'target_language' in args:
            self.target_language = args['target_language']
        if 'proficiency_level' in args:
            self.proficiency_level = args['proficiency_level']
        if 'enable_visual_learning' in args:
            self.enable_visual_learning = bool(args['enable_visual_learning'])
        if 'enable_pronunciation_practice' in args:
            self.enable_pronunciation_practice = bool(args['enable_pronunciation_practice'])
        if 'learning_activities' in args:
            self.learning_activities = args['learning_activities']
        if 'vocabulary_difficulty' in args:
            self.vocabulary_difficulty = DifficultyLevel[args['vocabulary_difficulty'].upper()]
        if 'grammar_difficulty' in args:
            self.grammar_difficulty = DifficultyLevel[args['grammar_difficulty'].upper()]
        if 'custom_settings' in args:
            self.custom_settings.update(args['custom_settings'])
    
    def validate(self) -> bool:
        """Validate the session configuration"""
        if self.duration_minutes <= 0:
            return False
        if not self.learning_activities:
            return False
        if not self.source_language or not self.target_language:
            return False
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            'session_type': self.session_type.name,
            'duration_minutes': self.duration_minutes,
            'auto_start': self.auto_start,
            'source_language': self.source_language,
            'target_language': self.target_language,
            'proficiency_level': self.proficiency_level,
            'enable_visual_learning': self.enable_visual_learning,
            'enable_pronunciation_practice': self.enable_pronunciation_practice,
            'learning_activities': self.learning_activities,
            'vocabulary_difficulty': self.vocabulary_difficulty.name,
            'grammar_difficulty': self.grammar_difficulty.name,
            'custom_settings': self.custom_settings
        }
    
    def __str__(self) -> str:
        """String representation of the configuration"""
        return str(self.to_dict())
