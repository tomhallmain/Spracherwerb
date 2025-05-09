
def placeholder_callback(*args, **kwargs):
    raise NotImplementedError("This callback is not implemented!")


class AppActions:
    def __init__(self,
                 update_media_frame_callback=placeholder_callback,  # For displaying images/videos in the media frame
                 update_lesson_content_callback=placeholder_callback,  # For updating the current lesson content
                 update_progress_callback=placeholder_callback,  # For tracking learning progress
                 update_vocabulary_callback=placeholder_callback,  # For updating vocabulary lists
                 update_grammar_exercises_callback=placeholder_callback,  # For updating grammar exercises
                 update_conversation_callback=placeholder_callback,  # For conversation practice
                 update_listening_exercise_callback=placeholder_callback,  # For listening comprehension
                 update_writing_exercise_callback=placeholder_callback,  # For writing practice
                 update_cultural_context_callback=placeholder_callback,  # For cultural lessons
                 update_pronunciation_callback=placeholder_callback,  # For pronunciation practice
                 update_reading_exercise_callback=placeholder_callback,  # For reading comprehension
                 update_situational_dialogue_callback=placeholder_callback,  # For situational dialogues
                 update_visual_vocabulary_callback=placeholder_callback,  # For visual vocabulary builder
                 show_feedback_callback=placeholder_callback,  # For showing user feedback
                 show_error_callback=placeholder_callback,  # For showing error messages
                 shutdown_callback=placeholder_callback,  # For application shutdown
                 open_translations_callback=placeholder_callback,  # For opening the translations window
                 ):
        # Media and content display
        self.update_media_frame = update_media_frame_callback
        self.update_lesson_content = update_lesson_content_callback
        
        # Progress tracking
        self.update_progress = update_progress_callback
        
        # Learning activity callbacks
        self.update_vocabulary = update_vocabulary_callback
        self.update_grammar_exercises = update_grammar_exercises_callback
        self.update_conversation = update_conversation_callback
        self.update_listening_exercise = update_listening_exercise_callback
        self.update_writing_exercise = update_writing_exercise_callback
        self.update_cultural_context = update_cultural_context_callback
        self.update_pronunciation = update_pronunciation_callback
        self.update_reading_exercise = update_reading_exercise_callback
        self.update_situational_dialogue = update_situational_dialogue_callback
        self.update_visual_vocabulary = update_visual_vocabulary_callback
        
        # UI feedback
        self.show_feedback = show_feedback_callback
        self.show_error = show_error_callback
        
        # Application control
        self.shutdown = shutdown_callback
        
        # Window management
        self.open_translations = open_translations_callback

