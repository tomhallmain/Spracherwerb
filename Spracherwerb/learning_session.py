from typing import Optional, Dict, Any, Callable
import time
import logging

from .session_config import SessionConfig
from .learning_engine import LearningEngine
from .session_context import SessionState, UserAction

logger = logging.getLogger(__name__)


class LearningSession:
    """Represents a single language learning session"""
    
    def __init__(
        self,
        session_config: SessionConfig,
        callbacks: Optional[Dict[str, Callable]] = None
    ):
        self.config = session_config
        self.state = SessionState(
            start_time=time.time(),
            activities_completed=[],
            vocabulary_learned=[],
            grammar_points_covered=[],
            time_spent=0
        )
        self.learning_engine = None
        self._setup_callbacks(callbacks)
        
    def _setup_callbacks(self, callbacks: Optional[Dict[str, Callable]]) -> None:
        """Setup callbacks for session events"""
        if not callbacks:
            return
            
        self.callbacks = {
            'activity_started': callbacks.get('activity_started'),
            'activity_completed': callbacks.get('activity_completed'),
            'user_response_processed': callbacks.get('user_response_processed'),
            'media_generated': callbacks.get('media_generated'),
            'error_occurred': callbacks.get('error_occurred')
        }
        
    def start(self) -> None:
        """Start the learning session"""
        try:
            if not self.config.validate():
                raise Exception("Invalid session configuration")
                
            self.learning_engine = LearningEngine(self.config, self.state)
            
            logger.info("Started new learning session")
            
        except Exception as e:
            logger.error(f"Failed to start learning session: {str(e)}")
            if self.callbacks and 'error_occurred' in self.callbacks:
                self.callbacks['error_occurred'](str(e))
            raise
            
    def start_activity(self, activity_type: str) -> Dict[str, Any]:
        """Start a new learning activity"""
        try:
            if not self.learning_engine:
                raise Exception("Session not started")
                
            result = self.learning_engine.start_activity(activity_type)
            
            if self.callbacks and 'activity_started' in self.callbacks:
                self.callbacks['activity_started'](activity_type, result)
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to start activity {activity_type}: {str(e)}")
            if self.callbacks and 'error_occurred' in self.callbacks:
                self.callbacks['error_occurred'](str(e))
            raise
            
    def process_user_response(self, response: str) -> Dict[str, Any]:
        """Process a user's response to the current activity"""
        try:
            if not self.learning_engine:
                raise Exception("Session not started")
                
            result = self.learning_engine.process_user_response(response)
            
            if self.callbacks and 'user_response_processed' in self.callbacks:
                self.callbacks['user_response_processed'](result)
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to process user response: {str(e)}")
            if self.callbacks and 'error_occurred' in self.callbacks:
                self.callbacks['error_occurred'](str(e))
            raise
            
    def generate_media(self, content: str) -> Optional[str]:
        """Generate media content for the current activity"""
        try:
            if not self.learning_engine:
                raise Exception("Session not started")
                
            media_path = self.learning_engine.generate_media(content)
            
            if media_path and self.callbacks and 'media_generated' in self.callbacks:
                self.callbacks['media_generated'](media_path)
                
            return media_path
            
        except Exception as e:
            logger.error(f"Failed to generate media: {str(e)}")
            if self.callbacks and 'error_occurred' in self.callbacks:
                self.callbacks['error_occurred'](str(e))
            return None
            
    def complete_current_activity(self) -> Dict[str, Any]:
        """Complete the current activity"""
        try:
            if not self.learning_engine:
                raise Exception("Session not started")
                
            results = self.learning_engine.complete_activity()
            
            if self.callbacks and 'activity_completed' in self.callbacks:
                self.callbacks['activity_completed'](results)
                
            return results
            
        except Exception as e:
            logger.error(f"Failed to complete activity: {str(e)}")
            if self.callbacks and 'error_occurred' in self.callbacks:
                self.callbacks['error_occurred'](str(e))
            raise
            
    def handle_user_action(self, action: UserAction) -> None:
        """Handle user actions like pause, resume, skip"""
        try:
            if not self.learning_engine:
                raise Exception("Session not started")
                
            self.learning_engine.handle_user_action(action)
            self.state.update_action(action)
                
        except Exception as e:
            logger.error(f"Failed to handle user action {action}: {str(e)}")
            if self.callbacks and 'error_occurred' in self.callbacks:
                self.callbacks['error_occurred'](str(e))
            raise
            
    def get_session_progress(self) -> Dict[str, Any]:
        """Get the current progress of the session"""
        return {
            'state': self.state.get_progress(),
            'current_activity': self.state.current_activity
        }
        
    def cleanup(self) -> None:
        """Clean up session resources"""
        if self.learning_engine:
            self.learning_engine.cleanup()
        self.learning_engine = None 