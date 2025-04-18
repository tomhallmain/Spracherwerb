from typing import Optional, Dict, Any, List
import time
import logging

from .voice import Voice
from .prompter import Prompter
from .session_context import SessionContext, UserAction
from .session_config import SessionConfig, SessionType, DifficultyLevel

logger = logging.getLogger(__name__)


class LearningEngine:
    """Core engine that handles learning activities, voice interactions, and prompt management"""
    
    def __init__(self, session_config: SessionConfig, session_state: SessionContext):
        self.config = session_config
        self.state = session_state
        self.voice = Voice()
        self.prompter = Prompter()
        self.current_activity = None
        self.activity_results = {}
        self._setup_voice()
        
    def _setup_voice(self) -> None:
        """Configure voice settings based on session config"""
        self.voice.set_language(self.config.target_language)
        self.voice.set_speed(1.0)  # Default speed, can be adjusted based on proficiency
        
    def start_activity(self, activity_type: str) -> Dict[str, Any]:
        """Start a new learning activity"""
        if not self.state.is_active():
            raise Exception("Cannot start activity in inactive session")
            
        self.current_activity = activity_type
        self.activity_results = {
            'start_time': time.time(),
            'activity_type': activity_type,
            'responses': [],
            'media_generated': []
        }
        
        # Get appropriate prompt for the activity
        prompt = self.prompter.get_prompt(
            activity_type,
            self.config.target_language,
            self.config.proficiency_level
        )
        
        # Initialize activity-specific state
        if activity_type == 'vocabulary_builder':
            self.activity_results['new_words'] = []
            self.activity_results['word_contexts'] = {}
        elif activity_type == 'grammar_practice':
            self.activity_results['grammar_points'] = []
            self.activity_results['examples'] = {}
            
        return {
            'prompt': prompt,
            'activity_type': activity_type,
            'config': self.config.to_dict()
        }
        
    def process_user_response(self, response: str) -> Dict[str, Any]:
        """Process a user's response to an activity"""
        if not self.current_activity:
            raise Exception("No active activity to process response for")
            
        # Get next prompt based on user response
        next_prompt = self.prompter.get_next_prompt(
            self.current_activity,
            response,
            self.config.target_language
        )
        
        # Generate voice response if needed
        voice_response = None
        if self.config.enable_pronunciation_practice:
            voice_response = self.voice.generate_speech(next_prompt)
            
        # Update activity results
        self.activity_results['responses'].append({
            'user_input': response,
            'system_response': next_prompt,
            'timestamp': time.time()
        })
        
        return {
            'text_response': next_prompt,
            'voice_response': voice_response,
            'activity_type': self.current_activity
        }
        
    def generate_media(self, content: str) -> Optional[str]:
        """Generate media content for the current activity"""
        if not self.config.enable_visual_learning:
            return None
            
        # TODO: Implement media generation
        # This will be implemented when we have the media generation system ready
        return None
        
    def complete_activity(self) -> Dict[str, Any]:
        """Complete the current activity and return results"""
        if not self.current_activity:
            raise Exception("No active activity to complete")
            
        self.activity_results['end_time'] = time.time()
        self.activity_results['duration'] = (
            self.activity_results['end_time'] - self.activity_results['start_time']
        )
        
        # Update session state with activity results
        self.state.complete_activity(self.current_activity, self.activity_results)
        
        # Clear current activity
        self.current_activity = None
        results = self.activity_results.copy()
        self.activity_results = {}
        
        return results
        
    def handle_user_action(self, action: UserAction) -> None:
        """Handle user actions like pause, resume, skip"""
        self.state.update_action(action)
        
        if action == UserAction.PAUSE:
            self.voice.pause()
        elif action == UserAction.RESUME:
            self.voice.resume()
        elif action == UserAction.SKIP_ACTIVITY:
            self.complete_activity()
            
    def cleanup(self) -> None:
        """Clean up resources"""
        self.voice.cleanup()
        self.current_activity = None
        self.activity_results = {} 