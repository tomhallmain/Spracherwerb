"""
Spracherwerb package for interactive language learning with AI assistance.
"""

from .activity_registry import ActivityRegistry
from .activity_results import ActivityStartResult, ActivityTurnResult, ModuleServices
from .activity_types import ActivityType, LearningActivity
from .base_learning_module import ActivityNotRegisteredError, BaseLearningModule
from .conversation_practice import ConversationPractice
from .grammar_practice import GrammarPractice
from .language_tutor import LanguageTutor
from .learning_engine import LearningEngine
from .learning_memory import LearningMemory
from .learning_progression import LearningProgression
from .learning_session import LearningSession
from .learning_spot_profile import LearningSpotProfile
from .listening_comprehension import ListeningComprehension
from .prompter import Prompter
from .session_config import SessionConfig
from .session_context import SessionContext
from .session_controller import SessionController
from .session_manager import SessionManager
from .stub_learning_module import StubLearningModule
from .visual_vocabulary import VisualVocabulary
from .vocabulary_builder import VocabularyBuilder
from .voice import Voice
from .writing_practice import WritingPractice
# TODO: Implement the following modules
# from .cultural_context import CulturalContext
# from .pronunciation_guide import PronunciationGuide
# from .idioms_and_expressions import IdiomsAndExpressions
# from .reading_comprehension import ReadingComprehension
# from .situational_dialogues import SituationalDialogues

__all__ = [
    'ActivityNotRegisteredError',
    'ActivityRegistry',
    'ActivityStartResult',
    'ActivityTurnResult',
    'ActivityType',
    'BaseLearningModule',
    'ConversationPractice',
    'GrammarPractice',
    'LanguageTutor',
    'LearningActivity',
    'LearningEngine',
    'LearningMemory',
    'LearningProgression',
    'LearningSession',
    'LearningSpotProfile',
    'ListeningComprehension',
    'ModuleServices',
    'Prompter',
    'SessionConfig',
    'SessionContext',
    'SessionController',
    'SessionManager',
    'StubLearningModule',
    'VisualVocabulary',
    'VocabularyBuilder',
    'Voice',
    'WritingPractice',
]
